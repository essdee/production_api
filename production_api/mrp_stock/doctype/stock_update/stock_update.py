# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from itertools import groupby
from frappe.model.document import Document
from production_api.utils import update_if_string_instance
from production_api.mrp_stock.utils import get_stock_balance
from production_api.production_api.doctype.item.item import get_or_create_variant
from production_api.production_api.doctype.item.item import get_attribute_details
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index


class StockUpdate(Document):
	def before_submit(self):
		for row in self.stock_update_details:
			if self.update_type == 'Reduce' and row.available_stock < row.update_diff_qty :
				frappe.throw(f"{row.item_variant} is not Available to Reduce {row.update_diff_qty - row.available_stock}")
			item_name = frappe.get_value("Item Variant", row.item_variant, "item")
			dept_attr = frappe.get_value("Item", item_name, "dependent_attribute")
			if dept_attr:
				frappe.throw("Can't update Dependent Attribute Item")

		self.update_uom_details()

	def on_submit(self):
		self.update_stock_ledger()

	def on_cancel(self):
		self.ignore_linked_doctypes = ('Stock Ledger Entry', 'Repost Item Valuation')
		self.update_stock_ledger()

	def onload(self):
		item_details = fetch_stock_entry_items(self.get('stock_update_details'))
		self.set_onload('item_details', item_details)

	def before_validate(self):
		if(self.get('item_details')) and self._action != "submit":
			items = save_stock_entry_items(self.item_details, self.posting_date, self.posting_time, self.warehouse)
			self.set('stock_update_details', items)

	def update_uom_details(self):
		from production_api.mrp_stock.doctype.stock_entry.stock_entry import get_uom_details
		for row in self.stock_update_details:
			item_details = get_uom_details(row.item_variant, row.uom, row.update_diff_qty)
			row.set("stock_uom", item_details.get("stock_uom"))
			row.set("conversion_factor", item_details.get("conversion_factor"))
			row.stock_qty = flt(
				flt(row.update_diff_qty) * flt(row.conversion_factor), self.precision("stock_qty", row)
			)

	def update_stock_ledger(self):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		sl_entries = self.get_sl_entries()

		if self.docstatus == 2:
			sl_entries.reverse()
		make_sl_entries(sl_entries)

	def get_sl_entries(self):
		items = []
		for row in self.stock_update_details:
			sl_dict = frappe._dict({
				"item": row.item_variant,
				"warehouse": self.warehouse,
				"received_type": row.received_type,
				"lot": row.lot,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"voucher_detail_no": row.name,
				"qty": row.update_diff_qty * (1 if self.update_type == 'Add' else -1),
				"uom": row.stock_uom,
				"rate": row.rate,
				"valuation_rate": row.rate,
				"is_cancelled": 1 if self.docstatus == 2 else 0,
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
			})
			items.append(sl_dict)
		return items

def save_stock_entry_items(item_details, post_date, post_time, location):
	"""
		Save item details to stock entry
	"""
	item_details = update_if_string_instance(item_details)
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
						uom = item.get('default_uom')
						rec_type = item.get('received_type')
						lot = item.get('lot')
						variant_name = get_or_create_variant(item_name, item_attributes)
						qty, rate = get_stock_balance(
							variant_name, location, rec_type, posting_date=post_date, posting_time=post_time, with_valuation_rate=True, uom=uom, lot=lot
						)	
						item1['item_variant'] = variant_name
						item1['lot'] = lot
						item1['uom'] = uom
						item1['update_diff_qty'] = values.get('qty')
						item1['rate'] = rate
						item1['available_stock'] = qty
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['received_type'] = rec_type
						items.append(item1)
			else:
				if item['values'].get('default') and item['values']['default'].get('qty'):
					item1 = {}
					variant_name = get_or_create_variant(item_name, item_attributes)
					uom = item.get('default_uom')
					rec_type = item.get('received_type')
					lot = item.get('lot')
					item1['item_variant'] = variant_name
					item1['lot'] = lot
					item1['uom'] = uom
					qty, rate = get_stock_balance(
						variant_name, location, rec_type, posting_date=post_date, posting_time=post_time, with_valuation_rate=True, uom=uom, lot=lot
					)	
					print(qty)
					print(rate)
					print("IIIIIIIIIIIIIIIIII")
					item1['rate'] = rate
					item1['available_stock'] = qty
					item1['update_diff_qty'] = item['values']['default'].get('qty')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['received_type'] = item.get('received_type')
					items.append(item1)
			row_index += 1
	return items

def fetch_stock_entry_items(items):
	if len(items) > 0 and type(items[0]) != dict:
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
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			'values': {},
			'default_uom': variants[0].get('uom') or current_item_attribute_details['default_uom'],
			'received_type':variants[0]['received_type'],
			'remarks': variants[0].get('remarks', None),
		}

		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							"available_stock": variant.get('available_stock', 0),
							'qty': variant.get('update_diff_qty',0),
							'rate': variant.get('rate',0),
						}
						break
		else:
			item['values']['default'] = {
				"available_stock": variants[0].get('available_stock', 0),
				'qty': variants[0].get('update_diff_qty', 0),
				'rate': variants[0].get('rate', 0),
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
	return item_details