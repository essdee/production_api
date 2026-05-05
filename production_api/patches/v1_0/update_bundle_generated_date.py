import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabCutting LaySheet` 
            SET bundle_generated_date = DATE(printed_time)
            WHERE status = 'Label Printed'
        """
    )