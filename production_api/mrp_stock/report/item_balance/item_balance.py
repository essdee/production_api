# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data

def get_columns(filters):
	return [
		{
			"label": _("Item"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("Item Variant"),
			"fieldname": "item_variant",
			"fieldtype": "Link",
			"options": "Item Variant",
			"width": 150,
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 120,
		},
		{
			"label": _("Warehouse Name"),
			"fieldname": "warehouse_name",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Lot"),
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"width": 150,
		},
		{
			"fieldname":"received_type",
			"fieldtype":"Link",
			"label":_("Received Type"),
			"options":"GRN Item Type",
			"width":80,
		},
		{
			"label": _("Balance Qty"),
			"fieldname": "actual_qty",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("UOM"),
			"fieldname": "stock_uom",
			"fieldtype": "Data",
			"width": 140,
		},
	]

def get_data(filters):
	bin = frappe.qb.DocType("Bin")
	variant = frappe.qb.DocType("Item Variant")
	supplier = frappe.qb.DocType("Supplier")

	query = (
		frappe.qb.from_(bin).from_(variant).from_(supplier)
		.select(
			variant.item.as_("item"),
			bin.item_code.as_("item_variant"),
			bin.warehouse.as_("warehouse"),
			supplier.supplier_name.as_("warehouse_name"),
			bin.lot.as_("lot"),
			bin.received_type,
			bin.actual_qty,
			bin.stock_uom,
		)
		.where((bin.item_code == variant.name) & (bin.warehouse == supplier.name))
	)

	if warehouse := filters.get("warehouse"):
		query = query.where(bin.warehouse == warehouse)
	if lot := filters.get("lot"):
		query = query.where(bin.lot == lot)
	if item_variant := filters.get("item_variant"):
		query = query.where(bin.item_code == item_variant)
	if item := filters.get("item"):
		query = query.where(variant.item == item)

	if filters.get("remove_zero_balance_item"):
		query = query.where(bin.actual_qty != 0)
	
	return query.run(as_dict=True)
