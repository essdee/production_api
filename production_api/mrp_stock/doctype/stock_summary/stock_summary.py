# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from six import string_types
from frappe.model.document import Document
from production_api.mrp_stock.report.item_balance.item_balance import execute as get_item_balance

class StockSummary(Document):
 	pass

@frappe.whitelist()
def get_stock_summary(lot, item, item_variant, warehouse, received_type):
	filters = {
		"remove_zero_balance_item":1,
	}
	if lot:
		filters['lot'] = lot
	if item:
		filters['item'] = item
	if item_variant:
		filters['item_variant'] = item_variant
	if warehouse:
		filters['warehouse'] = warehouse
	if received_type:
		filters['received_type'] = received_type
	
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
		"item": stock_values['item_variant'],
		"qty": stock_values['qty'],
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

	grouped_items = {}
	for item in selected_items:
		variant = item['item_variant']
		doc = frappe.get_cached_doc("Item Variant", variant)
		primary_attr = frappe.get_cached_value("Item", doc.item, "primary_attribute")
		attr_details = get_variant_attr_values(doc, primary_attr)
		key = (item['lot'], item['item'], item['received_type'], attr_details)
		if key not in grouped_items:
			grouped_items[key] = []
		grouped_items[key].append(item)
		
	final_list = []
	table_index = -1
	row_index = -1
	for (lot, item, received_type, stage), items in grouped_items.items():
		sorted_items = sorted(items, key=lambda x: x['item_variant'])
		table_index += 1
		row_index += 1
		primary = frappe.get_cached_value("Item", sorted_items[0]['item'], "primary_attribute")
		for item in sorted_items:
			if not primary:
				row_index += 1
			final_list.append({
                "item": item['item_variant'],
                "qty": item['actual_qty'],
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