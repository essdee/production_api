import frappe
from frappe.utils import now_datetime

from production_api.telegram_approval.service import (
	create_and_send_approval,
	finish_request_message,
)


YARN_ITEM_GROUP = "Purchase - Yarn"
PENDING_APPROVAL_STATUS = "Pending Approval"
SYSTEM_MANAGER_ROLE = "System Manager"
REJECTION_FLAG = "purchase_order_approval_rejection"
ACTION_FLAG = "purchase_order_approval_action"
PURCHASE_ORDER_MESSAGE_TEMPLATE = """\
PURCHASE ORDER APPROVAL
───────────────────────
PO: {{ doc.name }}
Supplier: {{ doc.supplier_name or doc.supplier or "-" }}
PO Date: {% if doc.po_date %}{{ format_date(doc.po_date) }}{% else %}-{% endif %}

ITEMS ({{ purchase_order_items | length }})
───────────────────────
{% for row in purchase_order_items %}
{{ loop.index }}. {{ row.item }}
   Quantity: {{ format_qty(row.qty) }}
   Lot: {{ row.lot or "-" }}
   Rate: {{ format_currency(row.rate) }}
{% endfor %}

Grand Total: {{ format_currency(doc.grand_total) }}"""

PURCHASE_ORDER_ROUTE_VALUES = {
	"enabled": 1,
	"reference_doctype": "Purchase Order",
	"process_type": "Field State",
	"trigger_field": "status",
	"trigger_value": PENDING_APPROVAL_STATUS,
	"message_template": PURCHASE_ORDER_MESSAGE_TEMPLATE,
	"approve_action": "Approve PO",
	"reject_action": "Reject PO",
	"target_field": "status",
	"approve_value": "Ordered",
	"reject_value": "Draft",
	"approve_roles": SYSTEM_MANAGER_ROLE,
	"reject_roles": SYSTEM_MANAGER_ROLE,
}


def requires_yarn_approval(doc):
	"""Return whether any PO row resolves to the exact yarn purchase group."""
	variants = {
		row.get("item_variant")
		for row in (doc.get("items") or [])
		if row.get("item_variant")
	}
	if not variants:
		return False

	variant_rows = frappe.get_all(
		"Item Variant",
		filters={"name": ["in", sorted(variants)]},
		fields=["name", "item"],
		limit_page_length=0,
	)
	items = {row.get("item") for row in variant_rows if row.get("item")}
	if not items:
		return False

	item_rows = frappe.get_all(
		"Item",
		filters={"name": ["in", sorted(items)]},
		fields=["name", "item_group"],
		limit_page_length=0,
	)
	return any(row.get("item_group") == YARN_ITEM_GROUP for row in item_rows)


def apply_draft_approval_status(doc, method=None):
	"""Classify an ordinary draft save without disturbing submitted records."""
	if doc.docstatus != 0 or doc.flags.get(REJECTION_FLAG):
		return
	_validate_not_locked_for_edit(doc)
	if requires_yarn_approval(doc):
		doc.status = PENDING_APPROVAL_STATUS
	elif doc.status == PENDING_APPROVAL_STATUS:
		doc.status = "Draft"


def _require_system_manager():
	if SYSTEM_MANAGER_ROLE not in frappe.get_roles():
		frappe.throw("Only System Manager can approve, reject, or submit this Purchase Order", frappe.PermissionError)


def _get_locked_purchase_order(name):
	frappe.db.get_value("Purchase Order", name, "name", for_update=True)
	return frappe.get_doc("Purchase Order", name)


def _validate_pending_yarn_purchase_order(doc):
	if doc.docstatus != 0 or doc.status != PENDING_APPROVAL_STATUS:
		frappe.throw("Purchase Order must be in Pending Approval before this action")
	if not requires_yarn_approval(doc):
		frappe.throw(f"Purchase Order must contain an item in {YARN_ITEM_GROUP}")


def validate_approval_submit(doc, method=None):
	"""Allow yarn PO submission only to an exact System Manager role holder."""
	if requires_yarn_approval(doc):
		_require_system_manager()


@frappe.whitelist()
def approve_purchase_order(name):
	_require_system_manager()
	doc = _get_locked_purchase_order(name)
	_validate_pending_yarn_purchase_order(doc)
	doc.flags[ACTION_FLAG] = "approve"
	doc.submit()
	if not _in_telegram_action():
		finalize_live_request(name, "Approved", "Approve PO")
	return {"name": doc.name, "status": doc.status, "docstatus": doc.docstatus}


@frappe.whitelist()
def reject_purchase_order(name):
	_require_system_manager()
	doc = _get_locked_purchase_order(name)
	_validate_pending_yarn_purchase_order(doc)
	doc.flags[REJECTION_FLAG] = True
	doc.status = "Draft"
	doc.save(ignore_permissions=True)
	if not _in_telegram_action():
		finalize_live_request(name, "Rejected", "Reject PO")
	return {"name": doc.name, "status": doc.status, "docstatus": doc.docstatus}


def _current_user():
	return frappe.session.user


def _in_telegram_action():
	return bool(getattr(frappe.local, "flags", {}).get("in_telegram_approval_action"))


def get_live_request(name):
	rows = frappe.get_all(
		"Telegram Approval Request",
		filters={
			"reference_doctype": "Purchase Order",
			"reference_name": name,
			"status": ["in", ["Queued", "Pending"]],
		},
		fields=["name", "status", "error"],
		order_by="creation desc",
		limit_page_length=1,
	)
	return rows[0] if rows else None


def _validate_not_locked_for_edit(doc):
	if not doc.get("name") or str(doc.get("name")).startswith("new-"):
		return
	live_request = get_live_request(doc.name)
	if live_request and live_request.get("status") in {"Queued", "Pending"}:
		frappe.throw(
			f"Purchase Order is locked by Telegram approval request {live_request.name}"
		)


def _require_send_permissions(doc):
	if not frappe.has_permission("Purchase Order", ptype="create"):
		frappe.throw(
			"Purchase Order create permission is required to send an approval request",
			frappe.PermissionError,
		)
	doc.check_permission("read")


def _prepare_purchase_order_request(name):
	doc = _get_locked_purchase_order(name)
	_require_send_permissions(doc)
	_validate_pending_yarn_purchase_order(doc)
	return doc


def finalize_live_request(name, result_status, action_label):
	live_request = get_live_request(name)
	if not live_request:
		return None

	request_doc = frappe.get_doc("Telegram Approval Request", live_request.name)
	frappe_user = _current_user()
	request_doc.db_set(
		{
			"status": result_status,
			"action_taken": action_label,
			"frappe_user": frappe_user,
			"acted_on": now_datetime(),
			"error": None,
		}
	)
	finish_request_message(request_doc, action_label, frappe_user)
	return request_doc.name


def finalize_purchase_order_submission(doc, method=None):
	if _in_telegram_action():
		return
	action_label = (
		"Approve PO"
		if (doc.get("flags") or {}).get(ACTION_FLAG) == "approve"
		else "Submit PO"
	)
	finalize_live_request(doc.name, "Approved", action_label)


@frappe.whitelist()
def get_purchase_order_approval_state(name):
	doc = frappe.get_doc("Purchase Order", name)
	doc.check_permission("read")
	live_request = get_live_request(name)
	return {
		"pending_approval": doc.docstatus == 0 and doc.status == PENDING_APPROVAL_STATUS,
		"live_request": dict(live_request) if live_request else None,
	}


def ensure_purchase_order_approval_route():
	"""Create or reconcile the manual PO route using the Process Cost group."""
	try:
		settings = frappe.get_cached_doc("Telegram Approval Settings")
	except frappe.DoesNotExistError:
		return None

	process_route = next(
		(
			route
			for route in (settings.routes or [])
			if route.get("enabled")
			and route.get("reference_doctype") == "Process Cost"
			and route.get("group_chat_id")
		),
		None,
	)
	if not process_route:
		return None

	po_route = next(
		(route for route in (settings.routes or []) if route.get("reference_doctype") == "Purchase Order"),
		None,
	)
	created = po_route is None
	if created:
		po_route = settings.append("routes", {})

	desired = {**PURCHASE_ORDER_ROUTE_VALUES, "group_chat_id": process_route.group_chat_id}
	changed = created
	for fieldname, value in desired.items():
		if po_route.get(fieldname) != value:
			if isinstance(po_route, dict):
				po_route[fieldname] = value
			else:
				po_route.set(fieldname, value)
			changed = True

	if changed:
		settings.save(ignore_permissions=True)
	return po_route.name


@frappe.whitelist()
def send_purchase_order_request(name):
	_prepare_purchase_order_request(name)
	live_request = get_live_request(name)
	if live_request:
		return {
			"request": live_request.name,
			"status": live_request.status,
			"error": live_request.get("error"),
		}

	route_name = ensure_purchase_order_approval_route()
	if not route_name:
		frappe.throw("Configure an enabled Process Cost Telegram approval route first")

	settings = frappe.get_cached_doc("Telegram Approval Settings")
	if not settings.enabled:
		frappe.throw("Telegram approvals are not enabled")
	route = next(
		(
			route
			for route in settings.routes
			if route.name == route_name and route.enabled and route.reference_doctype == "Purchase Order"
		),
		None,
	)
	if not route:
		frappe.throw("Purchase Order Telegram approval route is not available")

	request_name = create_and_send_approval("Purchase Order", name, route.name)
	request_doc = frappe.get_doc("Telegram Approval Request", request_name)
	return {
		"request": request_doc.name,
		"status": request_doc.status,
		"error": request_doc.get("error"),
	}
