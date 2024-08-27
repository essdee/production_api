# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
from frappe.model.document import Document
from six import string_types
from frappe.utils import flt
from production_api.production_api.doctype.item.item import create_variant, get_variant, get_attribute_details, get_or_create_variant
from itertools import groupby
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details

class ProductionOrder(Document):
	def before_submit(self):
		if len(self.bom_summary) == 0:
			frappe.throw("BOM is not calculated")

	def before_validate(self):
		if self.get('item_details'):
			items = save_item_details(self.item_details, dependent_attr=self.get('dependent_attribute_mapping'))
			self.set("items",items)
		qty = 0
		for item in self.items:
			qty = qty + item.qty
		self.total_quantity = qty
		items = calculate_order_details(self.get('items'), self.production_detail, self.packing_uom, self.uom)
		self.set('production_order_details',items )

	def onload(self):
		item_details = fetch_item_details(self.get('items'), self.production_detail)
		self.set_onload('item_details', item_details)
		if len(self.get('production_order_details')) > 0:
			items = fetch_order_item_details(self.get('production_order_details'), self.production_detail)
			self.set_onload('order_item_details', items)

def calculate_order_details(items, production_detail, packing_uom, final_uom):
	item_detail = frappe.get_doc("Item Production Detail", production_detail)
	final_list = []
	import math
	doc = frappe.get_doc("Item", item_detail.item)
	dept_attr = None
	pack_stage = None
	if item_detail.dependent_attribute:
		pack_stage = item_detail.packing_stage
		dept_attr = item_detail.dependent_attribute
	uom_factor = get_uom_conversion_factor(doc.uom_conversion_details,final_uom, packing_uom)
	for item in items:
		variant = frappe.get_doc("Item Variant", item.item_variant)
		is_not_pack_attr = True
		for attribute in variant.attributes:
			attribute = attribute.as_dict()
			if attribute.attribute == item_detail.packing_attribute:
				is_not_pack_attr = False
				break
		if is_not_pack_attr:
			qty = (item.qty * uom_factor)
			if item_detail.auto_calculate:
				qty = qty / item_detail.packing_attribute_no
			else:
				qty = qty / item_detail.packing_combo
			if item_detail.is_set_item:
				for attr in item_detail.set_item_combination_details:
					attrs = {}
					for attribute in variant.attributes:
						attribute = attribute.as_dict()
						if attribute.attribute == dept_attr:
							attrs[attribute.attribute] = pack_stage
						else:
							attrs[attribute.attribute] = attribute['attribute_value']
					attrs[item_detail.set_item_attribute] = attr.set_item_attribute_value
					attrs[item_detail.packing_attribute] = attr.attribute_value	
					if not item_detail.auto_calculate:
						major_attr = attr.major_attribute_value
						q = get_quantity(major_attr, item_detail.packing_attribute_details)
					new_variant = get_or_create_variant(variant.item, attrs,dependent_attr=item_detail.dependent_attribute_mapping)
					item1 = {
						'item_variant': new_variant,
						'table_index': item.table_index,
						'row_index': item.row_index,
						'quantity': math.ceil(qty) if item_detail.auto_calculate else round(qty * flt(q))
					}
					final_list.append(item1)

			else:
				for attr in item_detail.packing_attribute_details:
					attrs = {}
					for attribute in variant.attributes:
						attribute = attribute.as_dict()
						if attribute.attribute == dept_attr:
							attrs[attribute.attribute] = pack_stage
						else:	
							attrs[attribute.attribute] = attribute['attribute_value']
					attrs[item_detail.packing_attribute] = attr.attribute_value
					new_variant = get_or_create_variant(variant.item, attrs,dependent_attr=item_detail.dependent_attribute_mapping)
					item1 = {
						'item_variant': new_variant,
						'table_index': item.table_index,
						'row_index': item.row_index,
						'quantity': math.ceil(qty) if item_detail.auto_calculate else math.ceil(qty * attr.quantity)
					}
					final_list.append(item1)
	return final_list

def save_item_details(item_details, dependent_attr=None):
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
	item = item_details[0]
	items = []
	for id1, row in enumerate(item['items']):
		if row['primary_attribute']:
			attributes = row['attributes']
			attributes[item['dependent_attribute']] = item['final_state']	
			for id2, val in enumerate(row['values'].keys()):
				attributes[row['primary_attribute']] = val
				item1 = {}
				variant_name = get_variant(item['item'], attributes)
				if not variant_name:
					variant1 = create_variant(item['item'], attributes, dependent_attr=dependent_attr)
					variant1.insert()
					variant_name = variant1.name
				item1['item_variant'] = variant_name
				item1['qty'] = row['values'][val]
				item1['table_index'] = id1
				item1['row_index'] = id2
				items.append(item1)
		else:
			item1 = {}
			attributes = row['attributes']
			variant_name = item['item']
			variant_name = get_variant(item['item'], attributes)
			if not variant_name:
				variant1 = create_variant(item['item'], attributes)
				variant1.insert()
				variant_name = variant1.name
			item1['item_variant'] = variant_name
			item1['qty'] = row['values']['qty']
			item1['table_index'] = id1
			items.append(item1)
	return items

def fetch_item_details(items, production_detail):
	items = [item.as_dict() for item in items]
	dependent_attr_map_value = frappe.get_value("Item Production Detail",production_detail,'dependent_attribute_mapping')
	item_structure = None
	for key, variants in groupby(items, lambda i: i['table_index']):
		variants = list(variants)
		item1 = {}
		grp_variant = frappe.get_doc("Item Variant", variants[0]['item_variant'])
		if not item_structure:
			uom = get_isfinal_uom(production_detail)
			item_structure = get_item_details(grp_variant.item, uom=uom, dependent_attr_mapping=dependent_attr_map_value)
		values = {}	
		for variant in variants:
			current_variant = frappe.get_doc("Item Variant", variant['item_variant'])
			variant_attr_details = get_attribute_details(current_variant.item)
			item_attribute_details = get_item_attribute_details(current_variant, variant_attr_details)
			doc = frappe.get_doc("Item", current_variant.item)
			if doc.dependent_attribute and doc.dependent_attribute in item_attribute_details:
				del item_attribute_details[doc.dependent_attribute]
			if doc.primary_attribute:
				for attr in current_variant.attributes:
					if attr.attribute == variant_attr_details['primary_attribute']:
						values[attr.attribute_value] = variant['qty']
						break
			else:
				values['qty'] = variant['qty']
		item1['primary_attribute'] = variant_attr_details['primary_attribute']
		item1['attributes'] = item_attribute_details
		item1['values'] = values
		item_structure['items'].append(item1)
	return item_structure

def get_quantity(attr, packing_attribute_details):
	for item in packing_attribute_details:
		if item.attribute_value == attr:
			return item.quantity

def get_same_index_set_item(index, set_item_details, set_attr, pack_attr):
	attr = {}
	attr[set_attr] = []
	for item in set_item_details:
		if item.index == index:
			attr[set_attr].append({'major_attribute':item.major_attribute_value,set_attr :item.set_item_attribute_value,pack_attr : item.attribute_value})
		if item.index > index:
			break	
	return attr	

@frappe.whitelist()
def fetch_order_item_details(items, production_detail):
	item_detail = frappe.get_doc("Item Production Detail", production_detail)
	items = [item.as_dict() for item in items]
	if isinstance(items, string_types):
		items = json.loads(items)
	order_item_details = []
	grp_variant_item = frappe.get_value("Item Variant", items[0]['item_variant'], 'item')	
	item_structure = get_item_details(grp_variant_item, production_detail=production_detail, dependent_state=item_detail.packing_stage,dependent_attr_mapping=item_detail.dependent_attribute_mapping )
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		for variant in variants:
			item1 = {}
			values = {}
			current_variant = frappe.get_doc("Item Variant", variant['item_variant'])
			variant_attr_details = get_attribute_details(current_variant.item)
			item_attribute_details = get_item_attribute_details(current_variant, variant_attr_details)
			doc = frappe.get_doc("Item", current_variant.item)
			if doc.dependent_attribute and doc.dependent_attribute in item_attribute_details:
				del item_attribute_details[doc.dependent_attribute]
			if doc.primary_attribute:
				for attr in current_variant.attributes:
					if attr.attribute == variant_attr_details['primary_attribute']:
						values[attr.attribute_value] = variant['quantity']
						break
			else:
				values['qty'] = variant['quantity']
			item1['primary_attribute'] = variant_attr_details['primary_attribute'] or None
			item1['attributes'] = item_attribute_details
			item1['values'] = values
			check = True
			for x in item_structure['items']:
				if x['attributes'] == item_attribute_details:
					for key in x['values']:
						if key in values:
							values[key] += x['values'][key]
					x['values'].update(values)
					check = False
					break
			if check:
				item_structure['items'].append(item1)
	order_item_details.append(item_structure)
	return order_item_details

def get_item_attribute_details(variant, item_attributes):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute in item_attributes['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

@frappe.whitelist()
def get_item_details(item_name, uom=None, production_detail=None, dependent_state=None, dependent_attr_mapping=None):
	item = get_attribute_details(item_name, dependent_attr_mapping=dependent_attr_mapping)
	if uom:
		item['default_uom'] = uom
	final_state = None
	final_state_attr = None
	item['items'] = []
	if item['dependent_attribute']:
		if dependent_state:
			for attr in item['dependent_attribute_details']['attr_list']:
				if attr == dependent_state:
					final_state = dependent_state
					final_state_attr = item['dependent_attribute_details']['attr_list'][attr]['attributes']
					break
		else:
			for attr in item['dependent_attribute_details']['attr_list']:
				if item['dependent_attribute_details']['attr_list'][attr]['is_final'] == 1:
					final_state = attr
					final_state_attr = item['dependent_attribute_details']['attr_list'][attr]['attributes']
					break
		if not final_state:
			frappe.msgprint("There is no final state for this item")
			return []
		item['final_state'] = final_state
		if item['primary_attribute'] in final_state_attr:
			final_state_attr.remove(item['primary_attribute'])
		item['final_state_attr'] = final_state_attr	
	elif not item['dependent_attribute'] and not item['primary_attribute']:
		doc = frappe.get_doc("Item", item['item'])
		final_state_attr = []
		x = [attr.attribute for attr in doc.attributes]
		final_state_attr = final_state_attr + x
		item['final_state_attr'] = final_state_attr
	if production_detail:
		doc = frappe.get_doc("Item Production Detail", production_detail)
		item['packing_attr'] = doc.packing_attribute
	return item

@frappe.whitelist()
def get_isfinal_uom(item_production_detail, get_pack_stage=None):
	uom = None
	doc = frappe.get_doc("Item Production Detail", item_production_detail)
	if doc.dependent_attribute_mapping:
		attribute_details = get_dependent_attribute_details(doc.dependent_attribute_mapping)
		for attr in attribute_details['attr_list']:
			if attribute_details['attr_list'][attr]['is_final'] == 1:
				uom = attribute_details['attr_list'][attr]['uom']
				break
	else:
		item = doc.item
		item_doc = frappe.get_doc("Item", item)
		uom = item_doc.default_unit_of_measure
	if not get_pack_stage:
		return uom
	else:
		pack_stage = doc.packing_stage
		if doc.dependent_attribute_mapping:
			attribute_details = get_dependent_attribute_details(doc.dependent_attribute_mapping)
			return {
				'uom':uom,
				'packing_stage':pack_stage,
				'packing_uom': attribute_details['attr_list'][pack_stage]['uom'],
				'dependent_attr_mapping': doc.dependent_attribute_mapping,
			}

@frappe.whitelist()
def get_pack_stage_uom(item_production_detail):
	doc = frappe.get_doc("Item Production Detail", item_production_detail)
	pack_stage = doc.packing_stage
	if doc.dependent_attribute_mapping:
		attribute_details = get_dependent_attribute_details(doc.dependent_attribute_mapping)
		return {
			'packing_stage':pack_stage,
			'packing_uom': attribute_details['attr_list'][pack_stage]['uom']
		}

def get_uom_conversion_factor(uom_conversion_details, from_uom, to_uom):
	to_uom_factor = None
	from_uom_factor = None
	for item in uom_conversion_details:
		if item.uom == from_uom:
			from_uom_factor = item.conversion_factor
		if item.uom == to_uom:
			to_uom_factor = item.conversion_factor
	return from_uom_factor / to_uom_factor


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_production_detail(doctype, txt, searchfield, start, page_len, filters):
	production_list = frappe.get_list('Item Production Detail',filters={'item':filters['item']},pluck='name')	
	return [[value] for value in production_list if value.lower().startswith(txt.lower())]
