import frappe

def execute():
    indexes = [
        # "cbm_key_index", 
        # "supplier_posting_datetime_index", 
        # "supplier_item_variant_index", 
        # "supplier_lot_index", 
        # "size_colour_item_panel_lot_index", 
        # "is_cancelled_is_collapsed_transformed_index",
        "posting_datetime_index",
        "supplier_index",
    ]

    for index in indexes:
        try:
            print(index)
            frappe.db.sql(
                f"""
                    DROP INDEX `{index}` ON `tabCut Bundle Movement Ledger`
                """
            ) 
            print(index)
        except Exception as e:
            print(e)    

    frappe.db.sql(
        """ optimize table `tabCut Bundle Movement Ledger` """
    )        