"""Generate tiny synthetic import fixtures without using the live database."""

import csv
from datetime import date, timedelta
from pathlib import Path


folder = Path(__file__).resolve().parent.parent / "data/samples"
folder.mkdir(parents=True, exist_ok=True)
with (folder / "daily-sales.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream)
    writer.writerow(["date", "sku", "name", "category", "location", "units_sold", "unit_price", "observation_status"])
    for i in range(240):
        day = date(2026, 1, 1) + timedelta(days=i)
        for sku, name, price, base in [("DEMO-01", "Oat milk", 145, 12), ("DEMO-02", "Coffee", 320, 8)]:
            writer.writerow([str(day), sku, name, "Sample", "Main store", base + (i % 7) * 2, price, "observed"])
(folder / "invalid-sales.csv").write_text(
    "date,sku,units_sold,unit_price\n2026-01-01,A,-2,145\nnot-a-date,A,4,145\n", encoding="utf-8"
)
