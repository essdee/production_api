# Copyright (c) 2025, Aerele Technologies Pvt Ltd and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking import (
	revert_purchase_invoice_link,
)


def _make_vbt(pi_field, pi_value, form_status):
	supplier = frappe.db.get_value("Supplier", {}, "name") or frappe.get_doc({
		"doctype": "Supplier",
		"supplier_name": "VBT-Test-Supplier",
		"supplier_group": frappe.db.get_value("Supplier Group", {}, "name"),
	}).insert(ignore_permissions=True).name

	doc = frappe.get_doc({
		"doctype": "Vendor Bill Tracking",
		"supplier": supplier,
		"bill_no": frappe.generate_hash(length=8),
		"bill_date": frappe.utils.today(),
		"invoice_value": 100,
		"received_date": frappe.utils.today(),
		"received_via": "HO",
	})
	doc.insert(ignore_permissions=True)
	doc.submit()
	frappe.db.set_value("Vendor Bill Tracking", doc.name, {
		pi_field: pi_value,
		"form_status": form_status,
	}, update_modified=False)
	return frappe.get_doc("Vendor Bill Tracking", doc.name)


class TestVendorBillTracking(FrappeTestCase):
	def test_revert_invalid_field_raises(self):
		with self.assertRaises(frappe.ValidationError):
			revert_purchase_invoice_link("nonexistent", "bogus_field", "PI-X")

	def test_revert_mismatch_is_noop_and_logs(self):
		vbt = _make_vbt("mrp_purchase_invoice", "PI-REAL", "Closed")
		before_logs = frappe.db.count("Error Log")
		revert_purchase_invoice_link(vbt.name, "mrp_purchase_invoice", "PI-OTHER", origin="MRP-cancel")
		vbt.reload()
		self.assertEqual(vbt.mrp_purchase_invoice, "PI-REAL")
		self.assertEqual(vbt.form_status, "Closed")
		self.assertGreater(frappe.db.count("Error Log"), before_logs)

	def test_mrp_revert_clears_field_only(self):
		# MRP-side revert: only the mrp_purchase_invoice link is cleared — no reopen
		# row and no status change (the bill's Closed status is driven by the ERP PI).
		vbt = _make_vbt("mrp_purchase_invoice", "PI-MATCH", "Closed")
		history_before = len(vbt.vendor_bill_tracking_history)
		revert_purchase_invoice_link(vbt.name, "mrp_purchase_invoice", "PI-MATCH", origin="MRP-cancel")
		vbt.reload()
		self.assertFalse(vbt.mrp_purchase_invoice)
		self.assertEqual(vbt.form_status, "Closed")
		self.assertEqual(len(vbt.vendor_bill_tracking_history), history_before)

	def test_erp_revert_closed_reopens_with_history(self):
		# ERP-side revert of a Closed bill: clear the link, add a Reopen history row
		# and revert the status to Reopen.
		vbt = _make_vbt("purchase_invoice", "PI-ERP-CLOSED", "Closed")
		history_before = len(vbt.vendor_bill_tracking_history)
		revert_purchase_invoice_link(vbt.name, "purchase_invoice", "PI-ERP-CLOSED", origin="ERP-cancel")
		vbt.reload()
		self.assertFalse(vbt.purchase_invoice)
		self.assertEqual(vbt.form_status, "Reopen")
		self.assertEqual(len(vbt.vendor_bill_tracking_history), history_before + 1)
		last = vbt.vendor_bill_tracking_history[-1]
		self.assertEqual(last.action, "Reopen")
		self.assertIn("ERP-cancel", last.remarks or "")
		self.assertIn("PI-ERP-CLOSED", last.remarks or "")

	def test_erp_revert_non_closed_keeps_status_adds_history(self):
		# ERP-side revert of a non-Closed bill: clear the link and add a Reopen row,
		# but leave the status untouched.
		vbt = _make_vbt("purchase_invoice", "PI-ERP-1", "Open")
		revert_purchase_invoice_link(vbt.name, "purchase_invoice", "PI-ERP-1", origin="ERP-delete")
		vbt.reload()
		self.assertFalse(vbt.purchase_invoice)
		self.assertEqual(vbt.form_status, "Open")
		last = vbt.vendor_bill_tracking_history[-1]
		self.assertEqual(last.action, "Reopen")
		self.assertIn("ERP-delete", last.remarks or "")
