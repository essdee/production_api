import frappe

def execute():
    cp_list = frappe.get_list("Cutting Plan", filters={"version":"V1","item": ["is", "set"]})
    for cp in cp_list:
        doc = frappe.get_doc("Cutting Plan", cp)
        from production_api.production_api.doctype.cutting_plan.cutting_plan import get_items, save_item_details
        items = get_items(doc.lot)
        table_data = save_item_details(items)
        doc.set("items", table_data)
        doc.save()
        