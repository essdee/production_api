# Copyright (c) 2023, Essdee and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.mrp_stock.stock_ledger import update_entries_after


class TestStockLedgerEntry(FrappeTestCase):
	def test_fifo_value_is_rebuilt_from_queue_without_negative_rounding_residue(self):
		updater = object.__new__(update_entries_after)
		updater.wh_data = frappe._dict(
			qty_after_transaction=38,
			stock_value=521.09,
			valuation_rate=13.7129305,
			stock_queue=[[9, 57.89928641], [29, 0]],
		)
		sle = frappe._dict(qty=-35, rate=13.7129305, outgoing_rate=0)

		updater.update_queue_values(sle)

		self.assertEqual(updater.wh_data.qty_after_transaction, 3)
		self.assertEqual(updater.wh_data.stock_queue, [[3, 0]])
		self.assertEqual(updater.wh_data.stock_value, 0)
		self.assertEqual(updater.wh_data.valuation_rate, 0)
