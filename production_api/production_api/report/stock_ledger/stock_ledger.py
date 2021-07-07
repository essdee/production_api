# Copyright (c) 2013, Essdee and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.utils import cint, flt
from frappe import _
from production_api.production_api.utils.stock_ledger import get_previous_sle

def execute(filters=None):
	columns = get_columns()
	items = get_items(filters)
	sl_entries = get_stock_ledger_entries(filters, items)
	item_details = get_item_details(items, sl_entries)
	opening_row = get_opening_balance(filters, columns)

	data = []
	if opening_row:
		data.append(opening_row)

	actual_qty =  0

	available_serial_nos = {}
	for sle in sl_entries:
		item_detail = item_details[sle.item_code]

		sle.update(item_detail)


		sle.update({
			"in_qty": max(sle.actual_qty, 0),
			"out_qty": min(sle.actual_qty, 0)
		})


		data.append(sle)

	return columns, data

def get_columns():
	columns = [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Datetime", "width": 150},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 100},
		{"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 80, "convertible": "qty"},
		{"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 80, "convertible": "qty"},
		{"label": _("Location"), "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 150},
		{"label": _("Lot"), "fieldname": "lot", "fieldtype": "Link", "options": "Lot Creation", "width": 150},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "width": 110},
		{"label": _("Voucher #"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 100}
	]

	return columns

def get_stock_ledger_entries(filters, items):
	item_conditions_sql = ''
	if items:
		item_conditions_sql = 'and sle.item_code in ({})'\
			.format(', '.join([frappe.db.escape(i) for i in items]))

	sl_entries = frappe.db.sql("""
		SELECT
			concat_ws(" ", posting_date, posting_time) AS date,
			item_code,
			location,
			actual_qty,
			voucher_type,
			voucher_no,
			lot
		FROM
			`tabStock Ledger Entry` sle
		WHERE
			is_cancelled = 0 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
				{sle_conditions}
				{item_conditions_sql}
		ORDER BY
			posting_date asc, posting_time asc, creation asc
		""".format(sle_conditions=get_sle_conditions(filters), item_conditions_sql=item_conditions_sql),
		filters, as_dict=1)

	return sl_entries


def get_items(filters):
	conditions = []
	if filters.get("item_code"):
		conditions.append("item.name=%(item_code)s")

	items = []
	if conditions:
		items = frappe.db.sql_list("""select name from `tabItem` item where {}"""
			.format(" and ".join(conditions)), filters)
	return items


def get_item_details(items, sl_entries):
	item_details = {}
	if not items:
		items = list(set([d.item_code for d in sl_entries]))

	if not items:
		return item_details

	res = frappe.db.sql("""
		select
			item.name, item.item_name
		from
			`tabItem` item
		where
			item.name in ({item_codes})
	""".format(item_codes=','.join(['%s'] *len(items))), items, as_dict=1)

	for item in res:
		item_details.setdefault(item.name, item)

	return item_details


def get_sle_conditions(filters):
	conditions = []
	if filters.get("location"):
		conditions.append("location=%(location)s")
	if filters.get("voucher_no"):
		conditions.append("voucher_no=%(voucher_no)s")

	return "and {}".format(" and ".join(conditions)) if conditions else ""

def get_opening_balance(filters, columns):
	if not (filters.item_code and filters.location and filters.from_date):
		return

	last_entry = get_previous_sle({
		"item_code": filters.item_code,
		"location_condition": filters.location,
		"posting_date": filters.from_date,
		"posting_time": "00:00:00"
	})

	row = {
		"item_code": _("'Opening'")
	}

	return row