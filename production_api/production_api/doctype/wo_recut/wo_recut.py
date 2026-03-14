# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
from itertools import groupby
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_group_index
from production_api.production_api.doctype.work_order.work_order import get_item_attribute_details
from production_api.utils import update_if_string_instance


class WORecut(Document):
	def onload(self):
		if not self.is_new():
			recut_item_details = fetch_recut_item_details(self.get('wo_recut_details'))
			self.set_onload('recut_item_details', recut_item_details)

	def before_validate(self):
		if self.docstatus == 1:
			return
		if self.get('recut_item_details'):
			items = save_recut_item_details(self.recut_item_details)
			self.set("wo_recut_details", items)


def fetch_recut_item_details(items):
	"""Reconstruct grouped item structure from flat WO Recut Detail child rows."""
	items = [item.as_dict() for item in items]
	item_details = []
	items = sorted(items, key=lambda i: i['row_index'])

	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)

		item = {
			'name': current_variant.item,
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			'dependent_attribute': current_item_attribute_details['dependent_attribute'],
			'dependent_attribute_details': current_item_attribute_details['dependent_attribute_details'],
			'values': {},
			'default_uom': current_item_attribute_details['default_uom'],
			'secondary_uom': current_item_attribute_details['secondary_uom'],
		}

		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'qty': round(variant.quantity, 3) if variant.quantity else 0,
						}
						break
		else:
			item['values']['default'] = {
				'qty': round(variants[0].quantity, 3) if variants[0].quantity else 0,
			}

		index = get_item_group_index(item_details, current_item_attribute_details)
		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				'dependent_attribute': current_item_attribute_details['dependent_attribute'],
				'dependent_attribute_details': current_item_attribute_details['dependent_attribute_details'],
				'additional_parameters': current_item_attribute_details['additional_parameters'],
				'items': [item],
			})
		else:
			item_details[index]['items'].append(item)

	return item_details


def save_recut_item_details(item_details):
	"""Parse grouped item JSON → flatten to WO Recut Detail child table rows."""
	item_details = update_if_string_instance(item_details)
	items = []
	row_index = 0
	table_index = -1

	for group in item_details:
		table_index += 1
		primary_attribute = group.get('primary_attribute')
		for item in group.get('items', []):
			item_name = item.get('name')
			item_attributes = item.get('attributes', {})
			values = item.get('values', {})

			if primary_attribute:
				for attr_value, val_data in values.items():
					qty = val_data.get('qty', 0)
					if not qty:
						continue
					attrs = dict(item_attributes)
					attrs[primary_attribute] = attr_value
					variant = get_or_create_variant(item_name, attrs)
					items.append({
						'item_variant': variant,
						'quantity': qty,
						'table_index': table_index,
						'row_index': row_index,
					})
			else:
				default_vals = values.get('default', {})
				qty = default_vals.get('qty', 0)
				if not qty:
					row_index += 1
					continue
				variant = get_or_create_variant(item_name, item_attributes)
				items.append({
					'item_variant': variant,
					'quantity': qty,
					'table_index': table_index,
					'row_index': row_index,
				})
			row_index += 1

	return items
