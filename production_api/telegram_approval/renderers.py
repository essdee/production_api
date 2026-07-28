from __future__ import annotations

from collections.abc import Callable

import frappe
from frappe.utils import flt, format_date, fmt_money


MAX_MESSAGE_LENGTH = 3900
MessageContextProvider = Callable[[object], dict]


def render_message(doc, route: frappe._dict) -> str:
	"""Render a route-configured Jinja template with safe, prepared context."""
	context = get_message_context(doc, route)
	if route.get("message_template"):
		message = frappe.render_template(route.message_template, context).strip()
	else:
		message = render_generic(doc, route)

	return _truncate_message(message)


def get_message_context(doc, route: frappe._dict) -> dict:
	context = {
		"doc": doc,
		"route": route,
		"format_currency": _format_currency,
		"format_date": format_date,
		"format_qty": _format_qty,
	}
	provider = MESSAGE_CONTEXT_PROVIDERS.get(doc.doctype)
	if provider:
		context.update(provider(doc))
	return context


def get_purchase_invoice_context(doc) -> dict:
	"""Prepare derived PI values that are not directly available to Jinja."""
	work_order_rows = list(doc.get("pi_work_order_billed_details") or [])
	work_orders = list(
		dict.fromkeys(row.work_order for row in work_order_rows if row.work_order)
	)
	return {
		"summary": frappe._dict(
			{
				"debit_amount": _get_purchase_invoice_debit_amount(doc, work_orders),
				"total_amount": flt(doc.get("total")),
				"total_delivered": sum(
					flt(row.total_delivered) for row in work_order_rows
				),
				"total_received": sum(
					flt(row.total_received) for row in work_order_rows
				),
				"work_orders": ", ".join(work_orders) if work_orders else "Not applicable",
			}
		)
	}


def render_generic(doc, route: frappe._dict) -> str:
	return "\n".join(
		[
			"APPROVAL REQUIRED",
			"─────────────────",
			f"Document: {doc.doctype}",
			f"Name: {doc.name}",
			f"State: {route.trigger_value}",
			f"Requested by: {doc.modified_by}",
		]
	)


def _format_qty(value) -> str:
	number = flt(value)
	return f"{number:,.2f}".rstrip("0").rstrip(".")


def _format_currency(value) -> str:
	currency = frappe.defaults.get_global_default("currency")
	return fmt_money(value, currency=currency)


def _get_purchase_invoice_debit_amount(doc, work_orders: list[str]) -> float:
	debit_rows = list(doc.get("purchase_invoice_debit_details") or [])
	if debit_rows:
		return sum(flt(row.debit_value) for row in debit_rows)

	if not work_orders:
		return 0

	debits = frappe.get_all(
		"Essdee Debit",
		filters={
			"against": "Work Order",
			"against_id": ["in", work_orders],
			"docstatus": 1,
		},
		fields=["debit_value"],
		limit_page_length=0,
	)
	return sum(flt(row.debit_value) for row in debits)


def _truncate_message(message: str) -> str:
	if len(message) <= MAX_MESSAGE_LENGTH:
		return message
	suffix = "\n... Open the document to view the remaining details."
	return f"{message[: MAX_MESSAGE_LENGTH - len(suffix)].rstrip()}{suffix}"


MESSAGE_CONTEXT_PROVIDERS: dict[str, MessageContextProvider] = {
	"Purchase Invoice": get_purchase_invoice_context,
}
