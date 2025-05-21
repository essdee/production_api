import frappe

def execute():

    frappe.db.sql("""
        UPDATE `tabStock Ledger Entry` t1 JOIN `tabFG Stock Entry Detail` t2
        ON t1.voucher_detail_no = t2.name AND t2.parent=t1.voucher_no
        SET t1.uom = t2.stock_uom
    """)