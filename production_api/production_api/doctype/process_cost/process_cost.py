# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_attribute_details
from frappe.utils import nowdate
from frappe import utils


class ProcessCost(Document):
	def before_submit(self):
		filters = [
			["item", "=", self.item],
		    ["process_name","=", self.process_name],
			["docstatus", "=", 1],
		    ["name","!=",self.name],
			['is_expired','=',0],
		]
		if self.supplier != None:
			filters.append(["supplier", "=", self.supplier])
		process_cost_list = frappe.db.get_list(
			'Process Cost',
			filters=filters,
			pluck= "name",
			order_by='from_date asc',
		)
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
				
# Use this code to automate the before-submit function process. 

# doc = frappe.get_list("Process Cost",filters={
# 			'item':self.item,
# 			'process_name':self.process_name,
# 			'docstatus':1,
# 			'is_expired': 0,
# 			'name':['!=',self.name]
# 			},
# 		pluck='name')

# 		if doc:
# 			check_and_update_docs(doc,self.from_date, self.to_date)
# def check_and_update_docs(docnames, date1, date2 = None):
# 	for docname in docnames:
# 		doc = frappe.get_doc('Process Cost', docname)
# 		if doc.from_date == date1:
# 			frappe.throw(f"An Process cost was found with the same `From Date`.")
# 		if not doc.to_date:
# 			if doc.from_date < date1:
# 				doc.to_date = utils.add_days(date1,-1)
# 			else:
# 				doc.is_expired = True
# 		else:
# 			if not date2:
# 				doc.is_expired = True
# 			else:	
# 				if doc.to_date < date2 and doc.from_date > date1:
# 					doc.is_expired = True
# 				elif doc.to_date < date2: 
# 					doc.to_date = utils.add_days(date1,-1)
# 				else:
# 					doc.from_date = utils.add_days(date2, 1)
# 		doc.save()

