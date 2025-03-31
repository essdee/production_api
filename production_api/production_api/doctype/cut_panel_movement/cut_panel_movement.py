# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe, json
from six import string_types
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_or_create_variant
from production_api.mrp_stock.doctype.stock_entry.stock_entry import fetch_stock_entry_items
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details

class CutPanelMovement(Document):
	def onload(self):
		if self.cut_panel_movement_json and len(self.cut_panel_movement_json) > 0:
			json_data = self.cut_panel_movement_json
			if isinstance(json_data, string_types):
				json_data = json.loads(json_data)
			self.set_onload("movement_details", json_data)

	def before_validate(self):
		if self.docstatus == 1:
			return

		if self.is_new():
			res = frappe.db.sql(
				f"""
					SELECT name FROM `tabCut Panel Movement` WHERE cutting_plan = '{self.cutting_plan}' AND docstatus = 0
				""", as_dict=True
			)
			if len(res) > 0:
				frappe.throw(f"Already a Cut Panel Movement was not Submitted for Cutting Plan {self.cutting_plan}")
		
		if self.get('movement_data'):
			items = self.movement_data
			if isinstance(items, string_types):
				items = json.loads(items)
			if items['accessory_data']:
				for item in items['accessory_data']:
					if not item['moved_weight']:
						item['moved_weight'] = 0
					if item['weight'] < item['moved_weight']:
						frappe.throw("Accessory Moving Weight Greater than Used Weight")
			items = get_total(items)
			self.set("cut_panel_movement_json", items)
	
	def before_submit(self):
		datas = {}
		json_data = self.cut_panel_movement_json
		if isinstance(json_data, string_types):
			json_data = json.loads(json_data)
		panels = json_data['panels']
		is_set_item = json_data['is_set_item']
		data = json_data['data']
		for colour in data:
			datas[colour] = {"part":data[colour]['part'], 'data':[]}
			for row in data[colour]['data']:
				if row['bundle_moved']:
					datas[colour]['data'].append(row)
				else:
					if is_set_item:
						part = data[colour]['part']
						for panel in panels[part]:
							x = panel+"_moved"
							if x in row and row[x] == True:
								datas[colour]['data'].append(row)
								break
					else:
						for panel in panels:
							x = panel+"_moved"
							if x in row and row[x] == True:
								datas[colour]['data'].append(row)
								break
		json_data['data'] = datas
		accessory = json_data['accessory_data']
		if accessory:
			accessories = []
			for acc in accessory:
				if acc['moved_weight'] > 0:
					accessories.append(acc)
			json_data['accessory_data'] = accessories		

		self.set("cut_panel_movement_json", json_data)
	
	def on_cancel(self):
		update_cls(self.cut_panel_movement_json, self.docstatus, self.cutting_plan, self.process_name)
		update_accessory(self.cutting_plan, self.cut_panel_movement_json, self.docstatus, self.process_name)

	def on_submit(self):
		if check_panel_and_accessories(self.cut_panel_movement_json):
			update_cls(self.cut_panel_movement_json, self.docstatus, self.cutting_plan, self.process_name)
			update_accessory(self.cutting_plan, self.cut_panel_movement_json, self.docstatus, self.process_name)
		else:
			frappe.throw("No Panels and Accessories are moved")

def get_total(items):
	colour_panel = {}
	total_bundle = {}
	for colour in items["data"].keys():
		colour_panel[colour] = {}
		total_bundle[colour] = 0
		if items["is_set_item"]:
			pt = items["data"][colour]["part"]
			for i in range(len(items["data"][colour]["data"])):
				item = items["data"][colour]["data"][i]
				qty = 0

				for panel in items["panels"][pt]:
					if panel not in colour_panel[colour]:
						colour_panel[colour][panel] = 0
					
					if panel in item:
						if item.get(f"{panel}_moved"):
							qty += 1
							colour_panel[colour][panel] += item[panel]
				item["total"] = qty
				total_bundle[colour] += qty
				items["data"][colour]["data"][i] = item
		else:
			for i in range(len(items["data"][colour]["data"])):
				item = items["data"][colour]["data"][i]
				qty = 0

				for panel in items["panels"]:
					if panel not in colour_panel[colour]:
						colour_panel[colour][panel] = 0

					if panel in item:
						if item.get(f"{panel}_moved"):
							qty += 1
							colour_panel[colour][panel] += item[panel]
				item["total"] = qty
				total_bundle[colour] += qty
				items["data"][colour]["data"][i] = item
		items["total_pieces"] = colour_panel
		items['total_bundles'] = total_bundle
	return items

def check_panel_and_accessories(cut_panel_movement_json):
	json_data = cut_panel_movement_json
	if isinstance(json_data, string_types):
		json_data = json.loads(json_data)
	panels = json_data['panels']
	is_set_item = json_data['is_set_item']
	data = json_data['data']

	for colour in data:
		for row in data[colour]['data']:
			if is_set_item:
				part = data[colour]['part']
				for panel in panels[part]:
					x = panel+"_moved"
					if x in row and row[x] == True:
						return True
			else:
				for panel in panels:
					x = panel+"_moved"
					if x in row and row[x] == True:
						return True
					
	accessory_data = cut_panel_movement_json['accessory_data']
	for row in accessory_data:
		if row['moved_weight'] > 0:
			return True
		
	return False		
		
def update_cls(cut_panel_movement_json, docstatus, cutting_plan, process_name):
	ipd = frappe.get_value("Cutting Plan", cutting_plan, "production_detail")
	process = frappe.get_value("Item Production Detail", ipd, "cutting_process")
	if process != process_name:
		return
	ref_doclist = set()
	json_data = cut_panel_movement_json
	if isinstance(json_data, string_types):
		json_data = json.loads(json_data)
	panels = json_data['panels']
	is_set_item = json_data['is_set_item']
	data = json_data['data']
	for colour in data:
		for row in data[colour]['data']:
			if is_set_item:
				part = data[colour]['part']
				for panel in panels[part]:
					x = panel+"_moved"
					if x in row and row[x] == True:
						ref_doclist.add(row[panel+'_ref_docname'])
			else:
				for panel in panels:
					x = panel+"_moved"
					if x in row and row[x] == True:
						ref_doclist.add(row[panel+'_ref_docname'])

	ref_doclist = tuple(ref_doclist)
	moved = 1
	if docstatus == 2:
		moved = 0
	
	if len(ref_doclist) > 0:
		frappe.db.sql(
			f"""
				Update `tabCutting LaySheet Bundle` SET is_moved = {moved} WHERE name IN {(ref_doclist)}
			"""
		)

def update_accessory(cutting_plan, cut_panel_movement_json, docstatus, process_name):
	ipd = frappe.get_value("Cutting Plan", cutting_plan, "production_detail")
	process = frappe.get_value("Item Production Detail", ipd, "cutting_process")
	if process != process_name:
		return
	
	if isinstance(cut_panel_movement_json, string_types):
		cut_panel_movement_json = json.loads(cut_panel_movement_json)
	
	if cut_panel_movement_json and cut_panel_movement_json['accessory_data']:
		accessory_data = cut_panel_movement_json['accessory_data']
		order = "ASC"
		if docstatus == 2:
			order = "DESC"

		cls_list = frappe.db.sql(
			f"""
				SELECT name FROM `tabCutting LaySheet` WHERE cutting_plan = '{cutting_plan}' ORDER BY lay_no {order}
			""", as_list = True
		)

		accessory = {}
		for row in accessory_data:
			key = (row['cloth_type'], row['colour'], row['shade'], row['dia'])
			accessory[key] = row['moved_weight']	
		
		for cls in cls_list:
			cls_doc = frappe.get_doc("Cutting LaySheet", cls)
			check = False
			for row in cls_doc.cutting_laysheet_accessory_details:
				key = (row.cloth_type, row.colour, row.shade, row.dia)
				if docstatus == 1:
					if key in accessory and row.moved_weight != row.weight and accessory[key] > 0:
						moved_weight = accessory[key]
						check = True
						balance_weight = row.weight - row.moved_weight
						if balance_weight >= moved_weight:
							row.moved_weight += moved_weight
							accessory[key] -= moved_weight
						else:
							row.moved_weight += balance_weight
							accessory[key] -= balance_weight
				else:
					if key in accessory and accessory[key] > 0 and row.moved_weight > 0:
						moved_weight = accessory[key]
						check = True
						if row.moved_weight >= moved_weight:
							row.moved_weight -= moved_weight
							accessory[key] -= moved_weight
						else:
							accessory[key] -= row.moved_weight
							row.moved_weight = 0
			if check:
				cls_doc.save()

@frappe.whitelist()
def get_cutting_plan_unmoved_data(cutting_plan, process_name):
	cp_doc = frappe.get_doc("Cutting Plan", cutting_plan)
	if cp_doc.version == "V1":
		frappe.throw("Can't create Cutting Movement for Version V1 Cutting Plan's")

	ipd_doc = frappe.get_cached_doc("Item Production Detail", cp_doc.production_detail)
	is_moved = True
	if ipd_doc.cutting_process == process_name:
		is_moved = False

	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	sizes = get_ipd_primary_values(cp_doc.production_detail)
	panels = []
	if ipd_doc.is_set_item:
		panels = {}
		for row in ipd_doc.stiching_item_details:
			panels.setdefault(row.set_item_attribute_value, [])
	cls_list = frappe.get_list("Cutting LaySheet", filters={"cutting_plan":cutting_plan,"status":"Label Printed"}, pluck="name", order_by="lay_no asc")	
	lay_details = {}
	accessory_details = []
	accessories = {}

	for cls in cls_list:
		cls_doc = frappe.get_doc("Cutting LaySheet",cls)
		lay_no = cls_doc.lay_no
		lay_details[lay_no] = {}
		for row in cls_doc.cutting_laysheet_bundles:
			if not row.is_moved or is_moved:
				bundle_no = row.bundle_no
				parts = row.part.split(",")
				parts = ", ".join(parts)
				set_combination = row.set_combination
				if isinstance(set_combination, string_types):
					set_combination = json.loads(set_combination)
				major_colour = set_combination['major_colour']
				panel_colour = row.colour
				if ipd_doc.is_set_item:
					if set_combination.get('set_part'):
						if set_combination.get('is_same_packing_attribute'):
							if parts not in panels[set_combination['set_part']]:
								panels[set_combination['set_part']].append(parts)
							major_colour = major_colour +"-"+set_combination.get('set_part')
						else:
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
				lay_details[lay_no][major_colour].setdefault(bundle_no, {})
				lay_details[lay_no][major_colour][bundle_no].setdefault(row.size, {})	
				lay_details[lay_no][major_colour][bundle_no][row.size].setdefault(row.shade, {})
				lay_details[lay_no][major_colour][bundle_no][row.size][row.shade].setdefault(parts, {
					"qty":0,
					"ref_docname": None,
					"colour": panel_colour,
				})
				lay_details[lay_no][major_colour][bundle_no][row.size][row.shade][parts]["qty"] += row.quantity
				lay_details[lay_no][major_colour][bundle_no][row.size][row.shade][parts]["ref_docname"] = row.name
		
		for row in cls_doc.cutting_laysheet_accessory_details:
			if is_moved:
				key = (row.cloth_item, row.cloth_type, row.colour, row.dia, row.shade)
				if key in accessories:
					accessories[key] += row.weight
				else:
					accessories[key] = row.weight
			else:
				weight = row.weight - row.moved_weight
				if weight > 0:
					key = (row.cloth_item, row.cloth_type, row.colour, row.dia, row.shade)
					if key in accessories:
						accessories[key] += weight
					else:
						accessories[key] = weight

	for key, weight in accessories.items():
		cloth_item, cloth_type, colour, dia, shade = key
		accessory_details.append({
			"cloth_name":cloth_item,
			"cloth_type":cloth_type,
			"colour":colour,
			"shade":shade,
			"dia":dia,
			"weight": weight,
			"moved_weight": 0,
		}) 			
	
	doc_names = set()
	final_data = {}
	for size in sizes:
		for lay_number, colour_dict in lay_details.items():
			if not lay_details.get(lay_number):
				continue
			for colour, colour_detail in colour_dict.items():
				for bundle_no in lay_details.get(lay_number).get(colour):
					for cur_size, panel_detail in lay_details.get(lay_number).get(colour).get(bundle_no).items():
						if cur_size == size:
							shade = list(panel_detail.keys())[0]
							d = {
								"part":None,
								"data":[]
							}
							if ipd_doc.is_set_item:
								splits = colour.split("-")
								d['part'] = splits[len(splits) - 1]

							final_data.setdefault(colour, d)
							duplicate = {}
							duplicate['lay_no'] = lay_number
							duplicate['size'] = size
							duplicate['shade'] = shade
							duplicate['bundle_no'] = bundle_no
							for panel, details in panel_detail[shade].items():
								doc_names.add(details['ref_docname'])
								duplicate[panel] = details['qty']
								duplicate[panel+"_colour"] = details["colour"]
								duplicate[panel+"_moved"] = False
								duplicate[panel+'_ref_docname'] = details['ref_docname']
							duplicate['bundle_moved'] = False	
							final_data[colour]["data"].append(duplicate)	
	from operator import itemgetter
	for colour in final_data:
		data = final_data[colour]["data"]
		final_data[colour]["data"] = sorted(data, key=itemgetter('size', 'shade'))
		
	return {
		"panels":panels,
		"data": final_data,
		"accessory_data": accessory_details,
		"is_set_item":ipd_doc.is_set_item
	}

@frappe.whitelist()
def create_stock_entry(doc_name):
	cpm_doc = frappe.get_doc("Cut Panel Movement", doc_name)
	ipd = frappe.get_value("Cutting Plan", cpm_doc.cutting_plan, "production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	cpm_json = cpm_doc.cut_panel_movement_json
	stock_entry_dict = {}
	group_dict = {}
	attr_details = get_dependent_attribute_details(ipd_doc.dependent_attribute_mapping)
	uom = attr_details['attr_list'][ipd_doc.stiching_in_stage]['uom']
	if isinstance(cpm_json, string_types):
		cpm_json = json.loads(cpm_json)

	for colour in cpm_json['data']:
		if ipd_doc.is_set_item:
			part = cpm_json['data'][colour]['part']
			panels = cpm_json['panels'][part]
		else:
			panels = cpm_json['panels']

		for data in cpm_json['data'][colour]['data']:
			for grp_panel in panels:
				if data.get(grp_panel) and data[grp_panel+"_moved"]:
					panel_list = grp_panel.split(",")
					for panel in panel_list:	
						grp_key = (panel, colour)
						if grp_key not in group_dict:
							group_dict[grp_key] = []
						key = {
							ipd_doc.primary_item_attribute: data['size'],
							ipd_doc.packing_attribute: data[panel+'_colour'],
							ipd_doc.dependent_attribute: ipd_doc.stiching_in_stage,
							ipd_doc.stiching_attribute: panel,
						}
						key = tuple(sorted(key.items()))
						if key in stock_entry_dict:
							stock_entry_dict[key]["qty"] += data[panel]
						else:
							stock_entry_dict[key] = { "qty": data[panel], "group_key": grp_key }
	for attrs_tuple in stock_entry_dict:
		attrs = get_tuple_attributes(attrs_tuple)
		qty = stock_entry_dict[attrs_tuple]['qty']
		grp_key = stock_entry_dict[attrs_tuple]['group_key']
		variant = get_or_create_variant(cpm_doc.item, attrs)
		group_dict[grp_key].append( { "item_variant": variant, "qty": qty })

	table_index = -1
	row_index = -1
	stock_entry_item_list = []
	lot = cpm_doc.lot
	received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	for (panel, colour), items in group_dict.items():
		sorted_items = sorted(items, key=lambda x: x['item_variant'])
		table_index += 1
		row_index += 1
		for item in sorted_items:
			stock_entry_item_list.append({
                "item": item['item_variant'],
                "qty": item['qty'],
                "lot": lot,
                "received_type": received_type,
                "uom": uom,
				'table_index': table_index,
				'row_index': row_index,
            })
	table_index += 1
	row_index += 1
	for acc in cpm_json['accessory_data']:
		variant = get_or_create_variant(acc['cloth_name'], { ipd_doc.packing_attribute: acc['colour'], "Dia": acc['dia'] })
		uom = frappe.get_value("Item", acc['cloth_name'], "default_unit_of_measure")
		stock_entry_item_list.append({
			"item": variant,
			"qty": acc['moved_weight'],
			"lot": lot,
			"received_type": received_type,
			"uom": uom,
			'table_index': table_index,
			'row_index': row_index,
		})
		row_index += 1
	data = fetch_stock_entry_items(stock_entry_item_list)
	return data

def get_tuple_attributes(tuple_data):
	attrs = {}
	for data in tuple_data:
		attrs[data[0]] = data[1]
	return attrs	

