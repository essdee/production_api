# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EssdeeRawPrintFormat(Document):
	pass

@frappe.whitelist()
def get_value_with_pad(value:str, pad:int):
	if len(value) < pad:
		length = pad - len(value)
		value = value.ljust(length, ' ')
	return value

@frappe.whitelist()
def get_item_size(item,min,min_size, max_size):
	if len(item)< min:
		return max_size
	else:
		return min_size