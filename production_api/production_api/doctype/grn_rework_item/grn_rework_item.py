# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from production_api.utils import update_if_string_instance

class GRNReworkItem(Document):
	pass

@frappe.whitelist()
def revert_reworked_item(docname):
	doc = frappe.get_doc("GRN Rework Item", docname)
	warehouse = doc.warehouse
	single_doc = frappe.get_single("Stock Settings")
	accepted = single_doc.default_received_type
	rejected = single_doc.default_rejected_type	
	sl_entries = []
	for row in doc.grn_rework_item_details:
		if row.completed == 0:
			continue
		if row.rejection > 0:
			sl_entries.append({
				"item": row.item_variant,
				"warehouse": warehouse,
				"received_type": rejected,
				"lot": doc.lot,
				"voucher_type": "GRN Rework Item",
				"voucher_no": docname,
				"voucher_detail_no": row.name,
				"qty": row.rejection * -1,
				"uom": row.uom,
				"rate": 0,
				"valuation_rate": 0,
				"is_cancelled": 0,
				"posting_date": frappe.utils.nowdate(),
				"posting_time": frappe.utils.nowtime(),
			})
		if row.quantity - row.rejection > 0:
			sl_entries.append({
				"item": row.item_variant,
				"warehouse": warehouse,
				"received_type": accepted,
				"lot": doc.lot,
				"voucher_type": "GRN Rework Item",
				"voucher_no": docname,
				"voucher_detail_no": row.name,
				"qty":  (row.quantity - row.rejection) * -1,
				"uom": row.uom,
				"rate": 0,
				"valuation_rate": 0,
				"is_cancelled": 0,
				"posting_date": frappe.utils.nowdate(),
				"posting_time": frappe.utils.nowtime(),
			})			
		sl_entries.append({
			"item": row.item_variant,
			"warehouse": warehouse,
			"received_type": row.received_type,
			"lot": doc.lot,
			"voucher_type": "GRN Rework Item",
			"voucher_no": docname,
			"voucher_detail_no": row.name,
			"qty": row.quantity,
			"uom": row.uom,
			"rate": 0,
			"valuation_rate": 0,
			"is_cancelled": 0,
			"posting_date": frappe.utils.nowdate(),
			"posting_time": frappe.utils.nowtime(),
		})	
		row.completed = 0
		row.rejection = 0
		row.reworked = 0
	doc.completed = 0	
	doc.set("grn_reworked_item_details", [])
	doc.save(ignore_permissions=True)	
	from production_api.mrp_stock.stock_ledger import make_sl_entries
	make_sl_entries(sl_entries)

@frappe.whitelist()
def get_rework_items(lot):
	filters = {
		"completed": 0,
	}
	if lot:
		filters["lot"] = lot
	rework_items = frappe.get_all("GRN Rework Item", filters=filters, pluck="name", order_by="name" )
	data = {
		"report_detail": {},
		"types": [],
	}
	from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import get_variant_attr_details
	for item in rework_items:
		doc = frappe.get_doc("GRN Rework Item", item)
		ipd = frappe.get_cached_value("Lot", doc.lot, "production_detail")
		ipd_fields = ['packing_attribute', 'primary_item_attribute', 'is_set_item', 'set_item_attribute']
		pack_attr, primary_attr, set_item, set_attr = frappe.get_cached_value("Item Production Detail", ipd, ipd_fields)
		data["report_detail"].setdefault(item, {
			"grn_number": doc.grn_number,
			"lot": doc.lot,
			"item": doc.item,
			"rework_detail": {},
			"size": primary_attr,
			"types": {}
		})
		for row in doc.grn_rework_item_details:
			if row.completed == 1:
				continue
			attr_details = get_variant_attr_details(row.item_variant)
			key = row.received_type+"-"+attr_details[pack_attr]
			if set_item:
				key += "-"+attr_details[set_attr]
			data["report_detail"][item]['rework_detail'].setdefault(key, {
				"changed": 0,
				'items': [],
			})
			if row.received_type not in data['types']:
				data['types'].append(row.received_type)
				
			data["report_detail"][item]['types'].setdefault(row.received_type, 0)
			data["report_detail"][item]['types'][row.received_type] += row.quantity - row.reworked
			data["report_detail"][item]['rework_detail'][key]['items'].append({
				primary_attr : attr_details[primary_attr],
				"rework_qty": row.quantity - row.reworked,
				"rejected": row.rejection, 
				"rework": 0,
				"set_combination": frappe.json.loads(row.set_combination),
				"row_name": row.name,
				"variant": row.item_variant,
				"received_type": row.received_type,
				"uom": row.uom,
			})
	return data	

@frappe.whitelist()
def update_rejected_quantity(rejection_data, completed:int, lot):
	rejection_data = update_if_string_instance(rejection_data)
	for row in rejection_data:
		frappe.db.sql(
			"""
				UPDATE `tabGRN Rework Item Detail` SET rejection = %(reject_qty)s, 
				completed = %(completed)s WHERE name = %(name)s 
			""", {
				"reject_qty": row['rejected'],
				"name": row['row_name'],
				"completed": completed, 
			}
		)

	parent = frappe.db.sql(
		"""
			SELECT parent FROM `tabGRN Rework Item Detail` WHERE name = %(row_name)s
		""", {
			"row_name": rejection_data[0]['row_name']
		}, as_dict=True
	)[0]['parent']	
	if completed:
		convert_received_type(rejection_data, parent, lot)

	incompleted = frappe.db.sql(
		"""
			SELECT name FROM `tabGRN Rework Item Detail` WHERE parent = %(parent)s 
			AND completed = 0
		""", {
			"parent": parent
		}, as_dict=True
	)

	if not incompleted:
		frappe.db.sql(
			"""
				UPDATE `tabGRN Rework Item` SET completed = 1 WHERE name = %(name)s
			""", {
				"name": parent
			}
		)

def convert_received_type(rejection_data, docname, lot):
	warehouse = frappe.db.sql(
		"""
			SELECT warehouse FROM `tabGRN Rework Item` WHERE name = %(docname)s
		""", {
			"docname": docname
		}, as_dict=True
	)[0]['warehouse']
	doc = frappe.get_single("Stock Settings")
	accepted = doc.default_received_type
	rejected = doc.default_rejected_type	
	sl_entries = []
	table_data = []
	for row in rejection_data:
		sl_entries.append({
			"item": row['variant'],
			"warehouse": warehouse,
			"received_type": row['received_type'],
			"lot": lot,
			"voucher_type": "GRN Rework Item",
			"voucher_no": docname,
			"voucher_detail_no": row['row_name'],
			"qty": row['rework_qty'] * -1,
			"uom": row['uom'],
			"rate": 0,
			"valuation_rate": 0,
			"is_cancelled": 0,
			"posting_date": frappe.utils.nowdate(),
			"posting_time": frappe.utils.nowtime(),
		})	
		if row['rejected'] > 0:
			sl_entries.append({
				"item": row['variant'],
				"warehouse": warehouse,
				"received_type": rejected,
				"lot": lot,
				"voucher_type": "GRN Rework Item",
				"voucher_no": docname,
				"voucher_detail_no": row['row_name'],
				"qty": row['rejected'],
				"uom": row['uom'],
				"rate": 0,
				"valuation_rate": 0,
				"is_cancelled": 0,
				"posting_date": frappe.utils.nowdate(),
				"posting_time": frappe.utils.nowtime(),
			})

		if row['rework_qty'] - row['rejected'] > 0:
			sl_entries.append({
				"item": row['variant'],
				"warehouse": warehouse,
				"received_type": accepted,
				"lot": lot,
				"voucher_type": "GRN Rework Item",
				"voucher_no": docname,
				"voucher_detail_no": row['row_name'],
				"qty":  row['rework_qty'] - row['rejected'],
				"uom": row['uom'],
				"rate": 0,
				"valuation_rate": 0,
				"is_cancelled": 0,
				"posting_date": frappe.utils.nowdate(),
				"posting_time": frappe.utils.nowtime(),
			})	
			table_data.append({
				"item_variant": row['variant'],
				"quantity": row['rework_qty'] - row['rejected'],
				"received_type": row['received_type'],
				"uom": row['uom'],
				"reworked_time": frappe.utils.now_datetime(),
				"set_combination": frappe.json.dumps(row['set_combination'])
			})			
	if table_data:
		doc = frappe.get_doc("GRN Rework Item", docname)
		for row in table_data:
			doc.append("grn_reworked_item_details", row)
		doc.save(ignore_permissions=True)
	from production_api.mrp_stock.stock_ledger import make_sl_entries
	make_sl_entries(sl_entries)

@frappe.whitelist()
def update_partial_quantity(data, lot):
	data = update_if_string_instance(data)
	docname = frappe.db.sql(
		"""
			SELECT parent FROM `tabGRN Rework Item Detail` WHERE name = %(row_name)s
		""", {
			"row_name": data[0]['row_name']
		}, as_dict=True
	)[0]['parent']	
	warehouse = frappe.db.sql(
		"""
			SELECT warehouse FROM `tabGRN Rework Item` WHERE name = %(docname)s
		""", {
			"docname": docname
		}, as_dict=True
	)[0]['warehouse']
	accepted = frappe.db.get_single_value("Stock Settings", "default_received_type")
	sl_entries = []
	table_data = []
	for row in data:
		if row['rework'] > 0:
			print(row)
			sl_entries.append({
				"item": row['variant'],
				"warehouse": warehouse,
				"received_type": row['received_type'],
				"lot": lot,
				"voucher_type": "GRN Rework Item",
				"voucher_no": docname,
				"voucher_detail_no": row['row_name'],
				"qty":  row['rework'] * -1,
				"uom": row['uom'],
				"rate": 0,
				"valuation_rate": 0,
				"is_cancelled": 0,
				"posting_date": frappe.utils.nowdate(),
				"posting_time": frappe.utils.nowtime(),
			})
			sl_entries.append({
				"item": row['variant'],
				"warehouse": warehouse,
				"received_type": accepted,
				"lot": lot,
				"voucher_type": "GRN Rework Item",
				"voucher_no": docname,
				"voucher_detail_no": row['row_name'],
				"qty":  row['rework'],
				"uom": row['uom'],
				"rate": 0,
				"valuation_rate": 0,
				"is_cancelled": 0,
				"posting_date": frappe.utils.nowdate(),
				"posting_time": frappe.utils.nowtime(),
			})	
			frappe.db.sql(
				"""
					UPDATE `tabGRN Rework Item Detail` SET reworked = IFNULL(reworked, 0) + %(qty)s
					WHERE name = %(name)s
				""",
				{
					"qty": row['rework'],
					"name": row['row_name']
				}
			)
			table_data.append({
				"item_variant": row['variant'],
				"quantity": row['rework'],
				"received_type": row['received_type'],
				"uom": row['uom'],
				"reworked_time": frappe.utils.now_datetime(),
				"set_combination": frappe.json.dumps(row['set_combination'])
			})

	if table_data:
		doc = frappe.get_doc("GRN Rework Item", docname)
		for row in table_data:
			doc.append("grn_reworked_item_details", row)
		doc.save(ignore_permissions=True)
	from production_api.mrp_stock.stock_ledger import make_sl_entries
	make_sl_entries(sl_entries)		

@frappe.whitelist()
def get_rework_completion(lot, process):
	grns = frappe.get_all("Goods Received Note", filters={
		"against": "Work Order",
		"docstatus": 1,
		"lot": lot,
		"process_name": process
	}, pluck="name")

	grn_rework_item = frappe.get_all("GRN Rework Item", filters={
		"grn_number": ["in", grns]
	}, pluck="name")
	conditions = ""
	if len(grn_rework_item) == 1:
		print(grn_rework_item)
		print(grn_rework_item[0])
		conditions += f"('{grn_rework_item[0]}')"
	else:
		conditions += f"{tuple(grn_rework_item)}"
	print(grn_rework_item)
	query = f"""
		SELECT item_variant, quantity, uom, parent, set_combination FROM `tabGRN Reworked Item Detail`
		WHERE parent IN {conditions} AND quantity > 0
	"""
	print(query)
	items = frappe.db.sql(query, as_dict=True)
	from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import get_variant_attr_details
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values

	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
	is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	reworked_qty = {}
	colours = []
	default_received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	type_list = [default_received_type]
	for item in items:
		set_comb = update_if_string_instance(item['set_combination'])
		set_comb = update_if_string_instance(set_comb)
		major_colour = set_comb['major_colour']
		colour = major_colour
		attr_details = get_variant_attr_details(item['item_variant'])
		size = attr_details[primary_attr]
		part = None
		if is_set_item:
			variant_colour = attr_details[pack_attr]
			part = attr_details[set_attr]
			colour = variant_colour+"("+ major_colour+")"
		if colour not in colours:
			colours.append(colour)
			reworked_qty.setdefault(colour, {})
			reworked_qty[colour]['values'] = {}
			reworked_qty[colour]["part"] = part
			reworked_qty[colour]['type_wise_total'] = {}
			reworked_qty[colour]['size_wise_total'] = {}
			reworked_qty[colour]['colour_total'] = {}
			reworked_qty[colour]['colour_total'].setdefault("total", 0)

		reworked_qty[colour]["values"].setdefault(size, {})
		reworked_qty[colour]['size_wise_total'].setdefault(size, 0)

		qty = item['quantity']
		reworked_qty[colour]['size_wise_total'][size] += qty
		reworked_qty[colour]['colour_total']['total'] += qty
		reworked_qty[colour]["type_wise_total"].setdefault(default_received_type, 0)
		reworked_qty[colour]["type_wise_total"][default_received_type] += qty	
		reworked_qty[colour]["values"][size].setdefault(default_received_type, 0)
		reworked_qty[colour]["values"][size][default_received_type] += qty

	primary_values = get_ipd_primary_values(ipd)
	return {
		"primary_values": primary_values,
		"types": type_list,
		"data": reworked_qty,
		"is_set_item": is_set_item,
		"set_attr": set_attr
	}