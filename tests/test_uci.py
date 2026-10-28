from datetime import datetime, timedelta
import openpyxl
from retailiq.models import Sale, Product
from retailiq.services.uci import import_uci


def test_public_adapter_and_training_only_selection(tmp_path, db):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(
        ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
    )
    for i in range(240):
        sheet.append([str(i), "12345", "Gift", 10, datetime(2011, 1, 1) + timedelta(days=i), 2.5, 123, "UK"])
    sheet.append(["late", "99999", "Future bestseller", 999999, datetime(2011, 8, 1), 3, 456, "UK"])
    sheet.append(["C10", "12345", "Gift", -3, datetime(2011, 2, 1), 2.5, 123, "UK"])
    sheet.append(["ship", "POST", "Postage", 1, datetime(2011, 2, 1), 2.5, 123, "UK"])
    path = tmp_path / "retail.xlsx"
    book.save(path)
    ds = import_uci(path, products=1)
    assert ds.source_kind == "public" and ds.currency == "GBP"
    assert Product.objects.get(dataset=ds).sku == "12345"
    assert Product.objects.get(dataset=ds).unit_cost is None
    assert ds.metadata["excluded"]["returns_cancellations"] == 1
    assert Sale.objects.filter(product__dataset=ds).count() == 239
    assert import_uci(path, products=1).id == ds.id
