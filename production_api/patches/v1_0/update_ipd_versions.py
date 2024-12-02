import frappe
def execute():
    frappe.db.sql("""Update `tabItem Production Detail` set version = 1 where version = 0;""")