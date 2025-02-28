import frappe

def execute():
    frappe.db.sql(
        """
            Update `tabCutting Plan` as t1 join `tabCutting LaySheet` as t2 ON t1.name = t2.cutting_plan Set t1.version = 'V1'  
        """
    )
    frappe.db.sql(
        """
            Update `tabCutting Plan` set version = 'V2' where version is null;
        """
    )
