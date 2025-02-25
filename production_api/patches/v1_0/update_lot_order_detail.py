import frappe
from production_api.essdee_production.doctype.lot.lot import Lot

def execute():
    frappe.set_user("Administrator")
    lot_list = frappe.get_all("Lot", pluck="name")
    for lot in lot_list:
        doc = frappe.get_doc("Lot", lot)
        if doc.item and doc.production_detail and len(doc.items) > 0:
            doc = Lot(doc.as_dict())
            doc.calculate_order()
            doc.save()
