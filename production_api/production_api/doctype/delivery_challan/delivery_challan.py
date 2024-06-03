# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document
from production_api.mrp_stock.utils import get_stock_balance
from itertools import zip_longest


class DeliveryChallan(Document):
	def before_submit(self):
		for row in self.items:
			quantity = get_stock_balance(row.item_variant, self.supplier, with_valuation_rate=False)
			if quantity <= row.qty:
				frappe.throw(f"Required quantity is {row.qty} but stock count is {quantity}")
		
		doc = frappe.get_doc("Work Order", self.work_order)
		for item, work_order_item in zip_longest(self.items, doc.deliverables):
			if item.ref_docname == work_order_item.name:
				work_order_item.pending_quantity = work_order_item.pending_quantity - item.get('qty')
			else:
				frappe.throw("some conflict")		
		doc.save()
		doc.submit()
	
	def on_submit(self):
		item = [item.as_dict() for item in self.items if item.pending_quantity != 0]
		self.set('items',item)
		self.save()

	def onload(self):
		deliverable_item_details = fetch_item_details(self.get('items'))
		self.set_onload('deliverable_item_details', deliverable_item_details)

	def before_validate(self):
		if(self.get('deliverable_item_details')):
			deliverables = json.loads(self.deliverable_item_details)
			self.set('items',deliverables)
	
	def before_save(self):
		for row in self.items:
			quantity,rate = get_stock_balance(row.item_variant,self.supplier,with_valuation_rate = True)
			if row.qty < 0:
				frappe.throw("Only positive")
			if row.qty > row.pending_quantity:
				frappe.throw("High amount of product in " + row.item_variant)	
			if quantity <= row.qty:
				frappe.throw(f"Quantity is {row.qty} but stock count is {quantity}")
			row.rate = rate	

def fetch_item_details(deliverables):
	item = []
	for row in deliverables:
		x = {
			"item_variant" : row.item_variant,
			"lot" : row.lot,
			"qty": row.qty,
			"rate": row.rate,
			"uom": row.uom,
			"secondary_qty" : row.secondary_qty,
			"secondary_uom": row.secondary_uom,
			"comments": row.comments,
			"table_index" : row.table_index,
			"row_index" : row.row_index,
			"additional_parameters": row.additional_parameters,
			"pending_quantity": row.pending_quantity,
			"ref_doctype":row.ref_doctype,
			"ref_docname":row.ref_docname,
		}
		item.append(x)
	return item
			
@frappe.whitelist()
def get_deliverables(work_order):
	doc = frappe.get_doc("Work Order",work_order)
	item = []
	for row in doc.deliverables:
		x = {
			"item_variant" : row.item_variant,
			"lot" : row.lot,
			"qty": row.pending_quantity,
			"rate": row.rate,
			"uom": row.uom,
			"secondary_qty" : row.secondary_qty,
			"secondary_uom": row.secondary_uom,
			"comments": row.comments,
			"table_index" : row.table_index,
			"row_index" : row.row_index,
			"additional_parameters": row.additional_parameters,
			"pending_quantity": row.pending_quantity,
			"ref_doctype":row.doctype,
			"ref_docname":row.name,
		}
		item.append(x)
	return item

