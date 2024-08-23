# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from itertools import groupby
from six import string_types
import json
import frappe
from frappe import _, msgprint
from frappe.utils import cstr, flt
from frappe.model.mapper import get_mapped_doc
from frappe.model.document import Document

from production_api.production_api.doctype.item.item import create_variant, get_attribute_details, get_variant
from production_api.production_api.doctype.item_price.item_price import get_item_variant_price
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index
from production_api.mrp_stock.utils import get_stock_balance

class StockEntry(Document):
	def onload(self):
		item_details = fetch_stock_entry_items(self.get('items'))
		self.set('print_item_details', json.dumps(item_details))
		self.set_onload('item_details', item_details)

	def before_validate(self):
		if(self.get('item_details')) and self._action != "submit":
			items = save_stock_entry_items(self.item_details)
			self.set('items', items)
		elif self.is_new() or not self.get('items'):
			frappe.throw('Add items to Stock Entry.', title='Stock Entry')

	def validate(self):
		self.validate_data()
		self.validate_warehouse()
		self.calculate_rate_and_amount()

	def validate_data(self):
		def _get_msg(table_num, row_num, msg):
			return _("Table # {0} Row # {1}:").format(table_num + 1, row_num + 1) + " " + msg

		self.validation_messages = []
		item_lot_combinations = []

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
					row.item, None, self.posting_date, self.posting_time, with_valuation_rate=True
				)[1]
				if not row.rate:
					# try if there is a buying price list in default currency
					buying_rate = get_item_variant_price(row.item)
					if buying_rate:
						row.rate = buying_rate
			
			# if not row.rate:
			# 	self.validation_messages.append(_get_msg(row.table_index, row.row_index, _("Could not find valuation rate.")))

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

	def validate_warehouse(self):
		source_mandatory = [
			"Material Issue",
			"Send to Warehouse",
			"Receive at Warehouse",
			"Material Consumed"
		]

		target_mandatory = [
			"Material Receipt",
			"Send to Warehouse",
			"Receive at Warehouse"
		]

		if self.purpose in source_mandatory:
			if self.purpose not in target_mandatory:
				self.to_warehouse = None
			if not self.from_warehouse:
				frappe.throw("Source Warehouse is Mandatory")
		if self.purpose in target_mandatory:
			if  self.purpose not in source_mandatory:
				self.from_warehouse = None
			if not self.to_warehouse:
				frappe.throw("Target Warehouse is Mandatory")
	
	def calculate_rate_and_amount(self):
		self.total_amount = sum([flt(item.qty) * flt(item.rate) for item in self.get("items")]) + flt(self.additional_amount)

	def on_submit(self):
		self.update_stock_ledger()
		self.update_transferred_qty()
	
	def before_cancel(self):
		self.ignore_linked_doctypes = ("Stock Ledger Entry")
		self.update_stock_ledger()
		self.update_transferred_qty()
	
	def update_stock_ledger(self):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		if self.docstatus == 0:
			return
		
		sl_entries = []

		from_warehouse = None
		if self.purpose == "Receive at Warehouse":
			from_warehouse = frappe.get_single("Stock Settings").transit_warehouse
		# make sl entries for source warehouse first
		self.get_sle_for_source_warehouse(sl_entries, warehouse=from_warehouse)

		to_warehouse = None
		if self.purpose == "Send to Warehouse":
			to_warehouse = frappe.get_single("Stock Settings").transit_warehouse
		# SLE for target warehouse
		self.get_sle_for_target_warehouse(sl_entries, warehouse=to_warehouse)

		# reverse sl entries if cancel
		if self.docstatus == 2:
			sl_entries.reverse()
		
		make_sl_entries(sl_entries)

	def get_sle_for_source_warehouse(self, sl_entries, warehouse=None):
		if not warehouse:
			warehouse = self.from_warehouse
		if cstr(warehouse):
			for d in self.get("items"):
				sle = self.get_sl_entries(
					d, 
					{
						"warehouse": cstr(warehouse),
						"qty": -flt(d.qty),
						"rate": 0,
						"outgoing_rate": flt(d.rate)
					}
				)
				if cstr(self.to_warehouse):
					sle.dependant_sle_voucher_detail_no = d.name

				sl_entries.append(sle)

	def get_sle_for_target_warehouse(self, sl_entries, warehouse=None):
		if not warehouse:
			warehouse = self.to_warehouse
		if cstr(warehouse):
			for d in self.get("items"):
				sle = self.get_sl_entries(
					d,
					{
						"warehouse": cstr(warehouse),
						"qty": flt(d.qty),
						"rate": flt(d.rate),
					},
				)

				sl_entries.append(sle)

	def get_sl_entries(self, d, args):
		sl_dict = frappe._dict(
			{
				"item": d.get("item", None),
				"warehouse": d.get("warehouse", None),
				"lot": d.get("lot"),
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"voucher_detail_no": d.name,
				"qty": (self.docstatus == 1 and 1 or -1) * flt(d.get("qty", 0)),
				"uom": d.uom,
				"rate": 0,
				"is_cancelled": 1 if self.docstatus == 2 else 0,
				"remarks": d.remarks,
			}
		)

		sl_dict.update(args)

		return sl_dict
	
	def update_transferred_qty(self):
		if self.purpose == "Receive at Warehouse":
			stock_entries = {}
			stock_entries_child_list = []
			for d in self.items:
				if not (d.against_stock_entry and d.ste_detail):
					continue

				stock_entries_child_list.append(d.ste_detail)
				transferred_qty = frappe.get_all(
					"Stock Entry Detail",
					fields=["sum(qty) as qty"],
					filters={
						"against_stock_entry": d.against_stock_entry,
						"ste_detail": d.ste_detail,
						"docstatus": 1,
					},
				)

				stock_entries[(d.against_stock_entry, d.ste_detail)] = (
					transferred_qty[0].qty if transferred_qty and transferred_qty[0] else 0.0
				) or 0.0

			if not stock_entries:
				return None

			cond = ""
			for data, transferred_qty in stock_entries.items():
				cond += """ WHEN (parent = %s and name = %s) THEN %s
					""" % (
					frappe.db.escape(data[0]),
					frappe.db.escape(data[1]),
					transferred_qty,
				)

			if stock_entries_child_list:
				frappe.db.sql(
					""" UPDATE `tabStock Entry Detail`
					SET
						transferred_qty = CASE {cond} END
					WHERE
						name in ({ste_details}) """.format(
						cond=cond, ste_details=",".join(["%s"] * len(stock_entries_child_list))
					),
					tuple(stock_entries_child_list),
				)

			target_doc = frappe.get_doc("Stock Entry", self.outgoing_stock_entry)
			total_qty = 0
			total_transferred = 0
			for item in target_doc.items:
				total_qty += item.qty
				total_transferred += item.transferred_qty
			target_doc.set("per_transferred", total_transferred/total_qty*100)
			target_doc.save()

@frappe.whitelist()
def fetch_stock_entry_items(items):
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
			'remarks': variants[0]['remarks'],
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
							'against_stock_entry': variant.get("against_stock_entry", None),
							'ste_detail': variant.get("ste_detail", None),
							'transferred_qty': variant.get("transferred_qty", None),
							# 'tax': variant.tax,
						}
						break
		else:
			item['values']['default'] = {
				'qty': variants[0].qty,
				'rate': variants[0].rate,
				'against_stock_entry': variants[0].get("against_stock_entry", None),
				'ste_detail': variants[0].get("ste_detail", None),
				'transferred_qty': variants[0].get("transferred_qty", None),
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

def save_stock_entry_items(item_details):
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
						item1['uom'] = item.get('default_uom')
						item1['qty'] = values.get('qty')
						item1['rate'] = values.get('rate')
						item1['against_stock_entry'] = values.get("against_stock_entry", None)
						item1['ste_detail'] = values.get("ste_detail", None)
						item1['transferred_qty'] = values.get("transferred_qty", None)
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['remarks'] = item.get('remarks')
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
					item1['uom'] = item.get('default_uom')
					item1['qty'] = item['values']['default'].get('qty')
					item1['rate'] = item['values']['default'].get('rate')
					item1['against_stock_entry'] = item['values']['default'].get("against_stock_entry", None)
					item1['ste_detail'] = item['values']['default'].get("ste_detail", None)
					item1['transferred_qty'] = item['values']['default'].get("transferred_qty", None)
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['remarks'] = item.get('remarks')
					items.append(item1)
			row_index += 1
	return items

@frappe.whitelist()
def make_stock_in_entry(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.purpose = "Receive at Warehouse"
		target.set_onload("item_details", fetch_stock_entry_items(target.items))
		# target.set_missing_values()

	def update_item(source_doc, target_doc, source_parent):
		# target_doc.t_warehouse = ""

		# if source_doc.material_request_item and source_doc.material_request:
		# 	add_to_transit = frappe.db.get_value("Stock Entry", source_name, "add_to_transit")
		# 	if add_to_transit:
		# 		warehouse = frappe.get_value(
		# 			"Material Request Item", source_doc.material_request_item, "warehouse"
		# 		)
		# 		target_doc.t_warehouse = warehouse

		# target_doc.s_warehouse = source_doc.t_warehouse
		target_doc.qty = source_doc.qty - source_doc.transferred_qty

	doclist = get_mapped_doc(
		"Stock Entry",
		source_name,
		{
			"Stock Entry": {
				"doctype": "Stock Entry",
				"field_map": {"name": "outgoing_stock_entry"},
				"validation": {"docstatus": ["=", 1]},
			},
			"Stock Entry Detail": {
				"doctype": "Stock Entry Detail",
				"field_map": {
					"name": "ste_detail",
					"parent": "against_stock_entry",
					# "serial_no": "serial_no",
					# "batch_no": "batch_no",
				},
				"postprocess": update_item,
				"condition": lambda doc: flt(doc.qty) - flt(doc.transferred_qty) > 0.01,
			},
		},
		target_doc,
		set_missing_values,
	)

	return doclist