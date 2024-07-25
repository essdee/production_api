# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe

def execute(filters=None):
	columns, data = [], []
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
            "fieldname": "purchase_order",
            "label": "Purchase Order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 100,
        },
		{
            "fieldname": "po_date",
            "label": "PO Date",
            "fieldtype": "Date",
            "width": 150,
        },
		{
            "fieldname": "supplier",
            "label": "Supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 200,
        },
		{
            "fieldname": "item_variant",
            "label": "Item",
            "fieldtype": "Link",
			"options": "Item Variant",
            "width": 200,
        },
		{
            "fieldname": "type",
            "label": "Type",
            "fieldtype": "Data",
            "width": 200,
        },
		{
            "fieldname": "posting_date",
            "label": "Posting Date",
            "fieldtype": "Date",
            "width": 150,
        },
		{
            "fieldname": "posting_time",
            "label": "Posting Time",
            "fieldtype": "Time",
            "width": 150,
        },
		{
            "fieldname": "qty",
            "label": "Qty",
            "fieldtype": "Float",
            "width": 100,
        },
		{
            "fieldname": "previous_date",
            "label": "Previous Date",
            "fieldtype": "Date",
            "width": 150,
        },
		{
            "fieldname": "changed_date",
            "label": "Changed Date",
            "fieldtype": "Date",
            "width": 150,
        },
		{
            "fieldname": "reason",
            "label": "Reason",
            "fieldtype": "Small Text",
            "width": 100,
        },
	]

def get_data(filters):
	pol = frappe.qb.DocType('Purchase Order Log')
	query = frappe.qb.from_(pol).select(
		pol.purchase_order.as_('purchase_order'),
		pol.po_date.as_('po_date'),
		pol.supplier.as_('supplier'),
		pol.item_variant.as_('item_variant'),
		pol.type.as_('type'),
		pol.posting_date.as_('posting_date'),
		pol.posting_time.as_('posting_time'),
		pol.qty.as_('qty'),
		pol.previous_date.as_('previous_date'),
		pol.changed_date.as_('changed_date'),
		pol.reason.as_('reason'),
	)
	if filters.get('purchase_order'):
		query = query.where(pol.purchase_order == filters.get('purchase_order'))
	if filters.get('po_date'):
		query = query.where(pol.po_date == filters.get('po_date'))
	if filters.get('supplier'):
		query = query.where(pol.supplier == filters.get('supplier'))			
	
	return query.run(as_dict=True)
