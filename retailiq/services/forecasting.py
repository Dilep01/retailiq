import hashlib
import importlib.metadata
import json
import platform
import time
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.db import transaction
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from retailiq.models import ForecastRun, ForecastPoint
from .data import sales_frame


def metrics(actual, predicted):
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if len(a) == 0:
        return {"mae": None, "rmse": None, "wape": None, "bias": None, "n": 0}
    denom = float(a.sum())
    return {
        "mae": round(float(np.mean(np.abs(a - p))), 4),
        "rmse": round(float(np.sqrt(np.mean((a - p) ** 2))), 4),
        "wape": round(float(np.abs(a - p).sum() / denom), 5) if denom else None,
        "bias": round(float((p - a).sum() / denom), 5) if denom else None,
        "n": len(a),
    }


def seasonal(history, horizon=28):
    y = np.asarray(history, dtype=float)
    if len(y) < 7 or not np.isfinite(y[-7:]).all():
        raise ValueError("At least seven complete recent days are required.")
    return np.tile(y[-7:], int(np.ceil(horizon / 7)))[:horizon]


def features(history, origin, horizon):
    """History ends at origin; no target-period observations are used."""
    y = np.asarray(history, dtype=float)
    if len(y) < 28 or not np.isfinite(y[-28:]).all():
        raise ValueError("28 complete observed days are required for ML features.")
    target = pd.Timestamp(origin) + pd.Timedelta(days=int(horizon))
    return [
        y[-1],
        y[-7],
        y[-14],
        np.mean(y[-7:]),
        np.mean(y[-28:]),
        np.std(y[-28:]),
        np.mean(y[-28:] == 0),
        np.mean(y[-7:]) - np.mean(y[-28:]),
        horizon,
        np.sin(2 * np.pi * target.weekday() / 7),
        np.cos(2 * np.pi * target.weekday() / 7),
        np.sin(2 * np.pi * target.month / 12),
        np.cos(2 * np.pi * target.month / 12),
    ]


def series_map(frame):
    result = {}
    for key, group in frame.groupby(["product_id", "location_id"]):
        s = group.set_index("date")["units"].astype(float)
        s.loc[~group.set_index("date")["observed"]] = np.nan
        result[tuple(int(x) for x in key)] = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))
    return result


def training_rows(series, cutoff, horizon=28):
    xs, ys, target_dates = [], [], []
    for s in series.values():
        past = s.loc[:cutoff].iloc[-420:]
        values = past.to_numpy()
        for i in range(27, len(values) - 1, 7):
            if not np.isfinite(values[max(0, i - 27) : i + 1]).all():
                continue
            for h in range(1, min(horizon, len(values) - i - 1) + 1):
                if not np.isfinite(values[i + h]):
                    continue
                xs.append(features(values[: i + 1], past.index[i], h))
                ys.append(values[i + h])
                target_dates.append(past.index[i + h])
    if len(xs) > 250000:
        raise ValueError("Training exceeds 250,000 examples. Reduce products/history.")
    return np.asarray(xs), np.asarray(ys), target_dates


def fit_model(series, cutoff):
    x, y, dates = training_rows(series, cutoff)
    if len(y) < 100:
        raise ValueError("Not enough complete training examples for ML.")
    assert max(dates) <= pd.Timestamp(cutoff)
    model = HistGradientBoostingRegressor(
        max_iter=65, max_leaf_nodes=15, learning_rate=0.08, l2_regularization=2, early_stopping=False, random_state=42
    )
    with threadpool_limits(limits=2):
        model.fit(x, y)
    return model


def predict_series(series, cutoff, model=None, horizon=28):
    predictions, skipped, fallback = {}, [], []
    for key, s in series.items():
        history = s.loc[:cutoff]
        # A series ending before the origin is stale, not a sequence of zero sales.
        if history.empty or history.index[-1] != pd.Timestamp(cutoff):
            skipped.append(list(key))
            continue
        try:
            baseline = seasonal(history, horizon)
            if model is not None:
                try:
                    x = np.array([features(history, cutoff, h) for h in range(1, horizon + 1)])
                    with threadpool_limits(limits=2):
                        prediction = np.maximum(0, model.predict(x))
                except ValueError:
                    fallback.append(list(key))
                    prediction = baseline
            else:
                prediction = baseline
            predictions[key] = prediction
        except ValueError:
            skipped.append(list(key))
    return predictions, skipped, fallback


def evaluate_at(series, cutoff, model=None, horizon=28):
    predictions, skipped, fallback = predict_series(series, cutoff, model, horizon)
    actual, pred, per_series, errors = [], [], [], []
    for key, p in predictions.items():
        s = series[key]
        a = s.reindex(pd.date_range(pd.Timestamp(cutoff) + pd.Timedelta(days=1), periods=horizon)).to_numpy()
        mask = np.isfinite(a)
        actual.extend(a[mask].tolist())
        pred.extend(p[mask].tolist())
        scale = max(1.0, float(s.loc[:cutoff].iloc[-28:].mean()))
        errors.extend(((a[mask] - p[mask]) / scale).tolist())
        per_series.append({"product_id": key[0], "location_id": key[1], **metrics(a[mask], p[mask])})
    return {
        "metrics": metrics(actual, pred),
        "per_series": per_series,
        "skipped": skipped,
        "fallback": fallback,
        "errors": errors,
    }


def run_forecast(dataset, include_ml=True):
    started = time.perf_counter()
    series = series_map(sales_frame(dataset))
    end = pd.Timestamp(dataset.end_date)
    if (end - pd.Timestamp(dataset.start_date)).days < 180:
        raise ValueError("Backtesting needs at least 181 calendar days. Import more history.")
    validation, baseline_errors, ml_errors = [], [], []
    for offset in [112, 84, 56]:
        cutoff = end - pd.Timedelta(days=offset)
        baseline = evaluate_at(series, cutoff)
        candidate = evaluate_at(series, cutoff, fit_model(series, cutoff)) if include_ml else None
        baseline_errors.extend(baseline["errors"])
        if candidate:
            ml_errors.extend(candidate["errors"])
        validation.append(
            {
                "cutoff": str(cutoff.date()),
                "baseline": baseline["metrics"],
                "ml": candidate["metrics"] if candidate else None,
            }
        )
    base_score = np.mean([v["baseline"]["mae"] for v in validation if v["baseline"]["mae"] is not None])
    ml_scores = [v["ml"]["mae"] for v in validation if v["ml"] and v["ml"]["mae"] is not None]
    chosen = "pooled_gradient_boosting" if ml_scores and np.mean(ml_scores) < base_score else "seasonal_naive"
    cutoff = end - pd.Timedelta(days=28)
    # Holdout is evaluated only after selecting on validation. Retesting is recorded per run.
    test_base = evaluate_at(series, cutoff)
    test_ml = evaluate_at(series, cutoff, fit_model(series, cutoff)) if include_ml else None
    errors = ml_errors if chosen == "pooled_gradient_boosting" else baseline_errors
    if not errors:
        raise ValueError("No valid validation targets. Check missing observations.")
    low, high = [float(v) for v in np.quantile(errors, [0.1, 0.9])]
    chosen_test = test_ml if chosen == "pooled_gradient_boosting" else test_base
    test_model = fit_model(series, cutoff) if chosen == "pooled_gradient_boosting" else None
    test_predictions, _, _ = predict_series(series, cutoff, test_model)
    covered, total, widths, pinball_low, pinball_high = 0, 0, [], [], []
    for key, p in test_predictions.items():
        scale = max(1.0, float(series[key].loc[:cutoff].iloc[-28:].mean()))
        a = series[key].reindex(pd.date_range(cutoff + pd.Timedelta(days=1), periods=28)).to_numpy()
        mask = np.isfinite(a)
        lo, hi = np.maximum(0, p + low * scale), np.maximum(0, p + high * scale)
        covered += int(((a[mask] >= lo[mask]) & (a[mask] <= hi[mask])).sum())
        total += int(mask.sum())
        widths.extend((hi - lo).tolist())
        for q, bound, bucket in [(0.1, lo, pinball_low), (0.9, hi, pinball_high)]:
            err = a[mask] - bound[mask]
            bucket.extend(np.maximum(q * err, (q - 1) * err).tolist())
    final_model = fit_model(series, end) if chosen == "pooled_gradient_boosting" else None
    predictions, skipped, fallback = predict_series(series, end, final_model)
    if not predictions:
        raise ValueError("No series has seven complete days at the dataset origin.")
    packages = {p: importlib.metadata.version(p) for p in ["Django", "numpy", "pandas", "scikit-learn"]}
    evaluation = {
        "validation": validation,
        "test_cutoff": str(cutoff.date()),
        "test_end": str(end.date()),
        "baseline": test_base["metrics"],
        "ml": test_ml["metrics"] if test_ml else None,
        "selected": chosen_test["metrics"],
        "per_series": chosen_test["per_series"],
        "interval": {
            "method": "validation-normalized residual P10/P90; approximate marginal intervals",
            "nominal_coverage": 0.8,
            "test_coverage": covered / total if total else None,
            "mean_width": float(np.mean(widths)),
            "residual_quantiles": [low, high],
            "pinball_p10": float(np.mean(pinball_low)),
            "pinball_p90": float(np.mean(pinball_high)),
        },
        "eligible_series": len(predictions),
        "skipped_series": skipped,
        "fallback_series": fallback,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    manifest = {
        "dataset_checksum": dataset.checksum,
        "python": platform.python_version(),
        "packages": packages,
        "seed": 42,
        "feature_version": "origin-v1",
        "interval_limitation": "Marginal daily intervals cannot be summed into an aggregate quantile.",
        "training_target_guard": "target_date <= fold_cutoff",
        "test_reuse": "Every rerun reuses this historical holdout; not fresh independent evidence.",
    }
    code = b"".join(
        p.read_bytes() for p in sorted((settings.BASE_DIR / "retailiq").rglob("*.py")) if "migrations" not in str(p)
    )
    manifest["source_sha256"] = hashlib.sha256(code).hexdigest()
    manifest["configuration_hash"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    directory = settings.BASE_DIR / "artifacts/models"
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / f"{manifest['configuration_hash']}.joblib"
    temporary = Path(str(artifact) + ".tmp")
    joblib.dump({"model": final_model, "model_name": chosen, "feature_version": "origin-v1"}, temporary)
    temporary.replace(artifact)
    manifest["artifact_path"] = str(artifact.relative_to(settings.BASE_DIR))
    manifest["artifact_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    with transaction.atomic():
        run = ForecastRun.objects.create(
            dataset=dataset, origin=dataset.end_date, model_name=chosen, metadata=manifest, evaluation=evaluation
        )
        points = []
        for (pid, lid), values in predictions.items():
            scale = max(1.0, float(series[(pid, lid)].iloc[-28:].mean()))
            for h, p in enumerate(values, 1):
                points.append(
                    ForecastPoint(
                        run=run,
                        product_id=pid,
                        location_id=lid,
                        date=dataset.end_date + timedelta(days=h),
                        prediction=float(p),
                        lower=float(max(0, p + low * scale)),
                        upper=float(max(0, p + high * scale)),
                    )
                )
        ForecastPoint.objects.bulk_create(points)
    return run
