# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff
from frappe.model.document import Document
from production_api.utils import update_if_string_instance

class ActionMasterTemplate(Document):
	def autoname(self):
		self.naming_series = "Master Template-" 

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
		data = get_t_and_a_preview_data(frappe.utils.nowdate(), [{'colour': 'colour', 'master': self.name}], is_template=True)		
		dispatch_date = data['colour'][len(data['colour']) - 1]['rescheduled_date']
		lead_time = date_diff(dispatch_date, frappe.utils.nowdate())
		self.lead_time = lead_time

@frappe.whitelist()
def get_work_station(action):
	name = frappe.get_value("Work Station", filters={"action":action,"default":1},pluck = "name")
	return name