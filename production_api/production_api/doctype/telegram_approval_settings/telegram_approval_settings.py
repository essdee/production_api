# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.jinja import get_jenv
from jinja2 import TemplateSyntaxError


def validate_message_template(template: str | None, reference_doctype: str | None = None):
	if not template:
		return

	try:
		get_jenv().parse(template)
	except TemplateSyntaxError as exc:
		frappe.throw(
			_("Invalid Telegram message template for {0} on line {1}: {2}").format(
				reference_doctype or _("approval route"),
				exc.lineno or _("unknown"),
				exc.message,
			)
		)


class TelegramApprovalSettings(Document):
	def validate(self):
		if self.enabled and not self.bot_token:
			frappe.throw(_("Bot Token is required when Telegram approvals are enabled."))

		seen_routes = set()
		for route in self.routes:
			validate_message_template(route.message_template, route.reference_doctype)
			if not route.enabled:
				continue

			key = (
				route.reference_doctype,
				route.trigger_field,
				route.trigger_value,
				route.group_chat_id,
			)
			if key in seen_routes:
				frappe.throw(
					_(
						"Duplicate Telegram approval route for {0}, field {1}, value {2}, and group {3}."
					).format(*key)
				)
			seen_routes.add(key)

			if route.process_type == "Field State":
				if not route.target_field:
					frappe.throw(_("Target Field is required for Field State routes."))
				if not route.approve_value and not route.reject_value:
					frappe.throw(
						_("At least one target value is required for Field State route {0}.").format(
							route.reference_doctype
						)
					)
