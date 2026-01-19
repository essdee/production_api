# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from production_api.utils import get_variant_attr_details, update_if_string_instance


class EssdeeQualityInspection(Document):
	def onload(self):
		d = {
			"colours": [],
			"sizes": [],
		}
		for row in self.essdee_quality_inspection_colours:
			d['colours'].append({
				"colour": row.colour,
				"selected": True if row.selected else False
			})
		for row in self.essdee_quality_inspection_sizes:
			d['sizes'].append({
				"size": row.size,
				"selected": True if row.selected else False
			})	
		self.set_onload("colour_size_data", d)

	def before_submit(self):
		if self.result not in ['Pass', "Fail", "Hold"]:
			frappe.thow("Please set the result")

		self.inspector = frappe.session.user
		self.inspector_name = frappe.get_value("User", frappe.session.user, "full_name")
		
	def before_validate(self):
		if self.offer_qty == 0:
			frappe.throw("Offer Qty Cannot be Zero")

		d = get_max_minor_defect_allowed(self.checking_level, self.offer_qty, self.major_aql_level, self.minor_aql_level)
		self.sample_piece_count = d['sample']
		self.major_defect_maximum_allowed = d['major_allowed']
		self.minor_defect_maximum_allowed = d['minor_allowed']
		if self.get("colour_and_size_data"):
			colours_and_size = update_if_string_instance(self.colour_and_size_data)
			self.set("essdee_quality_inspection_colours", colours_and_size['colours'])
			self.set('essdee_quality_inspection_sizes', colours_and_size['sizes'])

		check = False
		if not self.result and not self.calculated_result:
			check = True
		elif self.result == self.calculated_result:
			check = True

		if check:
			if self.major_defect_found <= self.major_defect_maximum_allowed and self.minor_defect_found <= self.minor_defect_maximum_allowed:
				self.result = 'Pass'
				self.calculated_result = 'Pass'
			else:
				self.result = 'Fail'
				self.calculated_result = 'Fail'

		wo_doc = frappe.get_doc(self.against, self.against_id)
		selected_colours = []
		for row in self.essdee_quality_inspection_colours:
			if row.selected == 1:
				selected_colours.append(row.colour)
		selected_sizes = []		
		for row in self.essdee_quality_inspection_sizes:
			if row.selected == 1:
				selected_sizes.append(row.size)
				
		ipd = wo_doc.production_detail
		ipd_fields = ['packing_attribute', 'is_set_item', 'set_item_attribute', 'major_attribute_value', 'primary_item_attribute']
		colour, set_item, set_attr, major_attr, primary = frappe.get_value("Item Production Detail", ipd, ipd_fields)
		order_qty = 0
		for row in wo_doc.work_order_calculated_items: 
			if row.delivered_quantity == 0:
				continue
			attrs = get_variant_attr_details(row.item_variant)
			colour_val = attrs[colour]
			primary_val = attrs[primary]
			if set_item:
				if attrs[set_attr] != major_attr:
					set_comb = update_if_string_instance(row.set_combination)
					colour_val = colour_val + "("+ set_comb['major_colour'] +")"
				if colour_val in selected_colours and primary_val in selected_sizes:
					order_qty += row.delivered_quantity
			else:
				if colour_val in selected_colours and primary_val in selected_sizes:
					order_qty += row.delivered_quantity

		self.order_qty = order_qty			

@frappe.whitelist()
def get_max_minor_defect_allowed(level, offer_qty: int, major_aql_level, minor_aql_level):
	sample_piece_count = 0
	major_defect_allowed = 0
	minor_defect_allowed = 0
	if level == 'Level 1':
		major_doc = frappe.get_doc("AQL Level", major_aql_level)
		for row in major_doc.aql_level_limit_details:
			if row.min_qty <= offer_qty and row.max_qty >= offer_qty:
				major_defect_allowed = row.level_1
				sample_piece_count = row.sample_qty_level_1
				break
		minor_doc = frappe.get_doc("AQL Level", minor_aql_level)
		for row in minor_doc.aql_level_limit_details:
			if row.min_qty <= offer_qty and row.max_qty >= offer_qty:
				minor_defect_allowed = row.level_1
				break	
	else:
		major_doc = frappe.get_doc("AQL Level", major_aql_level)
		for row in major_doc.aql_level_limit_details:
			if row.min_qty <= offer_qty and row.max_qty >= offer_qty:
				major_defect_allowed = row.level_2
				sample_piece_count = row.sample_qty_level_2
				break
		minor_doc = frappe.get_doc("AQL Level", minor_aql_level)
		for row in minor_doc.aql_level_limit_details:
			if row.min_qty <= offer_qty and row.max_qty >= offer_qty:
				minor_defect_allowed = row.level_2
				break	
	return {
		"sample": sample_piece_count,
		"major_allowed": major_defect_allowed,
		"minor_allowed": minor_defect_allowed,
	}		

@frappe.whitelist()
def get_against_details(against, against_id):
	colours, sizes = fetch_colours_and_sizes(against_id)
	supplier, lot, item = frappe.get_value(against, against_id, ['supplier', 'lot', 'item'])
	res = frappe.db.sql(
		f"""
			SELECT sum(delivered_quantity) as order_qty FROM `tabWork Order Calculated Item` 
			WHERE parent = {frappe.db.escape(against_id)}
		""", as_dict=True
	)
	return {
		"colours": colours,
		"sizes": sizes,
		"supplier": supplier,
		"lot": lot,
		"item": item,
		"order_qty": res[0]['order_qty']
	}

def fetch_colours_and_sizes(work_order):
	wo_doc = frappe.get_doc("Work Order", work_order)
	colours = []
	sizes = []
	selected_colour_and_sizes = []
	ipd = wo_doc.production_detail
	ipd_fields = ['primary_item_attribute', 'packing_attribute', 'is_set_item', 'set_item_attribute', 'major_attribute_value']
	size, colour, set_item, set_attr, major_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	for row in wo_doc.work_order_calculated_items: 
		if row.delivered_quantity == 0:
			continue
		attrs = get_variant_attr_details(row.item_variant)
		if set_item:
			colour_val = attrs[colour]
			if attrs[set_attr] != major_attr:
				set_comb = update_if_string_instance(row.set_combination)
				colour_val = colour_val + "("+ set_comb['major_colour'] +")"
			if colour_val not in selected_colour_and_sizes:
				colours.append({
					"colour": colour_val,
					"selected": False,
				})	
				selected_colour_and_sizes.append(colour_val)
		else:
			if attrs[colour] not in selected_colour_and_sizes:
				colours.append({
					"colour": attrs[colour],
					"selected": False,
				})	
				selected_colour_and_sizes.append(attrs[colour])

		if attrs[size] not in selected_colour_and_sizes:
			sizes.append({
				"size": attrs[size],
				"selected": False,
			})	
			selected_colour_and_sizes.append(attrs[size])
	return colours, sizes				

@frappe.whitelist()
def get_default_aql_level():
	single_doc = frappe.get_single("MRP Settings")
	return {
		"major": single_doc.default_major_aql_level,
		"minor": single_doc.default_minor_aql_level
	}