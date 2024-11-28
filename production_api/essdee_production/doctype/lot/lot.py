# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
from frappe.model.document import Document
from six import string_types
from frappe.utils import flt, add_days
from production_api.production_api.doctype.item.item import create_variant, get_variant, get_attribute_details, get_or_create_variant
from itertools import groupby, zip_longest
import math
from production_api.essdee_production.doctype.holiday_list.holiday_list import get_next_date
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details

class Lot(Document):
	def before_submit(self):
		if len(self.bom_summary) == 0:
			frappe.throw("BOM is not calculated")

	def before_validate(self):
		if self.get('item_details') and len(self.lot_time_and_action_details) == 0:
			items = save_item_details(self.item_details, dependent_attr=self.get('dependent_attribute_mapping'))
			self.set("items",items)

		if self.get('order_item_details') and len(self.lot_time_and_action_details) == 0:
			order_items = save_order_item_details(self.order_item_details)
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
def save_order_item_details(item_details, dependent_attr = None):
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
	if len(item_details) == 0:
		return []
	items = item_details[0]
	item_list = []
	for item in items['items']:
		if item['primary_attribute']:
			attributes = item['attributes']
			attributes[items['dependent_attribute']] = items['final_state']	
			for value in item['values'].keys():
				item1 = {}
				attributes[item['primary_attribute']] = value
				variant_name = get_variant(items['item'], attributes)
				if not variant_name:
					variant1 = create_variant(items['item'], attributes, dependent_attr=dependent_attr)
					variant1.insert()
					variant_name = variant1.name

				item1['item_variant'] = variant_name
				item1['quantity'] = item['values'][value]
				item_list.append(item1)
		else:
			item1 = {}
			attributes = item['attributes']
			variant_name = item['item']
			variant_name = get_variant(item['item'], attributes)
			if not variant_name:
				variant1 = create_variant(item['item'], attributes)
				variant1.insert()
				variant_name = variant1.name
			item1['item_variant'] = variant_name
			item1['qty'] = item['values']['qty']
			item_list.append(item1)
	return item_list


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

def save_item_details(item_details, dependent_attr=None):
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

@frappe.whitelist()
def get_item_list_details(lot):
	doc = frappe.get_doc("Lot",lot)
	items = []
	for item in doc.items:
		items.append(item.as_dict())

	return items	

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

	for item in items:
		d[item] = {}
		for idx,val in enumerate(items[item]):
			d[item][val['action']] = idx
	
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
		master_doc = frappe.get_doc("Action Master",item["master"])
		child_table = []
		x = 1
		day = start_date
		day2 = start_date
		for master in master_doc.details:
			day = get_next_date(day, master.lead_time)
			struct = {
				"action":master.action,
				"lead_time":master.lead_time,
				"department":master.department,
				"date":day,
				"rescheduled_date":day,
				"planned_start_date":day2,
				"rescheduled_start_date":day2,
				"index2":x
			}
			if master.work_station:
				index = d[item['colour']][master.action]
				struct["work_station"] = items[item['colour']][index]['work_station']
			day2 = get_next_date(day2, master.lead_time)	
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

@frappe.whitelist()
def get_select_options(lot):
	lot_doc = frappe.get_doc("Lot",lot)
	select_options = []
	for item in lot_doc.lot_time_and_action_details:
		select_options.append(item.colour)
	return select_options

@frappe.whitelist()
def get_action_master_details(master_list):
	if isinstance(master_list,string_types):
		master_list = json.loads(master_list)
	work_station = {}
	for item in master_list:
		work_station[item['colour']] = []
		master_doc = frappe.get_doc("Action Master",item['master'])
		for action in master_doc.details:
			if action.work_station:
				work_station[item['colour']].append(action.as_dict())
	
	return work_station

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

	for item in items:
		d[item] = {}
		for idx,val in enumerate(items[item]):
			d[item][val['action']] = idx
	
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
		master_doc = frappe.get_doc("Action Master",item["master"])
		child_table = []
		x = 1
		day = start_date
		day2 = start_date
		for master in master_doc.details:
			day = get_next_date(day, master.lead_time)
			struct = {
				"action":master.action,
				"lead_time":master.lead_time,
				"department":master.department,
				"date":day,
				"rescheduled_date":day,
				"planned_start_date":day2,
				"rescheduled_start_date":day2,
				"index2":x
			}
			if master.work_station:
				index = d[item['colour']][master.action]
				struct["work_station"] = items[item['colour']][index]['work_station']
			day2 = get_next_date(day2, master.lead_time)	
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

@frappe.whitelist()
def get_select_options(lot):
	lot_doc = frappe.get_doc("Lot",lot)
	select_options = []
	for item in lot_doc.lot_time_and_action_details:
		select_options.append(item.colour)
	return select_options

@frappe.whitelist()
def get_action_master_details(master_list):
	if isinstance(master_list,string_types):
		master_list = json.loads(master_list)
	work_station = {}
	for item in master_list:
		work_station[item['colour']] = []
		master_doc = frappe.get_doc("Action Master",item['master'])
		for action in master_doc.details:
			if action.work_station:
				work_station[item['colour']].append(action.as_dict())
	
	return work_station

@frappe.whitelist()
def get_order_details(doc_name):
	doc = frappe.get_doc("Lot", doc_name)
	doc.calculate_order()
	doc.save()