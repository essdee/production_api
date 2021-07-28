# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ItemTemplate(Document):
	
	def onload(self):
		"""Load Attribute List in `__onload`"""

		attribute_list = []
		for attribute in self.attribute_list:
			attribute_doc = frappe.get_doc("Item Attribute", attribute.attribute)
			if not attribute_doc.numeric_values:
				if attribute.attribute_values != None:
					doc = frappe.get_doc("Item Attribute Value Mapping", attribute.attribute_values)
					attribute_list.append({
						'name': attribute.name,
						'attr_name': attribute.attribute,
						'attr_values_link': attribute.attribute_values,
						'attr_values': doc.attribute_values,
						'doctype': 'Item Attribute Value Mapping'
					})
				else:
					attribute_list.append({
						'name': attribute.name,
						'attr_name': attribute.attribute,
						'attr_values_link': attribute.attribute_values,
						'attr_values': [],
						'doctype': 'Item Attribute Value Mapping'
					})
		self.set_onload('attr_list', attribute_list)

	def before_save(self):
		"""Add a empty Mapping Table for each attribute"""
		
		for attribute in self.get('attribute_list'):
			if attribute.attribute_values == None:
				doc = frappe.new_doc("Item Attribute Value Mapping")
				doc.save()
				attribute.attribute_values = doc.name
