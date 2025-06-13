import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabWork Order` t1
            JOIN (
                SELECT parent, SUM(quantity) AS total_qty
                FROM `tabWork Order Calculated Item`
                GROUP BY parent
            ) t2 ON t1.name = t2.parent
            SET t1.planned_quantity = t2.total_qty
            WHERE t1.docstatus = 1
        """
    )