from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.utils import get_work_order_pending_report


class TestWorkOrderPendingReport(FrappeTestCase):
	def test_filters_submitted_work_orders_and_wo_date(self):
		expected = [{
			"production_order": "PPO-TEST",
			"work_order": "WO-TEST",
			"lot": "LOT-TEST",
			"process_name": "Sewing",
			"supplier_name": "Test Supplier",
			"item_name": "Test Item",
			"item_variant": "Test Variant",
			"delivered_qty": 10,
			"received_qty": 4,
			"pending_quantity": 6,
		}]
		with patch.object(frappe.db, "sql", return_value=expected) as sql:
			result = get_work_order_pending_report(
				production_order=["PPO-TEST"],
				lot=["LOT-TEST"],
				process=["Sewing"],
				supplier=["SUP-TEST"],
				item=["ITEM-TEST"],
				item_variant=["VARIANT-TEST"],
				from_date="2026-07-01",
				to_date="2026-07-31",
				status="Open",
			)

		query, params = sql.call_args.args[:2]
		self.assertIn("t1.docstatus = 1", query)
		self.assertIn("t1.name AS work_order", query)
		self.assertIn("t1.wo_date BETWEEN", query)
		self.assertIn("l.production_order IN", query)
		self.assertIn("t2.item_variant IN", query)
		self.assertEqual(params["from_date"], "2026-07-01")
		self.assertEqual(params["to_date"], "2026-07-31")
		self.assertEqual(params["open_status"], "Open")
		self.assertEqual(result, expected)

	def test_packing_wo_is_collapsed_and_received_is_converted_to_pieces(self):
		with patch.object(frappe.db, "sql", return_value=[]) as sql:
			get_work_order_pending_report()

		query = sql.call_args.args[0]
		self.assertIn("t1.name AS work_order", query)
		self.assertIn("ipd.packing_combo", query)
		self.assertIn("packing_grn.received_qty", query)
		self.assertIn("grn.is_return = 0", query)
		self.assertIn("THEN COALESCE(t1.item, '')", query)
		self.assertIn("t1.includes_packing", query)
		self.assertIn("t1.name,", query)
		self.assertNotIn("HAVING pending_quantity > 0", query)

	def test_requires_both_dates(self):
		with self.assertRaisesRegex(frappe.ValidationError, "both From Date and To Date"):
			get_work_order_pending_report(from_date="2026-07-01")

	def test_page_has_requested_filters_and_columns(self):
		from pathlib import Path

		source = Path(
			frappe.get_app_path(
				"production_api",
				"public",
				"js",
				"components",
				"WorkOrderPendingReport.vue",
			)
		).read_text()

		for label in (
			"Production Order",
			"WO",
			"Lot",
			"Process",
			"Supplier",
			"Item",
			"Item Variant",
			"Delivered",
			"Received",
			"Diff",
		):
			self.assertIn(f">{label}<", source)
		self.assertIn('"from_date"', source)
		self.assertIn('"to_date"', source)
		self.assertIn('"status"', source)
