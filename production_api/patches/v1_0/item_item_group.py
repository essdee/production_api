import frappe

def execute():

    frappe.db.sql("""
        UPDATE `tabItem` t1 JOIN `tabItem Group` t2 ON t1.item_group=t2.name
                  SET t1.item_group=NULL
                   WHERE t2.is_group = 1
    """)