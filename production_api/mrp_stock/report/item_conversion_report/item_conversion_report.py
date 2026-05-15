# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	return get_columns(), get_data(filters)


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date") and filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be greater than To Date"))


def get_columns():
	return [
		{
			"fieldname": "item_conversion",
			"fieldtype": "Link",
			"label": "Item Conversion",
			"options": "Item Conversion",
			"width": 170,
		},
		{"fieldname": "posting_date", "fieldtype": "Date", "label": "Posting Date", "width": 110},
		{"fieldname": "location", "fieldtype": "Link", "label": "Location", "options": "Supplier", "width": 170},
		{"fieldname": "location_name", "fieldtype": "Data", "label": "Location Name", "width": 220},
		{
			"fieldname": "from_item",
			"fieldtype": "Link",
			"label": "From Item",
			"options": "Item",
			"width": 200,
		},
		{
			"fieldname": "from_item_variant",
			"fieldtype": "Link",
			"label": "From Item Variant",
			"options": "Item Variant",
			"width": 230,
		},
		{
			"fieldname": "from_lot",
			"fieldtype": "Link",
			"label": "From Lot",
			"options": "Lot",
			"width": 120,
		},
		{"fieldname": "from_qty", "fieldtype": "Float", "label": "From Qty", "width": 100},
		{"fieldname": "from_uom", "fieldtype": "Link", "label": "From UOM", "options": "UOM", "width": 100},
		{
			"fieldname": "from_valuation_rate",
			"fieldtype": "Currency",
			"label": "From Valuation Rate",
			"width": 150,
		},
		{
			"fieldname": "from_valuation_amount",
			"fieldtype": "Currency",
			"label": "From Valuation Amount",
			"width": 160,
		},
		{"fieldname": "to_item", "fieldtype": "Link", "label": "To Item", "options": "Item", "width": 200},
		{
			"fieldname": "to_item_variant",
			"fieldtype": "Link",
			"label": "To Item Variant",
			"options": "Item Variant",
			"width": 230,
		},
		{"fieldname": "to_lot", "fieldtype": "Link", "label": "To Lot", "options": "Lot", "width": 120},
		{"fieldname": "to_qty", "fieldtype": "Float", "label": "To Qty", "width": 100},
		{"fieldname": "to_uom", "fieldtype": "Link", "label": "To UOM", "options": "UOM", "width": 100},
		{
			"fieldname": "to_valuation_rate",
			"fieldtype": "Currency",
			"label": "To Valuation Rate",
			"width": 150,
		},
		{
			"fieldname": "to_valuation_amount",
			"fieldtype": "Currency",
			"label": "To Valuation Amount",
			"width": 160,
		},
		{
			"fieldname": "from_received_type",
			"fieldtype": "Link",
			"label": "From Received Type",
			"options": "GRN Item Type",
			"width": 150,
		},
		{
			"fieldname": "to_received_type",
			"fieldtype": "Link",
			"label": "To Received Type",
			"options": "GRN Item Type",
			"width": 150,
		},
	]


def get_data(filters):
	params = {}
	conditions = ["ic.docstatus = 1"]

	if filters.get("from_date"):
		conditions.append("ic.posting_date >= %(from_date)s")
		params["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("ic.posting_date <= %(to_date)s")
		params["to_date"] = filters.to_date

	if filters.get("lot"):
		conditions.append(
			"""
			EXISTS (
				SELECT 1
				FROM `tabItem Conversion Detail` lot_detail
				WHERE lot_detail.parent = ic.name
					AND lot_detail.parenttype = 'Item Conversion'
					AND lot_detail.lot = %(lot)s
			)
			"""
		)
		params["lot"] = filters.lot

	if filters.get("from_item"):
		conditions.append("ic.from_item = %(from_item)s")
		params["from_item"] = filters.from_item

	if filters.get("to_item"):
		conditions.append("ic.to_item = %(to_item)s")
		params["to_item"] = filters.to_item

	conversions = frappe.db.sql(
		"""
			SELECT
				ic.name AS item_conversion,
				ic.posting_date AS posting_date,
				ic.posting_time AS posting_time,
				ic.warehouse AS location,
				supplier.supplier_name AS location_name,
				ic.from_item AS from_item,
				ic.to_item AS to_item
			FROM `tabItem Conversion` ic
			LEFT JOIN `tabSupplier` supplier ON supplier.name = ic.warehouse
			WHERE {conditions}
			ORDER BY
				ic.posting_date DESC,
				ic.posting_time DESC,
				ic.name DESC
		""".format(conditions=" AND ".join(conditions)),
		params,
		as_dict=True,
	)

	data = []
	for conversion in conversions:
		from_items = get_conversion_items(conversion.item_conversion, "from_items")
		to_items = get_conversion_items(conversion.item_conversion, "to_items")
		row_count = max(len(from_items), len(to_items))

		for index in range(row_count):
			from_row = from_items[index] if index < len(from_items) else frappe._dict()
			to_row = to_items[index] if index < len(to_items) else frappe._dict()

			if filters.get("lot") and filters.lot not in [from_row.get("lot"), to_row.get("lot")]:
				continue

			data.append(get_report_row(conversion, from_row, to_row))

	return data


def get_conversion_items(item_conversion, parentfield):
	return frappe.db.sql(
		"""
			SELECT
				detail.item AS item_variant,
				line_variant.item AS item,
				detail.lot AS lot,
				detail.qty AS qty,
				detail.uom AS uom,
				detail.rate AS valuation_rate,
				detail.amount AS valuation_amount,
				detail.received_type AS received_type,
				detail.row_index AS row_index,
				detail.idx AS idx
			FROM `tabItem Conversion Detail` detail
			LEFT JOIN `tabItem Variant` line_variant ON line_variant.name = detail.item
			WHERE detail.parent = %(item_conversion)s
				AND detail.parenttype = 'Item Conversion'
				AND detail.parentfield = %(parentfield)s
			ORDER BY detail.row_index ASC, detail.idx ASC
		""",
		{"item_conversion": item_conversion, "parentfield": parentfield},
		as_dict=True,
	)


def get_report_row(conversion, from_row, to_row):
	return {
		"item_conversion": conversion.item_conversion,
		"posting_date": conversion.posting_date,
		"location": conversion.location,
		"location_name": conversion.location_name,
		"from_item": conversion.from_item,
		"from_item_variant": from_row.get("item_variant"),
		"from_lot": from_row.get("lot"),
		"from_qty": from_row.get("qty"),
		"from_uom": from_row.get("uom"),
		"from_valuation_rate": from_row.get("valuation_rate"),
		"from_valuation_amount": from_row.get("valuation_amount"),
		"to_item": conversion.to_item,
		"to_item_variant": to_row.get("item_variant"),
		"to_lot": to_row.get("lot"),
		"to_qty": to_row.get("qty"),
		"to_uom": to_row.get("uom"),
		"to_valuation_rate": to_row.get("valuation_rate"),
		"to_valuation_amount": to_row.get("valuation_amount"),
		"from_received_type": from_row.get("received_type"),
		"to_received_type": to_row.get("received_type"),
	}
