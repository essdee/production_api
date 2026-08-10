from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import get_url_to_form, now_datetime

from production_api.telegram_approval.client import TelegramAPIError, TelegramClient
from production_api.telegram_approval.renderers import render_message


ROUTE_SNAPSHOT_FIELDS = (
	"reference_doctype",
	"process_type",
	"trigger_field",
	"trigger_value",
	"group_chat_id",
	"message_template",
	"approve_action",
	"reject_action",
	"target_field",
	"approve_value",
	"reject_value",
	"approve_roles",
	"reject_roles",
)


def get_settings():
	return frappe.get_cached_doc("Telegram Approval Settings")


def get_client(settings=None) -> TelegramClient:
	settings = settings or get_settings()
	token = settings.get_password("bot_token")
	return TelegramClient(token)


def get_route_snapshot(route) -> frappe._dict:
	return frappe._dict({field: route.get(field) for field in ROUTE_SNAPSHOT_FIELDS})


def handle_document_event(doc, method=None):
	"""Detect configured state changes without adding Telegram code to each DocType."""
	if (
		frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.get("in_telegram_approval_action")
	):
		return

	try:
		settings = get_settings()
	except frappe.DoesNotExistError:
		return

	if not settings.enabled:
		return

	routes = [
		route
		for route in settings.routes
		if route.enabled and route.reference_doctype == doc.doctype
	]
	if not routes:
		return

	previous_doc = doc.get_doc_before_save()
	for route in routes:
		current_value = _as_text(doc.get(route.trigger_field))
		previous_value = (
			_as_text(previous_doc.get(route.trigger_field)) if previous_doc else None
		)
		trigger_value = _as_text(route.trigger_value)

		if current_value == trigger_value and previous_value != current_value:
			frappe.enqueue(
				"production_api.telegram_approval.service.create_and_send_approval",
				queue="short",
				enqueue_after_commit=True,
				doctype=doc.doctype,
				docname=doc.name,
				route_row=route.name,
			)

	_expire_stale_requests(doc)


def create_and_send_approval(doctype: str, docname: str, route_row: str):
	settings = get_settings()
	if not settings.enabled:
		return

	route = next(
		(route for route in settings.routes if route.name == route_row and route.enabled),
		None,
	)
	if not route:
		return

	doc = frappe.get_doc(doctype, docname)
	if _as_text(doc.get(route.trigger_field)) != _as_text(route.trigger_value):
		return

	existing = frappe.db.exists(
		"Telegram Approval Request",
		{
			"reference_doctype": doctype,
			"reference_name": docname,
			"state_field": route.trigger_field,
			"source_value": route.trigger_value,
			"group_chat_id": route.group_chat_id,
			"status": ["in", ["Queued", "Pending"]],
		},
	)
	if existing:
		return existing

	route_snapshot = get_route_snapshot(route)
	request_doc = frappe.get_doc(
		{
			"doctype": "Telegram Approval Request",
			"reference_doctype": doctype,
			"reference_name": docname,
			"route_row": route.name,
			"route_snapshot": json.dumps(route_snapshot, sort_keys=True),
			"state_field": route.trigger_field,
			"source_value": route.trigger_value,
			"group_chat_id": route.group_chat_id,
			"status": "Queued",
		}
	).insert(ignore_permissions=True)

	try:
		message_text = render_approval_message(doc, route_snapshot)
		reply_markup = build_approval_keyboard(request_doc.name, route_snapshot, doc)
		result = get_client(settings).send_message(
			route.group_chat_id,
			message_text,
			reply_markup=reply_markup,
		)
		request_doc.db_set(
			{
				"telegram_message_id": str(result["message_id"]),
				"message_text": message_text,
				"status": "Pending",
				"error": None,
			}
		)
	except (frappe.ValidationError, TelegramAPIError) as exc:
		request_doc.db_set({"status": "Error", "error": str(exc)[:500]})
		frappe.log_error(
			title=f"Telegram approval send failed: {doctype} {docname}",
			message=str(exc),
		)

	return request_doc.name


def render_approval_message(doc, route) -> str:
	return render_message(doc, route)


def build_approval_keyboard(request_name: str, route, doc) -> dict:
	action_buttons = []
	if route.get("approve_action"):
		action_buttons.append(
			{"text": route.approve_action, "callback_data": f"ta:{request_name}:a"}
		)
	if route.get("reject_action"):
		action_buttons.append(
			{"text": route.reject_action, "callback_data": f"ta:{request_name}:r"}
		)

	rows = [action_buttons] if action_buttons else []
	rows.append([{"text": "Open in Frappe", "url": get_url_to_form(doc.doctype, doc.name)}])
	return {"inline_keyboard": rows}


def finish_request_message(request_doc, result_label: str, frappe_user: str):
	if not request_doc.telegram_message_id:
		return

	text = (
		f"{request_doc.message_text}\n\n"
		f"{result_label} by {frappe_user}\n"
		f"{now_datetime().strftime('%d-%m-%Y %I:%M %p')}"
	)
	try:
		get_client().edit_message(
			request_doc.group_chat_id,
			request_doc.telegram_message_id,
			text,
			reply_markup={"inline_keyboard": []},
		)
	except TelegramAPIError as exc:
		frappe.log_error(
			title=f"Telegram approval message update failed: {request_doc.name}",
			message=str(exc),
		)


def expire_request_message(request_name: str):
	request_doc = frappe.get_doc("Telegram Approval Request", request_name)
	if not request_doc.telegram_message_id:
		return

	text = f"{request_doc.message_text}\n\nRequest closed because the document state changed in Frappe."
	try:
		get_client().edit_message(
			request_doc.group_chat_id,
			request_doc.telegram_message_id,
			text,
			reply_markup={"inline_keyboard": []},
		)
	except TelegramAPIError as exc:
		frappe.log_error(
			title=f"Telegram approval expiry update failed: {request_doc.name}",
			message=str(exc),
		)


def _expire_stale_requests(doc):
	pending_requests = frappe.get_all(
		"Telegram Approval Request",
		filters={
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"status": ["in", ["Queued", "Pending"]],
		},
		fields=["name", "state_field", "source_value"],
	)
	for request_data in pending_requests:
		if _as_text(doc.get(request_data.state_field)) == _as_text(request_data.source_value):
			continue
		frappe.db.set_value(
			"Telegram Approval Request",
			request_data.name,
			"status",
			"Expired",
		)
		frappe.enqueue(
			"production_api.telegram_approval.service.expire_request_message",
			queue="short",
			enqueue_after_commit=True,
			request_name=request_data.name,
		)


def _as_text(value) -> str:
	return str(value or "")
