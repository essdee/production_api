import frappe
from frappe.model.naming import make_autoname

def execute():
    lot_list = frappe.db.sql(
        """
            SELECT name FROM `tabLot`
        """, as_dict=True
    )
    for lot_detail in lot_list:
        hash_value = make_autoname(key="hash")
        frappe.db.sql(
            """
                UPDATE `tabLot` SET lot_hash_value = %(hash)s WHERE name = %(lot)s
            """, {
                "hash": hash_value,
                "lot": lot_detail['name']
            }
        )
    item_list = frappe.db.sql(
        """
            SELECT name FROM `tabItem`
        """, as_dict=True
    )
    for item_detail in item_list:
        hash_value = make_autoname(key="hash")
        frappe.db.sql(
            """
                UPDATE `tabItem` SET item_hash_value = %(hash)s WHERE name = %(lot)s
            """, {
                "hash": hash_value,
                "lot": item_detail['name']
            }
        )    