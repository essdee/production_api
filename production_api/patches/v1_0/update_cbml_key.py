import frappe

def execute():
    lot_list = frappe.db.sql(
        """
            SELECT name, lot_hash_value FROM `tabLot`
        """, as_dict=True
    )
    lot_dict = {}
    for lot_detail in lot_list:
        lot_dict[lot_detail['name']] = lot_detail['lot_hash_value']

    item_list = frappe.db.sql(
        """
            SELECT name, item_hash_value FROM `tabItem`
        """, as_dict=True
    )
    item_dict = {}
    for item_detail in item_list:
        item_dict[item_detail['name']] = item_detail['item_hash_value']
    
    cbml_list = frappe.db.sql(
        """
            SELECT name, lot, supplier, lay_no, bundle_no, shade, item, size, colour, panel 
            FROM `tabCut Bundle Movement Ledger`
        """, as_dict=True
    )    

    for cbml in cbml_list:
        d = [
            str(lot_dict[cbml['lot']]),
            str(cbml['supplier']),
            str(cbml['lay_no']),
            str(cbml['bundle_no']),
            str(cbml['shade']),
            str(item_dict[cbml['item']]),
            str(cbml['size']),
            str(cbml['colour']),
            str(cbml['panel']),
        ]
        cbm_key = "-".join(d)
        frappe.db.sql(
            """
                UPDATE `tabCut Bundle Movement Ledger` SET cbm_key = %(key)s WHERE name = %(docname)s
            """, {
                "docname": cbml['name'],
                "key": cbm_key
            }
        )