# Data card

## Synthetic demo

20 products, one location, 730 calendar days, seed 42. End date 27 October 2026. Product names, prices, demand patterns, procurement costs, current stock and lead times are synthetic. Historical sales assume available stock; they are not an inventory-ledger replay. The independent inventory simulator creates separate seeded latent demand with a mid-scenario spike and censors each policy's observations at its own available stock.

The generator is deterministic for its configuration. Performance on this generator does not prove transfer to another retailer or demand process.

## UCI Online Retail

Source: [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail).

Attribution: Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. DOI: 10.24432/C5BW33. CC BY 4.0. The code's MIT license does not replace the dataset's license.

Original source: UK non-store online retailer, with many wholesale customers, 1 December 2010 through 9 December 2011. Currency: GBP. This is historical transaction data, not current retail operations.

Transformations:

- Keep positive-quantity, positive-price physical-product transactions.
- Count and exclude cancellations/returns from the gross-positive-sales forecasting target; the current app does not publish a separate returns ledger.
- Exclude service/nonstandard product codes through a documented five-digit-plus-optional-letter pattern.
- Discard customer IDs and country; create one logical online location.
- Select the top 20 products by positive units in the first 180 days. Later sales do not choose the cohort.
- Aggregate daily units and sales-value-weighted prices.
- Discard the incomplete final export day.
- Under the complete-export assumption, fill transaction-free calendar days with zero sales. This does not establish that a product was active or in stock; the assumption can bias demand estimates.
- Store raw-file hash, selection cutoff, exclusions and transformation assumptions in dataset metadata.

No procurement costs, supplier lead times, real stock availability, historical lost demand or inventory outcomes are supplied. The adapter leaves costs/stock absent. User-entered scenario assumptions are required for inventory simulation. Historical sales replay cannot recover unobserved demand.

## User CSV

UTF-8; maximum 10 MB, 100,000 rows, 100 product-location series and ten years per file. Dates must be within 1900–2100. Required daily columns are date, sku, units_sold and unit_price. Dates must be ISO; quantities are nonnegative integers; currency is selected once per dataset. Returns are not negative demand and must be prepared separately. The import preview rejects duplicates and malformed rows before an atomic commit. An identical file cannot be reinterpreted under another currency. Unknown dates remain unknown and can make a series ineligible for forecasting. No real customer information is required.
