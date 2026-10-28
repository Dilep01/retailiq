# Model card

Task: daily gross-positive sales forecasting for each product/location, at horizons 1–28. Sales are an imperfect demand proxy when stock availability is unknown.

Baseline: repeat the final observed seven-day pattern at the forecast origin. Candidate: pooled `HistGradientBoostingRegressor`, 65 iterations, 15 maximum leaves, learning rate .08, L2 regularization 2, seed 42, random early stopping disabled. No GPU or external model service is used.

Features: last sales, 7/14-day lag positions, trailing 7/28-day means, 28-day standard deviation, zero-sales fraction, recent trend difference, horizon, target weekday and target month sine/cosine. Product identifiers and future prices/promotions are excluded. The pool shares patterns across series through their historical sales features.

Training examples use origin history only and require target dates on/before the fold cutoff. Recent input windows require 28 observed daily values for ML; seasonal naive requires seven. Missing recent ML history falls back to the baseline where possible; stale/incomplete baseline windows are skipped and recorded. Training uses at most 420 historical days, origin stride seven, and a 250,000-example cap.

Evaluation: three expanding calendar cutoffs with 28-day future validation windows. Mean validation MAE selects the candidate or baseline. The final historical 28 days are evaluated after selection. Each model is then refit through the dataset end to publish a future forecast. Repeated developer runs reuse the same holdout; reported runs are not independent prospective validations.

Intervals: estimate normalized residual P10/P90 on the validation folds, scaling by the origin's trailing mean (minimum scale one). Publish nonnegative daily bounds and report empirical held-out coverage, mean width and pinball loss. These are approximate marginal prediction intervals. Temporal dependence, limited samples and distribution changes weaken calibration. Sums of daily bounds are not cumulative-demand quantiles.

Each run saves dataset checksum, origin, feature version, package versions, Python version, source digest and a local trusted joblib artifact/checksum. Artifacts are never accepted from uploads. Metrics and interval coverage must be interpreted alongside series eligibility and source assumptions.

See EVALUATION.md for observed results. In particular, public-data absolute errors remain large despite baseline improvement. Intended use is local analysis and learning, followed by planner review. It does not establish reliable production demand or automatic procurement.
