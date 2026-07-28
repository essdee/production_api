from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
import requests

from production_api.telegram_approval.adapters import _parse_roles
from production_api.telegram_approval.api import _clean_error
from production_api.telegram_approval.client import TelegramAPIError, TelegramClient
from production_api.telegram_approval.renderers import render_message
from production_api.telegram_approval.service import build_approval_keyboard


class TestTelegramApprovalHelpers(TestCase):
	def test_role_parser_accepts_commas_and_newlines(self):
		self.assertEqual(
			_parse_roles("Merch Manager, Accounts Manager\nSystem Manager"),
			{"Merch Manager", "Accounts Manager", "System Manager"},
		)

	def test_callback_data_is_short_and_opaque(self):
		route = frappe._dict(
			{
				"approve_action": "Approve",
				"reject_action": "Reject",
			}
		)
		doc = frappe._dict({"doctype": "Process Cost", "name": "PC-0001"})
		keyboard = build_approval_keyboard("abc123def4", route, doc)

		callbacks = [
			button["callback_data"]
			for row in keyboard["inline_keyboard"]
			for button in row
			if button.get("callback_data")
		]
		self.assertEqual(callbacks, ["ta:abc123def4:a", "ta:abc123def4:r"])
		self.assertTrue(all(len(value.encode()) <= 64 for value in callbacks))

	def test_user_facing_errors_do_not_include_html(self):
		self.assertEqual(_clean_error(Exception("<b>Not permitted</b>")), "Not permitted")

	def test_process_cost_renderer_includes_child_table_values(self):
		doc = frappe._dict(
			{
				"doctype": "Process Cost",
				"name": "PC-TEST",
				"lot": "LOT-001",
				"item": "Test Item",
				"uom": "Pieces",
				"process_name": "Cutting",
				"supplier": "SUP-001",
				"supplier_name": "Test Supplier",
				"from_date": "2026-07-28",
				"to_date": None,
				"attribute": "Colour",
				"tax_slab": "5",
				"is_rework": 0,
				"process_cost_values": [
					frappe._dict(
						{
							"attribute_value": "Red",
							"min_order_qty": 25,
							"price": 12.5,
						}
					),
					frappe._dict(
						{
							"attribute_value": "Blue",
							"min_order_qty": 50,
							"price": 11,
						}
					),
				],
			}
		)
		message = render_message(doc, frappe._dict({"trigger_value": "Approval Pending"}))

		self.assertIn("PROCESS COST VALUES (2)", message)
		self.assertIn("1. Red", message)
		self.assertIn("Minimum Order Qty: 25 Pieces", message)
		self.assertIn("2. Blue", message)
		self.assertIn("Price (Excl. Tax)", message)

	@patch("production_api.telegram_approval.renderers.frappe.get_all")
	def test_purchase_invoice_renderer_includes_requested_summary(self, get_all):
		get_all.return_value = [
			frappe._dict({"debit_value": 125}),
			frappe._dict({"debit_value": 75.5}),
		]
		doc = frappe._dict(
			{
				"doctype": "Purchase Invoice",
				"name": "MPI-TEST",
				"billing_supplier": "Test Supplier",
				"supplier": "Test Supplier",
				"against": "Work Order",
				"bill_no": "BILL-101",
				"bill_date": "2026-07-28",
				"total": 12000,
				"purchase_invoice_debit_details": [],
				"pi_work_order_billed_details": [
					frappe._dict(
						{
							"work_order": "WO-001",
							"total_delivered": 100,
							"total_received": 95,
						}
					),
					frappe._dict(
						{
							"work_order": "WO-001",
							"total_delivered": 50,
							"total_received": 48,
						}
					),
				],
			}
		)
		message = render_message(
			doc, frappe._dict({"trigger_value": "Approval Initiated"})
		)

		self.assertIn("PURCHASE INVOICE APPROVAL", message)
		self.assertIn("Approval Stage: Approval Initiated", message)
		self.assertIn("Total Delivered: 150", message)
		self.assertIn("Total Received: 143", message)
		self.assertIn("Debit Amount:", message)
		self.assertIn("200.50", message)
		self.assertIn("Total Amount:", message)
		self.assertIn("12,000.00", message)
		get_all.assert_called_once()


class TestTelegramClient(TestCase):
	@patch("production_api.telegram_approval.client.requests.post")
	def test_successful_api_call_returns_result(self, post):
		response = Mock()
		response.ok = True
		response.json.return_value = {"ok": True, "result": {"id": 123}}
		post.return_value = response

		self.assertEqual(TelegramClient("secret-token").get_me(), {"id": 123})

	@patch("production_api.telegram_approval.client.requests.post")
	def test_connection_error_never_exposes_token(self, post):
		post.side_effect = requests.ConnectionError("request URL contained secret-token")
		client = TelegramClient("secret-token")

		with self.assertRaises(TelegramAPIError) as error:
			client.get_me()

		self.assertNotIn("secret-token", str(error.exception))
