# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

from frappe import bold
from six import string_types
from frappe.model.document import Document
import frappe, json, sys, base64, math, time
from production_api.utils import get_part_list
from frappe.utils import getdate, nowdate, now
from production_api.utils import get_stich_details
from secrets import token_bytes as get_random_bytes
from production_api.utils import update_if_string_instance
from production_api.production_api.doctype.item.item import get_or_create_variant
from production_api.production_api.doctype.cutting_marker.cutting_marker import fetch_marker_details
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_stitching_combination

class CuttingLaySheet(Document):
	def autoname(self):
		self.naming_series = "CLS-.YY..MM.-.{#####}."

	def onload(self):
		if not self.is_new():
			item_detail = {}
			if self.is_manual_entry:
				item_detail = fetch_manual_item_details(self.cutting_laysheet_manual_items, self.name)
			details = {
				"manual_items": item_detail,
				"cloth_items": self.cutting_laysheet_details,
			}	
			self.set_onload("item_details", details)
			self.set_onload("item_accessories", self.cutting_laysheet_accessory_details)
			if self.selected_type:
				items = fetch_marker_details(self.cutting_marker_ratios, self.selected_type)
				details = {
					"cutting_marker_ratios": items,
					"cutting_marker_groups": [],
				}
				self.set_onload("marker_details", details)

	def before_validate(self):
		if frappe.get_value("Cutting LaySheet", self.name, "status") == "Cancelled" and self.status == "Cancelled":
			frappe.throw("Can't update the Cancelled Laysheet")

		if self.get('item_details'):
			if self.is_manual_entry:
				items = save_manual_item_details(self.item_details, self.cutting_plan, self.calculated_parts, self.name)
				self.set("cutting_laysheet_manual_items", items)
			items = save_item_details(self.item_details, self.cutting_plan, self.calculated_parts)
			self.set("cutting_laysheet_details", items)

		if self.get('item_accessory_details'):
			items = save_accessory_details(self.item_accessory_details, self.cutting_plan)	
			self.set("cutting_laysheet_accessory_details", items)

		status = frappe.get_value("Cutting Plan",self.cutting_plan,"status")	
		if status == "Completed":
			frappe.throw("Select the Incompleted Cutting Plan")
		
		cm_docstatus, cut_marker_cp  = frappe.get_value("Cutting Marker",self.cutting_marker,["docstatus","cutting_plan"])
		if cm_docstatus != 1:
			frappe.throw("Select a Submitted Cutting Marker")

		if cut_marker_cp != self.cutting_plan:
			frappe.throw(f"Select a Cutting Marker which is against {self.cutting_plan}")

		if self.is_new():
			cut_plan_doc = frappe.get_doc("Cutting Plan",self.cutting_plan)	
			cut_marker_doc = frappe.get_doc("Cutting Marker",self.cutting_marker)		
			is_set_item = frappe.get_value("Item Production Detail", cut_plan_doc.production_detail, "is_set_item")
			self.is_set_item = is_set_item
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
		total_bits = 0.0
		weight = 0.0
		end_bit_weight = 0.0
		accessory_weight = 0.0
		no_of_rolls = 0
		used_weight = 0.0

		if self.is_manual_entry:
			if len(self.cutting_laysheet_manual_items) > 0 and self.status == "Started":
				self.status = "Completed"

		for item in self.cutting_laysheet_details:
			total_bits += item.effective_bits
			weight += item.weight
			end_bit_weight += item.end_bit_weight
			no_of_rolls += item.no_of_rolls
			used_weight += item.used_weight
			colours.add(item.colour)

		for item in self.cutting_laysheet_accessory_details:
			accessory_weight += item.weight
			no_of_rolls += item.no_of_rolls
			colours.add(item.colour)

		sizes = {}
		ratio_sum = 0
		for row in self.cutting_marker_ratios:
			if row.size not in sizes:
				ratio_sum += row.ratio
				sizes[row.size] = row.ratio

		if weight and self.status == 'Started':
			self.status = "Completed"

		items = []
		for colour in colours:
			for item in self.cutting_laysheet_details:
				if item.colour == colour:
					items.append(item)
		self.no_of_rolls = no_of_rolls
		self.no_of_bits = total_bits
		self.weight = weight
		self.end_bit_weight = end_bit_weight
		self.accessory_weight = accessory_weight
		if self.is_manual_entry:
			self.total_used_weight = weight
			total_pieces = 0
			for row in self.cutting_laysheet_bundles:
				total_pieces += row.quantity
			self.total_no_of_pieces = total_pieces
			if self.total_no_of_pieces:
				self.piece_weight = weight / self.total_no_of_pieces
		else:
			self.total_used_weight = used_weight
			self.total_no_of_pieces = total_bits * ratio_sum
			if self.total_no_of_pieces:
				self.piece_weight = used_weight / self.total_no_of_pieces
		self.set("cutting_laysheet_details",items)			

def fetch_manual_item_details(manual_items, cutting_laysheet):
	grouped_items = get_grouped_items(manual_items, cutting_laysheet)
	manual_items = {}
	idx = 0
	for items in grouped_items:
		manual_items[idx] = {}
		manual_items[idx]['colour'] = items[0].colour
		manual_items[idx]['major_colour'] = items[0].major_colour
		manual_items[idx]['shade'] = items[0].shade
		manual_items[idx]['quantity'] = items[0].quantity
		manual_items[idx]['manual_index'] =  idx
		for item in items:
			manual_items[idx][item.size] = item.multiplier
		set_combination = update_if_string_instance(items[0].set_combination)
		for key in set_combination:
			manual_items[idx][key] = set_combination[key]	
		idx += 1
	return manual_items

def get_grouped_items(manual_items, cutting_laysheet):
	primary_values = get_primary_values(cutting_laysheet)
	group_size = len(primary_values)
	if group_size == 0:
		return []
	grouped_items = [
        manual_items[i:i + group_size] 
        for i in range(0, len(manual_items), group_size)
	]
	return grouped_items

def save_item_details(items, cutting_plan, calculated_parts):
	items = update_if_string_instance(items)
	items = items['cloth_items']
	if calculated_parts:
		panels = calculated_parts.split(",")
		panels = [panel.strip() for panel in panels]
	ipd = frappe.get_value("Cutting Plan",cutting_plan,"production_detail")
	ipd_doc = frappe.get_cached_doc("Item Production Detail",ipd)
	cloth_combination, add_pack_attr = get_combined_combination(ipd_doc)
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
		for panel in panels:
			d = {
				ipd_doc.stiching_attribute: panel,
				"Dia": item['dia'],
				"Cloth": item['cloth_type'],
			}
			if add_pack_attr:
				d[ipd_doc.packing_attribute] = item['colour']
			
			key = tuple(sorted(d.items()))
			if key not in cloth_combination:
				frappe.throw(f"{panel} is not mentioned with {item['cloth_type']}-{item['dia']}")
		
		effective_bits = item.get('no_of_bits', 0)
		if item['fabric_type'] == "Tubler":
			effective_bits = effective_bits * 2
		item_list.append({
			"cloth_item_variant":variant,
			"cloth_type":item['cloth_type'],
			"colour":item['colour'],
			"dia":item['dia'],
			"shade":item['shade'],
			"weight":item['weight'],
			"no_of_rolls":item.get('no_of_rolls', 0),
			"no_of_bits":item.get('no_of_bits',0),
			"effective_bits": effective_bits,
			"end_bit_weight":item.get('end_bit_weight', 0),
			"comments":item.get('comments', None),
			"fabric_type": item['fabric_type'],
			"used_weight":item.get('used_weight', 0),
			"balance_weight":item.get('balance_weight', 0),
			"items_json":item['items_json'] if item.get('items_json') and len(item['items_json']) > 0 else {},
			"set_combination": item['set_combination'] if item.get('set_combination') and len(item['set_combination']) > 0 else {}
		})
	return item_list	

def save_manual_item_details(items, cutting_plan, calculated_parts, cutting_laysheet):
	items = update_if_string_instance(items)
	items = items['manual_items']
	primary_values = get_primary_values(cutting_laysheet)
	manual_items = []
	for key, detail in items.items():
		d_list = []
		for pv in primary_values:
			d_list.append({
				"colour": detail['colour'],
				"major_colour": detail['major_colour'],
				"shade": detail['shade'],
				"multiplier": int(detail[pv]),
				"size": pv,
				"quantity": int(detail['quantity']),
			})
		del detail['colour']
		del detail['shade']
		del detail['quantity']
		del detail['manual_index']
		for pv in primary_values:
			del detail[pv]
		for d in d_list:
			x = {
				"set_combination": detail
			}
			d.update(x)
			manual_items.append(d)
	return manual_items		

def save_accessory_details(items, cutting_plan):
	items = update_if_string_instance(items)
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
			"cloth_item": cloth_name,
			"cloth_type":item['cloth_type'],
			"colour":item['colour'],
			"dia":item['dia'],
			"shade":item['shade'],
			"weight":item['weight'],
			"no_of_rolls":item['no_of_rolls'],
			"moved_weight": item.get('moved_weight', 0)
		})
	return item_list	

def get_combined_combination(ipd_doc):
	cutting_items_json = update_if_string_instance(ipd_doc.cutting_items_json)
	cutting_cloths_json = update_if_string_instance(ipd_doc.cutting_cloths_json)
	cutting_attrs = [attr.attribute for attr in ipd_doc.cutting_attributes]
	cloths_attrs = [attr.attribute for attr in ipd_doc.cloth_attributes]
	add_pack_attr = False
	if ipd_doc.packing_attribute in cutting_attrs or ipd_doc.packing_attribute in cloths_attrs:
		add_pack_attr = True
	
	cutting_items = cutting_items_json['items']
	cutting_cloths = cutting_cloths_json['items']
	combination = {}
	if ipd_doc.stiching_attribute in cutting_attrs or ipd_doc.stiching_attribute in cloths_attrs:
		for row1 in cutting_items:
			for row2 in cutting_cloths:
				row1.update(row2)
				d = {
					ipd_doc.stiching_attribute: row1[ipd_doc.stiching_attribute],
					"Dia": row1['Dia'],
					"Cloth": row1['Cloth']
				}
				if add_pack_attr and row1.get(ipd_doc.packing_attribute):
					d[ipd_doc.packing_attribute] = row1[ipd_doc.packing_attribute]

				key = tuple(sorted(d.items()))
				combination[key] = None
	else:
		for row1 in cutting_items:
			for row2 in cutting_cloths:
				row1.update(row2)
				for row in ipd_doc.stiching_item_details:
					d = {
						ipd_doc.stiching_attribute: row.stiching_attribute_value,
						"Dia": row1['Dia'],
						"Cloth": row1['Cloth']
					}
					if add_pack_attr and row1.get(ipd_doc.packing_attribute):
						d[ipd_doc.packing_attribute] = row1[ipd_doc.packing_attribute]
					key = tuple(sorted(d.items()))
					combination[key] = None
	return combination, add_pack_attr		
	
@frappe.whitelist()
def get_select_attributes(cutting_plan):
	doc = frappe.get_doc("Cutting Plan",cutting_plan)
	cloth_type = set()
	colour = set()
	dia = set()
	part = []

	ipd_doc = frappe.get_doc("Item Production Detail",doc.production_detail)
	if ipd_doc.is_set_item:
		part = get_part_list(ipd_doc)

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
	doc = frappe.get_doc("Cutting Marker",cutting_marker)
	panel_list = []
	idx = 1
	if doc.version and doc.version == "V3" and len(doc.cutting_marker_groups) > 0:
		for row in doc.cutting_marker_groups:
			group = row.group_panels.split(",")
			for panel in group:
				panel_list.append({ "part": panel, "value": idx})	
			idx += 1
	else:
		panels = doc.calculated_parts.split(",")	
		for panel in panels:
			panel_list.append({ "part": panel, "value": idx })
			idx += 1
	return panel_list

@frappe.whitelist()
def get_cut_sheet_data(doc_name,cutting_marker,laysheet_details, manual_item_details,items, max_plys:int,maximum_allow:int):
	items = update_if_string_instance(items)
	items_combined = {}
	for item in items:
		if items_combined.get(item['value']):
			items_combined[item['value']].append(item['part'])
		else:
			items_combined[item['value']] = [item['part']]	
	items = []
	for value, arr in items_combined.items():		
		arr.sort()
		items.append(",".join(arr))

	item_details = update_if_string_instance(laysheet_details)	
	manual_details = update_if_string_instance(manual_item_details)
	maximum_plys = max_plys + (max_plys/100) * maximum_allow
	bundle_no = 0
	cm_doc = frappe.get_doc("Cutting Marker",cutting_marker)
	grouped_items = []
	group_length = {}
	if cm_doc.version and cm_doc.version == 'V3':
		for row in cm_doc.cutting_marker_groups:
			grouped_items.append(row.group_panels)
			grp_panels = row.group_panels.split(",")
			if len(grp_panels) > 1:
				final_check = False
				for item in items:
					check = True
					p = item.split(",")
					for panel in grp_panels:
						if panel not in p:
							check = False
					if check:
						group_length[item] = len(grp_panels)
						final_check = True		
				if not final_check:
					frappe.throw("Make the Group Correctly")
			else:
				group_length[row.group_panels] = 1	
				for item in items:
					if item not in group_length:
						group_length[item] = 1	

	check_ratio_parts(items_combined, cm_doc.cutting_marker_ratios)
	cut_sheet_data = []
	if cm_doc.is_manual_entry:
		bundle_no = 1
		cut_sheet_data = []
		colours = []
		for item in item_details:
			colours.append(item['colour'])

		for item in manual_details:
			if item['multiplier'] == 0:
				continue
			if item['colour'] not in colours:
				frappe.throw(f"There is no detail for Colour {item['colour']}")

			for part_value in items:
				qty = item['quantity'] * item['multiplier']
				d = get_cut_sheet_dict(item['size'], item['colour'], item['shade'], part_value , qty, bundle_no, item.get('set_combination', {}))
				cut_sheet_data.append(d)
				bundle_no += 1
	else:	
		for item in item_details:
			if item['effective_bits'] == 0:
				continue
			effective_bits = item['effective_bits']
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
					if item['effective_bits'] % 2 == 1:
						frappe.throw(f"You cannot divide this lay by 2 (effective bits = {effective_bits})")

				if no_of_marks == 0:
					if markCount > 0:
						if first_size != last_size:
							last_size = cm_item.size
							calc_panels = []
							bundle_no = bundle_no + 1

						qty = markCount * effective_bits
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
								d = get_cut_sheet_dict(cm_item.size, item['colour'], item['shade'], part_value , qty, bundle_no, item.get('set_combination', {}))
								cut_sheet_data.append(d)
				else:
					max_grouping = int(maximum_plys/effective_bits)
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
								qty = maximum * effective_bits
								if cm_doc.version and cm_doc.version == 'V3':
									qty = qty/group_length[part_value]		
								last_balance = 0
								if minimum_count == 0 and check and j == maximum_count - 1:
									x = qty + effective_bits/2
									update = False						
									if x > maximum_plys:
										last_balance = effective_bits/2
									else:
										qty = qty + effective_bits/2	
								d = get_cut_sheet_dict(cm_item.size, item['colour'], item['shade'], part_value , qty, bundle_no, item.get('set_combination', {}))
								cut_sheet_data.append(d)	

								if last_balance > 0:
									bundle_no = bundle_no + 1
									d = get_cut_sheet_dict(cm_item.size, item['colour'], item['shade'], part_value , last_balance, bundle_no, item.get('set_combination', {}))
									cut_sheet_data.append(d)

							for j in range(minimum_count):
								bundle_no = bundle_no + 1
								qty = minimum * effective_bits
								if cm_doc.version and cm_doc.version == 'V3':
									qty = qty/group_length[part_value]			
								last_balance = 0
								if check and j == minimum_count - 1:
									x = qty + effective_bits/2
									update = False						
									if x > maximum_plys:
										last_balance = effective_bits/2
									else:
										qty = qty + effective_bits/2	

								d = get_cut_sheet_dict(cm_item.size, item['colour'], item['shade'], part_value , qty, bundle_no, item.get('set_combination', {}))
								cut_sheet_data.append(d)
								if last_balance > 0:
									bundle_no = bundle_no + 1
									d = get_cut_sheet_dict(cm_item.size, item['colour'], item['shade'], part_value , last_balance, bundle_no, item.get('set_combination', {}))
									cut_sheet_data.append(d)

							if update and check:
								bundle_no = bundle_no + 1
								d = get_cut_sheet_dict(cm_item.size, item['colour'], item['shade'], part_value , effective_bits/2, bundle_no, item.get('set_combination', {}))
								cut_sheet_data.append(d)
				temp = bundle_no	

	from operator import itemgetter
	cut_sheet_data = sorted(cut_sheet_data, key=itemgetter('bundle_no'))

	doc = frappe.get_doc("Cutting LaySheet", doc_name)
	doc.maximum_no_of_plys = max_plys
	doc.maximum_allow_percentage = maximum_allow 
	doc.status = "Bundles Generated"
	doc.set("cutting_laysheet_bundles", cut_sheet_data)
	doc.save()
	accessory= {}
	cloth = {}
	for item in doc.cutting_laysheet_details:
		key = (item.colour, item.cloth_type, item.dia)
		cloth.setdefault(key,0)
		cloth[key] += item.weight - item.balance_weight
	
	accessory_cloth = {}
	for item in doc.cutting_laysheet_accessory_details:
		key = (item.accessory, item.colour, item.cloth_type, item.dia)
		accessory.setdefault(key,0)
		accessory[key] += item.weight
		key = (item.colour, item.cloth_type, item.dia)
		accessory_cloth.setdefault(key,0)
		accessory_cloth[key] += item.weight
	
	cp_doc = frappe.get_doc("Cutting Plan",doc.cutting_plan)
	for item in cp_doc.cutting_plan_cloth_details:
		key = (item.colour, item.cloth_type, item.dia)
		if key in cloth:
			item.used_weight += cloth[key]
			item.balance_weight = item.weight - item.used_weight
			if item.balance_weight < 0:
				frappe.throw(f"{bold(item.dia)} {bold(item.colour)}, {bold(item.cloth_type)} was used more than the received weight")
				return
		if key in accessory_cloth:
			item.used_weight += accessory_cloth[key]
			item.balance_weight = item.weight - item.used_weight
			if item.balance_weight < 0:
				frappe.throw(f"{bold(item.dia)} {bold(item.colour)}, {bold(item.cloth_type)} was used more than the received weight")
				return	
				
	update_cutting_plan(doc_name, check_cp=True)		

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
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	accessory_list = []
	x = update_if_string_instance(ipd_doc.accessory_clothtype_json)
	if x:
		for key,val in x.items():
			accessory_list.append(key)
	return accessory_list	

@frappe.whitelist()
def print_labels(print_items, lay_no, cutting_plan, doc_name):
	lot_no, item_name, work_order = frappe.get_value("Cutting Plan",cutting_plan,["lot", "item", "work_order"])
	print_items = update_if_string_instance(print_items)
	zpl = ""
	cls_doc = frappe.get_doc("Cutting LaySheet",doc_name)
	creation = cls_doc.creation
	date = get_created_date(creation)
	# for item in print_items:
		# string_value = item['colour']
		# set_combination = update_if_string_instance(item.get("set_combination", {}))
		# if set_combination:
		# 	if set_combination.get('is_same_packing_attribute'):
		# 		if set_combination.get('set_part'):
		# 			string_value = string_value +" ("+set_combination.get('major_colour')+")"
		# 	else:
		# 		if set_combination.get('set_part'):
		# 			string_value = string_value +" / "+ set_combination.get("set_colour")+" ("+set_combination.get('major_colour')+")"
		# 		else:
		# 			string_value = string_value + " ("+set_combination.get('major_colour')+")"		
					
		# x = f"""^XA
		# 	^FO70,30^GFA,2736,2736,38,,:::::::::::::::P0FI0MF803MFC01MFC0NFI0MF803LFEF8,0018001006B001MF807MFC07MFC0NF801MF807LFEB8,001C00300EI03MF80NFC07MFC0NFC03MF80MFE,001E00701EI07MF81NFC0NFC0NFE07MF81MFE,001F00F03EI07MF81NFC0NFC0NFE07MF81MFE,001F01F07EI07MF81NFC1NFC0NFE07MF81MFE,001F83F07EI07MF81NFC1NFC0NFE07MF81MFE,001F83F0FEI07MF81NFC1NFC0NFE07MF81MFE,001FC3F0FEI07MF01NF81NFC0NFE07MF01MFC,001FC3F0FEI07FCL01FFM01FF8M0FF8I07FE07FCL01FF,001FC3F0FEI07FCL01FFM01FF8M0FF8I03FE07FCL01FF,:::001FC3F0FEI07MF81MFE01MFE00FF8I03FE07MF81MFE,001FC3F0FEI07MF81NF01NF80FF8I03FE07MF81MFE,001FC3F0FEI07MF81NF81NF80FF8I03FE07MF81MFE,001FC3F0FEI07MF81NF80NFC0FF8I03FE07MF81MFE,I0FC3F0FCI07MF81NFC0NFC0FF8I03FE07MF81MFE,I07C3F0F8I07MF80NFC0NFC0FF8I03FE07MF81MFE,I03C3F0FJ07MF807MFC07MFC0FF8I03FE07MF81MFE,I01C3F0EJ07MF803MFC01MFC0FF8I03FE07MF81MFE,J0C3F0CJ07FCS0FFCM07FC0FF8I03FE07FCL01FF,J043F08J07FCS0FFCM07FC0FF8I03FE07FCL01FF,K03FL07FCS0FFCM07FC0FF8I03FE07FCL01FF,::::::K03FL07FCS0FFCM07FC0FF8I07FE07FCL01FF,K03FL07MF81NFC1NFC0NFE07MF81MFE,:K03EL07MF81NFC1NFC0NFE07MF81MFE,K03CL07MF81NFC1NFC0NFE07MF81MFE,K038L07MF81NF81NFC0NFE07MF81MFE,K03M03MF81NF81NFC0NFC03MF80MFE,K02M03MF81NF01NF80NFC01MF80MFE,K02N0MF81MFE01NF00NFI0MF803LFE,,:::::::::::::::^FS
		# 	^PW1000
		# 	^FO720,50^A0,40,40^FD{date}^FS
		# 	^FO108,35^A0,15,15^FDTM^FS
		# 	^FO350,35^A0,15,15^FDTM^FS

		# 	^FO30,15^GB910,435,5^FS
		# 	^FO30,110^GB910,70,5^FS
		# 	^FO30,245^GB910,70,5^FS
		# 	^FO30,380^GB910,70,5^FS
		# 	^FO30,447^GB475,70,5^FS
		# 	^FO500,310^GB2,205,5^FS

		# 	^FO40,130^A0,40,40^FDStyle^FS
		# 	^FO40,195^A0,40,40^FDPanel^FS
		# 	^FO40,267^A0,40,40^FDColour^FS
		# 	^FO40,335^A0,40,40^FDLay/Bundle No^FS
		# 	^FO40,403^A0,40,40^FDSize^FS
		# 	^FO40,470^A0,40,40^FDLot No^FS
		# 	^FO510,335^A0,40,40^FDShade^FS
		# 	^FO510,403^A0,40,40^FDQty^FS

		# 	^FO150,130^A0,40,40^FD: {item_name}^FS
		# 	^FO150,195^A0,40,40^FD: {item['part']}^FS
		# 	^FO150,269^A0,35,35^FD: {string_value}^FS
		# 	^FO280,335^A0,35,35^FD: {lay_no}/{item['bundle_no']}^FS
		# 	^FO150,405^A0,40,40^FD: {item['size']}^FS
		# 	^FO150,470^A0,40,40^FD: {lot_no}^FS
		# 	^FO610,335^A0,40,40^FD: {item['shade']}^FS
		# 	^FO610,403^A0,40,40^FD: {item['quantity']}^FS

		# 	^BY2,1,60
		# 	^FO510,455^BC^FD{item['hash_value']}^FS

		# 	^XZ"""
		# zpl += x
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
	if work_order:
		create_grn_entry(doc_name)
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
		colours.add(f"{item.colour}({json.loads(item.set_combination)['major_colour']})")
	colour_items = {}
	for colour in colours:
		for item in items:
			item_colour = f"{item.colour}({json.loads(item.set_combination)['major_colour']})"
			if item_colour == colour:
				if colour in colour_items:
					colour_items[colour].append(item)
				else:
					colour_items[colour] = [item]
	return colours,colour_items
	
@frappe.whitelist()
def get_created_date(creation):
	created_date = getdate(creation)
	return created_date.strftime("%d-%m-%Y")

@frappe.whitelist()
def update_cutting_plan(cutting_laysheet, check_cp = False):
	cls_doc = frappe.get_doc("Cutting LaySheet",cutting_laysheet)
	production_detail, incomplete_items_json, completed_items_json, version = frappe.get_value("Cutting Plan",cls_doc.cutting_plan,['production_detail',"incomplete_items_json","completed_items_json", "version"])
	ipd_doc = frappe.get_cached_doc("Item Production Detail",production_detail)
	incomplete_items = json.loads(incomplete_items_json)
	completed_items = json.loads(completed_items_json)
	if cls_doc.is_manual_entry:
		colours = []
		for item in cls_doc.cutting_laysheet_details:
			colours.append(item.colour)

		for item in cls_doc.cutting_laysheet_manual_items:
			if item.colour not in colours:
				frappe.throw(f"There is no detail for Colour {item.colour}")

	if version == "V2" or version == "V3":
		if not ipd_doc.is_set_item:
			alter_incomplete_items = {}
			for item in incomplete_items['items']:
				colour = item['attributes'][ipd_doc.packing_attribute]
				alter_incomplete_items[colour] = item['values']
			
			for item in cls_doc.cutting_laysheet_bundles:
				parts = item.part.split(",")
				set_combination = update_if_string_instance(item.set_combination)
				set_colour = set_combination['major_colour']
				qty = item.quantity
				for part in parts:
					alter_incomplete_items[set_colour][item.size][part] += qty	
			
			total_qty = completed_items['total_qty']
			for item in completed_items['items']:
				colour = item['attributes'][ipd_doc.packing_attribute]
				for val in item['values']:
					min = sys.maxsize
					for panel in alter_incomplete_items[colour][val]:
						if alter_incomplete_items[colour][val][panel] < min:
							min = alter_incomplete_items[colour][val][panel]
					
					if item['completed'] and min > 0 and check_cp:
						frappe.throw(f"Already {colour} was completed")			
					
					if not check_cp:		
						total_qty[val] += min
						item['values'][val] += min
						for panel in alter_incomplete_items[colour][val]:
							alter_incomplete_items[colour][val][panel] -= min
			if not check_cp:
				completed_items['total_qty'] = total_qty				
				for item in incomplete_items['items']:
					colour = item['attributes'][ipd_doc.packing_attribute]
					item['values'] = alter_incomplete_items[colour]
		else:
			stich_details = get_stich_details(ipd_doc)
			alter_incomplete_items = {}
			for item in incomplete_items['items']:
				set_combination = update_if_string_instance(item['item_keys'])
				colour = set_combination['major_colour']
				part = item['attributes'][ipd_doc.set_item_attribute]
				if alter_incomplete_items.get(colour):
					alter_incomplete_items[colour][part] = item['values']
				else:	
					alter_incomplete_items[colour] = {}
					alter_incomplete_items[colour][part] = item['values']
			for item in cls_doc.cutting_laysheet_bundles:
				parts = item.part.split(",")
				set_combination = update_if_string_instance(item.set_combination)
				major_part = set_combination['major_part']
				major_colour = set_combination['major_colour']
				d = {
					"major_colour": major_colour,
				}
				if set_combination.get('set_part'):
					major_part = set_combination['set_part']
					major_colour = set_combination['set_colour']
				d['major_part'] = major_part	

				qty = item.quantity
				for part in parts:
					try:
						alter_incomplete_items[d['major_colour']][d['major_part']][item.size][part] += qty
					except:
						secondary_part = stich_details[part]
						alter_incomplete_items[d['major_colour']][secondary_part][item.size][part] += qty
			
			total_qty = completed_items['total_qty']
			for item in completed_items['items']:
				set_combination = update_if_string_instance(item['item_keys'])
				colour = set_combination['major_colour']
				part = item['attributes'][ipd_doc.set_item_attribute]
				for val in item['values']:
					min = sys.maxsize
					for panel in alter_incomplete_items[colour][part][val]:
						if alter_incomplete_items[colour][part][val][panel] < min:
							min = alter_incomplete_items[colour][part][val][panel]
					
					if item['completed'] and min > 0 and check_cp:
						txt = colour + "-" + part
						frappe.throw(f"Already {txt} was completed")		
					
					if not check_cp:
						total_qty[val] += min
						item['values'][val] += min
						for panel in alter_incomplete_items[colour][part][val]:
							alter_incomplete_items[colour][part][val][panel] -= min		
			
			if not check_cp:
				completed_items["total_qty"] = total_qty
				for item in incomplete_items['items']:
					set_combination = update_if_string_instance(item['item_keys'])
					colour = set_combination['major_colour']
					part = item['attributes'][ipd_doc.set_item_attribute]
					item['values'] = alter_incomplete_items[colour][part]
		
		cloth = {}
		accessory = {}
		accessory_cloth = {}
		cp_cloth = []
		cp_accessory = []
		for item in cls_doc.cutting_laysheet_details:
			key = (item.colour, item.cloth_type, item.dia)
			cloth.setdefault(key,0)
			cloth[key] += item.weight - item.balance_weight
		for item in cls_doc.cutting_laysheet_accessory_details:
			key = (item.accessory, item.colour, item.cloth_type, item.dia)
			accessory.setdefault(key,0)
			accessory[key] += item.weight
			key = (item.colour, item.cloth_type, item.dia)
			accessory_cloth.setdefault(key,0)
			accessory_cloth[key] += item.weight

		cp_doc = frappe.get_doc("Cutting Plan",cls_doc.cutting_plan)

		if check_cp:
			for item in cp_doc.cutting_plan_cloth_details:
				cp_cloth.append((item.colour, item.cloth_type, item.dia))

			for item in cp_doc.cutting_plan_accessory_details:
				cp_accessory.append((item.accessory, item.colour, item.cloth_type, item.dia))

			for key in cloth:
				colour, cloth_type, dia = key
				if key not in cp_cloth:
					frappe.throw(f"No cloth is mentioned with {cloth_type}, {colour}-{dia}")
			
			for key in accessory:
				accessory, colour, cloth_type, dia = key
				if key not in cp_accessory:
					frappe.throw(f"Accessory {accessory} is not mentioned with {cloth_type}, {colour}-{dia}")

		if not check_cp:
			for item in cp_doc.cutting_plan_cloth_details:
				key = (item.colour, item.cloth_type, item.dia)
				if key in cloth:
					item.used_weight += cloth[key]
					item.balance_weight = item.weight - item.used_weight
				if key in accessory_cloth:
					item.used_weight += accessory_cloth[key]
					item.balance_weight = item.weight - item.used_weight	

			for item in cp_doc.cutting_plan_accessory_details:
				key = (item.accessory, item.colour, item.cloth_type, item.dia)
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
					check = False
					for val in x['values']:
						if item.size == val:
							for part in parts:
								condition = True
								if completed_items['is_set_item']:
									condition = part in incomplete_items[ipd_doc.stiching_attribute][x['attributes'][ipd_doc.set_item_attribute]]
								if condition:
									check = True
									x['values'][val][part] += item.quantity
					if check:
						break
		
		stitching_combination = get_stitching_combination(ipd_doc)
		set_item = ipd_doc.is_set_item
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

			if check and min != sys.maxsize:
				for x in completed_items['items']:
					total_qty = 0
					condition3 = True
					if set_item:
						condition3 = x['attributes'][ipd_doc.set_item_attribute] == part
					if x['attributes'][ipd_doc.packing_attribute] == item[1] and condition3:
						if x['completed'] and check_cp:
							txt = item[1]
							if set_item:
								txt += "-" + part
							frappe.throw(f"Already {txt} was completed")
						if not check_cp:
							x['values'][item[0]] += min
							completed_items['total_qty'][item[0]] += min
							total_qty += x['values'][item[0]]
							break	
					if not check_cp:
						if total_qty != 0:
							x['total_qty'] = total_qty

				if not check_cp:
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
		cp_cloth = []
		cp_accessory = []
		cp_doc = frappe.get_doc("Cutting Plan",cls_doc.cutting_plan)
		for item in cls_doc.cutting_laysheet_details:
			key = (item.colour, item.cloth_type, item.dia)
			cloth.setdefault(key,0)
			cloth[key] += item.weight - item.balance_weight

		for item in cls_doc.cutting_laysheet_accessory_details:
			key = (item.accessory, item.colour, item.cloth_type, item.dia)
			accessory.setdefault(key,0)
			accessory[key] += item.weight

		if check_cp:
			for item in cp_doc.cutting_plan_cloth_details:
				cp_cloth.append((item.colour, item.cloth_type, item.dia))

			for item in cp_doc.cutting_plan_accessory_details:
				cp_accessory.append((item.colour, item.cloth_type, item.dia))

			for key in cloth:
				colour, cloth_type, dia = key
				if key not in cp_cloth:
					frappe.throw(f"No cloth is mentioned with {cloth_type}, {colour}-{dia}")
			
			for key in accessory:
				colour, cloth_type, dia = key
				if key not in cp_accessory:
					frappe.throw(f"No accessory is mentioned with {cloth_type}, {colour}-{dia}")

		if not check_cp:
			for item in cp_doc.cutting_plan_cloth_details:
				key = (item.colour, item.cloth_type, item.dia)
				if key in cloth:
					item.used_weight += cloth[key]
					item.balance_weight = item.weight - item.used_weight
				if key in accessory:
					item.used_weight += accessory[key]
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
	select_attributes = update_if_string_instance(select_attributes)
	cm_doc = frappe.get_doc("Cutting Marker",cutting_marker)
	panels = cm_doc.calculated_parts.split(",")
	ipd = frappe.get_value("Cutting Plan",cm_doc.cutting_plan,"production_detail")
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	stich_attr_value = ipd_doc.stiching_major_attribute_value
	major_attr_value = ipd_doc.major_attribute_value
	select_vals = select_attributes['colour']
	is_same_packing_attr = ipd_doc.is_same_packing_attribute
	part_colours = {}
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
		part_set_colours = {}
		index = -1
		last_colour = None
		for row in ipd_doc.set_item_combination_details:
			if row.index != index:
				part_colours[row.attribute_value] = {}
				index = row.index
				last_colour = row.attribute_value
			part_colours[last_colour][row.set_item_attribute_value] = row.attribute_value 		
			part_set_colours.setdefault(row.set_item_attribute_value, set())
			part_set_colours[row.set_item_attribute_value].add(row.attribute_value)

		if len(marker_parts) > 1:
			inputs.append({"fieldname":"major_part", "fieldtype":"Data", "label":"Major Part", "default": major_attr_value})
			inputs.append({"fieldname":"major_panel", "fieldtype":"Data", "label":"Major Panel", "default": default[major_attr_value]})
			inputs.append({"fieldname":"major_colour", "fieldtype":"Select", "label":"Major Colour", "options":select_vals})
		else:
			if marker_parts[0] == major_attr_value:
				inputs.append({"fieldname":"major_part", "fieldtype":"Data", "label":"Major Part", "default": major_attr_value})		
				inputs.append({"fieldname":"major_panel", "fieldtype":"Data", "label":"Major Panel", "default": default[marker_parts[0]]})
				if is_same_packing_attr:
					inputs.append({"fieldname":"major_colour", "fieldtype":"Data", "label":"Major Colour", "default":colour})
				else:
					inputs.append({"fieldname":"major_colour", "fieldtype":"Select", "label":"Major Colour", "options":list(part_set_colours[major_attr_value])})
			else:
				inputs.append({"fieldname":"major_part", "fieldtype":"Data", "label":"Major Part", "default": major_attr_value})
				inputs.append({"fieldname":"major_panel", "fieldtype":"Data", "label":"Major Panel", "default": default[major_attr_value]})
				if is_same_packing_attr:
					v = []
					for c in part_colours:
						if part_colours[c][marker_parts[0]] == colour:
							v.append(part_colours[c][major_attr_value])
					if len(v) == 1:
						inputs.append({"fieldname":"major_colour", "fieldtype":"Data", "label":"Major Colour", "default": v[0]})
					else:
						inputs.append({"fieldname":"major_colour", "fieldtype":"Select", "label":"Major Colour", "options": v})
					inputs.append({"fieldname":"set_part", "fieldtype":"Data", "label":"Set Part", "default": marker_parts[0]})
					inputs.append({"fieldname":"set_panel", "fieldtype":"Data", "label":"Set Panel", "default": default[marker_parts[0]]})
					inputs.append({"fieldname":"set_colour", "fieldtype":"Data", "label":"Set Colour", "default":colour})
				else:
					inputs.append({"fieldname":"major_colour", "fieldtype":"Select", "label":"Major Colour", "options":list(part_set_colours[major_attr_value])})
					inputs.append({"fieldname":"set_part", "fieldtype":"Data", "label":"Set Part", "default": marker_parts[0]})
					inputs.append({"fieldname":"set_panel", "fieldtype":"Data", "label":"Set Panel", "default": default[marker_parts[0]]})
					inputs.append({"fieldname":"set_colour", "fieldtype":"Select", "label":"Set Colour", "options":list(part_set_colours[marker_parts[0]])})
	else:
		if ipd_doc.is_same_packing_attribute or stich_attr_value in panels:
			inputs.append({"fieldname":"major_panel", "fieldtype":"Data", "label":"Major Panel", "default": stich_attr_value})
			inputs.append({"fieldname":"major_colour", "fieldtype":"Data", "label":"Major Colour", "default":colour})
		else:
			inputs.append({"fieldname":"major_panel", "fieldtype":"Data", "label":"Major Panel", "default": stich_attr_value})
			inputs.append({"fieldname":"major_colour", "fieldtype":"Select", "label":"Major Colour", "options":select_vals})

	inputs.append({"fieldname":"is_same_packing_attribute","fieldtype":"Check","label":"Is Same Packing Attribute","hidden":True,"default":is_same_packing_attr})	
	inputs.append({"fieldname":"is_set_item","fieldtype":"Check","label":"Is Set Item","hidden":True,"default":ipd_doc.is_set_item})	
	return {
		"input_fields":inputs, 
		"part_colours": part_colours if part_colours else None
	}	

@frappe.whitelist()
def revert_labels(doc_name):
	cls_doc = frappe.get_doc("Cutting LaySheet", doc_name)
	is_moved_list = frappe.db.sql(
		f"""
			SELECT name FROM `tabCutting LaySheet Bundle` WHERE parent = '{doc_name}' AND is_moved = 1
		""", as_list = True
	)
	if len(is_moved_list) > 0:
		frappe.throw("Some panels are moved, can't revert the process")

	acc_moved_list = frappe.db.sql(
		f"""
			SELECT name FROM `tabCutting LaySheet Accessory Detail` WHERE parent = '{doc_name}' AND moved_weight > 0
		""", as_list=True
	)

	if len(acc_moved_list) > 0:
		frappe.throw("Some accessories are moved, can't revert the process")

	cls_doc.status = "Bundles Generated"
	if cls_doc.goods_received_note:
		grn_doc = frappe.get_doc("Goods Received Note", cls_doc.goods_received_note)
		grn_doc.cancel()
	cls_doc.goods_received_note =  None
	cls_doc.reverted = 1
	cls_doc.save()
	from production_api.production_api.doctype.cutting_plan.cutting_plan import calculate_laysheets
	calculate_laysheets(cls_doc.cutting_plan)

@frappe.whitelist()
def create_grn_entry(doc_name):
	cls_doc = frappe.get_doc("Cutting LaySheet", doc_name)
	wo, ipd = frappe.get_value("Cutting Plan", cls_doc.cutting_plan, ["work_order", "production_detail"])
	if not wo:
		return
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	panel_qty_dict = {}
	for item in ipd_doc.stiching_item_details:
		panel_qty_dict[item.stiching_attribute_value] = item.quantity

	cls_panels = {}
	for row in cls_doc.cutting_laysheet_bundles:
		combination = update_if_string_instance(row.set_combination)
		set_combination = {} 
		set_combination['major_colour'] = combination.get("major_colour")
		if combination.get('major_part'):
			set_combination['major_part'] = combination.get('major_part')

		parts = row.part.split(",")
		for part in parts:
			part = part.strip()
			set_comb_tuple = tuple(sorted(set_combination.items()))
			key = (row.size, row.colour, part, set_comb_tuple)
			qty = row.quantity * panel_qty_dict[part]
			if key in cls_panels:
				cls_panels[key]["qty"] += qty
			else:
				cls_panels[key] = {
					"qty":qty,
					"set_combination": set_combination,
				}
	cls_cloths = {}
	for row in cls_doc.cutting_laysheet_accessory_details:
		set_combination = {}
		cls_cloths.setdefault(row.cloth_item_variant, 0)
		cls_cloths[row.cloth_item_variant] += row.weight

	item_name, ipd = frappe.get_value("Lot", cls_doc.lot, ["item","production_detail"])
	primary, pack_attr, stich_attr, stich_stage, dependent_attr = frappe.get_value("Item Production Detail", ipd, ['primary_item_attribute', "packing_attribute", "stiching_attribute", "stiching_in_stage", "dependent_attribute"])
	
	wo_doc = frappe.get_doc("Work Order", wo)
	new_doc = frappe.new_doc("Goods Received Note")
	new_doc.update({
		"against": "Work Order",
		"against_id": wo,
		"posting_date": nowdate(),
		"posting_time": now(),
		"delivery_date": nowdate(),
		"is_internal_unit": wo_doc.is_internal_unit,
		"is_manual_entry": wo_doc.is_manual_entry,
		"delivery_location": wo_doc.supplier,
		"delivery_location_name": wo_doc.supplier_name,
		"supplier": wo_doc.supplier,
		"supplier_name": wo_doc.supplier_name,
		"vehicle_no":"NA",
		"supplier_document_no":"NA",
		"supplier_address": wo_doc.supplier_address,
		"supplier_address_display": wo_doc.supplier_address_details,
		"delivery_address": wo_doc.supplier_address,
		"deliverey_address_display": wo_doc.supplier_address_details,
		"cutting_laysheet": doc_name
	})
	new_doc.flags.from_cls = True
	new_doc.total_quantity = 0
	new_doc.save()
	total_received_qty = 0
	received_type = frappe.db.get_single_value("Stock Settings","default_received_type")
	for key, details in cls_panels.items():		
		size, colour, panel, set_comb_tuple = key
		attributes = {
			primary: size,
			pack_attr: colour,
			stich_attr: panel,
			dependent_attr: stich_stage
		}
		variant = get_or_create_variant(item_name, attributes)
		set_combination = update_if_string_instance(details['set_combination'])
		for item in new_doc.items:
			item_set = update_if_string_instance(item.set_combination)
			if item.item_variant == variant and item_set == set_combination:
				item.quantity += details['qty']
				received_types = update_if_string_instance(item.received_types)
				total_received_qty += details['qty']
				if received_type in received_types:
					received_types[received_type] += details['qty']
				else:
					received_types[received_type] = details['qty']
				item.received_types = received_types	
				break

	for cloth, weight in cls_cloths.items():
		for item in new_doc.items:
			if item.item_variant == cloth:
				item.quantity += weight
				received_types = update_if_string_instance(item.received_types)
				total_received_qty += weight
				if received_type in received_types:
					received_types[received_type] += weight
				else:
					received_types[received_type] = weight
				item.received_types = received_types	
				break

	new_doc.total_received_quantity =  total_received_qty
	deliverables_dict = {}
	for item in cls_doc.cutting_laysheet_details:
		if item.cloth_item_variant in deliverables_dict:
			deliverables_dict[item.cloth_item_variant] += item.used_weight	
		else:
			deliverables_dict[item.cloth_item_variant] = item.used_weight	
	
	for item in cls_doc.cutting_laysheet_accessory_details:
		if item.cloth_item_variant in deliverables_dict:
			deliverables_dict[item.cloth_item_variant] += item.weight	
		else:
			deliverables_dict[item.cloth_item_variant] = item.weight	
	
	items = []
	row_index = 0
	for variant in deliverables_dict:
		item_name = frappe.get_cached_value("Item Variant", variant, "item")
		uom = frappe.get_cached_value("Item", item_name, "default_unit_of_measure")
		items.append({
			"item_variant": variant,
			"quantity": deliverables_dict[variant],
			"uom": uom,
			"valuation_rate": 0.0,
			"table_index": 0,
			"row_index": row_index,
			"set_combination": {},
		})
		row_index += 1
	new_doc.set("grn_deliverables", items)
	new_doc.save()
	new_doc.submit()
	frappe.db.sql(
		"""
			UPDATE `tabCutting LaySheet` SET goods_received_note = %s WHERE name = %s
		""", (new_doc.name, doc_name, )
	)

@frappe.whitelist()
def cancel_laysheet(doc_name):
	doc = frappe.get_doc("Cutting LaySheet", doc_name)
	doc.status = "Cancelled"
	if doc.goods_received_note:
		grn_doc = frappe.get_doc("Goods Received Note", doc.goods_received_note)
		grn_doc.cancel()
	doc.goods_received_note =  None
	doc.save()

@frappe.whitelist()
def update_label_print_status(doc_name):
	doc = frappe.get_doc("Cutting LaySheet", doc_name)
	wo = frappe.get_value("Cutting Plan", doc.cutting_plan, "work_order")
	if wo:
		create_grn_entry(doc_name)
	doc.status = "Label Printed"
	doc.reverted = 0
	doc.save()
	from production_api.production_api.doctype.cutting_plan.cutting_plan import calculate_laysheets
	calculate_laysheets(doc.cutting_plan)

@frappe.whitelist()
def get_primary_values(cutting_laysheet):
	lot = frappe.get_value("Cutting LaySheet", cutting_laysheet, "lot")
	ipd = frappe.get_value("Lot", lot, "production_detail")
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	primary_values = get_ipd_primary_values(ipd)
	return primary_values