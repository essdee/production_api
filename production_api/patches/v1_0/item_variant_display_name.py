import frappe

def execute():
    # Execute the patch to update display names for Item Variant Attributes
    frappe.db.sql("update `tabItem Variant Attribute` set `display_name` = `attribute_value`")