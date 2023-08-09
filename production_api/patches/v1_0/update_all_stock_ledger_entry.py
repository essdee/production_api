import frappe
from production_api.mrp_stock.stock_ledger import update_entries_after

def execute():
    sl_entries = frappe.get_all("Stock Ledger Entry", filters={"is_cancelled": 0})
    for s in sl_entries:
        sle = frappe.get_doc("Stock Ledger Entry")
        update_entries_after(
            {
                "item": sle.get("item"),
                "warehouse": sle.get("warehouse"),
                "lot": sle.get("lot"),
                "posting_date": sle.get("posting_date"),
                "posting_time": sle.get("posting_time"),
                "sle_id": sle.get("name"),
                "creation": sle.get("creation"),
            },
        )