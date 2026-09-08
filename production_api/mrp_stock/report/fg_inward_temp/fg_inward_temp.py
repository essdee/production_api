"""Historical SMS receipts, independent of current stock and consumption.

Do not substitute current-stock reconciliation for historical inward quantities.
See README.md in this directory for legacy schema limitations.
"""

import frappe
import pymysql.cursors
from frappe import _
from frappe.utils import add_days, getdate
from production_api.mrp_stock.report.fg_stock_with_lot.fg_old_db_connection import get_connection
from production_api.mrp_stock.report.fg_stock_with_lot.fg_stock_with_lot import old_warehouse_mapping

SIZE_FIELDS = tuple(f"size{index}" for index in range(1, 11))


def execute(filters=None):
	filters = validate_filters(filters)
	return get_columns(), get_data(filters), _(
		"Legacy receipts: dates use creationdate and quantities are boxes, as in FG Stock With Lot. "
		"No cancellation field exists in the supplied tables; all matching stored entries are included. "
		"Item and Item Name both use the legacy name. Unmapped nonzero size slots are retained and labelled."
	)


def build_query(filters, location_id):
	conditions = ["entry.idlocation = %(location_id)s",
		"entry.creationdate >= %(start_date)s", "entry.creationdate < %(end_exclusive)s"]
	values = dict(location_id=location_id, start_date=filters.start_date, end_exclusive=filters.end_exclusive)
	for field, column in (("lot", "entry.lotnumber"), ("item", "item.name")):
		if filters.get(field):
			conditions.append(f"{column} = %({field})s")
			values[field] = filters[field]
	sizes = ", ".join(
		f"line.{field} AS {field}, sr.{field} AS enabled_{field}, st.{field} AS label_{field}"
		for field in SIZE_FIELDS)
	return f"""
		SELECT entry.idstockentry AS inward_reference, line.id AS line_id,
		entry.lotnumber AS lot, entry.creationdate AS inward_date,
		entry.blame_user AS created_by, item.name AS item, line.iditem AS legacy_item_id, {sizes}
		FROM stockentrydetails entry
		JOIN stockentryitems line ON line.idstockentry = entry.idstockentry
		LEFT JOIN iteminfo item ON item.iditem = line.iditem
		LEFT JOIN sizerange sr ON sr.idsize = item.sizerange
		LEFT JOIN sizetype st ON st.id = sr.idsizetype
		WHERE {' AND '.join(conditions)}
		ORDER BY entry.creationdate, entry.idstockentry, line.id
	""", values


def get_data(filters):
	location_id, warehouse, warehouse_name = old_warehouse_mapping(filters.warehouse)
	query, values = build_query(filters, location_id)
	connection = get_connection()
	try:
		with connection.cursor(pymysql.cursors.DictCursor) as cursor:
			cursor.execute(query, values)
			return expand_rows(cursor.fetchall(), filters, warehouse_name or warehouse)
	finally:
		connection.close()


def expand_rows(source_rows, filters, warehouse):
	result = []
	for source in source_rows:
		item = source.get("item") or f"[Legacy item ID {source['legacy_item_id']}]"
		for field in SIZE_FIELDS:
			qty = source.get(field)
			if qty is None or qty == 0:
				continue
			label = source.get(f"label_{field}")
			mapped = source.get(f"enabled_{field}") == 1 and label not in (None, "")
			variant = f"{item}-{label}" if mapped else f"{item} [unmapped {field}]"
			result.append(dict(inward_reference=source['inward_reference'], lot=source['lot'],
				inward_date=source['inward_date'], warehouse=warehouse, item=item, item_name=item,
				item_variant=variant, qty=qty, uom='Box', created_by=source['created_by']))
	return result


def validate_filters(filters=None):
	filters = frappe._dict(filters or {})
	for field, label in (
		("start_date", _("Start Date")),
		("end_date", _("End Date")),
		("warehouse", _("Warehouse")),
	):
		if not filters.get(field):
			frappe.throw(_("{0} is required").format(label))
	start, end = getdate(filters.start_date), getdate(filters.end_date)
	if start > end:
		frappe.throw(_("Start Date cannot be after End Date"))
	# Query timestamps with >= start and < next day to include the entire end day.
	return frappe._dict(
		start_date=start,
		end_exclusive=getdate(add_days(end, 1)),
		warehouse=filters.warehouse,
		lot=filters.get("lot"),
		item=filters.get("item"),
	)


def get_columns():
	# Legacy identifiers are Data, not broken links into the current database.
	return [
		{"fieldname": field, "label": _(label), "fieldtype": kind, "width": width}
		for field, label, kind, width in (
			("inward_reference", "FG Inward Reference", "Data", 160),
			("lot", "Lot Number", "Data", 140),
			("inward_date", "Stock Inward Date", "Datetime", 170),
			("warehouse", "Warehouse", "Data", 160),
			("item", "Item", "Data", 140),
			("item_name", "Item Name", "Data", 180),
			("item_variant", "Item Variant", "Data", 160),
			("qty", "Received Quantity", "Float", 140),
			("uom", "UOM", "Data", 90),
			("created_by", "Created By", "Data", 180),
		)
	]
