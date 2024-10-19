# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
from six import string_types
from frappe.model.document import Document
from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details
from production_api.production_api.doctype.item.item import get_or_create_variant, get_attribute_details
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import calculate_cloth, get_cloth_combination

class CuttingPlan(Document):
	def onload(self):
		items = fetch_order_item_details(self.items, self.production_detail)
		self.set_onload('item_details', items)

		cloth_items = fetch_cloth_details(self.cutting_plan_cloth_details)
		self.set_onload('item_cloth_details', cloth_items)

	def before_validate(self):
		if self.get('item_details'):
			items = save_item_details(self.item_details)
			self.set("items",items)

		if self.get('item_cloth_details'):
			items = save_item_cloth_details(self.item_cloth_details)
			self.set("cutting_plan_cloth_details",items)	

def save_item_cloth_details(items):
	if isinstance(items, string_types):
		items = json.loads(items)
	item_details = []
	for item in items:
		item_details.append({
			"cloth_item_variant":item['cloth_item_variant'],
			"cloth_type":item['cloth_type'],
			"colour":item['colour'],
			"dia":item['dia'],
			"required_weight":item['required_weight'],
			"weight":item['weight']
		})
	return item_details	

def save_item_details(items):
	if isinstance(items, string_types):
		items = json.loads(items)
	items = items[0]
	item_list = []
	for item in items['items']:
		for val in item['values']:
			i = {}
			attributes = item['attributes']
			attributes[item['primary_attribute']] = val
			attributes[items['dependent_attribute']] = items['final_state']
			new_variant = get_or_create_variant(items['item'], attributes)
			i['item_variant'] = new_variant
			i['quantity'] = item['values'][val]
			item_list.append(i)
	return item_list

def fetch_cloth_details(items):
	item_details = []
	for item in items:
		variant = item.cloth_item_variant
		variant_doc = frappe.get_doc("Item Variant",variant)
		item_details.append({
			"cloth_item_variant":item.cloth_item_variant,
			"item":variant_doc.item,
			"colour":item.colour,
			"dia":item.dia,
			"cloth_type":item.cloth_type,
			"required_weight":item.required_weight,
			"weight":item.weight,
		})
	return item_details	

@frappe.whitelist()
def get_items(lot):
	lot_doc = frappe.get_doc("Lot",lot)
	items = fetch_order_item_details(lot_doc.lot_order_details, lot_doc.production_detail)
	return items

@frappe.whitelist()
def get_cloth(ipd, item_name, items, doc_name):
	if isinstance(items, string_types):
		items = json.loads(items)
	cloth_list = {}
	ipd_doc = frappe.get_doc("Item Production Detail",ipd)
	item_attributes = get_attribute_details(item_name)
	cloth_combination = get_cloth_combination(ipd_doc.cutting_items_json, ipd_doc.cutting_cloths_json)
	for item in items:
		variant = frappe.get_doc("Item Variant", item['item_variant'])
		attr_details = item_attribute_details(variant, item_attributes)
		cloths = calculate_cloth({},ipd_doc,cloth_combination, attr_details,item['quantity'])
		for cloth, cloth_items in cloths.items():
			for key, value in cloth_items.items():
				if cloth_list.get(key):
					cloth_list[key] += value[0]
				else:
					cloth_list[key] = value[0]
	cloth_type = {}
	for cloth in ipd_doc.cloth_detail:
		cloth_type[cloth.cloth] = cloth.name1

	required_cloth_details = []
	for cloth_name, weight in cloth_list.items():
		variant = frappe.get_doc("Item Variant", cloth_name)
		attribute_details = {}
		for attr in variant.attributes:
			attribute_details[attr.attribute] = attr.attribute_value
		required_cloth_details.append({
			"cloth_item_variant":cloth_name,
			"cloth_type":cloth_type[variant.item],
			"colour":attribute_details[ipd_doc.packing_attribute],
			'dia':attribute_details['Dia'],
			"required_weight":weight,
			"weight":0.0
		})	
	doc = frappe.get_doc("Cutting Plan", doc_name)
	doc.set("cutting_plan_cloth_details", required_cloth_details)
	doc.save()

def item_attribute_details(variant, item_attributes):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute in item_attributes['attributes'] and attr.attribute != item_attributes['dependent_attribute']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details