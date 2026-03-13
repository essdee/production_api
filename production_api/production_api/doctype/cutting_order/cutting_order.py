# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
import json
import copy
from frappe.model.document import Document


class CuttingOrder(Document):
	def autoname(self):
		self.naming_series = "CTO-.YY..MM.-.{#####}."

	def onload(self):
		if self.items_json:
			try:
				self.set_onload('cutting_order_items', json.loads(self.items_json))
			except (json.JSONDecodeError, TypeError):
				pass

	def validate(self):
		if not self.cutting_order_detail:
			frappe.throw("Cutting Order Detail is required")

	def before_submit(self):
		if not self.items_json:
			frappe.throw("Please enter item quantities before submitting")

		data = json.loads(self.items_json)
		if not any(
			qty > 0
			for item in data.get('items', [])
			for qty in item.get('quantities', {}).values()
		):
			frappe.throw("At least one quantity must be greater than zero")

		# Build panels dict from Cutting Order Detail's stiching_item_details
		cod = frappe.get_doc("Cutting Order Detail", self.cutting_order_detail)
		if cod.is_set_item:
			# panels: {part: {panel: 0, ...}, ...}
			panels = {}
			for row in cod.stiching_item_details:
				panels.setdefault(row.set_item_attribute_value, {})
				panels[row.set_item_attribute_value][row.stiching_attribute_value] = 0
		else:
			# panels: {panel: 0, ...}
			panels = {}
			for row in cod.stiching_item_details:
				panels[row.stiching_attribute_value] = 0

		# Completed: all quantities zeroed, completed=False
		completed = copy.deepcopy(data)
		for item in completed['items']:
			for size in item['quantities']:
				item['quantities'][size] = 0
			item['completed'] = False
			item['completed_date'] = None

		# Incomplete: each quantity → panel dict (tracking per-panel cuts remaining)
		incomplete = copy.deepcopy(data)
		for item in incomplete['items']:
			if cod.is_set_item:
				part = item.get('part', '')
				panel_dict = panels.get(part, {})
			else:
				panel_dict = panels
			for size in item['quantities']:
				item['quantities'][size] = copy.deepcopy(panel_dict)

		self.completed_items_json = json.dumps(completed)
		self.incomplete_items_json = json.dumps(incomplete)

	def on_submit(self):
		pass


@frappe.whitelist()
def get_cutting_order_detail_data(cutting_order_detail):
	doc = frappe.get_doc("Cutting Order Detail", cutting_order_detail)

	colours = [row.attribute_value for row in doc.attribute_values]

	sizes = []
	for attr_row in doc.item_attributes:
		if attr_row.attribute == doc.primary_attribute and attr_row.mapping:
			mapping_doc = frappe.get_cached_doc("Item Item Attribute Mapping", attr_row.mapping)
			sizes = [v.attribute_value for v in mapping_doc.values]
			break

	if doc.is_set_item:
		# Build combination dict: major_colour → {part → actual_colour}
		comb_dict = {}
		parts = []
		for row in doc.set_item_combination_details:
			comb_dict.setdefault(row.major_attribute_value, {})
			comb_dict[row.major_attribute_value][row.set_item_attribute_value] = row.attribute_value
			if row.set_item_attribute_value not in parts:
				parts.append(row.set_item_attribute_value)

		# Build actual items: for each major colour × part, resolve actual colour
		items = []
		for major_colour in colours:
			for part in parts:
				actual_colour = comb_dict.get(major_colour, {}).get(part, major_colour)
				items.append({
					"colour": actual_colour,
					"part": part,
					"major_colour": major_colour,
				})

		return {
			"item": doc.item,
			"is_set_item": doc.is_set_item,
			"colours": colours,
			"sizes": sizes,
			"parts": parts,
			"items": items,
		}
	else:
		parts = [row.stiching_attribute_value for row in doc.stiching_item_details]

		return {
			"item": doc.item,
			"is_set_item": doc.is_set_item,
			"colours": colours,
			"sizes": sizes,
			"parts": parts,
		}
