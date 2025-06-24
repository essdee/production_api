import frappe
from production_api.utils import update_if_string_instance

def execute():
    work_orders = frappe.get_all("Work Order", filters={"open_status": "Open", "docstatus": 1}, pluck="name")
    for work_order in work_orders:
        grns = frappe.get_all("Goods Received Note", filters={"docstatus": 1, "against": "Work Order", "against_id": work_order}, pluck="name")
        if not grns:
            continue

        wo_doc = frappe.get_cached_doc("Work Order", work_order)
        for item in wo_doc.deliverables:
            item.stock_update = 0

        calculated_items = {}
        for grn in grns:
            grn_doc = frappe.get_doc("Goods Received Note", grn)
            for item in grn_doc.grn_deliverables:
                key = update_if_string_instance(item.set_combination)
                key.update({"variant": item.item_variant})
                frozen_key = frozenset(key.items())
                calculated_items[frozen_key] = calculated_items.get(frozen_key, 0) + item.quantity

        for item in wo_doc.deliverables:
            key = update_if_string_instance(item.set_combination)
            key.update({"variant": item.item_variant})
            frozen_key = frozenset(key.items())
            delivered_qty = calculated_items.get(frozen_key, 0)

            if item.is_calculated and delivered_qty:
                item.stock_update = delivered_qty

        wo_doc.save()
