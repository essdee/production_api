# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from pypika import Order


def execute(filters=None):
    columns, data = [], []
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    columns = [
        {
            "fieldname": "name",
            "label": "Name",
            "fieldtype": "Link",
            "options": "Purchase Order",
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
            "fieldname": "po_date",
            "label": "PO Date",
            "fieldtype": "Date",
            "width": 100
		},
		{
            "fieldname": "qty",
            "label": "Qty",
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
            "fieldname": "cancelled_qty",
            "label": "Cancelled Qty",
            "fieldtype": "Float",
            "width": 100
		},
        {
            "fieldname": "received_qty",
            "label": "Received Qty",
            "fieldtype": "Float",
            "width": 100
		},
        {
            "fieldname": "balance_qty",
            "label": "Balance Qty",
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
            "fieldname": "rate",
            "label": "Rate",
            "fieldtype": "Currency",
            "width": 100
		},
        {
            "fieldname": "delivery_date",
            "label": "Delivery Date",
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
            "fieldname": "grn_status",
            "label": "GRN Status",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "po_status",
            "label": "PO Status",
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
        .left_join(supplier)
        .on(grn.delivery_location == supplier.name)
        .left_join(item_variant)
        .on(po_item.item_variant == item_variant.name)
        .select(
            po.name,
            po_item.item_variant,
            po.supplier,
            po.supplier_name,
            po.po_date,
            po_item.qty,
            po_item.pending_qty,
            po_item.cancelled_qty,
            grn_item.quantity.as_('received_qty'),
            po_item.uom,
            po_item.rate,
            grn.delivery_location,
            grn.delivery_date,
            supplier.supplier_name.as_('delivery_location_name'),
            grn.name.as_('grn_name'),
            grn.grn_date,
            grn_item.lot,
            grn_item.comments,
            grn.creation,
            grn.modified,
            grn.modified_by,
            # grn.comments,
            grn.docstatus.as_('grn_status'),
            po.status.as_('po_status'),
            po_item.name.as_('po_item_name'),
        )
    )
    # .desc(), po_item.idx.asc(), grn_item.creation.asc()

    q = q.orderby(po.modified, order=Order.desc)
    q = q.orderby(po_item.idx, order=Order.asc)
    q = q.orderby(grn_item.creation, order=Order.asc)
    
    print(q)
    data = q.run(as_dict=True)
    
    return compute_data(data)

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
