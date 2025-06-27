import frappe

def execute():
    frappe.db.sql("""
        UPDATE `tabWork Order` t1 SET t1.total_quantity = (
            SELECT IFNULL(SUM(t2.quantity), 0) FROM `tabWork Order Calculated Item` t2 WHERE t2.parent = t1.name
        )
    """)
    frappe.db.sql("""
        UPDATE `tabWork Order` t1 SET t1.total_no_of_pieces_delivered = (
            SELECT IFNULL(SUM(t2.delivered_quantity), 0) FROM `tabWork Order Calculated Item` t2 WHERE t2.parent = t1.name
        )
    """)
    frappe.db.sql("""
        UPDATE `tabWork Order` t1 SET t1.total_no_of_pieces_received = (
            SELECT IFNULL(SUM(t2.received_qty), 0) FROM `tabWork Order Calculated Item` t2 WHERE t2.parent = t1.name
        )
    """)