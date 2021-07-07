# Copyright (c) 2013, Essdee and contributors
# For license information, please see license.txt
from __future__ import unicode_literals

import frappe

def get_previous_sle(args, for_update=False):
	"""
		get the last sle on or before the current time-bucket,
		to get actual qty before transaction, this function
		is called from various transaction like stock entry, reco etc

		args = {
			"item_code": "ABC",
			"warehouse": "XYZ",
			"posting_date": "2012-12-12",
			"posting_time": "12:00",
			"sle": "name of reference Stock Ledger Entry"
		}
	"""
	args["name"] = args.get("sle", None) or ""
	sle = get_stock_ledger_entries(args, "<=", "desc", "limit 1", for_update=for_update)
	return sle and sle[0] or {}

def get_stock_ledger_entries(previous_sle, operator=None,
	order="desc", limit=None, for_update=False, debug=False):
	"""get stock ledger entries filtered by specific posting datetime conditions"""
	conditions = " and timestamp(posting_date, posting_time) {0} timestamp(%(posting_date)s, %(posting_time)s)".format(operator)
	if previous_sle.get("warehouse"):
		conditions += " and warehouse = %(warehouse)s"
	elif previous_sle.get("warehouse_condition"):
		conditions += " and " + previous_sle.get("warehouse_condition")

	if not previous_sle.get("posting_date"):
		previous_sle["posting_date"] = "1900-01-01"
	if not previous_sle.get("posting_time"):
		previous_sle["posting_time"] = "00:00"

	if operator in (">", "<=") and previous_sle.get("name"):
		conditions += " and name!=%(name)s"

	return frappe.db.sql("""
		select *, timestamp(posting_date, posting_time) as "timestamp"
		from `tabStock Ledger Entry`
		where item_code = %%(item_code)s
		and is_cancelled = 0
		%(conditions)s
		order by timestamp(posting_date, posting_time) %(order)s, creation %(order)s
		%(limit)s %(for_update)s""" % {
			"conditions": conditions,
			"limit": limit or "",
			"for_update": for_update and "for update" or "",
			"order": order
		}, previous_sle, as_dict=1, debug=debug)