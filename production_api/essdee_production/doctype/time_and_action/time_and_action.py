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
			for item in master_doc.details:
				d = add_days(d,item.lead_time)
				self.append("details",{
					"action":item.action,
					"lead_time":item.lead_time,
					"department":item.department,
					"date":d,
					"rescheduled_date":d,
				})

	def before_validate(self):
		if not self.is_new():
			idx = None
			actual_date = None
			for item in self.details:
				if item.actual_date and not item.completed:
					item.completed = 1
					idx = item.idx
					actual_date = item.actual_date
					item.date_diff = date_diff(item.rescheduled_date,item.actual_date)
					break

			if idx:
				for item in self.details:
					if item.idx > idx:
						actual_date = add_days(actual_date,item.lead_time)
						item.rescheduled_date = actual_date


