import frappe

def execute():
    frappe.db.sql(
        """update `tabStock Ledger Entry` 
        set posting_datetime = timestamp(posting_date, posting_time)
        where 1 = 1;"""
    )