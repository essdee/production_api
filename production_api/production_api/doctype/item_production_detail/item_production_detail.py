# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
from frappe.model.document import Document
from frappe.utils import flt
from six import string_types
from production_api.production_api.doctype.item.item import get_or_create_variant, get_attribute_details
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details

class ItemProductionDetail(Document):
	def load_attribute_list(self):
		attribute_list = []
		for attribute in self.item_attributes:
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
		bom_attribute_list = []
		for bom in self.item_bom:
			if bom.attribute_mapping != None:
				doc = frappe.get_doc("Item BOM Attribute Mapping", bom.attribute_mapping)
				bom_attribute_list.append({
					'bom_item': bom.item,
					'bom_attr_mapping_link': bom.attribute_mapping,
					'bom_attr_mapping_based_on': bom.based_on_attribute_mapping,
					'bom_attr_mapping_list': doc.values,
					'doctype': 'Item BOM Attribute Mapping'
				})
		self.set_onload('bom_attr_list', bom_attribute_list)

	def load_dependent_attribute(self):
		"""Load Dependent Attribute Detail into `__onload`"""
		
		dependent_attribute = {}
		if self.dependent_attribute and self.dependent_attribute_mapping:
			dependent_attribute = get_dependent_attribute_details(self.dependent_attribute_mapping)

		self.set_onload('dependent_attribute', dependent_attribute)	

	def onload(self):
		self.load_attribute_list()
		self.load_bom_attribute_list()
		self.load_dependent_attribute()

	def validate(self):
		if self.get('__islocal'):
			for attribute in self.get('item_attributes'):
				if attribute.mapping:
					doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
					duplicate_doc = frappe.new_doc("Item Item Attribute Mapping")
					duplicate_doc.values = doc.values
					duplicate_doc.save()
					attribute.mapping = duplicate_doc.name
			
			for bom in self.get('item_bom'):
				if bom.based_on_attribute_mapping and bom.attribute_mapping:
					doc = frappe.get_doc("Item BOM Attribute Mapping", bom.attribute_mapping)
					duplicate_doc = frappe.new_doc("Item BOM Attribute Mapping")
					duplicate_doc.values = doc.values
					duplicate_doc.item_production_detail = self.name
					duplicate_doc.item = self.item
					duplicate_doc.bom_item = bom.item
					duplicate_doc.save()
					bom.attribute_mapping = duplicate_doc.name
				else:
					bom.attribute_mapping = None

		for attribute in self.get('item_attributes'):
			if attribute.mapping == None:
				doc = frappe.new_doc("Item Item Attribute Mapping")
				doc.attribute_name= attribute.attribute 
				doc.save()
				attribute.mapping = doc.name
		
		for bom in self.get('item_bom'):
			if bom.based_on_attribute_mapping and not bom.attribute_mapping:
				doc = frappe.new_doc("Item BOM Attribute Mapping")
				doc.item_production_detail = self.name
				doc.item = self.item
				doc.bom_item = bom.item
				doc.flags.ignore_validate = True
				doc.save()
				bom.attribute_mapping = doc.name
			elif not bom.based_on_attribute_mapping and bom.attribute_mapping:
				name = bom.attribute_mapping
				bom.attribute_mapping = None
				frappe.delete_doc("Item BOM Attribute Mapping", name)

		mapping = None
		is_attribute = False
		for item in self.item_attributes:
			if item.attribute == self.packing_attribute:
				is_attribute = True
				mapping = item.mapping
				break
		
		if not is_attribute:
			frappe.throw("The packing attribute is not the item attribute")

		map_doc = frappe.get_doc("Item Item Attribute Mapping", mapping)
		if len(map_doc.values) < self.packing_attribute_no:
			frappe.throw(f"The Packing attribute number is {self.packing_attribute_no} But there is only {len(map_doc.values)} attributes are available")		

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_attributes(doctype, txt, searchfield, start, page_len, filters):
	if (doctype != 'Item Attribute' or filters['item_production_detail'] == None):
		return []
	
	item_production_detail_name = filters['item_production_detail']
	item_production_detail = frappe.get_doc("Item Production Detail", item_production_detail_name)
	attributes = [attribute.attribute for attribute in item_production_detail.item_attributes]
	return [[value] for value in attributes if value.lower().startswith(txt.lower())]

@frappe.whitelist()
def get_attribute_values(item_production_detail, attributes = None):
	lot = frappe.get_doc("Item Production Detail", item_production_detail)
	attribute_values = {}

	if not attributes:
		attributes = [attr.attribute for attr in lot.item_attributes]

	for attribute in lot.item_attributes:
		if attribute.attribute in attributes and attribute.mapping != None:
			doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
			attribute_values[attribute.attribute] = [d.attribute_value for d in doc.values]
	
	return attribute_values


@frappe.whitelist()
def get_calculated_bom(item_production_detail, planned_qty):

	if isinstance(planned_qty, string_types):
		planned_qty = json.loads(planned_qty)
	item_detail = frappe.get_doc("Item Production Detail", item_production_detail)
	bom = {}
	for p in planned_qty:
		variant = p['item_variant']
		for item in item_detail.item_bom:
			if item.based_on_attribute_mapping:
				doc = frappe.get_doc("Item Variant",variant)
				variant_attr = [attr.attribute for attr in doc.attributes]
			# 	variant_attr_values = [attr.attribute_value for attr in doc.attributes]
			# 	item_name = doc.item
			# 	mapping_doc = frappe.get_doc("Item BOM Attribute Mapping", item.attribute_mapping)
			# 	from itertools import groupby
			# 	attributes = {}
			# 	for key, groups in groupby(mapping_doc.values, lambda i: i.index):
			# 		print(key)
			# 		for grp in groups:
			# 			if grp.type == 'item' and grp.attribute not in variant_attr or grp.attribute_value not in variant_attr_values:
			# 				break
			# 			else:
			# 				if grp.type == 'bom':
			# 					attributes[grp.attribute] = grp.attribute_value
			# 					break
			# 		if attributes:
			# 			break
			# 	new_v = get_or_create_variant(mapping_doc.bom_item,attributes)
			# 	qty = p['qty']/item.qty_of_product
			# 	if not bom.get(new_v, False):
			# 		bom[new_v] = qty
			# 	else:
			# 		bom[new_v] += qty
			# else:
			# 	qty = p['qty']/item.qty_of_product
			# 	if not bom.get(item.item, False):
			# 		bom[item.item] = qty
			# 	else:
			# 		bom[item.item] += qty

	print(bom)				
	
