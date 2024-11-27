# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, getdate
from production_api.essdee_production.doctype.holiday_list.holiday_list import get_events,get_next_date

class TimeandAction(Document):
	def before_validate(self):
		if not self.is_new():
			idx = actual_date = d = index2 = actual_start_date = None
			for item in self.details:
				if item.actual_date and not item.completed:
					item.completed = 1
					idx = item.idx
					
					d = date_diff(item.date,item.actual_date)
					date1 = item.date
					date2 = item.actual_date
					if getdate(date1) > getdate(date2):
						date1 = item.actual_date
						date2 = item.date
					
					events = get_events(date1,date2)
					events_len = len(events)
					d = d + events_len if d < 0 else d - events_len
					
					item.date_diff = d

					diff = date_diff(item.rescheduled_date,item.actual_date)
					date1 = item.rescheduled_date
					date2 = item.actual_date
					if getdate(item.rescheduled_date) > getdate(item.actual_date):
						date1 = item.actual_date
						date2 = item.rescheduled_date

					events2 = get_events(date1, date2)
					events2_len = len(events2)
					diff = diff + events2_len if diff < 0 else diff - events2_len

					item.performance = get_performance(diff)					
					actual_date = item.actual_date
					index2 = item.index2
					actual_start_date = item.actual_date
					if item.idx == 1:
						item.actual_start_date = self.start_date
					break

			action = None
			if idx:
				for item in self.details:
					if index2 and item.index2 == index2 + 1:
						item.actual_start_date = actual_start_date

					item.index2 -= 1
					if item.idx == idx + 1:
						action = item.action
						
					if item.idx > idx:
						actual_date = get_next_date(actual_date,item.lead_time)
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
