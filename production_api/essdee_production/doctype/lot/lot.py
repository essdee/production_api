# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe, json, math
from six import string_types
from frappe.utils import flt, date_diff
from itertools import groupby, zip_longest
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from production_api.utils import update_if_string_instance
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
			self.lot_hash_value = make_autoname(key="hash")
			if len(self.items) > 0:
				self.calculate_order()
		else:
			cp_plan = frappe.get_value("Lot", self.name, "capacity_planning")
			if self.capacity_planning != cp_plan and len(self.lot_time_and_action_details) > 0:
				frappe.throw("Can't change capacity planning after creating T and A")

			if self.capacity_planning:
				self.version = "V2"
			else:
				self.version = "V1"

			if len(self.lot_time_and_action_details) == 0 :	
				doc = frappe.get_doc("Lot",self.name)
				if len(doc.items) == 0 and len(self.items) > 0:
					self.calculate_order()

				qty = 0
				for item in self.items:
					qty = qty + item.qty
				self.total_quantity = qty

		total_qty = 0
		for item in self.lot_order_details:
			total_qty += vars(item)['quantity']
		self.total_order_quantity = total_qty
		
		if self.get("action_details"):
			update_time_and_action(self.action_details,self.lot_time_and_action_details)
	
	def calculate_order(self):	
		previous_data = {}
		for item in self.lot_order_details:
			set_combination = update_if_string_instance(item.set_combination)
			if set_combination not in [None, ""]:	
				set_combination = set_combination.copy()
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
				key = update_if_string_instance(item['set_combination'])
				if key not in [None, ""]:
					key = key.copy()
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
					new_variant = get_or_create_variant(variant.item, attrs,dependent_attr=item_detail.dependent_attribute_mapping)
					temp_qty = math.ceil(qty) if item_detail.auto_calculate else math.ceil(qty * attr.quantity)
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
	item_details = update_if_string_instance(item_details)
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
	action_details = update_if_string_instance(action_details)
	for item1,item2 in zip_longest(action_details,lot_action_details):
		if item1['process']:
			doc = frappe.get_doc("Time and Action",item2.time_and_action)
			d = {}
			check = False
			for i in doc.details:
				if i.name == item1['name'] and item1['actual_date']:
					check = True
					i.actual_date = item1['actual_date']
					i.reason = item1['reason']
					if i.work_station:
						d[i.name] = {
							"actual_date": item1['actual_date'],
							"reason": item1['reason'],
						}
					if i.actual_date != i.rescheduled_date:
						frappe.db.sql(
							"""
								SELECT name FROM `tabWork Station Action` 
							"""
						)	
					break
			if check:	
				for row in doc.time_and_action_work_station_details:
					if d.get(row.parent_link_value):
						row.actual_date = d[row.parent_link_value]['actual_date']
						row.reason = d[row.parent_link_value]['reason']
				doc.save()	

def save_item_details(item_details):
	item_details = update_if_string_instance(item_details)
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
def fetch_order_item_details(items, production_detail, process=None, includes_packing:bool=False):
	ipd_doc = frappe.get_doc("Item Production Detail", production_detail)
	items = update_if_string_instance(items)
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	field = "quantity"
	if process:
		prs_doc = frappe.get_cached_doc("Process", process)
		if prs_doc.is_group:
			for prs in prs_doc.process_details:
				process = prs.process_name
				break
			
		field = "quantity" if process == ipd_doc.cutting_process else "cut_qty" if process == ipd_doc.stiching_process else  "stich_qty" if process == ipd_doc.packing_process else None
		if includes_packing:
			field = "cut_qty"
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
	primary_values = get_ipd_primary_values(production_detail)
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
		current_item_attribute_details['primary_attribute_values'] = primary_values
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0}
			for variant in variants:
				set_combination = update_if_string_instance(variant.set_combination)
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
				"stiching_attribute": ipd_doc.stiching_attribute,
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	for item in item_details:
		size_wise_total = {}
		total_sum = 0
		for row in item['items']:
			sum = 0
			for val in row['values']:
				size_wise_total.setdefault(val, 0)
				size_wise_total[val] += row['values'][val]['qty']
				sum += row['values'][val]['qty']
			row['total_qty'] = sum
			total_sum += sum
		item['size_wise_total'] = size_wise_total
		item['total_sum'] = total_sum	

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
	if isinstance(data, string_types):
		data = json.loads(data)
	return data

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
def create_time_and_action_v1(lot, item_name, args , values, total_qty, items):
	args = update_if_string_instance(args)
	values = update_if_string_instance(values)	
	
	sizes = args['sizes']
	ratios = args['ratios']
	combo = args['combo']
	item_list = values['table']
	start_date = values['start_date']

	sizes = sizes[:-1]
	d = {}
	items = update_if_string_instance(items)

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
		new_doc.set("end_date", day)
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
def get_time_and_action_v2(lot, item_name, args , values, total_qty, items):
	args = update_if_string_instance(args)
	values = update_if_string_instance(values)	
	
	sizes = args['sizes']
	ratios = args['ratios']
	combo = args['combo']
	item_list = values['table']
	start_date = values['start_date']

	sizes = sizes[:-1]
	d = {}
	items = update_if_string_instance(items)

	ws_allocated_days = {}
	for idx,item in enumerate(item_list):
		for colour_item in items[item['colour']]:
			if colour_item.get('work_station'):
				for ws in colour_item['work_station']:
					if ws_allocated_days.get(ws['work_station']):
						continue
					ws_doc = frappe.get_doc("Work Station", ws['work_station'])
					ws_allocated_days.setdefault(ws['work_station'], {})

					for row in ws_doc.work_station_actions:
						ws_allocated_days[ws['work_station']].setdefault(row.allocated_date, 0)
						ws_allocated_days[ws['work_station']][row.allocated_date] += row.capacity

	cur_allocated_days = {}
	for idx,item in enumerate(item_list):
		colour = item['colour']
		d.setdefault(colour, {})
		d[colour] = {
			"lot":lot,
			"item":item_name,
			"sizes":sizes,
			"colour":colour,
			"master":item["master"],
			"start_date":start_date,
		}
		qty = 0
		if combo:
			qty = math.ceil(flt(total_qty)/flt(combo))
		else:
			qty = math.ceil(flt(total_qty)/flt(ratios[idx]))
		d[colour]['qty'] = qty

		child_table = []
		x = 1
		day = start_date
		day2 = start_date
		cur_allocated_days.setdefault(colour, {})
		for colour_item in items[colour]:
			lead_time = colour_item['lead_time']
			action = colour_item.get('action')
			if colour_item.get('work_station'):
				cur_allocated_days[colour].setdefault(action, {})
				per_day_production = 0
				ws_per_day_production = {}
				for ws in colour_item['work_station']:
					capacity = ws['capacity']/ 100
					one_day_production = ws['target'] * capacity
					ws_per_day_production[ws['work_station']] = one_day_production
					per_day_production += one_day_production
				lead_time = qty / per_day_production
				
				temp_date = day
				max_days = 0
				for ws in colour_item['work_station']:
					work_station = ws['work_station']
					temp_date = day
					temp_max = 0
					capacity = ws['capacity']
					x_capacity = capacity / 100
					one_day_production = ws['target'] * x_capacity
					total_production = math.ceil(ws_per_day_production[ws['work_station']] * lead_time)

					cur_allocated_days[colour][action].setdefault(work_station, {
						"allocated_days": {},
						"per_day_production": {},
						"start_date": None,
						"end_date": None,
						"total_production": total_production,
						"show_allocated": 0,
						"per_day_capacity": capacity,
						"target": ws["target"],
					})
					while total_production > 0:
						if ws_allocated_days[work_station].get(temp_date):
							if ws_allocated_days[work_station].get(temp_date) >= 100:
								temp_date = get_next_date(temp_date, 1)
								continue
							free_capacity = 100 - ws_allocated_days[work_station][temp_date]
							if free_capacity >= capacity:
								temp_day_production = one_day_production
								temp_capacity = capacity
								if temp_day_production > total_production:
									temp_day_production = total_production
									x = one_day_production / capacity
									temp_capacity = temp_day_production / x
								total_production -= temp_day_production
								ws_allocated_days[work_station][temp_date] += temp_capacity
								cur_allocated_days[colour][action][work_station]["allocated_days"][temp_date] = temp_capacity
								cur_allocated_days[colour][action][work_station]['per_day_production'][temp_date] = temp_day_production
							else:
								x = one_day_production / capacity
								temp_day_production = x * free_capacity
								if temp_day_production > total_production:
									temp_day_production = total_production
									free_capacity = temp_day_production / x

								total_production -= temp_day_production
								ws_allocated_days[work_station][temp_date] += free_capacity
								cur_allocated_days[colour][action][work_station]["allocated_days"][temp_date] = free_capacity
								cur_allocated_days[colour][action][work_station]['per_day_production'][temp_date] = temp_day_production
						else:
							temp_day_production = one_day_production
							temp_capacity = capacity
							if temp_day_production > total_production:
								temp_day_production = total_production
								x = one_day_production / capacity
								temp_capacity = temp_day_production / x

							total_production -= temp_day_production
							ws_allocated_days[work_station][temp_date] = temp_capacity
							cur_allocated_days[colour][action][work_station]["allocated_days"][temp_date] = temp_capacity
							cur_allocated_days[colour][action][work_station]['per_day_production'][temp_date] = temp_day_production

						temp_max += 1

						if not cur_allocated_days[colour][action][work_station]['start_date']:
							cur_allocated_days[colour][action][work_station]['start_date'] = temp_date
							day2 = temp_date

						if total_production > 0:
							temp_date = get_next_date(temp_date, 1)
							cur_allocated_days[colour][action][work_station]['end_date'] = temp_date
						elif total_production == 0 and not cur_allocated_days[colour][action][work_station]['end_date']: 	
							cur_allocated_days[colour][action][work_station]['end_date'] = temp_date
					if max_days < temp_max:
						max_days = temp_max

				lead_time = max_days
				colour_item["lead_time"] = lead_time
			day = get_next_date(day2, colour_item['lead_time'])
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
				struct['work_station_details'] = cur_allocated_days[colour][action]

			day2 = get_next_date(day2, colour_item['lead_time'])
			x = x + 1
			child_table.append(struct)
		
		cur_allocated_days[colour]['quantity'] = qty
		d[colour]["details"] = child_table
		d[colour]['end_date'] = day
		d[colour]['master'] = item['master']
	return d

@frappe.whitelist()
def create_time_and_action_v2(details, lot):
	lot_items = []
	details = update_if_string_instance(details)
	for colour in details:
		new_doc = frappe.new_doc("Time and Action")
		new_doc.lot = details[colour]['lot']
		new_doc.item = details[colour]['item'] 
		new_doc.colour = details[colour]['colour']
		new_doc.sizes = details[colour]['sizes'] 
		new_doc.master = details[colour]['master'] 
		new_doc.qty = details[colour]['qty'] 
		new_doc.start_date = details[colour]['start_date'] 
		child_table_data = []
		update_ws_allocated_days = {}
		x = {}
		for row in details[colour]['details']:
			data = {
				"action":row['action'],
				"lead_time":row['lead_time'],
				"department":row['department'],
				"date":row['date'],
				"rescheduled_date": row['rescheduled_date'],
				"planned_start_date": row['planned_start_date'],
				"rescheduled_start_date": row['rescheduled_start_date'],
				"index2": row['index2']
			}
			x.setdefault(row['action'], {})
			if row.get('work_station_details'):
				work_station = ""
				for ws in row['work_station_details']:
					x[row['action']][ws] = {
						"capacity": row['work_station_details'][ws]['per_day_capacity'],
						"target": row['work_station_details'][ws]['target']
					}
					work_station += ws+","
					update_ws_allocated_days.setdefault(ws, [])
					for d, c in row['work_station_details'][ws]['allocated_days'].items():
						update_ws_allocated_days[ws].append({
							"allocated_date": d,
							"lot": details[colour]['lot'],
							"colour": colour,
							"capacity": c,
							"target": row['work_station_details'][ws]['per_day_production'][d],
						})
				work_station = work_station[:-1]	
				data['work_station'] = work_station
		
			child_table_data.append(data)
			new_doc.end_date = row['rescheduled_date']
		new_doc.set("details", child_table_data)
		new_doc.save()

		child_table_data = []
		for row in new_doc.details:
			if row.work_station:
				work_stations = row.work_station.split(",")
				for ws in work_stations:
					capacity = x[row.action][ws]['capacity']
					target = x[row.action][ws]['target']
					child_table_data.append({
						"parent_link_value": row.name,
						"work_station": ws,
						"rescheduled_date": row.rescheduled_date,
						"actual_date": None,
						"date_diff": 0,
						"reason": None,
						"performance": 0,
						"capacity": capacity,
						"target": target,
					})
		new_doc.set("time_and_action_work_station_details", child_table_data)
		new_doc.save()    

		for ws in update_ws_allocated_days:
			for row in update_ws_allocated_days[ws]:
				row['time_and_action'] = new_doc.name

			ws_doc = frappe.get_doc("Work Station", ws)
			table_data = [ws_detail.as_dict() for ws_detail in ws_doc.work_station_actions]
			combined = table_data + update_ws_allocated_days[ws]
			ws_doc.set("work_station_actions", combined)
			ws_doc.save()	

		lot_items.append({
			"colour":colour,
			"master":details[colour]['master'],
			"time_and_action":new_doc.name,	
		})
	lot_doc = frappe.get_doc("Lot",lot)
	lot_doc.set("lot_time_and_action_details",lot_items)
	lot_doc.save()

@frappe.whitelist()
def get_time_and_action_details(docname):
	doc = frappe.get_doc("Time and Action",docname)
	version = frappe.get_cached_value("Lot", doc.lot, "version")
	item_list = []
	if version == "V1":
		item_list = [item.as_dict() for item in doc.details]
	else:
		for row in doc.details:
			if row.work_station and row.completed == 0:
				check = False
				allocated = None
				for ws in row.work_station.split(","):
					allocated_last_date = frappe.db.sql(
						"""
							SELECT allocated_date FROM `tabWork Station Action` WHERE parent = %(ws)s
							AND time_and_action = %(t_and_a)s ORDER BY allocated_date DESC LIMIT 1
						""", {
							"ws": ws,
							"t_and_a": docname
						}, as_dict=True
					)
					if allocated_last_date:
						if allocated in [None]:
							allocated = True
						if row.rescheduled_date < allocated_last_date[0]['allocated_date']:
							check = True
					else:
						allocated = False	
				row = row.as_dict()
				if check:
					row['change_allocation'] = True
				if not allocated:
					row['not_allocated'] = True					
				item_list.append(row)
			else:
				item_list.append(row.as_dict())		
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
def get_action_master_details(master_list, version):
	master_list = update_if_string_instance(master_list)
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
				if version == "V1":
					action_data['work_station'] = frappe.get_value("Work Station",name_list[0],"name")
				else:		
					action_data['work_station'] = [{
						"work_station": frappe.get_value("Work Station",name_list[0],"name"),
						"target": action.target,
						"capacity": 100
					}]
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
	
	child_name = None
	for item in t_and_a.details:
		if item.idx == index:
			child_name = item.name
			item.performance = None
			item.actual_date = None
			item.actual_start_date = None
			item.completed = 0
			item.date_diff = None
			item.reason = None
			break

	for row in t_and_a.time_and_action_work_station_details:
		if row.parent_link_value == child_name:
			row.performance = None
			row.actual_date = None
			row.date_diff = None
			row.reason = None
			break
	
	for item in t_and_a.details:
		item.index2 = item.index2 + 2

	rescheduled_date = None
	if index and index != 1:
		for item in t_and_a.details:
			if item.idx == index + 1:
				item.actual_start_date = None
				break
		for item in t_and_a.details:
			rescheduled_date = item.rescheduled_date
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
			rescheduled_date = item.rescheduled_date
	t_and_a.end_date = rescheduled_date
	t_and_a.save()		

@frappe.whitelist()
def update_order_details(doc_name):
	doc = frappe.get_doc("Lot", doc_name)
	doc.calculate_order()
	doc.save()

@frappe.whitelist()
def get_work_stations(items, lot):
	work_station = {}
	version = frappe.get_value("Lot", lot, "version")
	items = update_if_string_instance(items)
	for item in items:
		if item['action'] != "Completed":
			doc = frappe.get_doc("Time and Action",item['parent'])
			work_station[item['colour']] = []

			if version == "V1":
				for child in doc.details:
					child_data = child.as_dict()
					child_data['master'] = doc.master
					work_station[item['colour']].append(child_data)
			else:
				x = {}
				for row in doc.time_and_action_work_station_details:
					x.setdefault(row.work_station, {
						"target": row.target,
						"capacity": row.capacity
					})
				for child in doc.details:
					action_data = child.as_dict()
					if child.work_station:
						action_data['work_station'] = []
						for ws in child.work_station.split(","):
							action_data['work_station'].append(
								{
									"work_station": ws,
									"target": x[ws]['target'],
									"capacity": x[ws]['capacity']
								}
							)
					action_data['master'] = item['master']	
					work_station[item['colour']].append(action_data)
	return work_station		

@frappe.whitelist()
def update_t_and_a_ws(datas, version):
	datas = update_if_string_instance(datas)
	for d in datas:
		doc = frappe.get_doc("Time and Action",datas[d][0]['parent'])
		child_table = []
		x = {}
		ws_details = {}
		for row in doc.time_and_action_work_station_details:
			ws_details[row.work_station] = {
				"target": row.target,
				"capacity": row.capacity,
			}
		for data, row in zip_longest(datas[d], doc.details):
			d = {
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
			}
			if data['work_station'] and version == "V2":
				work_staion = ""
				target_changed = False
				capacity_changed = False
				for ws in data['work_station']:
					x.setdefault(ws['work_station'], {
						"capacity":ws['capacity'],
						"target": ws['target']
					})
					if ws_details.get(ws['work_station']):
						if ws_details[ws['work_station']]['capacity'] != ws['capacity']:
							capacity_changed = True
						if ws_details[ws['work_station']]['target'] != ws['target']:
							target_changed = True

					work_staion += ws['work_station']+","
				work_staion = work_staion[:-1]
				if row.work_station != work_staion or capacity_changed or target_changed:
					for ws in row.work_station.split(","):
						frappe.db.sql(
							"""
								DELETE FROM `tabWork Station Action` WHERE time_and_action = %(t_and_a)s
								AND parent = %(ws)s 
							""", {
								"t_and_a": doc.name,
								"ws": ws
							}
						)		
				d['work_station'] = work_staion
			child_table.append(d)
		doc.set("details",child_table)
		doc.save()	
		child_table_data = []
		for row in doc.details:
			if row.work_station:
				for ws in row.work_station.split(","):
					child_table_data.append({
						"parent_link_value": row.name,
						"work_station": ws,
						"rescheduled_date": row.rescheduled_date,
						"actual_date": row.actual_date,
						"date_diff": row.date_diff,
						"reason": row.reason,
						"performance": row.performance,
						"target": x.get(ws, {}).get("target", None),
						"capacity": x.get(ws, {}).get("capacity", None),
					})
		doc.set("time_and_action_work_station_details", child_table_data)
		doc.save()

@frappe.whitelist()
def get_t_and_a_preview_data(start_date, table):
	table = update_if_string_instance(table)
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
				'doctype': 'Item BOM Attribute Mapping',
				"qty": bom.qty_of_bom_item,
			})

	map_dict = {}
	for mapping in bom_attribute_list:	
		bom_qty = mapping.get('qty')
		bom_item = mapping.get('bom_item')
		mapping = mapping.get('bom_attr_mapping_list')
		data = []
		for d in mapping:
			x = d.index
			if len(data) <= d.index:
				while x >= 0:
					x = x -1
					data.append({"item": [], "bom": [], "quantity": 0})
			if d.type == "item":
				data[d.index]["item"].append(d.attribute_value)
			elif (d.type == "bom"):
				data[d.index]["bom"].append(d.attribute_value)
			qty = d.quantity
			if d.quantity == 0:
				qty = bom_qty
			data[d.index]['quantity'] = qty	
			
		i = 0
		while i < len(data):
			if data[i] == None:
				data.splice(i, 1)
			else:
				i = i + 1
		items = "\n"
		for d in data:
			if d.get('item'):
				item_str = ", ".join(d['item'])
				bom_str = ", ".join(d['bom'])
				items += f"{item_str} -> {bom_str} / {d['quantity']}<br>"
		map_dict[bom_item] = items
	return map_dict

@frappe.whitelist()
def revert_t_and_a(doc_name):
	doc = frappe.get_doc("Lot", doc_name)
	t_and_a_list = []
	for row in doc.lot_time_and_action_details:
		t_and_a_list.append(row.time_and_action)
		frappe.db.sql(
			"""
				DELETE FROM `tabWork Station Action` WHERE time_and_action = %(t_and_a)s
			""", {
				"t_and_a": row.time_and_action
			}
		)

	doc.set("lot_time_and_action_details", [])
	doc.save()
	t_and_a_list = tuple(t_and_a_list)
	frappe.db.sql(
		f"""
			DELETE FROM `tabTime and Action` WHERE name in {t_and_a_list} 
		"""
	)	
	frappe.db.sql(
		f"""
			DELETE FROM `tabTime and Action Detail` WHERE parent in {t_and_a_list} 
		"""
	)

@frappe.whitelist()
def get_ipd_print_accessory_combination(ipd):
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	stiching_accessory_json = update_if_string_instance(ipd_doc.stiching_accessory_json)
	items = {}
	if ipd_doc.is_set_item:
		for row in stiching_accessory_json['items']:
			items.setdefault(row[ipd_doc.set_item_attribute],{})
			colour_key = row['major_colour']
			if row.get('major_attr_value'):
				colour_key += "("+row['major_attr_value']+")"

			items[row[ipd_doc.set_item_attribute]].setdefault(colour_key,{})
			items[row[ipd_doc.set_item_attribute]][colour_key].setdefault(row['accessory'],{})
			items[row[ipd_doc.set_item_attribute]][colour_key][row['accessory']] = {
				"colour":row['accessory_colour'],
				"cloth_type": row['cloth_type']
			}
	else:
		for row in stiching_accessory_json['items']:
			items.setdefault(row['major_colour'],{})
			items[row['major_colour']].setdefault(row['accessory'],{})
			items[row['major_colour']][row['accessory']] = {
				"colour":row['accessory_colour'],
				"cloth_type": row['cloth_type']
			}			
	return items

@frappe.whitelist()
def fetch_work_stations():
	work_stations = frappe.db.sql(
		"""
			SELECT name, action FROM `tabWork Station`
		""", as_dict=True
	)
	action_dict = {}
	for work_station in work_stations:
		action_dict.setdefault(work_station['action'], [])
		action_dict[work_station['action']].append(work_station['name'])

	return action_dict	

@frappe.whitelist()
def get_allocated_days(t_and_a_data):
	work_station = {}
	items = update_if_string_instance(t_and_a_data)
	for item in items:
		if item['action'] != "Completed":
			doc = frappe.get_doc("Time and Action",item['parent'])
			work_station[item['colour']] = []
			x = {}
			for row in doc.time_and_action_work_station_details:
				x.setdefault(row.work_station, {
					"target": row.target,
					"capacity": round(row.capacity, 2)
				})
			for child in doc.details:
				action_data = child.as_dict()
				if child.work_station and child.completed == 0:
					action_data['work_station'] = []
					for ws in child.work_station.split(","):
						action_data['work_station'].append(
							{
								"work_station": ws,
								"target": x[ws]['target'],
								"capacity": x[ws]['capacity'],
								"allocated_days": get_ws_days(ws, doc.name),
								"changed": False,
							}
						)
				action_data['previous_allocated'] = action_data['work_station']		
				action_data['master'] = item['master']	
				work_station[item['colour']].append(action_data)
	return work_station

def get_ws_days(work_station, t_and_a):
	data = frappe.db.sql(
		"""
			SELECT name, allocated_date, capacity, target FROM `tabWork Station Action` WHERE parent = %(ws)s
			AND time_and_action = %(t_and_a)s ORDER BY allocated_date
		""", {
			"ws": work_station,
			"t_and_a": t_and_a
		}, as_dict=True
	)
	dates = [{
				"allocated":row['allocated_date'],
				"target": row['target'],
				"capacity": round(row['capacity'], 2),
				"name": row['name']
			} for row in data]
	return dates

@frappe.whitelist()
def update_and_unallocate_workstation(data):
	data = update_if_string_instance(data)
	for colour in data:
		for row in data[colour]:
			if not row['work_station']:
				continue
			rescheduled_date = row['rescheduled_date']
			lead_time = row['lead_time']
			lot = frappe.get_value("Time and Action", row['parent'], "lot")
			max_date = rescheduled_date
			for ws, pa in zip_longest(row['work_station'], row['previous_allocated']):
				if not ws['changed']:
					continue
				for day in pa['allocated_days']:
					frappe.db.sql(
						"""
							DELETE FROM `tabWork Station Action` WHERE name = %(row_name)s
						""", {
							"row_name": day['name']
						}
					)
				work_station = ws['work_station']
				ws_doc = frappe.get_doc("Work Station", work_station)	
				for day in ws['allocated_days']:
					if max_date < day['allocated']:
						max_date = day['allocated']
					ws_doc.append("work_station_actions", {
						"allocated_date": day['allocated'],
						"lot": lot,
						"colour": colour,
						"target": day['target'],
						"capacity": day['capacity'],
						"time_and_action": row['parent'],
					})
				ws_doc.save()
			if max_date > rescheduled_date:
				diff = date_diff(max_date, rescheduled_date)
				lead_time += diff
				frappe.db.sql(
					"""
						UPDATE `tabTime and Action Detail` SET lead_time = %(lead)s WHERE name = %(row_name)s
 					""", {
						 "lead": lead_time,
						 "row_name": row['name']
					}
				)
				frappe.get_doc("Time and Action", row['parent']).save()

@frappe.whitelist()
def get_allocated_ws_details():
	ws_list = frappe.get_all("Work Station", pluck="name")
	ws_allocated_days = {}
	ws_date_wise_allocation = {}
	for ws in ws_list:
		ws_doc = frappe.get_doc("Work Station", ws)
		ws_allocated_days.setdefault(ws, {})
		ws_date_wise_allocation.setdefault(ws, {})
		for row in ws_doc.work_station_actions:
			c = round(row.capacity, 2)
			d = str(row.allocated_date)
			ws_allocated_days[ws].setdefault(d, 0)
			ws_allocated_days[ws][d] += c
			ws_date_wise_allocation[ws].setdefault(d, {})
			ws_date_wise_allocation[ws][d].setdefault(row.time_and_action, 0)
			ws_date_wise_allocation[ws][d][row.time_and_action] += c
	return {
		"total_allocated":ws_allocated_days,
		"date_wise_allocated": ws_date_wise_allocation
	}		

def get_ironing_mistake_pf_items(lot):
	lot_doc = frappe.get_doc("Lot", lot)
	items = fetch_order_item_details(lot_doc.lot_order_details, lot_doc.production_detail)
	return items
