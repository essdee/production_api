# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class ItemAttribute(Document):

	def validate(self):
		if self.numeric_values:
			self.create_numeric_values()

	def create_numeric_values(self):
		"""Generate all values in the range by its increment"""

		from_range = self.from_range
		to_range = self.to_range
		increment = self.increment
		if from_range and to_range and increment:
			# Generate values from range
			cur_val = float(from_range)
			while cur_val <= to_range:
				if not frappe.db.exists("Item Attribute Value", remove_suffix(str(cur_val), '.0') + ' ' +  self.name):
					frappe.get_doc({
						"doctype": "Item Attribute Value",
						"attribute_name": self.name,
						"attribute_value": remove_suffix(str(cur_val), '.0') + ' ' +  self.name
					}).insert()
				cur_val += increment
			

	def onload(self):
		"""Load Attribute Values in `__onload`"""
		filters = {"attribute_name": self.name}
		attribute_values = frappe.get_all("Item Attribute Value", filters=filters, fields=["*"])
		self.set_onload('attr_values', attribute_values)

def remove_suffix(input_string, suffix):
    if suffix and input_string.endswith(suffix):
        return input_string[:-len(suffix)]
    return input_string
