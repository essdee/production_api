import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabCutting LaySheet Detail` SET actual_dia = dia
        """
    )
    frappe.db.sql(
        """
            UPDATE `tabCutting LaySheet Accessory Detail` SET actual_dia = dia
        """
    )