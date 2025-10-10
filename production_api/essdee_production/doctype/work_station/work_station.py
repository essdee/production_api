# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from itertools import zip_longest
from frappe.model.document import Document
from production_api.utils import update_if_string_instance


class WorkStation(Document):
	def before_validate(self):
		if self.default:
			conditions = "action = %(action)s AND `default` = 1"
			con = {
				"action": self.action
			}
			if not self.is_new():
				conditions += " AND name != %(docname)s"
				con["docname"] = self.name
				
			ws_list = frappe.db.sql(
				f"""
					Select name from `tabWork Station` where {conditions} order by creation desc LIMIT 1
				""", con, as_dict = True
			)
			if ws_list:
				frappe.throw(f"Work Station {ws_list[0]['name']} exist for Action {self.action}")

@frappe.whitelist()
def get_work_stations(items, lot):
	work_station = {}
	items = update_if_string_instance(items)
	for item in items:
		if item['action'] != "Completed":
			doc = frappe.get_doc("Time and Action",item['parent'])
			work_station[item['colour']] = []

			for child in doc.details:
				child_data = child.as_dict()
				child_data['master'] = doc.master
				work_station[item['colour']].append(child_data)
	return work_station	

@frappe.whitelist()
def update_t_and_a_ws(datas):
	datas = update_if_string_instance(datas)
	for d in datas:
		doc = frappe.get_doc("Time and Action",datas[d][0]['parent'])
		child_table = []
		x = {}
		for data, row in zip_longest(datas[d], doc.details):
			d = {
				"action": data['action'],
				"department":data['department'],
				"lead_time":data['lead_time'],
				"date":data['date'],
				"rescheduled_date":data['rescheduled_date'],
				"actual_date":data['actual_date'],
				"work_station":data['work_station'],
				"date_diff":data['date_diff'],
				"reason":data['reason'],
				"performance":data['performance'],
				"completed":data['completed'],
				"index2":data['index2'],
				"planned_start_date":data['planned_start_date'],
				"rescheduled_start_date":data['rescheduled_start_date'],
				"actual_start_date":data['actual_start_date'],
			}
			child_table.append(d)
		doc.set("details",child_table)
		doc.save()