# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import math
import frappe,json
from itertools import groupby
from six import string_types
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_or_create_variant

class CuttingLaySheet(Document):
	def onload(self):
		self.set_onload("item_details",self.cutting_laysheet_details)

	def before_validate(self):
		if self.get('item_details'):
			items = save_item_details(self.item_details, self.cutting_plan)
			self.set("cutting_laysheet_details", items)

		if self.is_new():
			cut_plan_doc = frappe.get_doc("Cutting Plan",self.cutting_plan)	
			self.lay_no = cut_plan_doc.lay_no + 1
			cut_plan_doc.lay_no = self.lay_no
			cut_plan_doc.save()

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
def get_parts(cutting_plan):
	ipd = frappe.get_value("Cutting Plan",cutting_plan,"production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	part_list = []
	for item in ipd_doc.stiching_item_details:
		part_list.append(item.stiching_attribute_value)
	return part_list	

@frappe.whitelist()
def get_cut_sheet_data(doc_name,cutting_marker,item_details,items, max_plys:int):
	if isinstance(items, string_types):
		items = json.loads(items)
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)	
	max_plys = max_plys + (max_plys/100) * 10
	bundle_no = 0
	cm_doc = frappe.get_doc("Cutting Marker",cutting_marker)
	cut_sheet_data = []
	for item in item_details:
		for cm_item in cm_doc.cutting_marker_ratios:
			no_of_marks = cm_item.ratio
			max_grouping = int(max_plys/item['no_of_bits'])
			total_bundles = math.ceil(no_of_marks/max_grouping)
			avg_grouping = no_of_marks/total_bundles

			minimum = math.floor(avg_grouping)
			maximum = math.ceil(avg_grouping)

			maximum_count = no_of_marks - (total_bundles * minimum)
			minimum_count = total_bundles - maximum_count
	
			temp = bundle_no 
			groups = []
			for part,group in items.items():
				if group in groups:
					bundle_no = temp
				else:
					groups.append(group)
					temp = bundle_no
					bundle_no = temp	

				for j in range(maximum_count):
					bundle_no = bundle_no + 1
					cut_sheet_data.append({
						"size":cm_item.size,
						"colour":item['colour'],
						"shade":item['shade'],
						"bundle_no":bundle_no,
						"part":part,
						"quantity":maximum * item['no_of_bits'],
					})	
				for j in range(minimum_count):
					bundle_no = bundle_no + 1
					cut_sheet_data.append({
						"size":cm_item.size,
						"colour":item['colour'],
						"shade":item['shade'],
						"bundle_no":bundle_no,
						"part":part,
						"quantity":minimum * item['no_of_bits'],
					})		
			temp = bundle_no	
	
	dictionary = {}
	for items in cut_sheet_data:
		if dictionary.get(items['bundle_no']):
			item = dictionary[items['bundle_no']]
			part = item['part']
			item['part'] = part + ", " + items['part']
			dictionary[items['bundle_no']] = item
		else:	
			dictionary[items['bundle_no']] = items

	cut_sheet_data = []
	for key, values in dictionary.items():
		cut_sheet_data.append(values)


	doc = frappe.get_doc("Cutting LaySheet", doc_name)
	doc.set("cutting_laysheet_bundles", cut_sheet_data)
	doc.save()
