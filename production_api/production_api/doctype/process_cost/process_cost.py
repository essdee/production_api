# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import utils
from frappe.model.document import Document

class ProcessCost(Document):
	def before_validate(self):
		if not self.supplier and self.is_rework:
			frappe.throw("Please mention supplier if it is Rework Process")

	def before_submit(self):
		self.approved_by = frappe.session.user
		filters = [
			["item", "=", self.item],
		    ["process_name","=", self.process_name],
			["docstatus", "=", 1],
		    ["name","!=",self.name],
			['workflow_state',"=","Approved"],
			['is_expired','=',0],
			['is_rework','=', self.is_rework],
			['lot', '=', self.lot]
		]
		if self.supplier != None:
			filters.append(["supplier", "=", self.supplier])
		process_cost_list = frappe.db.get_list( 'Process Cost', filters=filters, pluck= "name", order_by='from_date asc')

		for process_cost in process_cost_list:
			doc = frappe.get_doc("Process Cost", process_cost)
			from_date = utils.get_datetime(self.from_date).date()
			to_date = utils.get_datetime(self.to_date).date()
			if doc.from_date == from_date:
				frappe.throw(f"An Process cost was found with the same `From Date`.")
			elif doc.from_date > from_date:
				if not to_date or to_date >= doc.from_date:
					frappe.throw(f"An Updated Process cost list for the same Item and Supplier exists from {frappe.utils.format_date(doc.from_date)}. Please set `To Date` less than that date or cancel the next Price")
			else:
				to_dates = utils.add_days(from_date, -1)
				doc.to_date = to_dates
				doc.save()	
