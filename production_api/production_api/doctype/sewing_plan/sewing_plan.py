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
	data = {}
	received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	sp_list = frappe.get_all("Sewing Plan", filters={
		"supplier": supplier
	}, pluck="name")
	total = {}
	for sp_name in sp_list:
		sp_doc = frappe.get_doc("Sewing Plan", sp_name)
		lot = sp_doc.lot
		item = sp_doc.item
		primary_attr = frappe.get_value("Item", item, "primary_attribute")
		wo_doc = frappe.get_doc("Work Order", sp_doc.work_order)
		for row in wo_doc.work_order_calculated_items:
			key = get_sp_key(row, item, lot, primary_attr)
			attr_details = get_variant_attr_details(row.item_variant)
			data.setdefault(key, {
				"item": item,
				"lot": lot,
				"item_variant": row.item_variant,
				"attr_details": attr_details,
				"pack_attr": ipd_settings.default_packing_attribute,
				"set_attr": ipd_settings.default_set_item_attribute,
			})
			input_key = "GRN Qty"
			data[key].setdefault(input_key, 0)
			data[key][input_key] += row.received_qty
			
			total.setdefault(input_key, 0)
			total[input_key] += row.received_qty
		
		for row in sp_doc.sewing_plan_order_details:
			key = get_sp_key(row, item, lot, primary_attr)

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

		sp_entry_list = frappe.get_all("Sewing Plan Entry Detail", filters={
			"sewing_plan": sp_name
		}, pluck="name")

		total.setdefault("checking_total", 0)
		
		for sp_entry in sp_entry_list:
			spe_doc = frappe.get_doc("Sewing Plan Entry Detail", sp_entry)
			for row in spe_doc.sewing_plan_details:
				key = get_sp_key(row, item, lot, primary_attr)
				input_key = spe_doc.input_type
				if input_key == type_wise_diff_input:
					total["checking_total"] += row.quantity
					data[key].setdefault("checking_total", 0)
					data[key]["checking_total"] += row.quantity
					if received_type != spe_doc.received_type:
						input_key = spe_doc.received_type
				else:
					if received_type != spe_doc.received_type:
						input_key += " " + spe_doc.received_type
				total.setdefault(input_key, 0)
				total[input_key] += row.quantity
				data[key].setdefault(input_key, 0)
				data[key][input_key] += row.quantity

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
	
	sp_list = frappe.get_all("Sewing Plan", filters=filters, pluck="name")
	if not sp_list:
		return []
	
	sewing_data = {}
	mrp_doc = frappe.get_single("MRP Settings")
	inspection_key = mrp_doc.sewing_plan_inspection_type.lower().replace(" ", "_")
	for sp_name in sp_list:
		sp_doc = frappe.get_doc("Sewing Plan", sp_name)	
		ipd = frappe.get_value("Lot", sp_doc.lot, "production_detail")
		sewing_data.setdefault(sp_doc.lot, {})
		ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
		is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)
		sewing_data[sp_doc.lot].setdefault(sp_name, {
			"details": {
				"item": sp_doc.item,
				"lot": sp_doc.lot,
				"supplier": sp_doc.supplier,
				"primary_values": get_ipd_primary_values(ipd),
				"is_set_item": is_set_item,
				"pack_attr": pack_attr,
				"primary_attr": primary_attr,
				"set_attr": set_attr
			},
			"colours": {}
		})

		for item in sp_doc.sewing_plan_order_details:
			size, part, colour, v_colour = get_colour_size_data(item.set_combination, item.item_variant, is_set_item, pack_attr, set_attr, primary_attr)
			set_comb = update_if_string_instance(item.set_combination)
			sewing_data[sp_doc.lot][sp_name]['colours'].setdefault(colour, {
				"values": {},
				"part": part,
				"colour": colour,
				"variant_colour": v_colour,
				"set_combination": set_comb,
				"qty": 0,
				"inspection_total": {
					"pre_final": 0,
					"final_inspection": 0,
					inspection_key: 0,
				}
			})
			sewing_data[sp_doc.lot][sp_name]['colours'][colour]["qty"] += item.quantity
			sewing_data[sp_doc.lot][sp_name]['colours'][colour]["values"].setdefault(size, {
				"order_qty": 0,
				"data_entry": 0,
				"pre_final": 0,
				"final_inspection": 0,
			})
			sewing_data[sp_doc.lot][sp_name]['colours'][colour]["values"][size]['order_qty'] += item.quantity
			sewing_data[sp_doc.lot][sp_name]['colours'][colour]["values"][size]['pre_final'] += item.pre_final
			sewing_data[sp_doc.lot][sp_name]['colours'][colour]["values"][size]['final_inspection'] += item.final_inspection
			sewing_data[sp_doc.lot][sp_name]['colours'][colour]['inspection_total']['final_inspection'] += item.final_inspection
			sewing_data[sp_doc.lot][sp_name]['colours'][colour]['inspection_total']['pre_final'] += item.pre_final
		
		sp_entry_list = frappe.get_all("Sewing Plan Entry Detail", filters={
			"sewing_plan": sp_name
		}, pluck="name")

		for sp_entry in sp_entry_list:
			spe_doc = frappe.get_doc("Sewing Plan Entry Detail", sp_entry)
			for row in spe_doc.sewing_plan_details:
				size, part, colour, v_colour = get_colour_size_data(row.set_combination, row.item_variant, is_set_item, pack_attr, set_attr, primary_attr)
				new_key = spe_doc.input_type.lower().replace(" ", "_")
				if new_key == inspection_key:
					sewing_data[sp_doc.lot][sp_name]['colours'][colour]['inspection_total'][new_key] += row.quantity
				sewing_data[sp_doc.lot][sp_name]['colours'][colour]['values'][size].setdefault(new_key, 0)
				sewing_data[sp_doc.lot][sp_name]['colours'][colour]['values'][size][new_key] += row.quantity
	
	
	diff_keys = {}
	for row in mrp_doc.sewing_plan_input_orders:
		diff_keys[row.input_type.lower().replace(" ", "_")] = row.difference_from.lower().replace(" ", "_")		

	return {
		"data": sewing_data,
		"diff": diff_keys,
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
	print(sp_list)
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

			scr_data[colour]["values"][size].setdefault(input_key, 0)
			scr_data[colour]["values"][size][input_key] += row.quantity

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
						new_size_wise_keys[new_key] = scr_data[colour]["values"][size][input_type] - scr_data[colour]['values'][size][diff_keys[input_type]]
					elif input_type not in headers and input_type not in unlinked_types:
						new_key = type_wise_diff_input + " Total"
						new_size_wise_keys.setdefault(new_key, 0)
						new_size_wise_keys[new_key] += scr_data[colour]["values"][size][input_type]
						unlinked_types.append(input_type)
			scr_data[colour]["values"][size].update(new_size_wise_keys)		

	for colour in scr_data:
		for size in scr_data[colour]["values"]:
			if type_wise_diff_input in scr_data[colour]['values'][size]:
				scr_data[colour]['values'][size][type_wise_diff_input+ " Balance"] = scr_data[colour]['values'][size][type_wise_diff_input+ " Total"] - scr_data[colour]['values'][size][diff_keys[type_wise_diff_input]]

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
	
	print(scr_data)
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
	data = frappe.db.sql(
		f"""
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
			LIMIT {previous_days}
		""", {"supplier": supplier}, as_dict=True
	)
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
				"set_attr": set_attr
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
