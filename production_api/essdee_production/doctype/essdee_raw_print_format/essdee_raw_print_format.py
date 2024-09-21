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
