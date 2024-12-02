import frappe
from production_api.mrp_stock.report.stock_balance.stock_balance import execute as get_stock_balance
from frappe.utils import today

def execute():
    _, data = get_stock_balance({
        "from_date": today(),
        "to_date": today(),
    })

    for d in data:
        bin_doc = frappe.new_doc("Bin")
        bin_doc.update({
            "item_code": d["item"],
            "warehouse": d["warehouse"],
            "lot": d["lot"],
            "actual_qty": d["bal_qty"],
            "reserved_qty": 0,
            "stock_uom": d["stock_uom"],
        })
        bin_doc.db_insert()