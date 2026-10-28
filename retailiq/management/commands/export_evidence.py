import json
import platform
from django.conf import settings
from django.core.management.base import BaseCommand
from retailiq.models import Dataset, ForecastRun, Simulation, Plan, Sale


class Command(BaseCommand):
    help = "Export shareable evaluation summaries, excluding users, secrets and customer data."

    def handle(self, **options):
        folder = settings.BASE_DIR / "docs/evidence"
        folder.mkdir(parents=True, exist_ok=True)
        report = {"platform": platform.platform(), "python": platform.python_version(), "datasets": []}
        lines = [
            "# Measured evaluation results",
            "",
            "Generated from completed local runs. Historical test blocks are reused on reruns; these are not independent prospective trials.",
            "",
        ]
        for ds in Dataset.objects.order_by("id"):
            run = ForecastRun.objects.filter(dataset=ds).last()
            if not run:
                continue
            entry = {
                "name": ds.name,
                "source": ds.source_kind,
                "currency": ds.currency,
                "rows": Sale.objects.filter(product__dataset=ds).count(),
                "start": str(ds.start_date),
                "end": str(ds.end_date),
                "checksum": ds.checksum,
                "source_metadata": ds.metadata,
                "model": run.model_name,
                "run_id": run.id,
                "manifest": run.metadata,
                "evaluation": run.evaluation,
            }
            # Local absolute paths and credentials are never exported.
            entry["manifest"] = {k: v for k, v in entry["manifest"].items() if k != "artifact_path"}
            simulations = list(Simulation.objects.filter(dataset=ds).values("id", "params", "results"))
            entry["simulations"] = [
                {"id": s["id"], "params": s["params"], "policies": s["results"]["policies"]} for s in simulations
            ]
            plan = Plan.objects.filter(dataset=ds).last()
            if plan:
                entry["plan"] = plan.summary
            report["datasets"].append(entry)
            ev = run.evaluation
            lines += [
                f"## {ds.name}",
                "",
                f"Source: **{ds.source_kind}**. {entry['rows']:,} daily rows. Currency: {ds.currency}.",
                "",
                f"Holdout: after {ev['test_cutoff']} through {ev['test_end']}. {ev['eligible_series']} forecast series.",
                "",
                "| Model | MAE (units/day) | RMSE | WAPE |",
                "| --- | ---: | ---: | ---: |",
            ]
            for name, key in [("Seasonal naive", "baseline"), ("Pooled gradient boosting", "ml")]:
                result = ev.get(key)
                if result:
                    wape = f"{result['wape'] * 100:.2f}%" if result["wape"] is not None else "undefined"
                    lines.append(f"| {name} | {result['mae']:.2f} | {result['rmse']:.2f} | {wape} |")
            lines += [
                "",
                f"Selected on earlier validation: **{run.model_name}**. Approximate daily interval coverage: {ev['interval']['test_coverage']:.1%} versus 80% nominal. Full run elapsed: {ev['elapsed_seconds']} seconds on this machine.",
                "",
            ]
            if ds.source_kind == "public":
                lines += [
                    "UCI sales are irregular and include wholesale behavior. Large remaining errors limit operational usefulness. Stock availability, real procurement costs, and lead times are absent. No real stockout-reduction claim is supported.",
                    "",
                ]
            for sim in entry["simulations"]:
                lines += [
                    f"### Simulation {sim['id']}: {sim['params']['days']} days, budget {sim['params']['budget']:,.0f} per review",
                    "",
                    "| Policy | Unit fill rate | Mean comparison cost | Mean ending stock |",
                    "| --- | ---: | ---: | ---: |",
                ]
                for row in sim["policies"]:
                    fill = f"{row['fill_rate']:.1%}" if row["fill_rate"] is not None else "undefined"
                    lines.append(
                        f"| {row['policy']} | {fill} | {row['comparison_cost']:,.0f} | {row['ending_stock']:,.0f} |"
                    )
                lines += [
                    "",
                    "Simulation only. Cost excludes procurement spend and has no salvage credit. Equal budget shares, assumed costs, and ending stock affect comparisons.",
                    "",
                ]
        (folder / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (settings.BASE_DIR / "docs/EVALUATION.md").write_text("\n".join(lines), encoding="utf-8")
        self.stdout.write("Saved docs/EVALUATION.md and docs/evidence/evaluation.json")
