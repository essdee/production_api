# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.desk.search import search_widget
from frappe.model.document import Document
from frappe.utils import flt
from six import string_types

from production_api.production_api.doctype.item.item import get_or_create_variant

class LotTemplate(Document):
	def load_attribute_list(self):
		"""Load Attribute List into `__onload`"""
		
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
		"""Load BOM Item Attribute Mapping List into `__onload`"""

		bom_attribute_list = []
		for bom in self.bom:
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

	def onload(self):
		"""Load Attribute List and BOM Item Attribute Mapping List into `__onload`"""

		self.load_attribute_list()
		self.load_bom_attribute_list()

	def validate(self):
		print(self.name)
		"""Add a empty Mapping Table for each attribute"""
		if self.get('__islocal'):
			for attribute in self.get('item_attributes'):
				if attribute.mapping:
					doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
					duplicate_doc = frappe.new_doc("Item Item Attribute Mapping")
					duplicate_doc.values = doc.values
					duplicate_doc.save()
					attribute.mapping = duplicate_doc.name
			
			for bom in self.get('bom'):
				if bom.based_on_attribute_mapping and bom.attribute_mapping:
					doc = frappe.get_doc("Item BOM Attribute Mapping", bom.attribute_mapping)
					duplicate_doc = frappe.new_doc("Item BOM Attribute Mapping")
					duplicate_doc.values = doc.values
					duplicate_doc.lot_template = self.name
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
		
		for bom in self.get('bom'):
			if bom.based_on_attribute_mapping and not bom.attribute_mapping:
				doc = frappe.new_doc("Item BOM Attribute Mapping")
				doc.lot_template = self.name
				doc.item = self.item
				doc.bom_item = bom.item
				doc.flags.ignore_validate = True
				doc.save()
				bom.attribute_mapping = doc.name
			elif not bom.based_on_attribute_mapping and bom.attribute_mapping:
				name = bom.attribute_mapping
				bom.attribute_mapping = None
				doc = frappe.delete_doc("Item BOM Attribute Mapping", name)

		# for attribute in self.get('item_attributes'):
		# 	if attribute.mapping == None:
		# 		doc = frappe.new_doc("Item Item Attribute Mapping")
		# 		doc.save()
		# 		attribute.mapping = doc.name
		
		# for bom in self.get('bom'):
		# 	if bom.attribute_mapping_based_on and not bom.attribute_mapping:
		# 		doc = frappe.new_doc("Item BOM Attribute Mapping")
		# 		doc.save()
		# 		bom.attribute_mapping = doc.name

	def on_trash(self):
		for attribute in self.get('item_attributes'):
			if attribute.mapping:
				# frappe.delete_doc("Item Item Attribute Mapping", attribute.mapping)
				attribute.mapping = None
			
		for bom in self.get('bom'):
			if bom.attribute_mapping_based_on and bom.attribute_mapping:
				# frappe.delete_doc("Item BOM Attribute Mapping", bom.attribute_mapping)
				bom.attribute_mapping = None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_attribute_values(doctype, txt, searchfield, start, page_len, filters):
	if (doctype != 'Item Attribute Value' or filters['item'] == None or filters['attribute'] == None):
		return []

	attribute = filters['attribute']
	lot_template_name = filters['lot_template']

	attr = frappe.get_doc("Item Attribute", attribute)
	if attr.numeric_values:
		values = search_widget(doctype=doctype, txt=txt, page_length=page_len, searchfield=searchfield, filters=[['Item Attribute Value', 'attribute_name', '=', attribute]])
		return values

	lot_template = frappe.get_doc("Lot Template", lot_template_name)
	attributes = [attribute.attribute for attribute in lot_template.attributes]
	if attribute not in attributes:
		return []
	for attr_obj in lot_template.attributes:
		if attribute == attr_obj.attribute:
			mapping_doc = frappe.get_doc("Item Item Attribute Mapping", attr_obj.mapping)
			if len(mapping_doc.values) == 0:
				values = search_widget(doctype=doctype, txt=txt, page_length=page_len, searchfield=searchfield, filters=[['Item Attribute Value', 'attribute_name', '=', attribute]])
			else:
				attribute_values = [value.attribute_value for value in mapping_doc.values]
				return [[value] for value in attribute_values if value.lower().startswith(txt.lower())]
		
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_attributes(doctype, txt, searchfield, start, page_len, filters):
	if (doctype != 'Item Attribute' or filters['lot_template'] == None):
		return []
	
	lot_template_name = filters['lot_template']
	lot_template = frappe.get_doc("Lot Template", lot_template_name)
	attributes = [attribute.attribute for attribute in lot_template.item_attributes]
	return [[value] for value in attributes if value.lower().startswith(txt.lower())]

@frappe.whitelist()
def get_attribute_values(lot_template, attributes = None):
	lot = frappe.get_doc("Lot Template", lot_template)
	attribute_values = {}

	if not attributes:
		attributes = [attr.attribute for attr in lot.item_attributes]

	for attribute in lot.item_attributes:
		if attribute.attribute in attributes and attribute.mapping != None:
			doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
			attribute_values[attribute.attribute] = [d.attribute_value for d in doc.values]
	
	return attribute_values

@frappe.whitelist()
def get_calculated_bom(lot_template, planned_qty):
	if isinstance(planned_qty, string_types):
		planned_qty = json.loads(planned_qty)
	lot = frappe.get_doc("Lot Template", lot_template)
	attributes = get_attribute_values(lot_template)
	bom = []
	errors = []
	for b in lot.bom:
		try:
			bom1 = []
			if b.based_on_attribute_mapping:
				attribute_mapping = frappe.get_doc("Item BOM Attribute Mapping", b.attribute_mapping)
				valid = validate_bom_item(attribute_mapping.bom_item, [attr.attribute for attr in attribute_mapping.bom_item_attributes])
				attribute_mapping_list = attribute_mapping.get_attribute_mapping()
				print(attribute_mapping_list)
				qty = get_planned_qty_based_on_attributes(planned_qty, attributes, based_on = list(attribute_mapping_list[0]['item'].keys()))
				print('Qty', qty)
				for m in attribute_mapping_list:
					variant_name = get_or_create_variant(attribute_mapping.bom_item, m['bom'])
					print(variant_name)
					bom1.append({
						"item": variant_name,
						"required_qty": (get_qty(qty, m['item']) / b.qty_of_product) * b.qty_of_bom_item,
					})
			else:
				valid = validate_bom_item(b.item, [])
				if valid:
					variant_name = get_or_create_variant(b.item, {})
					qty = get_planned_qty_based_on_attributes(planned_qty, attributes)
					bom1.append({
						"item": variant_name,
						"required_qty": (get_qty(qty, {}) / b.qty_of_product) * b.qty_of_bom_item,
					})
		except Exception as e:
			errors.append({"item": b.item, "exception": e})
		else:
			bom.extend(bom1)
	
	return {
		'items': cumulate_duplicate(bom),
		'errors': errors, 
	}

def cumulate_duplicate(bom):
	total = {}
	for b in bom:
		if not total.get(b['item']):
			total[b['item']] = b['required_qty']
		else:
			total[b['item']] = total[b['item']] + b['required_qty']
	bom = []
	for t, t1 in total.items():
		bom.append({'item': t, 'required_qty': t1})
	return bom

def get_qty(qty, attributes):
	for q in qty:
		if len(list(attributes)) == 0 and len(list(q['attributes'])) == 0:
			return q['qty']
		flag = True
		print('Flag:', flag)
		print('Attributes:', attributes)
		for attr, attr_value in attributes.items():
			print('Attr:', attr, attr_value)
			if q['attributes'][attr] != "*" and q['attributes'][attr] != attr_value:
				flag = False
				break
		if flag:
			return q['qty']
	
	raise Exception("Could not calculate Qty")
		

def get_planned_qty_based_on_attributes(planned_qty, attributes, based_on = None):
	print(planned_qty)
	total = sum([flt(q['qty']) for q in planned_qty])
	print(total)
	if not based_on or len(based_on) == 0:
		return [{
			'attributes': {},
			'qty': total,
		}]
	based_on = sorted(based_on)
	if 'Size' in based_on:
		qty = []
		for q in planned_qty:
			attribute_values = {'Size': q['size']}
			x = 1
			for b in based_on:
				if b != 'Size':
					x *= len(attributes[b])
					attribute_values[b] = "*"
			qty.append({
				'attributes': attribute_values,
				'qty': flt(q['qty']) / x
			})
		return qty
	else:
		qty = []
		attribute_values = {}
		x = 1
		for b in based_on:
			x *= len(attributes[b])
			attribute_values[b] = "*"
		qty.append({
			'attributes': attribute_values,
			'qty': total / x
		})
		return qty


def validate_bom_item(item, attributes):
	item = frappe.get_doc("Item", item)
	attributes = attributes or []
	item_attributes = [attr.attribute for attr in item.attributes]
	if len(attributes) != len(item_attributes):
		return False
	attributes.sort()
	item_attributes.sort()
	for i in range(0, len(attributes)):
		if (attributes[i] != item_attributes[i]):
			return False
	return True