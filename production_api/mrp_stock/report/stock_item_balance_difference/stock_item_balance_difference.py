# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from production_api.mrp_stock.report.item_balance.item_balance import get_data as item_balance_report
from production_api.mrp_stock.report.stock_balance.stock_balance import execute as stock_balance_report
from frappe import _

def execute(filters):
	columns, data = get_colums(filters), get_report_data(filters)
	return columns, data


def get_report_data(filters):
	item_bal = item_balance_report(filters)
	_,stock_bal = stock_balance_report(filters)

	diff_dict = {}
	for i in item_bal:
		key = get_combine_key(i['item_variant'], i['warehouse'], i['lot'])
		if key not in diff_dict:
			diff_dict[key] = {
				"item" : i['item_variant'],
				"parent_item" : i['item'],
				"warehouse" : i['warehouse'],
				"lot" : i['lot'],
				"item_bal" : 0.0,
				"stock_bal" : 0.0
			}
		diff_dict[key]['item_bal'] += float(i['actual_qty'])
	for i in stock_bal:
		key = get_combine_key(i['item'], i['warehouse'], i['lot'])
		if key not in diff_dict:
			diff_dict[key] = {
				"item" : i['item'],
				"parent_item" : i['item_name'],
				"warehouse" : i['warehouse'],
				"lot" : i['lot'],
				"item_bal" : 0.0,
				"stock_bal" : 0.0
			}
		diff_dict[key]['stock_bal'] += float(i['bal_qty'])
	
	result = []
	for key, value in diff_dict.items():


		value.update({
			"diff_between" : float(value['stock_bal']) - float(value['item_bal'])
		})
		if filters.get("remove_zero_diff") == 1 and value['diff_between'] == float(0):
			continue

		result.append(value)

	return result


def get_colums(filters):
	
	columns = [
		{
			"label": _("Item"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item Variant",
			"width": 150,
		},
		{
			"label": _("Item Name"),
			"fieldname": "parent_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150
		},
		{
			"label": _("Lot"),
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"width": 100,
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 100,
		},
	]

	columns.extend(
		[
			{
				"label": _("Stock Difference"),
				"fieldname": "diff_between",
				"fieldtype": "Float",
				"width": 100,
				"convertible": "qty",
			},
			{
				"label": _("Stock Qty"),
				"fieldname": "stock_bal",
				"fieldtype": "Float",
				"width": 100,
				"convertible": "qty",
			},
			{
				"label": _("Item Balance"),
				"fieldname": "item_bal",
				"fieldtype": "Float",
				"width": 100,
				"convertible": "qty",
			},
		]
	)

	return columns


def get_combine_key(item_variant, lot, warehouse):
	return f"{item_variant}{lot}{warehouse}"