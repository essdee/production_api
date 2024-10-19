# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe, json
from six import string_types
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_attribute_details

class CuttingMarker(Document):
	def before_validate(self):
		count = 0
		for item in self.cutting_marker_ratios:
			count += item.ratio
		if count == 0:
			frappe.throw("The Sum of ratios should not be Zero")	

@frappe.whitelist()
def get_primary_attributes(item):
	item_attr_details = get_attribute_details(item)
	primary_attributes = []
	if item_attr_details['primary_attribute']:
		for attr in item_attr_details['primary_attribute_values']:
			primary_attributes.append({
				"size":attr,
				"ratio":0,
			})
	return primary_attributes	

@frappe.whitelist()
def calculate_parts(ratios, cutting_plan, doc_name):
	if isinstance(ratios,string_types):
		ratios = json.loads(ratios)

	ipd = frappe.get_value("Cutting Plan", cutting_plan,"production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail",ipd)
	attribute_list = []
	for ratio in ratios:
		for item in ipd_doc.stiching_item_details:
			attribute_list.append({
				"part": item.stiching_attribute_value,
				"size": ratio['size'],
				"quantity": ratio['ratio'] * item.quantity
			})

	cm_doc = frappe.get_doc("Cutting Marker", doc_name)
	cm_doc.set("cutting_marker_parts",attribute_list)
	cm_doc.save()		