# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
from frappe.model.document import Document
from frappe.utils import flt
from six import string_types
from production_api.production_api.doctype.item.item import get_or_create_variant
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
	attributes = get_attribute_values(item_production_detail)
	bom = []
	errors = []
	for b in item_detail.item_bom:
		try:
			bom1 = []
			if b.based_on_attribute_mapping:
				print(b.item)
				attribute_mapping = frappe.get_doc("Item BOM Attribute Mapping", b.attribute_mapping)
				valid = validate_bom_item(attribute_mapping.bom_item, [attr.attribute for attr in attribute_mapping.bom_item_attributes])
				print(valid)
				attribute_mapping_list = attribute_mapping.get_attribute_mapping()
				print(attribute_mapping_list)
				qty = get_planned_qty_based_on_attributes(planned_qty, attributes, based_on = list(attribute_mapping_list[0]['item'].keys()))
				for m in attribute_mapping_list:
					variant_name = get_or_create_variant(attribute_mapping.bom_item, m['bom'])
					bom1.append({
						"item": variant_name,
						"required_qty": (get_qty(qty, m['item']) / b.qty_of_product) * b.qty_of_bom_item,
					})
			else:
				print(b.item)
				valid = validate_bom_item(b.item, [])
				print(valid)
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