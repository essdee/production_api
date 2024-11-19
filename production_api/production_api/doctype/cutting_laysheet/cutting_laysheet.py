# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import math
import frappe,json
from itertools import groupby
from six import string_types
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_or_create_variant
from frappe.utils import getdate
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_stitching_combination
from itertools import zip_longest
import sys

class CuttingLaySheet(Document):
	def autoname(self):
		self.naming_series = "CLS-.YY..MM.-.{#####}."

	def onload(self):
		self.set_onload("item_details",self.cutting_laysheet_details)

	def before_validate(self):
		if self.get('item_details'):
			items = save_item_details(self.item_details, self.cutting_plan)
			self.set("cutting_laysheet_details", items)

		status = frappe.get_value("Cutting Plan",self.cutting_plan,"status")	
		if status == "Completed":
			frappe.throw("Select the Incompleted Cutting Plan")

		cut_marker_cp = frappe.get_value("Cutting Marker",self.cutting_marker,"cutting_plan")		
		if cut_marker_cp != self.cutting_plan:
			frappe.throw(f"Select the Cutting Marker which is against {self.cutting_plan}")

		if self.is_new():
			cut_plan_doc = frappe.get_doc("Cutting Plan",self.cutting_plan)	
			cut_marker_doc = frappe.get_doc("Cutting Marker",self.cutting_marker)		

			self.lay_no = cut_plan_doc.lay_no + 1
			self.maximum_no_of_plys = cut_plan_doc.maximum_no_of_plys
			self.maximum_allow_percentage = cut_plan_doc.maximum_allow_percent
			cut_plan_doc.lay_no = self.lay_no
			cut_plan_doc.flags.ignore_permissions = 1
			cut_plan_doc.save()
			
			marker_list = []
			for item in cut_marker_doc.cutting_marker_ratios:
				marker_list.append({'size':item.size,'ratio':item.ratio})

			self.set("cutting_marker_ratios",marker_list)		
		colours = set()
		no_of_bits = 0.0
		weight = 0.0
		end_bit_weight = 0.0
		accessory_weight = 0.0
		no_of_rolls = 0
		used_weight = 0.0
		for item in self.cutting_laysheet_details:
			no_of_bits += item.no_of_bits
			weight += item.weight
			end_bit_weight += item.end_bit_weight
			accessory_weight += item.accessory_weight
			no_of_rolls += item.no_of_rolls
			used_weight += item.used_weight
			colours.add(item.colour)

		if weight and self.status == 'Started':
			self.status = "Completed"

		items = []
		for colour in colours:
			for item in self.cutting_laysheet_details:
				if item.colour == colour:
					items.append(item)
		self.no_of_rolls = no_of_rolls
		self.no_of_bits = no_of_bits
		self.weight = weight
		self.end_bit_weight = end_bit_weight
		self.accessory_weight = accessory_weight
		self.total_used_weight = used_weight
		if self.total_no_of_pieces:
			self.piece_weight = used_weight / self.total_no_of_pieces
		self.set("cutting_laysheet_details",items)			

def save_item_details(items, cutting_plan):
	if isinstance(items, string_types):
		items = json.loads(items)
	ipd = frappe.get_value("Cutting Plan",cutting_plan,"production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail",ipd)
	item_list = []
	for item in items:
		attributes = {}
		attributes[ipd_doc.packing_attribute] = item['colour']
		attributes['Dia'] = item['dia']
		cloth_name = None
		for cloth in ipd_doc.cloth_detail:
			if cloth.name1 == item['cloth_type']:
				cloth_name = cloth.cloth
				break
		variant = get_or_create_variant(cloth_name, attributes)
		item_list.append({
			"cloth_item_variant":variant,
			"cloth_type":item['cloth_type'],
			"colour":item['colour'],
			"dia":item['dia'],
			"shade":item['shade'],
			"weight":item['weight'],
			"no_of_rolls":item['no_of_rolls'],
			"no_of_bits":item['no_of_bits'],
			"end_bit_weight":item['end_bit_weight'],
			"comments":item['comments'],
			"used_weight":item['used_weight'],
			"balance_weight":item['balance_weight'],
			"accessory_json":item['accessory_json'],
			"accessory_weight":item['accessory_weight']
		})	
	return item_list	

@frappe.whitelist()
def get_select_attributes(cutting_plan):
	doc = frappe.get_doc("Cutting Plan",cutting_plan)
	cloth_type = set()
	colour = set()
	dia = set()
	for item in doc.cutting_plan_cloth_details:
		cloth_type.add(item.cloth_type)
		colour.add(item.colour)
		dia.add(item.dia)
	return {
		"cloth_type":cloth_type,
		"colour":colour,
		"dia":dia,
	}	

@frappe.whitelist()
def get_parts(cutting_marker):
	cm_doc = frappe.get_doc("Cutting Marker",cutting_marker)
	part_list = []
	for item in cm_doc.cutting_marker_parts:
		part_list.append(item.part)
	return part_list	

@frappe.whitelist()
def get_cut_sheet_data(doc_name,cutting_marker,item_details,items, max_plys:int,maximum_allow:int):
	if isinstance(items, string_types):
		items = json.loads(items)
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)	
	maximum_plys = max_plys + (max_plys/100) * maximum_allow
	bundle_no = 0
	cm_doc = frappe.get_doc("Cutting Marker",cutting_marker)
	cut_sheet_data = []
	for item in item_details:
		if item['no_of_bits'] == 0:
			continue
		for cm_item in cm_doc.cutting_marker_ratios:
			no_of_marks = cm_item.ratio
			max_grouping = int(maximum_plys/item['no_of_bits'])
			total_bundles = math.ceil(no_of_marks/max_grouping)
			avg_grouping = no_of_marks/total_bundles

			minimum = math.floor(avg_grouping)
			maximum = math.ceil(avg_grouping)

			maximum_count = no_of_marks - (total_bundles * minimum)
			minimum_count = total_bundles - maximum_count
	
			temp = bundle_no 
			for part_value in items:
				bundle_no = temp	
				for j in range(maximum_count):
					bundle_no = bundle_no + 1
					hash_value = get_timestamp_prefix() + generate_random_string(12)
					qty = maximum * item['no_of_bits']
					cut_sheet_data.append({
						"size":cm_item.size,
						"colour":item['colour'],
						"shade":item['shade'],
						"bundle_no":bundle_no,
						"part":part_value['part'],
						"quantity": qty,
						"hash_value":hash_value
					})	
				for j in range(minimum_count):
					bundle_no = bundle_no + 1
					hash_value = get_timestamp_prefix() + generate_random_string(12)
					qty = minimum * item['no_of_bits']
					cut_sheet_data.append({
						"size":cm_item.size,
						"colour":item['colour'],
						"shade":item['shade'],
						"bundle_no":bundle_no,
						"part":part_value['part'],
						"quantity":qty,
						"hash_value":hash_value
					})		
			temp = bundle_no	
	
	dictionary = {}
	for item in cut_sheet_data:
		if dictionary.get(item['bundle_no']):
			dictionary[item['bundle_no']].append(item)
		else:
			dictionary[item['bundle_no']] = [item]	

	item_dict = {}
	for item in items:
		item_dict[item['part']] = item['value']

	final_list = {}
	for key,values in dictionary.items():
		final_list[key] = []
		group = []
		for value in values:
			part = value['part']
			if item_dict[part] not in group:
				value['group'] = item_dict[part]
				final_list[key].append(value)
			else:
				for j in final_list[key]:
					if j['group'] == item_dict[part]:
						pt = j['part']
						j['part'] =  pt + "," + part
			group.append(item_dict[part])				

	cut_sheet_data = []
	for key, values in final_list.items():
		for val in values:
			val['bundle_no'] = key
			cut_sheet_data.append(val)
	
	doc = frappe.get_doc("Cutting LaySheet", doc_name)
	count = 0
	for item in doc.cutting_marker_ratios:
		count += item.ratio

	total_pieces = count * doc.no_of_bits
	doc.maximum_no_of_plys = max_plys
	doc.maximum_allow_percentage = maximum_allow 
	doc.total_no_of_pieces = total_pieces
	doc.status = "Bundles Generated"
	doc.set("cutting_laysheet_bundles", cut_sheet_data)
	doc.save()

import base64
from secrets import token_bytes as get_random_bytes
import time

def get_timestamp_prefix():
	ts = int(time.time() * 10) 
	ts = ts % (32**4)
	return base64.b32hexencode(ts.to_bytes(length=5, byteorder="big")).decode()[-4:].lower()

def generate_random_string(length=10):
	return base64.b32hexencode(get_random_bytes(length)).decode()[:length].lower()

@frappe.whitelist()
def get_cloth_accessories(cutting_plan):
	ipd = frappe.get_value("Cutting Plan", cutting_plan, "production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	accessory_list = []
	x = ipd_doc.accessory_clothtype_json
	if isinstance(x,string_types):
		x = json.loads(x)
	if x:
		for key,val in x.items():
			accessory_list.append(key)
	return accessory_list	

@frappe.whitelist()
def print_labels(print_items, lay_no, cutting_plan, doc_name):
	lot_no,item_name = frappe.get_value("Cutting Plan",cutting_plan,["lot","item"])
	if isinstance(print_items,string_types):
		print_items = json.loads(print_items)
	zpl = ""
	cls_doc = frappe.get_doc("Cutting LaySheet",doc_name)
	creation = cls_doc.creation
	date = get_created_date(creation)
	for item in print_items:
		x = f"""^XA
			^FO70,30^GFA,2736,2736,38,,:::::::::::::::P0FI0MF803MFC01MFC0NFI0MF803LFEF8,0018001006B001MF807MFC07MFC0NF801MF807LFEB8,001C00300EI03MF80NFC07MFC0NFC03MF80MFE,001E00701EI07MF81NFC0NFC0NFE07MF81MFE,001F00F03EI07MF81NFC0NFC0NFE07MF81MFE,001F01F07EI07MF81NFC1NFC0NFE07MF81MFE,001F83F07EI07MF81NFC1NFC0NFE07MF81MFE,001F83F0FEI07MF81NFC1NFC0NFE07MF81MFE,001FC3F0FEI07MF01NF81NFC0NFE07MF01MFC,001FC3F0FEI07FCL01FFM01FF8M0FF8I07FE07FCL01FF,001FC3F0FEI07FCL01FFM01FF8M0FF8I03FE07FCL01FF,:::001FC3F0FEI07MF81MFE01MFE00FF8I03FE07MF81MFE,001FC3F0FEI07MF81NF01NF80FF8I03FE07MF81MFE,001FC3F0FEI07MF81NF81NF80FF8I03FE07MF81MFE,001FC3F0FEI07MF81NF80NFC0FF8I03FE07MF81MFE,I0FC3F0FCI07MF81NFC0NFC0FF8I03FE07MF81MFE,I07C3F0F8I07MF80NFC0NFC0FF8I03FE07MF81MFE,I03C3F0FJ07MF807MFC07MFC0FF8I03FE07MF81MFE,I01C3F0EJ07MF803MFC01MFC0FF8I03FE07MF81MFE,J0C3F0CJ07FCS0FFCM07FC0FF8I03FE07FCL01FF,J043F08J07FCS0FFCM07FC0FF8I03FE07FCL01FF,K03FL07FCS0FFCM07FC0FF8I03FE07FCL01FF,::::::K03FL07FCS0FFCM07FC0FF8I07FE07FCL01FF,K03FL07MF81NFC1NFC0NFE07MF81MFE,:K03EL07MF81NFC1NFC0NFE07MF81MFE,K03CL07MF81NFC1NFC0NFE07MF81MFE,K038L07MF81NF81NFC0NFE07MF81MFE,K03M03MF81NF81NFC0NFC03MF80MFE,K02M03MF81NF01NF80NFC01MF80MFE,K02N0MF81MFE01NF00NFI0MF803LFE,,:::::::::::::::^FS
			^PW1000
			^FO720,50^A0,40,40^FD{date}^FS
			^FO108,35^A0,15,15^FDTM^FS
			^FO350,35^A0,15,15^FDTM^FS

			^FO30,15^GB910,435,5^FS
			^FO30,110^GB910,70,5^FS
			^FO30,245^GB910,70,5^FS
			^FO30,380^GB910,70,5^FS
			^FO30,447^GB475,70,5^FS
			^FO500,245^GB2,205,5^FS

			^FO40,130^A0,40,40^FDStyle^FS
			^FO40,195^A0,40,40^FDPanel^FS
			^FO40,267^A0,40,40^FDLay No^FS
			^FO40,335^A0,40,40^FDColour^FS
			^FO40,403^A0,40,40^FDSize^FS
			^FO40,470^A0,40,40^FDLot No^FS
			^FO510,267^A0,40,40^FDBundle No^FS
			^FO510,335^A0,40,40^FDShade^FS
			^FO510,403^A0,40,40^FDQty^FS

			^FO150,130^A0,40,40^FD: {item_name}^FS
			^FO150,195^A0,40,40^FD: {item['part']}^FS
			^FO150,267^A0,40,40^FD: {lay_no}^FS
			^FO150,335^A0,40,40^FD: {item['colour']}^FS
			^FO150,403^A0,40,40^FD: {item['size']}^FS
			^FO150,470^A0,40,40^FD: {lot_no}^FS
			^FO680,267^A0,40,40^FD: {item['bundle_no']}^FS
			^FO610,335^A0,40,40^FD: {item['shade']}^FS
			^FO610,403^A0,40,40^FD: {item['quantity']}^FS

			^BY2,1,60
			^FO510,455^BC^FD{item['hash_value']}^FS

			^XZ"""
		zpl += x
	update_cutting_plan(doc_name)
	cls_doc.status = "Label Printed"
	cls_doc.save()
	return zpl	

@frappe.whitelist()
def get_panels(cutting_laysheet):
	doc = frappe.get_doc("Cutting LaySheet",cutting_laysheet)
	items = []
	for item in doc.cutting_laysheet_bundles:
		if item.bundle_no > 1:
			break
		items.append(item.part)
	return items

@frappe.whitelist()
def get_bundle_items(cutting_laysheet):
	doc = frappe.get_doc("Cutting LaySheet",cutting_laysheet)
	items = []
	bundles = []
	for item in doc.cutting_laysheet_bundles:
		if item.bundle_no not in bundles:
			items.append(item.as_dict())
			bundles.append(item.bundle_no)
	
	return items

@frappe.whitelist()
def get_colours(cutting_laysheet, items):
	doc = frappe.get_doc("Cutting LaySheet",cutting_laysheet)
	colours = set()
	for item in doc.cutting_laysheet_details:
		colours.add(item.colour)
	
	colour_items = {}

	for colour in colours:
		for item in items:
			if item['colour'] == colour:
				if colour in colour_items:
					colour_items[colour].append(item)
				else:
					colour_items[colour] = [item]

	return colours,colour_items
	
@frappe.whitelist()
def get_created_date(creation):
	created_date = getdate(creation)
	date = created_date.day
	month = created_date.month
	year = created_date.year 
	return str(date)+"/"+str(month)+"/"+str(year)

@frappe.whitelist()
def update_cutting_plan(cutting_laysheet):
	cls_doc = frappe.get_doc("Cutting LaySheet",cutting_laysheet)
	cp_doc = frappe.get_doc("Cutting Plan",cls_doc.cutting_plan)
	ipd_doc = frappe.get_doc("Item Production Detail",cp_doc.production_detail)

	incomplete_items = json.loads(cp_doc.incomplete_items_json)
	completed_items = json.loads(cp_doc.completed_items_json)
	
	for item in cls_doc.cutting_laysheet_bundles:
		parts = item.part.split(",")
		for x in incomplete_items['items']:
			if completed_items['is_set_item']:
				if x['attributes'][ipd_doc.packing_attribute] == item.colour and item.part in incomplete_items[ipd_doc.stiching_attribute][x['attributes'][ipd_doc.set_item_attribute]]:
					for val in x['values']:
						if item.size == val:
							for part in parts:
								x['values'][val][part] += item.quantity
			else:
				if x['attributes'][ipd_doc.packing_attribute] == item.colour:
					for val in x['values']:
						if item.size == val:
							for part in parts:
								x['values'][val][part] += item.quantity						
	
	stitching_combination = get_stitching_combination(ipd_doc)
	set_item = ipd_doc.is_set_item
	if not ipd_doc.is_same_packing_attribute:
		cm_doc = frappe.get_doc("Cutting Marker",cls_doc.cutting_marker)
		cutting_marker_list = []
		for mark in cm_doc.cutting_marker_parts:
			cutting_marker_list.append(mark.part)

		item_panel = {}
		for item in incomplete_items['items']:
			for val in item['values']:
				for panel in item['values'][val]:
					if set_item:
						key = (val,item['attributes'][ipd_doc.packing_attribute],item['attributes'][ipd_doc.set_item_attribute])
					else:
						key = (val,item['attributes'][ipd_doc.packing_attribute])	
					if key in item_panel:
						if panel in item_panel[key]:
							item_panel[key][panel] += item['values'][val][panel]
						else:
							item_panel[key][panel] = item['values'][val][panel]
					else:	
						item_panel[key] = {}
						item_panel[key][panel] = item['values'][val][panel] 
		
		for item in item_panel:
			check = True
			min = sys.maxsize
			part = None
			condition1 = True
			if set_item:
				part = item[2]

			for i in stitching_combination['stitching_combination'][item[1]]:
				if i in cutting_marker_list:
					panel_colour = stitching_combination['stitching_combination'][item[1]][i]
					if set_item:
						condition1 = i in incomplete_items[ipd_doc.stiching_attribute][part]

					if condition1:	
						m = False
						for panel in item_panel:
							condition2 = True
							if set_item:
								condition2 = panel[2] == part
							if condition2 and panel[0] == item[0] and panel[1] == panel_colour and item_panel[panel][i] > 0:
								m = True
								if item_panel[panel][i] < min:
									min = item_panel[panel][i]
								break
						if not m:
							check = False
							break
				else:
					check = False		
			if check:
				for x in completed_items['items']:
					total_qty = 0
					condition3 = True
					if set_item:
						condition3 = x['attributes'][ipd_doc.set_item_attribute] == part
					if x['attributes'][ipd_doc.packing_attribute] == item[1] and condition3:
						x['values'][item[0]] += min
						completed_items['total_qty'][item[0]] += min
						total_qty += x['values'][item[0]]
						break	
					if total_qty != 0:
						x['total_qty'] = total_qty

				for i in stitching_combination['stitching_combination'][item[1]]:
					panel_colour = stitching_combination['stitching_combination'][item[1]][i]
					condition4 = True
					if set_item:
						condition4 = i in incomplete_items[ipd_doc.stiching_attribute][part]

					if condition4:	
						for panel in item_panel:
							condition5 = True
							if set_item:
								condition5 = panel[2] == part
							if condition5 and panel[0] == item[0] and panel[1] == panel_colour and item_panel[panel][i] > 0:
								item_panel[panel][i] -= min
								for x in incomplete_items['items']:
									condition6 = True
									if set_item:
										condition6 =  x['attributes'][ipd_doc.set_item_attribute] == part
									if x['attributes'][ipd_doc.packing_attribute] == panel_colour and condition6:
										x['values'][panel[0]][i] -= min
										break		
	else:	
		for item1,item2 in zip_longest(incomplete_items['items'],completed_items['items']):
			total_qty = 0
			for val in item1['values']:
				check = True
				min = sys.maxsize
				for panel in item1['values'][val]:
					panel_count = item1['values'][val][panel]
					if panel_count == 0:
						check = False
					elif min > panel_count:
						min = panel_count

				if check:
					for panel in item1['values'][val]:
						item1['values'][val][panel] -= min
					item2['values'][val] += min
					total_qty += item2['values'][val]
					completed_items['total_qty'][val] += min
			if total_qty != 0:		
				item2['total_qty'] = total_qty 			

	accessory= {}
	cloth = {}
	for item in cls_doc.cutting_laysheet_details:
		key = (item.colour, item.cloth_type, item.dia)
		cloth.setdefault(key,0)
		cloth[key] += item.weight - item.balance_weight
		accessory.setdefault(key,0)
		accessory[key] += item.accessory_weight

	cp_doc = frappe.get_doc("Cutting Plan",cls_doc.cutting_plan)
	for item in cp_doc.cutting_plan_cloth_details:
		key = (item.colour, item.cloth_type, item.dia)
		if key in cloth:
			item.used_weight += cloth[key]
			item.balance_weight = item.weight - item.used_weight

	for item in cp_doc.cutting_plan_accessory_details:
		key = (item.colour, item.cloth_type, item.dia)
		if key in accessory:
			item.used_weight += accessory[key]

	cp_doc.incomplete_items_json = incomplete_items
	cp_doc.completed_items_json = completed_items
	cp_doc.save()		