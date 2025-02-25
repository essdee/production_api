# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

from frappe import bold
from six import string_types
from frappe.utils import getdate
from itertools import zip_longest
from frappe.model.document import Document
import frappe, json, sys, base64, math, time
from secrets import token_bytes as get_random_bytes
from production_api.production_api.doctype.item.item import get_or_create_variant
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_stitching_combination
from production_api.production_api.doctype.cutting_marker.cutting_marker import fetch_marker_details

class CuttingLaySheet(Document):
	def autoname(self):
		self.naming_series = "CLS-.YY..MM.-.{#####}."

	def onload(self):
		self.set_onload("item_details",self.cutting_laysheet_details)
		self.set_onload("item_accessories", self.cutting_laysheet_accessory_details)
		if self.selected_type:
			items = fetch_marker_details(self.cutting_marker_ratios, self.selected_type)
			self.set_onload("marker_details", items)

	def before_validate(self):
		if self.get('item_details'):
			items = save_item_details(self.item_details, self.cutting_plan)
			self.set("cutting_laysheet_details", items)

		if self.get('item_accessory_details'):
			items = save_accessory_details(self.item_accessory_details, self.cutting_plan)	
			self.set("cutting_laysheet_accessory_details", items)

		status = frappe.get_value("Cutting Plan",self.cutting_plan,"status")	
		if status == "Completed":
			frappe.throw("Select the Incompleted Cutting Plan")
		
		cm_docstatus = frappe.get_value("Cutting Marker",self.cutting_marker,"docstatus")
		if cm_docstatus != 1:
			frappe.throw("Select a Submitted Cutting Marker")

		cut_marker_cp = frappe.get_value("Cutting Marker",self.cutting_marker,"cutting_plan")		
		if cut_marker_cp != self.cutting_plan:
			frappe.throw(f"Select a Cutting Marker which is against {self.cutting_plan}")

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
				marker_list.append({'size':item.size, "panel": item.panel, 'ratio':item.ratio})

			self.set("cutting_marker_ratios",marker_list)
			self.selected_type = cut_marker_doc.selected_type
			self.calculated_parts = cut_marker_doc.calculated_parts	
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
			no_of_rolls += item.no_of_rolls
			used_weight += item.used_weight
			colours.add(item.colour)

		for item in self.cutting_laysheet_accessory_details:
			accessory_weight += item.weight
			no_of_rolls += item.no_of_rolls
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
	ipd_doc = frappe.get_cached_doc("Item Production Detail",ipd)
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
			"items_json":item['items_json'] if item.get('items_json') and len(item['items_json']) > 0 else {},
			"set_combination": item['set_combination'] if item.get('set_combination') and len(item['set_combination']) > 0 else {}
		})
	return item_list	

def save_accessory_details(items, cutting_plan):
	if isinstance(items, string_types):
		items = json.loads(items)
	ipd = frappe.get_value("Cutting Plan",cutting_plan,"production_detail")
	ipd_doc = frappe.get_cached_doc("Item Production Detail",ipd)
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
			"accessory": item['accessory'],
			"cloth_item_variant":variant,
			"cloth_type":item['cloth_type'],
			"colour":item['colour'],
			"dia":item['dia'],
			"shade":item['shade'],
			"weight":item['weight'],
			"no_of_rolls":item['no_of_rolls'],
		})
	return item_list	

@frappe.whitelist()
def get_select_attributes(cutting_plan):
	doc = frappe.get_doc("Cutting Plan",cutting_plan)
	cloth_type = set()
	colour = set()
	dia = set()
	part = set()

	ipd_doc = frappe.get_doc("Item Production Detail",doc.production_detail)
	if ipd_doc.is_set_item:
		for row in ipd_doc.stiching_item_details:
			part.add(row.set_item_attribute_value)

	for item in doc.cutting_plan_cloth_details:
		cloth_type.add(item.cloth_type)
		colour.add(item.colour)
		dia.add(item.dia)
	return {
		"cloth_type":cloth_type,
		"colour":colour,
		"dia":dia,
		"part":part,
	}	

@frappe.whitelist()
def get_parts(cutting_marker):
	panels = frappe.get_value("Cutting Marker",cutting_marker,"calculated_parts")
	return panels.split(",")	

@frappe.whitelist()
def get_cut_sheet_data(doc_name,cutting_marker,item_details,items, max_plys:int,maximum_allow:int):
	if isinstance(items, string_types):
		items = json.loads(items)
	items_combined = {}
	for item in items:
		if items_combined.get(item['value']):
			items_combined[item['value']].append(item['part'])
		else:
			items_combined[item['value']] = [item['part']]	
	items = []
	for value, arr in items_combined.items():		
		items.append(",".join(arr))

	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)	
	maximum_plys = max_plys + (max_plys/100) * maximum_allow
	bundle_no = 0
	cm_doc = frappe.get_doc("Cutting Marker",cutting_marker)
	check_ratio_parts(items_combined, cm_doc.cutting_marker_ratios)
	cut_sheet_data = []
	for item in item_details:
		if item['no_of_bits'] == 0:
			continue
		first_size = None
		last_size = None
		calc_panels = []
		for cm_item in cm_doc.cutting_marker_ratios:
			first_size = cm_item.size
			markCount = cm_item.ratio
			no_of_marks = int(markCount)
			check = False
			if markCount != no_of_marks:
				check = True

			if no_of_marks == 0:
				continue

			max_grouping = int(maximum_plys/item['no_of_bits'])
			if max_grouping == 0:
				frappe.msgprint("Max number of Plys should not be less than No of Bits")
				return
			total_bundles = math.ceil(no_of_marks/max_grouping)
			avg_grouping = no_of_marks/total_bundles
			minimum = math.floor(avg_grouping)
			maximum = math.ceil(avg_grouping)
			maximum_count = no_of_marks - (total_bundles * minimum)
			minimum_count = total_bundles - maximum_count
	
			temp = bundle_no 
			if first_size != last_size:
				last_size = cm_item.size
				calc_panels = []

			for part_value in items:
				parts = part_value.split(",")
				start = True
				for part in parts:
					if part in calc_panels:
						start = False
						break
					else:
						calc_panels.append(part)	
				if start:
					bundle_no = temp	
					update = True
					for j in range(maximum_count):
						bundle_no = bundle_no + 1
						qty = maximum * item['no_of_bits']
						last_balance = 0
						if minimum_count == 0 and check and j == maximum_count - 1:
							x = qty + item['no_of_bits']/2
							update = False						
							if x > maximum_plys:
								last_balance = item['no_of_bits']/2
							else:
								qty = qty + item['no_of_bits']/2	
						d = get_cut_sheet_dict(cm_item.size, item['colour'], item['shade'], part_value , qty, bundle_no, item['set_combination'])
						cut_sheet_data.append(d)	

						if last_balance > 0:
							bundle_no = bundle_no + 1
							d = get_cut_sheet_dict(cm_item.size, item['colour'], item['shade'], part_value , last_balance, bundle_no, item['set_combination'])
							cut_sheet_data.append(d)

					for j in range(minimum_count):
						bundle_no = bundle_no + 1
						qty = minimum * item['no_of_bits']
						last_balance = 0
						if check and j == minimum_count - 1:
							x = qty + item['no_of_bits']/2
							update = False						
							if x > maximum_plys:
								last_balance = item['no_of_bits']/2
							else:
								qty = qty + item['no_of_bits']/2	

						d = get_cut_sheet_dict(cm_item.size, item['colour'], item['shade'], part_value , qty, bundle_no, item['set_combination'])
						cut_sheet_data.append(d)
						if last_balance > 0:
							bundle_no = bundle_no + 1
							d = get_cut_sheet_dict(cm_item.size, item['colour'], item['shade'], part_value , last_balance, bundle_no, item['set_combination'])
							cut_sheet_data.append(d)

					if update and check:
						bundle_no = bundle_no + 1
						d = get_cut_sheet_dict(cm_item.size, item['colour'], item['shade'], part_value , item['no_of_bits']/2, bundle_no, item['set_combination'])
						cut_sheet_data.append(d)
			temp = bundle_no	

	from operator import itemgetter
	cut_sheet_data = sorted(cut_sheet_data, key=itemgetter('bundle_no'))

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
	accessory= {}
	cloth = {}
	for item in doc.cutting_laysheet_details:
		key = (item.colour, item.cloth_type, item.dia)
		cloth.setdefault(key,0)
		cloth[key] += item.weight - item.balance_weight

	for item in doc.cutting_laysheet_accessory_details:
		key = (item.colour, item.cloth_type, item.dia)
		accessory.setdefault(key,0)
		accessory[key] += item.weight
	cp_doc = frappe.get_doc("Cutting Plan",doc.cutting_plan)
	for item in cp_doc.cutting_plan_cloth_details:
		key = (item.colour, item.cloth_type, item.dia)
		if key in cloth:
			item.used_weight += cloth[key]
			item.balance_weight = item.weight - item.used_weight
			if item.balance_weight < 0:
				frappe.throw(f"{bold(item.dia)} {bold(item.colour)}, {bold(item.cloth_type)} was used more than the received weight")
				return
		if key in accessory:
			item.used_weight += accessory[key]
			item.balance_weight = item.weight - item.used_weight
			if item.balance_weight < 0:
				frappe.throw(f"{bold(item.dia)} {bold(item.colour)}, {bold(item.cloth_type)} was used more than the received weight")
				return
	check_cutting_plan(doc_name)		

@frappe.whitelist()
def check_cutting_plan(cutting_laysheet):
	cls_doc = frappe.get_doc("Cutting LaySheet",cutting_laysheet)
	production_detail, incomplete_items_json, completed_items_json = frappe.get_value("Cutting Plan",cls_doc.cutting_plan,['production_detail',"incomplete_items_json","completed_items_json"])
	ipd_doc = frappe.get_doc("Item Production Detail",production_detail)

	incomplete_items = json.loads(incomplete_items_json)
	completed_items = json.loads(completed_items_json)
	for item in cls_doc.cutting_laysheet_bundles:
		parts = item.part.split(",")
		for x in incomplete_items['items']:
			if x['attributes'][ipd_doc.packing_attribute] == item.colour:
					for val in x['values']:
						if item.size == val:
							for part in parts:
								condition = True
								if completed_items['is_set_item']:
									condition = part in incomplete_items[ipd_doc.stiching_attribute][x['attributes'][ipd_doc.set_item_attribute]]
								if condition:
									x['values'][val][part] += item.quantity
	
	stitching_combination = get_stitching_combination(ipd_doc)
	set_item = ipd_doc.is_set_item
	cm_doc = frappe.get_doc("Cutting Marker",cls_doc.cutting_marker)
	cutting_marker_list = cm_doc.calculated_parts.split(",")
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
		stich_key = item[1]

		if set_item:
			part = item[2]
			stich_key = (stich_key, part)

		for i in stitching_combination['stitching_combination'][stich_key]:
			if i in cutting_marker_list:
				panel_colour = stitching_combination['stitching_combination'][stich_key][i]
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
					if x['completed']:
						txt = item[1]
						if set_item:
							txt += "-" + part
						frappe.throw(f"Already {txt} was completed")
					x['values'][item[0]] += min
					completed_items['total_qty'][item[0]] += min
					total_qty += x['values'][item[0]]
					break	
				
				if total_qty != 0:
					x['total_qty'] = total_qty

def check_ratio_parts(parts, marker_ratios):
	calculated_sizes = []
	ratios = {}
	for marker in marker_ratios:
		if marker.size not in calculated_sizes:
			calculated_sizes.append(marker.size)
			for value, panels in parts.items():
				ratios = []
				if len(panels) > 0:
					for panel in panels:
						for marker2 in marker_ratios:
							if marker2.size == marker.size and marker2.panel == panel:
								if marker2.ratio not in ratios and len(ratios) > 0:
									frappe.throw("Can't combine the different ratio's as a bundle")
								else:
									ratios.append(marker2.ratio)	

def get_cut_sheet_dict(size, colour, shade, part, qty, bundle_no, set_combination):
	hash_value = get_timestamp_prefix() + generate_random_string(12)
	return {
		"size": size,
		"colour":colour,
		"shade":shade,
		"bundle_no":bundle_no,
		"part": part,
		"quantity":qty,
		"hash_value":hash_value,
		"set_combination": set_combination,
	}

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
	production_detail, incomplete_items_json, completed_items_json, version = frappe.get_value("Cutting Plan",cls_doc.cutting_plan,['production_detail',"incomplete_items_json","completed_items_json"])
	ipd_doc = frappe.get_doc("Item Production Detail",production_detail)
	incomplete_items = json.loads(incomplete_items_json)
	completed_items = json.loads(completed_items_json)
	if version == "V2":
		if not ipd_doc.is_set_item:
			alter_incomplete_items = {}
			for item in incomplete_items['items']:
				colour = item['attributes'][ipd_doc.packing_attribute]
				alter_incomplete_items[colour] = item['values']
			
			for item in cls_doc.cutting_laysheet_bundles:
				parts = item.part.split(",")
				set_combination = item.set_combination
				if isinstance(set_combination, string_types):
					set_combination = json.loads(set_combination)
				set_colour = set_combination['major_colour']
				qty = item.quantity
				for part in parts:
					alter_incomplete_items[set_colour][item.size][part] += qty	
			
			for item in completed_items['items']:
				colour = item['attributes'][ipd_doc.packing_attribute]
				for val in item['values']:
					min = sys.maxsize
					for panel in alter_incomplete_items[colour][val]:
						if alter_incomplete_items[colour][val][panel] < min:
							min = alter_incomplete_items[colour][val][panel]
					item['values'][val] += min
					for panel in alter_incomplete_items[colour][val]:
						alter_incomplete_items[colour][val][panel] -= min

			for item in incomplete_items['items']:
				colour = item['attributes'][ipd_doc.packing_attribute]
				item['values'] = alter_incomplete_items[colour]
		else:
			alter_incomplete_items = {}
			for item in incomplete_items['items']:
				colour = item['attributes'][ipd_doc.packing_attribute]
				part = item['attributes'][ipd_doc.set_item_attribute]
				if alter_incomplete_items.get(colour):
					alter_incomplete_items[colour][part] = item['values']
				else:	
					alter_incomplete_items[colour] = {}
					alter_incomplete_items[colour][part] = item['values']

			for item in cls_doc.cutting_laysheet_bundles:
				parts = item.part.split(",")
				set_combination = item.set_combination
				if isinstance(set_combination, string_types):
					set_combination = json.loads(set_combination)
				major_part = set_combination['major_part']
				major_colour = set_combination['major_colour']
				if set_combination.get('set_part'):
					major_part = set_combination['set_part']
					major_colour = set_combination['set_colour']
				qty = item.quantity
				for part in parts:
					alter_incomplete_items[major_colour][major_part][item.size][part] += qty

			for item in completed_items['items']:
				colour = item['attributes'][ipd_doc.packing_attribute]
				part = item['attributes'][ipd_doc.set_item_attribute]
				for val in item['values']:
					min = sys.maxsize
					for panel in alter_incomplete_items[colour][part][val]:
						if alter_incomplete_items[colour][part][val][panel] < min:
							min = alter_incomplete_items[colour][part][val][panel]
					item['values'][val] += min
					for panel in alter_incomplete_items[colour][part][val]:
						alter_incomplete_items[colour][part][val][panel] -= min		

		cloth = {}
		for item in cls_doc.cutting_laysheet_details:
			key = (item.colour, item.cloth_type, item.dia)
			cloth.setdefault(key,0)
			cloth[key] += item.weight - item.balance_weight
		accessory = {}
		for item in cls_doc.cutting_laysheet_accessory_details:
			key = (item.colour, item.cloth_type, item.dia)
			accessory.setdefault(key,0)
			accessory[key] += item.weight
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
	else:
		for item in cls_doc.cutting_laysheet_bundles:
			parts = item.part.split(",")
			for x in incomplete_items['items']:
				if x['attributes'][ipd_doc.packing_attribute] == item.colour:
						for val in x['values']:
							if item.size == val:
								for part in parts:
									condition = True
									if completed_items['is_set_item']:
										condition = part in incomplete_items[ipd_doc.stiching_attribute][x['attributes'][ipd_doc.set_item_attribute]]
									if condition:
										x['values'][val][part] += item.quantity
		
		stitching_combination = get_stitching_combination(ipd_doc)
		set_item = ipd_doc.is_set_item
		cm_doc = frappe.get_doc("Cutting Marker",cls_doc.cutting_marker)
		cutting_marker_list = cm_doc.calculated_parts.split(",")
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
			stich_key = item[1]
			if set_item:
				part = item[2]
				stich_key = (stich_key, part)

			for i in stitching_combination['stitching_combination'][stich_key]:
				if i in cutting_marker_list:
					panel_colour = stitching_combination['stitching_combination'][stich_key][i]
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
						if x['completed']:
							txt = item[1]
							if set_item:
								txt += "-" + part
							frappe.throw(f"Already {txt} was completed")
						x['values'][item[0]] += min
						completed_items['total_qty'][item[0]] += min
						total_qty += x['values'][item[0]]
						break	
					
					if total_qty != 0:
						x['total_qty'] = total_qty

				for i in stitching_combination['stitching_combination'][stich_key]:
					panel_colour = stitching_combination['stitching_combination'][stich_key][i]
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

@frappe.whitelist()
def get_input_fields(cutting_marker, colour, select_attributes):
	inputs = []
	if isinstance(select_attributes, string_types):
		select_attributes = json.loads(select_attributes)
	cm_doc = frappe.get_doc("Cutting Marker",cutting_marker)
	panels = cm_doc.calculated_parts.split(",")
	ipd = frappe.get_value("Cutting Plan",cm_doc.cutting_plan,"production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	stich_attr_value = ipd_doc.stiching_major_attribute_value
	major_attr_value = ipd_doc.major_attribute_value
	select_vals = select_attributes['colour']
	if ipd_doc.is_set_item:
		stiching_details = {}
		default = {}

		for panel in ipd_doc.stiching_item_details:
			if panel.is_default:
				default[panel.set_item_attribute_value] = panel.stiching_attribute_value

			stiching_details[panel.stiching_attribute_value] = panel.set_item_attribute_value

		marker_parts = set()
		for panel in panels:
			marker_parts.add(stiching_details[panel])
		marker_parts = list(marker_parts)	
		part_colours = {}
		index = -1
		last_colour = None
		is_same = True
		for row in ipd_doc.set_item_combination_details:
			if row.index != index:
				index = row.index
				last_colour = row.attribute_value
			
			if last_colour != row.attribute_value:
				is_same = False

			part_colours.setdefault(row.set_item_attribute_value, set())
			part_colours[row.set_item_attribute_value].add(row.attribute_value)

		if len(marker_parts) > 1:
			inputs.append({"fieldname":"major_part", "fieldtype":"Data", "label":"Major Part", "default": major_attr_value})
			inputs.append({"fieldname":"major_panel", "fieldtype":"Data", "label":"Major Panel", "default": default[major_attr_value]})
			if is_same:
				inputs.append({"fieldname":"major_colour", "fieldtype":"Data", "label":"Major Colour", "default":colour})
			else:
				inputs.append({"fieldname":"major_colour", "fieldtype":"Select", "label":"Major Colour", "options":select_vals})
		else:
			if marker_parts[0] == major_attr_value:
				inputs.append({"fieldname":"major_part", "fieldtype":"Data", "label":"Major Part", "default": marker_parts[0]})		
				inputs.append({"fieldname":"major_panel", "fieldtype":"Data", "label":"Major Panel", "default": default[marker_parts[0]]})
				if is_same or default[marker_parts[0]] in panels:
					inputs.append({"fieldname":"major_colour", "fieldtype":"Data", "label":"Major Colour", "default":colour})
				else:
					inputs.append({"fieldname":"major_colour", "fieldtype":"Select", "label":"Major Colour", "options":select_vals})
			else:
				inputs.append({"fieldname":"major_part", "fieldtype":"Data", "label":"Major Part", "default": major_attr_value})
				inputs.append({"fieldname":"major_panel", "fieldtype":"Data", "label":"Major Panel", "default": default[major_attr_value]})
				if is_same:
					inputs.append({"fieldname":"major_colour", "fieldtype":"Data", "label":"Major Colour", "default":colour})
					inputs.append({"fieldname":"set_part", "fieldtype":"Data", "label":"Set Part", "default": marker_parts[0]})
					inputs.append({"fieldname":"set_panel", "fieldtype":"Data", "label":"Set Panel", "default": default[marker_parts[0]]})
					inputs.append({"fieldname":"set_colour", "fieldtype":"Data", "label":"Set Colour", "default":colour})
				else:
					inputs.append({"fieldname":"major_colour", "fieldtype":"Select", "label":"Major Colour", "options":select_vals})
					inputs.append({"fieldname":"set_part", "fieldtype":"Data", "label":"Set Part", "default": marker_parts[0]})
					inputs.append({"fieldname":"set_panel", "fieldtype":"Data", "label":"Set Panel", "default": default[marker_parts[0]]})
					inputs.append({"fieldname":"set_colour", "fieldtype":"Select", "label":"Set Colour", "options":select_vals})
	else:
		if ipd_doc.is_same_packing_attribute or stich_attr_value in panels:
			inputs.append({"fieldname":"major_panel", "fieldtype":"Data", "label":"Major Panel", "default": stich_attr_value})
			inputs.append({"fieldname":"major_colour", "fieldtype":"Data", "label":"Major Colour", "default":colour})
		else:
			inputs.append({"fieldname":"major_panel", "fieldtype":"Data", "label":"Major Panel", "default": stich_attr_value})
			inputs.append({"fieldname":"major_colour", "fieldtype":"Select", "label":"Major Colour", "options":select_vals})

	return inputs		