# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_or_create_variant
from production_api.utils import get_variant_attr_details, update_if_string_instance
from production_api.mrp_stock.doctype.stock_summary.stock_summary import get_variant_attr_values
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values

class SewingPlan(Document):
	pass

@frappe.whitelist()
def create_sewing_plan(work_order):
	finishing_inward_process = frappe.db.get_single_value("MRP Settings", "finishing_inward_process")
	process_name, internal_unit = frappe.get_value("Work Order", work_order, ["process_name", "is_internal_unit"])	
	if not internal_unit:
		return
	
	is_group = frappe.get_value("Process", process_name, "is_group")
	is_sewing = False
	if is_group:
		process = None
		doc = frappe.get_doc("Process", process_name)
		for row in doc.process_details:
			process = row.process_name
		is_sewing = process == finishing_inward_process
	else:
		is_sewing = process_name == finishing_inward_process

	if is_sewing:
		sp_list = frappe.get_all("Sewing Plan", filters={
			"work_order": work_order
		}, pluck="name")
		if sp_list:
			return
		wo_doc = frappe.get_doc("Work Order", work_order)
		items = []
		for row in wo_doc.work_order_calculated_items:
			items.append({
				"item_variant": row.item_variant,
				"set_combination": row.set_combination,
				"quantity": row.quantity,
			})
		new_doc = frappe.new_doc("Sewing Plan")	
		new_doc.work_order = work_order
		new_doc.set("sewing_plan_order_details", items)
		new_doc.save(ignore_permissions=True)

def delete_sewing_plan(work_order):
	sp_list = frappe.get_all("Sewing Plan", filters={
		"work_order": work_order, 
	}, pluck="name")
	if sp_list:
		sp_entry = frappe.get_all("Sewing Plan Entry Detail", filters={
			"sewing_plan": sp_list[0]
		}, pluck="name")
		if sp_entry:
			frappe.throw("Cannot cancel this Work Order")
		else:
			frappe.delete_doc("Sewing Plan", sp_list[0], ignore_permissions=True)	

def get_sp_entry_details(supplier, dpr_date=None, work_station=None, input_type=None):
	sp_list = frappe.get_all("Sewing Plan", filters={
		"supplier": supplier
	}, pluck="name")
	
	filters = {
		"sewing_plan": ["in", sp_list]
	}
	if dpr_date:
		filters['entry_date'] = dpr_date
	if work_station:
		filters['work_station'] = work_station
	if input_type:
		filters['input_type'] = input_type
	sp_entry_list = frappe.get_all("Sewing Plan Entry Detail", filters=filters, pluck="name")

	return sp_entry_list

@frappe.whitelist()
def get_dashboard_data(supplier):
	sp_entry_list = get_sp_entry_details(supplier)
	if not sp_entry_list:
		return []
	data = frappe.db.sql(
		"""
			SELECT SUM(t1.quantity) AS qty, t2.input_type
			FROM `tabSewing Plan Detail` t1
			JOIN `tabSewing Plan Entry Detail` t2
			ON t1.parent = t2.name
			WHERE t2.name IN %(entries)s
			GROUP BY t2.input_type
			ORDER BY SUM(t1.quantity) DESC
		""",
		{
			"entries": tuple(sp_entry_list)
		},
		as_dict=True
	)
	return data

@frappe.whitelist()
def get_sp_status_summary(supplier):
	ipd_settings = frappe.get_single("IPD Settings")
	mrp_doc = frappe.get_single("MRP Settings")
	type_wise_diff_input = mrp_doc.type_wise_diff_summary
	received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	input_qty_type = mrp_doc.sewing_input_qty_type
	line_output_type = mrp_doc.sewing_line_output_type

	# Query 1: All sewing plans for this supplier
	sp_records = frappe.db.sql("""
		SELECT name, work_order, lot, item
		FROM `tabSewing Plan`
		WHERE supplier = %(supplier)s
	""", {"supplier": supplier}, as_dict=True)

	if not sp_records:
		return {"header1": [], "header2": [], "data": [], "header3": []}

	sp_names = [r.name for r in sp_records]
	lots = list({r.lot for r in sp_records})
	wo_names = list({r.work_order for r in sp_records})

	# Query 2: Lot → production_detail mapping
	lot_rows = frappe.db.sql("""
		SELECT name, production_detail
		FROM `tabLot`
		WHERE name IN %(lots)s
	""", {"lots": tuple(lots)}, as_dict=True)
	lot_to_ipd = {r.name: r.production_detail for r in lot_rows}

	# Query 3: IPD details
	ipd_names = list({lot_to_ipd[l] for l in lot_to_ipd})
	ipd_rows = frappe.db.sql("""
		SELECT name, is_set_item, packing_attribute, primary_item_attribute, set_item_attribute
		FROM `tabItem Production Detail`
		WHERE name IN %(ipds)s
	""", {"ipds": tuple(ipd_names)}, as_dict=True)
	ipd_map = {r.name: r for r in ipd_rows}

	# Query 4: Work Order Calculated Items
	wo_calc_rows = frappe.db.sql("""
		SELECT parent, item_variant, set_combination, received_qty
		FROM `tabWork Order Calculated Item`
		WHERE parent IN %(wos)s
	""", {"wos": tuple(wo_names)}, as_dict=True)
	wo_calc_by_wo = {}
	for r in wo_calc_rows:
		wo_calc_by_wo.setdefault(r.parent, []).append(r)

	# Query 5: Sewing Plan Order Details
	sp_order_rows = frappe.db.sql("""
		SELECT parent, item_variant, set_combination, quantity, pre_final, final_inspection, fi_date
		FROM `tabSewing Plan Order Detail`
		WHERE parent IN %(sps)s
	""", {"sps": tuple(sp_names)}, as_dict=True)
	sp_order_by_sp = {}
	for r in sp_order_rows:
		sp_order_by_sp.setdefault(r.parent, []).append(r)

	# Query 6a: Sewing Plan Entry Details
	entry_rows = frappe.db.sql("""
		SELECT name, sewing_plan, input_type, received_type, entry_date
		FROM `tabSewing Plan Entry Detail`
		WHERE sewing_plan IN %(sps)s
	""", {"sps": tuple(sp_names)}, as_dict=True)
	entries_by_sp = {}
	entry_names = []
	for r in entry_rows:
		entries_by_sp.setdefault(r.sewing_plan, []).append(r)
		entry_names.append(r.name)

	# Query 6b: Sewing Plan Details (child rows of entries)
	sp_details_by_entry = {}
	if entry_names:
		sp_detail_rows = frappe.db.sql("""
			SELECT parent, item_variant, set_combination, quantity
			FROM `tabSewing Plan Detail`
			WHERE parent IN %(entries)s
		""", {"entries": tuple(entry_names)}, as_dict=True)
		for r in sp_detail_rows:
			sp_details_by_entry.setdefault(r.parent, []).append(r)

	# Query 7: Item Variant Attributes — bulk fetch for all variants
	all_variants = set()
	for r in wo_calc_rows:
		all_variants.add(r.item_variant)
	for r in sp_order_rows:
		all_variants.add(r.item_variant)
	for rows in sp_details_by_entry.values():
		for r in rows:
			all_variants.add(r.item_variant)

	variant_attr_cache = {}
	if all_variants:
		variant_attr_rows = frappe.db.sql("""
			SELECT parent, attribute, attribute_value
			FROM `tabItem Variant Attribute`
			WHERE parent IN %(variants)s
		""", {"variants": tuple(all_variants)}, as_dict=True)
		for r in variant_attr_rows:
			variant_attr_cache.setdefault(r.parent, {})[r.attribute] = r.attribute_value

	def get_sp_key_cached(row, item, lot, primary_attr):
		attrs_dict = variant_attr_cache.get(row.item_variant, {})
		attrs = sorted([v for k, v in attrs_dict.items() if k != primary_attr])
		attrs = tuple(attrs) if attrs else None
		set_comb = update_if_string_instance(row.set_combination)
		set_comb_key = tuple(sorted(set_comb.items()))
		return (item, lot, attrs, set_comb_key)

	# ── Process all data (zero DB calls) ──
	data = {}
	total = {}
	fi_dates_by_key = {}

	for sp in sp_records:
		sp_name = sp.name
		lot = sp.lot
		item = sp.item

		ipd_name = lot_to_ipd.get(lot)
		ipd = ipd_map.get(ipd_name, {})
		is_set_item = ipd.get("is_set_item")
		pack_attr = ipd.get("packing_attribute")
		primary_attr = ipd.get("primary_item_attribute")
		set_attr = ipd.get("set_item_attribute")

		# WO calculated items → GRN Qty
		for row in wo_calc_by_wo.get(sp.work_order, []):
			key = get_sp_key_cached(row, item, lot, primary_attr)
			attr_details = variant_attr_cache.get(row.item_variant, {})
			set_comb = update_if_string_instance(row.set_combination)
			major_colour = set_comb.get("major_colour", "")

			if is_set_item:
				variant_colour = attr_details.get(pack_attr, "")
				display_colour = f"{variant_colour} ({major_colour})"
			else:
				display_colour = major_colour

			data.setdefault(key, {
				"item": item,
				"lot": lot,
				"item_variant": row.item_variant,
				"attr_details": attr_details,
				"pack_attr": pack_attr if is_set_item else ipd_settings.default_packing_attribute,
				"set_attr": set_attr if is_set_item else None,
				"is_set_item": is_set_item,
				"major_colour": major_colour,
				"display_colour": display_colour,
				"input_dates": [],
				"output_dates": [],
			})
			input_key = "GRN Qty"
			data[key].setdefault(input_key, 0)
			data[key][input_key] += row.received_qty
			total.setdefault(input_key, 0)
			total[input_key] += row.received_qty

		# SP order details → Order Qty, Pre Final, Final Inspection, FI dates
		for row in sp_order_by_sp.get(sp_name, []):
			key = get_sp_key_cached(row, item, lot, primary_attr)

			input_key = "Order Qty"
			data[key].setdefault(input_key, 0)
			data[key][input_key] += row.quantity
			total.setdefault(input_key, 0)
			total[input_key] += row.quantity

			input_key = "Pre Final"
			data[key].setdefault(input_key, 0)
			data[key][input_key] += row.pre_final
			total.setdefault(input_key, 0)
			total[input_key] += row.pre_final

			input_key = "Final Inspection"
			data[key].setdefault(input_key, 0)
			data[key][input_key] += row.final_inspection
			total.setdefault(input_key, 0)
			total[input_key] += row.final_inspection

			if row.fi_date:
				fi_dates_by_key.setdefault(key, [])
				fi_dates_by_key[key].append(row.fi_date)

		# SP entry details → input type quantities, dates
		total.setdefault("checking_total", 0)

		for entry in entries_by_sp.get(sp_name, []):
			entry_date = entry.entry_date
			for row in sp_details_by_entry.get(entry.name, []):
				key = get_sp_key_cached(row, item, lot, primary_attr)
				input_key = entry.input_type

				if input_key == input_qty_type:
					data[key]["input_dates"].append(entry_date)
				if input_key == line_output_type:
					data[key]["output_dates"].append(entry_date)

				if input_key == type_wise_diff_input:
					total["checking_total"] += row.quantity
					data[key].setdefault("checking_total", 0)
					data[key]["checking_total"] += row.quantity
					if received_type != entry.received_type:
						input_key = entry.received_type
				else:
					if received_type != entry.received_type:
						input_key += " " + entry.received_type
				total.setdefault(input_key, 0)
				total[input_key] += row.quantity
				data[key].setdefault(input_key, 0)
				data[key][input_key] += row.quantity

	# ── Post-processing (unchanged) ──
	inspection_type = mrp_doc.sewing_plan_inspection_type
	line_output = mrp_doc.sewing_line_output_type
	input_qty = mrp_doc.sewing_input_qty_type
	data_list = []
	for row in data:
		x = data[row]
		if x.get(line_output) and x.get('checking_total'):
			x['Ready for Checking'] = "Under Checking" if x[line_output] > x['checking_total'] else "Completed"
		if x.get(type_wise_diff_input) and x.get(inspection_type):
			x['Ready for AQL'] = "Under AQL" if x[type_wise_diff_input] > x[inspection_type] else "Completed"
		if x.get(inspection_type) and x.get('Pre Final', 0) > 0:
			x['Ready for Pre final'] = "Under Pre Final" if x[inspection_type] > x['Pre Final'] else "Completed"
		if x.get('Final Inspection', 0) > 0:
			x['Ready for Final Inspection'] = "Under Final Inspection" if x.get('Pre Final', 0) > x['Final Inspection'] else "Completed"

		input_dates = x.get('input_dates', [])
		output_dates = x.get('output_dates', [])

		if input_dates:
			x['Input Date'] = min(input_dates)
		else:
			x['Input Date'] = None

		if output_dates:
			x['Last Sewing Output'] = max(output_dates)
		else:
			x['Last Sewing Output'] = None

		if x['Input Date'] and x['Last Sewing Output']:
			x['Total Running Days'] = (x['Last Sewing Output'] - x['Input Date']).days
		else:
			x['Total Running Days'] = None

		fi_dates = fi_dates_by_key.get(row, [])
		if fi_dates:
			x['FI Date'] = min(fi_dates).strftime("%Y-%m-%d")
		else:
			x['FI Date'] = None

		line_stock = x.get(line_output, 0) - x.get(input_qty, 0)
		stock = x.get('checking_total', 0) - x.get(line_output, 0)
		total.setdefault("Line Stock", 0)
		total["Line Stock"] += line_stock
		total.setdefault("Stock", 0)
		total["Stock"] += stock
		x['Line Stock'] = line_stock
		x['Stock'] = stock
		grn_pending = x.get(line_output, 0) - x['GRN Qty']
		total.setdefault("GRN Pending", 0)
		total["GRN Pending"] += grn_pending
		x['GRN Pending'] = grn_pending
		data_list.append(x)

	data_list = [total] + data_list

	header1 = [
		"Item",
		"Lot",
		ipd_settings.default_packing_attribute,
		ipd_settings.default_set_item_attribute,
		"FI Date",
		"Input Date",
		"Last Sewing Output",
		"Total Running Days",
	]
	header2 = ["Order Qty"]
	for row in mrp_doc.sewing_plan_status_summary:
		if row.input_type == type_wise_diff_input:
			if received_type != row.received_type:
				header2.append(row.received_type)
			else:
				header2.append(row.input_type)
		else:
			header2.append(row.input_type)

	header2.append("Pre Final")
	header2.append("Final Inspection")
	header2.append("GRN Qty")
	header2.append("GRN Pending")
	header2.append("Line Stock")
	header2.append("Stock")
	header3 = [
		"Ready for Checking",
		"Ready for AQL",
		"Ready for Pre final",
		"Ready for Final Inspection",
	]
	return {
		"header1": header1,
		"header2": header2,
		"data": data_list,
		"header3": header3,
	}

def get_sp_key(row, item, lot, primary_attr):
	doc = frappe.get_doc("Item Variant", row.item_variant)
	attrs = get_variant_attr_values(doc, primary_attr)
	set_comb = update_if_string_instance(row.set_combination)
	set_comb = tuple(sorted(set_comb.items()))
	key = (item, lot, attrs, set_comb)

	return key

@frappe.whitelist()
def get_data_entry_data(supplier, lot=None):
	filters = {"supplier": supplier}
	if lot:
		filters["lot"] = lot

	# Step 1: Bulk-fetch all sewing plans with needed fields
	sp_list = frappe.get_all("Sewing Plan", filters=filters, fields=["name", "lot", "item", "supplier"], limit_page_length=0)
	if not sp_list:
		return []

	sp_names = [sp.name for sp in sp_list]
	sp_map = {sp.name: sp for sp in sp_list}

	# Step 2: Bulk-fetch all order detail rows for all plans
	order_details = frappe.get_all("Sewing Plan Order Detail",
		filters={"parent": ["in", sp_names]},
		fields=["parent", "item_variant", "set_combination", "quantity", "pre_final", "final_inspection"],
		limit_page_length=0,
	)

	# Step 3: Bulk-fetch all entry details and their child rows
	entry_details = frappe.get_all("Sewing Plan Entry Detail",
		filters={"sewing_plan": ["in", sp_names]},
		fields=["name", "sewing_plan", "input_type"],
		limit_page_length=0,
	)
	entry_names = [e.name for e in entry_details]
	entry_rows = []
	if entry_names:
		entry_rows = frappe.get_all("Sewing Plan Detail",
			filters={"parent": ["in", entry_names]},
			fields=["parent", "item_variant", "set_combination", "quantity"],
			limit_page_length=0,
		)

	# Step 4: Bulk-fetch all variant attributes in one query
	all_variants = set()
	for row in order_details:
		all_variants.add(row.item_variant)
	for row in entry_rows:
		all_variants.add(row.item_variant)

	variant_attr_map = {}
	if all_variants:
		variant_attrs_raw = frappe.db.sql("""
			SELECT parent, attribute, attribute_value
			FROM `tabItem Variant Attribute`
			WHERE parent IN %(variants)s
		""", {"variants": list(all_variants)}, as_dict=True)
		for row in variant_attrs_raw:
			variant_attr_map.setdefault(row.parent, {})[row.attribute] = row.attribute_value

	# Step 5: Cache Lot → IPD lookups (deduplicated)
	unique_lots = set(sp.lot for sp in sp_list)
	lot_ipd_map = {}
	for l in unique_lots:
		lot_ipd_map[l] = frappe.get_value("Lot", l, "production_detail")

	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
	unique_ipds = set(lot_ipd_map.values())
	ipd_data_map = {}
	ipd_primary_map = {}
	for ipd in unique_ipds:
		ipd_data_map[ipd] = frappe.get_value("Item Production Detail", ipd, ipd_fields)
		ipd_primary_map[ipd] = get_ipd_primary_values(ipd)

	# Build order_details grouped by parent for quick lookup
	od_by_parent = {}
	for row in order_details:
		od_by_parent.setdefault(row.parent, []).append(row)

	# Build entry_details grouped by sewing_plan, and entry_rows grouped by parent
	ed_by_sp = {}
	for e in entry_details:
		ed_by_sp.setdefault(e.sewing_plan, []).append(e)
	er_by_parent = {}
	for row in entry_rows:
		er_by_parent.setdefault(row.parent, []).append(row)

	# Step 6: Assemble sewing_data using in-memory lookups
	sewing_data = {}
	mrp_doc = frappe.get_single("MRP Settings")
	inspection_key = mrp_doc.sewing_plan_inspection_type.lower().replace(" ", "_")

	for sp_name in sp_names:
		sp = sp_map[sp_name]
		ipd = lot_ipd_map[sp.lot]
		is_set_item, pack_attr, primary_attr, set_attr = ipd_data_map[ipd]

		sewing_data.setdefault(sp.lot, {})
		sewing_data[sp.lot].setdefault(sp_name, {
			"details": {
				"item": sp.item,
				"lot": sp.lot,
				"supplier": sp.supplier,
				"primary_values": ipd_primary_map[ipd],
				"is_set_item": is_set_item,
				"pack_attr": pack_attr,
				"primary_attr": primary_attr,
				"set_attr": set_attr
			},
			"colours": {}
		})

		# Process order details (in-memory)
		for item in od_by_parent.get(sp_name, []):
			attr_details = variant_attr_map.get(item.item_variant, {})
			set_comb = update_if_string_instance(item.set_combination)
			major_colour = set_comb.get("major_colour", "")
			colour = major_colour
			size = attr_details.get(primary_attr, "")
			part = None
			real_colour = colour
			if is_set_item:
				variant_colour = attr_details.get(pack_attr, "")
				part = attr_details.get(set_attr, "")
				real_colour = variant_colour
				if set_comb.get('major_part') != part:
					colour = f"{variant_colour} ({major_colour})"

			sewing_data[sp.lot][sp_name]['colours'].setdefault(colour, {
				"values": {},
				"part": part,
				"colour": colour,
				"variant_colour": real_colour,
				"set_combination": set_comb,
				"qty": 0,
				"inspection_total": {
					"pre_final": 0,
					"final_inspection": 0,
					inspection_key: 0,
				}
			})
			sewing_data[sp.lot][sp_name]['colours'][colour]["qty"] += item.quantity
			sewing_data[sp.lot][sp_name]['colours'][colour]["values"].setdefault(size, {
				"order_qty": 0,
				"data_entry": 0,
				"pre_final": 0,
				"final_inspection": 0,
			})
			sewing_data[sp.lot][sp_name]['colours'][colour]["values"][size]['order_qty'] += item.quantity
			sewing_data[sp.lot][sp_name]['colours'][colour]["values"][size]['pre_final'] += item.pre_final
			sewing_data[sp.lot][sp_name]['colours'][colour]["values"][size]['final_inspection'] += item.final_inspection
			sewing_data[sp.lot][sp_name]['colours'][colour]['inspection_total']['final_inspection'] += item.final_inspection
			sewing_data[sp.lot][sp_name]['colours'][colour]['inspection_total']['pre_final'] += item.pre_final

		# Process entry details (in-memory)
		for entry in ed_by_sp.get(sp_name, []):
			new_key = entry.input_type.lower().replace(" ", "_")
			for row in er_by_parent.get(entry.name, []):
				attr_details = variant_attr_map.get(row.item_variant, {})
				set_comb = update_if_string_instance(row.set_combination)
				major_colour = set_comb.get("major_colour", "")
				colour = major_colour
				size = attr_details.get(primary_attr, "")
				part = None
				real_colour = colour
				if is_set_item:
					variant_colour = attr_details.get(pack_attr, "")
					part = attr_details.get(set_attr, "")
					real_colour = variant_colour
					if set_comb.get('major_part') != part:
						colour = f"{variant_colour} ({major_colour})"

				if new_key == inspection_key:
					sewing_data[sp.lot][sp_name]['colours'][colour]['inspection_total'][new_key] += row.quantity
				sewing_data[sp.lot][sp_name]['colours'][colour]['values'][size].setdefault(new_key, 0)
				sewing_data[sp.lot][sp_name]['colours'][colour]['values'][size][new_key] += row.quantity

	diff_keys = {}
	for row in mrp_doc.sewing_plan_input_orders:
		diff_keys[row.input_type.lower().replace(" ", "_")] = row.difference_from.lower().replace(" ", "_")

	# Fetch allowance percentages for each input type
	allowances = {}
	for row in mrp_doc.sewing_plan_input_orders:
		input_key = row.input_type.lower().replace(" ", "_")
		allowance = frappe.db.get_value("Sewing Plan Input Type", row.input_type, "allowance") or 0
		allowances[input_key] = allowance

	# Calculate remaining quantities for each input type
	# remaining = base_qty - already_entered (exact, no allowance)
	for lot in sewing_data:
		for sp_name in sewing_data[lot]:
			for colour in sewing_data[lot][sp_name]['colours']:
				for size in sewing_data[lot][sp_name]['colours'][colour]['values']:
					size_data = sewing_data[lot][sp_name]['colours'][colour]['values'][size]
					for input_type_key, diff_from_key in diff_keys.items():
						base_qty = size_data.get(diff_from_key, 0)
						entered_qty = size_data.get(input_type_key, 0)
						remaining_key = f"{input_type_key}_remaining"
						size_data[remaining_key] = max(0, base_qty - entered_qty)

	return {
		"data": sewing_data,
		"diff": diff_keys,
		"allowances": allowances,
		"inspection_type": inspection_key
	}

@frappe.whitelist()
def submit_data_entry_log(payload):
	payload = update_if_string_instance(payload)
	details = payload['quantities']['details']
	lot = details['lot']
	ipd_fields = [
		'set_item_attribute', 
		'dependent_attribute', 
		'stiching_out_stage'
	]
	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_details = list(frappe.get_value("Item Production Detail", ipd, ipd_fields))
	items = []
	for colour in payload['quantities']['colours']:
		check = False
		for size in payload['quantities']['colours'][colour]['values']:
			if payload['quantities']['colours'][colour]['values'][size]['data_entry'] > 0:
				check = True
			if check:
				break	
		if check:
			variant_colour = payload['quantities']['colours'][colour]['variant_colour']
			for size in payload['quantities']['colours'][colour]['values']:
				attrs = {
					details['primary_attr']: size,
					ipd_details[1]: ipd_details[2],
				}
				if details['is_set_item']:
					attrs[ipd_details[0]] = payload['quantities']['colours'][colour]['part']

				attrs[details['pack_attr']] = variant_colour
				variant = get_or_create_variant(details['item'], attrs)
				items.append({
					"item_variant": variant,
					"set_combination": frappe.json.dumps(payload['quantities']['colours'][colour]['set_combination']),
					"quantity": payload['quantities']['colours'][colour]['values'][size]['data_entry']
				})

	new_doc = frappe.new_doc("Sewing Plan Entry Detail")
	new_doc.sewing_plan = payload['plan']
	new_doc.input_type = payload['input_type']
	new_doc.received_type = payload['grn_item_type']
	new_doc.work_station = payload['work_station']
	new_doc.entry_date = payload['date']
	new_doc.entry_time = payload['time']
	new_doc.posting_date = frappe.utils.nowdate()
	new_doc.posting_time = frappe.utils.nowtime()
	new_doc.set("sewing_plan_details", items)
	new_doc.save(ignore_permissions=True)
	return new_doc.name

@frappe.whitelist()
def get_scr_data(supplier, lot):
	sp_list = frappe.get_all("Sewing Plan", filters={"lot": lot, "supplier": supplier}, pluck="name")
	if not sp_list:
		return {
			"status": "failed",
			"message": f"No Data for supplier {supplier} and lot {lot}",
			"data": []
		}
	
	sp_entry_list = frappe.get_all("Sewing Plan Entry Detail", filters={
		"sewing_plan": ["in", sp_list]
	})

	mrp_doc = frappe.get_single("MRP Settings")
	type_wise_diff_input = mrp_doc.type_wise_diff_summary

	received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	scr_data = {}
	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute", "item"]
	is_set_item, pack_attr, primary_attr, set_attr, item_name = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	primary_values = get_ipd_primary_values(ipd)
	colours = []

	for sp_name in sp_list:
		sp_doc = frappe.get_doc("Sewing Plan", sp_name)
		for row in sp_doc.sewing_plan_order_details:
			size, part, colour, v_colour = get_colour_size_data(row.set_combination, row.item_variant, is_set_item, pack_attr, set_attr, primary_attr)
			if colour not in colours:
				colours.append(colour)

			set_comb = update_if_string_instance(row.set_combination)
			scr_data.setdefault(colour, {
				"values": {},
				"part": part,
				"colour": colour,
				"variant_colour": v_colour,
				"set_combination": set_comb,
				"type_wise_total": {},
			})
			scr_data[colour]["values"].setdefault(size, {})
			input_key = "Order Qty"
			scr_data[colour]["values"][size].setdefault(input_key, 0)
			scr_data[colour]["values"][size][input_key] += row.quantity

	for sp_entry in sp_entry_list:
		sp_doc = frappe.get_doc("Sewing Plan Entry Detail", sp_entry)
		for row in sp_doc.sewing_plan_details:
			size, part, colour, v_colour = get_colour_size_data(row.set_combination, row.item_variant, is_set_item, pack_attr, set_attr, primary_attr)
			
			input_key = sp_doc.input_type
			if input_key == type_wise_diff_input:
				if received_type != sp_doc.received_type:
					input_key = sp_doc.received_type
			else:
				if received_type != sp_doc.received_type:
					input_key += " " + sp_doc.received_type

			set_comb = update_if_string_instance(row.set_combination)
			scr_data.setdefault(colour, {
				"values": {},
				"part": part,
				"colour": colour,
				"variant_colour": v_colour,
				"set_combination": set_comb,
				"type_wise_total": {},
			})
			scr_data[colour]["values"].setdefault(size, {})
			scr_data[colour]["values"][size].setdefault(input_key, 0)
			scr_data[colour]["values"][size][input_key] += row.quantity
			if colour not in colours:
				colours.append(colour)

	diff_keys = {}
	for row in mrp_doc.sewing_plan_input_orders:
		diff_keys[row.input_type] = row.difference_from

	headers = ["Order Qty"]
	unlinked_types = []
	for colour in scr_data:
		for size in scr_data[colour]["values"]:
			new_size_wise_keys = {}
			for input_type in scr_data[colour]["values"][size]:
				if input_type == type_wise_diff_input:
					new_key = input_type + " Total"
					new_size_wise_keys.setdefault(new_key, 0)
					new_size_wise_keys[new_key] += scr_data[colour]["values"][size][input_type]
				else:
					if input_type in diff_keys:
						new_key = input_type + " Balance"
						new_size_wise_keys[new_key] = scr_data[colour]["values"][size][input_type] - scr_data[colour]['values'][size].get(diff_keys[input_type], 0)
					elif input_type not in headers and input_type not in unlinked_types:
						new_key = type_wise_diff_input + " Total"
						new_size_wise_keys.setdefault(new_key, 0)
						new_size_wise_keys[new_key] += scr_data[colour]["values"][size][input_type]
						unlinked_types.append(input_type)
					elif input_type != 'Order Qty':
						new_key = type_wise_diff_input + " Total"
						new_size_wise_keys.setdefault(new_key, 0)
						new_size_wise_keys[new_key] += scr_data[colour]["values"][size][input_type]

			scr_data[colour]["values"][size].update(new_size_wise_keys)		

	for colour in scr_data:
		for size in scr_data[colour]["values"]:
			if type_wise_diff_input and type_wise_diff_input in scr_data[colour]['values'][size] and type_wise_diff_input in diff_keys:
				scr_data[colour]['values'][size][type_wise_diff_input+ " Balance"] = scr_data[colour]['values'][size].get(type_wise_diff_input+ " Total", 0) - scr_data[colour]['values'][size].get(diff_keys[type_wise_diff_input], 0)

	for key in diff_keys:
		if key == type_wise_diff_input:
			headers.append(key)
			headers = headers + unlinked_types 
			headers.append(key+ " Total")
			headers.append(key+ " Balance")
		else:

			headers.append(key)
			headers.append(key + " Balance")	

	for colour in scr_data:
		scr_data[colour]["type_wise_total"] = {}
		for header in headers:
			total = 0
			for size in scr_data[colour]["values"]:
				total += scr_data[colour]["values"][size].get(header, 0)
			scr_data[colour]["type_wise_total"][header] = total
	
	return {
		"status": "success",
		"primary_values": primary_values,
		"data": scr_data,
		"colours": colours,
		"headers": headers,
		"is_set_item": is_set_item,
		"set_attr": set_attr,
		"item": item_name
	}


def get_colour_size_data(set_combination, item_variant, is_set_item, pack_attr, set_attr, primary_attr):
	set_comb = update_if_string_instance(set_combination)
	major_colour = set_comb["major_colour"]
	colour = major_colour
	attr_details = get_variant_attr_details(item_variant)
	size = attr_details[primary_attr]
	part = None
	real_colour = colour
	if is_set_item:
		variant_colour = attr_details[pack_attr]
		part = attr_details[set_attr]
		real_colour = variant_colour
		if set_comb['major_part'] != part:
			colour = f"{variant_colour} ({major_colour})"

	return size, part, colour, real_colour	

@frappe.whitelist()
def get_sewing_plan_dpr_data(supplier, dpr_date, work_station=None, input_type=None):
	sp_entry_list = get_sp_entry_details(supplier, dpr_date=dpr_date, work_station=work_station, input_type=input_type)
	dpr_data = {}
	for sp_entry in sp_entry_list:
		sp_doc = frappe.get_doc("Sewing Plan Entry Detail", sp_entry)
		dpr_data.setdefault(sp_doc.input_type, {})
		lot = frappe.get_value("Sewing Plan", sp_doc.sewing_plan, "lot")
		ipd = frappe.get_value("Lot", lot, "production_detail")
		ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute", "item"]
		is_set_item, pack_attr, primary_attr, set_attr, item_name = frappe.get_value("Item Production Detail", ipd, ipd_fields)

		rec_type = sp_doc.received_type
		in_type = sp_doc.input_type
		ws = sp_doc.work_station
		dpr_data[in_type].setdefault(lot, {
			"details": {},
			"is_set_item": is_set_item,
			"pack_attr": pack_attr,
			"set_attr": set_attr,
			"item": item_name,
			"primary_values": get_ipd_primary_values(ipd),
		})
		dpr_data[in_type][lot]['details'].setdefault(ws, {})
		dpr_data[in_type][lot]['details'][ws].setdefault(rec_type, {})
		
		for row in sp_doc.sewing_plan_details:
			size, part, colour, v_colour = get_colour_size_data(row.set_combination, row.item_variant, is_set_item, pack_attr, set_attr, primary_attr)
			set_comb = update_if_string_instance(row.set_combination)
			dpr_data[in_type][lot]['details'][ws][rec_type].setdefault(colour, {
				"values": {},
				"part": part,
				"colour": colour,
				"varaint_colour": v_colour,
				"set_combination": set_comb,
				"total": 0
			})
			dpr_data[in_type][lot]['details'][ws][rec_type][colour]["values"].setdefault(size, 0)
			dpr_data[in_type][lot]['details'][ws][rec_type][colour]["values"][size] += row.quantity
			dpr_data[in_type][lot]['details'][ws][rec_type][colour]['total'] += row.quantity

	mrp_doc = frappe.get_single("MRP Settings")
	orders = []
	for row in mrp_doc.sewing_plan_input_orders:
		orders.append(row.input_type)

	return {
		"headers": orders,
		"dpr_data": dpr_data,
	}	

@frappe.whitelist()
def get_sewing_plan_entries(supplier, input_type=None, work_station=None, lot_name=None):
	previous_days = frappe.db.get_single_value("MRP Settings", "previous_day_entries")
	previous_days = int(previous_days or 0)
	
	data = frappe.db.sql(
		"""
			SELECT 
				t1.entry_date as date 
				FROM `tabSewing Plan Entry Detail` t1
				JOIN `tabSewing Plan` t2 
				ON t1.sewing_plan = t2.name
			WHERE
				t2.supplier = %(supplier)s
			GROUP BY 
				t1.entry_date
			ORDER BY 
				t1.entry_date DESC
		""", {"supplier": supplier}, as_dict=True
	)
	
	cancellable_dates = set()
	for i, row in enumerate(data):
		if i < previous_days:
			cancellable_dates.add(row['date'])
		else:
			break
	
	entry_data = {}
	for row in data:
		sp_entries = get_sp_entry_details(supplier, dpr_date=row['date'], work_station=work_station, input_type=input_type)
		for sp_entry in sp_entries:
			sp_doc = frappe.get_doc("Sewing Plan Entry Detail", sp_entry)
			lot = frappe.get_value("Sewing Plan", sp_doc.sewing_plan, "lot")
			if lot_name and lot_name != lot:
				continue
			ipd = frappe.get_value("Lot", lot, "production_detail")
			ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute", "item"]
			is_set_item, pack_attr, primary_attr, set_attr, item_name = frappe.get_value("Item Production Detail", ipd, ipd_fields)
			
			is_cancellable = sp_doc.entry_date in cancellable_dates
			
			entry_data.setdefault(sp_entry, {
				"lot": lot,
				"details": {},
				"work_station": sp_doc.work_station,
				"input_type": sp_doc.input_type,
				"received_type": sp_doc.received_type,
				"item_name": item_name,
				"primary_values": get_ipd_primary_values(ipd),
				"is_set_item": is_set_item,
				"pack_attr": pack_attr,
				"set_attr": set_attr,
				"is_cancellable": is_cancellable,
				"entry_date": sp_doc.entry_date
			})
			for row in sp_doc.sewing_plan_details:
				size, part, colour, v_colour = get_colour_size_data(row.set_combination, row.item_variant, is_set_item, pack_attr, set_attr, primary_attr)
				set_comb = update_if_string_instance(row.set_combination)
				entry_data[sp_entry]['details'].setdefault(colour, {
					"values": {},
					"part": part,
					"colour": colour,
					"variant_colour": v_colour,
					"set_combination": set_comb,
					"total": 0
				})
				entry_data[sp_entry]['details'][colour]["values"].setdefault(size, 0)
				entry_data[sp_entry]['details'][colour]["values"][size] += row.quantity
				entry_data[sp_entry]['details'][colour]['total'] += row.quantity

	return entry_data

@frappe.whitelist()
def cancel_sewing_plan_entry(doc_id):
	frappe.delete_doc("Sewing Plan Entry Detail", doc_id, ignore_permissions=True)

@frappe.whitelist()
def update_sewing_plan_data(payload):
	payload = update_if_string_instance(payload)
	ipd = frappe.get_value("Lot", payload['lot'], "production_detail")
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute", "item", "dependent_attribute", "stiching_out_stage"]
	is_set_item, pack_attr, primary_attr, set_attr, item_name, dept_attr, stich_out_stage = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	d = {}
	action = payload.get('action', 'update')
	for row in payload['rows']:
		for size in row['qty']:
			attrs = {
				primary_attr: size,
				pack_attr: row['colour'],
				dept_attr: stich_out_stage,
			}
			if is_set_item:
				attrs[set_attr] = row['part']
			variant = get_or_create_variant(item_name , attrs)
			set_comb = update_if_string_instance(row['set_combination'])
			key = (variant, tuple(sorted(set_comb.items())))
			d.setdefault(key, 0)
			if action == 'revert':
				d[key] = 0
			else:
				d[key] += row['qty'][size][payload['inspection_type']]
	
	sp_doc = frappe.get_doc("Sewing Plan", payload['plan'])	
	inspection_type = frappe.db.get_single_value("MRP Settings", "sewing_plan_inspection_type")
	inspection_key = inspection_type.lower().replace(" ", "_")

	for row in sp_doc.sewing_plan_order_details:
		set_comb = update_if_string_instance(row.set_combination)
		key = (row.item_variant, tuple(sorted(set_comb.items())))
		if key in d:
			if payload['inspection_type'] == inspection_key:
				row.pre_final = d[key]
			else:
				row.final_inspection = d[key]

	sp_doc.save(ignore_permissions=True)			

	return "Success"

@frappe.whitelist()
def get_monthly_summary_data(supplier, start_date, end_date, input_type=None, show_grn=0):
	if int(show_grn):
		data = frappe.db.sql(
			"""
				SELECT
					grn.posting_date AS entry_date,
					lot.item AS style,
					CASE WHEN ipd.is_set_item = 1
						THEN iva.attribute_value
						ELSE '' END AS part,
					SUM(grni.quantity) AS qty
				FROM `tabGoods Received Note` grn
				JOIN `tabGoods Received Note Item` grni ON grni.parent = grn.name
				LEFT JOIN `tabLot` lot ON lot.name = grn.lot
				LEFT JOIN `tabItem Production Detail` ipd ON ipd.name = lot.production_detail
				LEFT JOIN `tabItem Variant Attribute` iva
					ON iva.parent = grni.item_variant
					AND iva.attribute = ipd.set_item_attribute
					AND ipd.is_set_item = 1
				WHERE grn.supplier = %(supplier)s
					AND grn.against = 'Work Order'
					AND grn.posting_date BETWEEN %(start_date)s AND %(end_date)s
					AND grn.docstatus = 1
					AND EXISTS (
						SELECT 1 FROM `tabSewing Plan` sp
						WHERE sp.work_order = grn.against_id
					)
				GROUP BY grn.posting_date, lot.item, part
				ORDER BY grn.posting_date, lot.item, part
			""",
			{
				"supplier": supplier,
				"start_date": start_date,
				"end_date": end_date,
			},
			as_dict=True,
		)
	else:
		data = frappe.db.sql(
			"""
				SELECT
					sped.entry_date,
					sp.item AS style,
					CASE WHEN ipd.is_set_item = 1
						THEN iva.attribute_value
						ELSE '' END AS part,
					SUM(spd.quantity) AS qty
				FROM `tabSewing Plan Entry Detail` sped
				JOIN `tabSewing Plan Detail` spd ON spd.parent = sped.name
				JOIN `tabSewing Plan` sp ON sp.name = sped.sewing_plan
				LEFT JOIN `tabLot` lot ON lot.name = sp.lot
				LEFT JOIN `tabItem Production Detail` ipd ON ipd.name = lot.production_detail
				LEFT JOIN `tabItem Variant Attribute` iva
					ON iva.parent = spd.item_variant
					AND iva.attribute = ipd.set_item_attribute
					AND ipd.is_set_item = 1
				WHERE sp.supplier = %(supplier)s
					AND sped.input_type = %(input_type)s
					AND sped.entry_date BETWEEN %(start_date)s AND %(end_date)s
				GROUP BY sped.entry_date, sp.item, part
				ORDER BY sped.entry_date, sp.item, part
			""",
			{
				"supplier": supplier,
				"input_type": input_type,
				"start_date": start_date,
				"end_date": end_date,
			},
			as_dict=True,
		)

	# Build column key: "STYLE (Part)" for set items, just "STYLE" otherwise
	def col_key(r):
		if r.part:
			return f"{r.style} ({r.part})"
		return r.style

	styles = sorted({col_key(r) for r in data})

	date_map = {}
	for r in data:
		date_str = str(r.entry_date)
		key = col_key(r)
		if date_str not in date_map:
			date_map[date_str] = {s: 0 for s in styles}
			date_map[date_str]["_total"] = 0
		date_map[date_str][key] = r.qty
		date_map[date_str]["_total"] += r.qty

	rows = []
	grand_total = {s: 0 for s in styles}
	grand_total["total"] = 0
	for date_str in sorted(date_map.keys()):
		row = {"date": date_str}
		for s in styles:
			row[s] = date_map[date_str][s]
			grand_total[s] += date_map[date_str][s]
		row["total"] = date_map[date_str]["_total"]
		grand_total["total"] += date_map[date_str]["_total"]
		rows.append(row)

	return {
		"styles": styles,
		"rows": rows,
		"grand_total": grand_total,
	}

@frappe.whitelist()
def get_fi_updates_data(supplier):
	sp_list = frappe.get_all("Sewing Plan", filters={"supplier": supplier}, pluck="name")
	
	if not sp_list:
		return {"data": []}
	
	colour_part_data = []
	seen_combinations = set()
	
	for sp_name in sp_list:
		sp_doc = frappe.get_doc("Sewing Plan", sp_name)
		lot = sp_doc.lot
		item = sp_doc.item
		ipd = frappe.get_value("Lot", lot, "production_detail")
		ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
		is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)
		
		for row in sp_doc.sewing_plan_order_details:
			# Only include rows without FI date
			if row.fi_date:
				continue
			
			size, part, colour, v_colour = get_colour_size_data(row.set_combination, row.item_variant, is_set_item, pack_attr, set_attr, primary_attr)
			
			# Unique key includes lot to show same colour/part in different lots
			key = (lot, colour, part)
			if key not in seen_combinations:
				seen_combinations.add(key)
				colour_part_data.append({
					"colour": colour,
					"part": part,
					"sewing_plan": sp_name,
					"lot": lot,
					"item": item,
					"is_set_item": is_set_item,
					"set_attr": set_attr
				})
	
	return {"data": colour_part_data}

@frappe.whitelist()
def update_fi_dates(data):
	data = update_if_string_instance(data)
	
	# Group data by sewing_plan for efficient updates
	sp_updates = {}
	for row in data:
		sp_name = row.get('sewing_plan')
		lot = row.get('lot')
		if not sp_name or not lot:
			continue
		
		if sp_name not in sp_updates:
			sp_updates[sp_name] = {"lot": lot, "rows": []}
		sp_updates[sp_name]["rows"].append(row)
	
	# Update each sewing plan
	for sp_name, sp_data in sp_updates.items():
		lot = sp_data["lot"]
		rows = sp_data["rows"]
		
		ipd = frappe.get_value("Lot", lot, "production_detail")
		ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
		is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)
		
		sp_doc = frappe.get_doc("Sewing Plan", sp_name)
		
		for update_row in rows:
			colour = update_row.get('colour')
			part = update_row.get('part')
			fi_date = update_row.get('date')
			
			# Update all matching rows in sewing_plan_order_details
			for sp_row in sp_doc.sewing_plan_order_details:
				size, row_part, row_colour, v_colour = get_colour_size_data(sp_row.set_combination, sp_row.item_variant, is_set_item, pack_attr, set_attr, primary_attr)
				
				if row_colour == colour and row_part == part:
					sp_row.fi_date = fi_date if fi_date else None
					
		sp_doc.save(ignore_permissions=True)
	
	return "Success"
