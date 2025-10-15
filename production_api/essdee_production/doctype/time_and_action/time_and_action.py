# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe, math
from frappe.model.document import Document
from frappe.utils import date_diff, getdate, flt
from production_api.utils import update_if_string_instance
from production_api.essdee_production.doctype.holiday_list.holiday_list import get_events_len, get_next_date

class TimeandAction(Document):
	def before_validate(self):
		if frappe.flags.in_patch:
			return
		if not self.is_new():
			data = {}
			for item in self.details:
				if item.actual_date:
					item.completed = 1
					data[item.action] = item.actual_date 
				else:
					item.completed = 0	

			for item in self.dependent_details:
				if data.get(item.dependent_action):
					item.dependent_action_date = data[item.dependent_action]
				else:
					item.dependent_action_date = None	

@frappe.whitelist()
def get_time_and_action_details(docname):
	doc = frappe.get_doc("Time and Action",docname)
	item_list = [item.as_dict() for item in doc.details]
	status = doc.status
	return {
		"item_list" : item_list,
		"status" : status
	}	

@frappe.whitelist()
def revert_t_and_a(doc_name):
	doc = frappe.get_doc("Lot", doc_name)
	t_and_a_list = []
	for row in doc.lot_time_and_action_details:
		t_and_a_list.append(row.time_and_action)

	doc.set("lot_time_and_action_details", [])
	doc.save()
	t_and_a_list = tuple(t_and_a_list)
	frappe.db.sql(
		f"""
			DELETE FROM `tabTime and Action` WHERE name in {t_and_a_list} 
		"""
	)	
	frappe.db.sql(
		f"""
			DELETE FROM `tabTime and Action Detail` WHERE parent in {t_and_a_list} 
		"""
	)
	frappe.db.sql(
		f"""
			DELETE FROM `tabTime and Action Dependent Detail` WHERE parent IN {t_and_a_list}
		"""
	)
	frappe.db.sql(
		f"""
			DELETE FROM `tabTime and Action Revised Date` WHERE parent IN {t_and_a_list}
		"""
	)

@frappe.whitelist()
def make_complete(time_and_action):
	t_and_a = frappe.get_doc("Time and Action",time_and_action)
	check = True
	for item in t_and_a.details:
		if not item.actual_date and not item.completed:
			check = False
			break
	if check:
		t_and_a.status = "Completed"
		t_and_a.save()	
	else:
		frappe.msgprint("Not all the Actions are Completed")

@frappe.whitelist()
def get_t_and_a_preview_data(start_date, table, is_template=False, master_doc=None):
	table = update_if_string_instance(table)
	preview_data = {}
	merge_process = {}
	merge_process_date = {}
	doc_data = {}

	for row in table:
		if not master_doc:
			doctype="Action Master"
			if is_template:
				doctype = "Action Master Template"
			doc = frappe.get_doc(doctype, row['master'])
		else:
			doc = master_doc
		doc_data[row['colour']] = doc
		day = start_date
		action_completion_date = {}
		dependent_action = build_dependent_action_map(doc)

		for data in doc.details:
			if data.merge_action:
				entry = merge_process.setdefault(data.action, {"count": 0, "lead_time": data.lead_time})
				if entry['lead_time'] != data.lead_time:
					frappe.throw(f"Different Lead Times for Action {data.action}")
				entry['count'] += 1

			dependent_list = dependent_action.get(data.action)
			if dependent_list:
				dept, dep_date = get_latest_dependency_date(dependent_list, action_completion_date)
				day = get_next_date(dep_date, data.lead_time) if dep_date else get_next_date(day, data.lead_time)
			else:
				day = get_next_date(day, data.lead_time)

			action_completion_date[data.action] = day
			merge_process_date[data.action] = max(merge_process_date.get(data.action, day), day)

	for act, info in merge_process.items():
		if info['count'] != len(table):
			frappe.throw(f"{act} is not a Merge Action in Action Master")

	for row in table:
		preview_data[row['colour']] = []
		doc = doc_data[row['colour']]
		day = start_date
		action_completion_date = {}
		dependent_action = build_dependent_action_map(doc)

		for data in doc.details:
			dependent_list = dependent_action.get(data.action)
			if dependent_list:
				if data.merge_action:
					dept, dep_date = get_latest_dependency_date(dependent_list, merge_process_date)
				else:
					dept, dep_date = get_latest_dependency_date(dependent_list, action_completion_date)
				if dep_date:
					day = get_next_date(dep_date, data.lead_time)
				else:
					day = get_next_date(day, data.lead_time)
			else:
				day = get_next_date(day, data.lead_time)

			struct = {
				"action": data.action,
				"lead_time": data.lead_time,
				"department": data.department,
				"date": day,
				"rescheduled_date": day,
			}
			if getattr(data, "work_station", None):
				struct["work_station"] = data.work_station

			action_completion_date[data.action] = day
			preview_data[row['colour']].append(struct)

	return preview_data

def get_latest_dependency_date(dependent_list, completion_dates):
	valid_dates = [(dept, completion_dates.get(dept)) for dept in dependent_list if completion_dates.get(dept)]
	if not valid_dates:
		return None, None
	return max(valid_dates, key=lambda x: x[1]) 

def build_dependent_action_map(doc):
	dependent_map = {}
	for d in doc.action_master_dependent_details:
		dependent_map.setdefault(d.action, []).append(d.dependent_action)
	return dependent_map

@frappe.whitelist()
def create_time_and_action(lot, item_name, args , values, total_qty, items):
	args = update_if_string_instance(args)
	values = update_if_string_instance(values)	
	
	sizes = args['sizes']
	ratios = args['ratios']
	combo = args['combo']
	item_list = values['table']
	start_date = values['start_date']
	merge_process = {}
	one_colour_prs = {}
	merge_process_date = {}
	sizes = sizes[:-1]
	d = {}
	items = update_if_string_instance(items)
	lot_items = []
	for idx,item in enumerate(item_list):
		dependent_action = {}
		for d in items[item['colour']]['dependent_details']:
			dependent_action.setdefault(d['action'], []).append(d['dependent_action'])
		
		action_completion_date = {}
		day = start_date
		for data in items[item['colour']]['details']:
			if data['merge_action']:
				entry = merge_process.setdefault(data['action'], {"count": 0, "lead_time": data['lead_time']})
				if entry['lead_time'] != data['lead_time']:
					frappe.throw(f"Different Lead Times for Action {data['action']}")
				entry['count'] += 1

			if data['one_colour_process']:
				one_colour_prs.setdefault(data['action'], 0)
				one_colour_prs[data['action']] += 1

			dependent_list = dependent_action.get(data['action'])
			if dependent_list:
				dept, dep_date = get_latest_dependency_date(dependent_list, action_completion_date)
				day = get_next_date(dep_date, data['lead_time']) if dep_date else get_next_date(day, data['lead_time'])
			else:
				day = get_next_date(day, data['lead_time'])

			action_completion_date[data['action']] = day
			merge_process_date[data['action']] = max(merge_process_date.get(data['action'], day), day)

	total_colour = len(item_list) 
	for act in one_colour_prs:
		if one_colour_prs[act] != total_colour:
			frappe.throw(f"Action {act} is not setted as One Colour Process in All Action Master")
	
	for act in merge_process:
		if merge_process[act]['count'] != total_colour:
			frappe.throw(f"Action {act} is not setted as Merge Process in All Action Master")

	for idx,item in enumerate(item_list):
		new_doc = frappe.new_doc("Time and Action")
		new_doc.update({
			"lot":lot,
			"item":item_name,
			"sizes":sizes,
			"colour":item['colour'],
			"master":item["master"],
			"start_date":start_date,
			"major_colour": item['major_colour']
		})
		if combo:
			new_doc.qty = math.ceil(flt(total_qty)/flt(combo))
		else:
			new_doc.qty = math.ceil(flt(total_qty)/flt(ratios[idx]))
		
		dependent_list = []
		action_completion_date = {}
		dependent_action = {}
		for dept in items[item['colour']]['dependent_details']:
			dependent_action.setdefault(dept['action'], []).append(dept['dependent_action'])
			dependent_list.append({
				"action": dept['action'],
				"dependent_action": dept['dependent_action']
			})
	
		child_table = []
		x = 1
		day = start_date
		day2 = start_date
		for colour_item in items[item['colour']]['details']:
			if dependent_action.get(colour_item['action']):
				dependent_process_list = dependent_action.get(colour_item['action'])
				if colour_item['merge_action']:
					dept, dep_date = get_latest_dependency_date(dependent_process_list, merge_process_date)
				else:
					dept, dep_date = get_latest_dependency_date(dependent_process_list, action_completion_date)
				if dep_date:
					day = get_next_date(dep_date, colour_item['lead_time'])
				else:
					day = get_next_date(day, colour_item['lead_time'])
			else:	
				day = get_next_date(day, colour_item['lead_time'])

			struct = {
				"action":colour_item['action'],
				"lead_time":colour_item['lead_time'],
				"department":colour_item['department'],
				"date":day,
				"planned_start_date": day,
				"rescheduled_date":day,
				"rescheduled_start_date":day,
				"index2":x,
				"merge_action": 1 if merge_process.get(colour_item['action']) else 0 ,
				"one_colour_process": 1 if one_colour_prs.get(colour_item['action']) else 0
			}
			if colour_item.get('work_station'):
				struct["work_station"] = colour_item['work_station']
			
			action_completion_date[colour_item['action']] = day	
			day2 = get_next_date(day2, colour_item['lead_time']	)
			x = x + 1
			child_table.append(struct)

		new_doc.set("details",child_table)
		new_doc.set("dependent_details", dependent_list)
		new_doc.set("end_date", day)
		new_doc.save()
		lot_items.append({
			"colour":item['colour'],
			"master":item["master"],
			"time_and_action":new_doc.name,	
		})
	lot_doc = frappe.get_doc("Lot",lot)
	lot_doc.set("lot_time_and_action_details",lot_items)
	lot_doc.save()

@frappe.whitelist()
def get_t_and_a_update_data(lot, item):
	data = {}
	conditions = ""
	con = {}

	conditions += " and t3.status != 'Completed'"	

	data.setdefault(lot, {
		"masters": {},
		"performance": 0,
		"over_all_delay": 0,
	})
	t_and_a_list = frappe.db.sql(
		f"""
			SELECT t1.time_and_action, t1.master FROM `tabLot Time and Action Detail` as t1 JOIN 
			`tabTime and Action Detail` as t2 ON t2.parent = t1.time_and_action JOIN 
			`tabTime and Action` as t3 ON t2.parent = t3.name 
			WHERE t1.parent = '{lot}' {conditions} GROUP BY t1.time_and_action
		""",con, as_dict=True
	)
	max_delay = 0
	masters = []
	for t_and_a in t_and_a_list:
		if t_and_a.master not in masters:
			masters.append(t_and_a.master)
	
	actual_date_details = {}
	t_and_a_docs = {}
	for master in masters:
		data[lot]['masters'].setdefault(master, {"actions": [], "datas": []})
		for t_and_a in t_and_a_list:
			if t_and_a.master == master:
				doc = frappe.get_doc("Time and Action", t_and_a.time_and_action)
				t_and_a_docs[t_and_a.time_and_action] = doc
				for row in doc.details:
					actual_date_details.setdefault(row.action, []).append(row.actual_date if row.actual_date else None)

	for master in masters:
		data[lot]['masters'].setdefault(master, {"actions": [], "datas": []})
		for t_and_a in t_and_a_list:
			if t_and_a.master == master:
				doc = t_and_a_docs[t_and_a.time_and_action]
				for row in doc.details:
					if not row.one_colour_process or not row.actual_date:
						continue

					for idx, d in enumerate(actual_date_details[row.action]):
						if not d or d > row.actual_date:
							actual_date_details[row.action][idx] = row.actual_date

	merge_actions = {}
	max_revised = 0
	size_set_colour = frappe.get_value("Lot", lot, "size_set_colour")
	for master in masters:
		data[lot]['masters'].setdefault(master, {"actions": [], "datas": []})
		for t_and_a in t_and_a_list:
			if t_and_a.master == master:
				doc = t_and_a_docs[t_and_a.time_and_action]
				d = {
					"item":doc.item,
					"master": doc.master,
					"major_colour": doc.major_colour,
					"revised_times": doc.revised,
					"colour": doc.colour,
					"sizes": doc.sizes,
					"qty": doc.qty,
					"start_date": doc.start_date,
					"delay": doc.delay,
					"rescheduled_delay": doc.rescheduled_delay,
					"t_and_a": t_and_a.time_and_action,
					"updated": False,
					"last_action": doc.action,
					"performance": get_performance(doc.delay),
				}
				if doc.revised > max_revised:
					max_revised = doc.revised

				if doc.delay < max_delay:
					max_delay = doc.delay
				if not data[lot]['masters'][master]['actions']:
					for row in doc.details:
						data[lot]['masters'][master]['actions'].append(row.action)
				d['actions'] = []
				idx = 0
				dependent_details = {}
				for row in doc.dependent_details:
					dependent_details.setdefault(row.action, {})
					dependent_details[row.action][row.dependent_action] = row.dependent_action_date
				end_date = None
				delay = False
				d['rescheduled_details'] = {}
				for row in doc.details:
					d['rescheduled_details'].setdefault(row.action, {
						"planned": row.planned_start_date,
						"freeze_date": row.date,
						"rescheduled_dates": [],
						"actual_date": row.actual_date,
						"cumulative_delay": get_diff(row.date, row.actual_date) if row.actual_date else 0,
						"reason": row.reason,
						"performance": row.performance,
						"date_diff": row.date_diff,
						"actual_delay": row.actual_delay,
					})
					x = {
						"planned_start_date": row.planned_start_date,
						"action": row.action,
						"department":row.department,
						"date":row.date,
						"rescheduled_date":row.rescheduled_date,
						"one_colour_process": row.one_colour_process,
						"actual_date":row.actual_date,
						"cumulative_delay": get_diff(row.date, row.actual_date) if row.actual_date else 0,
						"reason": row.reason,
						"performance": row.performance,
						"date_diff": row.date_diff,
						"actual_delay": row.actual_delay,
						"index": idx,
						"lead_time": row.lead_time,
						"merge_action": row.merge_action,
						"dependent_details": dependent_details.get(row.action, None)
					}
					if row.merge_action:
						merge_actions.setdefault(row.action, [])
						merge_actions[row.action].append(row.get('actual_date', None))

					end_date = row.rescheduled_date
					if row.rescheduled_date > row.date:
						delay = True
					else:
						delay = False	

					if dependent_details.get(row.action):
						dependent_completed = True
						for act in dependent_details[row.action]:
							if row.merge_action:
								if None in actual_date_details[act]:
									dependent_completed = False
									break
							else:
								if not dependent_details[row.action][act]:
									dependent_completed = False
									break
						if dependent_completed and not row.actual_date:
							x['enable_date'] = True
						else:
							x['enable_date'] = False	
					else:
						if not row.actual_date:
							x['enable_date'] = True
					
					if row.one_colour_process and doc.major_colour != size_set_colour:
						x['enable_date'] = False
					
					d['actions'].append(x)
					idx = idx + 1
				
				d['end_date'] = end_date
				d['end_date_delay'] = delay
				actions = {}
				for row in doc.time_and_action_revised_dates:
					d['rescheduled_details'].setdefault(row.action, [])
					d['rescheduled_details'][row.action]['rescheduled_dates'].append(row.from_date)

				for row in d['actions']:
					actions.setdefault(row['action'], [])
					if row['actual_date'] and row['dependent_details']:
						for dept_act in row['dependent_details']:
							actions[dept_act].append(row['action'])

				for row in d['actions']:
					if row['actual_date'] and len(actions[row['action']]) == 0:
						row['remove_date'] = True	
					else:
						row['remove_date'] = False		
				data[lot]['masters'][master]['datas'].append(d)

	not_completed = []
	for act in merge_actions:
		if None in merge_actions[act]:
			not_completed.append(act)

	for master in data[lot]['masters']:
		for data_row in data[lot]['masters'][master]['datas']:
			for row in data_row['actions']:
				if not row.get('enable_date'):
					continue
				if not row['enable_date'] or not row['dependent_details']:
					continue
				for act in row['dependent_details']:
					if act in not_completed:
						row['enable_date'] = False

	data[lot]['performance'] = get_performance(max_delay)
	data[lot]['over_all_delay'] = max_delay
	based_on_delay = frappe.db.get_single_value("T and A Settings", "ordering_based_on_delay")			
	if based_on_delay:
		data = sort_by_delay(data)

	t_and_a_settings = frappe.get_single("T and A Settings")	
	user = frappe.session.user
	department_data = frappe.db.sql(
		"""
			SELECT parent FROM `tabDepartment User` WHERE user = %(user)s
		""", {
			"user": user
		}, as_dict=True
	)
	department = department_data[0]['parent'] if department_data else None
	return {
		"data":data,
		"role": t_and_a_settings.revised_date_approver_role,
		"revised_limit": t_and_a_settings.revising_days_limit,
		"max_revised": max_revised,
		"department": department,
		"user": user,
	}

def sort_by_delay(data):
	for lot in data:
		for master in data[lot]['masters']:
			data[lot]['masters'][master]['datas'].sort(key=lambda x: x['rescheduled_delay'])
	return data		

def get_diff(rescheduled_date, actual_date):
	diff = date_diff(rescheduled_date,actual_date)
	date1 = rescheduled_date
	date2 = actual_date
	if getdate(rescheduled_date) > getdate(actual_date):
		date1 = actual_date
		date2 = rescheduled_date

	events2_len = get_events_len(date1,date2)
	diff = diff + events2_len if diff < 0 else diff - events2_len
	return diff

def get_t_and_a_datediff(date, actual_date):
	d = date_diff(date,actual_date)
	date1 = date
	date2 = actual_date
	if getdate(date1) > getdate(date2):
		date1 = actual_date
		date2 = date
	
	events_len = get_events_len(date1,date2)
	d = d + events_len if d < 0 else d - events_len

	return d

def get_performance(diff):
	perf = None
	if diff < -3:
		perf = 25
	elif diff == -3:
		perf = 50
	elif diff == -2:
		perf = 75
	elif diff == -1:
		perf = 85
	else:
		perf = 100
	return perf		

@frappe.whitelist()
def get_update_rescheduled_date(updated_date, key, updated_action, data_index, total_data, cur_index, lot, master):
	actual_date_details = {}
	rescheduled_date_details = {}
	total_data = update_if_string_instance(total_data)
	if key == "updated":
		total_data[lot]['masters'][master]['datas'][int(data_index)]['actions'][int(cur_index)]['actual_date'] = updated_date
	else:
		total_data[lot]['masters'][master]['datas'][int(data_index)]['actions'][int(cur_index)]['actual_date'] = None

	for master_val in total_data[lot]['masters']:
		for data_row in total_data[lot]['masters'][master_val]['datas']:
			for row in data_row['actions']:
				actual_date_details.setdefault(row['action'], []).append(row['actual_date'] if row['actual_date'] else None)
				rescheduled_date_details.setdefault(row['action'], []).append(row['rescheduled_date'] if row['rescheduled_date'] else None)
	
	size_set_colour = frappe.get_value("Lot", lot, "size_set_colour")
	for master_val in total_data[lot]['masters']:
		for data_row in total_data[lot]['masters'][master_val]['datas']:
			for row in data_row['actions']:
				if not row['one_colour_process'] or not row['actual_date']:
					continue
				for idx, d in enumerate(actual_date_details[row['action']]):
					if not d or d < row['actual_date']:
						actual_date_details[row['action']][idx] = row['actual_date']

				for idx, d in enumerate(rescheduled_date_details[row['action']]):
					if not d or d < row['rescheduled_date']:
						rescheduled_date_details[row['rescheduled_date']][idx] = row['rescheduled_date']		

	updated_colour = total_data[lot]['masters'][master]['datas'][int(data_index)]['colour']
	merge_actions = []
	for master_val in total_data[lot]['masters']:
		index = -1
		for data_row in total_data[lot]['masters'][master_val]['datas']:
			index += 1
			day = None
			actions = {}
			action_completion_date = {}
			dependent_action = {}
			for row in data_row['actions']:
				if row['merge_action'] and row['action'] not in merge_actions:
					merge_actions.append(row['action'])

				actions.setdefault(row['action'], [])
				if row['actual_date'] and row['dependent_details']:
					for dept_act in row['dependent_details']:
						actions[dept_act].append(row['action'])
				action_completion_date[row['action']] = row['actual_date'] if row['actual_date'] else row['rescheduled_date']

				if row['dependent_details']:	
					dependent_action.setdefault(row['action'], {})
					for dept_act in row['dependent_details']:
						dependent_action[row['action']].setdefault(dept_act, None) 
						dependent_action[row['action']][dept_act] = row['dependent_details'][dept_act]
						if dept_act == updated_action and data_row['colour'] ==  updated_colour:
							dependent_action[row['action']][dept_act] = updated_date
							if key == "updated":
								row['dependent_details'][dept_act] = updated_date
							else:
								row['dependent_details'][dept_act] = None

			if data_row['colour'] ==  updated_colour:
				action_completion_date[updated_action] = updated_date if key == "updated" else None

			for row in data_row['actions']:
				if row['actual_date'] and len(actions[row['action']]) == 0:
					row['remove_date'] = True	
				else:
					row['remove_date'] = False	
				if row['actual_date']:
					day = row['actual_date']
				else:
					if row['merge_action']:
						if row['dependent_details']:
							all_updated = True
							greater_date = None
							for dept_act in row['dependent_details']:
								for d in actual_date_details[dept_act]:
									if d:
										if not greater_date:
											greater_date = d
										if greater_date < d:
											greater_date = d
							if greater_date:
								day = get_next_date(greater_date, row['lead_time'])
								row['rescheduled_date'] = day
							else:
								greater_date = None
								for dept_act in row['dependent_details']:
									for d in rescheduled_date_details[dept_act]:
										if d:
											if not greater_date:
												greater_date = d
											if greater_date < d:
												greater_date = d

								if not greater_date:				
									row['rescheduled_date'] = row['date']
									day = row['rescheduled_date']
								else:
									day = get_next_date(greater_date, row['lead_time'])
									row['rescheduled_date'] = day	
						else:
							row['rescheduled_date'] = row['date']
							day = row['rescheduled_date']
					else:
						if dependent_action.get(row['action']):
							d = None
							dependent_last_action = None
							for k in dependent_action[row['action']]:
								if not d:
									dependent_last_action = k
									d = dependent_action[row['action']][k]
								else:
									if dependent_action[row['action']][k] and dependent_action[row['action']][k] > d:
										d = dependent_action[row['action']][k]
										dependent_last_action = k

							dependent = dependent_last_action
							if dependent in merge_actions:
								greater_date = None
								for d in actual_date_details[dependent]:
									if d:
										if not greater_date:
											greater_date = d
										if greater_date < d:
											greater_date = d
								if greater_date:
									day = get_next_date(greater_date, row['lead_time'])
									row['rescheduled_date'] = day
								else:
									greater_date = None
									for d in rescheduled_date_details[dependent]:
										if d:
											if not greater_date:
												greater_date = d
											if greater_date < d:
												greater_date = d

									if not greater_date:				
										row['rescheduled_date'] = row['date']
										day = row['rescheduled_date']
									else:
										day = get_next_date(greater_date, row['lead_time'])
										row['rescheduled_date'] = day	
							else:		
								day = get_next_date(action_completion_date[dependent], row['lead_time'])	
						else:	
							if not day:
								day = row['date']
							else:	
								day = get_next_date(day, row['lead_time'])

				action_completion_date[row['action']] = day	
				rescheduled_date_details[row['action']][index] = day
				if not row['actual_date']:
					row['rescheduled_date'] = day
				for act in dependent_action:
					for dept_act in dependent_action[act]:
						if dept_act == row['action']:
							dependent_action[act][dept_act] = day	
				
	for master_val in total_data[lot]['masters']:
		for data_row in total_data[lot]['masters'][master_val]['datas']:
			last_action = None
			end_date_delay = None
			last_row = data_row["actions"][-1]
			delay = get_diff(last_row['rescheduled_date'], last_row['planned_start_date'])
			if delay < 0:
				end_date_delay = True
			else:
				end_date_delay = False	

			end_date = last_row['actual_date'] if last_row['actual_date'] else last_row['rescheduled_date']	

			performance = get_performance(delay)
			rescheduled_delay = get_diff(last_row['rescheduled_date'], row['date'])
			data_row['rescheduled_delay'] = rescheduled_delay
			data_row['performance'] = performance
			data_row['delay'] = delay
			data_row['end_date'] = end_date
			data_row['end_date_delay'] = end_date_delay

			for row in data_row['actions']:
				if row['actual_date']:
					row['date_diff'] = get_diff(row['rescheduled_date'], row['actual_date'])
					row['performance'] = get_performance(row['date_diff'])
					row['actual_delay'] = get_diff(row['planned_start_date'], row['actual_date'])
					row['cumulative_delay'] = get_diff(row['date'], row['actual_date'])
					row['enable_date'] = False
				else:
					row['date_diff'] = 0
					row['performance'] = 0
					row['actual_delay'] = 0
					row['cumulative_delay'] = 0
					if not last_action:
						last_action = row['action']
					if row['one_colour_process']:
						pass
					elif row['merge_action']:
						if row['dependent_details']:
							all_updated = True
							for dept_act in row['dependent_details']:
								if None in actual_date_details[dept_act]:
									all_updated = False
									break
							if all_updated:
								row['enable_date'] = True
							else:
								row['enable_date'] = False	
						else:
							row['enable_date'] = True		
					else:	
						if row['dependent_details'] and not row['actual_date']:
							included_merge = False
							merge_list = []
							for act in row['dependent_details']:
								if act in merge_actions:
									merge_list.append(act)
									included_merge = True
							if not included_merge:
								enable = True
								for act in row['dependent_details']:
									if not row['dependent_details'][act]:
										enable = False
										break
								row['enable_date'] = enable
							else:
								enable = True
								for act in merge_list:
									if None in actual_date_details[act]:
										enable = False
										break
								row['enable_date'] = enable	
								
						elif not row['dependent_details'] and not row['actual_date']:
							row['enable_date'] = True			
						else:
							row['enable_date'] = False		
					if row['one_colour_process'] and data_row['major_colour'] != size_set_colour:
						row['enable_date'] = False

			data_row['last_action'] = last_action
	
	return {
		"details": total_data[lot]['masters'][master]['datas'][int(data_index)]['actions'],
		"diff": delay,
		"total_data": total_data 
	}

@frappe.whitelist()
def update_t_and_a(data):
	data = update_if_string_instance(data)
	for lot in data:
		for master in data[lot]['masters']:
			for row in data[lot]['masters'][master]['datas']:
				doc = frappe.get_doc("Time and Action", row['t_and_a'])
				doc.set("details", row['actions'])
				doc.action = row['last_action']
				last_action = row["actions"][-1]
				planned = last_action['planned_start_date']
				rescheduled = last_action['rescheduled_date']
				delay = get_diff(rescheduled, planned)
				doc.delay = delay
				doc.rescheduled_delay = get_diff(rescheduled, last_action['date'])
				if last_action['actual_date']:
					doc.end_date = last_action['actual_date']
				else:
					doc.end_date = last_action['rescheduled_date']	
				doc.save()

@frappe.whitelist()
def revise_date(data, reason):
	data = update_if_string_instance(data)
	for lot in data:
		for master in data[lot]['masters']:
			for row in data[lot]['masters'][master]['datas']:
				doc = frappe.get_doc("Time and Action", row['t_and_a'])
				revise_dates = []
				for tdata in doc.time_and_action_revised_dates:
					revise_dates.append({
						"action": tdata.action,
						"from_date": tdata.from_date,
						"to_date": tdata.to_date,
						"user": tdata.user,
						"reason": tdata.reason
					})
				for tdata in doc.details:
					revise_dates.append({
						"action": tdata.action,
						"from_date": tdata.date,
						"to_date": tdata.rescheduled_date,
						"user": frappe.session.user,
						"reason": reason
					})
					tdata.date = tdata.rescheduled_date
				doc.delay = 0	
				doc.revised += 1
				doc.set("time_and_action_revised_dates", revise_dates)	
				doc.save()	