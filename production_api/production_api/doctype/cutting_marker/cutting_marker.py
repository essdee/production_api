# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe, json
from six import string_types
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_attribute_details
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values

class CuttingMarker(Document):
	def onload(self):
		items = fetch_marker_details(self.cutting_marker_ratios, self.selected_type)
		self.set_onload("marker_ratio_detail",items)

	def autoname(self):
		self.naming_series = "CM-.YY..MM.-.{#####}."

	def before_validate(self):
		if self.get("marker_details"):
			items = []
			if self.selected_type == "Manual":
				for item in self.marker_details:
					ratio = round(item['ratio'], 1)
					str_num = str(ratio)
					if '.' in str_num:
						precision = int(str_num.split('.')[1]) % 10
						if precision != 5 or precision != 0:
							frappe.throw("Only 0.5 addition is acceptable")
					items.append({
						"size":item['size'],
						"panel":item['panel'],
						"ratio":ratio,
					})
			else:
				panels = self.calculated_parts.split(",")
				for item in self.marker_details:
					ratio = round(item['ratio'],1)
					str_num = str(ratio)
					if '.' in str_num:
						precision = int(str_num.split('.')[1]) % 10
						if precision != 5 or precision != 0:
							frappe.throw("Only 0.5 increment is acceptable")
					for panel in panels:
						items.append({
							"size":item['size'],
							"panel":panel,
							"ratio": ratio
						})
			self.set("cutting_marker_ratios", items)		

def fetch_marker_details(marker_details, selected_type):
	items = []
	if selected_type == "Manual":
		for item in marker_details:
			items.append({
				"size":item.size,
				"panel":item.panel,
				"ratio":round(item.ratio,1),
			})
	else:
		sizes = []		
		for item in marker_details:
			if item.size not in sizes:
				sizes.append(item.size)
				items.append({
					"size":item.size,
					"panel":item.panel,
					"ratio":item.ratio,
				})
	return items			
	
@frappe.whitelist()
def get_primary_attributes(lot, selected_value, panels):
	ipd = frappe.get_value("Lot",lot,"production_detail")
	primary_values = get_ipd_primary_values(ipd)
	primary_attributes = []
	if isinstance(panels, string_types):
		panels = json.loads(panels)
	for attr in primary_values:
		if selected_value == "Machine":
			primary_attributes.append({
				"size":attr,
				"ratio":0,
			})
		else:
			for panel in panels:
				primary_attributes.append({
					"size":attr,
					"panel":panel,
					"ratio":0,
				})
	return primary_attributes	

@frappe.whitelist()
def calculate_parts(cutting_plan):
	ipd = frappe.get_value("Cutting Plan", cutting_plan,"production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail",ipd)
	attribute_list = []
	for item in ipd_doc.stiching_item_details:
		attribute_list.append({
			"part": item.stiching_attribute_value,
		})
	return attribute_list