# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from itertools import groupby
from six import string_types
import json
import frappe
from frappe import _, msgprint
from frappe.utils import cstr, flt
from frappe.model.document import Document
from production_api.mrp_stock.utils import get_stock_balance

from production_api.production_api.doctype.item.item import create_variant, get_attribute_details, get_variant
from production_api.production_api.doctype.item_price.item_price import get_item_variant_price
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index

class LotTransfer(Document):
	def onload(self):
		item_details = fetch_lot_transfer_items(self.get('items'))
		self.set('print_item_details', json.dumps(item_details))
		self.set_onload('item_details', item_details)

	def before_validate(self):
		if(self.get('item_details')) and self._action != "submit":
			items = save_lot_transfer_items(self.item_details)
			self.set('items', items)
		elif self.is_new() or not self.get('items'):
			frappe.throw('Add items to Stock Entry.', title='Stock Entry')
		
	def validate(self):
		self.validate_data()
		pass

	def validate_data(self):
		def _get_msg(table_num, row_num, msg):
			return _("Table # {0} Row # {1}:").format(table_num + 1, row_num + 1) + " " + msg

		self.validation_messages = []
		# item_lot_combinations = []

		for row in self.items:
			# find duplicates
			# key = [row.item, row.lot]

			# if key in item_lot_combinations:
			# 	self.validation_messages.append(
			# 		_get_msg(row.table_index, row.row_index, _("Same item, lot combination already entered."))
			# 	)
			# else:
			# 	item_lot_combinations.append(key)

			self.validate_item(row.item, row)

			# if both not specified
			if row.qty in ["", None, 0] and row.rate in ["", None, 0]:
				self.validation_messages.append(
					_get_msg(row.table_index, row.row_index, _("Please specify either Quantity or Valuation Rate or both"))
				)

			# do not allow negative quantity
			if flt(row.qty) < 0:
				self.validation_messages.append(_get_msg(row.table_index, row.row_index, _("Negative Quantity is not allowed")))

			# do not allow negative valuation
			if flt(row.rate) < 0:
				self.validation_messages.append(_get_msg(row.table_index, row.row_index, _("Negative Valuation Rate is not allowed")))
			if row.qty and row.rate in ["", None, 0]:
				row.rate = get_stock_balance(
					row.item, None, self.posting_date, self.posting_time, with_valuation_rate=True,lot=row.from_lot,
				)[1]
				if not row.rate:
					# try if there is a buying price list in default currency
					buying_rate = get_item_variant_price(row.item)
					if buying_rate:
						row.rate = buying_rate
			
			if not row.rate and not row.allow_zero_valuation_rate:
				self.validation_messages.append(_get_msg(row.table_index, row.row_index, _("Could not find valuation rate.")))

		# throw all validation messages
		if self.validation_messages:
			for msg in self.validation_messages:
				msgprint(msg)

			raise frappe.ValidationError(self.validation_messages)
	
	def validate_item(self, item, row):
		from production_api.production_api.doctype.item.item import (
			validate_cancelled_item,
			validate_disabled,
			validate_is_stock_item,
		)

		# using try except to catch all validation msgs and display together
		try:
			item = frappe.get_value("Item Variant", item, "item")

			# end of life and stock item
			validate_disabled(item)
			validate_is_stock_item(item)

			# docstatus should be < 2
			validate_cancelled_item(item)

		except Exception as e:
			self.validation_messages.append(_("Row #") + " " + ("%d: " % (row.idx)) + cstr(e))
	
	def on_submit(self):
		self.update_stock_ledger()
	
	def before_cancel(self):
		self.update_stock_ledger()

	def update_stock_ledger(self):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		if self.docstatus == 0:
			return
		
		sl_entries = []

		# make sl entries for source lot first
		self.get_sle_for_source_lot(sl_entries)

		# SLE for target lot
		self.get_sle_for_target_lot(sl_entries)

		# reverse sl entries if cancel
		if self.docstatus == 2:
			sl_entries.reverse()
		
		make_sl_entries(sl_entries)
	
	def get_sle_for_source_lot(self, sl_entries):
		for d in self.get("items"):
			sle = self.get_sl_entries(
				d, 
				{
					"warehouse": cstr(d.warehouse),
					"qty": -flt(d.qty),
					"rate": 0,
					"outgoing_rate": flt(d.rate),
					"lot": cstr(d.from_lot),
				}
			)

			sl_entries.append(sle)

	def get_sle_for_target_lot(self, sl_entries):
		for d in self.get("items"):
			sle = self.get_sl_entries(
				d,
				{
					"warehouse": cstr(d.warehouse),
					"qty": flt(d.qty),
					"rate": flt(d.rate),
					"lot": cstr(d.to_lot),
				},
			)

			sl_entries.append(sle)

	def get_sl_entries(self, d, args):
		sl_dict = frappe._dict(
			{
				"item": d.get("item", None),
				"warehouse": d.get("warehouse", None),
				# "lot": d.get("lot"),
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"voucher_detail_no": d.name,
				"uom": d.uom,
				"rate": 0,
				"is_cancelled": 1 if self.docstatus == 2 else 0,
			}
		)

		sl_dict.update(args)

		return sl_dict

@frappe.whitelist()
def fetch_lot_transfer_items(items):
	items = [item.as_dict() for item in items]
	item_details = []
	items = sorted(items, key = lambda i: i['row_index'])
	for key, variants in groupby(items, lambda i: i['row_index']):
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
			# 'comments': variants[0]['comments'],
		}

		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_doc("Item Variant", variant['item'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'qty': variant.qty,
							'rate': variant.rate,
						}
						break
		else:
			item['values']['default'] = {
				'qty': variants[0].qty,
				'rate': variants[0].rate,
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

def save_lot_transfer_items(item_details):
	"""
		Save item details to stock entry
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
						item1['item'] = variant_name
						item1['from_lot'] = item.get('lot')
						item1['to_lot'] = item.get('to_lot')
						item1['warehouse'] = item.get('warehouse')
						item1['uom'] = item.get('default_uom')
						item1['qty'] = values.get('qty')
						item1['rate'] = values.get('rate')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						# item1['comments'] = item.get('comments')
						items.append(item1)
			else:
				if item['values'].get('default') and item['values']['default'].get('qty'):
					item1 = {}
					variant_name = get_variant(item_name, item_attributes)
					if not variant_name:
						variant1 = create_variant(item_name, item_attributes)
						variant1.insert()
						variant_name = variant1.name
					item1['item'] = variant_name
					item1['from_lot'] = item.get('lot')
					item1['to_lot'] = item.get('to_lot')
					item1['warehouse'] = item.get('warehouse')
					item1['uom'] = item.get('default_uom')
					item1['qty'] = item['values']['default'].get('qty')
					item1['rate'] = item['values']['default'].get('rate')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					# item1['comments'] = item.get('comments')
					items.append(item1)
			row_index += 1
	return items