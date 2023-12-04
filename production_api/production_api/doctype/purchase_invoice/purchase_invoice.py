# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt
import json
from six import string_types
import urllib.parse

import frappe
from frappe.model.document import Document
from frappe.utils.data import money_in_words

from production_api.production_api.doctype.mrp_settings.mrp_settings import post_erp_request

class PurchaseInvoice(Document):
	def validate(self):
		self.validate_grn()
		self.calculate_total()

	def validate_grn(self):
		if not len(self.grn):
			frappe.throw("Please set atleast one GRN")
		grns = [g.grn for g in self.grn]
		old_grns = []
		if not self.is_new():
			old = frappe.get_doc("Purchase Invoice", self.name)
			old_grns = [g.grn for g in old.grn]
			removed = [g for g in old_grns if g not in grns]
			added = [g for g in grns if g not in old_grns]
			for g in removed:
				grn = frappe.get_doc("Goods Received Note", g)
				grn.purchase_invoice_name = None
				grn.save(ignore_permissions=True)
			for g in added:
				grn = frappe.get_doc("Goods Received Note", g)
				grn.purchase_invoice_name = self.name
				grn.save(ignore_permissions=True)
	
	def calculate_total(self):
		total_amount = 0
		total_tax = 0
		total_discount = 0
		grand_total = 0
		for item in self.items:
			# Item Total
			item_total = item.rate * item.qty
			total_amount += item_total
			# Item Tax after discount
			tax = (item_total * (float(item.tax or 0) / 100))
			total_tax += tax
			# Item Total after tax
			total = item_total + tax
			grand_total += total
		self.set('total', total_amount)
		self.set('total_tax', total_tax)
		self.set('grand_total', grand_total)
		self.set('in_words', money_in_words(grand_total))
	
	def after_insert(self):
		grns = [g.grn for g in self.grn]
		for g in grns:
			grn = frappe.get_doc("Goods Received Note", g)
			grn.purchase_invoice_name = self.name
			grn.save(ignore_permissions=True)
	
	def before_cancel(self):
		grns = [g.grn for g in self.grn]
		for g in grns:
			grn = frappe.get_doc("Goods Received Note", g)
			grn.purchase_invoice_name = None
			grn.save(ignore_permissions=True)
		if not self.cancel_without_cancelling_erp_inv:
			res = post_erp_request("/api/method/essdee.essdee.utils.mrp.purchase_invoice.cancel", {"name": self.erp_inv_name})
			if res.status_code == 200:
				pass
			else:
				frappe.throw(res.json().get('exception') or f"Unknown Error - {res.status_code}")
	
	def before_submit(self):
		data = self.as_dict(convert_dates_to_str=True)
		p = "/api/method/essdee.essdee.utils.mrp.purchase_invoice.create"
		res = post_erp_request(p, {'data': data})
		if res.status_code == 200:
			data = res.json()['message']
			self.update({
				'erp_inv_name': data['name'],
				'final_amount': data['amount'],
				'due_date': data['due_date']
			})
		else:
			frappe.throw(res.json().get('exception') or f"Unknown Error - {res.status_code}")


@frappe.whitelist()
def fetch_grn_details(grns):
	if isinstance(grns, string_types):
		grns = json.loads(grns)
	grns = list(set(grns))
	print(grns)
	items = {}

	for grn in grns:
		grn_doc = frappe.get_doc("Goods Received Note", grn)
		for grn_item in grn_doc.items:
			key = (grn_item.item_variant, grn_item.uom, grn_item.rate, grn_item.tax)
			items.setdefault(key, {
				"item": grn_item.item_variant,
				"qty": 0,
				"uom": grn_item.uom,
				"rate": grn_item.rate,
				"amount": 0,
				"tax": grn_item.tax,
			})
			items[key]["qty"] += grn_item.quantity
			items[key]["amount"] += (grn_item.quantity * grn_item.rate)
	
	return list(items.values())

@frappe.whitelist()
def get_erp_inv_link(name):
	d = frappe.get_doc("Purchase Invoice", name)
	if d.docstatus == 1 and d.erp_inv_name:
		erp_url = frappe.get_single("MRP Settings").erp_site_url
		return f"{erp_url}/app/purchase-invoice/{urllib.parse.quote(d.erp_inv_name, safe='')}"
	else:
		frappe.throw("Document not submitted")
