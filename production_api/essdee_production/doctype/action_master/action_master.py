# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff
from frappe.model.document import Document
from production_api.utils import update_if_string_instance

class ActionMaster(Document):
	def autoname(self):
		self.naming_series = "Master-" 

	def onload(self):
		d = {}
		previous_action = []
		for row in self.details:
			previous_action.append({
				"option": row.action,
				"id": row.action
			})
			d[row.action] = {
				"action": row.action,
				"lead_time": row.lead_time,
				"department": row.department,
				"dependent_action": [],
				"check_value": row.merge_action,
				"one_colour_process": row.one_colour_process,
			}

		for row in self.action_master_dependent_details:
			d[row.action]['dependent_action'].append(row.dependent_action)

		list_data = [d[key] for key in d]
		self.set_onload("action_data", {
			"data": list_data,
			"previous": previous_action,
		})


	def before_validate(self):
		self.quantity = str(self.min_qty) + " - " + str(self.max_qty)
		if self.get('action_details'):
			action_details = update_if_string_instance(self.action_details)
			details = []
			dependent_details = []
			for row in action_details:
				details.append({
					"action": row['action'],
					"lead_time": row['lead_time'],
					"department": row['department'],
					"target": 0,
					"merge_action": row['check_value'],
					"one_colour_process": row['one_colour_process']
				})
				if len(row['dependent_action']) > 0:
					for act in row['dependent_action']:
						dependent_details.append({
							"action": row['action'],
							"dependent_action": act,
						})

			self.set("details", details)
			self.set("action_master_dependent_details", dependent_details)			

	def before_save(self):
		from production_api.essdee_production.doctype.time_and_action.time_and_action import get_t_and_a_preview_data
		data = get_t_and_a_preview_data(frappe.utils.nowdate(), [{'colour': 'colour', 'master': self.name}])		
		dispatch_date = data['colour'][len(data['colour']) - 1]['rescheduled_date']
		lead_time = date_diff(dispatch_date, frappe.utils.nowdate())
		self.lead_time = lead_time

@frappe.whitelist()
def get_action_master_details(master_list):
	master_list = update_if_string_instance(master_list)
	work_station = {}
	for item in master_list:
		work_station[item['colour']] = {
			"details": [],
			"dependent_details": []
		}
		master_doc = frappe.get_doc("Action Master",item['master'])
		for action in master_doc.details:
			action_data = action.as_dict()
			capacity_planning = frappe.get_value("Action",action_data['action'],"capacity_planning")
			if capacity_planning:
				name_list = frappe.get_list("Work Station", filters={"action":action_data["action"],"default":True},pluck = "name")
				if not name_list:
					frappe.throw(f"There is no Work Station for Action {action_data['action']}")

				action_data['work_station'] = frappe.get_value("Work Station",name_list[0],"name")
			action_data['master'] = item['master']	
			work_station[item['colour']]['details'].append(action_data)

		for row in master_doc.action_master_dependent_details:
			work_station[item['colour']]['dependent_details'].append(row.as_dict())
			
	return work_station

@frappe.whitelist()
def get_work_station(action):
	name = frappe.get_value("Work Station", filters={"action":action,"default":1},pluck = "name")
	return name

@frappe.whitelist()
def create_master_template(doc_name):
	master_doc = frappe.get_doc("Action Master", doc_name)
	new_doc = frappe.new_doc("Action Master Template")
	d = {
		"fabric": master_doc.fabric,
		"min_qty": master_doc.min_qty,
		"max_qty": master_doc.max_qty,
		"product_type": master_doc.product_type,
		"fabric": master_doc.fabric,
		"emblishment": master_doc.emblishment,
		"description": master_doc.description,
		"lead_time": master_doc.lead_time
	}
	new_doc.update(d)
	new_doc.set("details", master_doc.details)
	new_doc.set("action_master_dependent_details", master_doc.action_master_dependent_details)
	new_doc.save()

@frappe.whitelist()
def get_template_details(template):
	d = {}
	doc = frappe.get_doc("Action Master Template", template)
	for row in doc.details:
		d[row.action] = {
			"action": row.action,
			"lead_time": row.lead_time,
			"department": row.department,
			"dependent_action": [],
			"check_value": row.merge_action,
			"one_colour_process": row.one_colour_process,
		}

	for row in doc.action_master_dependent_details:
		d[row.action]['dependent_action'].append(row.dependent_action)	
	list_data = [d[key] for key in d]
	
	return list_data