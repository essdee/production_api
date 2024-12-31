import frappe
from production_api.mrp_stock.doctype.fg_stock_entry.fg_stock_entry import get_inward_stock

@frappe.whitelist()
def get_inward_stock_entry_details(item, warehouselist=[]):
    return get_inward_stock(item, warehouselist)