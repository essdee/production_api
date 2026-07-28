from __future__ import annotations

from collections.abc import Callable

import frappe
from frappe.utils import flt, format_date, fmt_money


MAX_MESSAGE_LENGTH = 3900
MessageRenderer = Callable[[object, frappe._dict], str]


def render_message(doc, route: frappe._dict) -> str:
	"""Render with a safe registered function, with Jinja as a route-level override."""
	if route.get("message_template"):
		return frappe.render_template(route.message_template, {"doc": doc, "route": route}).strip()

	renderer = MESSAGE_RENDERERS.get(doc.doctype, render_generic)
	return renderer(doc, route)


def render_process_cost(doc, route: frappe._dict) -> str:
	supplier = doc.supplier_name or doc.supplier or "-"
	if doc.supplier and doc.supplier_name:
		supplier = f"{doc.supplier_name} ({doc.supplier})"

	validity = format_date(doc.from_date)
	if doc.to_date:
		validity = f"{validity} to {format_date(doc.to_date)}"
	else:
		validity = f"{validity} onwards"

	rows = list(doc.process_cost_values or [])
	lines = [
		"PROCESS COST APPROVAL",
		"─────────────────────",
		f"Document: {doc.name}",
		f"Lot: {doc.lot}",
		f"Item: {doc.item}",
		f"Process: {doc.process_name}",
		f"Supplier: {supplier}",
		f"Validity: {validity}",
		f"Attribute: {doc.attribute or 'Not applicable'}",
		f"Tax Slab: {doc.tax_slab or '-'}",
		f"Rework: {'Yes' if doc.is_rework else 'No'}",
		"",
		f"PROCESS COST VALUES ({len(rows)})",
		"─────────────────────",
	]

	for index, row in enumerate(rows, start=1):
		row_lines = [
			f"{index}. {row.attribute_value or 'Default'}",
			f"   Minimum Order Qty: {_format_qty(row.min_order_qty)} {doc.uom or ''}".rstrip(),
			f"   Price (Excl. Tax): {_format_currency(row.price)}",
		]
		candidate = "\n".join(lines + row_lines)
		if len(candidate) > MAX_MESSAGE_LENGTH:
			remaining = len(rows) - index + 1
			lines.append(f"... {remaining} more value(s). Open the document to view all.")
			break
		lines.extend(row_lines)

	return "\n".join(lines)


def render_purchase_invoice(doc, route: frappe._dict) -> str:
	work_order_rows = list(doc.get("pi_work_order_billed_details") or [])
	work_orders = list(
		dict.fromkeys(row.work_order for row in work_order_rows if row.work_order)
	)
	total_delivered = sum(flt(row.total_delivered) for row in work_order_rows)
	total_received = sum(flt(row.total_received) for row in work_order_rows)
	debit_amount = _get_purchase_invoice_debit_amount(doc, work_orders)

	supplier = doc.get("billing_supplier") or doc.get("supplier") or "-"
	bill_date = format_date(doc.get("bill_date")) if doc.get("bill_date") else "-"
	work_order_text = ", ".join(work_orders) if work_orders else "Not applicable"

	return "\n".join(
		[
			"PURCHASE INVOICE APPROVAL",
			"─────────────────────────",
			f"Document: {doc.name}",
			f"Approval Stage: {route.trigger_value}",
			f"Supplier: {supplier}",
			f"Against: {doc.get('against') or '-'}",
			f"Supplier Bill: {doc.get('bill_no') or '-'}",
			f"Bill Date: {bill_date}",
			f"Work Order(s): {work_order_text}",
			"",
			"SUMMARY",
			"─────────────────────────",
			f"Total Delivered: {_format_qty(total_delivered)}",
			f"Total Received: {_format_qty(total_received)}",
			f"Debit Amount: {_format_currency(debit_amount)}",
			f"Total Amount: {_format_currency(doc.get('total'))}",
		]
	)


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
	"""Use the stored PI snapshot when present, otherwise mirror the live debit summary."""
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


MESSAGE_RENDERERS: dict[str, MessageRenderer] = {
	"Process Cost": render_process_cost,
	"Purchase Invoice": render_purchase_invoice,
}
