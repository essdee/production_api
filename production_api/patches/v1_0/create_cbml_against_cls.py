import frappe
from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import check_dependent_stage_variant
from production_api.production_api.doctype.cutting_laysheet.cutting_laysheet import create_cut_bundle_ledger

def execute():
    frappe.db.sql(
        """
            DELETE FROM `tabCut Bundle Movement Ledger` WHERE 1 = 1 
        """
    )
    lot_list = frappe.db.sql(
        """
            SELECT distinct(lot) as lot FROM `tabDelivery Challan` WHERE docstatus = 1
        """, as_dict=True
    )
    cp_lot_list = []
    cancelled_lot_list = []
    for lot in lot_list:
        lot = lot['lot']
        dc_list = frappe.get_all("Delivery Challan", filters={"lot": lot, "docstatus": 1}, pluck="name")
        ipd = frappe.get_value("Lot", lot, "production_detail")
        dept_attr, dept_attr_val = frappe.get_value("Item Production Detail", ipd, ['dependent_attribute', "stiching_in_stage"])
        for dc in dc_list:
            dc_doc = frappe.get_doc("Delivery Challan", dc)
            for row in dc_doc.items:
                check = check_dependent_stage_variant(row.item_variant, dependent_attribute=dept_attr, dependent_attribute_value=dept_attr_val)
                if check:
                    cancelled_lot_list.append(lot)
                    break
            if lot in cancelled_lot_list:
                break 
        if lot not in cancelled_lot_list:
            cp_lot_list.append(lot)

    for lot in cp_lot_list:
        cutting_plans = frappe.get_all("Cutting Plan", filters={"lot": lot, "work_order": ['is', 'set']}, pluck="name")
        for cutting_plan in cutting_plans:
            cls_list = frappe.get_all("Cutting LaySheet", filters={
                "cutting_plan": cutting_plan,
                "status": "Label Printed",
            }, pluck="name")

            for cls in cls_list:
                cls_doc = frappe.get_doc("Cutting LaySheet", cls)
                create_cut_bundle_ledger(cls_doc)    

    mrp_settings_doc = frappe.get_single("MRP Settings")              
    mrp_settings_doc.cut_bundle_cancelled_lot = ",".join(cancelled_lot_list)
    mrp_settings_doc.save()