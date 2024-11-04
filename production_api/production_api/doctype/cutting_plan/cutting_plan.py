# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
from six import string_types
from frappe.model.document import Document
from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details
from production_api.production_api.doctype.item.item import get_or_create_variant, get_attribute_details

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
def get_cloth1(cutting_plan):
	cutting_plan_doc = frappe.get_doc("Cutting Plan", cutting_plan)
	ipd_doc = frappe.get_doc("Item Production Detail", cutting_plan_doc.production_detail)
	
	item_attributes = get_attribute_details(cutting_plan_doc.item)
	cloth_combination = get_cloth_combination(ipd_doc)
	stitching_combination = get_stitching_combination(ipd_doc)
	cloth_detail = {}
	for cloth in ipd_doc.cloth_detail:
		if cloth.is_bom_item:
			cloth_detail[cloth.name1] = cloth.cloth
	cloth_details = {}

	for item in cutting_plan_doc.items:
		variant = frappe.get_doc("Item Variant", item.item_variant)
		attr_details = item_attribute_details(variant, item_attributes)
		c = calculate_cloth(ipd_doc, attr_details, item.quantity, cloth_combination, stitching_combination)
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

	cutting_plan_doc.set("cutting_plan_cloth_details", required_cloth_details)
	cutting_plan_doc.save()

def item_attribute_details(variant, item_attributes):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute != item_attributes['dependent_attribute']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

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

def get_cloth_combination(ipd_doc):
	cutting_attributes = [i.attribute for i in ipd_doc.cutting_attributes]
	cloth_attributes = [i.attribute for i in ipd_doc.cloth_attributes]
	accessory_attributes = [i.attribute for i in ipd_doc.accessory_attributes]
	cutting_combination = {}
	cloth_combination = {}
	accessory_combination = {}

	cutting_items = json.loads(ipd_doc.cutting_items_json)
	cutting_cloths = json.loads(ipd_doc.cutting_cloths_json)
	accessory_items = json.loads(ipd_doc.cloth_accessory_json)

	for item in cutting_items["items"]:
		cutting_combination[get_key(item, cutting_attributes)] = (item["Dia"], item["Weight"])
	for item in cutting_cloths["items"]:
		cloth_combination[get_key(item, cloth_attributes)] = item["Cloth"]
	accessory_attributes.append("Accessory")
	for item in accessory_items["items"]:
		accessory_combination[get_key(item, accessory_attributes)] = (item["Weight"])

	return {
		"cutting_attributes": cutting_attributes,
		"cloth_attributes": cloth_attributes,
		"accessory_attributes":accessory_attributes,
		"cutting_combination": cutting_combination,
		"cloth_combination": cloth_combination,
		"accessory_combination":accessory_combination,
	}

def get_key(item, attrs):
	key = []
	for attr in attrs:
		key.append(item[attr])
	return tuple(key)

def calculate_cloth(ipd_doc, variant_attrs, qty, cloth_combination, stitching_combination):
	attrs = variant_attrs.copy()
	if stitching_combination["stitching_attribute"] in cloth_combination["cloth_attributes"] and stitching_combination["stitching_attribute"] not in cloth_combination["cutting_attributes"]:
		frappe.throw(f"Cannot calculate cloth quantity without {stitching_combination['stitching_attribute']} in Cloth Weight Combination.")

	cloth_detail = []

	if stitching_combination["stitching_attribute"] in cloth_combination["cutting_attributes"]:
		for stiching_attr,attr_qty in stitching_combination["stitching_attribute_count"].items():
			attrs[ipd_doc.stiching_attribute] = stiching_attr
			if cloth_combination["cutting_combination"].get(get_key(attrs, cloth_combination["cutting_attributes"])):
				dia, weight = cloth_combination["cutting_combination"][get_key(attrs, cloth_combination["cutting_attributes"])]	
				cloth_type = cloth_combination["cloth_combination"][get_key(attrs, cloth_combination["cloth_attributes"])]
				weight = weight * qty * attr_qty
				cloth_colour = stitching_combination["stitching_combination"][attrs[ipd_doc.packing_attribute]][stiching_attr]
				cloth_detail.append(add_cloth_detail(weight, ipd_doc.additional_cloth,cloth_type,cloth_colour,dia))
	else:
		dia, weight = cloth_combination["cutting_combination"][get_key(attrs, cloth_combination["cutting_attributes"])]
		cloth_type = cloth_combination["cloth_combination"][get_key(attrs, cloth_combination["cloth_attributes"])]
		weight = weight * qty
		cloth_detail.append(add_cloth_detail(weight, ipd_doc.additional_cloth,cloth_type,attrs[ipd_doc.packing_attribute],dia))

	cloth_accessory_json = ipd_doc.accessory_clothtype_json
	if isinstance(cloth_accessory_json,string_types):
		cloth_accessory_json = json.loads(cloth_accessory_json)

	if ipd_doc.stiching_attribute in cloth_combination["accessory_attributes"] and cloth_accessory_json:
		for stiching_attr, attr_qty in stitching_combination["stitching_attribute_count"].items():
			attrs[ipd_doc.stiching_attribute] = stiching_attr
			for accessory_name, accessory_cloth in cloth_accessory_json.items():
				attrs["Accessory"] = accessory_name
				if cloth_combination["accessory_combination"].get(get_key(attrs, cloth_combination["accessory_attributes"])):
					accessory_weight = cloth_combination["accessory_combination"][get_key(attrs, cloth_combination["accessory_attributes"])]
					accessory_colour = get_accessory_colour(ipd_doc,attrs,accessory_name)
					weight = accessory_weight * qty * attr_qty
					cloth_detail.append(add_cloth_detail(weight, ipd_doc.additional_cloth,accessory_cloth,accessory_colour,dia))
	elif cloth_accessory_json:
		for accessory_name, accessory_cloth in cloth_accessory_json.items():
			attrs["Accessory"] = accessory_name
			accessory_weight = cloth_combination["accessory_combination"][get_key(attrs, cloth_combination["accessory_attributes"])]
			accessory_colour = get_accessory_colour(ipd_doc,attrs,accessory_name)	
			weight = accessory_weight * qty
			cloth_detail.append(add_cloth_detail(weight, ipd_doc.additional_cloth,accessory_cloth,accessory_colour,dia))
	return cloth_detail

def add_cloth_detail(weight, additional_cloth,cloth_type,cloth_colour,dia):
	x = get_additional_cloth(weight, additional_cloth)
	weight = weight + x
	return {
		"cloth_type": cloth_type,
		"colour": cloth_colour,
		"dia": dia,
		"quantity": weight,
	}

def get_accessory_colour(ipd_doc,variant_attrs,accessory):
	for acce in json.loads(ipd_doc.stiching_accessory_json)["items"]:
		if acce[ipd_doc.stiching_major_attribute_value] == variant_attrs[ipd_doc.packing_attribute]:
			return acce[accessory]		

def get_additional_cloth(weight, additional_cloth):
	if additional_cloth:
		x = weight/100
		return  x * additional_cloth
	return 0.0
		