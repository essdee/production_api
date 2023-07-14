# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
import json
from itertools import groupby
from six import string_types
from frappe.model.document import Document
from frappe.utils import cstr, flt
from frappe import _, msgprint

from production_api.production_api.doctype.item.item import create_variant, get_attribute_details, get_variant
from production_api.production_api.doctype.item_price.item_price import get_item_variant_price
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index
from production_api.mrp_stock.stock_ledger import get_previous_sle
from production_api.mrp_stock.utils import get_stock_balance


class StockReconciliation(Document):
	def onload(self):
		item_details = fetch_stock_reconciliation_items(self.get('items'))
		self.set('print_item_details', json.dumps(item_details))
		self.set_onload('item_details', item_details)
	
	def before_validate(self):
		if(self.get('item_details')):
			items = save_stock_reconciliation_items(self.item_details)
			self.set('items', items)
		elif self.is_new() or not self.get('items'):
			frappe.throw('Add items to Stock Reconciliation.', title='Stock Reconciliation')
		self.set_warehouse()
		
	def set_warehouse(self):
		for item in self.items:
			item.warehouse = self.default_warehouse

	def validate(self):
		self.validate_data()
		self.validate_opening_stock()

	def validate_data(self):
		def _get_msg(table_num, row_num, msg):
			return _("Table # {0} Row # {1}:").format(table_num + 1, row_num + 1) + " " + msg

		self.validation_messages = []
		item_warehouse_combinations = []

		for row in self.items:
			# find duplicates
			key = [row.item, row.warehouse, row.lot]

			if key in item_warehouse_combinations:
				self.validation_messages.append(
					_get_msg(row.table_index, row.row_index, _("Same item, lot and warehouse combination already entered."))
				)
			else:
				item_warehouse_combinations.append(key)

			self.validate_item(row.item, row)

			# if both not specified
			if row.qty in ["", None] and row.rate in ["", None]:
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
					row.item, None, self.posting_date, self.posting_time, with_valuation_rate=True
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

	def validate_opening_stock(self):
		if self.purpose == "Opening Stock":
			for item in self.items:
				exists = frappe.db.exists("Stock Ledger Entry", {
					"item": item.item,
					"warehouse": item.warehouse,
					"lot": item.lot,
					"isCancelled": 0,
				})
				if exists:
					frappe.throw(f"{item.item}, {item.warehouse}, {item.lot} Already Exists. If you are adjusting the Stock Value please use 'Stock Reconciliation' in Purpose")

	def on_submit(self):
		self.update_stock_ledger()
	
	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Ledger Entry")
		self.make_sle_on_cancel()
	
	def update_stock_ledger(self):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		if self.docstatus == 0:
			return
		
		sl_entries = []
		for row in self.items:
			previous_sle = get_previous_sle(
				{
					"item": row.item,
					"lot": row.lot,
					"warehouse": row.warehouse,
					"posting_date": self.posting_date,
					"posting_time": self.posting_time,
				}
			)

			if previous_sle:
				if row.qty in ("", None):
					row.qty = previous_sle.get("qty_after_transaction", 0)

				if row.rate in ("", None):
					row.rate = previous_sle.get("valuation_rate", 0)

			if row.qty and not row.rate and not row.allow_zero_valuation_rate:
				frappe.throw(
					_("Valuation Rate required for Item {0} at row {1}").format(row.item_code, row.idx)
				)

			if (
				previous_sle
				and row.qty == previous_sle.get("qty_after_transaction")
				and (row.valuation_rate == previous_sle.get("valuation_rate") or row.qty == 0)
			) or (not previous_sle and not row.qty):
				continue

			sl_entries.append(self.get_sle_for_items(row))
		if not len(sl_entries):
			frappe.throw("Empty")
		make_sl_entries(sl_entries)

	def make_sle_on_cancel(self):
		from production_api.mrp_stock.stock_ledger import make_sl_entries

		sl_entries = []
		
		for row in self.items:
			sl_entries.append(self.get_sle_for_items(row))

		if sl_entries:
			sl_entries.reverse()
			make_sl_entries(sl_entries)
	
	def get_sle_for_items(self, row):
		# sl_dict = frappe._dict(
		# 	{
		# 		"item": d.get("item", None),
		# 		"warehouse": d.get("warehouse", None),
		# 		"lot": cstr(d.get("lot", None)).strip(),
		# 		"voucher_type": self.doctype,
		# 		"voucher_no": self.name,
		# 		"voucher_detail_no": d.name,
		# 		"qty": flt(d.get("qty", 0)),
		# 		"uom": d.get("uom", None),
		# 		"rate": d.get("rate", None),
		# 		"is_cancelled": 1 if self.docstatus == 2 else 0,
		# 		"posting_date": self.posting_date,
		# 		"posting_time": self.posting_time,
		# 	}
		# )

		# sl_dict.update(args)
		# return sl_dict
		"""Insert Stock Ledger Entries"""

		# if not serial_nos and row.serial_no:
		# 	serial_nos = get_serial_nos(row.serial_no)

		data = frappe._dict(
			{
				"doctype": "Stock Ledger Entry",
				"item": row.item,
				"lot": row.lot,
				"warehouse": row.warehouse,
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"voucher_detail_no": row.name,
				"qty": 0,
				"uom": row.uom,
				"is_cancelled": 1 if self.docstatus == 2 else 0,
				"valuation_rate": flt(row.rate, row.precision("rate")),
			}
		)

		data.qty_after_transaction = flt(row.qty, row.precision("qty"))

		if self.docstatus == 2:
			# if row.current_qty:
			# 	data.qty = -1 * row.current_qty
			# 	data.qty_after_transaction = flt(row.current_qty)
			# 	data.previous_qty_after_transaction = flt(row.qty)
			# 	data.valuation_rate = flt(row.current_valuation_rate)
			# 	data.stock_value = data.qty_after_transaction * data.valuation_rate
			# 	data.stock_value_difference = -1 * flt(row.amount_difference)
			# else:
			data.qty = row.qty
			data.qty_after_transaction = 0.0
			data.valuation_rate = flt(row.rate)
			# data.stock_value_difference = -1 * flt(row.amount_difference)

		return data

@frappe.whitelist()
def fetch_stock_reconciliation_items(items):
	items = [item.as_dict() for item in items]
	item_details = []
	items = sorted(items, key = lambda i: i['row_index'])
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_doc("Item Variant", variants[0]['item'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
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
				item['allow_zero_valuation_rate'] = variant.allow_zero_valuation_rate
				current_variant = frappe.get_doc("Item Variant", variant['item'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'qty': variant.qty,
							'rate': variant.rate,
							# 'tax': variant.tax,
						}
						break
		else:
			item['allow_zero_valuation_rate'] = variants[0].allow_zero_valuation_rate
			item['values']['default'] = {
				'qty': variants[0].qty,
				'rate': variants[0].rate,
				# 'tax': variants[0].tax
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

def save_stock_reconciliation_items(item_details):
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
						item1['lot'] = item.get('lot')
						item1['qty'] = values.get('qty')
						item1['uom'] = values.get('default_uom')
						item1['rate'] = values.get('rate')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['allow_zero_valuation_rate'] = item.get('allow_zero_valuation_rate', False)
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
					item1['lot'] = item.get('lot')
					item1['qty'] = item['values']['default'].get('qty')
					item1['uom'] = item.get('default_uom')
					item1['rate'] = item['values']['default'].get('rate')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['allow_zero_valuation_rate'] = item.get('allow_zero_valuation_rate', False)
					# item1['comments'] = item.get('comments')
					items.append(item1)
			row_index += 1
	return items