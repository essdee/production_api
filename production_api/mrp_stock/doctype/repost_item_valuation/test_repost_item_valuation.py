# Copyright (c) 2025, Essdee and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.patches.v1_0 import repair_negative_stock_valuations as repair


class TestRepostItemValuation(FrappeTestCase):
	def test_classifies_currency_rounding_residual(self):
		row = frappe._dict(
			qty=-35,
			rate=13.71,
			qty_after_transaction=3,
			stock_value=-0.01,
			stock_queue="[[3, 0]]",
		)
		self.assertEqual(repair._classify_negative(row), "fifo_currency_rounding_residual")

	def test_classifies_negative_incoming_transaction_rate(self):
		row = frappe._dict(
			qty=3.878,
			rate=-253.196,
			qty_after_transaction=3.878,
			stock_value=-981.89,
			stock_queue="[[3.878, -253.196]]",
		)
		self.assertEqual(
			repair._classify_negative(row), "negative_incoming_transaction_rate"
		)

	def test_incoming_replacement_rate_uses_source_value_movement(self):
		row = frappe._dict(
			voucher_type="Delivery Challan",
			voucher_no="DC-TEST",
			voucher_detail_no="ROW-1",
			qty=3.878,
		)
		siblings = [
			frappe._dict(qty=-3.878, stock_value_difference=-1175.91),
			frappe._dict(qty=3.878, stock_value_difference=-981.89),
		]
		with patch.object(repair.frappe, "get_all", return_value=siblings):
			rate = repair._get_replacement_transaction_rate(row)

		self.assertAlmostEqual(rate, 303.22588963)
