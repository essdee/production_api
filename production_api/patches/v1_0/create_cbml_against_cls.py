import frappe
from production_api.production_api.doctype.cutting_laysheet.cutting_laysheet import create_cut_bundle_ledger
from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import (
    check_cut_stage_variant, get_collapsed_previous_cbm_list, get_variant_attr_details, create_inter_cbml_doc
)

def execute():
    cutting_plans = frappe.db.sql(
        """
            SELECT name FROM `tabCutting Plan` WHERE work_order IS NOT NULL AND name NOT IN (
                SELECT cutting_plan FROM `tabCut Panel Movement`
            )  
        """, as_dict=True
    )
    for cutting_plan in cutting_plans:
        cls_list = frappe.get_all("Cutting LaySheet", filters={
            "cutting_plan": cutting_plan['name'],
            "status": "Label Printed",
        }, pluck="name")

        for cls in cls_list:
            cls_doc = frappe.get_doc("Cutting LaySheet", cls)
            create_cut_bundle_ledger(cls_doc)

    cutting_plans = frappe.db.sql(
        """
            SELECT name, lot, production_detail FROM `tabCutting Plan` WHERE work_order IS NOT NULL AND name IN (
                SELECT cutting_plan FROM `tabCut Panel Movement`
            )  
        """, as_dict=True
    )
    lot = []
    for cutting_plan in cutting_plans:
        lot_name = cutting_plan['lot']
        if lot_name in lot:
            continue
        else:
            lot.append(lot_name)

        from production_api.mrp_stock.report.stock_balance.stock_balance import execute as get_stock_balance
        x = get_stock_balance({
            "from_date": frappe.utils.add_months(frappe.utils.nowdate(), -1),
            "to_date": frappe.utils.nowdate(),
            "lot": lot_name,
            "remove_zero_balance_item": 1,
        })[1]
        posting_date = frappe.utils.nowdate()
        posting_time = frappe.utils.nowtime()
        ipd_fields = ["primary_item_attribute", "packing_attribute", "stiching_attribute", "stiching_in_stage"]
        primary_attr, pack_attr, stich_attr, stich_stage = frappe.get_value("Item Production Detail", cutting_plan['production_detail'], ipd_fields)
        attrs = {
            "primary": primary_attr,
            "pack": pack_attr,
            "stich": stich_attr,
        }
        ipd = frappe.get_value("Lot", lot_name, "production_detail")
        ipd_doc = frappe.get_doc("Item Production Detail", ipd)
        panel_qty_dict = {}
        for row in ipd_doc.stiching_item_details:
            panel_qty_dict[row.stiching_attribute_value] = row.quantity
        for row in x:
            location = row['warehouse']
            item = frappe.get_value("Item Variant", row['item'], "item")
            dept_attr = frappe.get_value("Item", item, "dependent_attribute")
            if not dept_attr:
                continue
            if check_cut_stage_variant(row['item'], dept_attr, stich_stage):
                variant_attrs = get_variant_attr_details(row['item'])
                cb_previous_entries = get_collapsed_previous_cbm_list(posting_date, posting_time, location, row['item'])
                quantity = row['bal_qty']
                if not cb_previous_entries:
                    row_panel = variant_attrs[attrs['stich']]
                    d = {
                        "lot" : lot_name,
                        "item" : item,
                        "size" : variant_attrs[attrs['primary']],
                        "colour" : variant_attrs[attrs['pack']],
                        "panel" : row_panel,
                        "lay_no" : 0,
                        "bundle_no" : 0,
                        "quantity" : quantity * panel_qty_dict[row_panel],
                        "supplier" : row['warehouse'],
                        "posting_date": posting_date,
                        "posting_time": posting_time,
                        "voucher_type": "",
                        "voucher_no": "",
                        "collapsed_bundle": 1,
                        "shade": "NA",
                        "quantity_after_transaction": quantity * panel_qty_dict[row_panel],
                        "set_combination": frappe.json.dumps({}),
                    }
                    new_doc = frappe.new_doc("Cut Bundle Movement Ledger")
                    new_doc.update(d)
                    new_doc.save()
                    new_doc.set_posting_datetime()
                    new_doc.set_key()
                    new_doc.update_item_variant()
                    new_doc.submit()           
                else:
                    create_inter_cbml_doc(cb_previous_entries[0]['name'], "", "", quantity, 1, posting_date, posting_time)

