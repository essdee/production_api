import frappe
from production_api.utils import update_if_string_instance

def execute():
    cp_list = frappe.get_all("Cutting Plan", pluck="name")
    for cp in cp_list:
        cp_doc = frappe.get_doc("Cutting Plan", cp)
        completed_json = update_if_string_instance(cp_doc.completed_items_json)
        incompleted_json = update_if_string_instance(cp_doc.incomplete_items_json)
        if completed_json and incompleted_json:
            pack_attr_val = frappe.get_cached_value("Item Production Detail", cp_doc.production_detail, "packing_attribute")
            completed_json['pack_attr'] = pack_attr_val
            incompleted_json['pack_attr'] = pack_attr_val
            cp_doc.completed_items_json = completed_json
            cp_doc.incomplete_items_json = incompleted_json
            cp_doc.save()
