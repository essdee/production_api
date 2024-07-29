# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PurchaseOrderLog(Document):
	def on_cancel(self):
		frappe.throw("Individual Purchase Order Log cannot be cancelled.")
