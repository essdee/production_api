import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe


STATUS_JSON = (
	Path(__file__).parent
	/ "production_api"
	/ "doctype"
	/ "purchase_order"
	/ "purchase_order.json"
)


class TestPurchaseOrderApprovalState(TestCase):
	def _doc(self, *variants, status="Draft", docstatus=0):
		return frappe._dict(
			{
				"doctype": "Purchase Order",
				"name": "PO-TEST",
				"docstatus": docstatus,
				"status": status,
				"flags": frappe._dict(),
				"items": [frappe._dict({"item_variant": variant}) for variant in variants],
			}
		)

	def _item_lookup(self, groups):
		def get_all(doctype, filters=None, fields=None, limit_page_length=None):
			self.assertEqual(limit_page_length, 0)
			if doctype == "Item Variant":
				return [
					frappe._dict({"name": variant, "item": f"ITEM-{variant}"})
					for variant in filters["name"][1]
				]
			if doctype == "Item":
				return [
					frappe._dict({"name": item, "item_group": groups[item]})
					for item in filters["name"][1]
				]
			raise AssertionError(f"Unexpected lookup: {doctype}")

		return get_all

	def test_status_options_include_pending_approval_once(self):
		with STATUS_JSON.open() as source:
			metadata = json.load(source)
		status_field = next(field for field in metadata["fields"] if field["fieldname"] == "status")
		self.assertEqual(status_field["options"].splitlines().count("Pending Approval"), 1)

	def test_mixed_rows_trigger_on_one_exact_purchase_yarn_item(self):
		from production_api.purchase_order_approval import requires_yarn_approval

		groups = {
			"ITEM-IV-CLOTH": "Purchase - Fabric",
			"ITEM-IV-YARN": "Purchase - Yarn",
		}
		with patch("production_api.purchase_order_approval.frappe.get_all", side_effect=self._item_lookup(groups)):
			self.assertTrue(requires_yarn_approval(self._doc("IV-CLOTH", "IV-YARN")))

	def test_empty_rows_do_not_trigger(self):
		from production_api.purchase_order_approval import requires_yarn_approval

		with patch("production_api.purchase_order_approval.frappe.get_all") as get_all:
			self.assertFalse(requires_yarn_approval(self._doc()))
		get_all.assert_not_called()

	def test_child_and_similarly_named_groups_do_not_trigger(self):
		from production_api.purchase_order_approval import requires_yarn_approval

		groups = {
			"ITEM-IV-CHILD": "Purchase - Yarn / Dyed",
			"ITEM-IV-SIMILAR": "Purchase Yarn",
		}
		with patch("production_api.purchase_order_approval.frappe.get_all", side_effect=self._item_lookup(groups)):
			self.assertFalse(requires_yarn_approval(self._doc("IV-CHILD", "IV-SIMILAR")))

	def test_draft_save_sets_pending_approval(self):
		from production_api.purchase_order_approval import apply_draft_approval_status

		doc = self._doc("IV-YARN")
		with patch("production_api.purchase_order_approval.get_live_request", return_value=None), patch(
			"production_api.purchase_order_approval.requires_yarn_approval", return_value=True
		):
			apply_draft_approval_status(doc)
		self.assertEqual(doc.status, "Pending Approval")

	def test_non_yarn_draft_retains_controller_status(self):
		from production_api.purchase_order_approval import apply_draft_approval_status

		doc = self._doc("IV-CLOTH")
		with patch("production_api.purchase_order_approval.get_live_request", return_value=None), patch(
			"production_api.purchase_order_approval.requires_yarn_approval", return_value=False
		):
			apply_draft_approval_status(doc)
		self.assertEqual(doc.status, "Draft")

	def test_pending_approval_returns_to_draft_when_last_yarn_item_is_removed(self):
		from production_api.purchase_order_approval import apply_draft_approval_status

		doc = self._doc("IV-CLOTH", status="Pending Approval")
		with patch("production_api.purchase_order_approval.get_live_request", return_value=None), patch(
			"production_api.purchase_order_approval.requires_yarn_approval", return_value=False
		):
			apply_draft_approval_status(doc)
		self.assertEqual(doc.status, "Draft")

	def test_rejection_flag_preserves_draft_once(self):
		from production_api.purchase_order_approval import apply_draft_approval_status

		doc = self._doc("IV-YARN")
		doc.flags.purchase_order_approval_rejection = True
		with patch("production_api.purchase_order_approval.requires_yarn_approval") as requires:
			apply_draft_approval_status(doc)
		self.assertEqual(doc.status, "Draft")
		requires.assert_not_called()

	def test_submitted_document_is_not_reclassified(self):
		from production_api.purchase_order_approval import apply_draft_approval_status

		doc = self._doc("IV-YARN", status="Ordered", docstatus=1)
		with patch("production_api.purchase_order_approval.requires_yarn_approval") as requires:
			apply_draft_approval_status(doc)
		self.assertEqual(doc.status, "Ordered")
		requires.assert_not_called()


class TestPurchaseOrderApprovalTransitions(TestCase):
	def _call(self, method, *args):
		return getattr(method, "__wrapped__", method)(*args)

	def _doc(self, status="Pending Approval", docstatus=0):
		doc = Mock()
		doc.doctype = "Purchase Order"
		doc.name = "PO-TEST"
		doc.status = status
		doc.docstatus = docstatus
		doc.flags = frappe._dict()
		doc.items = [frappe._dict({"item_variant": "IV-YARN"})]
		doc.get.side_effect = lambda key: getattr(doc, key)
		return doc

	def _raise(self, message, *args, **kwargs):
		raise RuntimeError(message)

	@patch("production_api.purchase_order_approval.requires_yarn_approval", return_value=True)
	@patch("production_api.purchase_order_approval.frappe.get_roles", return_value=["Purchase Manager"])
	@patch("production_api.purchase_order_approval.frappe.throw")
	def test_non_system_manager_cannot_submit_yarn_po(self, throw, get_roles, requires):
		from production_api.purchase_order_approval import validate_approval_submit

		throw.side_effect = self._raise
		with self.assertRaisesRegex(RuntimeError, "Only System Manager"):
			validate_approval_submit(self._doc())

	@patch("production_api.purchase_order_approval.requires_yarn_approval", return_value=True)
	@patch("production_api.purchase_order_approval.frappe.get_roles", return_value=["System Manager"])
	def test_system_manager_can_submit_directly_from_draft_or_pending(self, get_roles, requires):
		from production_api.purchase_order_approval import validate_approval_submit

		validate_approval_submit(self._doc(status="Draft"))
		validate_approval_submit(self._doc(status="Pending Approval"))

	@patch("production_api.purchase_order_approval.requires_yarn_approval", return_value=False)
	@patch("production_api.purchase_order_approval.frappe.get_roles", return_value=["Purchase Manager"])
	def test_non_yarn_po_keeps_existing_submit_permissions(self, get_roles, requires):
		from production_api.purchase_order_approval import validate_approval_submit

		validate_approval_submit(self._doc(status="Draft"))

	@patch("production_api.purchase_order_approval.frappe.get_roles", return_value=["Purchase Manager"])
	@patch("production_api.purchase_order_approval.frappe.throw")
	def test_wrong_role_cannot_use_desk_actions(self, throw, get_roles):
		from production_api.purchase_order_approval import approve_purchase_order, reject_purchase_order

		throw.side_effect = self._raise
		with self.assertRaisesRegex(RuntimeError, "Only System Manager"):
			self._call(approve_purchase_order, "PO-TEST")
		with self.assertRaisesRegex(RuntimeError, "Only System Manager"):
			self._call(reject_purchase_order, "PO-TEST")

	@patch("production_api.purchase_order_approval.requires_yarn_approval", return_value=True)
	@patch("production_api.purchase_order_approval.frappe.get_roles", return_value=["System Manager"])
	@patch("production_api.purchase_order_approval._get_locked_purchase_order")
	@patch("production_api.purchase_order_approval.finalize_live_request")
	def test_approve_locks_and_submits_pending_po(self, finalize, get_locked, get_roles, requires):
		from production_api.purchase_order_approval import approve_purchase_order

		doc = self._doc()

		def submit():
			doc.docstatus = 1
			doc.status = "Ordered"
			doc.approved_by = "manager@example.com"

		doc.submit.side_effect = submit
		get_locked.return_value = doc

		result = self._call(approve_purchase_order, "PO-TEST")

		get_locked.assert_called_once_with("PO-TEST")
		doc.submit.assert_called_once_with()
		self.assertEqual(doc.flags.purchase_order_approval_action, "approve")
		self.assertEqual(result["status"], "Ordered")
		self.assertEqual(result["docstatus"], 1)
		self.assertEqual(doc.approved_by, "manager@example.com")
		finalize.assert_called_once_with("PO-TEST", "Approved", "Approve PO")

	@patch("production_api.purchase_order_approval.requires_yarn_approval", return_value=True)
	@patch("production_api.purchase_order_approval.frappe.get_roles", return_value=["System Manager"])
	@patch("production_api.purchase_order_approval._get_locked_purchase_order")
	@patch("production_api.purchase_order_approval.finalize_live_request")
	def test_reject_locks_and_returns_pending_po_to_draft(self, finalize, get_locked, get_roles, requires):
		from production_api.purchase_order_approval import reject_purchase_order

		doc = self._doc()
		get_locked.return_value = doc

		result = self._call(reject_purchase_order, "PO-TEST")

		get_locked.assert_called_once_with("PO-TEST")
		doc.save.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(doc.status, "Draft")
		self.assertTrue(doc.flags.purchase_order_approval_rejection)
		self.assertEqual(result["status"], "Draft")
		finalize.assert_called_once_with("PO-TEST", "Rejected", "Reject PO")

	@patch("production_api.purchase_order_approval.requires_yarn_approval", return_value=True)
	@patch("production_api.purchase_order_approval.frappe.get_roles", return_value=["System Manager"])
	@patch("production_api.purchase_order_approval._get_locked_purchase_order")
	@patch("production_api.purchase_order_approval.frappe.throw")
	def test_out_of_order_or_repeated_action_does_not_mutate_po(
		self, throw, get_locked, get_roles, requires
	):
		from production_api.purchase_order_approval import approve_purchase_order

		throw.side_effect = self._raise
		doc = self._doc(status="Ordered", docstatus=1)
		get_locked.return_value = doc
		with self.assertRaisesRegex(RuntimeError, "Pending Approval"):
			self._call(approve_purchase_order, "PO-TEST")
		doc.submit.assert_not_called()
		doc.save.assert_not_called()

	@patch("production_api.purchase_order_approval.frappe")
	def test_locked_loader_uses_database_row_lock_before_loading(self, frappe_module):
		from production_api.purchase_order_approval import _get_locked_purchase_order

		_get_locked_purchase_order("PO-TEST")

		frappe_module.db.get_value.assert_called_once_with(
			"Purchase Order", "PO-TEST", "name", for_update=True
		)
		frappe_module.get_doc.assert_called_once_with("Purchase Order", "PO-TEST")

	@patch("production_api.purchase_order_approval.finalize_live_request")
	@patch("production_api.purchase_order_approval._in_telegram_action", return_value=False)
	def test_on_submit_preserves_desk_approve_audit_label(self, in_telegram, finalize):
		from production_api.purchase_order_approval import finalize_purchase_order_submission

		doc = self._doc(status="Ordered", docstatus=1)
		doc.flags.purchase_order_approval_action = "approve"
		finalize_purchase_order_submission(doc)
		finalize.assert_called_once_with("PO-TEST", "Approved", "Approve PO")


class TestPurchaseOrderApprovalRoute(TestCase):
	@patch("production_api.purchase_order_approval.frappe.get_cached_doc")
	def test_route_setup_reuses_process_cost_group_and_is_idempotent(self, get_cached_doc):
		from production_api.purchase_order_approval import ensure_purchase_order_approval_route

		settings = Mock()
		settings.routes = [
			frappe._dict(
				{
					"name": "PROCESS-ROUTE",
					"enabled": 1,
					"reference_doctype": "Process Cost",
					"group_chat_id": "-100123",
				}
			)
		]

		def append(fieldname, values):
			row = frappe._dict({"name": "PO-ROUTE", **values})
			settings.routes.append(row)
			return row

		settings.append.side_effect = append
		get_cached_doc.return_value = settings

		self.assertEqual(ensure_purchase_order_approval_route(), "PO-ROUTE")
		self.assertEqual(ensure_purchase_order_approval_route(), "PO-ROUTE")
		settings.append.assert_called_once()
		created = settings.routes[-1]
		self.assertEqual(created.reference_doctype, "Purchase Order")
		self.assertEqual(created.group_chat_id, "-100123")
		self.assertEqual(created.trigger_field, "status")
		self.assertEqual(created.trigger_value, "Pending Approval")
		self.assertEqual(created.approve_action, "Approve PO")
		self.assertEqual(created.reject_action, "Reject PO")
		self.assertEqual(created.approve_roles, "System Manager")
		self.assertEqual(created.reject_roles, "System Manager")

	@patch("production_api.purchase_order_approval.frappe.get_cached_doc")
	def test_route_setup_is_noop_without_process_cost_route(self, get_cached_doc):
		from production_api.purchase_order_approval import ensure_purchase_order_approval_route

		settings = Mock(routes=[])
		get_cached_doc.return_value = settings
		self.assertIsNone(ensure_purchase_order_approval_route())
		settings.append.assert_not_called()
		settings.save.assert_not_called()

	@patch("production_api.purchase_order_approval.create_and_send_approval")
	@patch("production_api.purchase_order_approval.frappe.get_doc")
	@patch("production_api.purchase_order_approval.frappe.get_cached_doc")
	@patch("production_api.purchase_order_approval.ensure_purchase_order_approval_route", return_value="PO-ROUTE")
	@patch("production_api.purchase_order_approval.get_live_request", return_value=None)
	@patch("production_api.purchase_order_approval._prepare_purchase_order_request")
	def test_explicit_send_selects_purchase_order_route(
		self, prepare, get_live, ensure_route, get_cached_doc, get_doc, create_and_send
	):
		from production_api.purchase_order_approval import send_purchase_order_request

		settings = frappe._dict(
			{
				"enabled": 1,
				"routes": [
					frappe._dict({"name": "PROCESS-ROUTE", "enabled": 1, "reference_doctype": "Process Cost"}),
					frappe._dict({"name": "PO-ROUTE", "enabled": 1, "reference_doctype": "Purchase Order"}),
				],
			}
		)
		get_cached_doc.return_value = settings
		prepare.return_value = frappe._dict(
			{"doctype": "Purchase Order", "name": "PO-0012", "status": "Pending Approval", "docstatus": 0}
		)
		create_and_send.return_value = "REQ-001"
		get_doc.return_value = frappe._dict({"name": "REQ-001", "status": "Pending", "error": None})

		method = getattr(send_purchase_order_request, "__wrapped__", send_purchase_order_request)
		result = method("PO-0012")

		ensure_route.assert_called_once_with()
		create_and_send.assert_called_once_with("Purchase Order", "PO-0012", "PO-ROUTE")
		self.assertEqual(result["request"], "REQ-001")


class TestPurchaseOrderRequestLifecycle(TestCase):
	def _call(self, method, *args):
		return getattr(method, "__wrapped__", method)(*args)

	def _doc(self):
		doc = Mock()
		doc.doctype = "Purchase Order"
		doc.name = "PO-0012"
		doc.docstatus = 0
		doc.status = "Pending Approval"
		doc.flags = frappe._dict()
		doc.items = [frappe._dict({"item_variant": "IV-YARN"})]
		doc.get.side_effect = lambda key: getattr(doc, key)
		return doc

	def _raise(self, message, *args, **kwargs):
		raise RuntimeError(message)

	@patch("production_api.purchase_order_approval.frappe.throw")
	@patch("production_api.purchase_order_approval.frappe.has_permission", return_value=False)
	def test_send_requires_create_permission(self, has_permission, throw):
		from production_api.purchase_order_approval import _require_send_permissions

		throw.side_effect = self._raise
		with self.assertRaisesRegex(RuntimeError, "create permission"):
			_require_send_permissions(self._doc())

	@patch("production_api.purchase_order_approval.frappe.has_permission", return_value=True)
	def test_send_requires_document_read_permission(self, has_permission):
		from production_api.purchase_order_approval import _require_send_permissions

		doc = self._doc()
		_require_send_permissions(doc)
		has_permission.assert_called_once_with("Purchase Order", ptype="create")
		doc.check_permission.assert_called_once_with("read")

	@patch("production_api.purchase_order_approval.frappe.throw")
	@patch("production_api.purchase_order_approval.ensure_purchase_order_approval_route", return_value=None)
	@patch("production_api.purchase_order_approval.get_live_request", return_value=None)
	@patch("production_api.purchase_order_approval._prepare_purchase_order_request")
	def test_send_fails_clearly_when_route_is_missing(self, prepare, get_live, ensure_route, throw):
		from production_api.purchase_order_approval import send_purchase_order_request

		throw.side_effect = self._raise
		prepare.return_value = self._doc()
		with self.assertRaisesRegex(RuntimeError, "Process Cost"):
			self._call(send_purchase_order_request, "PO-0012")

	@patch("production_api.purchase_order_approval.frappe.throw")
	@patch("production_api.purchase_order_approval.frappe.get_cached_doc")
	@patch("production_api.purchase_order_approval.ensure_purchase_order_approval_route", return_value="PO-ROUTE")
	@patch("production_api.purchase_order_approval.get_live_request", return_value=None)
	@patch("production_api.purchase_order_approval._prepare_purchase_order_request")
	def test_send_fails_when_telegram_is_disabled(self, prepare, get_live, ensure_route, get_settings, throw):
		from production_api.purchase_order_approval import send_purchase_order_request

		throw.side_effect = self._raise
		prepare.return_value = self._doc()
		get_settings.return_value = frappe._dict({"enabled": 0, "routes": []})
		with self.assertRaisesRegex(RuntimeError, "not enabled"):
			self._call(send_purchase_order_request, "PO-0012")

	@patch("production_api.purchase_order_approval.create_and_send_approval")
	@patch("production_api.purchase_order_approval.get_live_request")
	@patch("production_api.purchase_order_approval._prepare_purchase_order_request")
	def test_duplicate_live_request_is_reused(self, prepare, get_live, create_and_send):
		from production_api.purchase_order_approval import send_purchase_order_request

		prepare.return_value = self._doc()
		get_live.return_value = frappe._dict({"name": "REQ-LIVE", "status": "Pending"})
		result = self._call(send_purchase_order_request, "PO-0012")
		self.assertEqual(result, {"request": "REQ-LIVE", "status": "Pending", "error": None})
		create_and_send.assert_not_called()

	@patch("production_api.purchase_order_approval.frappe.get_doc")
	@patch("production_api.purchase_order_approval.create_and_send_approval", return_value="REQ-NEW")
	@patch("production_api.purchase_order_approval.frappe.get_cached_doc")
	@patch("production_api.purchase_order_approval.ensure_purchase_order_approval_route", return_value="PO-ROUTE")
	@patch("production_api.purchase_order_approval.get_live_request", return_value=None)
	@patch("production_api.purchase_order_approval._prepare_purchase_order_request")
	def test_successful_send_returns_pending_lock(
		self, prepare, get_live, ensure_route, get_settings, create_and_send, get_doc
	):
		from production_api.purchase_order_approval import send_purchase_order_request

		prepare.return_value = self._doc()
		get_settings.return_value = frappe._dict(
			{
				"enabled": 1,
				"routes": [frappe._dict({"name": "PO-ROUTE", "enabled": 1, "reference_doctype": "Purchase Order"})],
			}
		)
		get_doc.return_value = frappe._dict({"name": "REQ-NEW", "status": "Pending", "error": None})
		result = self._call(send_purchase_order_request, "PO-0012")
		self.assertEqual(result, {"request": "REQ-NEW", "status": "Pending", "error": None})

	@patch("production_api.purchase_order_approval.frappe.get_doc")
	@patch("production_api.purchase_order_approval.create_and_send_approval", side_effect=["REQ-ERR-1", "REQ-ERR-2"])
	@patch("production_api.purchase_order_approval.frappe.get_cached_doc")
	@patch("production_api.purchase_order_approval.ensure_purchase_order_approval_route", return_value="PO-ROUTE")
	@patch("production_api.purchase_order_approval.get_live_request", return_value=None)
	@patch("production_api.purchase_order_approval._prepare_purchase_order_request")
	def test_error_request_does_not_lock_and_can_retry(
		self, prepare, get_live, ensure_route, get_settings, create_and_send, get_doc
	):
		from production_api.purchase_order_approval import send_purchase_order_request

		prepare.return_value = self._doc()
		get_settings.return_value = frappe._dict(
			{
				"enabled": 1,
				"routes": [frappe._dict({"name": "PO-ROUTE", "enabled": 1, "reference_doctype": "Purchase Order"})],
			}
		)
		get_doc.side_effect = [
			frappe._dict({"name": "REQ-ERR-1", "status": "Error", "error": "network"}),
			frappe._dict({"name": "REQ-ERR-2", "status": "Error", "error": "network"}),
		]
		first = self._call(send_purchase_order_request, "PO-0012")
		second = self._call(send_purchase_order_request, "PO-0012")
		self.assertEqual(first["status"], "Error")
		self.assertEqual(second["status"], "Error")
		self.assertEqual(create_and_send.call_count, 2)

	@patch("production_api.purchase_order_approval.frappe.throw")
	@patch("production_api.purchase_order_approval.get_live_request")
	def test_only_queued_or_pending_request_blocks_edits(self, get_live, throw):
		from production_api.purchase_order_approval import _validate_not_locked_for_edit

		throw.side_effect = self._raise
		for status in ("Queued", "Pending"):
			get_live.return_value = frappe._dict({"name": "REQ", "status": status})
			with self.assertRaisesRegex(RuntimeError, "locked"):
				_validate_not_locked_for_edit(self._doc())
		for status in ("Error", "Approved", "Rejected", "Expired"):
			get_live.return_value = frappe._dict({"name": "REQ", "status": status})
			_validate_not_locked_for_edit(self._doc())

	@patch("production_api.purchase_order_approval.finish_request_message")
	@patch("production_api.purchase_order_approval.now_datetime", return_value="2026-10-05 10:00:00")
	@patch("production_api.purchase_order_approval.frappe.get_doc")
	@patch("production_api.purchase_order_approval.get_live_request")
	@patch("production_api.purchase_order_approval._current_user", return_value="manager@example.com")
	def test_finalization_closes_live_request_and_removes_buttons(
		self, current_user, get_live, get_doc, now, finish
	):
		from production_api.purchase_order_approval import finalize_live_request

		get_live.return_value = frappe._dict({"name": "REQ-LIVE", "status": "Pending"})
		request = Mock()
		get_doc.return_value = request
		finalize_live_request("PO-0012", "Approved", "Approve PO")
		request.db_set.assert_called_once()
		values = request.db_set.call_args.args[0]
		self.assertEqual(values["status"], "Approved")
		self.assertEqual(values["action_taken"], "Approve PO")
		finish.assert_called_once_with(request, "Approve PO", "manager@example.com")

	@patch("production_api.purchase_order_approval.get_live_request")
	@patch("production_api.purchase_order_approval.frappe.get_doc")
	def test_read_only_state_endpoint_checks_read_permission(self, get_doc, get_live):
		from production_api.purchase_order_approval import get_purchase_order_approval_state

		doc = self._doc()
		get_doc.return_value = doc
		get_live.return_value = frappe._dict({"name": "REQ-LIVE", "status": "Pending", "error": None})
		result = self._call(get_purchase_order_approval_state, "PO-0012")
		doc.check_permission.assert_called_once_with("read")
		self.assertTrue(result["pending_approval"])
		self.assertEqual(result["live_request"]["name"], "REQ-LIVE")

	@patch("production_api.purchase_order_approval.finalize_live_request")
	@patch("production_api.purchase_order_approval._in_telegram_action", return_value=False)
	def test_system_manager_native_submit_finalizes_live_request(self, in_telegram, finalize):
		from production_api.purchase_order_approval import finalize_purchase_order_submission

		finalize_purchase_order_submission(frappe._dict({"name": "PO-0012"}))
		finalize.assert_called_once_with("PO-0012", "Approved", "Submit PO")
