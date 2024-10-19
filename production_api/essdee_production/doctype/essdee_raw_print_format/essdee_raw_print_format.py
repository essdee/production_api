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
def get_item_size(item, item_size, text_size):
	for idx,i in enumerate(item_size):
		if len(item) <= i:
			return text_size[idx]

	return text_size[len(text_size)-1]	