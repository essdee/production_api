# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

from production_api.utils import get_dispatch_percentage_report


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_dispatch_percentage_report(
		filters.get("percentage"),
		filters.get("lot"),
		filters.get("item"),
	)

	return columns, data


def get_columns():
	return [
		{
			"fieldname": "date",
			"fieldtype": "Date",
			"label": "Date",
			"width": 120,
		},
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"label": "Lot",
			"options": "Lot",
			"width": 140,
		},
		{
			"fieldname": "stock_entry",
			"fieldtype": "Link",
			"label": "Stock Entry",
			"options": "Stock Entry",
			"width": 160,
		},
		{
			"fieldname": "item",
			"fieldtype": "Link",
			"label": "Item",
			"options": "Item",
			"width": 220,
		},
		{
			"fieldname": "percentage",
			"fieldtype": "Percent",
			"label": "Percentage On That Date",
			"width": 180,
		},
	]
