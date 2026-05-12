# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date") and filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be greater than To Date"))


def get_columns():
	return [
		{"fieldname": "source_doctype", "fieldtype": "Data", "label": "Source Type", "width": 130},
		{"fieldname": "source_name", "fieldtype": "Dynamic Link", "options": "source_doctype", "label": "Source ID", "width": 170},
		{"fieldname": "against", "fieldtype": "Data", "label": "Against", "width": 130},
		{"fieldname": "against_id", "fieldtype": "Dynamic Link", "options": "against", "label": "Against ID", "width": 170},
		{"fieldname": "from_location", "fieldtype": "Link", "options": "Supplier", "label": "From Location", "width": 130},
		{"fieldname": "from_location_name", "fieldtype": "Data", "label": "From Location Name", "width": 200},
		{"fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "label": "Supplier", "width": 130},
		{"fieldname": "supplier_name", "fieldtype": "Data", "label": "Supplier Name", "width": 200},
		{"fieldname": "lot", "fieldtype": "Link", "options": "Lot", "label": "Lot", "width": 120},
		{"fieldname": "process", "fieldtype": "Link", "options": "Process", "label": "Process", "width": 140},
		{"fieldname": "item", "fieldtype": "Link", "options": "Item", "label": "Item", "width": 180},
		{"fieldname": "item_variant", "fieldtype": "Link", "options": "Item Variant", "label": "Item Variant", "width": 220},
		{"fieldname": "quantity", "fieldtype": "Float", "label": "Quantity", "width": 110},
		{"fieldname": "received_type", "fieldtype": "Link", "options": "GRN Item Type", "label": "Received Type", "width": 130},
		{"fieldname": "remarks", "fieldtype": "Data", "label": "Remarks", "width": 200},
	]


def get_data(filters):
	data = []
	data.extend(get_delivery_challan_rows(filters))
	data.extend(get_stock_entry_rows(filters))
	data.sort(
		key=lambda row: (
			row.get("posting_date") or "",
			row.get("posting_time") or "",
			row.get("source_name") or "",
		),
		reverse=True,
	)
	return data


def get_delivery_challan_rows(filters):
	params = {}
	conditions = [
		"dc.docstatus = 1",
		"dci.docstatus = 1",
		"dci.delivered_quantity > 0",
	]

	if filters.get("from_date"):
		conditions.append("dc.posting_date >= %(from_date)s")
		params["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("dc.posting_date <= %(to_date)s")
		params["to_date"] = filters.to_date

	if filters.get("lot"):
		conditions.append("(dci.lot = %(lot)s OR dc.lot = %(lot)s)")
		params["lot"] = filters.lot

	if filters.get("from_location"):
		conditions.append("dc.from_location = %(from_location)s")
		params["from_location"] = filters.from_location

	if filters.get("supplier"):
		conditions.append("dc.supplier = %(supplier)s")
		params["supplier"] = filters.supplier

	if filters.get("item"):
		conditions.append("iv.item = %(item)s")
		params["item"] = filters.item

	query = """
		SELECT
			'Work Order' AS against,
			dc.work_order AS against_id,
			'Delivery Challan' AS source_doctype,
			dc.name AS source_name,
			dc.from_location AS from_location,
			dc.from_location_name AS from_location_name,
			dc.supplier AS supplier,
			dc.supplier_name AS supplier_name,
			COALESCE(dci.lot, dc.lot) AS lot,
			dc.process_name AS process,
			iv.item AS item,
			dci.item_variant AS item_variant,
			dci.delivered_quantity AS quantity,
			dci.item_type AS received_type,
			dci.comments AS remarks,
			dc.posting_date AS posting_date,
			dc.posting_time AS posting_time
		FROM `tabDelivery Challan Item` dci
		INNER JOIN `tabDelivery Challan` dc ON dc.name = dci.parent
		LEFT JOIN `tabItem Variant` iv ON iv.name = dci.item_variant
		WHERE {conditions}
	""".format(conditions=" AND ".join(conditions))

	return frappe.db.sql(query, params, as_dict=True)


def get_stock_entry_rows(filters):
	params = {}
	conditions = [
		"se.docstatus = 1",
		"sed.docstatus = 1",
		"se.purpose = 'Material Issue'",
		"IFNULL(se.against, '') != ''",
	]
	supplier_expression = "se.transfer_supplier"

	if filters.get("from_date"):
		conditions.append("se.posting_date >= %(from_date)s")
		params["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("se.posting_date <= %(to_date)s")
		params["to_date"] = filters.to_date

	if filters.get("lot"):
		conditions.append("sed.lot = %(lot)s")
		params["lot"] = filters.lot

	if filters.get("from_location"):
		conditions.append("se.from_warehouse = %(from_location)s")
		params["from_location"] = filters.from_location

	if filters.get("supplier"):
		conditions.append(supplier_expression + " = %(supplier)s")
		params["supplier"] = filters.supplier

	if filters.get("item"):
		conditions.append("iv.item = %(item)s")
		params["item"] = filters.item

	query = """
		SELECT
			se.against AS against,
			se.against_id AS against_id,
			'Stock Entry' AS source_doctype,
			se.name AS source_name,
			se.from_warehouse AS from_location,
			from_supplier.supplier_name AS from_location_name,
			{supplier_expression} AS supplier,
			supplier.supplier_name AS supplier_name,
			sed.lot AS lot,
			wo.process_name AS process,
			iv.item AS item,
			sed.item AS item_variant,
			sed.qty AS quantity,
			sed.received_type AS received_type,
			sed.remarks AS remarks,
			se.posting_date AS posting_date,
			se.posting_time AS posting_time
		FROM `tabStock Entry Detail` sed
		INNER JOIN `tabStock Entry` se ON se.name = sed.parent
		LEFT JOIN `tabSupplier` from_supplier ON from_supplier.name = se.from_warehouse
		LEFT JOIN `tabSupplier` supplier ON supplier.name = {supplier_expression}
		LEFT JOIN `tabWork Order` wo ON se.against = 'Work Order' AND wo.name = se.against_id
		LEFT JOIN `tabItem Variant` iv ON iv.name = sed.item
		WHERE {conditions}
	""".format(
		conditions=" AND ".join(conditions),
		supplier_expression=supplier_expression,
	)

	return frappe.db.sql(query, params, as_dict=True)
