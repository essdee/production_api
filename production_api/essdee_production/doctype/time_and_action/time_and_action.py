# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days,date_diff

class TimeandAction(Document):
	def validate(self):
		if self.is_new():
			master_doc = frappe.get_doc("Action Master",self.master)
			d = self.start_date
			x = 1
			for item in master_doc.details:
				d = add_days(d,item.lead_time)
				self.append("details",{
					"action":item.action,
					"lead_time":item.lead_time,
					"department":item.department,
					"date":d,
					"rescheduled_date":d,
					"index2":x
				})
				x = x + 1

	def before_validate(self):
		if not self.is_new():
			idx = None
			actual_date = None
			d = None
			for item in self.details:
				if item.actual_date and not item.completed:
					item.completed = 1
					idx = item.idx
					actual_date = item.actual_date
					d = date_diff(item.date,item.actual_date)
					item.date_diff = d
					diff = date_diff(item.rescheduled_date,item.actual_date)
					item.performance = get_performance(diff)
					break

			action = None
			if idx:
				for item in self.details:
					item.index2 -= 1
					if item.idx == idx + 1:
						action = item.action

					if item.idx > idx:
						actual_date = add_days(actual_date,item.lead_time)
						item.rescheduled_date = actual_date
			
			self.action = action
			if d:
				self.delay = d	

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

