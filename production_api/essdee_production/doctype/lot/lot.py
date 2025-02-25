# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe, json, math
from six import string_types
from frappe.utils import flt
from itertools import groupby, zip_longest
from frappe.model.document import Document
from production_api.essdee_production.doctype.holiday_list.holiday_list import get_next_date
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_group_index
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details

class Lot(Document):
	def before_submit(self):
		if len(self.bom_summary) == 0:
			frappe.throw("BOM is not calculated")

	def before_validate(self):
		if self.get('item_details'):
			items = save_item_details(self.item_details)
			self.set("items",items)

		if self.get('order_item_details') and len(self.lot_time_and_action_details) == 0:
			order_items = save_order_item_details(self.production_detail, self.lot_order_details, self.order_item_details)
			self.set('lot_order_details',order_items)

		if self.is_new(): 
			if len(self.items) > 0:
				self.calculate_order()
		else:
			if len(self.lot_time_and_action_details) == 0 :	
				doc = frappe.get_doc("Lot",self.name)
				if len(doc.items) == 0 and len(self.items) > 0:
					self.calculate_order()

				qty = 0
				for item in self.items:
					qty = qty + item.qty
				self.total_quantity = qty

		if self.get("action_details"):
			update_time_and_action(self.action_details,self.lot_time_and_action_details)
	
	def calculate_order(self):	
		if self.production_detail and len(self.lot_time_and_action_details) == 0:
			previous_data = {}
			for item in self.lot_order_details:
				set_combination = item.set_combination
				if isinstance(set_combination, string_types):
					set_combination = json.loads(set_combination)
				set_combination.update({"variant":item.item_variant})
				set_combination = frozenset(set_combination)

				previous_data[set_combination] = {"cut_qty":item.cut_qty,"stich_qty":item.stich_qty,"pack_qty":item.pack_qty}
			items, qty = calculate_order_details(self.get('items'), self.production_detail, self.packing_uom, self.uom)
			x = []
			if len(items) == 0:
				for item in self.items:
					x.append({'item_variant': item.item_variant, 'quantity':item.qty })
					qty += item.qty
				self.set('lot_order_details',x)
				self.set('total_order_quantity', qty)
			else:
				for item in items:
					key = item['set_combination']
					if isinstance(key, string_types):
						key = json.loads(key)
					key.update({"variant":item['item_variant']})
					key = frozenset(key)
					if previous_data.get(key):
						item.update(
							{
								"cut_qty":previous_data[key]['cut_qty'],
								"stich_qty":previous_data[key]['stich_qty'],
								"pack_qty":previous_data[key]['pack_qty'],
							}
						)
				self.set('lot_order_details',items)
				self.set('total_order_quantity', qty)

	def onload(self):
		if self.production_detail:
			item_details = fetch_item_details(self.get('items'), self.production_detail)
			self.set_onload('item_details', item_details)
			if len(self.lot_order_details) > 0:
				items = fetch_order_item_details(self.get('lot_order_details'), self.production_detail)
				x = json.dumps(items[0])
				self.db_set('lot_order_details_json', x, update_modified=False)
				self.set_onload('order_item_details', items)

		if len(self.lot_time_and_action_details) > 0:
			items = get_time_and_action_process(self.lot_time_and_action_details)
			self.set_onload('action_details',items)		

def get_time_and_action_process(action_details):
	items = []
	for item in action_details:
		out = frappe.db.sql( 
			""" SELECT * FROM `tabTime and Action Detail` AS t_and_a WHERE t_and_a.parent = %s AND t_and_a.completed = 0
				ORDER BY t_and_a.idx ASC LIMIT 1 """,
			(item.time_and_action,),
			as_dict=1
		)
		if len(out) > 0:
			out = out[0]
			out['colour'] = item.colour
			out['master'] = item.master
			out['process'] = True
			items.append(out)
		else:
			items.append({
				"colour":item.colour,
				"master":item.master,
				"action":"Completed",
				"department":None,
				"date":None,
				"rescheduled_date":None,
				"process":False
			})	
	return items

def calculate_order_details(items, production_detail, packing_uom, final_uom):
	item_detail = frappe.get_cached_doc("Item Production Detail", production_detail)
	final_list = []
	doc = frappe.get_cached_doc("Item", item_detail.item)
	dept_attr = None
	pack_stage = None
	if item_detail.dependent_attribute:
		pack_stage = item_detail.pack_in_stage
		dept_attr = item_detail.dependent_attribute
	uom_factor = get_uom_conversion_factor(doc.uom_conversion_details,final_uom, packing_uom)
	final_qty = 0
	if item_detail.is_set_item:
		attrs = {}
		parts   = []	
		comb_dict = {}
		for attr in item_detail.set_item_combination_details:
			comb_dict.setdefault(attr.major_attribute_value, {})
			comb_dict[attr.major_attribute_value].setdefault(attr.set_item_attribute_value, attr.attribute_value)
			if attr.set_item_attribute_value not in parts:
				parts.append(attr.set_item_attribute_value)
	x = 0
	if item_detail.is_set_item:
		major_part = item_detail.major_attribute_value
		for attr in item_detail.packing_attribute_details:
			for part in parts:
				colour = comb_dict[attr.attribute_value][part]
				item_list = [] 
				for item in items:
					variant = frappe.get_cached_doc("Item Variant", item.item_variant)
					qty = (item.qty * uom_factor)
					if item_detail.auto_calculate:
						qty = qty / item_detail.packing_attribute_no
					else:
						qty = qty / item_detail.packing_combo
					attrs = {}
					for attribute in variant.attributes:
						attribute = attribute.as_dict()
						if attribute.attribute == dept_attr:
							attrs[attribute.attribute] = pack_stage
						else:	
							attrs[attribute.attribute] = attribute['attribute_value']
					attrs[item_detail.packing_attribute] = colour
					attrs[item_detail.set_item_attribute] = part
					if not item_detail.auto_calculate:
						major_attr = attrs[item_detail.set_item_attribute]
						q = get_quantity(major_attr, item_detail.packing_attribute_details)	
					new_variant = get_or_create_variant(variant.item, attrs,dependent_attr=item_detail.dependent_attribute_mapping)
					temp_qty = math.ceil(qty) if item_detail.auto_calculate else math.ceil(qty * flt(q))
					if item_detail.major_attribute_value == part:
						final_qty += temp_qty

					d = {
						"item_variant": new_variant,
						"quantity": temp_qty,
						"row_index":x,
						"table_index": 0,
						"set_combination":{}
					}
					if part == major_part:
						d['set_combination']['major_part'] = part
						d['set_combination']['major_colour'] = colour
					else:
						d['set_combination']['major_part'] = major_part
						d['set_combination']['major_colour'] = comb_dict[attr.attribute_value][major_part]
					item_list.append(d)
				x = x + 1		
				final_list = final_list + item_list
	else:	
		for attr in item_detail.packing_attribute_details:
			item_list = [] 
			for item in items:
				variant = frappe.get_cached_doc("Item Variant", item.item_variant)
				qty = (item.qty * uom_factor)
				if item_detail.auto_calculate:
					qty = qty / item_detail.packing_attribute_no
				else:
					qty = qty / item_detail.packing_combo
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
				item_list.append({
					"item_variant": new_variant,
					"quantity": temp_qty,
					"row_index":x,
					"table_index": 0,
					"set_combination":{"major_colour":attr.attribute_value},
				})
			x = x + 1
			final_list = final_list + item_list

	return final_list, final_qty

def save_order_item_details(name, lot_order_details, item_details):
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
	pack_attr, set_attr, is_set = frappe.get_value("Item Production Detail",name, ['packing_attribute', 'set_item_attribute', 'is_set_item'])
	qty_dict = {}
	for item in lot_order_details:
		variant_doc = frappe.get_cached_doc("Item Variant", item.item_variant)
		attrs = variant_attribute_details(variant_doc)
		x = {
			pack_attr : attrs[pack_attr]
		}
		if is_set:
			x[set_attr] = attrs[set_attr]
		tup = tuple(sorted(x.items()))
		qty_dict[tup] = {
			"cut_qty":item.cut_qty,
			"pack_qty":item.pack_qty,
			"stich_qty":item.stich_qty,
		}

	items = []
	row_index = 0
	table_index = -1
	for group in item_details:
		table_index += 1
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			for attr, values in item['values'].items():
				item1 = {}
				quantity = values.get('qty')
				if not quantity:
					quantity = 0
				item_attributes[item.get('primary_attribute')] = attr
				variant = get_or_create_variant(item_name,item_attributes)
				item1['item_variant'] = variant	
				item1['quantity'] = quantity
				item1['row_index'] = row_index
				item1['table_index'] = 0
				x = {
					pack_attr : item_attributes[pack_attr]
				}
				if is_set:
					x[set_attr] = item_attributes[set_attr]
				tup = tuple(sorted(x.items()))
				item1['cut_qty'] = qty_dict[tup]['cut_qty']
				item1['pack_qty'] = qty_dict[tup]['pack_qty']
				item1['stich_qty'] = qty_dict[tup]['stich_qty']
				item1['set_combination'] = item['item_keys']
				items.append(item1)
			row_index += 1
	return items

def update_time_and_action(action_details,lot_action_details):
	if isinstance(action_details,string_types):
		action_details = json.loads(action_details)
	for item1,item2 in zip_longest(action_details,lot_action_details):
		if item1['process']:
			doc = frappe.get_doc("Time and Action",item2.time_and_action)
			for i in doc.details:
				if i.name == item1['name'] and item1['actual_date']:
					i.actual_date = item1['actual_date']
					i.reason = item1['reason']
					doc.save()
					break

def save_item_details(item_details):
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
	if len(item_details) == 0:
		return []
	item = item_details[0]
	items = []
	for id1, row in enumerate(item['items']):
		if row['primary_attribute']:
			attributes = row['attributes']
			attributes[item['dependent_attribute']] = item['final_state']	
			for id2, val in enumerate(row['values'].keys()):
				attributes[row['primary_attribute']] = val
				item1 = {}
				variant_name = get_or_create_variant(item['item'], attributes)
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
			variant_name = get_or_create_variant(item['item'], attributes)
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
	variant_attr_details = get_attribute_details(grp_variant, dependent_attr_mapping=dependent_attr_map_value)
	primary_attr = variant_attr_details['primary_attribute']
	uom = get_isfinal_uom(production_detail)['uom']
	doc = frappe.get_cached_doc("Item", grp_variant)
	item_structure = get_item_details(grp_variant,attr_details=variant_attr_details, uom=uom,production_detail=production_detail, dependent_attr_mapping=dependent_attr_map_value)

	for key, variants in groupby(items, lambda i: i['table_index']):
		variants = list(variants)
		item1 = {}
		values = {}	
		for variant in variants:
			current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
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
def fetch_order_item_details(items, production_detail, process=None ):
	ipd_doc = frappe.get_doc("Item Production Detail", production_detail)
	if isinstance(items, string_types):
		items = json.loads(items)
	field = "quantity"
	if process:
		prs_doc = frappe.get_cached_doc("Process", process)
		if prs_doc.is_group:
			for prs in prs_doc.process_details:
				process = prs.process_name
				break
			
		field = "quantity" if process == ipd_doc.cutting_process else "cut_qty" if process == ipd_doc.stiching_process else  "stich_qty" if process == ipd_doc.packing_process else None
		if not field:
			stage = None
			for prs in ipd_doc.ipd_processes:
				if prs.process_name == process:
					stage = prs.stage
					break
			if stage:
				field = "cut_qty" if stage == ipd_doc.stiching_in_stage else "stich_qty" if stage == ipd_doc.pack_in_stage else "pack_qty"

	items = [item.as_dict() for item in items]
	item_details = []
	items = sorted(items, key = lambda i: i['row_index'])

	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			"item_keys": {},
			"is_set_item": ipd_doc.is_set_item,
			"set_attr": ipd_doc.set_item_attribute,
			"pack_attr": ipd_doc.packing_attribute,
			"major_attr_value": ipd_doc.major_attribute_value,
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			"dependent_attribute": current_item_attribute_details['dependent_attribute'],
			"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
			'values': {},
		}

		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0}
			for variant in variants:
				set_combination = variant.set_combination
				if isinstance(set_combination, string_types):
					set_combination = json.loads(set_combination)
				if set_combination:
					if set_combination.get("major_part"):
						item['item_keys']['major_part'] = set_combination.get("major_part")

					if set_combination.get("major_colour"):
						item['item_keys']['major_colour'] = set_combination.get("major_colour")		

				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'qty': getattr(variant, field, 0),
						}
						break
		else:
			item['values']['default'] = {
				'qty': getattr(variants[0], field, 0),
			}
			
		index = get_item_group_index(item_details, current_item_attribute_details)
		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				"dependent_attribute": current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				'additional_parameters': current_item_attribute_details['additional_parameters'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return item_details

def get_quantity(attr, packing_attribute_details):
	for item in packing_attribute_details:
		if item.attribute_value == attr:
			return item.quantity

def get_item_attribute_details(variant, item_attributes):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute in item_attributes['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

def variant_attribute_details(variant):
	attribute_details = {}
	for attr in variant.attributes:
		attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

@frappe.whitelist()
def get_item_details(item_name, attr_details = None, uom=None, production_detail=None, dependent_state=None, dependent_attr_mapping=None):
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	if not attr_details:
		item = get_attribute_details(item_name, dependent_attr_mapping=dependent_attr_mapping)
	else:
		item = attr_details	
	pack_out_stage = frappe.get_value("Item Production Detail", production_detail,"pack_out_stage")
	if uom:
		item['default_uom'] = uom
	final_state = None
	final_state_attr = None
	item['items'] = []
	if item['dependent_attribute']:
		attribute = dependent_state if dependent_state else pack_out_stage
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
		doc = frappe.get_cached_doc("Item", item['item'])
		final_state_attr = []
		x = [attr.attribute for attr in doc.attributes]
		final_state_attr = final_state_attr + x
		item['final_state_attr'] = final_state_attr
		
	if production_detail:
		pack_attr_value = frappe.get_value("Item Production Detail", production_detail, "packing_attribute")
		item['packing_attr'] = pack_attr_value
		item['primary_attribute_values'] = get_ipd_primary_values(production_detail)
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
		item_doc = frappe.get_cached_doc("Item", item)
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
	grp_variant_doc = frappe.get_cached_doc("Item Variant", data[0].item_variant)
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
		doc = frappe.get_cached_doc("Item Variant", item['item_variant'])
		temp_attr = {}
		for attr in doc.attributes:
			if attr.attribute != dept_attr:
				temp_attr[attr.attribute] = attr.attribute_value
		temp_attr['Ratio'] = item['ratio']
		temp_attr['MRP'] = item['mrp']	
		attr_list.append(temp_attr)
	return attribute_list, attr_list

# @frappe.whitelist()
# def get_item_list_details(lot):
# 	doc = frappe.get_doc("Lot",lot)
# 	items = []
# 	for item in doc.items:
# 		items.append(item.as_dict())

# 	return items	

@frappe.whitelist()
def get_packing_attributes(ipd):
	ipd_doc = frappe.get_doc("Item Production Detail",ipd)
	colours = []
	sizes = ""
	ratios = []
	combo = None

	if ipd_doc.auto_calculate:
		combo = ipd_doc.packing_attribute_no

	for item in ipd_doc.packing_attribute_details:
		colours.append(item.attribute_value)
		if not combo:
			ratios.append(ipd_doc.packing_combo/item.quantity)

	if ipd_doc.is_set_item:
		set_mapping = None
		for item in ipd_doc.item_attributes:
			if item.attribute == ipd_doc.set_item_attribute:
				set_mapping = item.mapping
				break
		set_map_doc = frappe.get_doc("Item Item Attribute Mapping",set_mapping)
		colour_combo = []
		ratio_combo = []
		index = -1		
		for colour in colours:
			index = index + 1
			for part in set_map_doc.values:
				colour_combo.append(str(colour)+"-"+str(part.attribute_value))
				if not combo:
					ratio_combo.append(ratios[index])
		colours = colour_combo
		ratios = ratio_combo

	mapping = None
	for item in ipd_doc.item_attributes:
		if item.attribute == ipd_doc.primary_item_attribute:
			mapping = item.mapping
			break

	map_doc = frappe.get_doc("Item Item Attribute Mapping",mapping)		
	for item in map_doc.values:
		sizes += item.attribute_value + ","

	return {
		"colours":colours,
		"sizes":sizes,
		"ratios":ratios,
		"combo":combo
	}	

@frappe.whitelist()
def create_time_and_action(lot, item_name, args , values, total_qty, items):
	if isinstance(args,string_types):
		args = json.loads(args)
	if isinstance(values,string_types):
		values = json.loads(values)	
	
	sizes = args['sizes']
	ratios = args['ratios']
	combo = args['combo']
	item_list = values['table']
	start_date = values['start_date']

	sizes = sizes[:-1]
	d = {}
	if isinstance(items,string_types):
		items = json.loads(items)

	lot_items = []
	for idx,item in enumerate(item_list):
		new_doc = frappe.new_doc("Time and Action")
		new_doc.update({
			"lot":lot,
			"item":item_name,
			"sizes":sizes,
			"colour":item['colour'],
			"master":item["master"],
			"start_date":start_date,
		})
		if combo:
			new_doc.qty = math.ceil(flt(total_qty)/flt(combo))
		else:
			new_doc.qty = math.ceil(flt(total_qty)/flt(ratios[idx]))
		child_table = []
		x = 1
		day = start_date
		day2 = start_date
		for colour_item in items[item['colour']]:
			day = get_next_date(day, colour_item['lead_time'])
			struct = {
				"action":colour_item['action'],
				"lead_time":colour_item['lead_time'],
				"department":colour_item['department'],
				"date":day,
				"rescheduled_date":day,
				"planned_start_date":day2,
				"rescheduled_start_date":day2,
				"index2":x
			}
			if colour_item.get('work_station'):
				struct["work_station"] = colour_item['work_station']
			day2 = get_next_date(day2, colour_item['lead_time']	)
			x = x + 1
			child_table.append(struct)

		new_doc.set("details",child_table)
		new_doc.save()
		lot_items.append({
			"colour":item['colour'],
			"master":item["master"],
			"time_and_action":new_doc.name,	
		})
	lot_doc = frappe.get_doc("Lot",lot)
	lot_doc.set("lot_time_and_action_details",lot_items)
	lot_doc.save()

@frappe.whitelist()
def get_time_and_action_details(docname):
	doc = frappe.get_doc("Time and Action",docname)
	item_list = [item.as_dict() for item in doc.details]
	status = doc.status
	return {
		"item_list" : item_list,
		"status" : status
	}	

@frappe.whitelist()
def make_complete(time_and_action):
	t_and_a = frappe.get_doc("Time and Action",time_and_action)
	check = True
	for item in t_and_a.details:
		if not item.actual_date and not item.completed:
			check = False
			break
	if check:
		t_and_a.status = "Completed"
		t_and_a.save()	
	else:
		frappe.msgprint("Not all the Actions are Completed")		

# @frappe.whitelist()
# def get_select_options(lot):
# 	lot_doc = frappe.get_doc("Lot",lot)
# 	select_options = []
# 	for item in lot_doc.lot_time_and_action_details:
# 		select_options.append(item.colour)
# 	return select_options

@frappe.whitelist()
def get_action_master_details(master_list):
	if isinstance(master_list,string_types):
		master_list = json.loads(master_list)
	work_station = {}
	for item in master_list:
		work_station[item['colour']] = []
		master_doc = frappe.get_doc("Action Master",item['master'])
		for action in master_doc.details:
			action_data = action.as_dict()
			capacity_planning = frappe.get_value("Action",action_data['action'],"capacity_planning")
			if capacity_planning:
				name_list = frappe.get_list("Work Station", filters={"action":action_data["action"],"default":True},pluck = "name")
				if not name_list:
					frappe.throw(f"There is no Work Station for Action {action_data['action']}")
				action_data['work_station'] = frappe.get_value("Work Station",name_list[0],"name")
			action_data['master'] = item['master']	
			work_station[item['colour']].append(action_data)
	return work_station

@frappe.whitelist()
def undo_last_update(time_and_action):
	t_and_a = frappe.get_doc("Time and Action",time_and_action)
	index = None
	for item in t_and_a.details:
		if item.completed:
			index = item.idx
	
	for item in t_and_a.details:
		if item.idx == index:
			item.performance = None
			item.actual_date = None
			item.actual_start_date = None
			item.completed = 0
			item.date_diff = None
			item.reason = None
			break
	
	for item in t_and_a.details:
		item.index2 = item.index2 + 2

	if index and index != 1:
		for item in t_and_a.details:
			if item.idx == index + 1:
				item.actual_start_date = None
				break
		for item in t_and_a.details:
			if item.idx == index - 1:
				item.completed = 0
				break
	else:
		for item in t_and_a.details:
			item.index2 = item.idx
			item.rescheduled_date = item.date	
			item.actual_start_date = None
			item.actual_date = None
			item.date_diff = None	
			item.reason = None
			item.performance = None
	t_and_a.save()		

@frappe.whitelist()
def update_order_details(doc_name):
	doc = frappe.get_doc("Lot", doc_name)
	doc.calculate_order()
	doc.save()

@frappe.whitelist()
def get_work_stations(items):
	work_station = {}
	if isinstance(items,string_types):
		items = json.loads(items)
	for item in items:
		if item['action'] != "Completed":
			doc = frappe.get_doc("Time and Action",item['parent'])
			work_station[item['colour']] = []
			for child in doc.details:
				child_data = child.as_dict()
				child_data['master'] = doc.master
				work_station[item['colour']].append(child_data)
	return work_station		

@frappe.whitelist()
def update_t_and_a_ws(datas):
	if isinstance(datas,string_types):
		datas = json.loads(datas)

	for d in datas:
		doc = frappe.get_doc("Time and Action",datas[d][0]['parent'])
		child_table = []
		for data in datas[d]:
			child_table.append({
				"action": data['action'],
				"department":data['department'],
				"lead_time":data['lead_time'],
				"date":data['date'],
				"rescheduled_date":data['rescheduled_date'],
				"actual_date":data['actual_date'],
				"work_station":data['work_station'],
				"date_diff":data['date_diff'],
				"reason":data['reason'],
				"performance":data['performance'],
				"completed":data['completed'],
				"index2":data['index2'],
				"planned_start_date":data['planned_start_date'],
				"rescheduled_start_date":data['rescheduled_start_date'],
				"actual_start_date":data['actual_start_date'],
			})	
		doc.set("details",child_table)
		doc.save()	

@frappe.whitelist()
def get_t_and_a_preview_data(start_date, table):
	if isinstance(table, string_types):
		table = json.loads(table)

	preview_data = {}
	for row in table:
		preview_data[row['colour']] = []
		doc = frappe.get_doc("Action Master",row['master'])
		day = start_date
		for data in doc.details:
			day = get_next_date(day, data.lead_time)
			struct = {
				"action":data.action,
				"lead_time":data.lead_time,
				"department":data.department,
				"date":day,
				"rescheduled_date":day,
			}
			if data.get('work_station'):
				struct["work_station"] = data.work_station
			preview_data[row['colour']].append(struct)
	return preview_data

@frappe.whitelist()
def get_mapping_details(ipd):
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	bom_attribute_list = []
	for bom in ipd_doc.item_bom:
		if bom.attribute_mapping != None:
			doc = frappe.get_cached_doc("Item BOM Attribute Mapping", bom.attribute_mapping)
			bom_attribute_list.append({
				'bom_item': bom.item,
				'bom_attr_mapping_link': bom.attribute_mapping,
				'bom_attr_mapping_based_on': bom.based_on_attribute_mapping,
				'bom_attr_mapping_list': doc.values,
				'doctype': 'Item BOM Attribute Mapping'
			})

	map_dict = {}
	for mapping in bom_attribute_list:	
		bom_item = mapping.get('bom_item')
		mapping = mapping.get('bom_attr_mapping_list')
		data = []
		for d in mapping:
			x = d.index
			if len(data) <= d.index:
				while x >= 0:
					x = x -1
					data.append({"item": [], "bom": []})
			if d.type == "item":
				data[d.index]["item"].append(d.attribute_value)
			elif (d.type == "bom"):
				data[d.index]["bom"].append(d.attribute_value)
			
		i = 0
		while i < len(data):
			if data[i] == None:
				data.splice(i, 1)
			else:
				i = i + 1
		items = "\n"
		for d in data:
			if d.get('item') and d.get('bom'):
				item_str = ", ".join(d['item'])
				bom_str = ", ".join(d['bom'])
				items += f"{item_str} -> {bom_str} <br>"
		map_dict[bom_item] = items
	return map_dict