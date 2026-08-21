# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from itertools import groupby
from production_api.mrp_stock.doctype.stock_entry.stock_entry import get_uom_details
from six import string_types
import json
import frappe
from frappe import _, msgprint
from frappe.utils import cstr, flt
from frappe.model.document import Document
from production_api.mrp_stock.utils import get_stock_balance
from production_api.utils import update_if_string_instance, get_finishing_plan_dict, get_finishing_plan_list
from production_api.production_api.doctype.item.item import create_variant, get_attribute_details, get_variant
from production_api.production_api.doctype.item_price.item_price import get_item_variant_price
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index

class LotTransfer(Document):
	def refresh_cutting_bulk_lay_sheet(self):
		if self.get("cutting_bulk_lay_sheet"):
			from production_api.production_api.doctype.cutting_bulk_lay_sheets.cutting_bulk_lay_sheets import (
				refresh_bulk_status,
			)

			refresh_bulk_status(self.get("cutting_bulk_lay_sheet"))

	def onload(self):
		item_details = fetch_lot_transfer_items(self.get('items'))
		self.set('print_item_details', json.dumps(item_details))
		self.set_onload('item_details', item_details)

	def before_validate(self):
		if(self.get('item_details')) and self._action != "submit":
			items = save_lot_transfer_items(self.item_details)
			self.set('items', items)
		elif not self.get('items') or (
			self.is_new() and not self.flags.allow_from_cutting_plan
		):
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
					row.item, None, row.received_type, self.posting_date, self.posting_time, with_valuation_rate=True,lot=row.from_lot, uom=row.uom,
				)[1]
				if not row.rate:
					# try if there is a buying price list in default currency
					buying_rate = get_item_variant_price(row.item, variant_uom=row.uom)
					if buying_rate:
						row.rate = buying_rate
			
			# if not row.rate and not row.allow_zero_valuation_rate:
			# 	self.validation_messages.append(_get_msg(row.table_index, row.row_index, _("Could not find valuation rate.")))
			
			item_details = get_uom_details(row.item, row.uom, row.qty)
			row.set("stock_uom", item_details.get("stock_uom"))
			row.set("conversion_factor", item_details.get("conversion_factor"))
			row.stock_qty = flt(
				flt(row.qty) * flt(row.conversion_factor), self.precision("stock_qty", row)
			)
			row.stock_uom_rate = flt(
				flt(row.rate) / flt(row.conversion_factor), self.precision("stock_uom_rate", row)
			)
			row.amount = flt(flt(row.rate) * flt(row.qty), self.precision("amount", row))

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
		if self.finishing_plan:
			self.update_finishing_plan()
		self.make_repost_action()
		self.refresh_cutting_bulk_lay_sheet()
	
	def update_finishing_plan(self):
		doc = frappe.get_doc("Finishing Plan", self.finishing_plan)
		finishing_items = get_finishing_plan_dict(doc)
		for row in self.items:
			set_comb = update_if_string_instance(row.set_combination)
			key = (row.item, tuple(sorted(set_comb.items())))
			qty = row.qty
			if self.docstatus == 2:
				qty = qty * -1

			finishing_items[key]['lot_transferred'] += qty	

		finshing_items_list = get_finishing_plan_list(finishing_items)
		lot_transfer_list = update_if_string_instance(doc.lot_transfer_list)
		if self.docstatus == 2:
			del lot_transfer_list[self.name]
		else:
			lot_transfer_list[self.name] = frappe.utils.now_datetime().strftime("%d-%m-%Y %H:%M:%S")
		
		doc.lot_transfer_list = frappe.json.dumps(lot_transfer_list)
		doc.set("finishing_plan_details", finshing_items_list)
		doc.save()	

	def before_cancel(self):
		self.ignore_linked_doctypes = ("Stock Ledger Entry", "Repost Item Valuation")
		self.update_stock_ledger()

	def on_cancel(self):	
		if self.finishing_plan:
			self.update_finishing_plan()
		self.make_repost_action()
		self.refresh_cutting_bulk_lay_sheet()

	def make_repost_action(self):
		from production_api.mrp_stock.stock_ledger import repost_future_stock_ledger_entry
		repost_future_stock_ledger_entry(self)

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
					"qty": -flt(d.stock_qty),
					"rate": 0,
					"outgoing_rate": flt(d.stock_uom_rate),
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
					"qty": flt(d.stock_qty),
					"rate": flt(d.stock_uom_rate),
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
				"uom": d.stock_uom,
				"rate": 0,
				"is_cancelled": 1 if self.docstatus == 2 else 0,
			}
		)

		sl_dict.update(args)

		return sl_dict


def get_lot_transfer_target_lot(items):
	target_lots = {
		row.to_lot for row in items
		if flt(row.qty) > 0 and row.to_lot
	}
	if len(target_lots) != 1:
		frappe.throw("Make DC requires all Lot Transfer items to have one target Lot")
	return target_lots.pop()


def get_lot_transfer_delivery_items(transfer_items, work_order_items, target_lot):
	transfer_qty = {}
	transfer_uom = {}
	for row in transfer_items:
		if flt(row.qty) <= 0:
			continue
		transfer_qty.setdefault(row.item, 0)
		transfer_qty[row.item] += flt(row.qty)
		transfer_uom.setdefault(row.item, row.uom)
		if transfer_uom[row.item] != row.uom:
			frappe.throw(f"Item {row.item} has multiple UOMs in the Lot Transfer")

	delivery_items = []
	first_matching_row = {}
	for row in work_order_items:
		as_dict = getattr(row, "as_dict", None)
		item = frappe._dict(as_dict() if callable(as_dict) else dict(row))
		item.lot = target_lot
		item.ref_doctype = "Work Order Deliverables"
		item.ref_docname = item.name
		item.comments = None
		item.delivered_quantity = 0
		available_qty = max(flt(item.pending_quantity), 0)
		item.qty = available_qty

		remaining_qty = flt(transfer_qty.get(item.item_variant))
		if remaining_qty > 0:
			first_matching_row.setdefault(item.item_variant, len(delivery_items))
			if transfer_uom[item.item_variant] != item.uom:
				frappe.throw(
					f"UOM mismatch for Item {item.item_variant}: "
					f"Lot Transfer uses {transfer_uom[item.item_variant]}, "
					f"but Work Order uses {item.uom}"
				)
			delivered_qty = min(remaining_qty, available_qty)
			item.delivered_quantity = delivered_qty
			transfer_qty[item.item_variant] = remaining_qty - delivered_qty

		delivery_items.append(item)

	items_not_in_work_order = []
	for item_variant, qty in transfer_qty.items():
		excess_qty = flt(qty, 3)
		if excess_qty <= 0:
			continue

		if item_variant in first_matching_row:
			item = delivery_items[first_matching_row[item_variant]]
			item.delivered_quantity = flt(item.delivered_quantity + excess_qty, 3)
			item.qty = max(flt(item.qty), item.delivered_quantity)
			continue

		items_not_in_work_order.append(item_variant)

	if items_not_in_work_order:
		frappe.throw(
			"The following Lot Transfer items are not in the selected Work Order "
			f"deliverables: {', '.join(sorted(items_not_in_work_order))}"
		)

	return delivery_items


@frappe.whitelist()
def get_delivery_challan_details(doc_name, work_order, from_location):
	lot_transfer = frappe.get_doc("Lot Transfer", doc_name)
	if lot_transfer.docstatus != 1:
		frappe.throw("Submit the Lot Transfer before making a Delivery Challan")
	if not from_location or not frappe.db.exists("Supplier", from_location):
		frappe.throw("Select a valid From Location")

	work_order_doc = frappe.get_cached_doc("Work Order", work_order)
	if (
		work_order_doc.docstatus != 1
		or work_order_doc.open_status != "Open"
		or work_order_doc.is_delivered
	):
		frappe.throw("Select an open, submitted Work Order")

	target_lot = get_lot_transfer_target_lot(lot_transfer.items)
	if work_order_doc.lot != target_lot:
		frappe.throw(
			f"Work Order {work_order} must belong to target Lot {target_lot}"
		)

	delivery_items = get_lot_transfer_delivery_items(
		lot_transfer.items, work_order_doc.deliverables, target_lot
	)
	from production_api.production_api.doctype.delivery_challan.delivery_challan import fetch_item_details
	from production_api.production_api.doctype.purchase_order.purchase_order import get_address_display
	from production_api.production_api.doctype.supplier.supplier import get_primary_address

	from_address = get_primary_address(from_location)
	if not from_address:
		frappe.throw(f"Primary Address is not configured for From Location {from_location}")

	supplier_address = work_order_doc.supplier_address or get_primary_address(work_order_doc.supplier)
	if not supplier_address:
		frappe.throw(f"Primary Address is not configured for Supplier {work_order_doc.supplier}")

	return {
		"item_details": fetch_item_details(
			delivery_items,
			work_order_doc.production_detail,
			target_lot,
		),
		"work_order": work_order_doc.name,
		"lot": target_lot,
		"item": work_order_doc.item,
		"production_detail": work_order_doc.production_detail,
		"process_name": work_order_doc.process_name,
		"includes_packing": work_order_doc.includes_packing,
		"is_internal_unit": work_order_doc.is_internal_unit,
		"from_location": from_location,
		"from_address": from_address,
		"from_address_details": get_address_display(from_address),
		"supplier": work_order_doc.supplier,
		"supplier_name": work_order_doc.supplier_name,
		"supplier_address": supplier_address,
		"supplier_address_details": work_order_doc.supplier_address_details,
	}

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
			'received_type':variants[0].get('received_type')
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
							'qty': variant.get('qty'),
							'rate': variant.get('rate'),
							"set_combination": frappe.json.loads(variant.get('set_combination', {}))
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
						item1['set_combination'] = frappe.json.dumps(values.get('set_combination', {}))
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['received_type'] = values.get('received_type')
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
					item1['received_type'] = item.get('received_type')
					# item1['comments'] = item.get('comments')
					items.append(item1)
			row_index += 1
	return items
