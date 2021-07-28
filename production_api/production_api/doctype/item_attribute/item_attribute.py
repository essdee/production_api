# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class ItemAttribute(Document):
	
	def onload(self):
		"""Load Attribute Values in `__onload`"""
		filters = {"attribute_name": self.name}
		attribute_values = frappe.get_all("Item Attribute Value", filters=filters, fields=["*"])
		self.set_onload('attr_values', attribute_values)
