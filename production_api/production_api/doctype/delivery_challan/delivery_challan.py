# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document
from production_api.mrp_stock.utils import get_stock_balance
from itertools import zip_longest
from frappe.utils import flt, cstr

class DeliveryChallan(Document):
	def before_submit(self):
		for row in self.items:
			quantity = get_stock_balance(row.item_variant, self.from_location, with_valuation_rate=False)
			if quantity < row.qty:
				frappe.throw(f"Required quantity is {row.qty} but stock count is {quantity}")
		
		doc = frappe.get_doc("Work Order", self.work_order)
		for item, work_order_item in zip_longest(self.items, doc.deliverables):
			if item.ref_docname == work_order_item.name:
				work_order_item.pending_quantity = work_order_item.pending_quantity - item.get('qty')
			else:
				frappe.throw("some conflict")				
		doc.start_date = self.posting_date
		doc.save()
		doc.submit()

	def on_submit(self):
		item = [item.as_dict() for item in self.items if item.pending_quantity != 0]
		self.set('items',item)
		self.save()
		self.update_stock_ledger()

	def update_stock_ledger(self):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		sl_deliver_entries = []
		sl_receiver_entries = []
		for item in self.items:
			if flt(item.qty) > flt(0):
				is_available = get_last_entry(item.item_variant, item.qty, self.from_location)
				if is_available:
					sl_deliver_entries.append(self.get_sl_entries(item, {},"from"))
					sl_receiver_entries.append(self.get_sl_entries(item, {},"to"))
		if self.docstatus == 2:
			sl_deliver_entries.reverse()
		make_sl_entries(sl_deliver_entries)		
		make_sl_entries(sl_receiver_entries)	

	def get_sl_entries(self, d, args, param):
		location = None
		qty = 0.0
		if param == "from":
			location = self.from_location
			qty = flt(d.get("qty") * flt(-1))
		else:
			location = self.supplier
			qty = flt(d.get("qty"))	
		sl_dict = frappe._dict(
			{
				"item": d.get("item_variant", None),
				"warehouse": location,
				"lot": cstr(d.get("lot")).strip(),
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"voucher_detail_no": d.name,
				"qty": qty,
				"uom": d.uom,
				"rate": d.rate,
				"is_cancelled": 1 if self.docstatus == 2 else 0,
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
			}
		)
		sl_dict.update(args)
		return sl_dict				

	def onload(self):
		deliverable_item_details = fetch_item_details(self.get('items'))
		self.set_onload('deliverable_item_details', deliverable_item_details)

	def before_validate(self):
		if(self.get('deliverable_item_details')):
			deliverables = json.loads(self.deliverable_item_details)
			self.set('items',deliverables)
	
	def before_save(self):
		for row in self.items:
			quantity,rate = get_stock_balance(row.item_variant,self.from_location,with_valuation_rate = True)
			if flt(row.qty) < flt(0.0):
				frappe.throw("Only positive")
			if flt(row.qty) > flt(row.pending_quantity):
				frappe.throw("High amount of product in " + row.item_variant)	
			if flt(quantity) < flt(row.qty):
				frappe.throw(f"Quantity is {row.qty} but stock count is {quantity}")
			row.rate = rate	

def get_last_entry(item, qty, sender):
	query = frappe.db.sql(
		"""
		SELECT qty_after_transaction
		FROM `tabStock Ledger Entry` 
		WHERE item = %(item_name)s 
		AND warehouse = %(supplier)s 
		ORDER BY posting_date DESC, posting_time DESC
		LIMIT 1
		""",
		{
			"item_name": item,
			"supplier": sender
		},
		as_dict=1
	)
	ledger_qty = query[0].qty_after_transaction
	if ledger_qty >= qty:
		return True
	frappe.throw(f"There is no enough quantity for {item}")

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
	result = {
		"item" : item,
		"supplier":doc.supplier,
		"supplier_address": doc.supplier_address,
	}	
	return result

