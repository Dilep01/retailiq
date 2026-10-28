# Measured evaluation results

Generated from completed local runs. Historical test blocks are reused on reruns; these are not independent prospective trials.

## The everyday market

Source: **synthetic**. 14,600 daily rows. Currency: INR.

Holdout: after 2026-09-29 through 2026-10-27. 20 forecast series.

| Model | MAE (units/day) | RMSE | WAPE |
| --- | ---: | ---: | ---: |
| Seasonal naive | 6.54 | 9.38 | 23.12% |
| Pooled gradient boosting | 5.01 | 6.58 | 17.71% |

Selected on earlier validation: **pooled_gradient_boosting**. Approximate daily interval coverage: 82.0% versus 80% nominal. Full run elapsed: 17.58 seconds on this machine.

### Simulation 1: 56 days, budget 25,000 per review

| Policy | Unit fill rate | Mean comparison cost | Mean ending stock |
| --- | ---: | ---: | ---: |
| fixed | 13.2% | 2,147,004 | 20 |
| seasonal | 13.2% | 2,147,004 | 20 |
| ml | 13.2% | 2,147,004 | 20 |

Simulation only. Cost excludes procurement spend and has no salvage credit. Equal budget shares, assumed costs, and ending stock affect comparisons.

### Simulation 2: 56 days, budget 750,000 per review

| Policy | Unit fill rate | Mean comparison cost | Mean ending stock |
| --- | ---: | ---: | ---: |
| fixed | 88.3% | 442,333 | 2,342 |
| seasonal | 89.3% | 424,945 | 3,083 |
| ml | 89.6% | 420,366 | 3,516 |

Simulation only. Cost excludes procurement spend and has no salvage credit. Equal budget shares, assumed costs, and ending stock affect comparisons.

## UCI Online Retail · 20 products

Source: **public**. 7,460 daily rows. Currency: GBP.

Holdout: after 2011-11-10 through 2011-12-08. 20 forecast series.

| Model | MAE (units/day) | RMSE | WAPE |
| --- | ---: | ---: | ---: |
| Seasonal naive | 109.27 | 272.53 | 117.48% |
| Pooled gradient boosting | 74.08 | 185.36 | 79.65% |

Selected on earlier validation: **pooled_gradient_boosting**. Approximate daily interval coverage: 80.9% versus 80% nominal. Full run elapsed: 13.5 seconds on this machine.

UCI sales are irregular and include wholesale behavior. Large remaining errors limit operational usefulness. Stock availability, real procurement costs, and lead times are absent. No real stockout-reduction claim is supported.
