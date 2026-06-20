# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TermsandCondition(Document):
	def validate(self):
		self.validate_default_po_term_unique()

	def validate_default_po_term_unique(self):
		if not self.is_default_po_term:
			return
		existing = frappe.db.get_value(
			"Terms and Condition",
			{"is_default_po_term": 1, "name": ["!=", self.name]},
			"name",
		)
		if existing:
			frappe.throw(
				_("{0} is already set as the Default PO Term. Only one Terms and Condition can be the default.").format(existing)
			)
