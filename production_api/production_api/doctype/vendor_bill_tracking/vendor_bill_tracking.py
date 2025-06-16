# Copyright (c) 2025, Aerele Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import frappe.utils
from six import string_types

class VendorBillTracking(Document):

	def before_insert(self):
		if self.new_supplier:
			self.create_new_supplier()
	
	def before_submit(self):
		if not self.amended_from:
			self.set_first_history()

	def create_new_supplier(self):
		# default_sup_grp = frappe.db.get_value("MRP Settings", "MRP Settings", "default_supplier_group")
		# if not default_sup_grp:
		# 	frappe.throw("Setup Default Supplier Group")
		sup = frappe.new_doc("Supplier")
		sup.supplier_name = self.new_supplier_name
		sup.save(ignore_permissions = True)
		self.supplier = sup.name

	def set_first_history(self):
		if not self.vendor_bill_tracking_history:
			self.append('vendor_bill_tracking_history', {
				'assigned_by' : frappe.session.user,
				'assigned_on' : frappe.utils.now_datetime(),
				'action' : 'Open'
			})
			self.set('form_status', 'Open')
	
	def close_vendor_bill(self, purchase_invoice, remarks = None):
		if self.form_status == 'Closed':
			frappe.throw("Vendor Bill Already Closed")
		self.append('vendor_bill_tracking_history', {
			"assigned_by" : frappe.session.user,
			'assigned_on' : frappe.utils.now_datetime(),
			"remarks" : remarks,
			"action" : 'Close'
		})
		self.set('form_status', 'Closed')
		self.set('purchase_invoice', purchase_invoice)
	
	def reopen_vendor_bill(self,remarks):
		self.append('vendor_bill_tracking_history', {
			"assigned_by" : frappe.session.user,
			'assigned_on' : frappe.utils.now_datetime(),
			"remarks" : remarks,
			"action" : 'Reopen'
		})
		self.set('form_status', 'Reopen')
		self.set('purchase_invoice', None)
	
	def assign_bill_to_user(self, user, remarks = None):
		self.append("vendor_bill_tracking_history", {
			"assigned_to" : user,
			'assigned_on' : frappe.utils.now_datetime(),
			"assigned_by" : frappe.session.user,
			"remarks" : remarks,
			"action" : 'Assign'
		})
		self.set('form_status', 'Assigned')

@frappe.whitelist()
def assign_vendor_bill(name, assigned_to, remarks = None):
	doc = frappe.get_doc("Vendor Bill Tracking", name)
	if doc.docstatus != 1 or doc.form_status not in ['Reopen', "Open", "Assigned"]:
		frappe.throw(f"Can't Assign Vendor Bill {doc.name}")
	doc.assign_bill_to_user(assigned_to, remarks)
	doc.save(ignore_permissions = True)

@frappe.whitelist()
def close_vendor_bill(name, purchase_invoice,remarks = None):
	doc = frappe.get_doc("Vendor Bill Tracking", name)
	doc.close_vendor_bill(purchase_invoice, remarks)
	doc.save(ignore_permissions = True)

@frappe.whitelist()
def reopen_vendor_bill(name, remarks=None):
	doc = frappe.get_doc('Vendor Bill Tracking', name)
	doc.reopen_vendor_bill(remarks)
	doc.save(ignore_permissions = True)

@frappe.whitelist()
def cancel_vendor_bill(name, cancel_reason):
	doc = frappe.get_doc("Vendor Bill Tracking", name)
	doc.cancel_reason = cancel_reason
	doc.flags.ignore_permissions = True
	doc.cancel()

@frappe.whitelist()
def get_bills_assigned_to_me():
    cur_user = frappe.session.user

    names = frappe.db.sql("""
        SELECT t1.name
        FROM `tabVendor Bill Tracking` t1
        JOIN `tabVendor Bill Tracking Assignment Detail` t2
            ON t1.name = t2.parent
        WHERE t1.docstatus = 1
          AND t1.form_status = 'Assigned'
          AND t2.idx = (
              SELECT MAX(idx)
              FROM `tabVendor Bill Tracking Assignment Detail`
              WHERE parent = t1.name
          )
          AND t2.assigned_to = %(cur_user)s
    """, {
        "cur_user": cur_user
    }, as_dict=True)

    return [i["name"] for i in names]

@frappe.whitelist()
def get_accounting_system_purchase_invoice(doc_name):
	doc = frappe.get_doc('Vendor Bill Tracking', doc_name)

	config = frappe.get_single('MRP Settings')
	if not config.erp_site_url:
		frappe.throw("Please Configure ERP properly")
	url = f"{config.erp_site_url}"

	return {
		"doctype" : 'Purchase Invoice',
		"bill_date" : doc.bill_date,
		"bill_no" : doc.bill_no,
		"supplier" : frappe.db.get_value("Supplier", doc.supplier, 'supplier_name'),
		"vendor_bill_tracking" : doc.name,
		"url" : url
	}

@frappe.whitelist()
def bulk_assign_bills(assign_to, selected_docs, remarks = None):
	if isinstance(selected_docs, string_types):
		selected_docs = frappe.json.loads(selected_docs)
	error = False
	for i in selected_docs:
		try:
			assign_vendor_bill(i['name'], assign_to, remarks)
		except Exception as e:
			error = True
	if error:
		frappe.db.rollback()