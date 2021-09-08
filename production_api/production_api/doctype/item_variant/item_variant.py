# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class ItemVariant(Document):
	
	def autoname(self):
		variant_name = self.item
		for attribute in self.attributes:
			if attribute.attribute_value:
				variant_name += '-' + attribute.attribute_value
		self.name = variant_name
