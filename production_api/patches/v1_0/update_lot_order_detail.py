import frappe
from production_api.essdee_production.doctype.lot.lot import Lot

def execute():
    lot_list = frappe.db.sql(
        """
            Select name from tabLot where item is not null AND production_detail is not null
        """, as_dict = True
    )
    for lot_name in lot_list:
        lot = lot_name['name']
        doc = frappe.get_doc("Lot", lot)
        if doc.item and doc.production_detail and len(doc.items) > 0:
            doc = Lot(doc.as_dict())
            doc.calculate_order()
            doc.save()
