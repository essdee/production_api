import frappe
from production_api.mrp_stock.doctype.fg_stock_entry.fg_stock_entry import get_inward_stock, get_outward_stock

@frappe.whitelist()
def get_inward_stock_entry_details(item, warehouselist=[], start_date = None, end_date = None):
    return get_inward_stock(item, warehouselist, start_date = start_date, end_date = end_date)

@frappe.whitelist()
def get_outward_stock_entry_details(item, warehouselist=[], start_date = None, end_date = None):
    return get_outward_stock(item, warehouselist, start_date = start_date, end_date = end_date)