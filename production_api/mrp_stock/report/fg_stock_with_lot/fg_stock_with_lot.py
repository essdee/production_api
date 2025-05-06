# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import pymysql.cursors
import frappe
from .fg_old_db_connection import get_connection
from production_api.mrp_stock.utils import sanitize_sql_input
from frappe import _


def execute(filters=None):
	columns, data = getColumns(), getData(filters)
	return columns, data

def getColumns():
	return [
		{
			"label": _("Item"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 120,
		},
		{
			"label": _("Warehouse Name"),
			"fieldname": "warehouse_name",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Lot"),
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"width": 150,
		},
		{
			"label": _("Quantity"),
			"fieldname": "qty",
			"fieldtype": "Float",
			"width": 140,
		},
	]

def getData(filters=None):

	stock = get_stock(filters)
	prev_fg_stock_entries = get_prev_fg_stock_entries(filters, stock)
	return prev_fg_stock_entries

def get_prev_fg_stock_entries(filters, stock):

	received_type =frappe.db.get_single_value("Stock Settings", "default_received_type")
	default_fg_lot = frappe.db.get_single_value("Stock Settings", 'default_fg_lot')

	query = """
		SELECT 
			t0.item_variant, SUM(t0.qty) as qty, t1.lot, t1.warehouse, t3.supplier_name as warehouse_name, t2.item
		FROM
		`tabFG Stock Entry Detail` t0 JOIN
		 `tabFG Stock Entry` t1 ON t0.parent=t1.name
		JOIN `tabItem Variant` t2 ON t0.item_variant=t2.name
		JOIN `tabSupplier` t3 ON t3.name=t1.warehouse 
		WHERE t1.docstatus=1 AND t0.received_type = %(received_type)s AND t1.warehouse = %(warehouse)s
		AND t1.posting_date <= %(filter_date)s
		AND t1.lot not in ('Not Applicable', '', %(lot)s)
		GROUP BY t2.item, t1.lot
		ORDER BY t1.posting_date, t1.posting_time DESC
	"""

	other_fg_entries_query = """
		SELECT 
			t0.item_variant, SUM(t0.qty) as qty, t1.warehouse, t3.supplier_name as warehouse_name, t2.item
		FROM
		`tabFG Stock Entry Detail` t0 JOIN
		 `tabFG Stock Entry` t1 ON t0.parent=t1.name
		JOIN `tabItem Variant` t2 ON t0.item_variant=t2.name
		JOIN `tabSupplier` t3 ON t3.name=t1.warehouse 
		WHERE t1.docstatus=1 AND t0.received_type = %(received_type)s AND t1.warehouse = %(warehouse)s
		AND t1.posting_date <= %(filter_date)s
		AND t1.lot in ('Not Applicable', '', %(lot)s)
		GROUP BY t2.item
		ORDER BY t1.posting_date, t1.posting_time DESC
	"""

	resp = frappe.db.sql(query, {
		"received_type" : received_type,
		"warehouse" : filters['warehouse'],
		"filter_date" : filters['filter_date'],
		"lot" : default_fg_lot
	}, as_dict=True)

	report = []

	item_stock = construct_item_wise_stock_detail(stock)

	other_resp = frappe.db.sql(other_fg_entries_query, {
		"received_type" : received_type,
		"warehouse" : filters['warehouse'],
		"filter_date" : filters['filter_date'],
		"lot" : default_fg_lot
	}, as_dict=True)

	for i in resp:

		if i['item'] not in item_stock or item_stock[i['item']] <= 0:
			continue
		report.append({
			"item" : i['item'],
			"qty" : i['qty'],
			"lot" : i['lot'],
			"warehouse" : i['warehouse'],
			"warehouse_name" : i['warehouse_name']
		})

		item_stock[i['item']] -= i['qty']
	
	old_data = get_old_sms_data(item_stock, filters['warehouse'], filter_date=filters['filter_date'])

	if other_resp:
		for i in other_resp:
			report.append({
				"item" : i['item'],
				"qty" : i['qty'],
				"lot" : default_fg_lot,
				"warehouse" : i['warehouse'],
				"warehouse_name" : i['warehouse_name']
			})
	
	report = report+old_data

	return duplicate_removed_data(report)

def duplicate_removed_data(data):
	result = {}
	for i in data:
		key = (i['item'], i['lot'])
		if key not in result:
			result[key] = i
		else :
			result[key]['qty'] += i['qty']

	return [v for k,v in result.items()]

def get_old_sms_data(stock_detail, warehouse, filter_date):

	warehouse_map = old_warehouse_mapping(warehouse)
	item_list = set()
	for i, v in stock_detail.items():
		if v > 0:
			item_list.add(i)
	
	item_list = list(item_list)

	items_filter = ",".join([ f"'{sanitize_sql_input(i)}'" for i in item_list])
	items_filter = f" AND t3.name in ({items_filter}) "

	if not item_list:
		return []
	
	connection = get_connection()
	report_data = []
	with connection.cursor(pymysql.cursors.DictCursor) as cursor:
		cursor.execute(f"""
			select 
			    t3.name as item, sum(t2.size1 + t2.size2 + t2.size3 + t2.size4 + t2.size5 + t2.size6 + t2.size7 + t2.size8 + t2.size9 + t2.size10) as qty, t1.lotnumber as lot, t1.creationdate, t1.idlocation
			from stockentrydetails t1 
			join stockentryitems t2 ON t1.idstockentry = t2.idstockentry
			join iteminfo t3 ON t3.iditem = t2.iditem
			WHERE 1=1  {items_filter}  AND t1.idlocation = {warehouse_map[0]} AND t1.creationdate <= '{filter_date}'
			group by t3.name, t1.lotnumber order by t1.creationdate desc;
		""")
		data = cursor.fetchall()
		for i in data:
			i['qty'] = int(i['qty'])
			if i['item'] not in stock_detail or stock_detail[i['item']] <=0:
				continue
			report_data.append({
				"item" : i['item'],
				"qty" : i['qty'],
				"lot" : i['lot'],
				"warehouse" : warehouse_map[1],
				"warehouse_name" : warehouse_map[2]
			})
			stock_detail[i['item']] -= i['qty']
	
	return report_data

def old_warehouse_mapping(warehouse):

	query = """
		SELECT 
			t1.old_location_id as loc_id, t1.warehouse, t2.supplier_name as warehouse_name 
		FROM `tabStock Settings Old Warehouse Mapping` t1 JOIN `tabSupplier` t2 ON t1.warehouse=t2.name
		WHERE t2.name=%(warehouse)s
		;
	"""
	resp = frappe.db.sql(query, {
		"warehouse" : warehouse
	}, as_dict=True)
	if not resp:
		frappe.throw("Please Setup Old Sales System Warehouse Mapping")

	return [resp[0]['loc_id'], resp[0]['warehouse'], resp[0]['warehouse_name']]



def construct_item_wise_stock_detail(stock):
	resp = {}
	for i in stock:
		resp[i['item']] = i['stock']

	return resp

def get_stock(filters):

	settings = frappe.get_single("Stock Settings")

	query = """
		WITH latest_sle AS (
		    SELECT 
		        name,
		        item,
		        warehouse,
		        lot,
		        ROW_NUMBER() OVER (
		            PARTITION BY item
		            ORDER BY posting_date DESC, posting_time DESC, creation DESC
		        ) AS rn
		    FROM `tabStock Ledger Entry`
		    WHERE posting_date <= %(filter_date)s
			AND is_cancelled = 0
			AND docstatus = 1
			AND received_type = %(received_type)s
			AND lot = %(lot)s
			AND warehouse = %(warehouse)s
		)
		SELECT 
		    t1.lot, 
		    (SUM(t1.qty_after_transaction) / t4.pcs_per_box) AS stock,
		    t2.item, 
		    t3.supplier_name AS warehouse_name, 
		    t3.name AS warehouse
		FROM `tabStock Ledger Entry` t1
		JOIN `tabItem Variant` t2 ON t2.name = t1.item
		JOIN `tabSupplier` t3 ON t3.name = t1.warehouse
		JOIN `tabFG Item Master` t4 ON t4.item = t2.item
		JOIN latest_sle ON latest_sle.name = t1.name AND latest_sle.rn = 1
		WHERE 
		    t1.posting_date <= %(filter_date)s
		    AND t1.is_cancelled = 0
		    AND t1.docstatus = 1
		    AND t1.received_type = %(received_type)s
		    AND t1.lot = %(lot)s
		    AND t1.warehouse = %(warehouse)s
		GROUP BY t2.item;
	"""

	return frappe.db.sql(query, {
		"filter_date" : filters['filter_date'],
		"warehouse" : filters['warehouse'],
		"lot" : settings.get('default_fg_lot'),
		"received_type" : settings.get('default_received_type')
	}, as_dict=True)