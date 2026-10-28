import hashlib
import re
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import openpyxl
from django.db import transaction
from retailiq.models import Dataset, Product, Location, Sale


def import_uci(path, products=20):
    if not 1 <= products <= 50:
        raise ValueError("Choose 1–50 products.")
    path = Path(path)
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    checksum = hashlib.sha256(f"uci-v1-{source_hash}-{products}".encode()).hexdigest()
    existing = Dataset.objects.filter(checksum=checksum).first()
    if existing:
        return existing
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = book.active
    rows = sheet.iter_rows(values_only=True)
    headers = [str(x).strip() for x in next(rows)]
    records, counts, excluded = [], Counter(), Counter()
    for values in rows:
        row = dict(zip(headers, values, strict=True))
        code = str(row.get("StockCode") or "").strip()
        qty, price, stamp = row.get("Quantity"), row.get("UnitPrice"), row.get("InvoiceDate")
        if not stamp or qty is None or price is None:
            excluded["incomplete"] += 1
            continue
        if str(row.get("InvoiceNo", "")).upper().startswith("C") or qty < 0:
            excluded["returns_cancellations"] += 1
            continue
        if not re.fullmatch(r"\d{5}[A-Za-z]?", code) or qty <= 0 or price <= 0:
            excluded["service_or_invalid"] += 1
            continue
        records.append((stamp.date(), code, int(qty), float(price), str(row.get("Description") or code)[:160]))
    book.close()
    if not records:
        raise ValueError("No eligible positive physical-product transactions.")
    start = min(x[0] for x in records)
    end = max(x[0] for x in records) - timedelta(days=1)  # discard the incomplete final export day
    selection_end = start + timedelta(days=179)
    for day, code, qty, price, _ in records:
        if day <= selection_end:
            counts[code] += qty
    codes = {code for code, _ in counts.most_common(products)}
    totals, revenue, names, lastprice = defaultdict(int), defaultdict(float), {}, {}
    for day, code, qty, price, name in records:
        if code in codes and day <= end:
            totals[(day, code)] += qty
            revenue[(day, code)] += qty * price
            names[code] = name
            lastprice[code] = price
    return _persist_uci(
        start, end, source_hash, checksum, selection_end, products, codes, totals, revenue, names, lastprice, excluded
    )


@transaction.atomic
def _persist_uci(
    start, end, source_hash, checksum, selection_end, products, codes, totals, revenue, names, lastprice, excluded
):
    existing = Dataset.objects.filter(checksum=checksum).first()
    if existing:
        return existing
    ds = Dataset.objects.create(
        name=f"UCI Online Retail · {products} products",
        source_kind="public",
        currency="GBP",
        checksum=checksum,
        start_date=start,
        end_date=end,
        metadata={
            "source": "https://archive.ics.uci.edu/dataset/352/online+retail",
            "attribution": "Chen, D. (2015). Online Retail. UCI. DOI: 10.24432/C5BW33. CC BY 4.0.",
            "source_file_sha256": source_hash,
            "selection_cutoff": str(selection_end),
            "selection": "Top positive-unit SKUs in the first 180 days only.",
            "zero_policy": "Assume complete transaction export; no transaction = zero sales within the export calendar. Stock availability is unknown.",
            "excluded": dict(excluded),
            "final_day": "Incomplete final export day excluded.",
            "inventory": "No inventory, procurement cost or supplier inputs supplied by UCI.",
        },
    )
    loc = Location.objects.create(dataset=ds, name="Online retail")
    sales = []
    for code in sorted(codes):
        product = Product.objects.create(
            dataset=ds,
            sku=code,
            name=names[code],
            category="UCI gifts",
            price=Decimal(str(lastprice[code])).quantize(Decimal(".01")),
        )
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            qty = totals[(day, code)]
            price = revenue[(day, code)] / qty if qty else lastprice[code]
            # Price on zero-sales days is display-only, never a forecast feature.
            sales.append(
                Sale(
                    product=product,
                    location=loc,
                    date=day,
                    units=qty,
                    price=Decimal(str(price)).quantize(Decimal(".01")),
                )
            )
    Sale.objects.bulk_create(sales, batch_size=1000)
    return ds
