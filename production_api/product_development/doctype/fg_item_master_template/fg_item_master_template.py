# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import create_dependent_attribute_mapping
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details

class FGItemMasterTemplate(Document):
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
	
	def load_dependent_attribute(self):
		"""Load Dependent Attribute Detail into `__onload`"""
		
		dependent_attribute = {}
		if self.dependent_attribute and self.dependent_attribute_mapping:
			dependent_attribute = get_dependent_attribute_details(self.dependent_attribute_mapping)

		self.set_onload('dependent_attribute', dependent_attribute)

	def onload(self):
		"""Load Attribute List into `__onload`"""

		self.load_attribute_list()
		self.load_dependent_attribute()
	
	def validate(self):
		"""Add a empty Mapping Table for each attribute"""
		secondary_only = frappe.get_value("UOM", self.default_unit_of_measure, "secondary_only")
		if secondary_only:
			frappe.throw(f"{self.default_unit_of_measure} can only be used as Secondary UOM")
		if self.primary_attribute and self.primary_attribute not in [attribute.attribute for attribute in self.attributes]:
			frappe.throw("Default Attribute must be in Attribute List")
		
		if self.get('__islocal'):
			for attribute in self.get('attributes'):
				if attribute.mapping:
					doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
					duplicate_doc = frappe.copy_doc(doc)
					duplicate_doc.save()
					attribute.mapping = duplicate_doc.name
			
			if self.dependent_attribute and self.dependent_attribute_mapping:
				doc = frappe.get_doc("Item Dependent Attribute Mapping", self.dependent_attribute_mapping)
				duplicate_doc = frappe.copy_doc(doc)
				duplicate_doc.save()
				self.dependent_attribute_mapping = duplicate_doc.name
			elif not self.dependent_attribute and self.dependent_attribute_mapping:
				self.dependent_attribute_mapping = None
		
		for attribute in self.get('attributes'):
			if attribute.mapping == None:
				doc = frappe.new_doc("Item Item Attribute Mapping")
				doc.attribute_name= attribute.attribute 
				doc.save()
				attribute.mapping = doc.name
		
		if self.primary_attribute:
			# Check if primary attribute has values
			flag = False
			for attribute in self.get('attributes'):
				if attribute.attribute == self.primary_attribute:
					flag = True
			if not flag:
				frappe.throw(f"{self.primary_attribute} is not in the attribute list")

		if self.dependent_attribute:
			# Check if dependent attribute has values
			flag = False
			dependent_attr_list = []
			for attribute in self.get('attributes'):
				if attribute.attribute == self.dependent_attribute:
					flag = True
					mapping = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
					if not mapping.values or len(mapping.values) == 0:
						frappe.throw(f"Please set {self.dependent_attribute} values before setting it as Dependent Attribute")
					dependent_attr_list = [v.attribute_value for v in mapping.values]
			if not flag:
				frappe.throw(f"{self.dependent_attribute} is not in the attribute list")
			if not self.primary_attribute:
				frappe.throw("Please set Primary Attribute for this Item")
			if not self.dependent_attribute_mapping:
				self.set("dependent_attribute_mapping", create_dependent_attribute_mapping(self, dependent_attr_list))
		else:
			# Remove Dependent Attribute Mapping
			if self.dependent_attribute_mapping:
				frappe.delete_doc("Item Dependent Attribute Mapping", self.dependent_attribute_mapping)
				self.dependent_attribute_mapping = None
