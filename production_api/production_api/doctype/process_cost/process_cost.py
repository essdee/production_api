# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_attribute_details
from frappe.utils import nowdate, cint
from frappe import utils, _


class ProcessCost(Document):
	def before_submit(self):
		filters = [
			["item", "=", self.item],
		    ["process_name","=", self.process_name],
			["docstatus", "=", 1],
		    ["name","!=",self.name],
			["workflow_state", "=", "Approved"],
		]
		if self.supplier != None:
			filters.append(["supplier", "=", self.supplier])
		else:
			filters.append(["supplier", "is", "not set"])

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
			if doc.from_date == from_date and doc.dependent_attribute_values == self.dependent_attribute_values and doc.supplier == self.supplier:
				frappe.throw(f"An Process cost was found with the same `From Date`.")
			elif doc.from_date > from_date and doc.dependent_attribute_values == self.dependent_attribute_values  and doc.supplier == self.supplier:
				if not to_date or to_date >= doc.from_date:
					frappe.throw(f"An Updated Process cost list for the same Item and Supplier exists from {frappe.utils.format_date(doc.from_date)}. Please set `To Date` less than that date or cancel the next Price")
			else:
				to_dates = utils.add_days(from_date, -1)
				doc.to_date = to_dates
				doc.save()	
		
		self.set('approved_by', frappe.get_user().doc.name)

	def validate(self):
		if len(self.process_cost_values) == 0:
			frappe.throw("There are no entries in the process cost values")
				
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





def update_expired_process_cost():
	filters = [
		["to_date", "<", utils.nowdate()],
		["to_date", "is", "set"],
		["docstatus", "=", 1]
	]
	process_cost_list = frappe.db.get_all(
		'Process Cost',
		filters=filters,
		pluck="name"
	)
	workflow_exists = frappe.db.exists("Workflow", {"document_type": "Process Cost", "is_active": 1})
	for process_cost in process_cost_list:
		doc = frappe.get_doc("Process Cost", process_cost)
		if workflow_exists:
			cancel_process_cost(doc)
		else:
			doc.cancel()
		doc.add_comment("Info", "Cancelled Automatically due to expiry")


def cancel_process_cost(doc):
	workflow_name = frappe.db.get_value("Workflow", {"document_type": "Process Cost", "is_active": 1}, "name")
	if workflow_name:
		workflow = frappe.get_doc("Workflow", workflow_name)
		cancel_states = []
		for state in workflow.states:
			if cint(state.doc_status) == 2:
				cancel_states.append(state.state)
		if "Expired" in cancel_states:
			cancel_states = ["Expired"]

		transition = get_cancel_transitions(doc, workflow, cancel_states)
		if transition:
			doc.set(workflow.workflow_state_field, transition.next_state)
			next_state = [d for d in workflow.states if d.state == transition.next_state][0]
			# update any additional field
			if next_state.update_field:
				doc.set(next_state.update_field, next_state.update_value)
			doc.cancel()
			doc.add_comment("Workflow", _(next_state.state))
	else:
		doc.cancel()

def get_cancel_transitions(doc, workflow, cancel_states) -> dict:
	"""Return list of possible transitions for the given doc"""
	from frappe.model.document import Document

	if not isinstance(doc, Document):
		doc = frappe.get_doc(frappe.parse_json(doc))
		doc.load_from_db()

	if doc.is_new():
		return []

	current_state = doc.get(workflow.workflow_state_field)

	if not current_state:	
		frappe.throw("Workflow State not set")

	transitions = []

	for transition in workflow.transitions:
		if transition.state == current_state and transition.next_state in cancel_states:
			transitions.append(transition.as_dict())

	if len(transitions) > 0:
		return transitions[0]
	return None
