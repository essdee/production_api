# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
import json
import copy
from frappe.model.document import Document
from production_api.utils import update_if_string_instance


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

		cod = frappe.get_doc("Cutting Order Detail", self.cutting_order_detail)

		# Get sizes from COD
		sizes = []
		for attr_row in cod.item_attributes:
			if attr_row.attribute == cod.primary_attribute and attr_row.mapping:
				mapping_doc = frappe.get_cached_doc("Item Item Attribute Mapping", attr_row.mapping)
				sizes = [v.attribute_value for v in mapping_doc.values]
				break

		# Build panels and stiching_attrs in CP-compatible format
		if cod.is_set_item:
			panels = {}
			stiching_attrs = {cod.stiching_attribute: {}}
			for row in cod.stiching_item_details:
				panels.setdefault(row.set_item_attribute_value, {})
				panels[row.set_item_attribute_value][row.stiching_attribute_value] = 0
				stiching_attrs[cod.stiching_attribute].setdefault(row.set_item_attribute_value, [])
				stiching_attrs[cod.stiching_attribute][row.set_item_attribute_value].append(row.stiching_attribute_value)
		else:
			panels = {}
			stiching_attrs = {cod.stiching_attribute: []}
			for row in cod.stiching_item_details:
				panels[row.stiching_attribute_value] = 0
				stiching_attrs[cod.stiching_attribute].append(row.stiching_attribute_value)

		# Build CP-compatible items list
		total_qty = {size: 0 for size in sizes}
		completed_items = []
		incomplete_items = []

		for item in data.get('items', []):
			# Build attributes dict
			colour = item.get('colour', '')
			attributes = {cod.packing_attribute: colour}
			item_keys = {}

			if cod.is_set_item:
				part = item.get('part', '')
				attributes[cod.set_item_attribute] = part
				item_keys = {
					"major_colour": item.get('major_colour', colour),
					"major_part": part,
				}

			# Build values dict from quantities (keyed by size)
			values = {}
			for size in sizes:
				values[size] = item.get('quantities', {}).get(size, 0)

			# Completed item: zeroed values
			comp_item = {
				"attributes": copy.deepcopy(attributes),
				"values": {size: 0 for size in sizes},
				"completed": False,
				"completed_date": None,
			}
			if cod.is_set_item:
				comp_item["item_keys"] = copy.deepcopy(item_keys)
			completed_items.append(comp_item)

			# Incomplete item: panel dicts
			inc_item = {
				"attributes": copy.deepcopy(attributes),
				"completed": False,
				"completed_date": None,
			}
			if cod.is_set_item:
				inc_item["item_keys"] = copy.deepcopy(item_keys)
				inc_item["values"] = {size: copy.deepcopy(panels.get(part, {})) for size in sizes}
			else:
				inc_item["values"] = {size: copy.deepcopy(panels) for size in sizes}
			incomplete_items.append(inc_item)

		completed = {
			"items": completed_items,
			"total_qty": total_qty,
			"is_set_item": cod.is_set_item,
			"pack_attr": cod.packing_attribute,
			"stiching_attr": cod.stiching_attribute,
			"primary_attribute_values": sizes,
		}
		if cod.is_set_item:
			completed["set_item_attr"] = cod.set_item_attribute
		completed.update(stiching_attrs)

		incomplete = {
			"items": incomplete_items,
			"total_qty": copy.deepcopy(total_qty),
			"is_set_item": cod.is_set_item,
			"pack_attr": cod.packing_attribute,
			"stiching_attr": cod.stiching_attribute,
			"primary_attribute_values": sizes,
		}
		if cod.is_set_item:
			incomplete["set_item_attr"] = cod.set_item_attribute
		incomplete.update(copy.deepcopy(stiching_attrs))

		self.completed_items_json = json.dumps(completed)
		self.incomplete_items_json = json.dumps(incomplete)
		self.co_status = "Submitted"

	def on_submit(self):
		pass

	def on_update_after_submit(self):
		completed_json = update_if_string_instance(self.completed_items_json)
		all_completed = True
		any_completed = False
		for item in completed_json.get('items', []):
			if item.get('completed'):
				any_completed = True
			else:
				all_completed = False

		has_laysheets = frappe.db.exists("Cutting LaySheet", {
			"cutting_order": self.name,
			"status": ["!=", "Cancelled"],
		})

		if all_completed and any_completed:
			new_status = "Completed"
		elif any_completed:
			new_status = "Partially Completed"
		elif has_laysheets:
			new_status = "Cutting In Progress"
		else:
			new_status = "Submitted"

		frappe.db.set_value(self.doctype, self.name, "co_status", new_status)


@frappe.whitelist()
def calculate_laysheets(cutting_order):
	frappe.enqueue(calc_laysheets, "short", cutting_order=cutting_order)


def calc_laysheets(cutting_order):
	co_doc = frappe.get_doc("Cutting Order", cutting_order)
	cod = frappe.get_cached_doc("Cutting Order Detail", co_doc.cutting_order_detail)
	data = json.loads(co_doc.items_json)

	# Get sizes from COD
	sizes = []
	for attr_row in cod.item_attributes:
		if attr_row.attribute == cod.primary_attribute and attr_row.mapping:
			mapping_doc = frappe.get_cached_doc("Item Item Attribute Mapping", attr_row.mapping)
			sizes = [v.attribute_value for v in mapping_doc.values]
			break

	# Build panels and stiching_attrs
	if cod.is_set_item:
		panels = {}
		stiching_attrs = {cod.stiching_attribute: {}}
		for row in cod.stiching_item_details:
			panels.setdefault(row.set_item_attribute_value, {})
			panels[row.set_item_attribute_value][row.stiching_attribute_value] = 0
			stiching_attrs[cod.stiching_attribute].setdefault(row.set_item_attribute_value, [])
			stiching_attrs[cod.stiching_attribute][row.set_item_attribute_value].append(row.stiching_attribute_value)
	else:
		panels = {}
		stiching_attrs = {cod.stiching_attribute: []}
		for row in cod.stiching_item_details:
			panels[row.stiching_attribute_value] = 0
			stiching_attrs[cod.stiching_attribute].append(row.stiching_attribute_value)

	# Build zeroed completed/incomplete items
	total_qty = {size: 0 for size in sizes}
	completed_items = []
	incomplete_items = []

	for item in data.get('items', []):
		colour = item.get('colour', '')
		attributes = {cod.packing_attribute: colour}
		item_keys = {}

		if cod.is_set_item:
			part = item.get('part', '')
			attributes[cod.set_item_attribute] = part
			item_keys = {
				"major_colour": item.get('major_colour', colour),
				"major_part": part,
			}

		comp_item = {
			"attributes": copy.deepcopy(attributes),
			"values": {size: 0 for size in sizes},
			"completed": False,
			"completed_date": None,
		}
		if cod.is_set_item:
			comp_item["item_keys"] = copy.deepcopy(item_keys)
		completed_items.append(comp_item)

		inc_item = {
			"attributes": copy.deepcopy(attributes),
			"completed": False,
			"completed_date": None,
		}
		if cod.is_set_item:
			inc_item["item_keys"] = copy.deepcopy(item_keys)
			inc_item["values"] = {size: copy.deepcopy(panels.get(part, {})) for size in sizes}
		else:
			inc_item["values"] = {size: copy.deepcopy(panels) for size in sizes}
		incomplete_items.append(inc_item)

	completed = {
		"items": completed_items,
		"total_qty": total_qty,
		"is_set_item": cod.is_set_item,
		"pack_attr": cod.packing_attribute,
		"stiching_attr": cod.stiching_attribute,
		"primary_attribute_values": sizes,
	}
	if cod.is_set_item:
		completed["set_item_attr"] = cod.set_item_attribute
	completed.update(stiching_attrs)

	incomplete = {
		"items": incomplete_items,
		"total_qty": copy.deepcopy(total_qty),
		"is_set_item": cod.is_set_item,
		"pack_attr": cod.packing_attribute,
		"stiching_attr": cod.stiching_attribute,
		"primary_attribute_values": sizes,
	}
	if cod.is_set_item:
		incomplete["set_item_attr"] = cod.set_item_attribute
	incomplete.update(copy.deepcopy(stiching_attrs))

	co_doc.completed_items_json = json.dumps(completed)
	co_doc.incomplete_items_json = json.dumps(incomplete)
	co_doc.save()

	# Re-process all Label Printed LaySheets
	from production_api.production_api.doctype.cutting_laysheet.cutting_laysheet import update_cutting_plan
	cls_list = frappe.get_list("Cutting LaySheet", filters={"cutting_order": cutting_order, "status": "Label Printed"}, pluck="name")
	for cls in cls_list:
		update_cutting_plan(cls)

	co_doc.reload()
	co_doc.save()


@frappe.whitelist(allow_guest=True)
def get_cutting_order_laysheets_report(cutting_order):
	co_doc = frappe.get_doc("Cutting Order", cutting_order)
	cod_doc = frappe.get_cached_doc("Cutting Order Detail", co_doc.cutting_order_detail)

	# Get sizes from COD
	sizes = []
	for attr_row in cod_doc.item_attributes:
		if attr_row.attribute == cod_doc.primary_attribute and attr_row.mapping:
			mapping_doc = frappe.get_cached_doc("Item Item Attribute Mapping", attr_row.mapping)
			sizes = [v.attribute_value for v in mapping_doc.values]
			break

	panels = []
	if cod_doc.is_set_item:
		panels = {}
		for row in cod_doc.stiching_item_details:
			panels.setdefault(row.set_item_attribute_value, [])

	cls_list = frappe.get_list("Cutting LaySheet", filters={"cutting_order": cutting_order, "status": "Label Printed"}, pluck="name", order_by="lay_no asc")
	lay_details = {}
	for cls in cls_list:
		cls_doc = frappe.get_doc("Cutting LaySheet", cls)
		lay_no = cls_doc.lay_no
		lay_details[lay_no] = {}
		for row in cls_doc.cutting_laysheet_bundles:
			parts = row.part.split(",")
			parts = ", ".join(parts)
			set_combination = update_if_string_instance(row.set_combination)
			major_colour = set_combination['major_colour']
			if cod_doc.is_set_item:
				if set_combination.get('set_part'):
					if parts not in panels[set_combination['set_part']]:
						panels[set_combination['set_part']].append(parts)
					major_colour = "("+ major_colour +")" + set_combination["set_colour"] +"-"+set_combination.get('set_part')
				else:
					if parts not in panels[set_combination['major_part']]:
						panels[set_combination['major_part']].append(parts)
					major_colour = major_colour +"-"+set_combination.get('major_part')
			else:
				if parts not in panels:
					panels.append(parts)

			lay_details[lay_no].setdefault(major_colour, {})
			lay_details[lay_no][major_colour].setdefault(row.size, {})
			lay_details[lay_no][major_colour][row.size].setdefault(row.shade, {})
			lay_details[lay_no][major_colour][row.size][row.shade].setdefault(parts, {})
			lay_details[lay_no][major_colour][row.size][row.shade][parts].setdefault("qty", 0)
			lay_details[lay_no][major_colour][row.size][row.shade][parts]["qty"] += row.quantity
			lay_details[lay_no][major_colour][row.size][row.shade][parts].setdefault("bundles", 0)
			lay_details[lay_no][major_colour][row.size][row.shade][parts]['bundles'] += 1

	final_data = {}
	for size in sizes:
		for lay_number, colour_dict in lay_details.items():
			if not lay_details.get(lay_number):
				continue
			for colour, colour_detail in colour_dict.items():
				for cur_size, panel_detail in lay_details.get(lay_number).get(colour).items():
					if cur_size == size:
						final_data.setdefault(colour, [])
						for shade in panel_detail:
							duplicate = {}
							duplicate['lay_no'] = lay_number
							duplicate['size'] = size
							duplicate['shade'] = shade
							for panel, panel_details in panel_detail[shade].items():
								duplicate[panel] = panel_details['qty']
								duplicate[panel+"_Bundle"] = panel_details['bundles']
							final_data[colour].append(duplicate)
	return panels, final_data, cod_doc.is_set_item


@frappe.whitelist(allow_guest=True)
def get_cutting_order_size_reports(cutting_order):
	co_doc = frappe.get_doc("Cutting Order", cutting_order)
	cod_doc = frappe.get_cached_doc("Cutting Order Detail", co_doc.cutting_order_detail)

	# Get sizes from COD
	sizes = []
	for attr_row in cod_doc.item_attributes:
		if attr_row.attribute == cod_doc.primary_attribute and attr_row.mapping:
			mapping_doc = frappe.get_cached_doc("Item Item Attribute Mapping", attr_row.mapping)
			sizes = [v.attribute_value for v in mapping_doc.values]
			break

	panels = []
	if cod_doc.is_set_item:
		panels = {}
		for row in cod_doc.stiching_item_details:
			panels.setdefault(row.set_item_attribute_value, [])

	cls_list = frappe.get_list("Cutting LaySheet", filters={"cutting_order": cutting_order, "status": "Label Printed"}, pluck="name", order_by="lay_no asc")
	size_details = {}
	for cls in cls_list:
		cls_doc = frappe.get_doc("Cutting LaySheet", cls)
		for row in cls_doc.cutting_laysheet_bundles:
			parts = row.part.split(",")
			parts = ", ".join(parts)
			set_combination = update_if_string_instance(row.set_combination)
			major_colour = set_combination['major_colour']
			if cod_doc.is_set_item:
				if set_combination.get('set_part'):
					if parts not in panels[set_combination['set_part']]:
						panels[set_combination['set_part']].append(parts)
					major_colour = "("+ major_colour +")" + set_combination["set_colour"] +"-"+set_combination.get('set_part')
				else:
					if parts not in panels[set_combination['major_part']]:
						panels[set_combination['major_part']].append(parts)
					major_colour = major_colour +"-"+set_combination.get('major_part')
			else:
				if parts not in panels:
					panels.append(parts)
			size_details.setdefault(major_colour, {})
			size_details[major_colour].setdefault(row.size, {})
			size_details[major_colour][row.size].setdefault(parts, {})
			size_details[major_colour][row.size][parts].setdefault("qty", 0)
			size_details[major_colour][row.size][parts]["qty"] += row.quantity
			size_details[major_colour][row.size][parts].setdefault("bundles", 0)
			size_details[major_colour][row.size][parts]['bundles'] += 1

	final_data = {}
	for size in sizes:
		for colour, colour_details in size_details.items():
			for dict_size, panel_detail in colour_details.items():
				if dict_size == size:
					final_data.setdefault(colour, [])
					duplicate = {}
					duplicate['size'] = size
					for panel in panel_detail:
						duplicate[panel] = panel_detail[panel]['qty']
						duplicate[panel+"_Bundle"] = panel_detail[panel]['bundles']
					final_data[colour].append(duplicate)
	return panels, final_data, cod_doc.is_set_item


@frappe.whitelist(allow_guest=True)
def get_cutting_order_ccr(doc_name):
	co_doc = frappe.get_doc("Cutting Order", doc_name)
	cod_doc = frappe.get_cached_doc("Cutting Order Detail", co_doc.cutting_order_detail)

	cls_list = frappe.get_all("Cutting LaySheet", filters={"cutting_order": doc_name, "status": "Label Printed"}, pluck="name", order_by="lay_no asc")
	markers = {}
	for cls in cls_list:
		cls_doc = frappe.get_doc("Cutting LaySheet", cls)
		sizes = {}
		for row in cls_doc.cutting_marker_ratios:
			if row.size not in sizes:
				sizes[row.size] = row.ratio
		panels = cls_doc.calculated_parts.split(",")
		panels.sort()
		for idx, panel in enumerate(panels):
			panels[idx] = panel.strip()

		tup_panels = ", ".join(panels)
		markers.setdefault(tup_panels, {})
		for row in cls_doc.cutting_laysheet_details:
			key = (row.colour, row.cloth_type)
			markers[tup_panels].setdefault(key, {
				"used_weight": 0,
				"total_pieces": 0,
			})

			markers[tup_panels][key]["used_weight"] += row.used_weight
			for size in sizes:
				markers[tup_panels][key].setdefault(size, {"bits": 0})
				bits = sizes[size] * row.effective_bits
				markers[tup_panels][key][size]["bits"] += bits
				markers[tup_panels][key]["total_pieces"] += bits

		sizes = {}

	# Get sizes from COD
	all_sizes = []
	for attr_row in cod_doc.item_attributes:
		if attr_row.attribute == cod_doc.primary_attribute and attr_row.mapping:
			mapping_doc = frappe.get_cached_doc("Item Item Attribute Mapping", attr_row.mapping)
			all_sizes = [v.attribute_value for v in mapping_doc.values]
			break

	# Ensure every colour entry has all sizes
	for mark in markers:
		for key in markers[mark]:
			for size in all_sizes:
				markers[mark][key].setdefault(size, {"bits": 0})

	if markers:
		return {
			"marker_data": markers,
			"sizes": all_sizes,
		}


@frappe.whitelist()
def get_cutting_order_planned_vs_actual(cutting_order):
	co_doc = frappe.get_doc("Cutting Order", cutting_order)
	cod_doc = frappe.get_cached_doc("Cutting Order Detail", co_doc.cutting_order_detail)

	# Get sizes from COD
	sizes = []
	for attr_row in cod_doc.item_attributes:
		if attr_row.attribute == cod_doc.primary_attribute and attr_row.mapping:
			mapping_doc = frappe.get_cached_doc("Item Item Attribute Mapping", attr_row.mapping)
			sizes = [v.attribute_value for v in mapping_doc.values]
			break

	# Parse planned quantities from items_json
	data = json.loads(co_doc.items_json or '{}')
	planned_items = data.get('items', [])

	# Aggregate actual quantities from LaySheet bundles
	# Key: (colour, part_or_none) -> {size: qty}
	actual_qty = {}
	cls_list = frappe.get_list(
		"Cutting LaySheet",
		filters={"cutting_order": cutting_order, "status": "Label Printed"},
		pluck="name",
	)
	for cls_name in cls_list:
		cls_doc = frappe.get_doc("Cutting LaySheet", cls_name)
		for row in cls_doc.cutting_laysheet_bundles:
			set_combination = update_if_string_instance(row.set_combination)
			major_colour = set_combination.get('major_colour', '')

			if cod_doc.is_set_item:
				part = set_combination.get('set_part') or set_combination.get('major_part', '')
				colour = set_combination.get('set_colour') or major_colour
				key = (colour, part, major_colour)
			else:
				key = (major_colour, None, major_colour)

			actual_qty.setdefault(key, {s: 0 for s in sizes})
			if row.size in actual_qty[key]:
				actual_qty[key][row.size] += row.quantity

	# Build WOSummary-shaped result
	items_list = []
	total_details = {s: {"planned": 0, "received": 0} for s in sizes}
	overall_planned = 0
	overall_received = 0

	for item in planned_items:
		colour = item.get('colour', '')
		quantities = item.get('quantities', {})

		attributes = {cod_doc.packing_attribute: colour}
		item_keys = {}

		if cod_doc.is_set_item:
			part = item.get('part', '')
			attributes[cod_doc.set_item_attribute] = part
			major_colour = item.get('major_colour', colour)
			item_keys = {"major_colour": major_colour}
			key = (colour, part, major_colour)
		else:
			key = (colour, None, colour)

		values = {}
		total_qty = 0
		total_received = 0
		for s in sizes:
			planned = quantities.get(s, 0)
			received = actual_qty.get(key, {}).get(s, 0)
			values[s] = {"qty": planned, "received": received}
			total_qty += planned
			total_received += received
			total_details[s]["planned"] += planned
			total_details[s]["received"] += received

		entry = {
			"attributes": attributes,
			"values": values,
			"total_qty": total_qty,
			"total_received": total_received,
		}
		if cod_doc.is_set_item:
			entry["item_keys"] = item_keys

		items_list.append(entry)
		overall_planned += total_qty
		overall_received += total_received

	result = [{
		"pack_attr": cod_doc.packing_attribute,
		"is_set_item": cod_doc.is_set_item,
		"primary_attribute_values": sizes,
		"items": items_list,
		"total_details": total_details,
		"overall_planned": overall_planned,
		"overall_received": overall_received,
	}]

	if cod_doc.is_set_item:
		result[0]["set_attr"] = cod_doc.set_item_attribute

	return result


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
