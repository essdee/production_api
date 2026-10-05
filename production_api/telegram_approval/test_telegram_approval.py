from unittest import TestCase
from unittest.mock import Mock, patch
from pathlib import Path
from datetime import datetime

from jinja2 import Template

import frappe
import requests

from production_api.telegram_approval.adapters import (
	TelegramApprovalPermissionError,
	TelegramApprovalStateError,
	_parse_roles,
)
from production_api.telegram_approval.api import _clean_error
from production_api.telegram_approval.client import TelegramAPIError, TelegramClient
from production_api.telegram_approval.renderers import render_message
from production_api.telegram_approval.service import build_approval_keyboard


_INITIALIZED_FRAPPE = False


def setUpModule():
	global _INITIALIZED_FRAPPE
	if not getattr(frappe.local, "site", None):
		sites_path = Path(__file__).resolve().parents[4] / "sites"
		frappe.init(site="mrp3.site", sites_path=str(sites_path))
		_INITIALIZED_FRAPPE = True


def tearDownModule():
	if _INITIALIZED_FRAPPE:
		frappe.destroy()


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


PURCHASE_ORDER_TEMPLATE = """\
PURCHASE ORDER APPROVAL
───────────────────────
PO: {{ doc.name }}
Supplier: {{ doc.supplier_name or doc.supplier or "-" }}
PO Date: {{ format_date(doc.po_date) }}
{% for row in purchase_order_items %}
{{ loop.index }}. {{ row.item }} | Qty: {{ format_qty(row.qty) }} | Lot: {{ row.lot or "-" }} | Rate: {{ format_currency(row.rate) }}
{% endfor %}
Grand Total: {{ format_currency(doc.grand_total) }}"""


class TestTelegramApprovalHelpers(TestCase):
	def setUp(self):
		self.render_template = patch(
			"production_api.telegram_approval.renderers.frappe.render_template",
			side_effect=lambda template, context: Template(template).render(context),
		)
		self.format_currency = patch(
			"production_api.telegram_approval.renderers._format_currency",
			side_effect=lambda value: f"{float(value or 0):,.2f}",
		)
		self.format_date = patch(
			"production_api.telegram_approval.renderers.format_date",
			side_effect=lambda value: datetime.strptime(str(value), "%Y-%m-%d").strftime("%d-%m-%Y"),
		)
		self.render_template.start()
		self.format_currency.start()
		self.format_date.start()

	def tearDown(self):
		self.format_date.stop()
		self.format_currency.stop()
		self.render_template.stop()

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

	def test_purchase_order_renderer_includes_all_requested_rows(self):
		doc = frappe._dict(
			{
				"doctype": "Purchase Order",
				"name": "PO-0012",
				"supplier": "SUP-001",
				"supplier_name": "Yarn Supplier",
				"po_date": "2026-10-05",
				"grand_total": 1275,
				"items": [
					frappe._dict({"item_variant": "YARN-RED", "qty": 10, "lot": "LOT-1", "rate": 75}),
					frappe._dict({"item_variant": "YARN-BLUE", "qty": 5, "lot": "LOT-2", "rate": 105}),
				],
			}
		)
		message = render_message(
			doc,
			frappe._dict({"trigger_value": "Pending Approval", "message_template": PURCHASE_ORDER_TEMPLATE}),
		)

		self.assertIn("PO-0012", message)
		self.assertIn("Yarn Supplier", message)
		self.assertIn("05-10-2026", message)
		self.assertIn("YARN-RED", message)
		self.assertIn("Qty: 10", message)
		self.assertIn("LOT-1", message)
		self.assertIn("YARN-BLUE", message)
		self.assertIn("Qty: 5", message)
		self.assertIn("LOT-2", message)
		self.assertIn("1,275.00", message)

	@patch("production_api.telegram_approval.service._expire_stale_requests")
	@patch("production_api.telegram_approval.service.frappe.enqueue")
	@patch("production_api.telegram_approval.service.get_settings")
	def test_purchase_order_document_event_never_auto_sends(self, get_settings, enqueue, expire):
		from production_api.telegram_approval.service import handle_document_event

		get_settings.return_value = frappe._dict(
			{
				"enabled": 1,
				"routes": [
					frappe._dict(
						{
							"name": "PO-ROUTE",
							"enabled": 1,
							"reference_doctype": "Purchase Order",
							"trigger_field": "status",
							"trigger_value": "Pending Approval",
						}
					)
				],
			}
		)
		doc = frappe._dict({"doctype": "Purchase Order", "name": "PO-0012", "status": "Pending Approval"})
		doc.get_doc_before_save = Mock(return_value=frappe._dict({"status": "Draft"}))

		handle_document_event(doc)

		enqueue.assert_not_called()
		expire.assert_called_once_with(doc)

	@patch("production_api.telegram_approval.service._expire_stale_requests")
	@patch("production_api.telegram_approval.service.get_settings")
	def test_submitted_purchase_order_defers_to_on_submit_finalization(self, get_settings, expire):
		from production_api.telegram_approval.service import handle_document_event

		get_settings.return_value = frappe._dict(
			{
				"enabled": 1,
				"routes": [
					frappe._dict({"enabled": 1, "reference_doctype": "Purchase Order"})
				],
			}
		)
		doc = frappe._dict(
			{"doctype": "Purchase Order", "name": "PO-0012", "docstatus": 1, "status": "Ordered"}
		)
		handle_document_event(doc)
		expire.assert_not_called()


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


class TestPurchaseOrderTelegramActions(TestCase):
	def setUp(self):
		self.adapter_translation = patch(
			"production_api.telegram_approval.adapters._", side_effect=lambda message: message
		)
		self.api_translation = patch(
			"production_api.telegram_approval.api._", side_effect=lambda message: message
		)
		self.adapter_translation.start()
		self.api_translation.start()

	def tearDown(self):
		self.api_translation.stop()
		self.adapter_translation.stop()

	def _route(self, **overrides):
		values = {
			"process_type": "Field State",
			"target_field": "status",
			"trigger_field": "status",
			"trigger_value": "Pending Approval",
			"approve_action": "Approve PO",
			"reject_action": "Reject PO",
			"approve_value": "Ordered",
			"reject_value": "Draft",
			"approve_roles": "System Manager",
			"reject_roles": "System Manager",
		}
		values.update(overrides)
		return frappe._dict(values)

	def _doc(self, status="Pending Approval"):
		doc = Mock()
		doc.doctype = "Purchase Order"
		doc.name = "PO-0012"
		doc.status = status
		doc.get.side_effect = lambda key: getattr(doc, key)
		doc.meta.has_field.return_value = True
		return doc

	@patch("production_api.telegram_approval.adapters.frappe.get_doc")
	@patch("production_api.purchase_order_approval.approve_purchase_order")
	def test_mapped_system_manager_callback_submits_po(self, approve, get_doc):
		from production_api.telegram_approval.adapters import _apply_purchase_order_action

		doc = self._doc()
		updated = self._doc(status="Ordered")
		updated.docstatus = 1
		get_doc.return_value = updated
		result = _apply_purchase_order_action(
			doc, self._route(), "a", "Approve PO", "status", "Ordered"
		)
		approve.assert_called_once_with("PO-0012")
		self.assertIs(result, updated)

	@patch("production_api.telegram_approval.adapters.frappe.get_doc")
	@patch("production_api.purchase_order_approval.reject_purchase_order")
	def test_mapped_system_manager_callback_rejects_and_unlocks_po(self, reject, get_doc):
		from production_api.telegram_approval.adapters import _apply_purchase_order_action

		doc = self._doc()
		updated = self._doc(status="Draft")
		get_doc.return_value = updated
		result = _apply_purchase_order_action(
			doc, self._route(), "r", "Reject PO", "status", "Draft"
		)
		reject.assert_called_once_with("PO-0012")
		self.assertIs(result, updated)

	@patch("production_api.telegram_approval.adapters.frappe.get_roles", return_value=["Purchase Manager"])
	def test_mapped_non_manager_is_rejected(self, get_roles):
		from production_api.telegram_approval.adapters import _validate_action_roles

		with self.assertRaises(TelegramApprovalPermissionError):
			_validate_action_roles(self._route(), "a", "Approve PO")

	def test_direct_target_value_manipulation_is_rejected(self):
		from production_api.telegram_approval.adapters import _apply_purchase_order_action

		with self.assertRaises(TelegramApprovalStateError):
			_apply_purchase_order_action(
				self._doc(),
				self._route(approve_value="Draft"),
				"a",
				"Approve PO",
				"status",
				"Draft",
			)

	@patch("production_api.telegram_approval.adapters.frappe.get_doc")
	def test_stale_purchase_order_state_is_rejected_before_action(self, get_doc):
		from production_api.telegram_approval.adapters import execute_action

		get_doc.return_value = self._doc(status="Draft")
		request = frappe._dict(
			{
				"reference_doctype": "Purchase Order",
				"reference_name": "PO-0012",
				"state_field": "status",
				"source_value": "Pending Approval",
			}
		)
		with self.assertRaises(TelegramApprovalStateError):
			execute_action(request, self._route(), "manager@example.com", "a")

	@patch("production_api.telegram_approval.api._answer_callback")
	@patch("production_api.telegram_approval.api.get_client")
	@patch("production_api.telegram_approval.api.frappe")
	def test_repeated_callback_leaves_po_unchanged(self, frappe_module, get_client, answer):
		from production_api.telegram_approval.api import _process_callback_query

		request = frappe._dict(
			{
				"name": "REQ123",
				"status": "Approved",
				"group_chat_id": "-100123",
				"telegram_message_id": "55",
			}
		)
		frappe_module.db.exists.return_value = True
		frappe_module.get_doc.return_value = request
		_process_callback_query({"id": "CB-1", "data": "ta:REQ123:a"})
		answer.assert_called_once()
		frappe_module.set_user.assert_not_called()
