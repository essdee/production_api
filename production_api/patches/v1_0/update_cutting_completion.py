import frappe, json
from six import string_types

def execute():
    cp_list = frappe.get_all("Cutting Plan", pluck="name")
    for cp in cp_list:
        cp_doc = frappe.get_doc("Cutting Plan", cp)
        cp_doc.cutting_location = "Machine Cutting"
        completed = cp_doc.completed_items_json
        if isinstance(completed, string_types):
            completed = json.loads(completed)

        for item in completed['items']:
            item['completed'] = True    
        cp_doc.completed_items_json = completed
        cp_doc.save()
        