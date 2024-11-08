# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
from six import string_types
from frappe.model.document import Document
from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details
from production_api.production_api.doctype.item.item import get_or_create_variant, get_attribute_details
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_cloth_combination,get_stitching_combination,calculate_cloth,get_key,get_additional_cloth,get_accessory_colour, add_cloth_detail
import copy
from production_api.production_api.doctype.cutting_laysheet.cutting_laysheet import update_cutting_plan

class CuttingPlan(Document):
	def autoname(self):
		self.naming_series = "CP-.YY..MM.-.{#####}."
		
	def onload(self):
		items = fetch_order_item_details(self.items, self.production_detail)
		self.set_onload('item_details', items)

		cloth_items = fetch_cloth_details(self.cutting_plan_cloth_details)
		self.set_onload('item_cloth_details', cloth_items)

		accessory_items = fetch_cloth_details(self.cutting_plan_accessory_details)
		self.set_onload("item_accessory_details",accessory_items)
	
	def before_validate(self):
		if self.is_new():
			if self.get('item_details'):
				x, y = get_complete_incomplete_structure(self.production_detail,self.item_details)
				self.completed_items_json = x
				self.incomplete_items_json = y

		if self.get('item_details'):
			items = save_item_details(self.item_details)
			self.set("items",items)

		if self.get('item_cloth_details'):
			items = save_item_cloth_details(self.item_cloth_details)
			self.set("cutting_plan_cloth_details",items)	

def get_complete_incomplete_structure(ipd,item_details):
	ipd_doc = frappe.get_doc("Item Production Detail",ipd)
	stiching_attrs = None
	panels = {}
	
	if isinstance(item_details,string_types):
		item_details = json.loads(item_details)
	x = item_details
	x = x[0]
	x = add_additional_attributes(ipd_doc,x)
	if ipd_doc.is_set_item:
		panels, stiching_attrs = get_set_item_panels(ipd_doc,panels)
	else:
		panels, stiching_attrs = get_item_panels(ipd_doc,panels)
	y = copy.deepcopy(x)
	completed_items_json = get_complete_cut_structure(x,stiching_attrs)
	incomplete_items_json = get_incomplete_cut_structure(ipd_doc, panels, stiching_attrs, y)
	return completed_items_json,incomplete_items_json

def get_item_panels(ipd_doc,panels):
	stiching_attrs = {ipd_doc.stiching_attribute : []}
	for item in ipd_doc.stiching_item_details:
		panels[item.stiching_attribute_value] = 0
		stiching_attrs[ipd_doc.stiching_attribute].append(item.stiching_attribute_value)	
	return panels,stiching_attrs

def get_complete_cut_structure(x,stiching_attrs):
	for item in x['items']:
		for val in item['values']:
			item['values'][val] = 0
	x = x | stiching_attrs
	return x

def get_incomplete_cut_structure(ipd_doc,panels, stiching_attrs, y):
	if ipd_doc.is_set_item:
		for item in y['items']:
			for val in item['values']:
				item['values'][val] = panels[item['attributes'][ipd_doc.set_item_attribute]]
	else:
		for item in y['items']:
			for val in item['values']:
				item['values'][val] = panels
	y = y | stiching_attrs
	return y

def add_additional_attributes(ipd_doc,x):
	x['is_set_item'] = ipd_doc.is_set_item
	x['set_item_attr'] = ipd_doc.set_item_attribute
	x["stiching_attr"] = ipd_doc.stiching_attribute
	total_qty = {}
	for item in x['primary_attribute_values']:
		total_qty[item] = 0
	x['total_qty'] = total_qty

	return x

def get_set_item_panels(ipd_doc,panels):
	m = {ipd_doc.stiching_attribute : {}}
	for item in ipd_doc.stiching_item_details:
		if item.set_item_attribute_value in panels:
			panels[item.set_item_attribute_value][item.stiching_attribute_value] = 0
			m[ipd_doc.stiching_attribute][item.set_item_attribute_value].append(item.stiching_attribute_value)
		else:
			panels[item.set_item_attribute_value] = {}
			panels[item.set_item_attribute_value][item.stiching_attribute_value] = 0
			m[ipd_doc.stiching_attribute][item.set_item_attribute_value] = []
			m[ipd_doc.stiching_attribute][item.set_item_attribute_value].append(item.stiching_attribute_value)
	return panels,m

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
			"used_weight":item.used_weight,
			"balance_weight":item.balance_weight,
		})
	return item_details	

@frappe.whitelist()
def get_items(lot):
	lot_doc = frappe.get_doc("Lot",lot)
	items = fetch_order_item_details(lot_doc.lot_order_details, lot_doc.production_detail)
	return items

@frappe.whitelist()
def get_cloth1(cutting_plan):
	cutting_plan_doc = frappe.get_doc("Cutting Plan", cutting_plan)
	ipd_doc = frappe.get_doc("Item Production Detail", cutting_plan_doc.production_detail)
	
	item_attributes = get_attribute_details(cutting_plan_doc.item)
	cloth_combination = get_cloth_combination(ipd_doc)
	stitching_combination = get_stitching_combination(ipd_doc)
	cloth_detail = {}
	for cloth in ipd_doc.cloth_detail:
		cloth_detail[cloth.name1] = cloth.cloth

	cloth_details = {}
	accessory_detail = {}
	for item in cutting_plan_doc.items:
		variant = frappe.get_doc("Item Variant", item.item_variant)
		attr_details = item_attribute_details(variant, item_attributes)
		c = calculate_cloth(ipd_doc, attr_details, item.quantity, cloth_combination, stitching_combination)
		for c1 in c:
			key = (c1["cloth_type"], c1["colour"], c1["dia"])
			cloth_details.setdefault(key, 0)
			cloth_details[key] += c1["quantity"]

			if c1["type"] == "accessory":
				accessory_detail.setdefault(key,0)
				accessory_detail[key] += c1["quantity"]

	required_cloth_details = []
	for k in cloth_details:
		cloth_name = get_or_create_variant(cloth_detail[k[0]], {ipd_doc.packing_attribute: k[1], 'Dia': k[2]})
		required_cloth_details.append({
			"cloth_item_variant": cloth_name,
			"cloth_type": k[0],
			"colour": k[1],
			'dia': k[2],
			"required_weight": cloth_details[k],
			"weight":0.0
		})

	required_accessory_details = []
	for k in accessory_detail:
		cloth_name = get_or_create_variant(cloth_detail[k[0]], {ipd_doc.packing_attribute: k[1], 'Dia': k[2]})
		required_accessory_details.append({
			"cloth_item_variant": cloth_name,
			"cloth_type": k[0],
			"colour": k[1],
			'dia': k[2],
			"required_weight": accessory_detail[k],
			"weight":0.0
		})	

	cutting_plan_doc.set("cutting_plan_accessory_details", required_accessory_details)
	cutting_plan_doc.set("cutting_plan_cloth_details", required_cloth_details)
	cutting_plan_doc.save()

def item_attribute_details(variant, item_attributes):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute != item_attributes['dependent_attribute']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

@frappe.whitelist()
def calculate_laysheets(cutting_plan):
	frappe.enqueue(calc, "short", cutting_plan=cutting_plan)

def calc(cutting_plan):	
	cp_doc = frappe.get_doc("Cutting Plan",cutting_plan)
	item_details = fetch_order_item_details(cp_doc.items,cp_doc.production_detail)
	completed, incomplete = get_complete_incomplete_structure(cp_doc.production_detail,item_details)
	cp_doc.completed_items_json = completed
	cp_doc.incomplete_items_json = incomplete
	for item in cp_doc.cutting_plan_cloth_details:
		item.used_weight = 0
		item.balance_weight = 0

	for item in cp_doc.cutting_plan_accessory_details:
		item.used_weight = 0
	cp_doc.save()

	cls_list = frappe.get_list("Cutting LaySheet",filters = {"cutting_plan":cutting_plan},pluck = "name")
	for cls in cls_list:
		update_cutting_plan(cls)