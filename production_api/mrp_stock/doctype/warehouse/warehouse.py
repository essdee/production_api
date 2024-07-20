# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.nestedset import NestedSet


class Warehouse(NestedSet):
	pass

@frappe.whitelist()
def get_warehouse(supplier):
	doc_list1 = frappe.get_list('Warehouse', filters={'supplier':supplier, 'parent_warehouse': 'Stores'}, pluck = 'name')
	doc_list2 = frappe.get_list('Warehouse', filters={'supplier':supplier, 'parent_warehouse': 'Supplier Warehouses'}, pluck = 'name')
	docs = doc_list2 + doc_list1
	return docs[0]
