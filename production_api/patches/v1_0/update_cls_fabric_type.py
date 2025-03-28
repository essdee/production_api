import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabCutting LaySheet Detail` SET fabric_type = 'Open Width' 
        """
    )