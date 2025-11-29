# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from six import string_types
from itertools import groupby
from frappe.model.document import Document
from production_api.utils import update_if_string_instance
from production_api.production_api.doctype.item.item import get_attribute_details
from production_api.mrp_stock.report.stock_balance.stock_balance import execute as get_item_balance
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index


class StockSummary(Document):
 	pass

@frappe.whitelist()
def get_stock_summary(lot, item, item_variant, warehouse, received_type):
	filters = {
		"remove_zero_balance_item":1,
		"from_date": frappe.utils.add_months(frappe.utils.nowdate(), -1),
		"to_date": frappe.utils.nowdate()
	}
	if item:
		filters['parent_item'] = item
	if item_variant:
		filters['item'] = item_variant
	if warehouse:
		filters['warehouse'] = warehouse
	if received_type:
		filters['received_type'] = received_type
	lot = update_if_string_instance(lot)
	report_data = []
	if len(lot) > 0:
		for lot_name in lot:
			filters['lot'] = lot_name['lot']
			x = get_item_balance(filters)
			lot_report_data = x[1]
			report_data = report_data + lot_report_data
	else:	
		x = get_item_balance(filters)
		report_data = x[1]
	return report_data

@frappe.whitelist()
def create_stock_entry(stock_values):
	if isinstance(stock_values, string_types):
		stock_values = frappe.json.loads(stock_values)
	new_doc = frappe.new_doc("Stock Entry")
	new_doc.posting_date = stock_values['posting_date']
	new_doc.posting_time = stock_values['posting_time']
	new_doc.purpose = stock_values['purpose']
	if stock_values.get('to_warehouse'):
		new_doc.to_warehouse = stock_values['to_warehouse']
	if stock_values.get('from_warehouse'):
		new_doc.from_warehouse = stock_values['from_warehouse']
	
	items = [{
		"item": stock_values['item'],
		"qty": stock_values['bal_qty'],
		"lot": stock_values['lot'],
		"received_type": stock_values['received_type'],
		"uom":stock_values['uom']
	}]
	new_doc.set("items", items)
	new_doc.flags.allow_from_summary = True
	new_doc.save()
	return new_doc.name

@frappe.whitelist()
def create_bulk_stock_entry(locations, selected_items, purpose):
	if isinstance(locations, string_types):
		locations = frappe.json.loads(locations)
	if isinstance(selected_items, string_types):
		selected_items = frappe.json.loads(selected_items)
	
	new_doc = frappe.new_doc("Stock Entry")
	new_doc.purpose = purpose
	if locations.get('to_warehouse'):
		new_doc.to_warehouse = locations['to_warehouse']
	if locations.get('from_warehouse'):
		new_doc.from_warehouse = locations['from_warehouse']

	grouped_items = get_grouped_items(selected_items)
		
	final_list = []
	table_index = -1
	row_index = -1
	for (lot, item, received_type, stage), items in grouped_items.items():
		sorted_items = sorted(items, key=lambda x: x['item'])
		table_index += 1
		row_index += 1
		primary = frappe.get_cached_value("Item", sorted_items[0]['item_name'], "primary_attribute")
		for item in sorted_items:
			if not primary:
				row_index += 1
			final_list.append({
                "item": item['item'],
                "qty": item['bal_qty'],
                "lot": lot,
                "received_type": received_type,
                "uom": item['stock_uom'],
				'table_index': table_index,
				'row_index': row_index,
            })
	new_doc.set("items", final_list)
	new_doc.flags.allow_from_summary = True		
	new_doc.save()
	return new_doc.name

@frappe.whitelist()
def reduce_stock(selected_items, warehouse):
	if isinstance(selected_items, string_types):
		selected_items = frappe.json.loads(selected_items)
	grouped_items = get_grouped_items(selected_items)
	final_list = []
	table_index = -1
	row_index = -1
	for (lot, item, received_type, stage), items in grouped_items.items():
		sorted_items = sorted(items, key=lambda x: x['item'])
		table_index += 1
		row_index += 1
		primary = frappe.get_cached_value("Item", sorted_items[0]['item_name'], "primary_attribute")
		for item in sorted_items:
			if not primary:
				row_index += 1
			final_list.append({
                "item": item['item'],
                "qty": 0,
                "lot": lot,
                "received_type": received_type,
                "uom": item['stock_uom'],
				'table_index': table_index,
				'row_index': row_index,
				"make_qty_zero": 1,
				"warehouse": warehouse
            })

	doc = frappe.new_doc("Stock Reconciliation")
	doc.purpose = "Stock Reconciliation"
	doc.default_warehouse = warehouse
	doc.set("items", final_list)
	doc.save(ignore_permissions=True)
	return doc.name

def get_grouped_items(selected_items):
	grouped_items = {}
	for item in selected_items:
		variant = item['item']
		doc = frappe.get_cached_doc("Item Variant", variant)
		primary_attr = frappe.get_cached_value("Item", doc.item, "primary_attribute")
		attr_details = get_variant_attr_values(doc, primary_attr)
		key = (item['lot'], item['item_name'], item['received_type'], attr_details)
		if key not in grouped_items:
			grouped_items[key] = []
		grouped_items[key].append(item)
	return grouped_items	

def get_variant_attr_values(doc, primary_attr):
	attrs = []
	for attr in doc.attributes:
		if attr.attribute != primary_attr:
			attrs.append(attr.attribute_value)
	attrs.sort()
	if attrs:
		attrs = tuple(attrs)
	else:
		attrs = None			
	return attrs

@frappe.whitelist()
def lot_transfer_items(selected_items, transfer_lot):
	if isinstance(selected_items, string_types):
		selected_items = frappe.json.loads(selected_items)
	grouped_items = get_grouped_items(selected_items)	
	table_index = -1
	row_index = -1
	final_items = []
	for (lot, item, received_type, stage), items in grouped_items.items():
		sorted_items = sorted(items, key=lambda x: x['item'])
		table_index += 1
		row_index += 1
		primary = frappe.get_cached_value("Item", sorted_items[0]['item_name'], "primary_attribute")
		for item in sorted_items:
			if not primary:
				row_index += 1
			item1 = {}
			item1['item'] = item['item']
			item1['from_lot'] = item['lot']
			item1['to_lot'] = transfer_lot
			item1['warehouse'] = item['warehouse']
			item1['uom'] = item['stock_uom']
			item1['qty'] = item['bal_qty']
			item1['rate'] = 0
			item1['table_index'] = table_index
			item1['row_index'] = row_index
			item1['received_type'] = item['received_type']
			final_items.append(item1)

	item_details = []
	final_items = sorted(final_items, key = lambda i: i['row_index'])
	for key, variants in groupby(final_items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_doc("Item Variant", variants[0]['item'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['from_lot'],
			'to_lot': variants[0]['to_lot'],
			'warehouse': variants[0]['warehouse'],
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			'values': {},
			'default_uom': variants[0].get('uom') or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0].get('secondary_uom') or current_item_attribute_details['secondary_uom'],
			'received_type':variants[0].get('received_type')
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_doc("Item Variant", variant['item'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'qty': variant.get('qty'),
							'rate': variant.get('rate'),
							"set_combination": variant.get('set_combination'),
						}
						break
		else:
			item['values']['default'] = {
				'qty': variants[0]['qty'],
				'rate': variants[0]['rate'],
			}			
		index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	doc = frappe.new_doc("Lot Transfer")
	doc.item_details = item_details
	doc.save()

	return doc.name