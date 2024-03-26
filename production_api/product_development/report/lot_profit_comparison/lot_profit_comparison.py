# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = [], []
	columns = get_columns1()
	data = get_data1(filters)
	return columns, data

def get_columns():
	return [
		{
            "fieldname": "item",
            "label": "Item",
            "fieldtype": "Link",
            "options": "FG Item Master",
            "width": 250
        },
		{
            "fieldname": "lot",
            "label": "Lot",
            "fieldtype": "Link",
            "options": "Lot",
            "width": 150
        },
		{
            "fieldname": "lot_costing_type",
            "label": "lot_costing_type",
            "fieldtype": "Data",
            "width": 100
        },
		{
            "fieldname": "total_qty",
            "label": "Total Qty",
            "fieldtype": "Float",
            "width": 100
        },
		{
            "fieldname": "profit_percent_markdown",
            "label": "Profit %",
            "fieldtype": "Float",
            "width": 100
        },
	]

def get_columns1():
	return [
		{
            "fieldname": "item",
            "label": "Item",
            "fieldtype": "Link",
            "options": "FG Item Master",
            "width": 250
        },
		{
            "fieldname": "lot",
            "label": "Lot",
            "fieldtype": "Link",
            "options": "Lot",
            "width": 150
        },
		# {
        #     "fieldname": "lot_costing_type",
        #     "label": "lot_costing_type",
        #     "fieldtype": "Data",
        #     "width": 100
        # },
		{
            "fieldname": "Costing_qty",
            "label": "Costing Qty",
            "fieldtype": "Float",
            "width": 100
        },
		{
            "fieldname": "Costing_profit",
            "label": "Costing Profit %",
            "fieldtype": "Float",
            "width": 100
        },
		{
            "fieldname": "Planned Qty_qty",
            "label": "Planned Qty",
            "fieldtype": "Float",
            "width": 100
        },
		{
            "fieldname": "Planned Qty_profit",
            "label": "Planned Profit %",
            "fieldtype": "Float",
            "width": 100
        },
		{
            "fieldname": "Cutting Qty_qty",
            "label": "Cutting Qty",
            "fieldtype": "Float",
            "width": 100
        },
		{
            "fieldname": "Cutting Qty_profit",
            "label": "Cutting Profit %",
            "fieldtype": "Float",
            "width": 100
        },
		{
            "fieldname": "Final Qty_qty",
            "label": "Final Qty",
            "fieldtype": "Float",
            "width": 100
        },
		{
            "fieldname": "Final Qty_profit",
            "label": "Final Profit %",
            "fieldtype": "Float",
            "width": 100
        },
	]

def get_data(filters):
	LotProfit = frappe.qb.DocType("Lotwise Item Profit")

	q = (
		frappe.qb.from_(LotProfit)
		.select(
			LotProfit.name,
			LotProfit.item,
			LotProfit.lot,
			LotProfit.lot_costing_type,
			LotProfit.total_qty,
			LotProfit.profit_percent_markdown,
			LotProfit.creation,
		)
	)

	entries = q.run(as_dict=True)

	group_data = {}
	for entry in entries:
		group_data.setdefault(entry.item, {})
		group_data[entry.item].setdefault(entry.lot, [])
		group_data[entry.item][entry.lot].append(entry)
	data = []
	indent = 0
	for i, v in group_data.items():
		data.append({
			"item": i,
			"indent": indent,
			"is_group": True,
		})
		indent += 1
		for l, v1 in v.items():
			data.append({
				"item": i,
				"lot": l,
				"indent": indent,
				"is_group": True,
			})
			indent += 1
			for v2 in v1:
				data.append({
					**v2,
					"indent": indent,
					"is_group": False,
				})
			indent -= 1
		indent -= 1
	indent -= 1

	return data

def get_data1(filters):
	LotProfit = frappe.qb.DocType("Lotwise Item Profit")

	q = (
		frappe.qb.from_(LotProfit)
		.select(
			LotProfit.name,
			LotProfit.item,
			LotProfit.lot,
			LotProfit.lot_costing_type,
			LotProfit.total_qty,
			LotProfit.profit_percent_markdown,
			LotProfit.creation,
		)
	)

	if filters.get('lot'):
		q = q.where(LotProfit.lot == filters["lot"])
	if filters.get('item'):
		q = q.where(LotProfit.item == filters["item"])
	if filters.get('from_date') and filters.get('to_date'):
		q = q.where(LotProfit.creation >= filters["from_date"] and LotProfit.creation <= filters["to_date"])
	

	q = q.orderby(LotProfit.item)
	q = q.orderby(LotProfit.creation, order=frappe.qb.desc)

	entries = q.run(as_dict=True)
	group_data = {}
	for entry in entries:
		group_data.setdefault(entry.item, {})
		group_data[entry.item].setdefault(entry.lot, [])
		group_data[entry.item][entry.lot].append(entry)
	
	data = []
	for i, v in group_data.items():
		for l, v1 in v.items():
			g = []
			for v2 in v1:
				type = v2.lot_costing_type
				index = False
				for g1 in g:
					if get_type_name(type, "profit") not in g1:
						index = True
						g1[get_type_name(type, "profit")] = v2.profit_percent_markdown
						g1[get_type_name(type, "qty")] = v2.total_qty
						g1[get_type_name(type, "name")] = v2.name
						break
				if not index:
					d = {**v2}
					d[get_type_name(type, "profit")] = v2.profit_percent_markdown
					d[get_type_name(type, "qty")] = v2.total_qty
					d[get_type_name(type, "name")] = v2.name
					g.append(d)
			data.extend(g)
	return data

def get_type_name(type, field):
	return f"{type}_{field}"