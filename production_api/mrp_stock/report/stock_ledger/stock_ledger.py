# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.query_builder.functions import CombineDatetime
from frappe.utils import cint, flt

def execute(filters=None):
	include_uom = filters.get("include_uom")
	columns = get_columns(filters)
	items = get_items(filters)
	sl_entries = get_stock_ledger_entries(filters, items)
	item_details = get_item_details(items, sl_entries, include_uom)
	opening_row = get_opening_balance(filters, columns, sl_entries)
	precision = 3

	data = []
	conversion_factors = []
	if opening_row:
		data.append(opening_row)
		conversion_factors.append(0)

	actual_qty = stock_value = 0
	if opening_row:
		actual_qty = opening_row.get("qty_after_transaction")
		stock_value = opening_row.get("stock_value")

	available_serial_nos = {}
	# inventory_dimension_filters_applied = check_inventory_dimension_filters_applied(filters)

	for sle in sl_entries:
		item_detail = item_details[sle.item]

		sle.update(item_detail)

		# if filters.get("batch_no") or inventory_dimension_filters_applied:
		# 	actual_qty += flt(sle.actual_qty, precision)
		# 	stock_value += sle.stock_value_difference

		# 	if sle.voucher_type == "Stock Reconciliation" and not sle.actual_qty:
		# 		actual_qty = sle.qty_after_transaction
		# 		stock_value = sle.stock_value

		# 	sle.update({"qty_after_transaction": actual_qty, "stock_value": stock_value})

		sle.update({"in_qty": max(sle.qty, 0), "out_qty": min(sle.qty, 0)})

		# if sle.serial_no:
		# 	update_available_serial_nos(available_serial_nos, sle)

		if sle.actual_qty:
			sle["in_out_rate"] = flt(sle.stock_value_difference / sle.actual_qty, precision)

		elif sle.voucher_type == "Stock Reconciliation":
			sle["in_out_rate"] = sle.valuation_rate

		data.append(sle)

		if include_uom:
			conversion_factors.append(item_detail.conversion_factor)

	# update_included_uom_in_report(columns, data, include_uom, conversion_factors)
	return columns, data


def get_columns(filters):
	columns = [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Datetime", "width": 150},
		{
			"label": _("Lot"),
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"width": 100,
		},
		{
			"label": _("Item"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 100,
		},
		{"label": _("Item Name"), "fieldname": "item_name", "width": 100},
		{
			"label": _("Stock UOM"),
			"fieldname": "stock_uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 90,
		},
	]

	columns.extend(
		[
			{
				"label": _("In Qty"),
				"fieldname": "in_qty",
				"fieldtype": "Float",
				"width": 80,
				"convertible": "qty",
			},
			{
				"label": _("Out Qty"),
				"fieldname": "out_qty",
				"fieldtype": "Float",
				"width": 80,
				"convertible": "qty",
			},
			{
				"label": _("Balance Qty"),
				"fieldname": "qty_after_transaction",
				"fieldtype": "Float",
				"width": 100,
				"convertible": "qty",
			},
			{
				"label": _("Voucher #"),
				"fieldname": "voucher_no",
				"fieldtype": "Dynamic Link",
				"options": "voucher_type",
				"width": 150,
			},
			{
				"label": _("Warehouse"),
				"fieldname": "warehouse_name",
				"fieldtype": "Data",
				"options": "Supplier",
				"width": 150,
			},
			# {
			# 	"label": _("Item Group"),
			# 	"fieldname": "item_group",
			# 	"fieldtype": "Link",
			# 	"options": "Item Group",
			# 	"width": 100,
			# },
			# {
			# 	"label": _("Brand"),
			# 	"fieldname": "brand",
			# 	"fieldtype": "Link",
			# 	"options": "Brand",
			# 	"width": 100,
			# },
			# {"label": _("Description"), "fieldname": "description", "width": 200},
			{
				"label": _("Incoming Rate"),
				"fieldname": "rate",
				"fieldtype": "Currency",
				"width": 110,
				"options": "Company:company:default_currency",
				"convertible": "rate",
			},
			{
				"label": _("Avg Rate (Balance Stock)"),
				"fieldname": "valuation_rate",
				"fieldtype": "Currency",
				"width": 180,
				"options": "Company:company:default_currency",
				"convertible": "rate",
			},
			{
				"label": _("Valuation Rate"),
				"fieldname": "in_out_rate",
				"fieldtype": "Currency",
				"width": 140,
				"options": "Company:company:default_currency",
				"convertible": "rate",
			},
			{
				"label": _("Balance Value"),
				"fieldname": "stock_value",
				"fieldtype": "Currency",
				"width": 110,
				"options": "Company:company:default_currency",
			},
			{
				"label": _("Value Change"),
				"fieldname": "stock_value_difference",
				"fieldtype": "Currency",
				"width": 110,
				"options": "Company:company:default_currency",
			},
			{"label": _("Voucher Type"), "fieldname": "voucher_type", "width": 110},
			{
				"label": _("Voucher #"),
				"fieldname": "voucher_no",
				"fieldtype": "Dynamic Link",
				"options": "voucher_type",
				"width": 100,
			},
		]
	)

	return columns


def get_stock_ledger_entries(filters, items):
	sle = frappe.qb.DocType("Stock Ledger Entry")
	supplier = frappe.qb.DocType("Supplier")
	query = (
		frappe.qb.from_(sle).from_(supplier)
		.select(
			sle.item,
			CombineDatetime(sle.posting_date, sle.posting_time).as_("date"),
			sle.warehouse,
			supplier.supplier_name.as_('warehouse_name'),
			sle.posting_date,
			sle.posting_time,
			sle.qty,
			sle.rate,
			sle.valuation_rate,
			sle.voucher_type,
			sle.qty_after_transaction,
			sle.stock_value_difference,
			sle.voucher_no,
			sle.stock_value,
			sle.lot,
		)
		.where(
			(sle.docstatus < 2)
			& (sle.is_cancelled == 0)
			& (sle.posting_date[filters.from_date : filters.to_date])
			& (supplier.name == sle.warehouse)
		)
		.orderby(CombineDatetime(sle.posting_date, sle.posting_time))
		.orderby(sle.creation)
	)

	if items:
		query = query.where(sle.item.isin(items))

	for field in ["voucher_no", "lot", "warehouse"]:
		if filters.get(field):
			query = query.where(sle[field] == filters.get(field))

	# query = apply_warehouse_filter(query, sle, filters)

	return query.run(as_dict=True)


def get_items(filters):
	item_variant = frappe.qb.DocType("Item Variant")
	item = frappe.qb.DocType("Item")
	query = frappe.qb.from_(item_variant).from_(item).select(item_variant.name)
	conditions = [item.name == item_variant.item]

	if parent_item_code := filters.get("parent_item"):
		conditions.append(item.name == parent_item_code)
	elif item_code := filters.get("item"):
		conditions.append(item_variant.name == item_code)
	else:
		if brand := filters.get("brand"):
			conditions.append(item.brand == brand)
		if item_group := filters.get("item_group"):
			if condition := get_item_group_condition(item_group, item):
				conditions.append(condition)

	items = []
	if conditions:
		for condition in conditions:
			query = query.where(condition)
		items = [r[0] for r in query.run()]

	return items


def get_item_details(items, sl_entries, include_uom):
	item_details = {}
	if not items:
		items = list(set(d.item for d in sl_entries))

	if not items:
		return item_details

	item = frappe.qb.DocType("Item")
	item_variant = frappe.qb.DocType("Item Variant")
	query = (
		frappe.qb.from_(item_variant).from_(item)
		.select(item_variant.name, item.name.as_('item_name'), item.brand, item.default_unit_of_measure.as_('stock_uom'), item.item_group)
		.where((item_variant.name.isin(items)) & (item_variant.item == item.name))
	)

	res = query.run(as_dict=True)

	for item_variant in res:
		item_details.setdefault(item_variant.name, item_variant)

	return item_details


def get_sle_conditions(filters):
	conditions = []
	if filters.get("warehouse"):
		warehouse_condition = get_warehouse_condition(filters.get("warehouse"))
		if warehouse_condition:
			conditions.append(warehouse_condition)
	if filters.get("voucher_no"):
		conditions.append("voucher_no=%(voucher_no)s")
	if filters.get("lot"):
		conditions.append("lot=%(lot)s")

	return "and {}".format(" and ".join(conditions)) if conditions else ""


def get_opening_balance(filters, columns, sl_entries):
	if not (filters.item_code and filters.warehouse and filters.from_date):
		return

	from production_api.mrp_stock.stock_ledger import get_previous_sle

	last_entry = get_previous_sle(
		{
			"item_code": filters.item_code,
			"warehouse_condition": get_warehouse_condition(filters.warehouse),
			"posting_date": filters.from_date,
			"posting_time": "00:00:00",
		}
	)

	# check if any SLEs are actually Opening Stock Reconciliation
	for sle in list(sl_entries):
		if (
			sle.get("voucher_type") == "Stock Reconciliation"
			and sle.posting_date == filters.from_date
			and frappe.db.get_value("Stock Reconciliation", sle.voucher_no, "purpose") == "Opening Stock"
		):
			last_entry = sle
			sl_entries.remove(sle)

	row = {
		"item_code": _("'Opening'"),
		"qty_after_transaction": last_entry.get("qty_after_transaction", 0),
		"valuation_rate": last_entry.get("valuation_rate", 0),
		"stock_value": last_entry.get("stock_value", 0),
	}

	return row


def get_warehouse_condition(warehouse):
	warehouse_details = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"], as_dict=1)
	if warehouse_details:
		return (
			" exists (select name from `tabWarehouse` wh \
			where wh.lft >= %s and wh.rgt <= %s and warehouse = wh.name)"
			% (warehouse_details.lft, warehouse_details.rgt)
		)

	return ""


def get_item_group_condition(item_group, item_table=None):
	item_group_details = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=1)
	if item_group_details:
		if item_table:
			ig = frappe.qb.DocType("Item Group")
			return item_table.item_group.isin(
				(
					frappe.qb.from_(ig)
					.select(ig.name)
					.where(
						(ig.lft >= item_group_details.lft)
						& (ig.rgt <= item_group_details.rgt)
						& (item_table.item_group == ig.name)
					)
				)
			)
		else:
			return (
				"item.item_group in (select ig.name from `tabItem Group` ig \
				where ig.lft >= %s and ig.rgt <= %s and item.item_group = ig.name)"
				% (item_group_details.lft, item_group_details.rgt)
			)
