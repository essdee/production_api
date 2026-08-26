# Copyright (c) 2025, Essdee and Contributors
# See license.txt

from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe
from frappe import _dict

from production_api.production_api.doctype.production_order import production_order
from production_api.production_api.doctype.production_order.production_order import (
	PPO_DRAFT_STATUS,
	PPO_REQUEST_STATUS,
	STATUS_APPROVAL_REQUIRED_STATUSES,
	STATUS_CHANGE_LOCKED_STATUSES,
	TRANSFER_TARGET_STATUSES,
	get_quantity_ratio_changes,
	validate_size_quantities,
)


class TestProductionOrder(TestCase):
	def test_transfer_comment_cleanup_preserves_other_audit_blocks(self):
		from production_api.patches.v1_0.remove_ppo_quantity_transfer_comment_logs import (
			remove_quantity_transfer_comment_blocks,
		)

		comment_log = "\n".join([
			"[06-08-2026] PPO Approved and Submitted - merch@example.com",
			"Requested By: sales@example.com",
			"[06-08-2026] Quantity Transfer Requested - sales@example.com",
			"To Production Order: PPO-TARGET",
			"Quantity 75 cm: 100 + 10 -> 110",
			"Reason: Convert item",
			"[06-08-2026] Quantity Transfer Approved - merch@example.com",
			"To Production Order: PPO-TARGET",
			"Quantity 75 cm: 100 + 10 -> 110",
			"[06-08-2026] Status Change Approved - merch@example.com",
			"Status: Open -> Item Changed",
		])

		cleaned = remove_quantity_transfer_comment_blocks(comment_log)

		self.assertNotIn("Quantity Transfer", cleaned)
		self.assertIn("PPO Approved and Submitted", cleaned)
		self.assertIn("Status Change Approved", cleaned)

	def test_list_view_shows_ppo_request_instead_of_generic_draft(self):
		list_source = Path(
			frappe.get_app_path(
				"production_api",
				"production_api",
				"doctype",
				"production_order",
				"production_order_list.js",
			)
		).read_text()
		self.assertIn("has_indicator_for_draft: true", list_source)
		self.assertIn('doc.docstatus === 0 && doc.status === "PPO Request"', list_source)
		self.assertIn('return [__("PPO Request"), "orange"', list_source)

	def test_ppo_request_form_stays_editable(self):
		form_source = Path(
			frappe.get_app_path(
				"production_api",
				"production_api",
				"doctype",
				"production_order",
				"production_order.js",
			)
		).read_text()
		self.assertNotIn('frm.doc.status !== "PPO Request"', form_source)
		self.assertNotIn("frm.disable_save()", form_source)

	def test_sales_user_can_request_ppo_approval(self):
		doc = _dict(
			name="PPO-TEST",
			docstatus=0,
			status=PPO_DRAFT_STATUS,
			comment_log=None,
			delivery_date="2026-08-20",
		)
		doc.check_permission = MagicMock()
		doc.db_set = MagicMock(side_effect=lambda values: doc.update(values))

		with (
			patch.object(production_order, "require_ppo_action_role"),
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", return_value=doc),
			patch.object(production_order.frappe, "get_roles", return_value=["Sales User"]),
			patch.object(production_order.frappe, "session", _dict(user="sales@example.com")),
			patch.object(production_order.frappe.utils, "nowdate", return_value="2026-08-05"),
			patch.object(production_order, "now_datetime", return_value="2026-08-05 17:00:00"),
			patch.object(production_order, "validate_ppo_request_readiness") as validate_readiness,
			patch.object(production_order, "append_ppo_request_to_comment_log"),
		):
			result = production_order.request_ppo_approval("PPO-TEST")

		self.assertEqual(doc.status, PPO_REQUEST_STATUS)
		self.assertEqual(doc.ppo_requested_by, "sales@example.com")
		self.assertEqual(doc.posting_date, "2026-08-05")
		self.assertEqual(doc.lead_time_given, 15)
		self.assertEqual(result["status"], PPO_REQUEST_STATUS)
		doc.check_permission.assert_called_once_with("write")
		validate_readiness.assert_called_once()

	def test_user_without_configured_action_role_cannot_request_ppo_approval(self):
		with (
			patch.object(production_order, "get_ppo_action_roles", return_value={"Sales User", "Sales Manager"}),
			patch.object(production_order, "get_ppo_approver_roles", return_value={"Merch User", "Merch Manager"}),
			patch.object(production_order.frappe, "get_roles", return_value=["Merch User"]),
			self.assertRaisesRegex(frappe.ValidationError, "configured Production Order Action Role"),
		):
			production_order.require_ppo_action_role()

	def test_configured_action_role_is_allowed(self):
		with (
			patch.object(production_order, "get_ppo_action_roles", return_value={"Sales User", "Sales Manager"}),
			patch.object(production_order, "get_ppo_approver_roles", return_value={"Merch User", "Merch Manager"}),
			patch.object(production_order.frappe, "get_roles", return_value=["Sales Manager"]),
		):
			production_order.require_ppo_action_role()

	def test_configured_action_role_is_allowed_with_merch_approver_role(self):
		with (
			patch.object(production_order, "get_ppo_action_roles", return_value={"Sales User", "Sales Manager"}),
			patch.object(production_order.frappe, "get_roles", return_value=["Merch Manager", "Sales Manager"]),
		):
			production_order.require_ppo_action_role()

	def test_system_manager_is_allowed_without_configured_action_roles(self):
		with (
			patch.object(production_order, "get_ppo_action_roles", return_value=set()),
			patch.object(production_order.frappe, "get_roles", return_value=["System Manager"]),
		):
			production_order.require_ppo_action_role()
			self.assertTrue(production_order.user_can_manage_production_order())

	def test_ppo_request_requires_a_submitted_production_term(self):
		doc = _dict(
			production_term=None,
			posting_date="2026-08-05",
			delivery_date="2026-08-10",
			dont_deliver_after="2026-08-15",
		)
		doc._validate_mandatory = MagicMock()
		doc.flags = _dict(ignore_links=True)

		with self.assertRaisesRegex(frappe.ValidationError, "Production Term is required"):
			production_order.validate_ppo_request_readiness(doc)

		doc.production_term = "TERM-TEST"
		with (
			patch.object(production_order.frappe, "get_value", return_value=0),
			self.assertRaisesRegex(frappe.ValidationError, "must be submitted"),
		):
			production_order.validate_ppo_request_readiness(doc)

	def test_ppo_request_runs_submission_date_validation(self):
		doc = _dict(
			production_term="TERM-TEST",
			posting_date="2026-08-05",
			delivery_date="2026-08-04",
			dont_deliver_after="2026-08-15",
		)
		doc._validate_mandatory = MagicMock()
		doc.flags = _dict(ignore_links=True)

		with (
			patch.object(production_order.frappe, "get_value", return_value=1),
			self.assertRaisesRegex(frappe.ValidationError, "Delivery date is less than Posting Date"),
		):
			production_order.validate_ppo_request_readiness(doc)

	def test_ppo_request_link_validation_does_not_require_save_action(self):
		doc = _dict(flags=_dict(ignore_links=False), meta=_dict(is_submittable=True))
		doc.get_invalid_links = MagicMock(return_value=([], []))
		doc.get_all_children = MagicMock(return_value=[])

		production_order.validate_ppo_request_links(doc)

		doc.get_invalid_links.assert_called_once_with()

	def test_merch_user_can_approve_and_submit_ppo(self):
		doc = _dict(
			name="PPO-TEST",
			docstatus=0,
			status=PPO_REQUEST_STATUS,
			flags=_dict(),
		)

		def submit():
			doc.docstatus = 1
			doc.status = "Open"

		doc.submit = MagicMock(side_effect=submit)

		with (
			patch.object(production_order, "get_ppo_approver_roles", return_value={"Merch User", "Merch Manager"}),
			patch.object(production_order.frappe, "get_roles", return_value=["Merch User"]),
			patch.object(production_order.frappe, "session", _dict(user="merch@example.com")),
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", return_value=doc),
			patch.object(production_order, "append_ppo_approval_to_comment_log"),
		):
			result = production_order.approve_ppo("PPO-TEST")

		self.assertTrue(doc.flags.ignore_permissions)
		self.assertTrue(doc.flags.allow_ppo_approval)
		doc.submit.assert_called_once_with()
		self.assertEqual(result["docstatus"], 1)
		self.assertEqual(result["status"], "Open")

	def test_sales_user_cannot_approve_ppo(self):
		with (
			patch.object(production_order, "get_ppo_approver_roles", return_value={"Merch User", "Merch Manager"}),
			patch.object(production_order.frappe, "get_roles", return_value=["Sales User"]),
			self.assertRaisesRegex(frappe.ValidationError, "Only users with the configured Merch"),
		):
			production_order.approve_ppo("PPO-TEST")

	def test_merch_user_can_return_ppo_to_sales_with_comment(self):
		doc = _dict(
			name="PPO-TEST",
			docstatus=0,
			status=PPO_REQUEST_STATUS,
			ppo_requested_by="sales@example.com",
			ppo_requested_on="2026-08-05 17:00:00",
		)
		doc.db_set = MagicMock(side_effect=lambda values: doc.update(values))

		with (
			patch.object(production_order, "get_ppo_approver_roles", return_value={"Merch Manager"}),
			patch.object(production_order.frappe, "get_roles", return_value=["Merch Manager"]),
			patch.object(production_order.frappe, "session", _dict(user="merch@example.com")),
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", return_value=doc),
			patch.object(production_order, "append_ppo_changes_requested_to_comment_log") as append_log,
		):
			result = production_order.request_ppo_changes("PPO-TEST", "Correct the production term")

		self.assertEqual(doc.status, PPO_DRAFT_STATUS)
		self.assertIsNone(doc.ppo_requested_by)
		self.assertEqual(result["status"], PPO_DRAFT_STATUS)
		append_log.assert_called_once_with(doc, "Correct the production term", "sales@example.com")

	def test_requesting_ppo_changes_requires_a_comment(self):
		with (
			patch.object(production_order, "get_ppo_approver_roles", return_value={"Merch Manager"}),
			patch.object(production_order.frappe, "get_roles", return_value=["Merch Manager"]),
			self.assertRaisesRegex(frappe.ValidationError, "Reason is required"),
		):
			production_order.request_ppo_changes("PPO-TEST", "  ")

	def test_direct_submit_requires_ppo_request_and_merch_role(self):
		doc = _dict(status=PPO_DRAFT_STATUS)
		with (
			patch.object(production_order, "get_ppo_approver_roles", return_value={"Merch User", "Merch Manager"}),
			patch.object(production_order.frappe, "get_roles", return_value=["Merch Manager"]),
			self.assertRaisesRegex(frappe.ValidationError, "Send the Production Order for PPO approval"),
		):
			production_order.ProductionOrder.validate_ppo_submission(doc)

		doc.status = PPO_REQUEST_STATUS
		with (
			patch.object(production_order, "get_ppo_approver_roles", return_value={"Merch User", "Merch Manager"}),
			patch.object(production_order.frappe, "get_roles", return_value=["Sales Manager"]),
			self.assertRaisesRegex(frappe.ValidationError, "Only users with the configured Merch"),
		):
			production_order.ProductionOrder.validate_ppo_submission(doc)

	def test_ppo_request_status_cannot_be_spoofed(self):
		doc = _dict(
			docstatus=0,
			status=PPO_REQUEST_STATUS,
			flags=_dict(),
		)
		doc.get_doc_before_save = MagicMock(
			return_value=_dict(status=PPO_DRAFT_STATUS)
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Use the Request PPO Approval button"):
			production_order.ProductionOrder.validate_ppo_approval_state(doc)

	def test_ppo_request_can_be_edited_while_approval_is_pending(self):
		doc = _dict(
			docstatus=0,
			status=PPO_REQUEST_STATUS,
			flags=_dict(),
			production_term="Updated Term",
			delivery_date="2026-09-15",
			comments="Updated while awaiting approval",
		)
		doc.get_doc_before_save = MagicMock(
			return_value=_dict(
				status=PPO_REQUEST_STATUS,
				production_term="Original Term",
				delivery_date="2026-09-10",
				comments="Original comment",
			)
		)

		production_order.ProductionOrder.validate_ppo_approval_state(doc)

		self.assertEqual(doc.status, PPO_REQUEST_STATUS)

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
					patch.object(production_order, "require_ppo_action_role"),
					patch.object(production_order, "lock_production_orders"),
					patch.object(production_order.frappe, "get_doc", return_value=doc),
					patch.object(production_order, "get_linked_lots", return_value=[]),
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
			patch.object(production_order, "require_ppo_action_role"),
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
			patch.object(production_order, "require_ppo_action_role"),
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
			patch.object(production_order, "require_ppo_action_role"),
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", return_value=doc),
			patch.object(production_order, "get_linked_lots", return_value=[]),
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

	def test_status_change_is_blocked_when_lot_is_linked(self):
		doc = _dict(
			docstatus=1,
			status="Open",
			transferred_to_ppo=None,
			quantity_ratio_request=None,
			status_change_request=None,
		)
		doc.check_permission = MagicMock()

		with (
			patch.object(production_order, "require_ppo_action_role"),
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", return_value=doc),
			patch.object(production_order, "get_linked_lots", return_value=["LOT-TEST"]),
			self.assertRaisesRegex(
				frappe.ValidationError,
				"Status cannot be changed.*LOT-TEST",
			),
		):
			production_order.change_status(
				"PPO-TEST",
				"Item Changed",
				"Customer selected another item",
			)

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
			patch.object(production_order, "get_linked_lots", return_value=[]),
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

	def test_status_approval_is_blocked_if_lot_was_linked_after_request(self):
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
		)
		doc.check_permission = MagicMock()

		with (
			patch.object(production_order, "lock_production_orders"),
			patch.object(production_order.frappe, "get_doc", return_value=doc),
			patch.object(production_order, "get_linked_lots", return_value=["LOT-TEST"]),
			patch.object(production_order, "get_quantity_approver_role", return_value="Production Manager"),
			patch.object(production_order.frappe, "get_roles", return_value=["Production Manager"]),
			self.assertRaisesRegex(
				frappe.ValidationError,
				"Status cannot be approved.*LOT-TEST",
			),
		):
			production_order.approve_status_change("PPO-TEST")

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
			patch.object(production_order, "require_ppo_action_role"),
			patch.object(production_order, "lock_production_orders"),
			patch.object(
				production_order.frappe,
				"get_doc",
				side_effect=lambda _doctype, name: (
					source if name == source.name else target
				),
			),
			patch.object(production_order.frappe.db, "exists", return_value=True),
			patch.object(production_order, "has_transfer_marker_field", return_value=True),
			patch.object(production_order, "has_incoming_transfer_request_field", return_value=True),
			patch.object(production_order, "get_alternative_items", return_value=["TARGET-ITEM"]),
			patch.object(production_order, "get_quantity_approver_role", return_value="Production Manager"),
			patch.object(production_order, "get_transfer_quantities", return_value={"S": 5}),
			patch.object(production_order, "get_rows_by_size", return_value={"S": target_row}),
			patch.object(production_order, "now_datetime", return_value="2026-07-23 12:00:00"),
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
		self.assertTrue(request["transfer_reference"])
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
			patch.object(production_order, "append_quantity_transfer_history") as append_history,
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
		append_history.assert_called_once()

	def test_transfer_history_builds_reduced_and_added_rows(self):
		source = _dict(name="PPO-SOURCE")
		target = _dict(name="PPO-TARGET")
		changes = [{"size": "S", "qty": 5, "old_qty": 10, "new_qty": 15}]
		request = {
			"transfer_reference": "TRANSFER-1",
			"requested_user": "requester@example.com",
			"requested_on": "2026-07-24 12:00:00",
			"reason": "Move to alternative",
		}

		with patch.object(
			production_order,
			"get_rows_by_size",
			return_value={"S": _dict(quantity=5)},
		):
			source_rows, target_rows = production_order.build_quantity_transfer_history_rows(
				source,
				target,
				changes,
				request,
				"approver@example.com",
				"2026-07-24 12:30:00",
			)

		self.assertEqual(source_rows[0]["movement"], "Reduced")
		self.assertEqual(source_rows[0]["counterpart_production_order"], "PPO-TARGET")
		self.assertEqual(source_rows[0]["quantity_before"], 5)
		self.assertEqual(source_rows[0]["quantity_after"], 0)
		self.assertEqual(target_rows[0]["movement"], "Added")
		self.assertEqual(target_rows[0]["counterpart_production_order"], "PPO-SOURCE")
		self.assertEqual(target_rows[0]["quantity_before"], 10)
		self.assertEqual(target_rows[0]["quantity_after"], 15)
		self.assertEqual(target_rows[0]["transfer_reference"], "TRANSFER-1")

	def test_alternative_plan_converts_pieces_with_each_lots_packing_combo(self):
		source_row = _dict(quantity=100, ratio=1)
		target_row = _dict(quantity=10, ratio=1)
		source = _dict(
			name="PPO-SOURCE",
			item="SOURCE-ITEM",
			docstatus=1,
			status="Open",
			flags=_dict(),
		)
		target = _dict(
			name="PPO-TARGET",
			item="TARGET-ITEM",
			docstatus=1,
			status="Open",
			flags=_dict(),
		)
		source.save = MagicMock()
		target.save = MagicMock()

		def get_lot_ppo(_doctype, lot, _fieldname):
			return {
				"LOT-SOURCE": "PPO-SOURCE",
				"LOT-TARGET": "PPO-TARGET",
			}[lot]

		with (
			patch.object(production_order, "lock_production_orders"),
			patch.object(
				production_order,
				"_get_lot_packing_combo",
				side_effect=[10, 5],
			),
			patch.object(production_order.frappe, "get_doc", side_effect=[source, target]),
			patch.object(production_order.frappe.db, "get_value", side_effect=get_lot_ppo),
			patch.object(production_order, "get_alternative_items", return_value=["TARGET-ITEM"]),
			patch.object(
				production_order,
				"get_rows_by_size",
				side_effect=lambda doc: {"S": source_row} if doc.name == source.name else {"S": target_row},
			),
			patch.object(production_order, "now_datetime", return_value="2026-08-06 14:00:00"),
			patch.object(production_order.frappe, "generate_hash", return_value="ALT-TRANSFER"),
			patch.object(production_order.frappe, "session", _dict(user="planner@example.com")),
			patch.object(production_order, "append_quantity_transfer_history") as append_history,
		):
			result = production_order.apply_alternative_plan_ppo_transfer(
				"PPO-SOURCE",
				"PPO-TARGET",
				"LOT-SOURCE",
				"LOT-TARGET",
				{"S": 20},
				"Alternative conversion",
			)

		self.assertEqual(source_row.quantity, 98)
		self.assertEqual(target_row.quantity, 14)
		self.assertTrue(source.flags.allow_quantity_transfer)
		self.assertTrue(target.flags.allow_quantity_transfer)
		source.save.assert_called_once_with(ignore_permissions=True)
		target.save.assert_called_once_with(ignore_permissions=True)
		changes = append_history.call_args.args[2]
		self.assertEqual(changes[0]["piece_qty"], 20)
		self.assertEqual(changes[0]["source_qty"], 2)
		self.assertEqual(changes[0]["target_qty"], 4)
		self.assertEqual(changes[0]["source_old_qty"], 100)
		self.assertEqual(changes[0]["source_new_qty"], 98)
		self.assertEqual(changes[0]["old_qty"], 10)
		self.assertEqual(changes[0]["new_qty"], 14)
		self.assertEqual(result["transferred"], {"S": 20.0})
		self.assertEqual(result["source_boxes"], {"S": 2.0})
		self.assertEqual(result["target_boxes"], {"S": 4.0})

	def test_piece_transfer_conversion_example_uses_source_and_target_combos(self):
		pieces = {"75 cm": 300, "80 cm": 800}

		self.assertEqual(
			production_order._piece_transfers_to_boxes(pieces, 10),
			{"75 cm": 30.0, "80 cm": 80.0},
		)
		self.assertEqual(
			production_order._piece_transfers_to_boxes(pieces, 5),
			{"75 cm": 60.0, "80 cm": 160.0},
		)

	def test_alternative_plan_excess_pieces_clamp_source_ppo_at_zero(self):
		source_row = _dict(quantity=10, ratio=1)
		target_row = _dict(quantity=0, ratio=1)
		source = _dict(
			name="PPO-SOURCE",
			item="SOURCE-ITEM",
			docstatus=1,
			status="Open",
			flags=_dict(),
		)
		target = _dict(
			name="PPO-TARGET",
			item="TARGET-ITEM",
			docstatus=1,
			status="Open",
			flags=_dict(),
		)
		source.save = MagicMock()
		target.save = MagicMock()

		def get_lot_ppo(_doctype, lot, _fieldname):
			return {
				"LOT-SOURCE": "PPO-SOURCE",
				"LOT-TARGET": "PPO-TARGET",
			}[lot]

		with (
			patch.object(production_order, "lock_production_orders"),
			patch.object(
				production_order,
				"_get_lot_packing_combo",
				side_effect=[10, 5],
			),
			patch.object(production_order.frappe, "get_doc", side_effect=[source, target]),
			patch.object(production_order.frappe.db, "get_value", side_effect=get_lot_ppo),
			patch.object(production_order, "get_alternative_items", return_value=["TARGET-ITEM"]),
			patch.object(
				production_order,
				"get_rows_by_size",
				side_effect=lambda doc: {"S": source_row} if doc.name == source.name else {"S": target_row},
			),
			patch.object(production_order, "now_datetime", return_value="2026-08-07 14:00:00"),
			patch.object(production_order.frappe, "generate_hash", return_value="EXCESS-TRANSFER"),
			patch.object(production_order.frappe, "session", _dict(user="planner@example.com")),
			patch.object(production_order, "append_quantity_transfer_history") as append_history,
		):
			result = production_order.apply_alternative_plan_ppo_transfer(
				"PPO-SOURCE",
				"PPO-TARGET",
				"LOT-SOURCE",
				"LOT-TARGET",
				{"S": 120},
				"Alternative conversion with cutting excess",
			)

		self.assertEqual(source_row.quantity, 0)
		self.assertEqual(target_row.quantity, 24)
		changes = append_history.call_args.args[2]
		self.assertEqual(changes[0]["piece_qty"], 120)
		self.assertEqual(changes[0]["source_requested_qty"], 12)
		self.assertEqual(changes[0]["source_qty"], 10)
		self.assertEqual(changes[0]["target_qty"], 24)
		self.assertEqual(changes[0]["source_new_qty"], 0)
		self.assertEqual(result["transferred"], {"S": 120.0})
		self.assertEqual(result["requested_source_boxes"], {"S": 12.0})
		self.assertEqual(result["source_boxes"], {"S": 10.0})
		self.assertEqual(result["target_boxes"], {"S": 24.0})

	def test_transfer_history_uses_actual_reduced_source_values(self):
		source = _dict(name="PPO-SOURCE")
		target = _dict(name="PPO-TARGET")
		request = {
			"transfer_reference": "ALT-TRANSFER",
			"requested_user": "planner@example.com",
			"requested_on": "2026-08-06 14:00:00",
			"reason": "Alternative conversion",
		}
		changes = [{
			"size": "S",
			"qty": 60,
			"source_qty": 30,
			"target_qty": 60,
			"old_qty": 0,
			"new_qty": 60,
			"source_old_qty": 500,
			"source_new_qty": 470,
		}]

		with patch.object(
			production_order,
			"get_rows_by_size",
			return_value={"S": _dict(quantity=470)},
		):
			source_rows, target_rows = production_order.build_quantity_transfer_history_rows(
				source,
				target,
				changes,
				request,
				"planner@example.com",
				"2026-08-06 14:00:00",
			)

		self.assertEqual(source_rows[0]["movement"], "Reduced")
		self.assertEqual(source_rows[0]["quantity"], 30)
		self.assertEqual(source_rows[0]["quantity_before"], 500)
		self.assertEqual(source_rows[0]["quantity_after"], 470)
		self.assertEqual(target_rows[0]["movement"], "Added")
		self.assertEqual(target_rows[0]["quantity"], 60)
		self.assertEqual(target_rows[0]["quantity_before"], 0)
		self.assertEqual(target_rows[0]["quantity_after"], 60)
