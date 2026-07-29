from __future__ import annotations

import hmac
import json
import re

import frappe
from frappe import _
from frappe.utils import get_url, now_datetime

from production_api.telegram_approval.adapters import execute_action
from production_api.telegram_approval.client import TelegramAPIError
from production_api.telegram_approval.service import (
	finish_request_message,
	get_client,
	get_settings,
	handle_document_event,
)


CALLBACK_PATTERN = re.compile(r"^ta:([A-Za-z0-9]+):(a|r)$")


@frappe.whitelist()
def verify_bot():
	frappe.only_for("System Manager")
	return get_client().get_me()


@frappe.whitelist()
def configure_webhook():
	frappe.only_for("System Manager")
	settings = get_settings()
	if not settings.bot_token:
		frappe.throw(_("Configure the Bot Token first."))

	secret = (
		settings.get_password("webhook_secret")
		if settings.webhook_secret
		else frappe.generate_hash(length=40)
	)
	base_url = (settings.public_webhook_base_url or get_url()).strip().rstrip("/")
	if not base_url.startswith("https://"):
		frappe.throw(
			_(
				"Telegram requires a public HTTPS webhook URL. Configure Public Webhook Base URL first."
			)
		)
	webhook_url = (
		f"{base_url}/api/method/production_api.telegram_approval.api.webhook"
	)

	settings.webhook_secret = secret
	settings.webhook_url = webhook_url
	settings.save()
	get_client(settings).set_webhook(webhook_url, secret)
	frappe.msgprint(_("Telegram webhook configured successfully."))
	return {"url": webhook_url}


@frappe.whitelist()
def get_webhook_status():
	frappe.only_for("System Manager")
	return get_client().get_webhook_info()


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook():
	settings = get_settings()
	if not settings.enabled or not settings.webhook_secret:
		frappe.throw(_("Telegram approvals are not enabled."), frappe.AuthenticationError)

	expected_secret = settings.get_password("webhook_secret")
	received_secret = frappe.get_request_header("X-Telegram-Bot-Api-Secret-Token", "")
	if not hmac.compare_digest(received_secret or "", expected_secret or ""):
		frappe.throw(_("Invalid Telegram webhook secret."), frappe.AuthenticationError)

	payload = frappe.request.get_json(silent=True) or {}
	if payload.get("callback_query"):
		_process_callback_query(payload["callback_query"])
	elif payload.get("message"):
		_process_command(payload["message"])

	return {"ok": True}


def _process_callback_query(callback_query: dict):
	client = get_client()
	callback_id = str(callback_query.get("id") or "")
	match = CALLBACK_PATTERN.match(str(callback_query.get("data") or ""))
	if not match:
		_answer_callback(client, callback_id, _("Invalid approval button."), show_alert=True)
		return

	request_name, action_key = match.groups()
	frappe.db.sql(
		"select name from `tabTelegram Approval Request` where name = %s for update",
		request_name,
	)
	if not frappe.db.exists("Telegram Approval Request", request_name):
		_answer_callback(client, callback_id, _("Approval request was not found."), show_alert=True)
		return

	request_doc = frappe.get_doc("Telegram Approval Request", request_name)
	if request_doc.status != "Pending":
		_answer_callback(
			client,
			callback_id,
			_("This request is already {0}.").format(request_doc.status.lower()),
			show_alert=True,
		)
		return

	message = callback_query.get("message") or {}
	chat = message.get("chat") or {}
	if str(chat.get("id") or "") != str(request_doc.group_chat_id):
		_answer_callback(client, callback_id, _("This button belongs to another group."), True)
		return
	if request_doc.telegram_message_id and str(message.get("message_id") or "") != str(
		request_doc.telegram_message_id
	):
		_answer_callback(client, callback_id, _("This approval message is not valid."), True)
		return

	telegram_user = callback_query.get("from") or {}
	telegram_user_id = str(telegram_user.get("id") or "")
	if not telegram_user_id:
		_answer_callback(client, callback_id, _("Unable to identify the Telegram user."), True)
		return

	try:
		member = client.get_chat_member(request_doc.group_chat_id, telegram_user_id)
	except TelegramAPIError:
		_answer_callback(
			client,
			callback_id,
			_("Unable to verify your group membership. Please try again."),
			True,
		)
		return
	if member.get("status") in {"left", "kicked"} or (
		member.get("status") == "restricted" and not member.get("is_member")
	):
		_answer_callback(client, callback_id, _("You are no longer a member of this group."), True)
		return

	frappe_user = frappe.db.get_value(
		"User",
		{"telegram_user_id": telegram_user_id, "enabled": 1},
		"name",
	)
	if not frappe_user:
		_answer_callback(
			client,
			callback_id,
			_(
				"Your Telegram account is not linked to an active Frappe user. "
				"Use /whoami and ask an administrator to configure your Telegram User ID."
			),
			True,
		)
		return

	try:
		route = frappe._dict(json.loads(request_doc.route_snapshot))
	except (TypeError, ValueError):
		_answer_callback(client, callback_id, _("Approval configuration is invalid."), True)
		return

	savepoint = "telegram_approval_action"
	frappe.db.savepoint(savepoint)
	try:
		action_name, updated_doc = execute_action(
			request_doc,
			route,
			frappe_user,
			action_key,
		)
	except (frappe.PermissionError, frappe.ValidationError) as exc:
		frappe.db.rollback(save_point=savepoint)
		_answer_callback(client, callback_id, _clean_error(exc), show_alert=True)
		return
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		frappe.log_error(
			title=f"Telegram approval callback failed: {request_doc.name}",
			message=frappe.get_traceback(),
		)
		_answer_callback(
			client,
			callback_id,
			_("The approval could not be completed. Please contact the administrator."),
			show_alert=True,
		)
		return

	result_status = "Approved" if action_key == "a" else "Rejected"
	request_doc.db_set(
		{
			"status": result_status,
			"action_taken": action_name,
			"telegram_user_id": telegram_user_id,
			"frappe_user": frappe_user,
			"acted_on": now_datetime(),
			"error": None,
		}
	)
	handle_document_event(updated_doc)
	finish_request_message(request_doc, action_name, frappe_user)
	_answer_callback(
		client,
		callback_id,
		_("{0} completed successfully.").format(action_name),
		show_alert=False,
	)


def _process_command(message: dict):
	text = str(message.get("text") or "").strip()
	if not text.startswith("/"):
		return

	command = text.split(maxsplit=1)[0].split("@", 1)[0].lower()
	chat = message.get("chat") or {}
	sender = message.get("from") or {}
	chat_id = chat.get("id")
	telegram_user_id = str(sender.get("id") or "")
	client = get_client()

	if command in {"/start", "/help"}:
		client.send_message(
			chat_id,
			"Available commands:\n"
			"/whoami - show your Telegram ID and linked Frappe user\n"
			"/chatid - show this group chat ID (group admins only)",
		)
		return

	if command == "/whoami":
		frappe_user = frappe.db.get_value(
			"User",
			{"telegram_user_id": telegram_user_id},
			"name",
		)
		link_status = frappe_user or "Not linked"
		client.send_message(
			chat_id,
			f"Telegram User ID: {telegram_user_id}\nFrappe User: {link_status}",
		)
		return

	if command == "/chatid":
		member = client.get_chat_member(chat_id, telegram_user_id)
		if member.get("status") not in {"administrator", "creator"}:
			client.send_message(chat_id, "Only a group administrator can use /chatid.")
			return
		client.send_message(chat_id, f"Telegram Group Chat ID: {chat_id}")


def _answer_callback(
	client,
	callback_id: str,
	message: str,
	show_alert: bool = False,
):
	if not callback_id:
		return
	try:
		client.answer_callback_query(callback_id, message, show_alert)
	except TelegramAPIError as exc:
		frappe.log_error(
			title="Telegram callback response failed",
			message=str(exc),
		)


def _clean_error(exc: Exception) -> str:
	message = str(exc).strip() or _("You are not authorized to perform this action.")
	return re.sub(r"<[^>]+>", "", message)[:200]
