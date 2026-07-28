from __future__ import annotations

from typing import Any

import requests


class TelegramAPIError(Exception):
	"""A sanitized Telegram API error that never contains the bot token."""


class TelegramClient:
	def __init__(self, token: str, timeout: int = 20):
		if not token:
			raise TelegramAPIError("Telegram bot token is not configured.")
		self._token = token
		self._timeout = timeout

	def call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
		url = f"https://api.telegram.org/bot{self._token}/{method}"
		try:
			response = requests.post(url, json=payload or {}, timeout=self._timeout)
		except requests.RequestException:
			raise TelegramAPIError("Telegram API is currently unreachable.") from None

		try:
			body = response.json()
		except ValueError:
			raise TelegramAPIError(
				f"Telegram returned an invalid response (HTTP {response.status_code})."
			) from None

		if not response.ok or not body.get("ok"):
			description = body.get("description") or f"HTTP {response.status_code}"
			raise TelegramAPIError(f"Telegram API rejected the request: {description}")

		return body.get("result")

	def get_me(self) -> dict[str, Any]:
		return self.call("getMe")

	def set_webhook(self, url: str, secret_token: str) -> bool:
		return bool(
			self.call(
				"setWebhook",
				{
					"url": url,
					"secret_token": secret_token,
					"allowed_updates": ["callback_query", "message"],
					"drop_pending_updates": False,
				},
			)
		)

	def get_webhook_info(self) -> dict[str, Any]:
		return self.call("getWebhookInfo")

	def send_message(
		self,
		chat_id: str | int,
		text: str,
		reply_markup: dict[str, Any] | None = None,
	) -> dict[str, Any]:
		payload: dict[str, Any] = {
			"chat_id": chat_id,
			"text": text,
			"disable_web_page_preview": True,
		}
		if reply_markup is not None:
			payload["reply_markup"] = reply_markup
		return self.call("sendMessage", payload)

	def edit_message(
		self,
		chat_id: str | int,
		message_id: str | int,
		text: str,
		reply_markup: dict[str, Any] | None = None,
	) -> dict[str, Any] | bool:
		payload: dict[str, Any] = {
			"chat_id": chat_id,
			"message_id": message_id,
			"text": text,
			"disable_web_page_preview": True,
		}
		if reply_markup is not None:
			payload["reply_markup"] = reply_markup
		return self.call("editMessageText", payload)

	def answer_callback_query(
		self,
		callback_query_id: str,
		text: str,
		show_alert: bool = False,
	) -> bool:
		return bool(
			self.call(
				"answerCallbackQuery",
				{
					"callback_query_id": callback_query_id,
					"text": text[:200],
					"show_alert": show_alert,
				},
			)
		)

	def get_chat_member(self, chat_id: str | int, user_id: str | int) -> dict[str, Any]:
		return self.call("getChatMember", {"chat_id": chat_id, "user_id": user_id})
