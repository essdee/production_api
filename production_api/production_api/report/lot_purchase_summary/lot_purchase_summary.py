# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import CombineDatetime, Max, Sum


def execute(filters=None):
	columns, data = [], []
	columns = get_columns()
	data = get_data(filters)
	stock_data = get_stock_data(filters)
	pending_po_data = get_po_qty(filters, 1)
	data = compute(data, stock_data, pending_po_data)
	return columns, data

def get_key(item, lot):
	return tuple([item, lot])

def compute(data, stock_data, pending_po_data):
	il_map = {}
	for d in data:
		group_by_key = get_key(d.item, d.lot)
		if group_by_key not in il_map:
			il_map[group_by_key] = frappe._dict(
				{
					"item": d.item,
					"parent_item": d.parent_item,
					"lot": d.lot,
					"required_qty": d.required_qty,
					"stock_qty": 0.0,
					"po_pending_qty": 0.0,
				}
			)
		else:
			il_map[group_by_key].required_qty += d.required_qty
	for stock in stock_data:
		group_by_key = get_key(stock.item, stock.lot)
		if group_by_key not in il_map:
			il_map[group_by_key] = frappe._dict(
				{
					"item": stock.item,
					"parent_item": stock.parent_item,
					"lot": stock.lot,
					"required_qty": 0.0,
					"stock_qty": stock.qty,
					"po_pending_qty": 0.0,
				}
			)
		else:
			il_map[group_by_key].stock_qty += stock.qty
	for po in pending_po_data:
		group_by_key = get_key(po.item, po.lot)
		if group_by_key not in il_map:
			il_map[group_by_key] = frappe._dict(
				{
					"item": po.item,
					"parent_item": po.parent_item,
					"lot": po.lot,
					"required_qty": 0.0,
					"stock_qty": 0.0,
					"po_pending_qty": po.qty,
				}
			)
		else:
			il_map[group_by_key].po_pending_qty += po.qty
	data = []
	for key in il_map:
		d = {}
		d.update(il_map[key])
		data.append(d)
	return data

def get_columns():
	return [
		{
            "fieldname": "lot",
            "label": "Lot",
            "fieldtype": "Link",
            "options": "Lot",
            "width": 200,
        },
		{
            "fieldname": "parent_item",
            "label": "Parent Item",
            "fieldtype": "Link",
            "options": "Item",
            "width": 200,
        },
		{
            "fieldname": "item",
            "label": "Item",
            "fieldtype": "Link",
            "options": "Item Variant",
            "width": 200,
        },
		{
            "fieldname": "required_qty",
            "label": "Required Qty",
            "fieldtype": "Float",
            "width": 100,
        },
		{
            "fieldname": "stock_qty",
            "label": "Stock Qty",
            "fieldtype": "Float",
            "width": 100,
        },
		{
            "fieldname": "po_pending_qty",
            "label": "PO Pending Qty",
            "fieldtype": "Float",
            "width": 100,
        },
		{
            "fieldname": "po_draft_qty",
            "label": "PO Draft Qty",
            "fieldtype": "Float",
            "width": 100,
        },
	]

def get_data(filters):
	bom = frappe.qb.DocType('Lot BOM')
	item_variant = frappe.qb.DocType('Item Variant')
	query = frappe.qb.from_(bom).from_(item_variant).select(
		bom.parent.as_('lot'),
		bom.item_name.as_('item'),
		item_variant.item.as_('parent_item'),
		bom.required_qty,
	).where(bom.item_name == item_variant.name)

	if filters.get('lot'):
		query = query.where(bom.parent == filters.get('lot'))
	if filters.get('item'):
		query = query.where(bom.item_name == filters.get('item'))
	if filters.get('parent_item'):
		query = query.where(item_variant.item == filters.get('parent_item'))

	return query.run(as_dict=True)

def get_stock_data(filters):
	sle = frappe.qb.DocType("Stock Ledger Entry")
	supplier = frappe.qb.DocType("Supplier")
	item_variant = frappe.qb.DocType('Item Variant')
	query1 = (
		frappe.qb.from_(sle)
		.where(
			(sle.docstatus < 2)
			& (sle.is_cancelled == 0)
		)
		.groupby(sle.item)
		.groupby(sle.warehouse)
		.groupby(sle.lot)
		.select(
			sle.item,
			sle.warehouse,
			sle.lot,
			Max(CombineDatetime(sle.posting_date, sle.posting_time)).as_("date"),
		)
	)

	if filters.get('lot'):
		query1 = query1.where(sle.lot == filters.get('lot'))

	query = (
		frappe.qb.from_(sle).from_(query1).from_(supplier).from_(item_variant)
		.select(
			sle.item,
			item_variant.item.as_('parent_item'),
			sle.warehouse,
			supplier.supplier_name.as_('warehouse_name'),
			sle.lot,
			sle.qty_after_transaction.as_('qty')
		)
		.where(
			(sle.item == query1.item)
			& (sle.warehouse == query1.warehouse)
			& (sle.lot == query1.lot)
			& (CombineDatetime(sle.posting_date, sle.posting_time) == query1.date)
			& (supplier.name == sle.warehouse)
			& (sle.item == item_variant.name)
		)
	)
	if filters.get('item'):
		query = query.where(sle.item == filters.get('item'))
	if filters.get('parent_item'):
		query = query.where(item_variant.item == filters.get('parent_item'))

	d = query.run(as_dict=True)
	return d

def get_po_qty(filters, docstatus):
	po = frappe.qb.DocType("Purchase Order")
	po_item = frappe.qb.DocType("Purchase Order Item")
	item_variant = frappe.qb.DocType('Item Variant')

	query = (
		frappe.qb.from_(po).from_(po_item).from_(item_variant)
		.where(
			(po.name == po_item.parent)
			& (po.docstatus == docstatus)
			& (po.open_status == 'open')
			& (po_item.item_variant == item_variant.name)
		)
		.groupby(po_item.item_variant)
		.groupby(po_item.lot)
		.groupby(item_variant.item)
		.select(
			po_item.item_variant.as_('item'),
			po_item.lot,
			item_variant.item.as_('parent_item'),
			Sum(po_item.pending_qty).as_('qty')
		)
	)

	if filters.get('lot'):
		query = query.where(po_item.lot == filters.get('lot'))
	if filters.get('item'):
		query = query.where(po_item.item_variant == filters.get('item'))
	if filters.get('parent_item'):
		query = query.where(item_variant.item == filters.get('parent_item'))
	
	print(query)
	d = query.run(as_dict = True)
	return d