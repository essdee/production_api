# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import throw, _
import json, copy
from six import string_types
from itertools import groupby
from jinja2 import TemplateSyntaxError
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_variant, create_variant, get_attribute_details

class PurchaseOrder(Document):

	def onload(self):
		print('in onload')
		item_details = fetch_item_details(self.get('items'))
		self.set('print_item_details', json.dumps(item_details))
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
	row_index = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():
					if values.get('qty'):
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						variant_name = get_variant(item_name, item_attributes)
						if not variant_name:
							variant1 = create_variant(item_name, item_attributes)
							variant1.insert()
							variant_name = variant1.name
						item1['item_variant'] = variant_name
						item1['delivery_location'] = item['delivery_location']
						item1['delivery_date'] = item['delivery_date']
						item1['lot'] = item.get('lot')
						item1['qty'] = values.get('qty')
						item1['secondary_qty'] = values.get('secondary_qty')
						item1['rate'] = values.get('rate')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['comments'] = item.get('comments')
						items.append(item1)

			else:
				if item['values'].get('default') and item['values']['default'].get('qty'):
					print(item_name)
					item1 = {}
					variant_name = get_variant(item_name, item_attributes)
					if not variant_name:
						variant1 = create_variant(item_name, item_attributes)
						variant1.insert()
						variant_name = variant1.name
					item1['item_variant'] = variant_name
					item1['delivery_location'] = item['delivery_location']
					item1['delivery_date'] = item['delivery_date']
					item1['lot'] = item.get('lot')
					item1['qty'] = item['values']['default'].get('qty')
					item1['secondary_qty'] = item['values']['default'].get('secondary_qty')
					item1['rate'] = item['values']['default'].get('rate')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments')
					items.append(item1)
			row_index += 1
	
	return items

def get_item_attribute_details(variant, item_attributes):
	attribute_details = {}
	
	for attr in variant.attributes:
		if attr.attribute in item_attributes['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

def get_item_group_index(items, item_details):
	index = -1
	for i, item in enumerate(items):
		item_attr = item.get('attributes')
		item_details_attr = item_details.get('attributes')
		item_attr.sort()
		item_details_attr.sort()
		if not (len(item_attr) == len(item_details_attr) and len(item_attr) == sum([1 for i, j in zip(item_attr, item_details_attr) if i == j])):
			continue
		if not item.get('primary_attribute') == item_details.get('primary_attribute'):
			continue
		if not item.get('primary_attribute_values').sort() == item_details.get('primary_attribute_values').sort():
			continue
		index = i
		break
	return index

@frappe.whitelist()
def fetch_item_details(items):
	items = [item.as_dict() for item in items]
	item_details = []
	items = sorted(items, key = lambda i: i['row_index'])
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'delivery_location': variants[0]['delivery_location'],
			'delivery_date': str(variants[0]['delivery_date']),
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			'values': {},
			'default_uom': current_item_attribute_details['default_uom'],
			'secondary_uom': current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
		}

		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {'qty': variant.qty, 'secondary_qty': variant.secondary_qty, 'rate': variant.rate}
						break
		else:
			item['values']['default'] = {'qty': variants[0].qty, 'secondary_qty': variants[0].secondary_qty, 'rate': variants[0].rate}
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
	return item_details

@frappe.whitelist()
def get_address_display(address_dict):
	if not address_dict:
		return

	if not isinstance(address_dict, dict):
		address_dict = frappe.db.get_value("Address", address_dict, "*", as_dict=True, cache=True) or {}

	# name, template = get_address_templates(address_dict)
	template = '''
		{{ address_line1 }}, {% if address_line2 %}{{ address_line2 }}{% endif -%}<br>
		{{ city }}, {% if state %}{{ state }}{% endif -%}{% if pincode %} - {{ pincode }}{% endif -%}
	'''

	try:
		return frappe.render_template(template, address_dict)
	except TemplateSyntaxError:
		frappe.throw(_("There is an error in your Address Template"))
		