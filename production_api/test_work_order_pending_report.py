import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.report.work_order_pending_report import (
	work_order_pending_report as report,
)
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

	def test_script_report_forwards_filters_and_returns_native_summary(self):
		rows = [{
			"delivered_qty": 10,
			"received_qty": 4,
			"pending_quantity": 6,
		}]
		filters = {
			"production_order": ["PPO-TEST"],
			"lot": ["LOT-TEST"],
			"item": ["ITEM-TEST"],
			"item_variant": ["VARIANT-TEST"],
			"process": ["Sewing"],
			"supplier": ["SUP-TEST"],
			"from_date": "2026-07-01",
			"to_date": "2026-07-31",
			"status": "Open",
		}
		with patch.object(
			report,
			"get_work_order_pending_report",
			return_value=rows,
		) as get_data:
			columns, data, _message, _chart, summary = report.execute(filters)

		get_data.assert_called_once_with(**filters)
		self.assertEqual(data, rows)
		self.assertEqual(
			[column["fieldname"] for column in columns],
			[
				"production_order",
				"work_order",
				"lot",
				"process_name",
				"supplier_name",
				"item_name",
				"item_variant",
				"delivered_qty",
				"received_qty",
				"pending_quantity",
			],
		)
		self.assertEqual(
			[(row["label"], row["value"]) for row in summary],
			[("Rows", 1), ("Delivered", 10.0), ("Received", 4.0), ("Diff", 6.0)],
		)

	def test_standard_report_replaces_page_and_keeps_all_filters(self):
		report_dir = Path(
			frappe.get_app_path(
				"production_api",
				"production_api",
				"report",
				"work_order_pending_report",
			)
		)
		metadata = json.loads(
			(report_dir / "work_order_pending_report.json").read_text()
		)
		self.assertEqual(metadata["report_type"], "Script Report")
		self.assertEqual(metadata["ref_doctype"], "Work Order")
		self.assertEqual(metadata["add_total_row"], 1)

		source = (report_dir / "work_order_pending_report.js").read_text()
		for fieldname in (
			"production_order",
			"lot",
			"item",
			"item_variant",
			"process",
			"supplier",
			"from_date",
			"to_date",
			"status",
		):
			self.assertIn(f'"{fieldname}"', source)

		page_dir = Path(
			frappe.get_app_path(
				"production_api",
				"production_api",
				"page",
				"work_order_pending_report",
			)
		)
		self.assertFalse(
			(page_dir / "work_order_pending_report.json").exists()
		)
		self.assertFalse(
			(page_dir / "work_order_pending_report.js").exists()
		)

		workspace_path = Path(
			frappe.get_app_path(
				"production_api",
				"essdee_production",
				"workspace",
				"manufacturing",
				"manufacturing.json",
			)
		)
		workspace = json.loads(workspace_path.read_text())
		links = [
			link
			for link in workspace["links"]
			if link.get("link_to") == "Work Order Pending Report"
		]
		self.assertEqual(len(links), 1)
		self.assertEqual(links[0]["link_type"], "Report")
		self.assertEqual(links[0]["is_query_report"], 1)
