import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabDelivery Challan` as d JOIN `tabWork Order` as w  ON d.work_order = w.name
            set d.production_detail = w.production_detail 
        """
    )