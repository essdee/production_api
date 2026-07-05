# Copyright (c) 2024, Essdee and Contributors
# See license.txt

"""P1 (2026-07 incident): the Packing Slip cancel flow must NEVER cancel fully
Delivered (or Cancelled) Stock Reservation Entries. The old code applied the
Delivered/Cancelled exclusion in get_stock_reservation_entries_for_voucher only
when ignore_status=True (inverted) — so cancel_stock_reservation_entries, which
uses the DEFAULT path, cancelled even delivered reservations after their stock
had physically left the warehouse.

SRE rows are inserted with db_insert (no link validation) against a fake voucher
and removed in tearDown; sre.cancel() is mocked in the cancel-flow test so no
Bin/Stock Settings fixtures are needed."""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.mrp_stock.doctype.stock_reservation_entry.stock_reservation_entry import (
	cancel_stock_reservation_entries,
	get_stock_reservation_entries_for_voucher,
)

TEST_VOUCHER = "TEST-PS-SRE-FILTER-0001"


def _insert_sre(name, status, docstatus=1, delivered_qty=0):
	doc = frappe.new_doc("Stock Reservation Entry")
	doc.name = name
	doc.item_code = "TEST-SRE-ITEM"
	doc.warehouse = "TEST-SRE-WH"
	doc.lot = "TEST-SRE-LOT"
	doc.received_type = "TEST-SRE-RT"
	doc.voucher_type = "Packing Slip"
	doc.voucher_no = TEST_VOUCHER
	doc.available_qty = 10
	doc.voucher_qty = 10
	doc.reserved_qty = 10
	doc.delivered_qty = delivered_qty
	doc.stock_uom = "TEST-UOM"
	doc.status = status
	doc.docstatus = docstatus
	doc.db_insert()
	return doc.name


class TestStockReservationEntry(FrappeTestCase):

	def setUp(self):
		super().setUp()
		self.reserved = _insert_sre("TEST-SRE-RESERVED", "Reserved")
		self.partially = _insert_sre("TEST-SRE-PARTIAL", "Partially Delivered", delivered_qty=4)
		self.delivered = _insert_sre("TEST-SRE-DELIVERED", "Delivered", delivered_qty=10)
		self.cancelled = _insert_sre("TEST-SRE-CANCELLED", "Cancelled", docstatus=2)

	def tearDown(self):
		frappe.db.delete("Stock Reservation Entry", {"voucher_no": TEST_VOUCHER})
		super().tearDown()

	def test_default_path_excludes_delivered_and_cancelled(self):
		names = {d.name for d in get_stock_reservation_entries_for_voucher(
			"Packing Slip", TEST_VOUCHER, fields=["name", "status"])}
		self.assertEqual(names, {self.reserved, self.partially})
		self.assertNotIn(self.delivered, names)
		self.assertNotIn(self.cancelled, names)

	def test_ignore_status_true_returns_everything_submitted(self):
		"""Escape hatch for callers that explicitly need every docstatus-1 SRE,
		including fully Delivered ones (docstatus-2 Cancelled stays excluded by
		the docstatus filter)."""
		names = {d.name for d in get_stock_reservation_entries_for_voucher(
			"Packing Slip", TEST_VOUCHER, fields=["name"], ignore_status=True)}
		self.assertEqual(names, {self.reserved, self.partially, self.delivered})

	def test_cancel_flow_never_cancels_delivered_sres(self):
		"""cancel_stock_reservation_entries (the Packing Slip cancel path, reached
		via production_api.api.stock.cancel_stock_reservation_entries) must only
		.cancel() live reservations."""
		cancelled_names = []

		def fake_get_doc(doctype, name):
			self.assertEqual(doctype, "Stock Reservation Entry")
			doc = MagicMock()
			doc.cancel.side_effect = lambda: cancelled_names.append(name)
			return doc

		with patch.object(frappe, "get_doc", side_effect=fake_get_doc):
			cancel_stock_reservation_entries(
				voucher_type="Packing Slip", voucher_no=TEST_VOUCHER, notify=False)

		self.assertEqual(set(cancelled_names), {self.reserved, self.partially})
		self.assertNotIn(self.delivered, cancelled_names)
		self.assertNotIn(self.cancelled, cancelled_names)

	def test_explicit_sre_list_is_untouched(self):
		"""Callers that pass sre_list bypass the voucher fetch — their explicit
		selection is honoured unchanged."""
		cancelled_names = []

		def fake_get_doc(doctype, name):
			doc = MagicMock()
			doc.cancel.side_effect = lambda: cancelled_names.append(name)
			return doc

		with patch.object(frappe, "get_doc", side_effect=fake_get_doc):
			cancel_stock_reservation_entries(sre_list=[self.reserved], notify=False)

		self.assertEqual(cancelled_names, [self.reserved])
