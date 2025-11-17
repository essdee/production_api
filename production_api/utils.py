import frappe, json, sys
from six import string_types
from itertools import zip_longest
from frappe.query_builder.builder import Order as OrderBy
from frappe.utils import getdate, add_days, flt

class MyCustomException(Exception):
    def __init__(self, message):
        super().__init__(message)

    def __str__(self):
        return f"{self.message}"

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

def get_panel_colour_combination(ipd_doc):
	indexes = {}
	comb_details = {}
	for row in ipd_doc.stiching_item_combination_details:
		if indexes.get(row.index):
			major_colour = indexes[row.index]
			comb_details[major_colour][row.set_item_attribute_value] = row.attribute_value
		else:
			indexes[row.index] = row.major_attribute_value
			comb_details[row.major_attribute_value] = {}
			comb_details[row.major_attribute_value][row.set_item_attribute_value] = row.attribute_value

	return comb_details

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
				m = getdate(row[ky], parse_day_first=True)
				data[key]['min_reason_date'] = m
				m = m.strftime("%d-%m-%Y") 
				data[key]['expected_date'] = m 
		else:
			end_date = getdate(row['planned_end_date'], parse_day_first=True)
			if data[key]['planned_end_date'] < end_date:
				data[key]['planned_end_date'] = end_date
			data[key]['qty'] += row['qty']
			row_keys = ["lot", "item", "process_name", "qty", "reason", "delay", "planned_end_date", "assigned", "check_point"]	
			reason = row['reason']
			old_check_point = data[key].get('check_point')
			if not old_check_point:
				if row.get('check_point'):
					data[key]['check_point'] = row['check_point']
			elif row.get('check_point'):
				if getdate(row['check_point']) > getdate(old_check_point):
					data[key]['check_point'] = row['check_point']

			if data[key]['delay'] < row['delay']:
				data[key]['delay'] = row['delay']
			for k in row_keys:
				if not k in row:
					continue
				del row[k]

			if "min_reason_date" not in data[key]:
				for ky in row:	
					m = getdate(row[ky], parse_day_first=True)
					data[key]['min_reason_date'] = m
					m = m.strftime("%d-%m-%Y")
					data[key]['expected_date'] = m
			
			for d in row:
				if d == "min_reason_date" or d == "expected_date":
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
					if date1 > getdate(data[key]['expected_date']):
						date1 = date1.strftime("%d-%m-%Y")
						data[key]['expected_date'] = date1
				else:
					y = getdate(row[d], parse_day_first=True)
					if y > data[key].get('min_reason_date'):
						data[key]['min_reason_date'] = y
						data[key]['reason'] = reason
					data[key][d] = row[d]	
	date_keys = []
	if min_date and max_date:
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
				check = True
				for tracking_log in wo_doc.work_order_tracking_logs:
					if to_date == tracking_log.to_date:
						tracking_log.check_point = 1
						check = False
					else:
						tracking_log.check_point = 0
				if check:
					tracking_log = wo_doc.append("work_order_tracking_logs", {})
					tracking_log.from_date = to_date
					tracking_log.to_date = to_date
					tracking_log.check_point = 1
					tracking_log.user =	frappe.session.user	
				wo_doc.save(ignore_permissions=True)			

@frappe.whitelist()
def get_daily_production_report(date, location):
	from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details
	from production_api.production_api.doctype.cutting_plan.cutting_plan import get_complete_incomplete_structure
	cutting_plans = frappe.db.sql(
		"""
			SELECT distinct(cutting_plan) FROM `tabCutting LaySheet` WHERE DATE(printed_time) = %(date)s
		""", {
			"date": getdate(date)
		}, as_dict=True
	)
	report = []
	for cutting_plan in cutting_plans:
		cp_doc = frappe.get_doc("Cutting Plan",cutting_plan['cutting_plan'])
		if cp_doc.version == "V1":
			frappe.throw("Can't get report for Cutting Plan Version V1")
		if location and cp_doc.cutting_location != location:
			continue
		item_details = fetch_order_item_details(cp_doc.items,cp_doc.production_detail)
		completed, incomplete = get_complete_incomplete_structure(cp_doc.production_detail,item_details)
		incomplete_items = update_if_string_instance(incomplete)
		completed_items = update_if_string_instance(completed)
		previous_cls_list = frappe.db.sql(
			"""
				SELECT name FROM `tabCutting LaySheet` WHERE DATE(printed_time) < %(date)s
				AND cutting_plan = %(cutting_plan)s AND status = 'Label Printed'
			""", {
				"date": getdate(date),
				"cutting_plan": cutting_plan['cutting_plan']
			}, as_dict=True
		)
		production_detail = cp_doc.production_detail
		ipd_doc = frappe.get_cached_doc("Item Production Detail",production_detail)
		completed_items, incomplete_items = calculate_completed(previous_cls_list, ipd_doc, completed_items, incomplete_items)
		cls_list = frappe.db.sql(
			"""
				SELECT name FROM `tabCutting LaySheet` WHERE DATE(printed_time) = %(date)s  
				AND cutting_plan = %(cutting_plan)s AND status = 'Label Printed'
			""", {
				"date": getdate(date),
				"cutting_plan": cutting_plan['cutting_plan']
			}, as_dict=True
		)	
		previous_completed = frappe.json.dumps(completed_items)
		completed_items, incomplete_items = calculate_completed(cls_list, ipd_doc, completed_items, incomplete_items)
		previous_completed = update_if_string_instance(previous_completed)
		for item1, item2 in zip_longest(previous_completed['items'], completed_items['items']):
			for size in item1['values']:
				item2['values'][size] = item2['values'][size] - item1['values'][size]
		
		items_list = []
		total = 0
		total_planned_qty = 0
		total_received_qty = 0
		planned_dict = {}
		if cp_doc.work_order:
			wo_doc = frappe.get_doc("Work Order", cp_doc.work_order)
			for row in wo_doc.work_order_calculated_items:
				planned_dict.setdefault(row.item_variant, {
					"planned": row.quantity,
					"cumulative": row.received_qty
				})
		from production_api.production_api.doctype.item.item import get_or_create_variant
		for row in completed_items['items']:
			total_qty = 0
			total_planned = 0
			total_received = 0
			for val in row['values']:
				if row['values'][val] > 0:
					total_qty += row['values'][val]
					attrs = row['attributes']
					attrs[row['primary_attribute']] = val
					variant = get_or_create_variant(cp_doc.item, attrs)
					if planned_dict:
						total_planned += planned_dict[variant]['planned']
						total_received += planned_dict[variant]['cumulative']

			if total_qty > 0:	
				row['total_qty'] = total_qty	
				row['planned'] = total_planned
				row['cumulative'] = total_received
				items_list.append(row)
				total += total_qty
				total_planned_qty += total_planned
				total_received_qty += total_received

		if len(items_list) == 0:
			continue
		else:
			completed_items['items'] = items_list
		completed_items['total_sum'] = total
		completed_items['total_planned_sum'] = total_planned_qty
		completed_items['total_received_sum'] = total_received_qty
		completed_items['style_no'] = cp_doc.item
		completed_items['lot_no'] = cp_doc.lot
		completed_items['location'] = cp_doc.cutting_location
		report.append(completed_items)

	return report

def calculate_completed(cls_list, ipd_doc, completed_items, incomplete_items):
	for cls in cls_list:
		cls_doc = frappe.get_doc("Cutting LaySheet",cls['name'])
		if not ipd_doc.is_set_item:
			alter_incomplete_items = {}
			for item in incomplete_items['items']:
				colour = item['attributes'][ipd_doc.packing_attribute]
				alter_incomplete_items[colour] = item['values']
			
			for item in cls_doc.cutting_laysheet_bundles:
				parts = item.part.split(",")
				set_combination = update_if_string_instance(item.set_combination)
				set_colour = set_combination['major_colour']
				qty = item.quantity
				for part in parts:
					alter_incomplete_items[set_colour][item.size][part] += qty	
			total_qty = completed_items['total_qty']
			for item in completed_items['items']:
				colour = item['attributes'][ipd_doc.packing_attribute]
				for val in item['values']:
					min = sys.maxsize
					if not alter_incomplete_items[colour].get(val):
						continue
					for panel in alter_incomplete_items[colour][val]:
						if alter_incomplete_items[colour][val][panel] < min:
							min = alter_incomplete_items[colour][val][panel]
					total_qty[val] += min
					item['values'][val] += min
					for panel in alter_incomplete_items[colour][val]:
						alter_incomplete_items[colour][val][panel] -= min
			completed_items['total_qty'] = total_qty				
			for item in incomplete_items['items']:
				colour = item['attributes'][ipd_doc.packing_attribute]
				item['values'] = alter_incomplete_items[colour]
		else:
			stich_details = get_stich_details(ipd_doc)
			alter_incomplete_items = {}
			for item in incomplete_items['items']:
				set_combination = update_if_string_instance(item['item_keys'])
				colour = set_combination['major_colour']
				part = item['attributes'][ipd_doc.set_item_attribute]
				if alter_incomplete_items.get(colour):
					alter_incomplete_items[colour][part] = item['values']
				else:	
					alter_incomplete_items[colour] = {}
					alter_incomplete_items[colour][part] = item['values']
			for item in cls_doc.cutting_laysheet_bundles:
				parts = item.part.split(",")
				set_combination = update_if_string_instance(item.set_combination)
				major_part = set_combination['major_part']
				major_colour = set_combination['major_colour']
				d = {
					"major_colour": major_colour,
				}
				if set_combination.get('set_part'):
					major_part = set_combination['set_part']
					major_colour = set_combination['set_colour']
				d['major_part'] = major_part	

				qty = item.quantity
				for part in parts:
					try:
						alter_incomplete_items[d['major_colour']][d['major_part']][item.size][part] += qty
					except:
						secondary_part = stich_details[part]
						alter_incomplete_items[d['major_colour']][secondary_part][item.size][part] += qty
			
			total_qty = completed_items['total_qty']
			for item in completed_items['items']:
				set_combination = update_if_string_instance(item['item_keys'])
				colour = set_combination['major_colour']
				part = item['attributes'][ipd_doc.set_item_attribute]
				for val in item['values']:
					min = sys.maxsize
					for panel in alter_incomplete_items[colour][part][val]:
						if alter_incomplete_items[colour][part][val][panel] < min:
							min = alter_incomplete_items[colour][part][val][panel]
					
					total_qty[val] += min
					item['values'][val] += min
					for panel in alter_incomplete_items[colour][part][val]:
						alter_incomplete_items[colour][part][val][panel] -= min		
			
			completed_items["total_qty"] = total_qty
			for item in incomplete_items['items']:
				set_combination = update_if_string_instance(item['item_keys'])
				colour = set_combination['major_colour']
				part = item['attributes'][ipd_doc.set_item_attribute]
				item['values'] = alter_incomplete_items[colour][part]

	return completed_items, incomplete_items

@frappe.whitelist()
def get_cut_sheet_report(date, location):
	from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details
	from production_api.production_api.doctype.cutting_plan.cutting_plan import get_complete_incomplete_structure
	cutting_plans = frappe.db.sql(
		"""
			SELECT distinct(cutting_plan) FROM `tabCutting LaySheet` WHERE DATE(printed_time) = %(date)s
		""", {
			"date": getdate(date)
		}, as_dict=True
	)
	report = []
	for cutting_plan in cutting_plans:
		cp_doc = frappe.get_doc("Cutting Plan",cutting_plan['cutting_plan'])
		if cp_doc.version == "V1":
			frappe.throw("Can't get report for Cutting Plan Version V1")

		if location and cp_doc.cutting_location != location:
			continue
		item_details = fetch_order_item_details(cp_doc.items,cp_doc.production_detail)
		completed, incomplete = get_complete_incomplete_structure(cp_doc.production_detail,item_details)
		cls_list = frappe.db.sql(
			"""
				SELECT name FROM `tabCutting LaySheet` WHERE DATE(printed_time) = %(date)s  
				AND cutting_plan = %(cutting_plan)s AND status = 'Label Printed'
			""", {
				"date": getdate(date),
				"cutting_plan": cutting_plan['cutting_plan']
			}, as_dict=True
		)	
		incomplete_items = update_if_string_instance(incomplete)
		production_detail = cp_doc.production_detail
		ipd_doc = frappe.get_cached_doc("Item Production Detail",production_detail)
		alter_incomplete_items = {}
		if not ipd_doc.is_set_item:
			for item in incomplete_items['items']:
				colour = item['attributes'][ipd_doc.packing_attribute]
				alter_incomplete_items[colour] = item['values']
		else:
			for item in incomplete_items['items']:
				set_combination = update_if_string_instance(item['item_keys'])
				colour = set_combination['major_colour']
				part = item['attributes'][ipd_doc.set_item_attribute]
				if alter_incomplete_items.get(colour):
					alter_incomplete_items[colour][part] = item['values']
				else:	
					alter_incomplete_items[colour] = {}
					alter_incomplete_items[colour][part] = item['values']

		for cls in cls_list:
			cls_doc = frappe.get_doc("Cutting LaySheet",cls['name'])
			if not ipd_doc.is_set_item:
				for item in cls_doc.cutting_laysheet_bundles:
					parts = item.part.split(",")
					set_combination = update_if_string_instance(item.set_combination)
					set_colour = set_combination['major_colour']
					qty = item.quantity
					for part in parts:
						alter_incomplete_items[set_colour][item.size][part] += qty	
				for item in incomplete_items['items']:
					colour = item['attributes'][ipd_doc.packing_attribute]
					item['values'] = alter_incomplete_items[colour]		
				
			else:
				stich_details = get_stich_details(ipd_doc)
				for item in cls_doc.cutting_laysheet_bundles:
					parts = item.part.split(",")
					set_combination = update_if_string_instance(item.set_combination)
					major_part = set_combination['major_part']
					major_colour = set_combination['major_colour']
					d = {
						"major_colour": major_colour,
					}
					if set_combination.get('set_part'):
						major_part = set_combination['set_part']
						major_colour = set_combination['set_colour']
					d['major_part'] = major_part	

					qty = item.quantity
					for part in parts:
						try:
							alter_incomplete_items[d['major_colour']][d['major_part']][item.size][part] += qty
						except:
							secondary_part = stich_details[part]
							alter_incomplete_items[d['major_colour']][secondary_part][item.size][part] += qty
				
				for item in incomplete_items['items']:
					set_combination = update_if_string_instance(item['item_keys'])
					colour = set_combination['major_colour']
					part = item['attributes'][ipd_doc.set_item_attribute]
					item['values'] = alter_incomplete_items[colour][part]
		
		items_list = []
		for item in incomplete_items['items']:
			add_item = False
			for size in item['values']:
				check = False
				for panel in item['values'][size]:
					if item['values'][size][panel] > 0:
						check = True
						break
				if check:	
					add_item = True
					break
			if add_item:
				items_list.append(item)

		if len(items_list) == 0:
			continue

		incomplete_items['items'] = items_list			

		for item in incomplete_items['items']:
			item['total_panel_qty'] = {}
			for size in item['values']:
				for panel in item['values'][size]:
					if item['values'][size][panel] > 0:
						item['total_panel_qty'].setdefault(panel, 0)
						item['total_panel_qty'][panel] += item['values'][size][panel] 
		incomplete_items['style_no'] = cp_doc.item
		incomplete_items['lot_no'] = cp_doc.lot
		incomplete_items['location'] = cp_doc.cutting_location
		report.append(incomplete_items)

	return report

def get_lpiece_variant(pack_attr, dept_attr, variant):
	from production_api.production_api.doctype.item.item import get_or_create_variant
	attr_details = get_variant_attr_details(variant)
	del attr_details[pack_attr]
	if 'Part' in attr_details:
		del attr_details['Part']
	attr_details[dept_attr] = "Loose Piece"
	item_name = frappe.get_value("Item Variant", variant, "item")
	variant = get_or_create_variant(item_name, attr_details)
	return variant

@frappe.whitelist()
def get_inward_qty(lot, process):
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	wo_list = frappe.get_all("Work Order", filters={
		"lot": lot,
		"process_name": process,
		"docstatus": 1,
	}, pluck="name")
	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
	is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	inward_qty = {
		"data": {},
		"total": {},
	}
	type_list = []
	colours = []
	for wo in wo_list:
		items = frappe.db.sql(
			"""
				SELECT * FROM `tabWork Order Calculated Item` WHERE parent = %(work_order)s
			""", {
				"work_order": wo
			}, as_dict=True,
		)
		for item in items:
			set_comb = update_if_string_instance(item['set_combination'])
			major_colour = set_comb['major_colour']
			colour = major_colour
			attr_details = get_variant_attr_details(item['item_variant'])
			size = attr_details[primary_attr]
			part = None
			if is_set_item:
				variant_colour = attr_details[pack_attr]
				part = attr_details[set_attr]
				colour = variant_colour+"("+ major_colour+") @"+ part
			if not part:
				part = "item"
			inward_qty['total'].setdefault(part, {
				"size_wise": {},
				"type_wise": {},
				"size_type_wise": {},
				"over_all": 0,
			})

			inward_qty['total'][part]['size_wise'].setdefault(size, 0)
			inward_qty['total'][part]['size_type_wise'].setdefault(size, {})
			received_types = update_if_string_instance(item['received_type_json'])
			if colour not in colours:
				colours.append(colour)
				inward_qty["data"].setdefault(colour, {})
				inward_qty["data"][colour]['values'] = {}
				inward_qty["data"][colour]["part"] = part
				inward_qty["data"][colour]['type_wise_total'] = {}
				inward_qty["data"][colour]['size_wise_total'] = {}
				inward_qty["data"][colour]['colour_total'] = {}
				inward_qty["data"][colour]['colour_total'].setdefault("total", 0)

			inward_qty["data"][colour]["values"].setdefault(size, {})
			inward_qty["data"][colour]['size_wise_total'].setdefault(size, 0)

			for received_type in received_types:
				if received_type not in type_list:
					type_list.append(received_type)
				qty = received_types[received_type]
				inward_qty['total'][part]['size_wise'][size] += qty
				inward_qty['total'][part]['type_wise'].setdefault(received_type, 0)
				inward_qty['total'][part]['type_wise'][received_type] += qty
				inward_qty['total'][part]['size_type_wise'][size].setdefault(received_type, 0)
				inward_qty['total'][part]['over_all'] += qty
				inward_qty['total'][part]['size_type_wise'][size][received_type] += qty
				inward_qty["data"][colour]['size_wise_total'][size] += qty
				inward_qty["data"][colour]['colour_total']['total'] += qty
				inward_qty["data"][colour]["type_wise_total"].setdefault(received_type, 0)
				inward_qty["data"][colour]["type_wise_total"][received_type] += qty	
				inward_qty["data"][colour]["values"][size].setdefault(received_type, 0)
				inward_qty["data"][colour]["values"][size][received_type] += qty

	primary_values = get_ipd_primary_values(ipd)
	return {
		"primary_values": primary_values,
		"types": type_list,
		"data": inward_qty,
		"is_set_item": is_set_item,
		"set_attr": set_attr
	}

@frappe.whitelist()
def get_site_config_value():
    conf = frappe.get_conf()
    return conf

@frappe.whitelist()
def get_inhouse_qty(lot, process):
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import (
		get_ipd_primary_values,
	)

	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
	is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)

	inward_qty = {"data": {}, "total": {}, "over_all": {}}

	wo_list = frappe.get_all(
		"Work Order", filters={"lot": lot, "process_name": process, "docstatus": 1}, pluck="name"
	)
	if not wo_list:
		frappe.msgprint(f"No Work Order's for Process {process}")
		return
	items = frappe.db.sql(
		"""
			SELECT * FROM `tabWork Order Calculated Item` WHERE parent IN %(work_orders)s
		""",{
			"work_orders": tuple(wo_list)
		},as_dict=True,
	)

	for item in items:
		sup_name = frappe.get_cached_value("Work Order", item['parent'], "supplier_name")
		set_comb = update_if_string_instance(item["set_combination"])
		major_colour = set_comb["major_colour"]
		colour = major_colour
		attr_details = get_variant_attr_details(item["item_variant"])
		size = attr_details[primary_attr]
		part = None

		if is_set_item:
			variant_colour = attr_details[pack_attr]
			part = attr_details[set_attr]
			colour = f"{variant_colour}({major_colour}) @ "+ part

		inward_qty["data"].setdefault(colour, {})

		inward_qty['data'][colour].setdefault(sup_name, {
			"values": {},
			"part": part,
			"colour_total": {
				"delivered": 0, 
				"received": 0, 
			},
		})
		inward_qty["data"][colour][sup_name]["values"].setdefault(size, {
			"delivered": 0, 
			"received": 0, 
		})
		if not part:
			part = "item"

		inward_qty['total'].setdefault(part, {})
		inward_qty["total"][part].setdefault(size, {
			"delivered": 0,
			"received": 0,
		})

		received = item["received_qty"] or 0
		delivered = item["delivered_quantity"] or 0

		inward_qty["data"][colour][sup_name]["colour_total"]["received"] += received
		inward_qty["data"][colour][sup_name]["colour_total"]["delivered"] += delivered
		inward_qty["data"][colour][sup_name]["values"][size]["received"] += received
		inward_qty["data"][colour][sup_name]["values"][size]["delivered"] += delivered
		inward_qty["total"][part][size]['received'] += received
		inward_qty["total"][part][size]['delivered'] += delivered
		inward_qty['over_all'].setdefault(part, {
			"delivered": 0,
			"received": 0,
		})
		inward_qty['over_all'][part]['delivered'] += delivered
		inward_qty['over_all'][part]['received'] += received

	primary_values = get_ipd_primary_values(ipd)
	return {
		"primary_values": primary_values,
		"data": inward_qty,
		"is_set_item": is_set_item,
		"set_attr": set_attr,
	}

@frappe.whitelist()
def get_finishing_plan_dict(doc):
	finishing_items = {}
	for row in doc.finishing_plan_details:
		set_comb = update_if_string_instance(row.set_combination)
		key = (row.item_variant, tuple(sorted(set_comb.items())))
		finishing_items.setdefault(key, {
			"inward_quantity": row.inward_quantity,
			"delivered_quantity": row.delivered_quantity,
			"cutting_qty": row.cutting_qty,
			"received_types": update_if_string_instance(row.received_type_json),
			"accepted_qty": row.accepted_qty,
			"set_combination": row.set_combination,
			"dc_qty": row.dc_qty,
			"lot_transferred": row.lot_transferred,
			"ironing_excess": row.ironing_excess,
			"reworked": row.reworked,
			"return_qty": row.return_qty,
			"pack_return_qty": row.pack_return_qty
		})
	return finishing_items	

@frappe.whitelist()
def get_finishing_plan_list(finishing_items):
	finshing_items_list = []
	for key in finishing_items:
		variant, tuple_attrs = key
		finshing_items_list.append({
			"item_variant": variant,
			"cutting_qty": finishing_items[key]['cutting_qty'],
			"inward_quantity": finishing_items[key]['inward_quantity'],
			"delivered_quantity": finishing_items[key]['delivered_quantity'],
			"set_combination": finishing_items[key]['set_combination'],
			"received_type_json": frappe.json.dumps(finishing_items[key]['received_types']),
			"accepted_qty": finishing_items[key]['accepted_qty'],
			"dc_qty": finishing_items[key]['dc_qty'],
			"lot_transferred": finishing_items[key]['lot_transferred'],
			"ironing_excess": finishing_items[key]['ironing_excess'],
			"reworked": finishing_items[key]['reworked'],
			"return_qty": finishing_items[key]['return_qty'],
			"pack_return_qty": finishing_items[key]['pack_return_qty']
		})
	return finshing_items_list	

@frappe.whitelist()
def get_finishing_rework_dict(doc):
	finishing_rework_items = {}
	for row in doc.finishing_plan_reworked_details:
		set_comb = update_if_string_instance(row.set_combination)
		key = (row.item_variant, tuple(sorted(set_comb.items())))
		finishing_rework_items.setdefault(key, {
			"quantity": row.quantity,
			"reworked_quantity": row.reworked_quantity,
			"rejected_qty": row.rejected_qty,
			"set_combination": row.set_combination,
		})	
	return finishing_rework_items

@frappe.whitelist()
def get_finishing_rework_list(finishing_rework_items):
	finishing_rework_items_list = []
	for key in finishing_rework_items:
		variant, tuple_attrs = key
		finishing_rework_items_list.append({
			"item_variant": variant,
			"quantity": finishing_rework_items[key]['quantity'],
			"reworked_quantity": finishing_rework_items[key]['reworked_quantity'],
			"rejected_qty": finishing_rework_items[key]['rejected_qty'],
			"set_combination": finishing_rework_items[key]['set_combination'],
		})	
	return finishing_rework_items_list	

def get_variant_attr_details(variant):
	attr_details = frappe.db.sql(
		""" SELECT attribute, attribute_value FROM `tabItem Variant Attribute` WHERE parent = %(parent)s 
		""", {
			"parent": variant
		}, as_dict=True
	)
	d = {}
	for attr_detail in attr_details:
		d[attr_detail['attribute']] = attr_detail['attribute_value']
	return d

@frappe.whitelist()
def get_work_in_progress_report(category, status, lot_list_val, item_list, process_list):
	process_list = update_if_string_instance(process_list)
	conditions = ""
	con = {}
	if category:
		conditions += ' AND t2.product_category = %(cat)s'
		con['cat'] = category
	
	if status:
		conditions += ' AND t1.status = %(status)s'
		con['status'] = status

	lot_list_val = update_if_string_instance(lot_list_val)
	if lot_list_val:
		conditions += ' AND t1.name IN %(lot_list)s'
		lot_list_val.append("")
		con['lot_list'] = tuple(lot_list_val)

	item_list = update_if_string_instance(item_list)
	if item_list:
		conditions += ' AND t1.item IN %(item_list)s'
		item_list.append("")
		con['item_list'] = tuple(item_list)		

	lot_list = frappe.db.sql(
		f"""
			SELECT t1.name FROM `tabLot` t1 JOIN `tabItem` t2 ON t1.item = t2.name
			WHERE 1 = 1 {conditions}
		""", con, as_dict=True
	)

	lot_dict = {
		"columns": {
			"cut_columns": {
				"Order Qty": "order_qty",
				"Cut Qty": "cut_qty",
				"Order to Cut Diff": "order_to_cut_diff",
			},
			"against_cut_columns": {},
			"sew_columns": {
				"Sewing Sent": "sewing_sent",
				"Cut to Sew Diff": "cut_to_sew_diff",
				"Finishing Inward": "finishing_inward",
				"In Sew": "in_sew"
			},
			"against_sew_columns": {},
			"finishing_columns": {
				"Dispatch": 'dispatch',
				"In Packing": 'in_packing',
				"Cut to Dispatch Diff": "cut_to_dispatch_diff", 
			},
		},
		"diff_columns": ['order_to_cut_diff', 'cut_to_sew_diff', 'in_sew', 'in_packing', "cut_to_dispatch_diff"],
		"lot_data": {}
	}
	for lot in lot_list:
		lot = lot['name']
		ipd, item = frappe.get_value("Lot", lot, ["production_detail", "item"])
		lot_dict['lot_data'].setdefault(lot, {
			"style": item,
			"lot": lot,
			"cut_details": {
				"order_qty": 0,
				"cut_qty": 0,
				"order_to_cut_diff": 0,
			},
			"against_cut_details": {},
			"sewing_details": {
				"sewing_sent": 0,
				"cut_to_sew_diff": 0,
				"finishing_inward": 0,
				"in_sew": 0,
			},
			"against_sew_details": {},
			"finishing_details": {
				"dispatch": 0,
				"in_packing": 0,
				"cut_to_dispatch_diff": 0,
			},
			"last_cut_date": None,
			"sew_sent_date": None,
			"finishing_inward_date": None,
		})
		## ORDER QTY
		order_detail = frappe.db.sql(
			"""
				SELECT sum(quantity) as order_qty, sum(cut_qty) as cutting FROM `tabLot Order Detail` 
				WHERE parent = %(parent)s
			""", {
				"parent": lot,
			}, as_dict=True
		)
		if order_detail:
			lot_dict['lot_data'][lot]['cut_details']['order_qty'] += order_detail[0]['order_qty']
			lot_dict['lot_data'][lot]['cut_details']['cut_qty'] += order_detail[0]['cutting']
			lot_dict['lot_data'][lot]['cut_details']['order_to_cut_diff'] += (order_detail[0]['cutting']- order_detail[0]['order_qty'])

		cutting, sewing = frappe.get_value("Item Production Detail", ipd, ["cutting_process", "stiching_process"])
		sql_data = frappe.db.sql(
			"""
				SELECT max(last_grn_date) as date FROM `tabWork Order` WHERE docstatus = 1 AND
				lot = %(lot)s AND process_name = %(process)s
			""", {
				"lot": lot,
				"process": cutting
			}, as_dict=True
		)
		if sql_data and sql_data[0]['date']:
			lot_dict['lot_data'][lot]['last_cut_date'] = sql_data[0]['date']

		## Sewing Sent and Finishing Inward
		stich_wo_list = get_process_wo_list(sewing, lot)
		for wo in stich_wo_list:
			stich_detail = get_wo_total_delivered_received(wo)
			if stich_detail:
				lot_dict['lot_data'][lot]['sewing_details']['sewing_sent'] += stich_detail[0]['sent']
				lot_dict['lot_data'][lot]['sewing_details']['finishing_inward'] += stich_detail[0]['received']
		
		lot_dict['lot_data'][lot]['sewing_details']['cut_to_sew_diff'] = lot_dict['lot_data'][lot]['cut_details']['cut_qty'] - lot_dict['lot_data'][lot]['sewing_details']['sewing_sent']
		lot_dict['lot_data'][lot]['sewing_details']['in_sew'] = lot_dict['lot_data'][lot]['sewing_details']['finishing_inward'] - lot_dict['lot_data'][lot]['sewing_details']['sewing_sent']
		stich_wo_list.append("")
		sql_data = frappe.db.sql(
			"""
				SELECT max(last_grn_date) as grn_date, min(first_dc_date) as dc_date FROM `tabWork Order` 
				WHERE docstatus = 1 AND lot = %(lot)s AND name IN %(wo_list)s
			""", {
				"lot": lot,
				"wo_list": tuple(stich_wo_list)
			}, as_dict=True
		)

		if sql_data and sql_data[0]['grn_date']:
			lot_dict['lot_data'][lot]['sew_sent_date'] = sql_data[0]['dc_date']
			lot_dict['lot_data'][lot]['finishing_inward_date'] = sql_data[0]['grn_date']

		## Dispatched Qty
		finishing_plan_list =frappe.get_all("Finishing Plan", filters={
			"lot": lot,
		}, pluck="name")
		part_qty = 1
		is_set_item, set_attr = frappe.get_value("Item Production Detail", ipd, ["is_set_item", "set_item_attribute"])
		if is_set_item:
			mapping_value = frappe.db.sql(
				f"""
					SELECT mapping FROM `tabItem Item Attribute` 
					WHERE parent = {frappe.db.escape(ipd)} AND attribute = {frappe.db.escape(set_attr)}
				""", as_dict=True
			)
			if len(mapping_value) > 0:
				map_doc = frappe.get_doc("Item Item Attribute Mapping", mapping_value[0]['mapping'])
				part_qty = len(map_doc.values)

		for finishing_plan in finishing_plan_list:
			pcs_per_box = frappe.get_value("Finishing Plan", finishing_plan, "pieces_per_box")
			finishing_detail = frappe.db.sql(
				"""
					SELECT sum(dispatched) as dispatch_qty FROM `tabFinishing Plan GRN Detail` WHERE
					parent = %(parent)s
				""", {
					"parent": finishing_plan,
				}, as_dict=True
			)
			if finishing_detail:
				lot_dict['lot_data'][lot]['finishing_details']['dispatch'] += (finishing_detail[0]['dispatch_qty'] * pcs_per_box * part_qty)
		
		lot_dict['lot_data'][lot]['finishing_details']['in_packing'] = lot_dict['lot_data'][lot]['finishing_details']['dispatch'] - lot_dict['lot_data'][lot]['sewing_details']['finishing_inward']
		lot_dict['lot_data'][lot]['finishing_details']['cut_to_dispatch_diff'] = lot_dict['lot_data'][lot]['finishing_details']['dispatch'] - lot_dict['lot_data'][lot]['cut_details']['cut_qty']
		
		process_dict, cut, piece = get_ipd_process_dict(ipd)
		last_cut_process = None
		last_piece_process = None
		for process in process_list:
			process_name = process['process_name']
			if not process_dict.get(process_name):
				continue
			column_key = None
			details_key = None
			sent_key = process_name + " Sent"
			rec_key = process_name + " Received"
			sent_val = sent_key.lower().replace(" ", "_")
			rec_val = rec_key.lower().replace(" ", "_")
			diff_key = process_name + " Diff"
			diff_val = diff_key.lower().replace(" ", "_")
			if diff_val not in lot_dict['diff_columns']:
				lot_dict['diff_columns'].append(diff_val)

			against_val = process_name + " to"
			if process_dict[process_name] == cut:
				column_key = 'against_cut_columns'
				details_key = 'against_cut_details'
			else:
				column_key = 'against_sew_columns'
				details_key = 'against_sew_details'

			lot_dict['columns'][column_key].setdefault(sent_key, sent_val)
			lot_dict['columns'][column_key].setdefault(rec_key, rec_val)
			lot_dict['columns'][column_key].setdefault(diff_key, diff_val)
			lot_dict['lot_data'][lot][details_key].setdefault(sent_val, 0)
			lot_dict['lot_data'][lot][details_key].setdefault(rec_val, 0)
			lot_dict['lot_data'][lot][details_key].setdefault(diff_val, 0)

			wo_list = get_process_wo_list(process_name, lot)
			if not wo_list:
				process_exist = frappe.db.sql(
					f"""
						SELECT name FROM `tabIPD Process` WHERE parent = {frappe.db.escape(ipd)}
						AND process_name = {frappe.db.escape(process_name)}
					""", as_dict=True
				)
				val = -1
				if len(process_exist) > 0:
					val = 0

				lot_dict['lot_data'][lot][details_key][sent_val] = val
				lot_dict['lot_data'][lot][details_key][rec_val] = val
				lot_dict['lot_data'][lot][details_key][diff_val] = val 
				continue
			
			for wo in wo_list:
				detail = get_wo_total_delivered_received(wo)
				if detail:
					lot_dict['lot_data'][lot][details_key][sent_val] += detail[0]['sent']
					lot_dict['lot_data'][lot][details_key][rec_val] += detail[0]['received']
					lot_dict['lot_data'][lot][details_key][diff_val] += (detail[0]['received'] - detail[0]['received'])

			if process_dict[process_name] == cut:
				if not last_cut_process:
					against_key = process_name + " to Cut Diff"
					against_val = against_key.lower().replace(" ", "_")
					if against_val not in lot_dict['diff_columns']:
						lot_dict['diff_columns'].append(against_val)
					lot_dict['columns'][column_key].setdefault(against_key, against_val)
					lot_dict['lot_data'][lot][details_key].setdefault(against_val, 0)
					lot_dict['lot_data'][lot][details_key][against_val] += (lot_dict['lot_data'][lot][details_key][rec_val] - lot_dict['lot_data'][lot]['cut_details']["cut_qty"])
				else:
					against_key = process_name + " to "+ last_cut_process + " Diff"
					against_val = against_key.lower().replace(" ", "_")
					if against_val not in lot_dict['diff_columns']:
						lot_dict['diff_columns'].append(against_val)
					lot_dict['columns'][column_key].setdefault(against_key, against_val)
					lot_dict['lot_data'][lot][details_key].setdefault(against_val, 0)
					prev_key = last_cut_process + " Received"
					prev_val = prev_key.lower().replace(" ", "_")
					lot_dict['lot_data'][lot][details_key][against_val] += (lot_dict['lot_data'][lot][details_key][rec_val] - lot_dict['lot_data'][lot][details_key][prev_val])
				last_cut_process = process_name	
			else:
				if not last_piece_process:
					against_key = process_name + " to Sew Diff"
					against_val = against_key.lower().replace(" ", "_")
					if against_val not in lot_dict['diff_columns']:
						lot_dict['diff_columns'].append(against_val)
					lot_dict['columns'][column_key].setdefault(against_key, against_val)
					lot_dict['lot_data'][lot][details_key].setdefault(against_val, 0)
					lot_dict['lot_data'][lot][details_key][against_val] += (lot_dict['lot_data'][lot][details_key][rec_val] - lot_dict['lot_data'][lot]['sewing_details']["finishing_inward"])
				else:
					against_key = process_name + " to "+ last_piece_process + " Diff"
					against_val = against_key.lower().replace(" ", "_")
					if against_val not in lot_dict['diff_columns']:
						lot_dict['diff_columns'].append(against_val)
					lot_dict['columns'][column_key].setdefault(against_key, against_val)
					lot_dict['lot_data'][lot][details_key].setdefault(against_val, 0)
					prev_key = last_piece_process + " Received"
					prev_val = prev_key.lower().replace(" ", "_")
					lot_dict['lot_data'][lot][details_key][against_val] += (lot_dict['lot_data'][lot][details_key][rec_val] - lot_dict['lot_data'][lot][details_key][prev_val])
				last_piece_process = process_name
	return lot_dict	

def get_process_wo_list(process, lot):
	processes = frappe.db.sql(
		"""
			Select parent FROM `tabProcess Details` WHERE process_name = %(process)s OR parent = %(process)s
		""", {
			"process": process,
		}, as_dict=1
	)
	process_names = [p['parent'] for p in processes]
	process_names.append(process)
	wo_list = frappe.get_all("Work Order", filters={
		"lot": lot,
		"docstatus": 1,
		"process_name": ['in', process_names],
		"is_rework": 0,
	}, pluck="name")

	return wo_list

def get_wo_total_delivered_received(wo):
	detail = frappe.db.sql(
		"""
			SELECT sum(delivered_quantity) as sent, sum(received_qty) as received 
			FROM `tabWork Order Calculated Item` WHERE parent = %(parent)s
		""",{
			"parent": wo
		}, as_dict=True
	)
	return detail

@frappe.whitelist()
def get_month_wise_report(lot=None, item=None, start_date=None, end_date=None):
	conditions = ""
	con_dict = {}
	if lot:
		conditions += " AND lot = %(lot)s"
		con_dict['lot'] = lot
	
	if item:
		conditions += " AND item = %(item)s"
		con_dict['item'] = item


	ipd_settings = frappe.get_single("IPD Settings")
	cutting = ipd_settings.default_cutting_process
	sewing = ipd_settings.default_stitching_process

	processes = frappe.db.sql(
		""" 
			SELECT parent FROM `tabProcess Details` WHERE process_name = %(process)s OR parent = %(process)s
		""",{
		"process": cutting
		}, as_dict=1
	)
	process_names = [p['parent'] for p in processes]
	if cutting not in process_names:
		process_names.append(cutting)

	if len(process_names) == 1:
		process_names.append("")

	con_dict['process_name_list'] = tuple(process_names)
	cut_conditions = conditions + " AND process_name IN %(process_name_list)s"

	cut_wo_list = frappe.db.sql(
		f"""
			SELECT name FROM `tabWork Order` WHERE docstatus = 1 {cut_conditions}
		""", con_dict, as_dict=True
	)
	
	month_wise_data = {}
	months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
	start, end = None, None
	if start_date:
		start = getdate(start_date)
		end = getdate(end_date)

	for wo in cut_wo_list:
		wo_doc = frappe.get_doc("Work Order", wo['name'])
		for row in wo_doc.work_order_track_pieces:
			date = row.date
			if start and end and (date > end or date < start):
				continue
			wo_month = str(months[date.month-1])
			month_wise_data.setdefault(wo_month, {
				"cut_qty": 0,
				"sewing_sent": 0,
				"finishing_inward": 0,
				"dispatch": 0,
			})
			month_wise_data[wo_month]['cut_qty'] += row.received_qty

	processes = frappe.db.sql(
		""" 
			SELECT parent FROM `tabProcess Details` WHERE process_name = %(process)s OR parent = %(process)s
		""",{
		"process": sewing
		}, as_dict=1
	)
	process_names = [p['parent'] for p in processes]
	if sewing not in process_names:
		process_names.append(sewing)

	if len(process_names) == 1:
		process_names.append("")

	con_dict['process_name_list'] = tuple(process_names)
	sew_conditions = conditions + " AND process_name IN %(process_name_list)s"

	sew_wo_list = frappe.db.sql(
		f"""
			SELECT name FROM `tabWork Order` WHERE docstatus = 1 {sew_conditions}
		""", con_dict, as_dict=True
	)	

	for wo in sew_wo_list:
		wo_doc = frappe.get_doc("Work Order", wo['name'])
		for row in wo_doc.work_order_track_pieces:
			date = row.date
			if start and end and (date > end or date < start):
				continue
			wo_month = str(months[date.month-1])
			month_wise_data.setdefault(wo_month, {
				"cut_qty": 0,
				"sewing_sent": 0,
				"finishing_inward": 0,
				"dispatch": 0,
			})
			month_wise_data[wo_month]['sewing_sent'] += row.delivered_quantity
			month_wise_data[wo_month]['finishing_inward'] += row.received_qty

	conditions = ""
	con = {}
	if lot:
		conditions += " AND t2.lot = %(lot)s"
		con['lot'] = lot
	if item:
		conditions += " AND t4.name = %(item)s"
		con['item'] = item

	if start_date and end_date:
		conditions += " AND t1.posting_date BETWEEN %(start_date)s AND %(end_date)s"
		con_dict['start_date'] = start_date
		con_dict['end_date'] = end_date

	conditions += " AND t1.against IN %(doc_list)s"
	doc_list = ["Finishing Plan", "Finishing Plan Dispatch"]
	con['doc_list'] = tuple(doc_list)	

	se_list = frappe.db.sql(
		f"""
			SELECT t1.name FROM `tabStock Entry Detail` t2 LEFT JOIN `tabStock Entry` t1 ON t2.parent = t1.name
			LEFT JOIN `tabItem Variant` t3 ON t2.item = t3.name LEFT JOIN `tabItem` t4 ON t3.item = t4.name 
			WHERE t1.docstatus = 1 {conditions} GROUP BY t1.name
		""", con, as_dict=True
	)

	for se in se_list:
		se_doc = frappe.get_doc("Stock Entry", se['name'])
		date = se_doc.posting_date
		wo_month = str(months[date.month-1])
		month_wise_data.setdefault(wo_month, {
			"cut_qty": 0,
			"sewing_sent": 0,
			"finishing_inward": 0,
			"dispatch": 0,
		})
		for row in se_doc.items:
			if lot and row.lot != lot:
				continue
			if item and frappe.get_cached_value("Item Variant", row.item, "item") != item:
				continue

			month_wise_data[wo_month]['dispatch'] += (row.qty * row.conversion_factor)

	return month_wise_data

@frappe.whitelist()
def get_size_wise_stock_report(open_status, lot_list, item_list, category, process_list):
	conditions = ""
	con = {}
	if category:
		conditions += " AND t2.product_category = %(category)s"
		con = {
			"category": category
		}
	lot_list = update_if_string_instance(lot_list)
	item_list = update_if_string_instance(item_list)
	process_list = update_if_string_instance(process_list)
	if lot_list:
		lot_list.append("")
		conditions += " AND t1.name IN %(lot_list)s"
		con['lot_list'] = tuple(lot_list)

	if item_list:
		item_list.append("")
		conditions += " AND t1.item IN %(item_list)s"
		con['item_list'] = tuple(item_list)

	if open_status:
		conditions += " AND t1.status = %(status)s"
		con['status'] = open_status

	lot_list = frappe.db.sql(
		f"""
			SELECT t1.name FROM `tabLot` t1 JOIN `tabItem` t2 ON t1.item = t2.name 
			WHERE 1 = 1 {conditions}
		""", con, as_dict=True
	)
	lot_dict = {
		"lot_data": {},
		"diff_rows": ["order_to_cut_diff","cut_to_sew_diff","in_sew","in_packing","cut_to_dispatch_diff"],
		"rows": {
			"cut_rows": {
				"Order Qty": "order_qty",
				"Cut Qty": "cut_qty",
				"Order to Cut Diff": "order_to_cut_diff",
			},
			"against_cut_rows": {},
			"sew_rows": {
				"Sewing Sent": "sewing_sent",
				"Cut to Sew Diff": "cut_to_sew_diff",
				"Finishing Inward": "finishing_inward",
				"In Sew": "in_sew"
			},
			"against_sew_rows": {},
			"finishing_rows": {
				"Dispatch": 'dispatch',
				"In Packing": 'in_packing',
				"Cut to Dispatch Diff": "cut_to_dispatch_diff", 
				"Work In Progress": "work_in_progress",
			},
		}
	}
	for lot in lot_list:
		lot = lot['name']
		ipd, item = frappe.get_value("Lot", lot, ["production_detail", "item"])
		sewing, primary = frappe.get_value("Item Production Detail", ipd, ["stiching_process", "primary_item_attribute"])

		lot_dict['lot_data'].setdefault(lot, {
			"style": item,
			"lot": lot,
			"sizes": [],
			"cut_details": {
				"order_qty": {},
				"cut_qty": {},
				"order_to_cut_diff": {},
			},
			"against_cut_details": {},
			"sewing_details": {
				"sewing_sent": {},
				"cut_to_sew_diff": {},
				"finishing_inward": {},
				"in_sew": {},
			},
			"against_sew_details": {},
			"finishing_details": {
				"dispatch": {},
				"in_packing": {},
				"cut_to_dispatch_diff": {},
				"work_in_progress": {},
			},
			"total_details": {}
		})
		## ORDER QTY
		lot_doc = frappe.get_doc("Lot", lot)
		sizes = []
		for row in lot_doc.lot_order_details:
			attr_details = get_variant_attr_details(row.item_variant)
			size = attr_details[primary]
			if size not in sizes:
				sizes.append(size)
			lot_dict['lot_data'][lot]['cut_details']['order_qty'].setdefault(size, 0)
			lot_dict['lot_data'][lot]['cut_details']['cut_qty'].setdefault(size, 0)
			lot_dict['lot_data'][lot]['cut_details']['order_to_cut_diff'].setdefault(size, 0)
			lot_dict['lot_data'][lot]['sewing_details']['sewing_sent'].setdefault(size, 0)
			lot_dict['lot_data'][lot]['sewing_details']['finishing_inward'].setdefault(size, 0)
			lot_dict['lot_data'][lot]['sewing_details']['in_sew'].setdefault(size, 0)
			lot_dict['lot_data'][lot]['sewing_details']['cut_to_sew_diff'].setdefault(size, 0)
			lot_dict['lot_data'][lot]['finishing_details']['dispatch'].setdefault(size, 0)
			lot_dict['lot_data'][lot]['finishing_details']['in_packing'].setdefault(size, 0)
			lot_dict['lot_data'][lot]['finishing_details']['cut_to_dispatch_diff'].setdefault(size, 0)
			lot_dict['lot_data'][lot]['finishing_details']['work_in_progress'].setdefault(size, 0)

			lot_dict['lot_data'][lot]['cut_details']['order_qty'][size] += row.quantity
			lot_dict['lot_data'][lot]['cut_details']['cut_qty'][size] += row.cut_qty
			lot_dict['lot_data'][lot]['total_details'].setdefault("order_qty_total", 0)
			lot_dict['lot_data'][lot]['total_details'].setdefault("cut_qty_total", 0)
			lot_dict['lot_data'][lot]['total_details']["order_qty_total"] += row.quantity
			lot_dict['lot_data'][lot]['total_details']["cut_qty_total"] += row.cut_qty
		
		lot_dict['lot_data'][lot]["sizes"] = sizes

		stich_wo_list = get_process_wo_list(sewing, lot)
		for wo in stich_wo_list:
			wo_doc = frappe.get_doc("Work Order", wo)
			for row in wo_doc.work_order_calculated_items:
				attr_details = get_variant_attr_details(row.item_variant)
				size = attr_details[primary]
				lot_dict['lot_data'][lot]['sewing_details']['sewing_sent'][size] += row.delivered_quantity
				lot_dict['lot_data'][lot]['sewing_details']['finishing_inward'][size] += row.received_qty
				lot_dict['lot_data'][lot]['total_details'].setdefault("sewing_sent_total", 0)
				lot_dict['lot_data'][lot]['total_details'].setdefault("finishing_inward_total", 0)
				lot_dict['lot_data'][lot]['total_details']["sewing_sent_total"] += row.delivered_quantity
				lot_dict['lot_data'][lot]['total_details']["finishing_inward_total"] += row.received_qty


		finishing_plan_list =frappe.get_all("Finishing Plan", filters={
			"lot": lot,
		}, pluck="name")

		for finishing_plan in finishing_plan_list:
			fp_doc = frappe.get_doc("Finishing Plan", finishing_plan)
			for row in fp_doc.finishing_plan_grn_details:
				attr_details = get_variant_attr_details(row.item_variant)
				size = attr_details[primary]
				lot_dict['lot_data'][lot]['finishing_details']['dispatch'][size] += (row.dispatched * fp_doc.pieces_per_box)
				lot_dict['lot_data'][lot]['total_details'].setdefault("dispatch_total", 0)
				lot_dict['lot_data'][lot]['total_details']["dispatch_total"] += (row.dispatched * fp_doc.pieces_per_box)

		for size in sizes:		
			sent = lot_dict['lot_data'][lot]['sewing_details']['sewing_sent'][size]
			received = lot_dict['lot_data'][lot]['sewing_details']['finishing_inward'][size] 
			cut_qty = lot_dict['lot_data'][lot]['cut_details']['cut_qty'][size]
			order_qty = lot_dict['lot_data'][lot]['cut_details']['order_qty'][size]
			dispatch_qty = lot_dict['lot_data'][lot]['finishing_details']['dispatch'][size]
			#diff detail
			lot_dict['lot_data'][lot]['sewing_details']['in_sew'][size] += (received - sent)
			lot_dict['lot_data'][lot]['sewing_details']['cut_to_sew_diff'][size] += (sent - cut_qty)
			lot_dict['lot_data'][lot]['cut_details']['order_to_cut_diff'][size] = (cut_qty - order_qty) 
			lot_dict['lot_data'][lot]['finishing_details']['in_packing'][size] += (dispatch_qty - received)
			lot_dict['lot_data'][lot]['finishing_details']['cut_to_dispatch_diff'][size] += (dispatch_qty - cut_qty)
			lot_dict['lot_data'][lot]['finishing_details']['work_in_progress'][size] += (cut_qty - dispatch_qty)
			#total details
			lot_dict['lot_data'][lot]['total_details'].setdefault("in_sew_total", 0)
			lot_dict['lot_data'][lot]['total_details'].setdefault("cut_to_sew_diff_total", 0)
			lot_dict['lot_data'][lot]['total_details'].setdefault("order_to_cut_diff_total", 0)
			lot_dict['lot_data'][lot]['total_details'].setdefault("in_packing_total", 0)
			lot_dict['lot_data'][lot]['total_details'].setdefault("cut_to_dispatch_diff_total", 0)
			lot_dict['lot_data'][lot]['total_details'].setdefault("work_in_progress_total", 0)
			#diff total
			lot_dict['lot_data'][lot]['total_details']["in_sew_total"] += (received - sent)
			lot_dict['lot_data'][lot]['total_details']["cut_to_sew_diff_total"] += (sent - cut_qty)
			lot_dict['lot_data'][lot]['total_details']["order_to_cut_diff_total"] += (cut_qty - order_qty)
			lot_dict['lot_data'][lot]['total_details']["in_packing_total"] += (dispatch_qty - received)
			lot_dict['lot_data'][lot]['total_details']["cut_to_dispatch_diff_total"] += (dispatch_qty - cut_qty)
			lot_dict['lot_data'][lot]['total_details']["work_in_progress_total"] += (cut_qty - dispatch_qty)

		process_dict, cut, piece = get_ipd_process_dict(lot_doc.production_detail)
		last_cut_process = None
		last_piece_process = None
		for process in process_list:
			process_name = process['process_name']
			if not process_dict.get(process_name):
				continue
			row_key = None
			details_key = None
			sent_key = process_name + " Sent"
			rec_key = process_name + " Received"
			sent_val = sent_key.lower().replace(" ", "_")
			rec_val = rec_key.lower().replace(" ", "_")
			diff_key = process_name + " Diff"
			diff_val = diff_key.lower().replace(" ", "_")
			if diff_val not in lot_dict['diff_rows']:
				lot_dict['diff_rows'].append(diff_val)

			against_val = process_name + " to"
			if process_dict[process_name] == cut:
				row_key = 'against_cut_rows'
				details_key = 'against_cut_details'
			else:
				row_key = 'against_sew_rows'
				details_key = 'against_sew_details'

			lot_dict['rows'][row_key].setdefault(sent_key, sent_val)
			lot_dict['rows'][row_key].setdefault(rec_key, rec_val)
			lot_dict['rows'][row_key].setdefault(diff_key, diff_val)
			lot_dict['lot_data'][lot][details_key].setdefault(sent_val, {})
			lot_dict['lot_data'][lot][details_key].setdefault(rec_val, {})
			lot_dict['lot_data'][lot][details_key].setdefault(diff_val, {})

			wo_list = get_process_wo_list(process_name, lot)
			if not wo_list:
				continue

			for wo in wo_list:
				wo_doc = frappe.get_doc("Work Order", wo)
				total_sent_key = sent_val+"_total"
				total_rec_key = rec_val+"_total"
				total_diff_key = diff_val+"_total"
				for row in wo_doc.work_order_calculated_items:
					attr_details = get_variant_attr_details(row.item_variant)
					size = attr_details[primary]
					lot_dict['lot_data'][lot][details_key][sent_val].setdefault(size, 0)
					lot_dict['lot_data'][lot][details_key][rec_val].setdefault(size, 0)
					lot_dict['lot_data'][lot][details_key][diff_val].setdefault(size, 0)
					lot_dict['lot_data'][lot][details_key][sent_val][size] += row.delivered_quantity
					lot_dict['lot_data'][lot][details_key][rec_val][size] += row.received_qty
					lot_dict['lot_data'][lot][details_key][diff_val][size] += (row.received_qty - row.delivered_quantity)
					
					lot_dict['lot_data'][lot]['total_details'].setdefault(total_sent_key, 0)
					lot_dict['lot_data'][lot]['total_details'].setdefault(total_rec_key, 0)
					lot_dict['lot_data'][lot]['total_details'].setdefault(total_diff_key, 0)
					lot_dict['lot_data'][lot]['total_details'][total_sent_key] += row.delivered_quantity
					lot_dict['lot_data'][lot]['total_details'][total_rec_key] += row.received_qty
					lot_dict['lot_data'][lot]['total_details'][total_diff_key] += (row.received_qty - row.delivered_quantity)

			if process_dict[process_name] == cut:
				if not last_cut_process:
					against_key = process_name + " to Cut Diff"
					against_val = against_key.lower().replace(" ", "_")
					if against_val not in lot_dict['diff_rows']:
						lot_dict['diff_rows'].append(against_val)
					
					lot_dict['rows'][row_key].setdefault(against_key, against_val)
					lot_dict['lot_data'][lot][details_key].setdefault(against_val, {})
					for size in sizes:
						rec_value = lot_dict['lot_data'][lot][details_key][rec_val][size]
						cut_value = lot_dict['lot_data'][lot]['cut_details']["cut_qty"][size]
						lot_dict['lot_data'][lot][details_key][against_val].setdefault(size, 0)
						lot_dict['lot_data'][lot][details_key][against_val][size] += (rec_value - cut_value)
						total_against_key = against_val+"_total"
						lot_dict['lot_data'][lot]['total_details'].setdefault(total_against_key, 0)
						lot_dict['lot_data'][lot]['total_details'][total_against_key] += (rec_value - cut_value)
				else:
					against_key = process_name + " to "+ last_cut_process + " Diff"
					against_val = against_key.lower().replace(" ", "_")
					if against_val not in lot_dict['diff_rows']:
						lot_dict['diff_rows'].append(against_val)
					lot_dict['rows'][row_key].setdefault(against_key, against_val)
					lot_dict['lot_data'][lot][details_key].setdefault(against_val, {})
					prev_key = last_cut_process + " Received"
					prev_val = prev_key.lower().replace(" ", "_")
					for size in sizes:
						prev_prs_value = lot_dict['lot_data'][lot][details_key][prev_val][size]
						rec_value = lot_dict['lot_data'][lot][details_key][rec_val][size]
						lot_dict['lot_data'][lot][details_key][against_val].setdefault(size, 0)
						lot_dict['lot_data'][lot][details_key][against_val][size] += (rec_value - prev_prs_value)
						total_against_key = against_val+"_total"
						lot_dict['lot_data'][lot]['total_details'].setdefault(total_against_key, 0)
						lot_dict['lot_data'][lot]['total_details'][total_against_key] += (rec_value - prev_prs_value)
				last_cut_process = process_name	
			else:
				if not last_piece_process:
					against_key = process_name + " to Sew Diff"
					against_val = against_key.lower().replace(" ", "_")
					if against_val not in lot_dict['diff_rows']:
						lot_dict['diff_rows'].append(against_val)
					lot_dict['rows'][row_key].setdefault(against_key, against_val)
					lot_dict['lot_data'][lot][details_key].setdefault(against_val, {})
					for size in sizes:
						sew_inward = lot_dict['lot_data'][lot]['sewing_details']["finishing_inward"][size]
						rec_value = lot_dict['lot_data'][lot][details_key][rec_val][size]
						lot_dict['lot_data'][lot][details_key][against_val].setdefault(size, 0)
						lot_dict['lot_data'][lot][details_key][against_val][size] += (rec_value - sew_inward)
						total_against_key = against_val+"_total"
						lot_dict['lot_data'][lot]['total_details'].setdefault(total_against_key, 0)
						lot_dict['lot_data'][lot]['total_details'][total_against_key] += (rec_value - sew_inward)
				else:
					against_key = process_name + " to "+ last_piece_process + " Diff"
					against_val = against_key.lower().replace(" ", "_")
					if against_val not in lot_dict['diff_rows']:
						lot_dict['diff_rows'].append(against_val)
					lot_dict['rows'][row_key].setdefault(against_key, against_val)
					lot_dict['lot_data'][lot][details_key].setdefault(against_val, {})
					prev_key = last_piece_process + " Received"
					prev_val = prev_key.lower().replace(" ", "_")
					for size in sizes:
						prev_prs_value = lot_dict['lot_data'][lot][details_key][prev_val][size]
						rec_value = lot_dict['lot_data'][lot][details_key][rec_val][size]
						lot_dict['lot_data'][lot][details_key][against_val].setdefault(size, 0)
						lot_dict['lot_data'][lot][details_key][against_val][size] += (rec_value - prev_prs_value)
						total_against_key = against_val+"_total"
						lot_dict['lot_data'][lot]['total_details'].setdefault(total_against_key, 0)
						lot_dict['lot_data'][lot]['total_details'][total_against_key] += (rec_value - prev_prs_value)
				last_piece_process = process_name

	return lot_dict

@frappe.whitelist()
def get_colour_wise_diff_report(lot, process_list):
	lot_doc = frappe.get_doc("Lot", lot)
	ipd_fields = ['is_set_item', 'primary_item_attribute', 'packing_attribute', 'set_item_attribute', 'stiching_process', 'cutting_process']
	is_set_item, primary, pack_attr, set_attr, sewing, cutting = frappe.get_value("Item Production Detail", lot_doc.production_detail, ipd_fields)
	lot_dict = {
		"style": lot_doc.item,
		"lot": lot,
		"sizes": [],
		"values": {},
		"rows": {
			"cut_rows": {
				"Order Qty": "order_qty",
				"Cut Qty": "cut_qty",
				"Order to Cut Diff": "order_to_cut_diff",
			},
			"against_cut_rows": {},
			"sew_rows": {
				"Sewing Sent": "sewing_sent",
				"Cut to Sew Diff": "cut_to_sew_diff",
				"Finishing Inward": "finishing_inward",
				"In Sew": "in_sew"
			},
			"against_sew_rows": {},
		},
		"diff_rows": ["order_to_cut_diff","in_sew","cut_to_sew_diff"]
	}

	process_list = update_if_string_instance(process_list)
	for row in lot_doc.lot_order_details:
		attr_details = get_variant_attr_details(row.item_variant)
		size = attr_details[primary]
		if size not in lot_dict['sizes']:
			lot_dict['sizes'].append(size)
		colour = get_variant_set_colour(attr_details, row.set_combination, is_set_item, pack_attr, set_attr)		
		lot_dict['values'].setdefault(colour, {
			"cut_details": {
				"order_qty": {},
				"cut_qty": {},
				"order_to_cut_diff": {},
			},
			"against_cut_details": {},
			"sewing_details": {
				"sewing_sent": {},
				"cut_to_sew_diff": {},
				"finishing_inward": {},
				"in_sew": {},
			},
			"against_sew_details": {},
			"total_details": {},
			"supplier_details": {}
		})		

		lot_dict['values'][colour]['cut_details']['order_qty'].setdefault(size, 0)
		lot_dict['values'][colour]['cut_details']['cut_qty'].setdefault(size, 0)
		lot_dict['values'][colour]['cut_details']['order_to_cut_diff'].setdefault(size, 0)
		lot_dict['values'][colour]['sewing_details']['sewing_sent'].setdefault(size, 0)
		lot_dict['values'][colour]['sewing_details']['finishing_inward'].setdefault(size, 0)
		lot_dict['values'][colour]['sewing_details']['in_sew'].setdefault(size, 0)
		lot_dict['values'][colour]['sewing_details']['cut_to_sew_diff'].setdefault(size, 0)

		lot_dict['values'][colour]['cut_details']['order_qty'][size] += row.quantity
		lot_dict['values'][colour]['cut_details']['cut_qty'][size] += row.cut_qty
		lot_dict['values'][colour]['cut_details']['order_to_cut_diff'][size] += (row.cut_qty - row.quantity) 

		lot_dict['values'][colour]['total_details'].setdefault("order_qty_total", 0)
		lot_dict['values'][colour]['total_details'].setdefault("cut_qty_total", 0)
		lot_dict['values'][colour]['total_details'].setdefault("order_to_cut_diff_total", 0)

		lot_dict['values'][colour]['total_details']["order_qty_total"] += row.quantity
		lot_dict['values'][colour]['total_details']["cut_qty_total"] += row.cut_qty
		lot_dict['values'][colour]['total_details']["order_to_cut_diff_total"] += (row.cut_qty - row.quantity)

	
	cut_wo_list = get_process_wo_list(cutting, lot)
	if cut_wo_list:
		for wo in cut_wo_list:
			wo_doc = frappe.get_doc("Work Order", wo)
			for row in wo_doc.work_order_calculated_items:
				attr_details = get_variant_attr_details(row.item_variant)
				colour = get_variant_set_colour(attr_details, row.set_combination, is_set_item, pack_attr, set_attr)		
				lot_dict['values'][colour]['supplier_details'].setdefault('cut_qty', [])
				if wo_doc.supplier_name not in lot_dict['values'][colour]['supplier_details']['cut_qty']:
					lot_dict['values'][colour]['supplier_details']['cut_qty'].append(wo_doc.supplier_name)	
					
	stich_wo_list = get_process_wo_list(sewing, lot)
	for wo in stich_wo_list:
		wo_doc = frappe.get_doc("Work Order", wo)
		for row in wo_doc.work_order_calculated_items:
			attr_details = get_variant_attr_details(row.item_variant)
			size = attr_details[primary]
			colour = get_variant_set_colour(attr_details, row.set_combination, is_set_item, pack_attr, set_attr)				
			sent = row.delivered_quantity
			received = row.received_qty
			cut_qty = lot_dict['values'][colour]['cut_details']['cut_qty'][size]
			order_qty = lot_dict['values'][colour]['cut_details']['order_qty'][size]

			lot_dict['values'][colour]['sewing_details']['sewing_sent'][size] += sent
			lot_dict['values'][colour]['sewing_details']['finishing_inward'][size] += received
			lot_dict['values'][colour]['total_details'].setdefault("sewing_sent_total", 0)
			lot_dict['values'][colour]['total_details'].setdefault("finishing_inward_total", 0)
			lot_dict['values'][colour]['total_details']["sewing_sent_total"] += sent
			lot_dict['values'][colour]['total_details']["finishing_inward_total"] += received
			#diff detail
			lot_dict['values'][colour]['sewing_details']['in_sew'][size] += (received - sent)
			lot_dict['values'][colour]['sewing_details']['cut_to_sew_diff'][size] += (sent - cut_qty)
			#total details
			lot_dict['values'][colour]['total_details'].setdefault("in_sew_total", 0)
			lot_dict['values'][colour]['total_details'].setdefault("cut_to_sew_diff_total", 0)
			#diff total
			lot_dict['values'][colour]['total_details']["in_sew_total"] += (received - sent)
			lot_dict['values'][colour]['total_details']["cut_to_sew_diff_total"] += (sent - cut_qty)

			lot_dict['values'][colour]['supplier_details'].setdefault('sewing_sent', [])
			if wo_doc.supplier_name not in lot_dict['values'][colour]['supplier_details']['sewing_sent']:
				lot_dict['values'][colour]['supplier_details']['sewing_sent'].append(wo_doc.supplier_name)	
	
	process_dict, cut, piece = get_ipd_process_dict(lot_doc.production_detail)
	for process in process_list:
		process_name = process['process_name']
		if not process_dict.get(process_name):
			continue
		row_key = None
		details_key = None
		sent_key = process_name + " Sent"
		rec_key = process_name + " Received"
		sent_val = sent_key.lower().replace(" ", "_")
		rec_val = rec_key.lower().replace(" ", "_")
		diff_key = process_name + " Diff"
		diff_val = diff_key.lower().replace(" ", "_")
		if diff_val not in lot_dict['diff_rows']:
			lot_dict['diff_rows'].append(diff_val)

		against_val = process_name + " to"
		if process_dict[process_name] == cut:
			row_key = 'against_cut_rows'
			details_key = 'against_cut_details'
		else:
			row_key = 'against_sew_rows'
			details_key = 'against_sew_details'

		lot_dict['rows'][row_key].setdefault(sent_key, sent_val)
		lot_dict['rows'][row_key].setdefault(rec_key, rec_val)
		lot_dict['rows'][row_key].setdefault(diff_key, diff_val)
		wo_list = get_process_wo_list(process_name, lot)
		if not wo_list:
			continue

		for wo in wo_list:
			wo_doc = frappe.get_doc("Work Order", wo)
			total_sent_key = sent_val+"_total"
			total_rec_key = rec_val+"_total"
			total_diff_key = diff_val+"_total"
			colour_wise_last_process = {}
			for row in wo_doc.work_order_calculated_items:
				attr_details = get_variant_attr_details(row.item_variant)
				size = attr_details[primary]
				colour = get_variant_set_colour(attr_details, row.set_combination, is_set_item, pack_attr, set_attr)				
				lot_dict['values'][colour]['supplier_details'].setdefault(sent_val, [])
				if wo_doc.supplier_name not in lot_dict['values'][colour]['supplier_details'][sent_val]:
					lot_dict['values'][colour]['supplier_details'][sent_val].append(wo_doc.supplier_name)	
				colour_wise_last_process.setdefault(colour, {
					"last_cut_process": None,
					"last_piece_process": None,
				})
				lot_dict['values'][colour][details_key].setdefault(sent_val, {})
				lot_dict['values'][colour][details_key].setdefault(rec_val, {})
				lot_dict['values'][colour][details_key].setdefault(diff_val, {})
				lot_dict['values'][colour][details_key][sent_val].setdefault(size, 0)
				lot_dict['values'][colour][details_key][rec_val].setdefault(size, 0)
				lot_dict['values'][colour][details_key][diff_val].setdefault(size, 0)
				lot_dict['values'][colour][details_key][sent_val][size] += row.delivered_quantity
				lot_dict['values'][colour][details_key][rec_val][size] += row.received_qty
				lot_dict['values'][colour][details_key][diff_val][size] += (row.received_qty - row.delivered_quantity)
				
				lot_dict['values'][colour]['total_details'].setdefault(total_sent_key, 0)
				lot_dict['values'][colour]['total_details'].setdefault(total_rec_key, 0)
				lot_dict['values'][colour]['total_details'].setdefault(total_diff_key, 0)
				lot_dict['values'][colour]['total_details'][total_sent_key] += row.delivered_quantity
				lot_dict['values'][colour]['total_details'][total_rec_key] += row.received_qty
				lot_dict['values'][colour]['total_details'][total_diff_key] += (row.received_qty - row.delivered_quantity)
				
				if process_dict[process_name] == cut:
					if not colour_wise_last_process[colour]['last_cut_process']:
						against_key = process_name + " to Cut Diff"
						against_val = against_key.lower().replace(" ", "_")
						if against_val not in lot_dict['diff_rows']:
							lot_dict['diff_rows'].append(against_val)
						
						lot_dict['rows'][row_key].setdefault(against_key, against_val)
						lot_dict['values'][colour][details_key].setdefault(against_val, {})
						rec_value = lot_dict['values'][colour][details_key][rec_val][size]
						cut_value = lot_dict['values'][colour]['cut_details']["cut_qty"][size]
						lot_dict['values'][colour][details_key][against_val].setdefault(size, 0)
						lot_dict['values'][colour][details_key][against_val][size] += (rec_value - cut_value)
						total_against_key = against_val+"_total"
						lot_dict['values'][colour]['total_details'].setdefault(total_against_key, 0)
						lot_dict['values'][colour]['total_details'][total_against_key] += (rec_value - cut_value)
					else:
						against_key = process_name + " to "+ colour_wise_last_process[colour]['last_cut_process'] + " Diff"
						against_val = against_key.lower().replace(" ", "_")
						if against_val not in lot_dict['diff_rows']:
							lot_dict['diff_rows'].append(against_val)
						lot_dict['rows'][row_key].setdefault(against_key, against_val)
						lot_dict['values'][colour][details_key].setdefault(against_val, {})
						prev_key = colour_wise_last_process[colour]['last_cut_process'] + " Received"
						prev_val = prev_key.lower().replace(" ", "_")
						prev_prs_value = lot_dict['values'][colour][details_key][prev_val][size]
						rec_value = lot_dict['values'][colour][details_key][rec_val][size]
						lot_dict['values'][colour][details_key][against_val].setdefault(size, 0)
						lot_dict['values'][colour][details_key][against_val][size] += (rec_value - prev_prs_value)
						total_against_key = against_val+"_total"
						lot_dict['values'][colour]['total_details'].setdefault(total_against_key, 0)
						lot_dict['values'][colour]['total_details'][total_against_key] += (rec_value - prev_prs_value)
				else:
					if not colour_wise_last_process[colour]['last_piece_process']:
						against_key = process_name + " to Sew Diff"
						against_val = against_key.lower().replace(" ", "_")
						if against_val not in lot_dict['diff_rows']:
							lot_dict['diff_rows'].append(against_val)
						lot_dict['rows'][row_key].setdefault(against_key, against_val)
						lot_dict['values'][colour][details_key].setdefault(against_val, {})
						sew_inward = lot_dict['values'][colour]['sewing_details']["finishing_inward"][size]
						rec_value = lot_dict['values'][colour][details_key][rec_val][size]
						lot_dict['values'][colour][details_key][against_val].setdefault(size, 0)
						lot_dict['values'][colour][details_key][against_val][size] += (rec_value - sew_inward)
						total_against_key = against_val+"_total"
						lot_dict['values'][colour]['total_details'].setdefault(total_against_key, 0)
						lot_dict['values'][colour]['total_details'][total_against_key] += (rec_value - sew_inward)
					else:
						against_key = process_name + " to "+ colour_wise_last_process[colour]['last_piece_process'] + " Diff"
						against_val = against_key.lower().replace(" ", "_")
						if against_val not in lot_dict['diff_rows']:
							lot_dict['diff_rows'].append(against_val)
						lot_dict['rows'][row_key].setdefault(against_key, against_val)
						lot_dict['values'][colour][details_key].setdefault(against_val, {})
						prev_key = colour_wise_last_process[colour]['last_piece_process'] + " Received"
						prev_val = prev_key.lower().replace(" ", "_")
						prev_prs_value = lot_dict['values'][colour][details_key][prev_val][size]
						rec_value = lot_dict['values'][colour][details_key][rec_val][size]
						lot_dict['values'][colour][details_key][against_val].setdefault(size, 0)
						lot_dict['values'][colour][details_key][against_val][size] += (rec_value - prev_prs_value)
						total_against_key = against_val+"_total"
						lot_dict['values'][colour]['total_details'].setdefault(total_against_key, 0)
						lot_dict['values'][colour]['total_details'][total_against_key] += (rec_value - prev_prs_value)

				if process_dict[process_name] == cut:
					colour_wise_last_process[colour]['last_cut_process'] = process_name
				else:
					colour_wise_last_process[colour]['last_piece_process'] = process_name		

	return lot_dict		

def get_variant_set_colour(attr_details, set_combination, is_set_item, pack_attr, set_attr):
	set_comb = update_if_string_instance(set_combination)
	major_colour = set_comb['major_colour']
	colour = major_colour
	part = None
	if is_set_item:
		variant_colour = attr_details[pack_attr]
		part = attr_details[set_attr]
		colour = variant_colour+"("+ major_colour+") @"+ part
	return colour

def get_ipd_process_dict(ipd):
	ipd_process_data = frappe.db.sql(
		f"""
			SELECT process_name, stage FROM `tabIPD Process` WHERE parent = {frappe.db.escape(ipd)}
		""", as_dict=True
	)
	cut, piece = frappe.get_value("Item Production Detail", ipd, ['stiching_in_stage', 'stiching_out_stage']) 
	process_dict = {}
	for row in ipd_process_data:
		process_dict[row['process_name']] = row['stage']
	return process_dict, cut, piece	
