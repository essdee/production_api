# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TaxSlab(Document):
	def before_save(self):
		try:
			float(self.percentage)
			return
		except ValueError:
			frappe.throw("Percentage must be a Number")
