# Copyright (c) 2025, Aerele Technologies Pvt Ltd and Contributors
# See license.txt

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.vendor_bill_tracking import vendor_bill_tracking as vbt_api
from production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking import (
	revert_purchase_invoice_link,
)


class TestVendorBillTrackingMetadata(unittest.TestCase):
	def test_form_status_supports_cancel_approval_states_once(self):
		metadata = json.loads(Path(__file__).with_name("vendor_bill_tracking.json").read_text())
		status_field = next(field for field in metadata["fields"] if field["fieldname"] == "form_status")
		options = status_field["options"].splitlines()

		self.assertEqual(options.count("Pending Approval"), 1)
		self.assertEqual(options.count("Cancel Request Approved"), 1)


class _FakeVendorBill:
	def __init__(
		self,
		*,
		name="VBT-TEST",
		docstatus=1,
		form_status="Open",
		purchase_invoice=None,
		mrp_purchase_invoice=None,
	):
		self.name = name
		self.docstatus = docstatus
		self.form_status = form_status
		self.purchase_invoice = purchase_invoice
		self.mrp_purchase_invoice = mrp_purchase_invoice
		self.cancel_reason = None
		self.vendor_bill_tracking_history = []
		self.flags = frappe._dict()
		self.saved = False

	def set(self, fieldname, value):
		setattr(self, fieldname, value)

	def save(self, ignore_permissions=False):
		self.saved = ignore_permissions

	def append(self, fieldname, values):
		row = frappe._dict(values)
		getattr(self, fieldname).append(row)
		return row

	def set_cancelled_log(self):
		vbt_api.VendorBillTracking.set_cancelled_log(self)

	def cancel(self):
		previous_docstatus = self.docstatus
		self.docstatus = 2
		try:
			vbt_api.VendorBillTracking.before_cancel(self)
		except Exception:
			self.docstatus = previous_docstatus
			raise


class TestVendorBillCancellationStateMachine(unittest.TestCase):
	def call_as(self, roles, doc, method, *args):
		previous_db = getattr(frappe.local, "db", None)
		previous_flags = getattr(frappe.local, "flags", None)
		previous_message_log = getattr(frappe.local, "message_log", None)
		previous_session = getattr(frappe.local, "session", None)
		frappe.local.db = MagicMock()
		frappe.local.db.get_value.return_value = doc.name
		frappe.local.flags = frappe._dict(in_test=True, mute_messages=True)
		frappe.local.message_log = []
		frappe.local.session = frappe._dict(user="hr-user@example.com")
		try:
			with (
				patch.object(vbt_api.frappe, "get_roles", return_value=roles),
				patch.object(vbt_api.frappe, "get_doc", return_value=doc),
				patch.object(vbt_api.frappe.utils, "now_datetime", return_value="2026-10-03 12:00:00"),
			):
				return method(doc.name, *args)
		finally:
			frappe.local.db = previous_db
			frappe.local.flags = previous_flags
			frappe.local.message_log = previous_message_log
			frappe.local.session = previous_session

	def test_hr_user_requests_cancellation_from_each_requestable_status(self):
		for status in ("Open", "Assigned", "Reopen", "Amended"):
			with self.subTest(status=status):
				doc = _FakeVendorBill(form_status=status)
				self.call_as(["HR User"], doc, vbt_api.request_vendor_bill_cancellation)
				self.assertEqual(doc.form_status, "Pending Approval")
				self.assertTrue(doc.saved)

	def test_non_hr_user_cannot_request_cancellation(self):
		doc = _FakeVendorBill()
		with self.assertRaises(frappe.PermissionError):
			self.call_as(["Accounts User"], doc, vbt_api.request_vendor_bill_cancellation)
		self.assertEqual(doc.form_status, "Open")

	def test_request_requires_submitted_document(self):
		for docstatus in (0, 2):
			with self.subTest(docstatus=docstatus):
				doc = _FakeVendorBill(docstatus=docstatus)
				with self.assertRaises(frappe.ValidationError):
					self.call_as(["HR User"], doc, vbt_api.request_vendor_bill_cancellation)
				self.assertEqual(doc.form_status, "Open")

	def test_request_rejects_each_purchase_invoice_link(self):
		for fieldname in ("purchase_invoice", "mrp_purchase_invoice"):
			with self.subTest(fieldname=fieldname):
				doc = _FakeVendorBill(**{fieldname: "PI-TEST"})
				with self.assertRaises(frappe.ValidationError):
					self.call_as(["HR User"], doc, vbt_api.request_vendor_bill_cancellation)
				self.assertEqual(doc.form_status, "Open")

	def test_repeated_request_is_rejected(self):
		doc = _FakeVendorBill(form_status="Pending Approval")
		with self.assertRaises(frappe.ValidationError):
			self.call_as(["HR User"], doc, vbt_api.request_vendor_bill_cancellation)
		self.assertEqual(doc.form_status, "Pending Approval")

	def test_hr_manager_approves_pending_request(self):
		doc = _FakeVendorBill(form_status="Pending Approval")
		self.call_as(["HR Manager"], doc, vbt_api.approve_vendor_bill_cancellation)
		self.assertEqual(doc.form_status, "Cancel Request Approved")

	def test_non_hr_manager_cannot_approve_request(self):
		doc = _FakeVendorBill(form_status="Pending Approval")
		with self.assertRaises(frappe.PermissionError):
			self.call_as(["HR User"], doc, vbt_api.approve_vendor_bill_cancellation)
		self.assertEqual(doc.form_status, "Pending Approval")

	def test_approval_rejects_out_of_order_and_repeated_actions(self):
		for status in ("Open", "Cancel Request Approved"):
			with self.subTest(status=status):
				doc = _FakeVendorBill(form_status=status)
				with self.assertRaises(frappe.ValidationError):
					self.call_as(["HR Manager"], doc, vbt_api.approve_vendor_bill_cancellation)
				self.assertEqual(doc.form_status, status)

	def test_user_with_both_roles_still_requires_request_then_approval(self):
		doc = _FakeVendorBill(form_status="Open")
		roles = ["HR User", "HR Manager"]
		with self.assertRaises(frappe.ValidationError):
			self.call_as(roles, doc, vbt_api.approve_vendor_bill_cancellation)
		self.call_as(roles, doc, vbt_api.request_vendor_bill_cancellation)
		self.assertEqual(doc.form_status, "Pending Approval")
		self.call_as(roles, doc, vbt_api.approve_vendor_bill_cancellation)
		self.assertEqual(doc.form_status, "Cancel Request Approved")

	def test_approval_rejects_each_purchase_invoice_link(self):
		for fieldname in ("purchase_invoice", "mrp_purchase_invoice"):
			with self.subTest(fieldname=fieldname):
				doc = _FakeVendorBill(form_status="Pending Approval", **{fieldname: "PI-TEST"})
				with self.assertRaises(frappe.ValidationError):
					self.call_as(["HR Manager"], doc, vbt_api.approve_vendor_bill_cancellation)
				self.assertEqual(doc.form_status, "Pending Approval")

	def test_cancel_whitelist_rejects_unapproved_status(self):
		doc = _FakeVendorBill(form_status="Pending Approval")
		with self.assertRaises(frappe.ValidationError):
			self.call_as(["HR User"], doc, vbt_api.cancel_vendor_bill, "duplicate")
		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(doc.form_status, "Pending Approval")

	def test_direct_cancel_rejects_unapproved_status(self):
		doc = _FakeVendorBill(form_status="Open")
		with self.assertRaises(frappe.ValidationError):
			self.call_as(["HR User"], doc, lambda _name: doc.cancel())
		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(doc.form_status, "Open")

	def test_cancel_rejects_non_hr_user_after_approval(self):
		doc = _FakeVendorBill(form_status="Cancel Request Approved")
		with self.assertRaises(frappe.PermissionError):
			self.call_as(["HR Manager"], doc, vbt_api.cancel_vendor_bill, "duplicate")
		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(doc.form_status, "Cancel Request Approved")

	def test_cancel_rechecks_purchase_invoice_links_after_approval(self):
		doc = _FakeVendorBill(
			form_status="Cancel Request Approved",
			purchase_invoice="PI-LATE",
		)
		with self.assertRaises(frappe.ValidationError):
			self.call_as(["HR User"], doc, vbt_api.cancel_vendor_bill, "duplicate")
		self.assertEqual(doc.docstatus, 1)

	def test_approved_hr_user_cancels_with_reason_and_history(self):
		doc = _FakeVendorBill(form_status="Cancel Request Approved")
		self.call_as(["HR User"], doc, vbt_api.cancel_vendor_bill, "duplicate bill")
		self.assertEqual(doc.docstatus, 2)
		self.assertEqual(doc.form_status, "Cancelled")
		self.assertEqual(doc.cancel_reason, "duplicate bill")
		self.assertEqual(doc.vendor_bill_tracking_history[-1].action, "Cancel")


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
