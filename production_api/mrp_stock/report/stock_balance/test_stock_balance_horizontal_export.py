from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

import frappe

from production_api.mrp_stock.report.stock_balance import stock_balance


class TestStockBalanceHorizontalExport(TestCase):
	def test_queue_uses_long_worker_and_returns_immediately(self):
		job = SimpleNamespace(id="queued-job")
		with (
			patch.object(stock_balance.frappe, "has_permission") as has_permission,
			patch.object(stock_balance.frappe, "generate_hash", return_value="request123"),
			patch.object(stock_balance, "_set_horizontal_export_status") as set_status,
			patch.object(stock_balance.frappe, "enqueue", return_value=job) as enqueue,
		):
			result = stock_balance.queue_horizontal_download(
				'{"from_date":"2026-08-01","to_date":"2026-08-31"}'
			)

		has_permission.assert_called_once_with("Stock Ledger Entry", "read", throw=True)
		set_status.assert_called_once_with(
			"request123", frappe.session.user, "queued"
		)
		enqueue.assert_called_once_with(
			stock_balance.HORIZONTAL_EXPORT_JOB,
			queue="long",
			timeout=stock_balance.HORIZONTAL_EXPORT_TIMEOUT,
			job_id="stock-balance-horizontal-request123",
			filters={"from_date": "2026-08-01", "to_date": "2026-08-31"},
			request_id="request123",
			export_user=frappe.session.user,
		)
		self.assertEqual(result, {"request_id": "request123", "status": "queued"})

	def test_status_poll_bypasses_request_local_cache(self):
		ready = {
			"request_id": "request123",
			"status": "ready",
			"file_url": "/private/files/stock.xlsx",
		}
		with patch.object(
			stock_balance.frappe.cache,
			"get_value",
			return_value=ready,
		) as get_value:
			result = stock_balance.get_horizontal_download_status("request123")

		get_value.assert_called_once_with(
			stock_balance._horizontal_export_cache_key("request123"),
			user=frappe.session.user,
			expires=True,
		)
		self.assertEqual(result, ready)

	def test_worker_saves_private_file_before_marking_ready(self):
		file_doc = MagicMock(
			file_url="/private/files/Stock_Balance_Horizontal.xlsx",
			file_name="Stock_Balance_Horizontal.xlsx",
		)
		with (
			patch.object(stock_balance, "_build_horizontal_workbook_content", return_value=b"xlsx"),
			patch.object(stock_balance.frappe, "get_doc", return_value=file_doc) as get_doc,
			patch.object(stock_balance, "_set_horizontal_export_status") as set_status,
			patch.object(stock_balance.frappe.db, "commit") as commit,
			patch.object(stock_balance.frappe, "publish_realtime") as publish,
		):
			set_status.side_effect = lambda request_id, user, status, **values: {
				"request_id": request_id,
				"status": status,
				**values,
			}
			result = stock_balance.generate_horizontal_stock_balance_export(
				{"from_date": "2026-08-01", "to_date": "2026-08-31"},
				"request123",
				"user@example.com",
			)

		get_doc.assert_called_once_with(
			{
				"doctype": "File",
				"file_name": "Stock_Balance_Horizontal_2026-08-01_to_2026-08-31.xlsx",
				"content": b"xlsx",
				"is_private": 1,
			}
		)
		file_doc.save.assert_called_once_with(ignore_permissions=True)
		commit.assert_called_once_with()
		self.assertEqual(
			set_status.call_args_list,
			[
				call("request123", "user@example.com", "running"),
				call(
					"request123",
					"user@example.com",
					"ready",
					file_url=file_doc.file_url,
					file_name=file_doc.file_name,
				),
			],
		)
		publish.assert_called_once_with(
			stock_balance.HORIZONTAL_EXPORT_EVENT,
			result,
			user="user@example.com",
		)

	def test_workbook_content_is_returned_as_bytes(self):
		workbook = MagicMock()
		workbook.save.side_effect = lambda output: output.write(b"xlsx-content")
		with (
			patch.object(stock_balance, "execute", return_value=([], [{"item": "ITEM-1"}])),
			patch.object(stock_balance, "build_horizontal_stock_balance_data", return_value={"tables": []}),
			patch.object(stock_balance, "make_horizontal_stock_balance_workbook", return_value=workbook),
		):
			content = stock_balance._build_horizontal_workbook_content(frappe._dict())

		self.assertEqual(content, b"xlsx-content")
