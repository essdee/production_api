# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TelegramApprovalSettings(Document):
	def validate(self):
		if self.enabled and not self.bot_token:
			frappe.throw(_("Bot Token is required when Telegram approvals are enabled."))

		seen_routes = set()
		for route in self.routes:
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
