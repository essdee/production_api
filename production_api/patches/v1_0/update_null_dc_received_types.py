import frappe

def execute():
    receivedType = frappe.db.get_single_value("Stock Settings", "default_received_type")
    frappe.db.sql(
        f"""
            UPDATE `tabDelivery Challan Item` SET item_type = '{receivedType}' WHERE item_type IS NULL
        """
    ) 