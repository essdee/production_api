# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from pypika import Order


def execute(filters=None):
    columns, data = [], []
    validate_filters(filters)
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def validate_filters(filters):
    if filters.get('from_date') and filters.get('to_date'):
        if filters.get('from_date') > filters.get('to_date'):
            frappe.throw('From Date cannot be greater than To Date')

def get_columns():
    columns = [
        {
            "fieldname": "name",
            "label": "GRN",
            "fieldtype": "Link",
            "options": "Goods Received Note",
            "width": 100
        },
        {
            "fieldname": "po_name",
            "label": "PO",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 100
        },
        {
            "fieldname": "supplier",
            "label": "Supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 100
        },
        {
            "fieldname": "supplier_name",
            "label": "Supplier Name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "grn_date",
            "label": "GRn Date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "delivery_location",
            "label": "Delivery Location",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 100
        },
        {
            "fieldname": "delivery_location_name",
            "label": "Delivery Location Name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "lot",
            "label": "Lot",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "item_variant",
            "label": "Item Variant",
            "fieldtype": "Link",
            "options": "Item Variant",
            "width": 150
        },
        {
            "fieldname": "received_qty",
            "label": "Received Qty",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "uom",
            "label": "UOM",
            "fieldtype": "Link",
            "options": "UOM",
            "width": 100
        },
        {
            "fieldname": "po_qty",
            "label": "Purchase Order Quantity",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "po_rate",
            "label": "Purchase Order Rate",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "fieldname": "expected_delivery_date",
            "label": "Expected Delivery Date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "delivery_date",
            "label": "Delivery Date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "status",
            "label": "GRN Status",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "comments",
            "label": "Comments",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "modified",
            "label": "Modified",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "modified_by",
            "label": "Modified By",
            "fieldtype": "Link",
            "options": "User",
            "width": 100
        },
    ]

    return columns


def get_data(filters):
    grn_item = frappe.qb.DocType('Goods Received Note Item')
    po_item = frappe.qb.DocType('Purchase Order Item')
    grn = frappe.qb.DocType('Goods Received Note')
    po = frappe.qb.DocType('Purchase Order')
    supplier = frappe.qb.DocType('Supplier')
    item_variant = frappe.qb.DocType('Item Variant')

    q = (
        frappe.qb.from_(grn_item)
        .left_join(po_item)
        .on(grn_item.ref_docname == po_item.name)
        .left_join(grn)
        .on(grn_item.parent == grn.name)
        .left_join(po)
        .on(po_item.parent == po.name)
        .left_join(item_variant)
        .on(po_item.item_variant == item_variant.name)
        .left_join(supplier)
        .on(grn.delivery_location == supplier.name)
        .select(
            grn.name,
            po.name.as_('po_name'),
            po.supplier,
            po.supplier_name,
            grn.grn_date,
            grn.delivery_location,
            supplier.supplier_name.as_('delivery_location_name'),
            grn_item.item_variant,
            grn_item.quantity.as_('received_qty'),
            grn_item.uom,
            grn_item.lot,
            po_item.delivery_date.as_('expected_delivery_date'),
            po_item.qty.as_("po_qty"),
            po_item.rate.as_("po_rate"),
            grn.delivery_date,
            grn.docstatus.as_('status'),
            grn_item.comments,
            grn.modified,
            grn.modified_by,
        ).where(grn.against == "Purchase Order")
    )

    if filters.get('from_date'):
        q = q.where(grn.grn_date >= filters.get('from_date'))
    if filters.get('to_date'):
        q = q.where(grn.grn_date <= filters.get('to_date'))
    if filters.get('supplier'):
        q = q.where(grn.supplier == filters.get('supplier'))
    if filters.get('item'):
        q = q.where(item_variant.item == filters.get('item'))
    if filters.get('lot'):
        q = q.where(grn_item.lot == filters.get('lot'))
    if filters.get('grn_status'):
        q = q.where(grn.docstatus == filters.get('grn_status'))
    if filters.get('delivery_location'):
        q = q.where(grn.delivery_location == filters.get('delivery_location'))

    q = (
        q.orderby(po.modified, order=Order.desc)
        .orderby(po_item.idx, order=Order.asc)
        .orderby(grn_item.creation, order=Order.asc)
    )
    data = q.run(as_dict=True)

    return data
    # return compute_data(data)


def compute_data(data):
    # Compute the balance qty in a sequential manner
    # the data is sorted so go by each row and compute the balance qty grouped by name and po_item_name

    balance_qty = 0
    current_po = None
    current_po_item = None
    for row in data:
        if current_po != row.name or current_po_item != row.po_item_name:
            balance_qty = row.qty
            current_po = row.name
            current_po_item = row.po_item_name

        if row.grn_status == 1:
            balance_qty -= row.received_qty
        row.balance_qty = balance_qty

    return data
