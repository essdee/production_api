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
    if filters.get('date_based_on'):
        if filters.get('from_date') and filters.get('to_date'):
            if filters.get('from_date') > filters.get('to_date'):
                frappe.throw('From Date cannot be greater than To Date')


def get_columns():
    columns = [
        {
            "fieldname": "name",
            "label": "PO Number",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 115
        },
        {
            "fieldname": "po_date",
            "label": "PO Date",
            "fieldtype": "Date",
            "width": 100
        },
        # {
        #     "fieldname": "supplier",
        #     "label": "Supplier",
        #     "fieldtype": "Link",
        #     "options": "Supplier",
        #     "width": 100
        # },
        {
            "fieldname": "supplier_name",
            "label": "Supplier Name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "item_variant",
            "label": "Item Variant",
            "fieldtype": "Link",
            "options": "Item Variant",
            "width": 150
        },
        {
            "fieldname": "qty",
            "label": "Qty",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "delivered_qty",
            "label": "Delivered Qty",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "cancelled_qty",
            "label": "Cancelled Qty",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "pending_qty",
            "label": "Pending Qty",
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
            "fieldname": "delivery_date",
            "label": "Delivery Date",
            "fieldtype": "Date",
            "width": 100
        },
        # {
        #     "fieldname": "delivery_location",
        #     "label": "Delivery Location",
        #     "fieldtype": "Link",
        #     "options": "Supplier",
        #     "width": 100
        # },
        {
            "fieldname": "delivery_location_name",
            "label": "Delivery Location Name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "rate",
            "label": "Rate",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "discount_percentage",
            "label": "Discount %",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "lot",
            "label": "Lot",
            "fieldtype": "Link",
            "options": "Lot",
            "width": 100
        },
        {
            "fieldname": "status",
            "label": "Status",
            "fieldtype": "Data",
            "width": 200
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
        {
            "fieldname": "creation",
            "label": "Creation",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "comments",
            "label": "Comments",
            "fieldtype": "Data",
            "width": 100
        },
    ]
    return columns


def get_data(filters):
    po_item = frappe.qb.DocType('Purchase Order Item')
    po = frappe.qb.DocType('Purchase Order')
    supplier = frappe.qb.DocType('Supplier')
    item_variant = frappe.qb.DocType('Item Variant')

    query = (
        frappe.qb.from_(po_item)
        .left_join(po)
        .on(po_item.parent == po.name)
        .left_join(supplier)
        .on(po_item.delivery_location == supplier.name)
        .left_join(item_variant)
        .on(po_item.item_variant == item_variant.name)
        .select(
            po_item.item_variant,
            po_item.qty,
            po_item.pending_qty,
            po_item.cancelled_qty,
            (po_item.qty - po_item.pending_qty - po_item.cancelled_qty).as_('delivered_qty'),
            po_item.uom,
            po_item.rate,
            po_item.discount_percentage,
            po_item.delivery_location,
            supplier.supplier_name.as_('delivery_location_name'),
            po_item.delivery_date,
            po_item.lot,
            po_item.comments,
            po.name,
            po.creation,
            po.modified,
            po.modified_by,
            po.supplier,
            po.supplier_name,
            po.po_date,
            po.comments,
            po.status
        )
    )
    if (filters.get('docstatus')):
        query = query.where(po.docstatus == filters.get('docstatus'))
    if (filters.get('item_variant')):
        query = query.where(po_item.item_variant == filters.get('item_variant'))
    if (filters.get('item')):
        query = query.where(item_variant.item == filters.get('item'))
    if (filters.get('supplier')):
        query = query.where(po.supplier == filters.get('supplier'))
    if (filters.get('delivery_location')):
        query = query.where(po_item.delivery_location == filters.get('delivery_location'))
    if (filters.get('purchase_order')):
        query = query.where(po.name == filters.get('purchase_order'))
    if (filters.get('lot')):
        query = query.where(po_item.lot == filters.get('lot'))
    if (filters.get('status')):
        query = query.where(po.status == filters.get('status'))
    if (filters.get('open_status')):
        query = query.where(po.open_status == filters.get('open_status'))
    if (filters.get('date_based_on')):
        if filters.get('date_based_on') == 'Posting Date':
            if filters.get('from_date'):
                query = query.where(po.po_date >= filters.get('from_date'))
            if filters.get('to_date'):
                query = query.where(po.po_date <= filters.get('to_date'))
        elif filters.get('date_based_on') == 'Delivery Date':
            if filters.get('from_date'):
                query = query.where(po_item.delivery_date >= filters.get('from_date'))
            if filters.get('to_date'):
                query = query.where(po_item.delivery_date <= filters.get('to_date'))

    query = query.orderby(po.modified, order=Order.desc)
    data = query.run(as_dict=True)

    return data
