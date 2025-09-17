# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import pymysql.cursors
import frappe
from .fg_old_db_connection import get_connection
from production_api.mrp_stock.utils import get_conversion_factor, sanitize_sql_input
from production_api.production_api.doctype.mrp_settings.mrp_settings import get_sales_credentials
from production_api.production_api.util import make_get_request
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
			"label": _("Quantity (Boxes)"),
			"fieldname": "qty",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label" : _('Pieces Per Box'),
			"fieldname" : "pcs_per_box",
			"fieldtype" : "int",
			"width" : 140
		},
		{
			"label" : _('Stock Qty (Pieces)'),
			"fieldname" : "stock_in_pcs",
			"fieldtype" : "Float",
			"width" : 140
		},
		{
			"label" : _('Stock Value'),
			"fieldname" : "stock_price",
			"fieldtype" : "Currency",
			"width" : 140
		},
		{
			"label" : _('Stock Entry Date'),
			"fieldname" : "entry_date",
			"fieldtype" : "Datetime",
			"width" : 140
		},
		# {
		# 	"label" : _("Price Per Box"),
		# 	"fieldname" : "price_per_box",
		# 	"fieldtype" : "Currency",
		# 	"width" : 140
		# }
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
			t0.item_variant, SUM(t0.qty) as qty, t1.lot, t1.warehouse, t3.supplier_name as warehouse_name, t2.item, t4.pcs_per_box, t1.creation as entry_date
		FROM
		`tabFG Stock Entry Detail` t0 JOIN
		 `tabFG Stock Entry` t1 ON t0.parent=t1.name
		JOIN `tabItem Variant` t2 ON t0.item_variant=t2.name
		JOIN `tabSupplier` t3 ON t3.name=t1.warehouse 
		JOIN `tabFG Item Master` t4 ON t4.item = t2.item
		WHERE t1.docstatus=1 AND t0.received_type = %(received_type)s AND t1.warehouse = %(warehouse)s
		AND t1.posting_date <= %(filter_date)s
		GROUP BY t2.name, t1.name
		ORDER BY t1.posting_date DESC, t1.posting_time DESC
	"""

	resp = frappe.db.sql(query, {
		"received_type" : received_type,
		"warehouse" : filters['warehouse'],
		"filter_date" : filters['filter_date'],
		"lot" : default_fg_lot
	}, as_dict=True)

	report = []

	item_stock = construct_item_wise_stock_detail(stock)

	for index,i in enumerate(resp):
		i['lot'] = get_next_non_fg_lot(default_fg_lot, resp, index)
		if i['item_variant'] not in item_stock or item_stock[i['item_variant']]['stock'] <= 0:
			continue
	
		item_stock[i['item_variant']]['stock'] -= i['qty']
		if item_stock[i['item_variant']]['stock'] <= 0:
			i['qty'] += item_stock[i['item_variant']]['stock']
		row = {
			"item" : i['item'],
			"item_variant" : i['item_variant'],
			"qty" : i['qty'],
			"lot" : i['lot'],
			"warehouse" : i['warehouse'],
			"warehouse_name" : i['warehouse_name'],
			"stock_in_pcs" : i['qty'] * i['pcs_per_box'],
			"pcs_per_box" : i['pcs_per_box'],
			"entry_date" : i['entry_date']
		}
		calculate_and_update_price_and_valuation(row, item_stock[i['item_variant']])
		report.append(row)
	old_data = get_old_sms_data(item_stock, filters['warehouse'], filter_date=filters['filter_date'])
	report = report+old_data

	return duplicate_removed_data(report)

def calculate_and_update_price_and_valuation(report : dict, data : dict):
	report.update({
		"stock_price" : (data['price']/data['conversion_factor']) * report['pcs_per_box'] * report['qty'],
		# "price_per_box" : data['price']/data['conversion_factor']
	})

def get_next_non_fg_lot(fg_lot, list_items, curr_index):
	if curr_index >= len(list_items)-1:
		return list_items[curr_index]['lot']
	
	if not list_items[curr_index]['lot'] or list_items[curr_index]['lot'] in ['Not Applicable', fg_lot]:
		for i in range(curr_index +1, len(list_items)):
			if list_items[i]['lot'] and list_items[i]['lot'] not in ['Not Applicable', fg_lot]:
				return list_items[i]['lot']
		return fg_lot
	else :
		return list_items[curr_index]['lot']

def duplicate_removed_data(data):
	result = {}
	for i in data:
		key = (i['item'], i['lot'])
		if key not in result:
			result[key] = i
		else :
			result[key]['qty'] += i['qty']
			result[key]['stock_in_pcs'] += i['stock_in_pcs']
			result[key]['stock_price'] += i['stock_price']
	return [v for k,v in result.items()]

def get_old_sms_data(stock_detail, warehouse, filter_date):

	warehouse_map = old_warehouse_mapping(warehouse)
	item_list = set()
	for i, v in stock_detail.items():
		if v['stock'] > 0:
			item_list.add(v['item'])
	
	item_list = list(item_list)

	items_filter = ",".join([ f"'{sanitize_sql_input(i)}'" for i in item_list])
	items_filter = f" AND t3.name in ({items_filter}) "

	if not item_list:
		return []
	
	connection = get_connection()
	report_data = []
	with connection.cursor(pymysql.cursors.DictCursor) as cursor:
		cursor.execute("""SELECT 
					t1.name,
					t2.size1  AS x_size1,
					t2.size2  AS x_size2,
					t2.size3  AS x_size3,
					t2.size4  AS x_size4,
					t2.size5  AS x_size5,
					t2.size6  AS x_size6,
					t2.size7  AS x_size7,
					t2.size8  AS x_size8,
					t2.size9  AS x_size9,
					t2.size10 AS x_size10,
					t3.size1  AS size1,
					t3.size2  AS size2,
					t3.size3  AS size3,
					t3.size4  AS size4,
					t3.size5  AS size5,
					t3.size6  AS size6,
					t3.size7  AS size7,
					t3.size8  AS size8,
					t3.size9  AS size9,
					t3.size10 AS size10
				FROM iteminfo t1
				JOIN sizerange t2 ON t1.sizerange = t2.idsize
				JOIN sizetype  t3 ON t3.id = t2.idsizetype;
		""")
		item_size_type_details = {}
		size_ranges = ['size1', 'size2', 'size3', 'size4', 'size5', 'size6', 'size7', 'size8', 'size9', 'size10']
		item_details = cursor.fetchall()
		for i in item_details:
			if i['name'] not in item_size_type_details:
				item_size_type_details[i['name']] = {}
			for size in size_ranges:
				if i[f"x_{size}"] == 1:
					item_size_type_details[i['name']][size] = f"{i['name']}-{i[size]}"
				else:
					item_size_type_details[i['name']][size] = None
		cursor.execute(f"""
			select 
			    t3.name as item, t2.size1, t2.size2, t2.size3, t2.size4, t2.size5, t2.size6, t2.size7, t2.size8, t2.size9, t2.size10, t1.lotnumber as lot, t1.creationdate, t1.idlocation, t3.pieces as pcs_per_box, t1.creationdate as entry_date
			from stockentrydetails t1 
			join stockentryitems t2 ON t1.idstockentry = t2.idstockentry
			join iteminfo t3 ON t3.iditem = t2.iditem
			WHERE 1=1  {items_filter}  AND t1.idlocation = {warehouse_map[0]} AND t1.creationdate <= '{filter_date}'
			order by t1.creationdate desc;
		""")
		data = cursor.fetchall()
		for i in data:
			for size in size_ranges:
				if not item_size_type_details[i['item']][size] or item_size_type_details[i['item']][size] not in stock_detail or stock_detail[item_size_type_details[i['item']][size]]['stock'] <= 0:
					continue
				stock_detail[item_size_type_details[i['item']][size]]['stock'] -= i[size]
				if stock_detail[item_size_type_details[i['item']][size]]['stock'] <= 0:
					i[size] += stock_detail[item_size_type_details[i['item']][size]]['stock']
				if not i[size]:
					continue
				row = {
					"item" : i['item'],
					"qty" : i[size],
					"lot" : i['lot'],
					"warehouse" : warehouse_map[1],
					"warehouse_name" : warehouse_map[2],
					"stock_in_pcs" : i[size] * i['pcs_per_box'],
					"pcs_per_box" : i['pcs_per_box'],
					"entry_date" : i['entry_date']
				}
				calculate_and_update_price_and_valuation(row, stock_detail[item_size_type_details[i['item']][size]])
				report_data.append(row)
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
	price_and_valuations = get_price_valuation_for_items()
	for i in stock:
		resp[i['item_variant']] = price_and_valuations[i['item_variant']] if i['item_variant'] in price_and_valuations else {
            "price": 0.0,
            "uom": "Box",
        }
		resp[i['item_variant']]['stock'] = i['stock']
		resp[i['item_variant']]['item'] = i['item']
		resp[i['item_variant']]["conversion_factor"] = get_conversion_factor(i['item_variant'], uom=resp[i['item_variant']]['uom'])['conversion_factor']
	return resp

def get_price_valuation_for_items():
	credentials = get_sales_credentials()
	headers = {
		"Authorization" : credentials['token'],
		"Content-Type" : "application/json"
	}
	resp = make_get_request(
		"/api/method/essdee_sales.api.mrp.get_wholesales_price_details_for_items",
		{
			"headers" : headers,
			"url" : credentials['url']
		},
		params= {}
	)
	if resp.ok:
		return resp.json()['message']
	frappe.throw(resp.text)
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
			t1.item as item_variant,
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
		GROUP BY t1.item
		;
	"""

	return frappe.db.sql(query, {
		"filter_date" : filters['filter_date'],
		"warehouse" : filters['warehouse'],
		"lot" : settings.get('default_fg_lot'),
		"received_type" : settings.get('default_received_type')
	}, as_dict=True)