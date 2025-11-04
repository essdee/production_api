# Copyright (c) 2025, Aerele Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import frappe.utils
from six import string_types
from production_api.production_api.doctype.department.department import get_user_departments

class VendorBillTracking(Document):
	
	def before_submit(self):
		if not self.amended_from:
			self.set_first_history()

	def before_cancel(self):
		self.set_cancelled_log()

	def before_insert(self):
		self.check_for_unique_condition()
		if self.amended_from:
			self.set_amended_log()

	def check_for_unique_condition(self):
		flag = frappe.db.get_single_value("MRP Settings", 'enable_vendor_bill_no_unique_restriction')
		if not flag:
			return
		start_date = frappe.db.get_single_value("MRP Settings", 'fiscal_year_start_date')
		end_date = frappe.db.get_single_value("MRP Settings", 'fiscal_year_end_date')
		exist_bills= frappe.get_all("Vendor Bill Tracking", filters = [
			['bill_date', 'between', [start_date, end_date]],
			['supplier','=',self.supplier],
			['bill_no', '=', self.bill_no],
			['docstatus', '!=', 2]
		])
		if exist_bills:
			frappe.throw("The Following Bills Are Already Exist<br>"+"<br>".join([ f"<a href='/app/vendor-bill-tracking/{i['name']}' target='_blank' >{i['name']}</a>" for i in exist_bills]))

	def set_amended_log(self):
		self.append('vendor_bill_tracking_history', {
			"assigned_by" : frappe.session.user,
			"assigned_on" : frappe.utils.now_datetime(),
			"action" : "Amend"
		})
		self.set('form_status', 'Amended')

	def set_cancelled_log(self):
		self.append('vendor_bill_tracking_history', {
			"assigned_by" : frappe.session.user,
			"assigned_on" : frappe.utils.now_datetime(),
			"action" : "Cancel"
		})
		self.set('form_status', 'Cancelled')

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
	
	def assign_bill_to_department(self, user, remarks = None):
		self.append("vendor_bill_tracking_history", {
			"assigned_to" : user,
			'assigned_on' : frappe.utils.now_datetime(),
			"assigned_by" : frappe.session.user,
			"remarks" : remarks,
			"action" : 'Assign'
		})
		self.set('form_status', 'Assigned')
		self.set('assigned_to', user)

@frappe.whitelist()
def assign_vendor_bill(name, assigned_to, remarks = None):
	from production_api.production_api.doctype.supplier.supplier import update_supplier_department_on_vbt
	doc = frappe.get_doc("Vendor Bill Tracking", name)
	if doc.docstatus != 1 or doc.form_status not in ['Reopen', "Open", "Assigned", "Amended"]:
		frappe.throw(f"Can't Assign Vendor Bill {doc.name}")
	doc.assign_bill_to_department(assigned_to, remarks)
	update_supplier_department_on_vbt(doc.supplier, assigned_to)
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
def make_bill_recieved_acknowledgement(doc_name):
	departments = get_user_departments()
	vbt_doc = frappe.get_doc("Vendor Bill Tracking", doc_name)
	if vbt_doc.assigned_to not in departments:
		frappe.throw("This Bill is Assigned To Your Department")
	last_doc = None
	for idx, i in enumerate(vbt_doc.vendor_bill_tracking_history):
		if i.get('assigned_to') == vbt_doc.get('assigned_to'):
			last_doc = i
	if not last_doc:
		frappe.throw("Invalid Operation")
	last_doc.received = 1
	vbt_doc.save(ignore_permissions = True)
	

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

@frappe.whitelist()
def check_for_can_show_receive_btn(name):
	department = frappe.get_value("Vendor Bill Tracking", name, 'assigned_to')
	exists = get_user_departments(department)
	if exists:
		return True
	return False

@frappe.whitelist()
def get_erp_inv_link(name):
	import urllib.parse
	d = frappe.get_doc("Vendor Bill Tracking", name)
	if d.docstatus == 1 and d.purchase_invoice:
		erp_url = frappe.get_single("MRP Settings").erp_site_url
		return f"{erp_url}/app/purchase-invoice/{urllib.parse.quote(d.purchase_invoice, safe='')}"
	else:
		frappe.throw("Document not submitted")
