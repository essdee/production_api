import frappe

def execute():
    frappe.db.sql(
        """
            Update `tabWork Order` as t1 JOIN `tabProcess` as t2 ON t1.process_name = t2.name 
            set t1.is_manual_entry = t2.is_manual_entry_in_grn
        """
    )
