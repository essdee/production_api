import frappe
from production_api.essdee_production.doctype.lot.lot import Lot

def execute():
    lot_list = frappe.get_list("Lot", filters= {"item":['is',"set"], "production_detail":['is','set']} pluck="name")
    for lot in lot_list:
        doc = frappe.get_doc("Lot", lot)
        if doc.item and doc.production_detail and len(doc.items) > 0:
            doc = Lot(doc.as_dict())
            doc.calculate_order()
            doc.save()
