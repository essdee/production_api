# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt
import json
from six import string_types
import urllib.parse

import frappe
from frappe.model.document import Document
from frappe.utils.data import money_in_words

from production_api.production_api.doctype.mrp_settings.mrp_settings import get_purchase_invoice_series, post_erp_request

class PurchaseInvoice(Document):
	def validate(self):
		self.validate_grn()
		self.calculate_total()

	def validate_grn(self):
		# if not len(self.grn):
		# 	frappe.throw("Please set atleast one GRN")
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
			self.erp_inv_docstatus = 2
			res = post_erp_request("/api/method/essdee.essdee.utils.mrp.purchase_invoice.cancel", {"name": self.erp_inv_name})
			if res.status_code == 200:
				pass
			else:
				data = res.json()
				error = frappe.log_error("Purchase Inv Cancel Error", json.dumps(data), self.doctype, self.name)
				frappe.throw(data.get('exception') or f"Unknown Error - {frappe.get_desk_link(error.doctype, error.name)}")
	
	def before_submit(self):
		if not len(self.grn) or not len(self.items):
			frappe.throw("Please set at least 1 grn and item row.")
		data = self.as_dict(convert_dates_to_str=True)
		mapped_series = get_purchase_invoice_series(data['naming_series'])
		if mapped_series:
			data['mapped_series'] = mapped_series
		p = "/api/method/essdee.essdee.utils.mrp.purchase_invoice.create"
		res = post_erp_request(p, {'data': data})
		if res.status_code == 200:
			data = res.json()['message']
			self.update({
				'erp_inv_name': data['name'],
				'erp_inv_docstatus': data['docstatus'],
				'final_amount': data['amount'],
				'due_date': data['due_date']
			})
		else:
			data = res.json()
			error = frappe.log_error("Purchase Inv Submit Error", json.dumps(data), self.doctype, self.name)
			frappe.throw(res.json().get('exception') or f"Unknown Error - {frappe.get_desk_link(error.doctype, error.name)}")

@frappe.whitelist()
def submit_erp_invoice(name):
	inv = frappe.get_doc("Purchase Invoice", name)
	if inv.docstatus == 0:
		frappe.throw("Document not submitted")
	elif inv.docstatus == 2:
		frappe.throw("Document already cancelled")
	
	if inv.erp_inv_docstatus != 0:
		frappe.throw(f"ERP Invoice {inv.erp_inv_name} already submitted")
	
	res = post_erp_request("/api/method/essdee.essdee.utils.mrp.purchase_invoice.submit", {"name": inv.erp_inv_name})
	if res.status_code == 200:
		data = res.json()['message']
		inv.update({
			'erp_inv_name': data['name'],
			'erp_inv_docstatus': data['docstatus'],
			'final_amount': data['amount'],
			'due_date': data['due_date']
		})
		inv.save()
	else:
		data = res.json()
		error = frappe.log_error("Purchase Inv Submit Error", json.dumps(data), inv.doctype, inv.name)
		frappe.throw(res.json().get('exception') or f"Unknown Error - {frappe.get_desk_link(error.doctype, error.name)}")


def get_item_variant_item_group(item_variant):
	item_group = frappe.db.sql("""SELECT t2.item_group, t1.item FROM `tabItem Variant` t1
			   		JOIN `tabItem` t2 on t2.name = t1.item where t1.name=%(item_variant)s
			   """, {
				   "item_variant" : item_variant
			   }, as_dict=True)
	if not item_group:
		return None, None
	return item_group[0]['item_group'], item_group[0]['item']
	

@frappe.whitelist()
def fetch_grn_details(grns):
	if isinstance(grns, string_types):
		grns = json.loads(grns)
	grns = list(set(grns))
	items = {}
	exception_item_set = set()
	for grn in grns:
		grn_doc = frappe.get_doc("Goods Received Note", grn)
		for grn_item in grn_doc.items:
			rate = grn_item.rate
			discount_percentage = frappe.get_value(grn_item.ref_doctype, grn_item.ref_docname, "discount_percentage")
			if discount_percentage:
				rate = rate - (rate * (discount_percentage / 100))
			key = (grn_item.item_variant, grn_item.uom, rate, grn_item.tax)
			item_group, item = get_item_variant_item_group(grn_item.item_variant)
			if not item_group:
				exception_item_set.add(item)
			items.setdefault(key, {
				"item": grn_item.item_variant,
				"item_group" : item_group,
				"qty": 0,
				"uom": grn_item.uom,
				"rate": rate,
				"amount": 0,
				"tax": grn_item.tax,
			})
			items[key]["qty"] += grn_item.quantity
			items[key]["amount"] += (grn_item.quantity * rate)
	if exception_item_set and len(exception_item_set) > 0:
		exception = "The Below Item Does Not Have Item Group<br>"
		exception += "<br>".join([ f"<a href='/app/item/{_}' target='_blank'>{_}</a>" for _ in list(exception_item_set)])
		frappe.throw(exception)

	return list(items.values())

@frappe.whitelist()
def get_erp_inv_link(name):
	d = frappe.get_doc("Purchase Invoice", name)
	if d.docstatus == 1 and d.erp_inv_name:
		erp_url = frappe.get_single("MRP Settings").erp_site_url
		return f"{erp_url}/app/purchase-invoice/{urllib.parse.quote(d.erp_inv_name, safe='')}"
	else:
		frappe.throw("Document not submitted")
