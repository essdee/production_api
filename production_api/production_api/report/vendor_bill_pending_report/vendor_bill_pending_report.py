# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today


def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data

def get_columns(filters):
	return []

def get_data(filters):

	q_filters = ""

	if filters and filters.get('department'):
		q_filters += f" AND t1.assigned_to = {frappe.db.escape(filters.get('department'))} "

	if filters and filters.get('bill_start_date'):
		q_filters += f" AND t1.creation >= {frappe.db.escape(filters.get('bill_start_date'))} "

	if filters and filters.get('bill_end_date'):
		q_filters += f" AND t1.creation <= {frappe.db.escape(filters.get('bill_end_date'))} "

	query = f"""
		SELECT t1.name, t1.supplier, t4.supplier_name, t1.gstin, t1.pan, t3.remarks as assignment_comment,
		t1.bill_no, t1.invoice_value, t1.creation, DATEDIFF(%(curr_date)s, t1.bill_date) as bill_age,
		t3.assigned_to, t3.received, t3.assigned_on, t3.assigned_by,
		DATEDIFF(%(curr_date)s, t3.assigned_on) AS date_diff
		FROM `tabVendor Bill Tracking` t1
		LEFT JOIN (
		    SELECT t2.*
		    FROM `tabVendor Bill Tracking Assignment Detail` t2
		    INNER JOIN (
		        SELECT inner_child.parent, MAX(inner_child.idx) AS max_idx
		        FROM `tabVendor Bill Tracking Assignment Detail` inner_child
				JOIN `tabVendor Bill Tracking` inner_parent ON inner_parent.assigned_to = inner_child.assigned_to
		        GROUP BY parent
		    ) latest ON t2.parent = latest.parent AND t2.idx = latest.max_idx
		) t3 ON t1.name = t3.parent 
		JOIN `tabSupplier` t4 ON t4.name = t1.supplier
		WHERE t1.form_status NOT IN ('Closed')
		AND t1.docstatus = 1 {q_filters}
	"""

	result = frappe.db.sql(query, {
		"curr_date" : today()
	}, as_dict=True)
	return result

def get_columns(filters):

	return [
		{
            "fieldname": "name",
            "label": "Vendor Bill Tracking Number",
            "fieldtype": "Link",
            "options": "Vendor Bill Tracking",
            "width": 115
        },
		{
            "fieldname": "supplier",
            "label": "Supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 115
        },
		{
            "fieldname": "supplier_name",
            "label": "Supplier Name",
            "fieldtype": "Data",
            "width": 115
        },
		{
            "fieldname": "gstin",
            "label": "GST",
            "fieldtype": "Data",
            "width": 115
        },
		{
            "fieldname": "pan",
            "label": "Pan",
            "fieldtype": "Data",
            "width": 115
        },
		{
            "fieldname": "bill_no",
            "label": "Invoice No",
            "fieldtype": "Data",
            "width": 115
        },
		{
            "fieldname": "bill_age",
            "label": "Bill Age",
            "fieldtype": "Int",
            "width": 115
        },
		{
            "fieldname": "assigned_to",
            "label": "Assigned To",
            "fieldtype": "Link",
            "options": "Department",
            "width": 115
        },
		{
            "fieldname": "assigned_by",
            "label": "Assigned User",
            "fieldtype": "Link",
            "options": "User",
            "width": 115
        },
		{
            "fieldname": "assigned_on",
            "label": "Assigned On",
            "fieldtype": "Date",
            "width": 115
        },
		{
            "fieldname": "date_diff",
            "label": "Assigned Age",
            "fieldtype": "Int",
            "width": 115
        },
		{
            "fieldname": "assignment_comment",
            "label": "Assignment Comment",
            "fieldtype": "Small Text",
            "width": 115
        },
		{
            "fieldname": "received",
            "label": "Bill Received",
            "fieldtype": "Check",
            "width": 115
        },
	]