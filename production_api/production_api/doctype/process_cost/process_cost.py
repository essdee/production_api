# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import utils
from frappe.model.document import Document
from production_api.utils import update_if_string_instance

class ProcessCost(Document):
	def before_validate(self):
		check = True
		if len(self.process_cost_values) == 0:
			check = False
		for row in self.process_cost_values:
			if row.price > 0:
				check = False
				break
		if check:
			frappe.throw("Update the Price")

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

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_attributes(doctype, txt, searchfield, start, page_len, filters):
	if (doctype != 'Item Attribute' or filters['item'] == None):
		return []
	
	item_name = filters['item']
	lot = filters['lot']
	process_name = filters['process']

	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	item_attributes = []
	if ipd_doc.cutting_process == process_name:
		item_attributes = [[ipd_doc.stiching_attribute]]
	elif ipd_doc.stiching_process == process_name:
		item_attributes = [[ipd_doc.packing_attribute], [ipd_doc.primary_item_attribute]]
	elif ipd_doc.packing_process == process_name:
		item_attributes = [[ipd_doc.primary_item_attribute]]
	else:
		is_group = frappe.get_value("Process", process_name, "is_group")
		if not is_group:
			for row in ipd_doc.ipd_processes:
				if row.process_name != process_name:
					continue
				if row.stage == ipd_doc.stiching_in_stage:
					item_attributes = [[ipd_doc.stiching_attribute]]
				elif row.stage == ipd_doc.stiching_out_stage:
					item_attributes = [[ipd_doc.packing_attribute], [ipd_doc.primary_item_attribute]]
				else:
					item_attributes = [[ipd_doc.primary_item_attribute]]
		else:	
			item = frappe.get_doc("Item", item_name)
			attributes = [attribute.attribute for attribute in item.attributes]
			item_attributes = [[value] for value in attributes if txt.lower() in value.lower()]
	return item_attributes		
		
@frappe.whitelist()
def get_pc_attribute_values(lot, attribute, process_name):
	ipd = frappe.get_value("Lot", lot, "production_detail")
	cutting, emblishment = frappe.get_value("Item Production Detail", ipd, ["cutting_process", "emblishment_details_json"])
	mapping = frappe.get_list(
		'Item Item Attribute',
		parent_doctype = 'Item Production Detail',
		filters={
			"parent": ipd, 
			"attribute": attribute
		},
		fields = ['attribute', 'mapping'],
	)
	items = []
	if mapping:
		if frappe.get_value("Item Production Detail", ipd, "stiching_attribute") == attribute and process_name != cutting:
			emblishment = update_if_string_instance(emblishment)
			for process in emblishment:
				if process != process_name:
					continue
				for panel in emblishment[process]:
					items.append({
						"price": 0,
						"min_order_qty": 0,
						"attribute_value": panel
					})	
		else:	
			doc = frappe.get_doc("Item Item Attribute Mapping", mapping[0]['mapping'])
			for val in doc.values:
				items.append({
					"price": 0,
					"min_order_qty": 0,
					"attribute_value": val.attribute_value
				})

	return items

@frappe.whitelist()
def get_item_attribute_details(item, attribute, attribute_value, lot=None):
	ipd = frappe.get_value("Lot", lot, "production_detail") if lot else None
	price = 0
	min_order_qty = 0

	mapping = frappe.get_value(
		"Item Item Attribute",
		parent_doctype="Item Production Detail",
		filters={"parent": ipd, "attribute": attribute},
		field="mapping"
	)

	if mapping:
		mapping_doc = frappe.get_doc("Item Item Attribute Mapping", mapping)
		for val in mapping_doc.values:
			if val.attribute_value == attribute_value:
				price = val.price
				min_order_qty = val.min_order_qty
				break

	return {"price": price, "min_order_qty": min_order_qty}
