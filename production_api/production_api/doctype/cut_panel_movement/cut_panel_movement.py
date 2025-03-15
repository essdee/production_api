# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe, json
from six import string_types
from frappe.model.document import Document

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
			datas[colour] = []
			for row in data[colour]:
				if row['bundle_moved']:
					datas[colour].append(row)
				else:
					if is_set_item:
						splits = colour.split("-")
						part = splits[len(splits) - 1]
						for panel in panels[part]:
							x = panel+"_moved"
							if x in row and row[x] == True:
								datas[colour].append(row)
								break
					else:
						for panel in panels:
							x = panel+"_moved"
							if x in row and row[x] == True:
								datas[colour].append(row)
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
		update_cls(self.cut_panel_movement_json, self.docstatus)
		update_accessory(self.cutting_plan, self.cut_panel_movement_json, self.docstatus)

	def on_submit(self):
		if check_panel_and_accessories(self.cut_panel_movement_json):
			update_cls(self.cut_panel_movement_json, self.docstatus)
			update_accessory(self.cutting_plan, self.cut_panel_movement_json, self.docstatus)
		else:
			frappe.throw("No Panels and Accessories are moved")

def get_total(items):
	colour_panel = {}
	total_bundle = {}
	for colour in items["data"].keys():
		colour_panel[colour] = {}
		total_bundle[colour] = 0
		if items["is_set_item"]:
			splits = colour.split("-")
			pt = splits[len(splits) - 1]
			for i in range(len(items["data"][colour])):
				item = items["data"][colour][i]
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
				items["data"][colour][i] = item
		else:
			for i in range(len(items["data"][colour])):
				item = items["data"][colour][i]
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
				items["data"][colour][i] = item
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
		for row in data[colour]:
			if is_set_item:
				splits = colour.split("-")
				part = splits[len(splits) - 1]
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
		
def update_cls(cut_panel_movement_json, docstatus):
	ref_doclist = set()
	json_data = cut_panel_movement_json
	if isinstance(json_data, string_types):
		json_data = json.loads(json_data)
	panels = json_data['panels']
	is_set_item = json_data['is_set_item']
	data = json_data['data']

	for colour in data:
		for row in data[colour]:
			if is_set_item:
				splits = colour.split("-")
				part = splits[len(splits) - 1]
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

def update_accessory(cutting_plan, cut_panel_movement_json, docstatus):
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
def get_cutting_plan_unmoved_data(cutting_plan):
	cp_doc = frappe.get_doc("Cutting Plan", cutting_plan)
	if cp_doc.version == "V1":
		frappe.throw("Can't create Cutting Movement for Version V1 Cutting Plan's")

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
	accessory_details = []
	accessories = {}

	for cls in cls_list:
		cls_doc = frappe.get_doc("Cutting LaySheet",cls)
		lay_no = cls_doc.lay_no
		lay_details[lay_no] = {}
		for row in cls_doc.cutting_laysheet_bundles:
			if not row.is_moved:
				bundle_no = row.bundle_no
				parts = row.part.split(",")
				parts = ", ".join(parts)
				set_combination = row.set_combination
				if isinstance(set_combination, string_types):
					set_combination = json.loads(set_combination)
				major_colour = set_combination['major_colour']
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
				})
				lay_details[lay_no][major_colour][bundle_no][row.size][row.shade][parts]["qty"] += row.quantity
				lay_details[lay_no][major_colour][bundle_no][row.size][row.shade][parts]["ref_docname"] = row.name
		
		for row in cls_doc.cutting_laysheet_accessory_details:
			if row.weight - row.moved_weight > 0:
				key = (row.cloth_type, row.colour, row.dia, row.shade)
				if key in accessories:
					accessories[key] += row.weight - row.moved_weight
				else:
					accessories[key] = row.weight - row.moved_weight

	for key, weight in accessories.items():
		cloth_type, colour, dia, shade = key
		accessory_details.append({
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
							final_data.setdefault(colour, [])
							duplicate = {}
							duplicate['lay_no'] = lay_number
							duplicate['size'] = size
							duplicate['shade'] = shade
							duplicate['bundle_no'] = bundle_no
							for panel, details in panel_detail[shade].items():
								doc_names.add(details['ref_docname'])
								duplicate[panel] = details['qty']
								duplicate[panel+"_moved"] = False
								duplicate[panel+'_ref_docname'] = details['ref_docname']
							duplicate['bundle_moved'] = False	
							final_data[colour].append(duplicate)	
	from operator import itemgetter
	for colour in final_data:
		data = final_data[colour]
		final_data[colour] = sorted(data, key=itemgetter('lay_no', 'bundle_no'))
		
	return {
		"panels":panels,
		"data": final_data,
		"accessory_data": accessory_details,
		"is_set_item":ipd_doc.is_set_item
	}
