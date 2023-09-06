# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class ItemVariant(Document):
	
	def autoname(self):
		self.name = self.get_name()
	
	def get_name(self):
		variant_name = self.item
		for attribute in self.attributes:
			if attribute.attribute_value:
				variant_name += '-' + attribute.attribute_value
		return variant_name
	
	def get_attribute_value(self, attribute):
		attribute_value = None
		for attr in self.attributes:
			if attr.attribute == attribute:
				attribute_value = attr.attribute_value
				break
		
		return attribute_value
