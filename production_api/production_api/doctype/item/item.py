# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Item(Document):
	
	def load_attribute_list(self):
		"""Load Attribute List into `__onload`"""
		
		attribute_list = []
		for attribute in self.attributes:
			attribute_doc = frappe.get_doc("Item Attribute", attribute.attribute)
			if not attribute_doc.numeric_values:
				if attribute.mapping != None:
					doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
					attribute_list.append({
						'name': attribute.name,
						'attr_name': attribute.attribute,
						'attr_values_link': attribute.mapping,
						'attr_values': doc.values,
						'doctype': 'Item Item Attribute Mapping'
					})
				else:
					attribute_list.append({
						'name': attribute.name,
						'attr_name': attribute.attribute,
						'attr_values_link': attribute.mapping,
						'attr_values': [],
						'doctype': 'Item Item Attribute Mapping'
					})
		self.set_onload('attr_list', attribute_list)
	
	def load_bom_attribute_list(self):
		"""Load BOM Item Attribute Mapping List into `__onload`"""

		bom_attribute_list = []
		for bom in self.bom:
			if bom.attribute_mapping != None:
				doc = frappe.get_doc("Item BOM Attribute Mapping", bom.attribute_mapping)
				bom_attribute_list.append({
					'bom_item': bom.item,
					'bom_attr_mapping_link': bom.attribute_mapping,
					'bom_attr_mapping_based_on': bom.attribute_mapping_based_on,
					'bom_attr_mapping_list': doc.values,
					'doctype': 'Item BOM Attribute Mapping'
				})
		self.set_onload('bom_attr_list', bom_attribute_list)
	
	def load_price(self):
		"""Load Item Price List into `__onload`"""

		filters = {"item_name": self.name}
		item_price_list = frappe.get_list("Item Price", filters=filters, fields=["*"])
		self.set_onload('item_price_list', item_price_list)

	def onload(self):
		"""Load Attribute List and BOM Item Attribute Mapping List into `__onload`"""

		self.load_attribute_list()
		self.load_bom_attribute_list()
		self.load_price()

	def validate(self):
		"""Add a empty Mapping Table for each attribute"""
		if self.default_attribute not in [attribute.attribute for attribute in self.attributes]:
			frappe.throw("Default Attribute must be in Attribute List")
		
		for attribute in self.get('attributes'):
			if attribute.mapping == None:
				doc = frappe.new_doc("Item Item Attribute Mapping")
				doc.save()
				attribute.mapping = doc.name
		
		for bom in self.get('bom'):
			if bom.attribute_mapping_based_on and not bom.attribute_mapping:
				doc = frappe.new_doc("Item BOM Attribute Mapping")
				doc.save()
				bom.attribute_mapping = doc.name
