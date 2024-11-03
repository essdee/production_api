# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
from six import string_types
from frappe.model.document import Document
from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details
from production_api.production_api.doctype.item.item import get_or_create_variant, get_attribute_details
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import calculate_cloth, get_cloth_combination

class CuttingPlan(Document):
	def autoname(self):
		self.naming_series = "CP-.YY..MM.-.{#####}."
		
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
	print(vars(ipd_doc))
	item_attributes = get_attribute_details(item_name)
	cloth_combination = get_cloth_combination(ipd_doc)
	cloth_detail = {}
	for cloth in ipd_doc.cloth_detail:
		if cloth.is_bom_item:
			cloth_detail[cloth.name1] = cloth.cloth

	cut_attrs_list = []	
	for cut_attrs in ipd_doc.cutting_attributes:
		cut_attrs_list.append(cut_attrs.attribute)
	for item in items:
		variant = frappe.get_doc("Item Variant", item['item_variant'])
		attr_details = item_attribute_details(variant, item_attributes)
		cloths = calculate_cloth({},ipd_doc,cloth_combination, attr_details, item['quantity'],cloth_detail,cut_attrs_list)
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

@frappe.whitelist()
def get_cloth1(cutting_plan):
	cutting_plan_doc = frappe.get_doc("Cutting Plan", cutting_plan)
	ipd_doc = frappe.get_doc("Item Production Detail", cutting_plan_doc.production_detail)

	item_attributes = get_attribute_details(cutting_plan_doc.item)
	cloth_combination = get_cloth_combination1(ipd_doc)
	stitching_combination = get_stitching_combination(ipd_doc)
	print(item_attributes, cloth_combination, stitching_combination)
	cloth_detail = {}
	for cloth in ipd_doc.cloth_detail:
		if cloth.is_bom_item:
			cloth_detail[cloth.name1] = cloth.cloth
	print(cloth_detail)

	cloth_details = {}

	for item in cutting_plan_doc.items:
		variant = frappe.get_doc("Item Variant", item.item_variant)
		attr_details = item_attribute_details(variant, item_attributes)
		c = calculate_cloth1(ipd_doc, variant, attr_details, item.quantity, cloth_combination, stitching_combination)
		for c1 in c:
			key = (c1["cloth_type"], c1["colour"], c1["dia"])
			cloth_details.setdefault(key, 0)
			cloth_details[key] += c1["quantity"]

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

	print(required_cloth_details)
	cutting_plan_doc.set("cutting_plan_cloth_details", required_cloth_details)
	cutting_plan_doc.save()


def item_attribute_details(variant, item_attributes):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute != item_attributes['dependent_attribute']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

@frappe.whitelist()
def get_cutting_laysheet_details(cutting_plan):
	cut_lay = frappe.qb.DocType("Cutting LaySheet")

def get_stitching_combination(ipd_doc):
	stitching_combination = {}

	for detail in ipd_doc.stiching_item_combination_details:
		stitching_combination.setdefault(detail.major_attribute_value, {})
		stitching_combination[detail.major_attribute_value][detail.set_item_attribute_value] = detail.attribute_value

	return {
		"stitching_attribute": ipd_doc.stiching_attribute,
		"stitching_attribute_count": {i.stiching_attribute_value:i.quantity for i in ipd_doc.stiching_item_details},
		"is_same_packing_attribute": ipd_doc.is_same_packing_attribute,
		"stitching_combination": stitching_combination,
	}


def get_cloth_combination1(ipd_doc):
	cutting_attributes = [i.attribute for i in ipd_doc.cutting_attributes]
	cloth_attributes = [i.attribute for i in ipd_doc.cloth_attributes]

	cutting_combination = {}
	cloth_combination = {}

	cutting_items = json.loads(ipd_doc.cutting_items_json)
	cutting_cloths = json.loads(ipd_doc.cutting_cloths_json)
	for item in cutting_items["items"]:
		cutting_combination[get_key(item, cutting_attributes)] = (item["Dia"], item["Weight"])
	for item in cutting_cloths["items"]:
		cloth_combination[get_key(item, cloth_attributes)] = item["Cloth"]

	return {
		"cutting_attributes": cutting_attributes,
		"cloth_attributes": cloth_attributes,
		"cutting_combination": cutting_combination,
		"cloth_combination": cloth_combination,
	}

def get_key(item, attrs):
	key = []
	for attr in attrs:
		key.append(item[attr])
	return tuple(key)

# This function does not calculate for set item
def calculate_cloth1(ipd_doc, variant, variant_attrs, qty, cloth_combination, stitching_combination):
	if stitching_combination["stitching_attribute"] in cloth_combination["cloth_attributes"] and stitching_combination["stitching_attribute"] not in cloth_combination["cutting_attributes"]:
		frappe.throw(f"Cannot calculate cloth quantity without {stitching_combination['stitching_attribute']} in Cloth Weight Combination.")
	
	cloth_detail = []

	if stitching_combination["stitching_attribute"] in cloth_combination["cutting_attributes"]:
		frappe.throw("Please contact the developer team. Feature not implemented")
	else:
		dia, weight = cloth_combination["cutting_combination"][get_key(variant_attrs, cloth_combination["cutting_attributes"])]
		cloth_type = cloth_combination["cloth_combination"][get_key(variant_attrs, cloth_combination["cloth_attributes"])]
		cloth_detail.append({
			"cloth_type": cloth_type,
			"colour": variant_attrs[ipd_doc.packing_attribute],
			"dia": dia,
			"quantity": weight * qty,
		})
	return cloth_detail
