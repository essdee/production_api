from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
import requests

from production_api.telegram_approval.adapters import _parse_roles
from production_api.telegram_approval.api import _clean_error
from production_api.telegram_approval.client import TelegramAPIError, TelegramClient
from production_api.telegram_approval.renderers import render_message
from production_api.telegram_approval.service import (
	build_approval_keyboard,
	create_and_send_approval,
)
from production_api.production_api.doctype.telegram_approval_settings.telegram_approval_settings import (
	validate_message_template,
)
from production_api.patches.v1_0.fix_process_cost_telegram_template import (
	fix_requested_by_expression,
)


PROCESS_COST_TEMPLATE = """\
PROCESS COST APPROVAL
─────────────────────
Document: {{ doc.name }}
Lot: {{ doc.lot or "-" }}
Item: {{ doc.item or "-" }}
Process: {{ doc.process_name or "-" }}
Supplier: {{ doc.supplier_name or doc.supplier or "-" }}
Validity: {{ format_date(doc.from_date) }}{% if doc.to_date %} to {{ format_date(doc.to_date) }}{% else %} onwards{% endif %}
Attribute: {{ doc.attribute or "Not applicable" }}
Tax Slab: {{ doc.tax_slab or "-" }}
Rework: {% if doc.is_rework %}Yes{% else %}No{% endif %}

PROCESS COST VALUES ({{ doc.process_cost_values | length }})
─────────────────────
{% for row in doc.process_cost_values %}
{{ loop.index }}. {{ row.attribute_value or "Default" }}
   Minimum Order Qty: {{ format_qty(row.min_order_qty) }} {{ doc.uom or "" }}
   Price (Excl. Tax): {{ format_currency(row.price) }}
{% endfor %}"""


PURCHASE_INVOICE_TEMPLATE = """\
PURCHASE INVOICE APPROVAL
─────────────────────────
Document: {{ doc.name }}
Approval Stage: {{ route.trigger_value }}
Supplier: {{ doc.billing_supplier or doc.supplier or "-" }}
Against: {{ doc.against or "-" }}
Supplier Bill: {{ doc.bill_no or "-" }}
Bill Date: {% if doc.bill_date %}{{ format_date(doc.bill_date) }}{% else %}-{% endif %}
Work Order(s): {{ summary.work_orders }}

SUMMARY
─────────────────────────
Total Delivered: {{ format_qty(summary.total_delivered) }}
Total Received: {{ format_qty(summary.total_received) }}
Debit Amount: {{ format_currency(summary.debit_amount) }}
Total Amount: {{ format_currency(summary.total_amount) }}"""


class TestTelegramApprovalHelpers(TestCase):
	def test_valid_message_template_is_accepted(self):
		validate_message_template(
			'Requested By: {{ doc.modified_by or "-" }}',
			"Process Cost",
		)

	def test_invalid_message_template_is_rejected(self):
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"Invalid Telegram message template for Process Cost.*unknown tag 'doc'",
		):
			validate_message_template(
				"Requested By: {% doc.modified_by %}",
				"Process Cost",
			)

	def test_process_cost_template_patch_repairs_requested_by_tag(self):
		self.assertEqual(
			fix_requested_by_expression("Requested By: {% doc.modified_by %}"),
			'Requested By: {{ doc.modified_by or "-" }}',
		)

	@patch("production_api.telegram_approval.service.frappe.log_error")
	@patch("production_api.telegram_approval.service.render_approval_message")
	@patch("production_api.telegram_approval.service.frappe.db.exists", return_value=None)
	@patch("production_api.telegram_approval.service.frappe.get_doc")
	@patch("production_api.telegram_approval.service.get_settings")
	def test_template_render_failure_marks_request_as_error(
		self,
		get_settings,
		get_doc,
		_exists,
		render_approval_message,
		log_error,
	):
		route = frappe._dict(
			{
				"name": "ROUTE-1",
				"enabled": 1,
				"reference_doctype": "Process Cost",
				"process_type": "Workflow",
				"trigger_field": "workflow_state",
				"trigger_value": "Approval Pending",
				"group_chat_id": "-1001",
				"message_template": "{% doc.modified_by %}",
				"approve_action": "Approve",
				"reject_action": "Reject",
			}
		)
		get_settings.return_value = frappe._dict(enabled=1, routes=[route])
		source_doc = frappe._dict(
			{
				"doctype": "Process Cost",
				"name": "PC-TEST",
				"workflow_state": "Approval Pending",
			}
		)
		request_doc = Mock()
		request_doc.name = "REQUEST-1"
		request_builder = Mock()
		request_builder.insert.return_value = request_doc
		get_doc.side_effect = [source_doc, request_builder]
		render_approval_message.side_effect = frappe.ValidationError(
			"Invalid Telegram message template"
		)

		self.assertEqual(
			create_and_send_approval("Process Cost", "PC-TEST", "ROUTE-1"),
			"REQUEST-1",
		)
		request_doc.db_set.assert_called_once_with(
			{
				"status": "Error",
				"error": "Invalid Telegram message template",
			}
		)
		log_error.assert_called_once()

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
		message = render_message(
			doc,
			frappe._dict(
				{
					"trigger_value": "Approval Pending",
					"message_template": PROCESS_COST_TEMPLATE,
				}
			),
		)

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
			doc,
			frappe._dict(
				{
					"trigger_value": "Approval Initiated",
					"message_template": PURCHASE_INVOICE_TEMPLATE,
				}
			),
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
