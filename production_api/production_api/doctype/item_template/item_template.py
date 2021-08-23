# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ItemTemplate(Document):

	def load_attr_list(self):
		"""Load Attribute List into `__onload`"""
		
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
	
	def load_bom_item_attr_list(self):
		"""Load BOM Item Attribute Mapping List into `__onload`"""

		bom_item_attribute_list = []
		for bom_item in self.bom_items:
			if bom_item.attribute_mapping != None:
				doc = frappe.get_doc("IT BOM Item Attr Mapping", bom_item.attribute_mapping)
				bom_item_attribute_list.append({
					'bom_item': bom_item.item,
					'bom_item_attr_mapping_link': bom_item.attribute_mapping,
					'bom_item_attr_mapping_based_on': bom_item.attribute_mapping_based_on,
					'bom_item_attr_mapping_list': doc.it_bom_item_attr_mapping_list,
					'doctype': 'IT BOM Item Attr Mapping'
				})
		self.set_onload('bom_attr_list', bom_item_attribute_list)
	
	def load_item_price_list(self):
		"""Load Item Price List into `__onload`"""
		filters = {"item_name": self.name}
		item_price_list = frappe.get_list("Item Price", filters=filters, fields=["*"])
		self.set_onload('item_price_list', item_price_list)

	def onload(self):
		"""Load Attribute List and BOM Item Attribute Mapping List into `__onload`"""

		self.load_attr_list()
		self.load_bom_item_attr_list()
		self.load_item_price_list()

	def validate(self):
		"""Add a empty Mapping Table for each attribute"""
		
		for attribute in self.get('attribute_list'):
			if attribute.attribute_values == None:
				doc = frappe.new_doc("Item Attribute Value Mapping")
				doc.save()
				attribute.attribute_values = doc.name
		
		for bom_item in self.get('bom_items'):
			if bom_item.attribute_mapping == None:
				doc = frappe.new_doc("IT BOM Item Attr Mapping")
				doc.save()
				bom_item.attribute_mapping = doc.name
