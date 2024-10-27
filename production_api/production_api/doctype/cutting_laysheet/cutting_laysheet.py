# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import math
import frappe,json
from itertools import groupby
from six import string_types
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_or_create_variant
from frappe.utils import now_datetime

class CuttingLaySheet(Document):
	def autoname(self):
		self.naming_series = "CLS-.YY..MM.-.{#####}."

	def onload(self):
		self.set_onload("item_details",self.cutting_laysheet_details)

	def before_validate(self):
		if self.get('item_details'):
			items = save_item_details(self.item_details, self.cutting_plan)
			self.set("cutting_laysheet_details", items)

		if self.is_new():
			cut_plan_doc = frappe.get_doc("Cutting Plan",self.cutting_plan)	
			
			self.lay_no = cut_plan_doc.lay_no + 1
			self.maximum_no_of_plys = cut_plan_doc.maximum_no_of_plys
			self.maximum_allow_percentage = cut_plan_doc.maximum_allow_percent
			cut_plan_doc.lay_no = self.lay_no
			cut_plan_doc.flags.ignore_permissions = 1
			cut_plan_doc.save()
			cut_marker_doc = frappe.get_doc("Cutting Marker",self.cutting_marker)
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
		for item in self.cutting_laysheet_details:
			no_of_bits += item.no_of_bits
			weight += item.weight
			end_bit_weight += item.end_bit_weight
			accessory_weight += item.accessory_weight
			no_of_rolls += item.no_of_rolls
			colours.add(item.colour)

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
		for cm_item in cm_doc.cutting_marker_ratios:
			no_of_marks = cm_item.ratio
			if no_of_marks == 0:
				continue
			max_grouping = int(maximum_plys/item['no_of_bits'])
			total_bundles = math.ceil(no_of_marks/max_grouping)
			avg_grouping = no_of_marks/total_bundles

			minimum = math.floor(avg_grouping)
			maximum = math.ceil(avg_grouping)

			maximum_count = no_of_marks - (total_bundles * minimum)
			minimum_count = total_bundles - maximum_count
	
			temp = bundle_no 
			for part,group in items.items():
				bundle_no = temp	
				for j in range(maximum_count):
					bundle_no = bundle_no + 1
					hash_value = get_timestamp_prefix() + generate_random_string(12)
					cut_sheet_data.append({
						"size":cm_item.size,
						"colour":item['colour'],
						"shade":item['shade'],
						"bundle_no":bundle_no,
						"part":part,
						"quantity":maximum * item['no_of_bits'],
						"hash_value":hash_value
					})	
				for j in range(minimum_count):
					bundle_no = bundle_no + 1
					hash_value = get_timestamp_prefix() + generate_random_string(12)
					cut_sheet_data.append({
						"size":cm_item.size,
						"colour":item['colour'],
						"shade":item['shade'],
						"bundle_no":bundle_no,
						"part":part,
						"quantity":minimum * item['no_of_bits'],
						"hash_value":hash_value
					})		
			temp = bundle_no	
	
	dictionary = {}
	for item in cut_sheet_data:
		if dictionary.get(item['bundle_no']):
			dictionary[item['bundle_no']].append(item)
		else:
			dictionary[item['bundle_no']] = [item]	

	final_list = {}
	for key,values in dictionary.items():
		final_list[key] = []
		group = []
		for value in values:
			part = value['part']
			if items[part] not in group:
				value['group'] = items[part]
				final_list[key].append(value)
			else:
				for j in final_list[key]:
					if j['group'] == items[part]:
						pt = j['part']
						j['part'] =  pt + "," + part
			group.append(items[part])				

	cut_sheet_data = []
	for key, values in final_list.items():
		for val in values:
			val['bundle_no'] = key
			cut_sheet_data.append(val)

	doc = frappe.get_doc("Cutting LaySheet", doc_name)
	doc.maximum_no_of_plys = max_plys
	doc.maximum_allow_percentage = maximum_allow 
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
	creation = frappe.get_value("Cutting LaySheet",doc_name,"creation")
	date = get_created_date(creation)
	# month = now_datetime().month
	# date = now_datetime().day
	# year = now_datetime().year
	i = 0
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
	
from frappe.utils import getdate
@frappe.whitelist()
def get_created_date(creation):
	created_date = getdate(creation)
	date = created_date.day
	month = created_date.month
	year = created_date.year 
	return str(date)+"/"+str(month)+"/"+str(year)