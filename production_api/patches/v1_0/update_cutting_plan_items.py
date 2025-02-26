import frappe

def execute():
    cp_list = frappe.db.sql(
        """
            Select name from `tabCutting Plan` where version = 'V1' and item is not null
        """, as_dict = True
    )
    for cp_name in cp_list:
        cp = cp_name['name']
        doc = frappe.get_doc("Cutting Plan", cp)
        from production_api.production_api.doctype.cutting_plan.cutting_plan import get_items, save_item_details
        items = get_items(doc.lot)
        table_data = save_item_details(items)
        doc.set("items", table_data)
        doc.save()
        