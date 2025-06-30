import frappe, json
from six import string_types
from frappe.query_builder.builder import Order as OrderBy
from frappe.utils import getdate, add_days, flt

def get_bin(item_code, warehouse, lot):
	bin = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse, "lot": lot})
	if not bin:
		bin_obj = _create_bin(item_code, warehouse, lot)
	else:
		bin_obj = frappe.get_doc("Bin", bin)
	bin_obj.flags.ignore_permissions = True
	return bin_obj

def get_or_make_bin(item_code: str, warehouse: str, lot: str, received_type: str) -> str:
	bin_record = frappe.get_cached_value("Bin", {"item_code": item_code, "warehouse": warehouse, "lot": lot, "received_type": received_type})
	if not bin_record:
		bin_obj = _create_bin(item_code, warehouse, lot, received_type)
		bin_record = bin_obj.name
	return bin_record

def _create_bin(item_code, warehouse, lot, received_type):
	"""Create a bin and take care of concurrent inserts."""

	bin_creation_savepoint = "create_bin"
	try:
		frappe.db.savepoint(bin_creation_savepoint)
		bin_obj = frappe.get_doc(doctype="Bin", item_code=item_code, warehouse=warehouse, lot=lot, received_type=received_type)
		bin_obj.flags.ignore_permissions = 1
		bin_obj.insert()
	except frappe.UniqueValidationError:
		frappe.db.rollback(save_point=bin_creation_savepoint)  # preserve transaction in postgres
		bin_obj = frappe.get_last_doc("Bin", {"item_code": item_code, "warehouse": warehouse, 'lot' : lot, "received_type": received_type})

	return bin_obj

def get_unreserved_qty(item):
    
    bin = get_or_make_bin(item['item_name'],item['warehouse'],item['lot'], item['received_type'])
    bin_doc = frappe.get_doc("Bin",bin)
    return bin_doc.actual_qty - bin_doc.reserved_qty

def get_item_variant_stock(item :str, warehouse: str, lot: str) -> float:
    
    sle = frappe.qb.DocType("Stock Ledger Entry")
    
    query =  (
		frappe.qb.from_(sle)
		.select(
			sle.qty_after_transaction
		)
		.where((sle.item == item) & (sle.warehouse == warehouse) & (sle.lot == lot))
		.orderby(sle.creation,OrderBy.desc)
		.limit(1)
	)
    sle_ent =query.run(as_dict=True)
    if len(sle_ent) == 0:
        return 0
    return flt(sle_ent[0]['qty_after_transaction'])

def get_panel_list(ipd_doc):
	panel_list = []
	for panel in ipd_doc.stiching_item_details:
		panel_list.append(panel.stiching_attribute_value)
	return panel_list

def get_stich_details(ipd_doc):
	stich_details = {}
	for i in ipd_doc.stiching_item_details:
		stich_details[i.stiching_attribute_value] = i.set_item_attribute_value
	return stich_details	

def get_part_list(ipd_doc):
	part_list = []
	for stich in ipd_doc.stiching_item_details:
		if stich.set_item_attribute_value not in part_list:
			part_list.append(stich.set_item_attribute_value)
	return part_list

def update_if_string_instance(obj):
	if isinstance(obj, string_types):
		obj = json.loads(obj)

	if not obj:
		obj = {}

	return obj

@frappe.whitelist()
def get_item_from_variant(variant):
	return frappe.get_cached_value("Item Variant", variant, "item")	

def get_tuple_attributes(tuple_data):
	attrs = {}
	for data in tuple_data:
		attrs[data[0]] = data[1]
	return attrs	

@frappe.whitelist()
def get_t_and_a_report_data(lot, item, process_name):
	filters = {
		"docstatus": 1,
		"open_status": "Open",
	}
	if lot:
		filters['lot'] = lot
	if item:
		filters['item'] = item
	if process_name:
		filters['process_name'] = process_name

	wo_names = frappe.get_all("Work Order", filters=filters, pluck="name")
	min_date = None
	max_date = None
	report_data = [] 
	for wo in wo_names:
		doc = frappe.db.sql(
			f""" 
				SELECT t1.item, t1.lot, t1.process_name, t1.planned_quantity, t1.planned_end_date, t1.expected_delivery_date, t2.assigned_person_name
				FROM `tabWork Order` as t1 JOIN `tabLot` as t2 ON t1.lot = t2.name WHERE t1.name = '{wo}' 
			""", as_dict=True
		)
		delay = getdate(doc[0]['planned_end_date'], parse_day_first=True) - getdate(doc[0]['expected_delivery_date'], parse_day_first=True)
		d = {
			'item': doc[0]['item'],
			'lot': doc[0]['lot'],
			'process_name': doc[0]['process_name'],
			'qty': doc[0]['planned_quantity'],
			'reason': None,
			'planned_end_date': getdate(doc[0]['planned_end_date'], parse_day_first=True),
			"delay": delay.days,
			"assigned": doc[0]['assigned_person_name']
		}
		row_max_date = None
		rows = frappe.db.sql(
			f""" SELECT from_date, to_date, reason, check_point FROM `tabWork Order Tracking Log` WHERE parent = '{wo}' """, as_dict=True
		)
		for row in rows:
			from_date = getdate(row['from_date'])
			if not min_date or not max_date:
				min_date = from_date
				max_date = from_date
			else:
				if from_date > max_date:
					max_date = from_date
				if from_date < min_date:
					min_date = from_date

			to_date = getdate(row['to_date'])
			if not row_max_date:
				row_max_date = to_date
			else:
				if to_date > row_max_date:
					row_max_date = to_date

			from_date = from_date.strftime("%d-%m-%Y")
			to_date = to_date.strftime("%d-%m-%Y")
			if row['check_point'] == 1:
				d['check_point'] = to_date
			d[from_date] = to_date 
			d['reason'] = row['reason']	
		report_data.append(d)
	data = {}
	for row in report_data:
		d = {"lot": row['lot'], "item": row['item'], "process_name": row['process_name']}
		key =  tuple(sorted(d.items()))
		if key not in data:
			data[key] = row.copy()
			row_keys = ["lot", "item", "process_name", "qty", "reason", "delay", "planned_end_date", "assigned", "check_point"]	
			for k in row_keys:
				if not k in row:
					continue
				del row[k]
			for ky in row:	
				data[key]['min_reason_date'] = getdate(row[ky], parse_day_first=True)
		else:
			end_date = getdate(row['planned_end_date'], parse_day_first=True)
			if data[key]['planned_end_date'] < end_date:
				data[key]['planned_end_date'] = end_date
			data[key]['qty'] += row['qty']
			row_keys = ["lot", "item", "process_name", "qty", "reason", "delay", "planned_end_date", "assigned", "check_point"]	
			reason = row['reason']
			if data[key]['delay'] < row['delay']:
				data[key]['delay'] = row['delay']
			for k in row_keys:
				if not k in row:
					continue
				del row[k]
			for d in row:
				if d == "min_reason_date":
					continue
				if data[key].get(d):
					date1 = getdate(data[key][d], parse_day_first=True)
					date2 = getdate(row[d], parse_day_first=True)
					x = date1 if date1 >= date2 else date2
					if x > data[key].get('min_reason_date'):
						data[key]['min_reason_date'] = x
						data[key]['reason'] = reason
					x = x.strftime("%d-%m-%Y")
					data[key][d] = x
				else:
					y = getdate(row[d], parse_day_first=True)
					if y > data[key].get('min_reason_date'):
						data[key]['min_reason_date'] = y
						data[key]['reason'] = reason
					data[key][d] = row[d]	
	date_keys = []
	if min_date and max_date:
		if not lot and not item and not process_name:
			max_date = getdate(frappe.utils.nowdate(), parse_day_first=True)
			days = frappe.db.get_single_value("MRP Settings", "time_and_action_tracking_order_report_days")
			if days == 0 or not days:
				days = 6
			else:
				days = days - 1	
			days = days * -1	
			min_date = add_days(max_date, days)
		while min_date < max_date:
			x = min_date.strftime("%d-%m-%Y")
			date_keys.append(x)
			min_date = add_days(min_date, 1)
		date_keys.append(max_date.strftime("%d-%m-%Y"))	

	keys = ["item", "lot", "process_name", "qty"] + date_keys + ["reason", "delay", "planned_end_date", "assigned", "check_point"]
	x = []
	for d in data:
		end_data = data[d]['planned_end_date'].strftime("%d-%m-%Y")
		data[d]['planned_end_date'] = end_data
		x.append(data[d])
	d = {"row_keys": keys, "dates": date_keys, "datas": x}

	return d

@frappe.whitelist()
def get_work_order_details(detail):
	detail = update_if_string_instance(detail)
	filters = {
		"lot": detail['lot'], 
		"item": detail['item'], 
		"process_name": detail['process_name'],
		"docstatus": 1,
		"open_status": "Open"
	}
	fields = ["name", "wo_colours", "supplier", "supplier_name", "total_quantity", "total_no_of_pieces_received"]
	work_orders = frappe.get_all("Work Order", filters=filters, fields=fields)
	return work_orders

@frappe.whitelist()
def update_expected_date(work_order, expected_date, reason, _return=True):
	from production_api.production_api.doctype.work_order.work_order import add_comment
	expected_date = getdate(expected_date)
	add_comment(work_order, expected_date, reason)
	if _return:
		wo_doc = frappe.get_doc("Work Order", work_order)
		report_data = get_t_and_a_report_data(wo_doc.lot, wo_doc.item, wo_doc.process_name)
		return report_data['datas'][0]

@frappe.whitelist()
def update_all_work_orders(lot, item, process_name, work_order_details, expected_date, reason):
	work_order_details = update_if_string_instance(work_order_details)
	expected_date = getdate(expected_date)
	for detail in work_order_details:
		update_expected_date(detail['name'], expected_date, reason, _return=False)
	report_data = get_t_and_a_report_data(lot, item, process_name)
	return report_data['datas'][0]	

@frappe.whitelist()
def get_t_and_a_review_report_data(lot, item, report_date):
	conditions = ""
	con = {}
	if lot:
		conditions += f" and lot = %(lot)s"
		con["lot"] = lot
	
	if report_date:
		conditions += f' and end_date < %(end_date)s'
		con['end_date'] = report_date

	if item:
		conditions += f" and item = %(item)s"
		con['item'] = item

	lot_list = frappe.db.sql(
		f"""
			SELECT t1.lot FROM `tabTime and Action` AS t1 JOIN `tabTime and Action Detail` AS t2
			ON t2.parent = t1.name JOIN (
				SELECT parent, MAX(idx) AS max_idx FROM `tabTime and Action Detail` GROUP BY parent
			) AS D ON t2.parent = D.parent AND t2.idx = D.max_idx
			WHERE 1 = 1 {conditions} GROUP BY t1.lot ORDER BY t2.rescheduled_date;
		""", con, as_list=True
	)
	data = {}
	conditions = ""
	con = {}

	if report_date:
		conditions += f' and t3.end_date < %(end_date)s'
		con['end_date'] = report_date

	conditions += " and t3.status != 'Completed'"	

	for lot in lot_list:
		lot = lot[0]
		data.setdefault(lot, {})
		t_and_a_list = frappe.db.sql(
			f"""
				SELECT t1.time_and_action, t1.master FROM `tabLot Time and Action Detail` as t1 JOIN 
				`tabTime and Action Detail` as t2 ON t2.parent = t1.time_and_action JOIN 
				`tabTime and Action` as t3 ON t2.parent = t3.name 
				WHERE t1.parent = '{lot}' {conditions} GROUP BY t1.time_and_action
			""",con, as_dict=True
		)
		masters = []
		for t_and_a in t_and_a_list:
			if t_and_a.master not in masters:
				masters.append(t_and_a.master)
		
		for master in masters:
			data[lot].setdefault(master, {"actions": [], "datas": []})
			for t_and_a in t_and_a_list:
				if t_and_a.master == master:
					doc = frappe.get_doc("Time and Action", t_and_a.time_and_action)
					d = {
						"item":doc.item,
						"master": doc.master,
						"colour": doc.colour,
						"sizes": doc.sizes,
						"qty": doc.qty,
						"start_date": doc.start_date,
						"delay": doc.delay
					}
					if not data[lot][master]['actions']:
						for row in doc.details:
							data[lot][master]['actions'].append(row.action)
					d['actions'] = []
					for row in doc.details:
						d['actions'].append({
							"department":row.department,
							"date":row.date,
							"rescheduled_date":row.rescheduled_date,
							"actual_date":row.actual_date,
							"reason": row.reason,
							"performance": row.performance,
							"delay": row.date_diff

						})
					data[lot][master]['datas'].append(d)
	return data

@frappe.whitelist()
def update_wo_checkpoint(datas):
	data = update_if_string_instance(datas)
	for row in data:
		if not row.get("changed"):
			continue
		filters = {
			"item": row['item'],
			"process_name": row['process_name'],
			"lot": row['lot'],
			"docstatus": 1,
			"open_status": "Open",
		}
		keys = ['item', 'lot', 'process_name', 'qty', 'reason', 'planned_end_date', 'delay', 'assigned', "min_reason_date"]
		for key in keys:
			if not key in row:
				continue
			del row[key]

		if row:
			row = sorted(row.items())
			row = dict(row)
			work_orders = frappe.get_all("Work Order", filters=filters, pluck="name")
			for work_order in work_orders:
				to_date = None
				for key in row:
					to_date = row[key]
				to_date = getdate(to_date, parse_day_first=True)
				wo_doc = frappe.get_doc("Work Order", work_order)
				for tracking_log in wo_doc.work_order_tracking_logs:
					if to_date == tracking_log.to_date:
						tracking_log.check_point = 1
					else:
						tracking_log.check_point = 0
				wo_doc.save(ignore_permissions=True)			
