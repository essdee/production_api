from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import now_datetime


class TelegramApprovalPermissionError(frappe.PermissionError):
	pass


class TelegramApprovalStateError(frappe.ValidationError):
	pass


def execute_action(request_doc, route, frappe_user: str, action_key: str):
	"""Execute a configured action as the mapped Frappe user."""
	doc = frappe.get_doc(request_doc.reference_doctype, request_doc.reference_name)
	current_value = str(doc.get(request_doc.state_field) or "")
	if current_value != str(request_doc.source_value or ""):
		raise TelegramApprovalStateError(
			_("This document is no longer in {0}. Current value: {1}.").format(
				request_doc.source_value, current_value or _("empty")
			)
		)

	action_name = _get_action_name(route, action_key)
	original_user = frappe.session.user
	previous_flag = frappe.flags.get("in_telegram_approval_action")
	frappe.set_user(frappe_user)
	frappe.flags.in_telegram_approval_action = True

	try:
		if route.process_type == "Workflow":
			updated_doc = apply_workflow(doc.as_dict(), action_name)
		else:
			updated_doc = _apply_field_state_action(doc, route, action_key, action_name)
	finally:
		frappe.flags.in_telegram_approval_action = previous_flag
		frappe.set_user(original_user)

	return action_name, updated_doc


def _get_action_name(route, action_key: str) -> str:
	fieldname = "approve_action" if action_key == "a" else "reject_action"
	action_name = route.get(fieldname)
	if not action_name:
		raise TelegramApprovalStateError(_("This action is not configured."))
	return action_name


def _apply_field_state_action(doc, route, action_key: str, action_name: str):
	doc.check_permission("write")

	_validate_action_roles(route, action_key, action_name)

	target_field = route.get("target_field")
	if not target_field or not doc.meta.has_field(target_field):
		raise TelegramApprovalStateError(
			_("Configured target field {0} does not exist on {1}.").format(
				target_field or _("empty"), doc.doctype
			)
		)

	target_value = route.get("approve_value") if action_key == "a" else route.get("reject_value")
	if target_value in (None, ""):
		raise TelegramApprovalStateError(
			_("No target value is configured for action {0}.").format(action_name)
		)

	handler = FIELD_STATE_ACTION_HANDLERS.get(doc.doctype)
	if handler:
		return handler(doc, route, action_key, action_name, target_field, target_value)

	doc.set(target_field, target_value)
	doc.save()
	doc.add_comment(
		"Comment",
		_("Telegram action {0} performed by {1}.").format(action_name, frappe.session.user),
	)
	return doc


def _validate_action_roles(route, action_key: str, action_name: str):
	required_roles = _parse_roles(
		route.get("approve_roles") if action_key == "a" else route.get("reject_roles")
	)
	user_roles = set(frappe.get_roles())
	if required_roles and not user_roles.intersection(required_roles):
		raise TelegramApprovalPermissionError(
			_("You are not authorized to perform {0} on this document.").format(action_name)
		)


def _apply_purchase_invoice_action(
	doc,
	route,
	action_key: str,
	action_name: str,
	target_field: str,
	target_value: str,
):
	if target_field != "status":
		raise TelegramApprovalStateError(
			_("Purchase Invoice Telegram approvals must update the status field.")
		)

	source_status = str(doc.status or "")
	allowed_approve_transitions = {
		"Approval Initiated": "Approval Pending",
		"Approval Pending": "Approved",
	}
	if action_key == "a" and allowed_approve_transitions.get(source_status) != target_value:
		raise TelegramApprovalStateError(
			_("Invalid Purchase Invoice approval transition: {0} to {1}.").format(
				source_status, target_value
			)
		)

	if action_key == "a" and target_value == "Approval Pending":
		doc.senior_merch_approved_by = frappe.session.user
	elif action_key == "a" and target_value == "Approved":
		_validate_purchase_invoice_work_orders(doc)
		doc.approved_by = frappe.session.user
		if not doc.senior_merch_approved_by:
			doc.senior_merch_approved_by = frappe.session.user
	elif action_key == "r" and target_value == "Draft":
		doc.approved_by = None
		doc.senior_merch_approved_by = None

	doc.set(target_field, target_value)
	doc.append(
		"purchase_invoice_wo_approval_details",
		{
			"user": frappe.session.user,
			"approved_time": now_datetime(),
			"comments": _("{0} through Telegram").format(action_name),
		},
	)
	doc.save()
	doc.add_comment(
		"Comment",
		_("Telegram action {0} performed by {1}.").format(action_name, frappe.session.user),
	)
	return doc


def _validate_purchase_invoice_work_orders(doc):
	if doc.against != "Work Order":
		return
	if frappe.db.get_single_value("MRP Settings", "override_pi_approve"):
		return

	from production_api.production_api.doctype.purchase_invoice.purchase_invoice import (
		check_all_wo_closed,
	)

	result = check_all_wo_closed(doc.name)
	if result["all_closed"]:
		return

	work_orders = result["open_work_orders"] + result["close_request_wos"]
	raise TelegramApprovalStateError(
		_(
			"Cannot approve because these Work Orders are not closed: {0}."
		).format(", ".join(work_orders))
	)


def _parse_roles(value: str | None) -> set[str]:
	if not value:
		return set()
	return {role.strip() for role in re.split(r"[,\n]", value) if role.strip()}


FIELD_STATE_ACTION_HANDLERS = {
	"Purchase Invoice": _apply_purchase_invoice_action,
}
