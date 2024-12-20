import frappe

def execute():
    frappe.db.sql("update `tabGoods Received Note` set `posting_date` = `grn_date`, `posting_time` = TIME(`creation`)")
    pass