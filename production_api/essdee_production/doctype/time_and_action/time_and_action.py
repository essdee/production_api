# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, getdate
from production_api.essdee_production.doctype.holiday_list.holiday_list import get_events_len,get_next_date

class TimeandAction(Document):
	def before_validate(self):
		if not self.is_new():
			idx = actual_date = d = index2 = actual_start_date = None
			version = frappe.get_value("Lot", self.lot, "version")
			child_val = {}
			for item in self.details:
				if item.actual_date and not item.completed:
					item.completed = 1
					idx = item.idx
					child_val.setdefault(item.name, {})
					d = date_diff(item.date,item.actual_date)
					date1 = item.date
					date2 = item.actual_date
					if getdate(date1) > getdate(date2):
						date1 = item.actual_date
						date2 = item.date
					
					events_len = get_events_len(date1,date2)
					d = d + events_len if d < 0 else d - events_len
					
					item.date_diff = d
					child_val[item.name]['date_diff'] = d

					diff = date_diff(item.rescheduled_date,item.actual_date)
					date1 = item.rescheduled_date
					date2 = item.actual_date
					if getdate(item.rescheduled_date) > getdate(item.actual_date):
						date1 = item.actual_date
						date2 = item.rescheduled_date

					events2_len = get_events_len(date1,date2)
					diff = diff + events2_len if diff < 0 else diff - events2_len

					item.performance = get_performance(diff)	
					child_val[item.name]['performance'] = item.performance				
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
						if not child_val.get(item.name):
							child_val[item.name] = {}
						child_val[item.name]['rescheduled_date'] = actual_date	

					self.end_date = item.rescheduled_date
			elif version == 'V2':
				for item in self.details:
					if item.completed == 0:
						if not actual_date:
							actual_date = self.start_date
						actual_date = get_next_date(actual_date,item.lead_time)
						item.rescheduled_date = actual_date
						if not child_val.get(item.name):
							child_val[item.name] = {}
						child_val[item.name]['rescheduled_date'] = actual_date	
						self.end_date = item.rescheduled_date
					else:
						actual_date = item.actual_date 	
			
			if child_val:
				for row in self.time_and_action_work_station_details:
					if child_val.get(row.parent_link_value):
						if child_val[row.parent_link_value].get("date_diff"):
							row.date_diff = child_val[row.parent_link_value]['date_diff']
						if child_val[row.parent_link_value].get("performance"):
							row.performance = child_val[row.parent_link_value]['performance']	
						if child_val[row.parent_link_value].get("rescheduled_date"):
							row.rescheduled_date = child_val[row.parent_link_value]['rescheduled_date']			
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
