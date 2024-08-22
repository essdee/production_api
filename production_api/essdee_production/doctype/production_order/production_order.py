# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
from frappe.model.document import Document
from six import string_types
from production_api.production_api.doctype.item.item import create_variant, get_variant, get_attribute_details, get_or_create_variant
from itertools import groupby
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details

class ProductionOrder(Document):
	def before_submit(self):
		if len(self.bom_summary) == 0:
			frappe.throw("BOM is not calculated");

	def before_validate(self):
		if self.get('item_details'):
			items = save_item_details(self.item_details)
			self.set("items",items)
		qty = 0
		for item in self.items:
			qty = qty + item.qty
		self.total_quantity = qty
		items = calculate_order_details(self.get('items'), self.production_detail, self.packing_uom)
		self.set('production_order_details',items )

	def onload(self):
		item_details = fetch_item_details(self.get('items'), self.production_detail)
		self.set_onload('item_details', item_details)
		if len(self.get('production_order_details')) > 0:
			# items = fetch_order_item_details(self.get('production_order_details'), self.production_detail)
			# self.set_onload('order_item_details', items)
			self.set_onload('order_item_details', True)

		

def calculate_order_details(items, production_detail, packing_uom):
	item_detail = frappe.get_doc("Item Production Detail", production_detail)
	final_list = []
	import math
	uom = packing_uom
	doc = frappe.get_doc("Item", item_detail.item)
	uom_conv = 0.0
	for uom_conversion in doc.uom_conversion_details:
		if uom_conversion.uom == uom:
			uom_conv = uom_conversion.conversion_factor
			break
	dept_attr = None
	pack_stage = None
	if item_detail.dependent_attribute:
		pack_stage = item_detail.packing_stage
		dept_attr = item_detail.dependent_attribute
	for item in items:
		variant = frappe.get_doc("Item Variant", item.item_variant)
		is_not_pack_attr = True
		for attribute in variant.attributes:
			attribute = attribute.as_dict()
			if attribute.attribute == item_detail.packing_attribute:
				is_not_pack_attr = False
				break
		if is_not_pack_attr:		
			qty = item.qty * uom_conv
			if item_detail.auto_calculate:
				qty = qty / item_detail.packing_attribute_no
			else:
				qty = qty / item_detail.packing_combo
			if item_detail.is_set_item:
				for attr in item_detail.set_item_details:
					variant = frappe.get_doc("Item Variant", item.item_variant)
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
						q = get_quantity(major_attr, item_detail.packing_item_details)
					new_variant = get_or_create_variant(variant.item, attrs)
					item1 = {
						'item_variant': new_variant,
						'table_index': item.table_index,
						'row_index': item.row_index,
						'quantity': math.ceil(qty) if item_detail.auto_calculate else math.ceil(qty * q)
					}
					final_list.append(item1)		

			else:	
				for attr in item_detail.packing_item_details:
					variant = frappe.get_doc("Item Variant", item.item_variant)
					attrs = {}
					for attribute in variant.attributes:
						attribute = attribute.as_dict()
						if attribute.attribute == dept_attr:
							attrs[attribute.attribute] = pack_stage
						else:	
							attrs[attribute.attribute] = attribute['attribute_value']
					attrs[item_detail.packing_attribute] = attr.attribute_value
					new_variant = get_or_create_variant(variant.item, attrs)
					item1 = {
						'item_variant': new_variant,
						'table_index': item.table_index,
						'row_index': item.row_index,
						'quantity': math.ceil(qty) if item_detail.auto_calculate else math.ceil(qty * attr.quantity)
					}
					final_list.append(item1)		
			
	return final_list
def save_item_details(item_details):
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
					variant1 = create_variant(item['item'], attributes)
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
	item_structure = None
	for key, variants in groupby(items, lambda i: i['table_index']):
		variants = list(variants)
		item1 = {}
		grp_variant = frappe.get_doc("Item Variant", variants[0]['item_variant'])
		if not item_structure:
			uom = get_isfinal_uom(production_detail)
			item_structure = get_item_details(grp_variant.item, uom=uom)
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

def get_quantity(attr, packing_item_details):
	for item in packing_item_details:
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
	# items = [item.as_dict() for item in items]
	if isinstance(items, string_types):
		items = json.loads(items)
	order_item_details = []
	for key, grp_by_table_index in groupby(items, lambda i: i['table_index']):
		all_variants = list(grp_by_table_index)
		item_structure = None
		for key, variants in groupby(all_variants, lambda i: i['row_index']):
			variants = list(variants)
			if not item_structure:
				grp_variant_item = frappe.get_value("Item Variant", variants[0]['item_variant'], 'item')	
				item_structure = get_item_details(grp_variant_item, production_detail=production_detail, dependent_state=item_detail.packing_stage )
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
						for key,val in x['values'].items():
							if not values.get(key, False):
								pass
							else:
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
def get_item_details(item_name, uom=None, production_detail=None, dependent_state=None):
	item = get_attribute_details(item_name)
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
def update_bom_summary(doc_name, bom):
	if isinstance(bom, string_types):
		bom = json.loads(bom)
	bom_items = []	
	for key, val in bom.items():
		bom_items.append({'item': key,'required_qty':val})	
	doc = frappe.get_doc("Production Order", doc_name)
	doc.set('bom_summary', bom_items)
	doc.save()

@frappe.whitelist()
def get_isfinal_uom(item_production_detail):
	doc = frappe.get_doc("Item Production Detail", item_production_detail)
	if doc.dependent_attribute_mapping:
		attribute_details = get_dependent_attribute_details(doc.dependent_attribute_mapping)
		for attr in attribute_details['attr_list']:
			if attribute_details['attr_list'][attr]['is_final'] == 1:
				return attribute_details['attr_list'][attr]['uom']
	else:
		item = doc.item
		item_doc = frappe.get_doc("Item", item)
		return item_doc.default_unit_of_measure

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