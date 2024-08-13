# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
from frappe.model.document import Document
from six import string_types
from production_api.production_api.doctype.item.item import create_variant, get_variant, get_attribute_details
from itertools import groupby


class ProductionOrder(Document):
	def before_submit(self):
		if len(self.bom_summary) == 0:
			frappe.throw("BOM is not calculated");

	def before_validate(self):
		if(self.get('item_details')):
			items = save_item_details(self.item_details)
			self.set("items",items)

	def onload(self):
		item_details = fetch_item_details(self.get('items'))
		self.set_onload('item_details', item_details)


def save_item_details(item_details):
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
	item = item_details[0]
	items = []
	for id1, row in enumerate(item['items']):
		if row['primary_attribute']:
			attributes = row['attributes']
			if item['final_state']:
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

def fetch_item_details(items):
	items = [item.as_dict() for item in items]
	items = sorted(items, key = lambda i: i['table_index'])
	item_structure = None
	for key, variants in groupby(items, lambda i: i['table_index']):
		variants = list(variants)
		item1 = {}
		grp_variant = frappe.get_doc("Item Variant", variants[0]['item_variant'])
		if not item_structure:
			item_structure = get_item_details(grp_variant.item)
		values = {}	
		for variant in variants:
			current_variant = frappe.get_doc("Item Variant", variant['item_variant'])
			variant_attr_details = get_attribute_details(current_variant.item)
			item_attribute_details = get_item_attribute_details(current_variant, variant_attr_details)
			doc = frappe.get_doc("Item", current_variant.item)
			if doc.dependent_attribute:
				if doc.dependent_attribute in item_attribute_details:
					del item_attribute_details[doc.dependent_attribute]
			if doc.primary_attribute:		
				for attr in current_variant.attributes:
					if attr.attribute == variant_attr_details['primary_attribute']:
						values[attr.attribute_value] = variant['qty']
				primary_attribute = variant_attr_details['primary_attribute']
			else:
				values['qty'] = variant['qty']
				primary_attribute = None
		item1['primary_attribute'] = primary_attribute
		item1['attributes'] = item_attribute_details
		item1['values'] = values
		item_structure['items'].append(item1)
	return item_structure

def get_item_attribute_details(variant, item_attributes):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute in item_attributes['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

@frappe.whitelist()
def get_item_details(item_name):
	item = get_attribute_details(item_name)
	final_state = None
	final_state_attr = None
	item['items'] = []
	if item['dependent_attribute']:
		for attr in item['dependent_attribute_details']['attr_list']:
			if item['dependent_attribute_details']['attr_list'][attr]['is_final'] == 1:
				final_state = attr
				final_state_attr = item['dependent_attribute_details']['attr_list'][attr]['attributes']
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
		for attr in doc.attributes:
			final_state_attr.append(attr.attribute)
		item['final_state_attr'] = final_state_attr
	return item

@frappe.whitelist()
def update_bom_summary(doc_name, bom):
	doc = frappe.get_doc("Production Order", doc_name)
	doc.set('bom_summary', json.loads(bom))
	doc.save()

