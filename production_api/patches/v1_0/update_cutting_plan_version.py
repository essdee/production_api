import frappe
from production_api.production_api.doctype.cutting_plan.cutting_plan import get_complete_incomplete_structure
from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details

def execute():
    frappe.db.sql(
        """
            Update `tabCutting Plan` set version = null where 1 = 1;
        """
    )
    frappe.db.sql(
        """
            Update `tabCutting Plan` as t1 join `tabCutting LaySheet` as t2 ON t1.name = t2.cutting_plan Set t1.version = 'V1'  
        """
    )

    cp_list = frappe.db.sql(
        """
            Select name from `tabCutting Plan` where version is null;
        """, as_list=True
    )

    for cp in cp_list:
        cp = cp[0]
        doc = frappe.get_doc("Cutting Plan", cp)
        doc.version = "V2"
        item_details = fetch_order_item_details(doc.items, doc.production_detail)
        x, y = get_complete_incomplete_structure(doc.production_detail, item_details)
        doc.completed_items_json = x
        doc.incomplete_items_json = y
        doc.save()    