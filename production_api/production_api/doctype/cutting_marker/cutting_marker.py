# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe, json
from six import string_types
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_attribute_details
from production_api.essdee_production.doctype.lot.lot import get_ipd_primary_values

class CuttingMarker(Document):
	def autoname(self):
		self.naming_series = "CM-.YY..MM.-.{#####}."

	def before_validate(self):
		count = 0
		for item in self.cutting_marker_ratios:
			count += item.ratio
		if count == 0:
			frappe.throw("The Sum of ratios should not be Zero")	

@frappe.whitelist()
def get_primary_attributes(lot):
	ipd = frappe.get_value("Lot",lot,"production_detail")
	primary_values = get_ipd_primary_values(ipd)
	primary_attributes = []
	for attr in primary_values:
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
	for item in ipd_doc.stiching_item_details:
		attribute_list.append({
			"part": item.stiching_attribute_value,
		})

	cm_doc = frappe.get_doc("Cutting Marker", doc_name)
	cm_doc.set("cutting_marker_parts",attribute_list)
	cm_doc.save()		