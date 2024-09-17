# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
from frappe.model.document import Document
from six import string_types
from frappe.utils import flt
from production_api.production_api.doctype.item.item import create_variant, get_variant, get_attribute_details, get_or_create_variant
from itertools import groupby
import math
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details

class Lot(Document):
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
	
	def validate(self):	
		items, qty = calculate_order_details(self.get('items'), self.production_detail, self.packing_uom, self.uom)

		if len(items) == 0:
			x = []
			for item in self.items:
				x.append({'item_variant': item.item_variant, 'quantity':item.qty })
				qty += item.qty
			self.set('lot_order_details',x)
			self.set('total_order_quantity', qty)
		else:
			self.set('lot_order_details',items)
			self.set('total_order_quantity', qty)

	def onload(self):
		if self.production_detail:
			item_details = fetch_item_details(self.get('items'), self.production_detail)
			self.set_onload('item_details', item_details)
			items = fetch_order_item_details(self.get('lot_order_details'), self.production_detail)
			x = items[0]
			self.lot_order_details_json = x
			self.set_onload('order_item_details', items)

def calculate_order_details(items, production_detail, packing_uom, final_uom):
	item_detail = frappe.get_doc("Item Production Detail", production_detail)
	final_list = []
	doc = frappe.get_doc("Item", item_detail.item)
	dept_attr = None
	pack_stage = None
	if item_detail.dependent_attribute:
		pack_stage = item_detail.pack_in_stage
		dept_attr = item_detail.dependent_attribute
	uom_factor = get_uom_conversion_factor(doc.uom_conversion_details,final_uom, packing_uom)
	final_qty = 0
	for item in items:
		variant = frappe.get_doc("Item Variant", item.item_variant)
		is_not_pack_attr = True
		for attribute in variant.attributes:
			attribute = attribute.as_dict()
			if attribute.attribute == item_detail.packing_attribute:
				is_not_pack_attr = False
				break
		if is_not_pack_attr:
			item_list = {} 
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

					temp_qty = math.ceil(qty) if item_detail.auto_calculate else math.ceil(qty * flt(q))
					if item_detail.major_attribute_value == attr.set_item_attribute_value:
						final_qty += temp_qty
					if not item_list.get(new_variant,False):
						item_list[new_variant] = temp_qty
					else:
						item_list[new_variant] += temp_qty
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
					temp_qty = math.ceil(qty) if item_detail.auto_calculate else math.ceil(qty * attr.quantity)
					final_qty += temp_qty
					if not item_list.get(new_variant,False):
						item_list[new_variant] = temp_qty 
					else:
						item_list[new_variant] += temp_qty
			for key, val in item_list.items():
				final_list.append({
					'item_variant':key,
					'quantity':val,
				})		
	return final_list, final_qty

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
				item1['qty'] = row['values'][val]['qty']
				item1['ratio'] = row['values'][val]['ratio']
				item1['mrp'] = row['values'][val]['mrp']
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
			item1['ratio'] = row['values']['ratio']
			item1['mrp'] = row['values']['mrp']
			item1['table_index'] = id1
			items.append(item1)
	return items

def fetch_item_details(items, production_detail):
	items = [item.as_dict() for item in items]
	if len(items) == 0:
		return
	dependent_attr_map_value = frappe.get_value("Item Production Detail",production_detail,'dependent_attribute_mapping')
	grp_variant = frappe.get_value("Item Variant", items[0]['item_variant'],'item')
	variant_attr_details = get_attribute_details(grp_variant)
	primary_attr = variant_attr_details['primary_attribute']
	uom = get_isfinal_uom(production_detail)['uom']
	doc = frappe.get_doc("Item", grp_variant)
	item_structure = get_item_details(grp_variant, uom=uom,production_detail=production_detail, dependent_attr_mapping=dependent_attr_map_value)

	for key, variants in groupby(items, lambda i: i['table_index']):
		variants = list(variants)
		item1 = {}
		values = {}	
		for variant in variants:
			current_variant = frappe.get_doc("Item Variant", variant['item_variant'])
			item_attribute_details = get_item_attribute_details(current_variant, variant_attr_details)
			if doc.dependent_attribute and doc.dependent_attribute in item_attribute_details:
				del item_attribute_details[doc.dependent_attribute]
			if doc.primary_attribute:
				for attr in current_variant.attributes:
					if attr.attribute == primary_attr:
						values[attr.attribute_value] = {
							"qty":variant['qty'],
							"ratio": variant['ratio'],
							"mrp": variant['mrp'],
						}
						break
			else:
				values['qty'] = variant['qty']
				values['ratio'] = variant['ratio']
				values['mrp'] = variant['mrp']
		attrs = {}
		for item in item_structure['attributes']:
			if item in item_attribute_details:
				attrs[item]=item_attribute_details[item]

		item1['primary_attribute'] = primary_attr or None
		item1['attributes'] = attrs
		item1['values'] = values
		item_structure['items'].append(item1)
	return item_structure

@frappe.whitelist()
def fetch_order_item_details(items, production_detail):
	pack_in_stage, dept_attr_mapping = frappe.get_value("Item Production Detail", production_detail,['pack_in_stage','dependent_attribute_mapping'])
	if isinstance(items, string_types):
		items = json.loads(items)
	order_item_details = []
	grp_variant_item = frappe.get_value("Item Variant", items[0].item_variant, 'item')	
	doc = frappe.get_doc("Item", grp_variant_item)
	variant_attr_details = get_attribute_details(grp_variant_item)
	primary_attr = variant_attr_details['primary_attribute']
	item_structure = get_item_details(grp_variant_item, production_detail=production_detail, dependent_state=pack_in_stage,dependent_attr_mapping=dept_attr_mapping)

	for item in items:
		values = {}
		current_variant = frappe.get_doc("Item Variant", item.item_variant)
		item_attribute_details = get_item_attribute_details(current_variant, variant_attr_details)
		if doc.dependent_attribute and doc.dependent_attribute in item_attribute_details:
			del item_attribute_details[doc.dependent_attribute]
		if doc.primary_attribute:
			for attr in current_variant.attributes:
				if attr.attribute == primary_attr:
					values[attr.attribute_value] = item.quantity
					break
		else:
			values['qty'] = item.quantity

		check = True
		for x in item_structure['items']:
			if x['attributes'] == item_attribute_details:
				value_key = list(values.keys())[0]
				if value_key in x['values']:
					values[value_key] += x['values'][value_key]
				x['values'].update(values)
				check = False
				break
		if check:
			item1 = {}
			item1['primary_attribute'] = primary_attr or None
			item1['attributes'] = item_attribute_details
			item1['values'] = values
			item_structure['items'].append(item1)

	order_item_details.append(item_structure)
	return order_item_details

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

def get_item_attribute_details(variant, item_attributes):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute in item_attributes['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

@frappe.whitelist()
def get_item_details(item_name, uom=None, production_detail=None, dependent_state=None, dependent_attr_mapping=None):
	item = get_attribute_details(item_name, dependent_attr_mapping=dependent_attr_mapping)
	item_detail = frappe.get_doc("Item Production Detail", production_detail)
	if uom:
		item['default_uom'] = uom
	final_state = None
	final_state_attr = None
	item['items'] = []
	if item['dependent_attribute']:
		attribute = dependent_state if dependent_state else item_detail.pack_out_stage
		for attr in item['dependent_attribute_details']['attr_list']:
			if attr == attribute:
				final_state = attribute
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
			if attr == doc.pack_out_stage:
				uom = attribute_details['attr_list'][attr]['uom']
				break
	else:
		item = doc.item
		item_doc = frappe.get_doc("Item", item)
		uom = item_doc.default_unit_of_measure

	if get_pack_stage:
		pack_in_stage = doc.pack_in_stage
		pack_out_stage = doc.pack_out_stage
		if doc.dependent_attribute_mapping:
			attribute_details = get_dependent_attribute_details(doc.dependent_attribute_mapping)
			return {
				'uom':uom,
				'pack_in_stage':pack_in_stage,
				'pack_out_stage': pack_out_stage,
				'packing_uom': attribute_details['attr_list'][pack_in_stage]['uom'] or uom,
				'dependent_attr_mapping': doc.dependent_attribute_mapping,
				'tech_pack_version': doc.tech_pack_version,
				'pattern_version': doc.pattern_version,
				'packing_combo': doc.packing_combo,
			}
	return {
		'uom':uom,
	}

def get_uom_conversion_factor(uom_conversion_details, from_uom, to_uom):
	if not to_uom:
		to_uom = from_uom
	to_uom_factor = None
	from_uom_factor = None
	for item in uom_conversion_details:
		if item.uom == from_uom:
			from_uom_factor = item.conversion_factor
		if item.uom == to_uom:
			to_uom_factor = item.conversion_factor
	return from_uom_factor / to_uom_factor

@frappe.whitelist()
def get_dict_object(data):
	return json.loads(data)

@frappe.whitelist()
def combine_child_tables(table1, table2):
	table = table1 + table2
	tab_list = []
	for row in table:
		tab_list.append(row.as_dict())
	return tab_list

@frappe.whitelist()
def get_attributes(data):
	grp_variant_doc = frappe.get_doc("Item Variant", data[0].item_variant)
	grp_item = grp_variant_doc.item
	dept_attr = frappe.get_value("Item", grp_item, "dependent_attribute")
	attribute_list = []
	for attrs in grp_variant_doc.attributes:
		if attrs.attribute != dept_attr:
			attribute_list.append(attrs.attribute)
	attribute_list = attribute_list + ['Ratio', 'MRP']
	
	attr_list = []
	for item in data:
		item= item.as_dict()
		doc = frappe.get_doc("Item Variant", item['item_variant'])
		temp_attr = {}
		for attr in doc.attributes:
			if attr.attribute != dept_attr:
				temp_attr[attr.attribute] = attr.attribute_value
		temp_attr['Ratio'] = item['ratio']
		temp_attr['MRP'] = item['mrp']	
		attr_list.append(temp_attr)
	return attribute_list, attr_list

	
