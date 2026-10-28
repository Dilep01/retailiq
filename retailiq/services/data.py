import csv
import hashlib
import io
import math
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import numpy as np
import pandas as pd
from django.db import transaction
from retailiq.models import Dataset, Product, Location, Sale, Stock, ImportBatch

CATALOG = [
    ("Oat milk · original", "Dairy & alternatives", 145),
    ("House blend coffee", "Pantry", 320),
    ("Sourdough loaf", "Bakery", 180),
    ("Greek yogurt", "Dairy & alternatives", 95),
    ("Organic bananas", "Fresh produce", 65),
    ("Sea salt crackers", "Pantry", 110),
    ("Cold brew concentrate", "Beverages", 260),
    ("Almond butter", "Pantry", 390),
    ("Sparkling water", "Beverages", 55),
    ("Dark chocolate 70%", "Pantry", 155),
    ("Avocado · pack of 2", "Fresh produce", 220),
    ("Granola · honey & nuts", "Pantry", 285),
    ("Free-range eggs", "Dairy & alternatives", 135),
    ("Green tea · jasmine", "Beverages", 195),
    ("Olive oil · extra virgin", "Pantry", 640),
    ("Croissant · butter", "Bakery", 85),
    ("Pasta · fusilli", "Pantry", 120),
    ("Tomato passata", "Pantry", 175),
    ("Seasonal fruit box", "Fresh produce", 350),
    ("Kombucha · ginger", "Beverages", 190),
]


@transaction.atomic
def seed_demo(seed=42, days=730, count=20, locations=1):
    if not 210 <= days <= 1460 or not 1 <= count <= 50 or not 1 <= locations <= 2:
        raise ValueError("Use 210–1460 days, 1–50 products and 1–2 locations.")
    checksum = hashlib.sha256(f"demo-v1-{seed}-{days}-{count}-{locations}".encode()).hexdigest()
    existing = Dataset.objects.filter(checksum=checksum).first()
    if existing:
        return existing
    rng = np.random.default_rng(seed)
    end = date(2026, 10, 27)
    start = end - timedelta(days=days - 1)
    ds = Dataset.objects.create(
        name="The everyday market",
        source_kind="synthetic",
        checksum=checksum,
        start_date=start,
        end_date=end,
        metadata={
            "seed": seed,
            "generator": "v1",
            "assumptions": "All sales, stock, costs and suppliers are synthetic.",
        },
    )
    locs = [Location.objects.create(dataset=ds, name=["Indiranagar", "Koramangala"][i]) for i in range(locations)]
    sales = []
    for i in range(count):
        name, category, price = CATALOG[i % len(CATALOG)]
        if i >= 20:
            name += f" · variant {i // 20 + 1}"
        product = Product.objects.create(
            dataset=ds,
            sku=f"RIQ-{1001 + i}",
            name=name,
            category=category,
            price=price,
            unit_cost=Decimal(str(round(price * 0.61, 2))),
            lead_time=3 + i % 5,
            pack_size=6 if i % 3 else 12,
            moq=6,
        )
        for loc in locs:
            base = 9 + (20 - i % 20) * 1.4
            values = []
            for t in range(days):
                d = start + timedelta(days=t)
                level = base * (1 + 0.18 * math.sin(2 * math.pi * d.weekday() / 7)) * (1 + 0.18 * t / days)
                level *= 1.30 if d.weekday() in (5, 6) else 1
                units = int(rng.poisson(max(0.1, level)))
                if i % 9 == 8 and rng.random() < 0.68:
                    units = 0
                values.append(units)
                sales.append(Sale(product=product, location=loc, date=d, units=units, price=price))
            # Snapshot is a distinct scenario input, not inferred real inventory.
            coverage = [2, 4, 14, 3, 9, 21, 5, 11][i % 8]
            Stock.objects.create(
                product=product,
                location=loc,
                as_of=end,
                on_hand=int(np.mean(values[-28:]) * coverage),
                on_order=24 if i % 4 == 0 else 0,
                assumptions=True,
            )
    Sale.objects.bulk_create(sales, batch_size=1000)
    return ds


def sales_frame(dataset):
    rows = Sale.objects.filter(product__dataset=dataset).values(
        "product_id", "location_id", "date", "units", "price", "observed"
    )
    frame = pd.DataFrame.from_records(rows)
    if frame.empty:
        raise ValueError("This dataset contains no sales.")
    frame["date"] = pd.to_datetime(frame["date"])
    frame["price"] = frame["price"].astype(float)
    return frame.sort_values(["product_id", "location_id", "date"]).reset_index(drop=True)


def validate_csv(content):
    if len(content) > 10 * 1024 * 1024:
        return [], ["File exceeds the 10 MB limit."]
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        required = {"date", "sku", "units_sold", "unit_price"}
        if not required.issubset(reader.fieldnames or []):
            return [], ["Required columns: date, sku, units_sold, unit_price."]
        rows, errors, seen = [], [], set()
        for number, row in enumerate(reader, 2):
            if number > 100001:
                return [], ["File exceeds 100,000 data rows."]
            try:
                d = date.fromisoformat(row["date"])
                if not date(1900, 1, 1) <= d <= date(2100, 12, 31):
                    raise ValueError("dates must fall between 1900 and 2100")
                sku = row["sku"].strip()
                loc = (row.get("location") or "Main store").strip()
                units = int(row["units_sold"])
                price = Decimal(row["unit_price"])
                status = row.get("observation_status", "observed") or "observed"
                if not sku or len(sku) > 60 or not loc or len(loc) > 80:
                    raise ValueError("SKU/location is missing or too long")
                if units < 0 or units > 1000000 or not price.is_finite() or not 0 <= price <= 10000000:
                    raise ValueError("invalid nonnegative quantity or price")
                if status not in ["observed", "missing", "closed"]:
                    raise ValueError("observation_status must be observed, missing or closed")
                key = (sku, loc, str(d))
                if key in seen:
                    raise ValueError("duplicate date/SKU/location")
                seen.add(key)
                rows.append(
                    {
                        "date": str(d),
                        "sku": sku,
                        "location": loc,
                        "units": units,
                        "price": str(price.quantize(Decimal(".01"))),
                        "name": (row.get("name") or sku)[:160],
                        "category": (row.get("category") or "General")[:60],
                        "observed": status == "observed",
                    }
                )
            except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
                errors.append(f"Row {number}: {exc}")
                if len(errors) >= 50:
                    break
        if not rows and not errors:
            errors.append("The file contains no data rows.")
        if rows:
            dates = [date.fromisoformat(r["date"]) for r in rows]
            if (max(dates) - min(dates)).days > 3660:
                errors.append("A local dataset may span at most ten years.")
            if len({(r["sku"], r["location"]) for r in rows}) > 100:
                errors.append("A local dataset may contain at most 100 product-location series.")
        return rows, errors
    except (UnicodeDecodeError, csv.Error) as exc:
        return [], [f"Cannot read UTF-8 CSV: {exc}"]


def preview_import(name, content, currency="INR"):
    if currency not in ["INR", "GBP", "USD", "EUR"]:
        raise ValueError("Unsupported currency.")
    rows, errors = validate_csv(content)
    return ImportBatch.objects.create(
        name=name[:160], rows=rows, errors=errors, currency=currency, checksum=hashlib.sha256(content).hexdigest()
    )


@transaction.atomic
def commit_batch(batch):
    if batch.errors or not batch.rows:
        raise ValueError("Fix validation errors before importing.")
    ds = Dataset.objects.filter(checksum=batch.checksum).first()
    if ds is not None and ds.currency != batch.currency:
        raise ValueError(
            "This exact file was already imported with a different currency. Correct the source instead of relabeling it."
        )
    if ds is None:
        dates = [row["date"] for row in batch.rows]
        ds = Dataset.objects.create(
            name=batch.name,
            source_kind="uploaded",
            currency=batch.currency,
            checksum=batch.checksum,
            start_date=min(dates),
            end_date=max(dates),
            metadata={
                "missing_policy": "Unreported dates remain unknown; forecasts require a complete recent daily window."
            },
        )
        prods, locs, sales = {}, {}, []
        for row in batch.rows:
            if row["sku"] not in prods:
                prods[row["sku"]] = Product.objects.create(
                    dataset=ds, sku=row["sku"], name=row["name"], category=row["category"], price=row["price"]
                )
            if row["location"] not in locs:
                locs[row["location"]] = Location.objects.create(dataset=ds, name=row["location"])
            sales.append(
                Sale(
                    product=prods[row["sku"]],
                    location=locs[row["location"]],
                    date=row["date"],
                    units=row["units"],
                    price=row["price"],
                    observed=row["observed"],
                )
            )
        Sale.objects.bulk_create(sales, batch_size=1000)
    batch.dataset = ds
    batch.save(update_fields=["dataset"])
    return ds
