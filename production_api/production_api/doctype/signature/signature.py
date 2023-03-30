# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Signature(Document):
	pass

@frappe.whitelist()
def get_signature(user):
	if user == None or not user:
		return None
	filters = {"user": user, "docstatus": 1}
	signatures = frappe.db.get_list("Signature", filters = filters, pluck = 'signature')
	if len(signatures) > 0:
		return signatures[0]
	return None