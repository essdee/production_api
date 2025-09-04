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
	from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import get_variant_attr_details
	from production_api.production_api.doctype.item.item import get_or_create_variant
	attr_details = get_variant_attr_details(variant)
	del attr_details[pack_attr]
	attr_details[dept_attr] = "Loose Piece"
	item_name = frappe.get_value("Item Variant", variant, "item")
	variant = get_or_create_variant(item_name, attr_details)
	return variant

@frappe.whitelist()
def get_inward_qty(lot, process):
	from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import get_variant_attr_details
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	wo_list = frappe.get_all("Work Order", filters={
		"lot": lot,
		"process_name": process,
		"docstatus": 1,
	}, pluck="name")
	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
	is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	inward_qty = {}
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
				colour = variant_colour+"("+ major_colour+")"
			received_types = update_if_string_instance(item['received_type_json'])
			if colour not in colours:
				colours.append(colour)
				inward_qty.setdefault(colour, {})
				inward_qty[colour]['values'] = {}
				inward_qty[colour]["part"] = part
				inward_qty[colour]['type_wise_total'] = {}
				inward_qty[colour]['size_wise_total'] = {}
				inward_qty[colour]['colour_total'] = {}
				inward_qty[colour]['colour_total'].setdefault("total", 0)

			inward_qty[colour]["values"].setdefault(size, {})
			inward_qty[colour]['size_wise_total'].setdefault(size, 0)

			for received_type in received_types:
				if received_type not in type_list:
					type_list.append(received_type)
				qty = received_types[received_type]
				inward_qty[colour]['size_wise_total'][size] += qty
				inward_qty[colour]['colour_total']['total'] += qty
				inward_qty[colour]["type_wise_total"].setdefault(received_type, 0)
				inward_qty[colour]["type_wise_total"][received_type] += qty	
				inward_qty[colour]["values"][size].setdefault(received_type, 0)
				inward_qty[colour]["values"][size][received_type] += qty

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
