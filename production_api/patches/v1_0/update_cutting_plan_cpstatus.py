import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabCutting Plan` SET cp_status = status WHERE 1 = 1
        """
    )
    frappe.db.commit()
    frappe.db.sql(
        """
            ALTER TABLE `tabCutting Plan` DROP COLUMN status
        """
    )