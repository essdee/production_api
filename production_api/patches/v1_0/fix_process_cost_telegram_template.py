import re

import frappe


INVALID_REQUESTED_BY_TAG = re.compile(r"{%\s*doc\.modified_by\s*%}")
VALID_REQUESTED_BY_EXPRESSION = '{{ doc.modified_by or "-" }}'


def fix_requested_by_expression(template: str | None) -> str | None:
	if not template:
		return template
	return INVALID_REQUESTED_BY_TAG.sub(VALID_REQUESTED_BY_EXPRESSION, template)


def execute():
	routes = frappe.get_all(
		"Telegram Approval Route",
		filters={"reference_doctype": "Process Cost"},
		fields=["name", "message_template"],
	)
	corrected_route_names = []
	for route in routes:
		corrected = fix_requested_by_expression(route.message_template)
		if corrected == route.message_template:
			continue
		frappe.db.set_value(
			"Telegram Approval Route",
			route.name,
			"message_template",
			corrected,
			update_modified=False,
		)
		corrected_route_names.append(route.name)

	if corrected_route_names:
		frappe.db.set_value(
			"Telegram Approval Request",
			{
				"reference_doctype": "Process Cost",
				"route_row": ["in", corrected_route_names],
				"status": "Queued",
				"telegram_message_id": ["is", "not set"],
			},
			{
				"status": "Error",
				"error": "Message template failed before Telegram delivery.",
			},
			update_modified=False,
		)
