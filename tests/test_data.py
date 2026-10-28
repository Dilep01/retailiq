from decimal import Decimal
import pytest
from retailiq.models import Dataset, Sale
from retailiq.services.data import validate_csv, preview_import, commit_batch, seed_demo


def csv_bytes(rows="2026-01-01,A,12,2.50\n"):
    return ("date,sku,units_sold,unit_price\n" + rows).encode()


@pytest.mark.parametrize(
    "row",
    [
        "bad,A,12,2.5\n",
        "2026-01-01,A,-1,2.5\n",
        "2026-01-01,A,2,NaN\n",
        "2026-01-01,,2,2.5\n",
        "2026-01-01,A,2,-1\n",
        "2026-01-01,A,1.1,2\n",
        "2026-01-01,A,1000001,1\n",
    ],
)
def test_bad_rows(row):
    rows, errors = validate_csv(csv_bytes(row))
    assert errors and not rows


def test_missing_header_and_empty():
    assert validate_csv(b"hello,world\n")[1]
    assert validate_csv(csv_bytes(""))[1]


def test_duplicate_and_zero():
    rows, errors = validate_csv(csv_bytes("2026-01-01,A,0,2.50\n2026-01-01,A,0,2.50\n"))
    assert rows[0]["units"] == 0 and "duplicate" in errors[0]


@pytest.mark.django_db
def test_idempotent_import():
    a = preview_import("valid", csv_bytes())
    first = commit_batch(a)
    second = commit_batch(preview_import("repeat", csv_bytes()))
    assert first.pk == second.pk
    assert Sale.objects.count() == 1
    assert Sale.objects.get().price == Decimal("2.50")


@pytest.mark.django_db
def test_atomic_rejection():
    batch = preview_import("broken", csv_bytes("2026-01-01,A,12,2.50\nbad,B,1,2\n"))
    with pytest.raises(ValueError):
        commit_batch(batch)
    assert Dataset.objects.count() == 0


def test_missing_is_not_zero(db):
    batch = preview_import("unknown", b"date,sku,units_sold,unit_price,observation_status\n2026-01-01,A,0,2,missing\n")
    commit_batch(batch)
    assert not Sale.objects.get().observed


def test_seed_reproducibility(dataset):
    again = seed_demo(seed=123, days=240, count=3)
    assert again.pk == dataset.pk
    assert Sale.objects.count() == 720


def test_date_and_series_resource_bounds():
    assert validate_csv(csv_bytes("0001-01-01,A,1,2\n"))[1]
    assert validate_csv(csv_bytes("2000-01-01,A,1,2\n2026-01-01,A,1,2\n"))[1]
    many = "".join(f"2026-01-01,SKU-{i},1,2\n" for i in range(101))
    assert validate_csv(csv_bytes(many))[1]


@pytest.mark.django_db
def test_currency_cannot_be_reinterpreted():
    commit_batch(preview_import("first", csv_bytes(), currency="INR"))
    with pytest.raises(ValueError, match="different currency"):
        commit_batch(preview_import("second", csv_bytes(), currency="GBP"))
