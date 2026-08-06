# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

from frappe import _dict, _
from frappe.utils import flt

from production_api.utils import get_work_order_pending_report


def execute(filters=None):
	filters = _dict(filters or {})
	data = get_work_order_pending_report(
		production_order=filters.get("production_order"),
		lot=filters.get("lot"),
		process=filters.get("process"),
		supplier=filters.get("supplier"),
		item=filters.get("item"),
		item_variant=filters.get("item_variant"),
		from_date=filters.get("from_date"),
		to_date=filters.get("to_date"),
		status=filters.get("status"),
	)
	return get_columns(), data, None, None, get_report_summary(data)


def get_columns():
	return [
		{
			"fieldname": "production_order",
			"label": _("Production Order"),
			"fieldtype": "Link",
			"options": "Production Order",
			"width": 180,
		},
		{
			"fieldname": "work_order",
			"label": _("Work Order"),
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 180,
		},
		{
			"fieldname": "lot",
			"label": _("Lot"),
			"fieldtype": "Link",
			"options": "Lot",
			"width": 160,
		},
		{
			"fieldname": "process_name",
			"label": _("Process"),
			"fieldtype": "Link",
			"options": "Process",
			"width": 140,
		},
		{
			"fieldname": "supplier_name",
			"label": _("Supplier"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "item_name",
			"label": _("Item"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "item_variant",
			"label": _("Item Variant"),
			"fieldtype": "Link",
			"options": "Item Variant",
			"width": 220,
		},
		{
			"fieldname": "delivered_qty",
			"label": _("Delivered"),
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"fieldname": "received_qty",
			"label": _("Received"),
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"fieldname": "pending_quantity",
			"label": _("Diff"),
			"fieldtype": "Float",
			"width": 120,
		},
	]


def get_report_summary(data):
	return [
		{
			"value": len(data),
			"label": _("Rows"),
			"datatype": "Int",
			"indicator": "Blue",
		},
		{
			"value": flt(sum(flt(row.get("delivered_qty")) for row in data), 3),
			"label": _("Delivered"),
			"datatype": "Float",
			"indicator": "Blue",
		},
		{
			"value": flt(sum(flt(row.get("received_qty")) for row in data), 3),
			"label": _("Received"),
			"datatype": "Float",
			"indicator": "Green",
		},
		{
			"value": flt(sum(flt(row.get("pending_quantity")) for row in data), 3),
			"label": _("Diff"),
			"datatype": "Float",
			"indicator": "Orange",
		},
	]
