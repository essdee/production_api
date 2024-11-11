# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ActionMaster(Document):
	def autoname(self):
		self.naming_series = "Master-" 
		
	def before_validate(self):
		self.quantity = str(self.min_qty) + " - " + str(self.max_qty)
