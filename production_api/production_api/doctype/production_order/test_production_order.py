# Copyright (c) 2025, Essdee and Contributors
# See license.txt

from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe
from frappe import _dict

from production_api.production_api.doctype.production_order import production_order
from production_api.production_api.doctype.production_order.production_order import (
	STATUS_APPROVAL_REQUIRED_STATUSES,
	STATUS_CHANGE_LOCKED_STATUSES,
	TRANSFER_TARGET_STATUSES,
	get_quantity_ratio_changes,
	validate_size_quantities,
)


class TestProductionOrder(TestCase):
	def test_quantity_ratio_change_details_keep_rows_unchanged(self):
		rows = {
			"S": _dict(quantity=10, ratio=1),
			"M": _dict(quantity=20, ratio=2),
		}

		details = get_quantity_ratio_changes(
			rows,
			{"S": 15, "M": 20},
			{"S": 1, "M": 3},
		)

		self.assertEqual(details["qty_old_total"], 30)
		self.assertEqual(details["qty_new_total"], 35)
		self.assertEqual(details["qty_changes"], [{"size": "S", "old_qty": 10, "new_qty": 15}])
		self.assertEqual(details["ratio_changes"], [{"size": "M", "old_ratio": 2, "new_ratio": 3}])
		self.assertEqual(rows["S"].quantity, 10)
		self.assertEqual(rows["M"].ratio, 2)

	def test_quantity_must_be_a_non_negative_whole_number(self):
		rows = {"S": _dict(quantity=10, ratio=1)}

		with self.assertRaises(frappe.ValidationError):
			validate_size_quantities({"S": 1.5}, rows)
		with self.assertRaises(frappe.ValidationError):
			validate_size_quantities({"S": -1}, rows)

	def test_transfer_targets_exclude_closed_and_pending_requests(self):
		self.assertEqual(TRANSFER_TARGET_STATUSES, ["Open", "Item Changed", "Not Processed"])

	def test_exceptional_statuses_require_approval(self):
		self.assertEqual(STATUS_APPROVAL_REQUIRED_STATUSES, ["Item Changed", "Not Processed"])

	def test_approved_exceptional_statuses_are_terminal(self):
		self.assertEqual(STATUS_CHANGE_LOCKED_STATUSES, ["Item Changed", "Not Processed"])
		for status in STATUS_CHANGE_LOCKED_STATUSES:
			with self.subTest(status=status):
				doc = _dict(
					docstatus=1,
					status=status,
					transferred_to_ppo=None,
					quantity_ratio_request=None,
					status_change_request=None,
				)
				doc.check_permission = MagicMock()

				with (
					patch.object(production_order, "lock_production_orders"),
					patch.object(production_order.frappe, "get_doc", return_value=doc),
					self.assertRaisesRegex(
						frappe.ValidationError,
						f"Status cannot be changed after {status} is approved",
					),
				):
					production_order.change_status("PPO-TEST", "Open", "Reopen")

	def test_update_creates_request_without_changing_rows(self):
		row = _dict(quantity=10, ratio=1)
		doc = _dict(
			docstatus=1,
			status="Open",
			production_ordered_details=[],
			production_order_details=[row],
			transferred_to_ppo=None,
			quantity_ratio_request=None,
		)
		doc.check_permission = MagicMock()
		doc.db_set = MagicMock(side_effect=lambda values: doc.update(values))

		with (
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", return_value=doc),
			patch.object(production_order, "get_quantity_approver_role", return_value="Production Manager"),
			patch.object(production_order, "get_rows_by_size", return_value={"S": row}),
			patch.object(production_order, "now_datetime", return_value="2026-07-23 12:00:00"),
			patch.object(production_order, "append_quantity_ratio_request_to_comment_log"),
		):
			result = production_order.update_quantity_and_ratio(
				"PPO-TEST",
				{"S": 15},
				{"S": 2},
				"Planning Team",
				"Increase order",
			)

		self.assertEqual(row.quantity, 10)
		self.assertEqual(row.ratio, 1)
		self.assertEqual(doc.status, "Pending Request")
		request = frappe.parse_json(doc.quantity_ratio_request)
		self.assertEqual(request["requested_quantities"], {"S": 15})
		self.assertEqual(request["requested_ratios"], {"S": 2.0})
		self.assertEqual(result["status"], "Pending Request")

	def test_approval_applies_pending_values(self):
		row = _dict(quantity=10, ratio=1)
		request = {
			"original_quantities": {"S": 10},
			"original_ratios": {"S": 1},
			"requested_quantities": {"S": 15},
			"requested_ratios": {"S": 2},
			"requested_by": "Planning Team",
			"requested_user": "requester@example.com",
			"requested_on": "2026-07-23 12:00:00",
			"reason": "Increase order",
			"previous_status": "Open",
		}
		doc = _dict(
			docstatus=1,
			status="Pending Request",
			production_ordered_details=[],
			production_order_details=[row],
			transferred_to_ppo=None,
			quantity_ratio_request=frappe.as_json(request),
			flags=_dict(),
		)
		doc.check_permission = MagicMock()
		doc.set = lambda fieldname, value: doc.update({fieldname: value})
		doc.save = MagicMock()

		with (
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", return_value=doc),
			patch.object(production_order, "get_quantity_approver_role", return_value="Production Manager"),
			patch.object(production_order.frappe, "get_roles", return_value=["Production Manager"]),
			patch.object(production_order, "get_rows_by_size", return_value={"S": row}),
			patch.object(production_order, "append_quantity_ratio_to_comment_log"),
		):
			result = production_order.approve_quantity_and_ratio("PPO-TEST")

		self.assertEqual(row.quantity, 15)
		self.assertEqual(row.ratio, 2)
		self.assertEqual(doc.status, "Open")
		self.assertIsNone(doc.quantity_ratio_request)
		self.assertTrue(doc.flags.allow_quantity_ratio_approval)
		doc.save.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(result["status"], "Open")

	def test_status_change_creates_request_without_applying_status(self):
		doc = _dict(
			docstatus=1,
			status="Open",
			transferred_to_ppo=None,
			quantity_ratio_request=None,
			status_change_request=None,
		)
		doc.check_permission = MagicMock()
		doc.db_set = MagicMock(side_effect=lambda values: doc.update(values))

		with (
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", return_value=doc),
			patch.object(production_order, "get_quantity_approver_role", return_value="Production Manager"),
			patch.object(production_order, "now_datetime", return_value="2026-07-24 12:00:00"),
			patch.object(production_order, "append_status_change_request_to_comment_log"),
		):
			result = production_order.change_status(
				"PPO-TEST",
				"Item Changed",
				"Customer selected another item",
			)

		self.assertEqual(doc.status, "Pending Request")
		request = frappe.parse_json(doc.status_change_request)
		self.assertEqual(request["previous_status"], "Open")
		self.assertEqual(request["requested_status"], "Item Changed")
		self.assertEqual(request["reason"], "Customer selected another item")
		self.assertTrue(result["approval_required"])

	def test_status_approval_applies_requested_status(self):
		request = {
			"previous_status": "Open",
			"requested_status": "Not Processed",
			"requested_user": "requester@example.com",
			"requested_on": "2026-07-24 12:00:00",
			"reason": "Order put on hold",
		}
		doc = _dict(
			docstatus=1,
			status="Pending Request",
			transferred_to_ppo=None,
			quantity_ratio_request=None,
			status_change_request=frappe.as_json(request),
			flags=_dict(),
		)
		doc.check_permission = MagicMock()
		doc.set = lambda fieldname, value: doc.update({fieldname: value})
		doc.save = MagicMock()

		with (
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", return_value=doc),
			patch.object(production_order, "get_quantity_approver_role", return_value="Production Manager"),
			patch.object(production_order.frappe, "get_roles", return_value=["Production Manager"]),
			patch.object(production_order, "append_status_change_approved_to_comment_log"),
		):
			result = production_order.approve_status_change("PPO-TEST")

		self.assertEqual(doc.status, "Not Processed")
		self.assertIsNone(doc.status_change_request)
		self.assertTrue(doc.flags.allow_status_change_approval)
		doc.save.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(result["new_status"], "Not Processed")

	def test_status_approval_requires_configured_role(self):
		with (
			patch.object(production_order, "get_quantity_approver_role", return_value="Production Manager"),
			patch.object(production_order.frappe, "get_roles", return_value=["Sales Manager"]),
			self.assertRaises(frappe.ValidationError),
		):
			production_order.approve_status_change("PPO-TEST")

	def test_transfer_request_does_not_change_destination_quantity(self):
		source_row = _dict(quantity=5, ratio=1)
		target_row = _dict(quantity=10, ratio=3)
		source = _dict(
			name="PPO-SOURCE",
			item="SOURCE-ITEM",
			docstatus=1,
			status="Item Changed",
			production_ordered_details=[],
			production_order_details=[source_row],
			transferred_to_ppo=None,
			transferred_on=None,
			incoming_quantity_transfer_request=None,
		)
		target = _dict(
			name="PPO-TARGET",
			item="TARGET-ITEM",
			docstatus=1,
			status="Open",
			production_order_details=[target_row],
			transferred_to_ppo=None,
			incoming_quantity_transfer_request=None,
			flags=_dict(),
		)
		source.check_permission = MagicMock()
		target.check_permission = MagicMock()
		source.db_set = MagicMock(
			side_effect=lambda fieldname, value: source.update({fieldname: value}))
		target.db_set = MagicMock(
			side_effect=lambda fieldname, value=None: target.update(
				fieldname if isinstance(fieldname, dict) else {fieldname: value}))

		with (
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", side_effect=[source, target]),
			patch.object(production_order.frappe.db, "exists", return_value=True),
			patch.object(production_order, "has_transfer_marker_field", return_value=True),
			patch.object(production_order, "has_incoming_transfer_request_field", return_value=True),
			patch.object(production_order, "get_alternative_items", return_value=["TARGET-ITEM"]),
			patch.object(production_order, "get_quantity_approver_role", return_value="Production Manager"),
			patch.object(production_order, "get_transfer_quantities", return_value={"S": 5}),
			patch.object(production_order, "get_rows_by_size", return_value={"S": target_row}),
			patch.object(production_order, "now_datetime", return_value="2026-07-23 12:00:00"),
			patch.object(production_order, "append_transfer_request_logs"),
		):
			result = production_order.transfer_quantity_to_ppo(
				"PPO-SOURCE",
				"PPO-TARGET",
				"Move to alternative",
			)

		self.assertEqual(target_row.quantity, 10)
		self.assertEqual(target_row.ratio, 3)
		self.assertEqual(target.status, "Pending Request")
		self.assertEqual(source.transferred_to_ppo, "PPO-TARGET")
		self.assertIsNone(source.transferred_on)
		request = frappe.parse_json(target.incoming_quantity_transfer_request)
		self.assertEqual(request["target_previous_status"], "Open")
		self.assertEqual(request["transfers"], {"S": 5})
		self.assertEqual(request["target_original_quantities"], {"S": 10.0})
		self.assertEqual(result["status"], "Pending Approval")

	def test_destination_approval_applies_transfer_quantity(self):
		target_row = _dict(quantity=10, ratio=3)
		request = {
			"source_production_order": "PPO-SOURCE",
			"source_status": "Item Changed",
			"target_previous_status": "Open",
			"transfers": {"S": 5},
			"target_original_quantities": {"S": 10},
			"requested_user": "requester@example.com",
			"requested_on": "2026-07-24 12:00:00",
			"reason": "Move to alternative",
		}
		target = _dict(
			name="PPO-TARGET",
			item="TARGET-ITEM",
			docstatus=1,
			status="Pending Request",
			production_order_details=[target_row],
			transferred_to_ppo=None,
			incoming_quantity_transfer_request=frappe.as_json(request),
			flags=_dict(),
		)
		source = _dict(
			name="PPO-SOURCE",
			item="SOURCE-ITEM",
			docstatus=1,
			status="Item Changed",
			transferred_to_ppo="PPO-TARGET",
			transferred_on=None,
		)
		target.check_permission = MagicMock()
		target.set = lambda fieldname, value: target.update({fieldname: value})
		target.save = MagicMock()
		source.db_set = MagicMock(
			side_effect=lambda fieldname, value: source.update({fieldname: value}))

		with (
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", side_effect=[target, target, source]),
			patch.object(production_order, "get_quantity_approver_role", return_value="Production Manager"),
			patch.object(production_order.frappe, "get_roles", return_value=["Production Manager"]),
			patch.object(production_order, "get_alternative_items", return_value=["TARGET-ITEM"]),
			patch.object(production_order, "get_rows_by_size", return_value={"S": target_row}),
			patch.object(production_order, "now_datetime", return_value="2026-07-24 12:30:00"),
			patch.object(production_order, "append_transfer_approval_logs"),
		):
			result = production_order.approve_quantity_transfer("PPO-TARGET")

		self.assertEqual(target_row.quantity, 15)
		self.assertEqual(target_row.ratio, 3)
		self.assertEqual(target.status, "Open")
		self.assertIsNone(target.incoming_quantity_transfer_request)
		self.assertTrue(target.flags.allow_quantity_transfer)
		self.assertTrue(target.flags.allow_quantity_transfer_approval)
		target.save.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(source.transferred_on, "2026-07-24 12:30:00")
		self.assertEqual(result["transferred"], {"S": 5.0})
