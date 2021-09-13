# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
import json, copy
from six import string_types
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_variant, create_variant, get_attribute_details

class PurchaseOrder(Document):

	def onload(self):
		print('in onload')
		item_details = fetch_item_details(self.get('items'))
		print(item_details)
		self.set_onload('item_details', item_details)
	
	def before_validate(self):
		print(self.item_details)
		if(self.item_details):
			items = save_item_details(self.item_details)
			print(json.dumps(items, indent=3))
			self.set('items', items)
		else:
			frappe.throw('Add items to Purchase Order.', title='Purchase Order')

def save_item_details(item_details):
	"""
		Save item details to purchase order
		Item details format:
		Eg: see sample_po_item.jsonc
	"""
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
	items = []
	for table_index, item in enumerate(item_details):
		item_name = item['item']
		delivery_location = item['delivery_location']
		delivery_date = item['delivery_date']
		for row_index, variant in enumerate(item['variants']):
			variant_attributes = variant['attributes']
			if(variant.get('primary_attribute')):
				for attr, values in variant['values'].items():
					if values.get('qty'):
						print(item_name, attr)
						variant_attributes[variant.get('primary_attribute')] = attr
						item = {}
						variant_name = get_variant(item_name, variant_attributes)
						if not variant_name:
							variant1 = create_variant(item_name, variant_attributes)
							print(variant_name)
							for print_attr in variant1.attributes:
								print(print_attr.attribute, print_attr.attribute_value)
							variant1.insert()
							variant_name = variant1.name
						item['item_variant'] = variant_name
						item['delivery_location'] = delivery_location
						item['delivery_date'] = delivery_date
						item['lot'] = variant.get('lot')
						item['qty'] = values.get('qty')
						item['secondary_qty'] = values.get('secondary_qty')
						item['rate'] = values.get('rate')
						item['table_index'] = table_index
						item['row_index'] = row_index
						items.append(item)

			else:
				if variant['values'].get('default') and variant['values']['default'].get('qty'):
					print(item_name)
					item = {}
					variant_name = get_variant(item_name, variant_attributes)
					if not variant_name:
						variant1 = create_variant(item_name, variant_attributes)
						variant1.insert()
						variant_name = variant1.name
					item['item_variant'] = variant_name
					item['delivery_location'] = delivery_location
					item['delivery_date'] = delivery_date
					item['lot'] = variant.get('lot')
					item['qty'] = variant['values']['default'].get('qty')
					item['secondary_qty'] = variant['values']['default'].get('secondary_qty')
					item['rate'] = variant['values']['default'].get('rate')
					item['table_index'] = table_index
					item['row_index'] = row_index
					items.append(item)
	
	return items

def copy_item_details(variant, item, attribute_details):
	variant['lot'] = ''
	variant['attributes'] = {}
	variant['values'] = {}
	if attribute_details['primary_attribute']:
		variant['primary_attribute'] = attribute_details['primary_attribute']
		for attr in attribute_details['primary_attribute_values']:
			variant['values'][attr.attribute_value] = {'qty': 0, 'rate': 0}
	else:
		variant['values']['default'] = {'qty': 0, 'rate': 0}
		
	for attr in item.attributes:
		if attr.attribute in attribute_details['attributes']:
			variant['attributes'][attr.attribute] = attr.attribute_value
	

def fetch_item_details(items):
	
	item_purchase_details = []

	item_details = {}
	current_table_index = -1
	current_row_index = -1
	current_item_attribute_details = {}
	
	variant = {}
	for item in items:
		current_item = frappe.get_doc("Item Variant", item.item_variant)
		if current_table_index != item.table_index:
			if item_details:
				item_details['variants'].append(variant)
				item_purchase_details.append(item_details)
				item_details = {}	
			variant = {}
			current_table_index = item.table_index
			current_row_index = 0
			item_details['item'] = current_item.item
			item_details['delivery_location'] = item.delivery_location
			item_details['delivery_date'] = item.delivery_date
			current_item_attribute_details = get_attribute_details(current_item.item)
			item_details['default_uom'] = current_item_attribute_details['default_uom']
			item_details['secondary_uom'] = current_item_attribute_details['secondary_uom']
			item_details['variants'] = []
			copy_item_details(variant, current_item, current_item_attribute_details)
			variant['lot'] = item.lot

		if current_row_index != item.row_index:
			item_details['variants'].append(variant)
			variant = {}
			copy_item_details(variant, current_item, current_item_attribute_details)
			variant['lot'] = item.lot
		
		if variant.get('primary_attribute'):
			for attr in current_item.attributes:
				if attr.attribute == variant.get('primary_attribute'):
					variant['values'][attr.attribute_value] = {'qty': item.qty, 'secondary_qty': item.secondary_qty, 'rate': item.rate}
					break
		else:
			variant['values']['default'] = {'qty': item.qty, 'secondary_qty': item.secondary_qty, 'rate': item.rate}
	
	if variant:
		item_details['variants'].append(variant)
	if item_details:
		item_purchase_details.append(item_details)
	return item_purchase_details
			

		
		