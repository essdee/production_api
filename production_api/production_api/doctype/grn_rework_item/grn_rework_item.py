# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
import openpyxl
from io import BytesIO
from frappe.model.document import Document
from production_api.utils import update_if_string_instance, get_finishing_rework_list, get_finishing_rework_dict, get_variant_attr_details

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
	finishing_docs = frappe.get_all("Finishing Plan", filters={"lot": doc.lot}, pluck="name", limit=1)
	finishing_items = {}
	finishing_doc = None
	if finishing_docs:
		finishing_doc = frappe.get_doc("Finishing Plan", finishing_docs[0])
		finishing_items = get_finishing_rework_dict(finishing_doc)

	for row in doc.grn_rework_item_details:
		if row.completed == 0:
			continue
		set_comb = update_if_string_instance(row.set_combination)
		key = (row.item_variant, tuple(sorted(update_if_string_instance(set_comb).items())))
		if row.rejection > 0:
			if finishing_items.get(key):
				finishing_items[key]['rejected_qty'] -= row.rejection
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
			if finishing_items.get(key):
				finishing_items[key]['reworked_quantity'] -= row.quantity - row.rejection
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
	finishing_items_list = []	
	if finishing_doc:
		finishing_items_list = get_finishing_rework_list(finishing_items)
		finishing_doc.set("finishing_item_reworked_details", finishing_items_list)
		finishing_doc.save(ignore_permissions=True)
	from production_api.mrp_stock.stock_ledger import make_sl_entries
	make_sl_entries(sl_entries)

@frappe.whitelist()
def get_rework_items(lot, item, colour, grn_number=None):
	conditions = " AND t1.completed = 0"
	con = {}
	if grn_number:
		conditions += " AND t1.grn_number = %(grn_number)s"
		con['grn_number'] = grn_number
	else:	
		if item:
			conditions += " AND t1.item = %(item_name)s"
			con['item_name'] = item

		if lot:
			conditions += " AND t1.lot = %(lot_name)s"
			con['lot_name'] = lot

		if colour:
			conditions += " AND t2.item_variant LIKE  %(colour)s"
			con['colour'] = f"%{colour}%"

	rework_items = frappe.db.sql(
		f"""
			SELECT t1.name FROM `tabGRN Rework Item` t1 JOIN `tabGRN Rework Item Detail` t2 
			ON t1.name = t2.parent WHERE 1 = 1 {conditions} GROUP BY t1.name
		""", con, as_dict=True
	)	
	data = {
		"report_detail": {},
		"types": [],
		"total_detail": {},
		"total_sum": 0,
		"total_rejection": 0,
		"total_rejection_detail": {}
	}
	for item in rework_items:
		item = item['name']
		doc = frappe.get_doc("GRN Rework Item", item)
		ipd = frappe.get_cached_value("Lot", doc.lot, "production_detail")
		ipd_fields = ['packing_attribute', 'primary_item_attribute', 'is_set_item', 'set_item_attribute']
		pack_attr, primary_attr, set_item, set_attr = frappe.get_cached_value("Item Production Detail", ipd, ipd_fields)
		data["report_detail"].setdefault(item, {
			"grn_number": doc.grn_number,
			"date": doc.creation,
			"lot": doc.lot,
			"item": doc.item,
			"rework_detail": {},
			"size": primary_attr,
			"types": {},
			"total": 0,
			'rejection_detail': {},
			'total_rejection': 0,
		})
		for row in doc.grn_rework_item_details:
			if row.completed == 1:
				continue
			data['total_detail'].setdefault(row.received_type, 0)
			data['total_rejection_detail'].setdefault(row.received_type, 0)
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
			qty = row.quantity - row.reworked
			data['total_detail'][row.received_type] += qty
			data['total_rejection_detail'][row.received_type] += row.rejection
			data['total_sum'] += qty
			data['total_rejection'] += row.rejection
			data["report_detail"][item]['types'].setdefault(row.received_type, 0)
			data["report_detail"][item]['types'][row.received_type] += qty
			data["report_detail"][item]['total'] += qty
			data["report_detail"][item]['total_rejection'] += row.rejection
			data['report_detail'][item]['rejection_detail'].setdefault(row.received_type, 0)
			data['report_detail'][item]['rejection_detail'][row.received_type] += row.rejection
			data["report_detail"][item]['rework_detail'][key]['items'].append({
				primary_attr : attr_details[primary_attr],
				"rework_qty": qty,
				"rejected": row.rejection, 
				"rework": 0,
				"set_combination": update_if_string_instance(row.set_combination),
				"row_name": row.name,
				"variant": row.item_variant,
				"received_type": row.received_type,
				"uom": row.uom,
			})
	
	if grn_number:
		return data, rework_items[0]['name']
	
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
		if row['rework_qty'] > 0:
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

		if row['rework_qty'] - row['rejected'] > 0 or row['rejected'] > 0:
			table_data.append({
				"item_variant": row['variant'],
				"quantity": row['rework_qty'] - row['rejected'],
				"received_type": row['received_type'],
				"uom": row['uom'],
				"reworked_time": frappe.utils.now_datetime(),
				"rejected": row['rejected'],
				"set_combination": frappe.json.dumps(row['set_combination'])
			})

	finishing_docs = frappe.get_all("Finishing Plan", filters={"lot": lot}, pluck="name", limit=1)		
	finishing_data = {}
	if table_data:
		doc = frappe.get_doc("GRN Rework Item", docname)
		for row in table_data:
			if finishing_docs:
				set_comb = update_if_string_instance(frappe.json.loads(row['set_combination']))
				key = (row['item_variant'], tuple(sorted(set_comb.items())))
				finishing_data.setdefault(key, {
					"reworked": 0,
					"rejected": 0,
				})
				finishing_data[key]['reworked'] += row['quantity']
				finishing_data[key]['rejected'] += row['rejected']
			doc.append("grn_reworked_item_details", row)
		doc.save(ignore_permissions=True)

	if finishing_docs:
		doc = frappe.get_doc("Finishing Plan", finishing_docs[0])
		for row in doc.finishing_plan_reworked_details:
			key = (row.item_variant, tuple(sorted(update_if_string_instance(row.set_combination).items())))
			if finishing_data.get(key):
				row.reworked_quantity += finishing_data[key]['reworked']
				row.rejected_qty += finishing_data[key]['rejected']
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

	finishing_docs = frappe.get_all("Finishing Plan", filters={"lot": lot}, pluck="name", limit=1)		
	finishing_data = {}
	if table_data:
		doc = frappe.get_doc("GRN Rework Item", docname)
		for row in table_data:
			if finishing_docs:
				set_comb = update_if_string_instance(frappe.json.loads(row['set_combination']))
				key = (row['item_variant'], tuple(sorted(set_comb.items())))
				finishing_data.setdefault(key, 0)
				finishing_data[key] += row['quantity']
			doc.append("grn_reworked_item_details", row)
		doc.save(ignore_permissions=True)

	if finishing_docs:
		doc = frappe.get_doc("Finishing Plan", finishing_docs[0])
		for row in doc.finishing_plan_reworked_details:
			key1 = (row.item_variant, tuple(sorted(update_if_string_instance(row.set_combination).items())))
			for key in finishing_data:
				if key1 == key:
					row.reworked_quantity += finishing_data[key]
					break
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
		conditions += f"('{grn_rework_item[0]}')"
	else:
		conditions += f"{tuple(grn_rework_item)}"

	query = f"""
		SELECT item_variant, quantity, uom, parent, set_combination FROM `tabGRN Reworked Item Detail`
		WHERE parent IN {conditions} AND quantity > 0
	"""
	items = frappe.db.sql(query, as_dict=True)
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

@frappe.whitelist()
def get_partial_reworked_qty(doc_name, colour_mistake, data):
	data = update_if_string_instance(data)
	doc = frappe.get_doc("GRN Rework Item", doc_name)
	ipd = frappe.get_cached_value("Lot", doc.lot, "production_detail")
	primary_attr = frappe.get_cached_value("Item Production Detail", ipd, "primary_item_attribute")
	mistake = colour_mistake.split("-")[0]
	key = colour_mistake
	data["report_detail"][doc_name]['rework_detail'][key]['changed'] = 0
	data["report_detail"][doc_name]['rework_detail'][key]['items'] = []
	data["report_detail"][doc_name]['types'][mistake] = 0
	data["report_detail"][doc_name]['total'] = 0
	for row in doc.grn_rework_item_details:
		if row.completed == 1:
			continue
		qty = row.quantity - row.reworked
		data["report_detail"][doc_name]['total'] += qty
		if row.received_type != mistake:
			continue

		attr_details = get_variant_attr_details(row.item_variant)
		if row.received_type not in data['types']:
			data['types'].append(row.received_type)
		qty = row.quantity - row.reworked
		data["report_detail"][doc_name]['types'][mistake] += qty
		data["report_detail"][doc_name]['rework_detail'][key]['items'].append({
			primary_attr : attr_details[primary_attr],
			"rework_qty": qty,
			"rejected": row.rejection, 
			"rework": 0,
			"set_combination": update_if_string_instance(row.set_combination),
			"row_name": row.name,
			"variant": row.item_variant,
			"received_type": row.received_type,
			"uom": row.uom,
		})
	return data

@frappe.whitelist()
def download_xl(data):
	if isinstance(data, str):
		data = frappe.json.loads(data)  
	wb = openpyxl.Workbook(write_only=True)
	ws = wb.create_sheet("Sheet1", 0)
	columns = ['Series No', "Date", "GRN Number", "Lot", "Item", "Colour"] + data['types']
	ws.append(columns)
	for series_id in data['report_detail']:
		x = data['report_detail'][series_id]
		l_data = list(x['rework_detail'].keys())[0].split("-")
		l_data = l_data[1:]
		colour = "-".join(l_data)
		from datetime import datetime
		raw_date = x['date']
		dt = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S.%f")
		formatted_date = dt.strftime("%d-%m-%Y")
		d = [series_id, formatted_date, x['grn_number'], x['lot'], x['item'], colour]
		for ty in data['types']:
			qty = x['types'].get(ty, 0)
			reject_qty = x['rejection_detail'].get(ty, 0)
			d.append(qty - reject_qty)
		ws.append(d)  
	xlsx_file = BytesIO()
	wb.save(xlsx_file)
	frappe.local.response.filename = "rework_details.xlsx"
	frappe.local.response.filecontent = xlsx_file.getvalue()
	frappe.local.response.type = "binary"