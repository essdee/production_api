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
		items2 = fetch_group_marker_details(self.calculated_parts, self.cutting_marker_groups) 
		details = {
			"cutting_marker_ratios": items,
			"cutting_marker_groups": items2,
		}	
		self.set_onload("marker_detail",details)

	def autoname(self):
		self.naming_series = "CM-.YY..MM.-.{#####}."

	def before_submit(self):
		if not self.length or not self.width:
			frappe.throw("Enter the Values for Length and Width")
			
		if self.version == "V3" and len(self.cutting_marker_groups) == 0:
			items = []
			for part in self.calculated_parts.split(","):
				part = part.strip()
				items.append({"group_panels": part})
			self.set("cutting_marker_groups", items)	

	def before_validate(self):
		if self.get("marker_details"):
			marker_details = self.marker_details['ratio_items']
			items = []
			if self.selected_type == "Manual":
				for item in marker_details:
					ratio = round(item['ratio'], 1)
					str_num = str(ratio)
					if '.' in str_num:
						precision = int(str_num.split('.')[1]) % 10
						if not(precision == 5 or precision == 0):
							frappe.throw("Only 0.5 addition is acceptable")
					items.append({
						"size":item['size'],
						"panel":item['panel'],
						"ratio":ratio,
					})
			else:
				if self.calculated_parts:
					panels = self.calculated_parts.split(",")
					for item in marker_details:
						ratio = round(item['ratio'],1)
						str_num = str(ratio)
						if '.' in str_num:
							precision = int(str_num.split('.')[1]) % 10
							if not(precision == 5 or precision == 0):
								frappe.throw("Only 0.5 increment is acceptable")
						for panel in panels:
							items.append({
								"size":item['size'],
								"panel":panel,
								"ratio": ratio
							})
			self.set("cutting_marker_ratios", items)		

			group_items = self.marker_details['group_items']
			items2 = []
			for item in group_items:
				item['selected'].sort()
				selected = ",".join(item['selected'])
				if selected:
					items2.append({
						"group_panels":selected,
					})
			self.set("cutting_marker_groups", items2)	

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

def fetch_group_marker_details(calculated_parts, cutting_marker_groups):
	options = []
	items = []
	if calculated_parts:
		panels = calculated_parts.split(",")
		for panel in panels:
			options.append({ "option": panel, "id": panel })
		index = 0
		for item in cutting_marker_groups:
			panels = item.group_panels.split(",")
			default_list = []
			for panel in panels:
				default_list.append(panel)

			items.append({
				"id": index,
				"options": options,
				"setDefault":True,
				"defaultList": default_list,
				"selected": panels,
			})
			index += 1
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

@frappe.whitelist()
def get_panels_and_size(lot, cutting_plan):
	ipd = frappe.get_value("Lot",lot,"production_detail")
	primary_values = get_ipd_primary_values(ipd)
	panels = calculate_parts(cutting_plan)
	return {
		"sizes": primary_values,
		"panels": panels,
	}