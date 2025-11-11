# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, copy
from datetime import datetime
from frappe.model.document import Document
from production_api.utils import update_if_string_instance
from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant
from production_api.production_api.doctype.cutting_laysheet.cutting_laysheet import update_cutting_plan
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_cloth_combination, get_stitching_combination, calculate_cloth

class CuttingPlan(Document):
	def on_update_after_submit(self):
		status = self.status
		percent = frappe.db.get_single_value("MRP Settings", "cloth_allowance_percentage")
		check = True
		for row in self.cutting_plan_cloth_details:
			if row.weight < row.required_weight:
				percent_weight = (row.weight/100) * percent
				if row.weight < (row.required_weight - percent_weight):
					check = False

		updated_status = None			
		if check:
			if status in ['Planned', 'Fabric Partially Received']:
				updated_status = 'Ready to Cut'
		else:
			if status in ['Planned', 'Ready to Cut']:
				updated_status = 'Fabric Partially Received'

		if not updated_status:
			completed_json = update_if_string_instance(self.completed_items_json)
			check = True
			one_colour_completed = False
			for row in completed_json['items']:
				if row['completed']:
					one_colour_completed = True
				if not row['completed']:
					check = False
			if check:
				updated_status = "Completed"	
			elif one_colour_completed:
				updated_status = 'Partially Completed'		
			else:
				updated_status = "Cutting In Progress"	

		for item in self.cutting_plan_cloth_details:
			item.balance_weight = round(item.weight - item.used_weight, 3)
		self.status = updated_status	

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
			self.version = "V3"
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

	def before_submit(self):
		percent = frappe.db.get_single_value("MRP Settings", "cloth_allowance_percentage")
		check = True
		all_zero = True
		for row in self.cutting_plan_cloth_details:
			if row.weight > 0:
				all_zero = False
			if row.weight < row.required_weight:
				percent_weight = (row.weight/100) * percent
				if row.weight < (row.required_weight - percent_weight):
					check = False

		if all_zero:			
			self.status = 'Planned'
		elif not check:
			self.status = 'Fabric Partially Received'
		else:
			self.status = 'Ready to Cut'	

def get_complete_incomplete_structure(ipd,item_details):
	ipd_doc = frappe.get_doc("Item Production Detail",ipd)
	stiching_attrs = None
	panels = {}
	item_details = update_if_string_instance(item_details)
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
		item['completed'] = False
		item['completed_date'] = None
	x = x | stiching_attrs
	return x

def get_incomplete_cut_structure(ipd_doc,panels, stiching_attrs, y):
	if ipd_doc.is_set_item:
		for item in y['items']:
			for val in item['values']:
				item['values'][val] = panels[item['attributes'][ipd_doc.set_item_attribute]].copy()
	else:
		for item in y['items']:
			for val in item['values']:
				item['values'][val] = panels.copy()
	y = y | stiching_attrs
	return y

def add_additional_attributes(ipd_doc,x):
	x['is_set_item'] = ipd_doc.is_set_item
	x['set_item_attr'] = ipd_doc.set_item_attribute
	x["stiching_attr"] = ipd_doc.stiching_attribute
	x['pack_attr'] = ipd_doc.packing_attribute
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
	items = update_if_string_instance(items)
	item_details = []
	for item in items:
		item_details.append({
			"cloth_item_variant":item['cloth_item_variant'],
			"cloth_type":item['cloth_type'],
			"colour":item['colour'],
			"dia":item['dia'],
			"required_weight":item['required_weight'],
			"weight":item['weight'],
			"used_weight": item['used_weight'],
			"balance_weight": round(item['weight'] - item['used_weight'], 3)
		})
	return item_details	

def save_item_details(item_details):
	item_details = update_if_string_instance(item_details)
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
				variant = get_or_create_variant(item_name, item_attributes)
				item1['item_variant'] = variant	
				item1['quantity'] = quantity
				item1['row_index'] = row_index
				item1['table_index'] = 0
				item1['set_combination'] = item.get('item_keys', {})
				items.append(item1)
			row_index += 1
	return items

def fetch_cloth_details(items):
	item_details = []
	for item in items:
		variant = item.cloth_item_variant
		variant_doc = frappe.get_doc("Item Variant",variant)
		item_details.append({
			"accessory": item.accessory,
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
	ipd_doc = frappe.get_cached_doc("Item Production Detail", cutting_plan_doc.production_detail)
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
		if item.set_combination:
			set_combination = update_if_string_instance(item.set_combination)
			if set_colour:= set_combination.get("major_colour"):
				attr_details['set_colour'] = set_colour

		c = calculate_cloth(ipd_doc, attr_details, item.quantity, cloth_combination, stitching_combination)
		for c1 in c:
			key = (c1["cloth_type"], c1["colour"], c1["dia"])
			cloth_details.setdefault(key, 0)
			cloth_details[key] += c1["quantity"]

			if c1["type"] == "accessory":
				key = (c1["cloth_type"], c1["colour"], c1["dia"], c1['accessory_name'])
				accessory_detail.setdefault(key,0)
				accessory_detail[key] += c1["quantity"]

	required_cloth_details = []
	for k in cloth_details:
		attributes = {ipd_doc.packing_attribute: k[1], 'Dia': k[2]}
		item_name = cloth_detail[k[0]]
		cloth_name = get_or_create_variant(item_name, attributes)
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
		attributes = {ipd_doc.packing_attribute: k[1], 'Dia': k[2]}
		item_name = cloth_detail[k[0]]
		cloth_name = get_or_create_variant(item_name, attributes)
		required_accessory_details.append({
			"accessory": k[3],
			"cloth_item_variant": cloth_name,
			"cloth_type": k[0],
			"colour": k[1],
			'dia': k[2],
			"required_weight": accessory_detail[k],
			"weight":0.0
		})	
	cutting_plan_doc.set("cutting_plan_accessory_details", required_accessory_details)
	cutting_plan_doc.set("cutting_plan_cloth_details", required_cloth_details)
	text = f"Cloth Generated on {datetime.now()} by {frappe.session.user}"
	cutting_plan_doc.add_comment('Comment',text=text)
	cutting_plan_doc.save()

def item_attribute_details(variant, item_attributes):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute != item_attributes['dependent_attribute']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

@frappe.whitelist()
def calculate_laysheets(cutting_plan):
	# calc(cutting_plan)
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

	cls_list = frappe.get_list("Cutting LaySheet",filters = {"cutting_plan":cutting_plan,"status":"Label Printed"},pluck = "name")
	for cls in cls_list:
		update_cutting_plan(cls)

@frappe.whitelist()
def get_cutting_plan_laysheets_report(cutting_plan):
	cp_doc = frappe.get_doc("Cutting Plan", cutting_plan)
	ipd_doc = frappe.get_cached_doc("Item Production Detail", cp_doc.production_detail)
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	sizes = get_ipd_primary_values(cp_doc.production_detail)
	panels = []
	if ipd_doc.is_set_item:
		panels = {}
		for row in ipd_doc.stiching_item_details:
			panels.setdefault(row.set_item_attribute_value, [])

	cls_list = frappe.get_list("Cutting LaySheet", filters={"cutting_plan":cutting_plan,"status":"Label Printed"}, pluck="name", order_by="lay_no asc")	
	lay_details = {}
	for cls in cls_list:
		cls_doc = frappe.get_doc("Cutting LaySheet",cls)
		lay_no = cls_doc.lay_no
		lay_details[lay_no] = {}
		for row in cls_doc.cutting_laysheet_bundles:
			parts = row.part.split(",")
			parts = ", ".join(parts)
			set_combination = update_if_string_instance(row.set_combination)
			major_colour = set_combination['major_colour']
			if ipd_doc.is_set_item:
				if set_combination.get('set_part'):
					if parts not in panels[set_combination['set_part']]:
						panels[set_combination['set_part']].append(parts)
					major_colour = "("+ major_colour +")" + set_combination["set_colour"] +"-"+set_combination.get('set_part')
				else:
					if parts not in panels[set_combination['major_part']]:
						panels[set_combination['major_part']].append(parts)
					major_colour = major_colour +"-"+set_combination.get('major_part')
			else:
				if parts not in panels:
					panels.append(parts)

			lay_details[lay_no].setdefault(major_colour, {})
			lay_details[lay_no][major_colour].setdefault(row.size, {})	
			lay_details[lay_no][major_colour][row.size].setdefault(row.shade, {})
			lay_details[lay_no][major_colour][row.size][row.shade].setdefault(parts, {})
			lay_details[lay_no][major_colour][row.size][row.shade][parts].setdefault("qty", 0)
			lay_details[lay_no][major_colour][row.size][row.shade][parts]["qty"] += row.quantity
			lay_details[lay_no][major_colour][row.size][row.shade][parts].setdefault("bundles", 0)
			lay_details[lay_no][major_colour][row.size][row.shade][parts]['bundles'] += 1
	final_data = {}
	for size in sizes:
		for lay_number, colour_dict in lay_details.items():
			if not lay_details.get(lay_number):
				continue
			for colour, colour_detail in colour_dict.items():
				for cur_size, panel_detail in lay_details.get(lay_number).get(colour).items():
					if cur_size == size:
						final_data.setdefault(colour, [])
						for shade in panel_detail:
							duplicate = {}
							duplicate['lay_no'] = lay_number
							duplicate['size'] = size
							duplicate['shade'] = shade
							for panel, panel_details in panel_detail[shade].items():
								duplicate[panel] = panel_details['qty']
								duplicate[panel+"_Bundle"] = panel_details['bundles']
							final_data[colour].append(duplicate)	
	return panels, final_data, ipd_doc.is_set_item

@frappe.whitelist()
def get_ccr(doc_name):
	cp_doc = frappe.get_doc("Cutting Plan", doc_name)
	cls_list = frappe.get_all("Cutting LaySheet", filters={"cutting_plan": doc_name, "status": "Label Printed"}, pluck="name", order_by="lay_no asc")
	markers = {}
	keys = []
	for cls in cls_list:
		cls_doc = frappe.get_doc("Cutting LaySheet", cls)
		sizes = {}
		for row in cls_doc.cutting_marker_ratios:
			if row.size not in sizes:
				sizes[row.size] = row.ratio
		panels = cls_doc.calculated_parts.split(",")
		panels.sort()
		for idx, panel in enumerate(panels):
			panels[idx] = panel.strip()

		tup_panels = ", ".join(panels)
		markers.setdefault(tup_panels, {})
		cloth_type = {}
		for row in cls_doc.cutting_laysheet_details:
			key = (row.colour, row.cloth_type)
			cloth_type.setdefault(row.colour, row.cloth_type)
			markers[tup_panels].setdefault(key, {
				"used_weight": 0,
				"received_weight": 0,
				"balance_weight": 0,
				"total_pieces": 0,
				"reqd_weight": 0,
			})
			if key not in keys:
				keys.append(key)
				markers[tup_panels][key]['reqd_weight'] += cls_doc.required_pcs_weight

			markers[tup_panels][key]["used_weight"] += row.used_weight
			for size in sizes:
				markers[tup_panels][key].setdefault(size, { "bits": 0 })
				bits = sizes[size] * row.effective_bits
				markers[tup_panels][key][size]["bits"] += bits
				markers[tup_panels][key]["total_pieces"] += bits

		if cp_doc.is_manual_entry:
			for row in cls_doc.cutting_laysheet_bundles:
				key = (row.colour, cloth_type[row.colour])
				markers[tup_panels][key][row.size]["bits"] += row.quantity
				markers[tup_panels][key]["total_pieces"] += row.quantity
		sizes = {}

	cp_doc_colours = {}
	for row in cp_doc.cutting_plan_cloth_details:
		key = (row.colour, row.cloth_type)
		cp_doc_colours.setdefault(key, { "received_weight": 0 })
		cp_doc_colours[key]["received_weight"] += row.weight

	for key in cp_doc_colours:
		colour_count = 0
		final_index = 0
		final_mark = None
		for idx, mark in enumerate(markers):
			if markers[mark].get(key):
				colour_count += 1
				final_index = idx
				final_mark = mark
		
		if colour_count == 1:
			markers[final_mark][key]['received_weight'] = cp_doc_colours[key]['received_weight']
			markers[final_mark][key]['balance_weight'] = cp_doc_colours[key]['received_weight'] - markers[final_mark][key]['used_weight']
		elif colour_count > 1:
			for idx, mark in enumerate(markers):
				if markers[mark].get(key):
					if idx == final_index:
						markers[final_mark][key]['received_weight'] = cp_doc_colours[key]['received_weight']
						markers[final_mark][key]['balance_weight'] = cp_doc_colours[key]['received_weight'] - markers[final_mark][key]['used_weight']
					else:
						markers[mark][key]['received_weight'] = markers[mark][key]['used_weight']
						markers[mark][key]['balance_weight'] = 0
						cp_doc_colours[key]['received_weight'] -= markers[mark][key]['used_weight']
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	sizes = get_ipd_primary_values(cp_doc.production_detail)
	if markers:
		return {
			"marker_data": markers,
			"sizes": sizes,
		}					

@frappe.whitelist()
def remove_empty_rows(cutting_json, json_type):
	cutting_json = update_if_string_instance(cutting_json)
	output_json = cutting_json.copy()
	output_json['items'] = []
	for row in cutting_json['items']:
		check = False
		for val in row['values']:
			if json_type == "completed":
				if row['values'][val]:
					check = True
					break
			else:
				for panel in row['values'][val]:
					if row['values'][val][panel]:
						check = True
						break
			if check:
				break		
		if check:	
			output_json['items'].append(row)

	if len(output_json['items']) > 0:
		return [output_json]
	return None

@frappe.whitelist(allow_guest=True)
def get_cutting_plan_size_reports(cutting_plan):
	cp_doc = frappe.get_doc("Cutting Plan", cutting_plan)
	ipd_doc = frappe.get_cached_doc("Item Production Detail", cp_doc.production_detail)
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	sizes = get_ipd_primary_values(cp_doc.production_detail)
	panels = []
	if ipd_doc.is_set_item:
		panels = {}
		for row in ipd_doc.stiching_item_details:
			panels.setdefault(row.set_item_attribute_value, [])

	cls_list = frappe.get_list("Cutting LaySheet", filters={"cutting_plan":cutting_plan,"status":"Label Printed"}, pluck="name", order_by="lay_no asc")	
	size_details = {}
	for cls in cls_list:
		cls_doc = frappe.get_doc("Cutting LaySheet",cls)
		for row in cls_doc.cutting_laysheet_bundles:
			parts = row.part.split(",")
			parts = ", ".join(parts)
			set_combination = update_if_string_instance(row.set_combination)
			major_colour = set_combination['major_colour']
			if ipd_doc.is_set_item:
				if set_combination.get('set_part'):
					if parts not in panels[set_combination['set_part']]:
						panels[set_combination['set_part']].append(parts)
					major_colour = "("+ major_colour +")" + set_combination["set_colour"] +"-"+set_combination.get('set_part')
				else:
					if parts not in panels[set_combination['major_part']]:
						panels[set_combination['major_part']].append(parts)
					major_colour = major_colour +"-"+set_combination.get('major_part')
			else:
				if parts not in panels:
					panels.append(parts)
			size_details.setdefault(major_colour, {})
			size_details[major_colour].setdefault(row.size, {})	
			size_details[major_colour][row.size].setdefault(parts, {})
			size_details[major_colour][row.size][parts].setdefault("qty", 0)
			size_details[major_colour][row.size][parts]["qty"] += row.quantity
			size_details[major_colour][row.size][parts].setdefault("bundles", 0)
			size_details[major_colour][row.size][parts]['bundles'] += 1

	final_data = {}
	for size in sizes:
		for colour, colour_details in size_details.items():
			for dict_size, panel_detail in colour_details.items():
				if dict_size == size:
					final_data.setdefault(colour, [])
					duplicate = {}
					duplicate['size'] = size
					for panel in panel_detail:
						duplicate[panel] = panel_detail[panel]['qty']
						duplicate[panel+"_Bundle"] = panel_detail[panel]['bundles']
					final_data[colour].append(duplicate)
	return panels, final_data, ipd_doc.is_set_item

@frappe.whitelist()
def fetch_received_cloth(docname):
	cp_doc = frappe.get_doc("Cutting Plan", docname)
	dc_list = frappe.get_all("Delivery Challan", filters={
		"docstatus": 1,
		"work_order": cp_doc.work_order
	}, pluck="name")

	for item in cp_doc.cutting_plan_cloth_details:
		item.weight = 0

	for dc in dc_list:
		internal, _from, _to = frappe.get_value("Delivery Challan", dc, ["is_internal_unit", "from_address", "supplier_address"])
		if internal and _from != _to:
			se_list = frappe.get_all("Stock Entry", filters={
				"purpose": "DC Completion",
				"against": "Delivery Challan",
				"docstatus": 1,
				"against_id": dc
			}, pluck="name")
			for se in se_list:
				se_doc = frappe.get_doc("Stock Entry", se)
				for ste_item in se_doc.items:
					for item in cp_doc.cutting_plan_cloth_details:
						if item.cloth_item_variant == ste_item.item:	
							item.weight += ste_item.qty
							break
		else:
			dc_doc = frappe.get_doc("Delivery Challan", dc)
			for dc_item in dc_doc.items:
				for item in cp_doc.cutting_plan_cloth_details:
					if item.cloth_item_variant == dc_item.item_variant:	
						item.weight += dc_item.delivered_quantity
						break
	for item in cp_doc.cutting_plan_cloth_details:
		item.balance_weight = round(item.weight - item.used_weight, 3)

	cp_doc.save()
