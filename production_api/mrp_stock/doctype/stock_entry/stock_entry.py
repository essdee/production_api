# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe, json
from six import string_types
from itertools import groupby
from frappe import _, msgprint
from frappe.utils import cstr, flt
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from production_api.utils import update_if_string_instance
from production_api.mrp_stock.utils import get_conversion_factor, get_stock_balance
from production_api.production_api.doctype.item_price.item_price import get_item_variant_price
from production_api.production_api.doctype.item.item import create_variant, get_attribute_details, get_variant
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index
from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import make_cut_bundle_ledger, cancel_cut_bundle_ledger

class StockEntry(Document):
	def onload(self):
		ipd = None
		if self.purpose == "DC Completion":
			ipd = frappe.get_value("Delivery Challan",self.against_id,"production_detail")
		elif self.purpose == "GRN Completion":
			wo = frappe.get_value("Goods Received Note", self.against_id, "against_id")
			ipd = frappe.get_value("Work Order", wo, "production_detail")
			
		item_details = fetch_stock_entry_items(self.get('items'), ipd=ipd)
		self.set('print_item_details', json.dumps(item_details))
		self.set_onload('item_details', item_details)

	def before_validate(self):
		if self.cut_panel_movement and self.purpose not in ["Send to Warehouse", "Receive at Warehouse", "DC Completion", "GRN Completion"]:
			frappe.throw(f"For Bundle Movement Purpose {self.purpose} is not Applicable")

		if(self.get('item_details')) and self._action != "submit":
			items = save_stock_entry_items(self.item_details)
			self.set('items', items)
		elif not self.flags.allow_from_sms and not self.flags.allow_from_dc and not self.flags.allow_from_summary and not self.flags.allow_from_grn and self.is_new() or not self.get('items'):
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
					row.item, None, row.received_type, self.posting_date, self.posting_time, with_valuation_rate=True, uom=row.uom,
				)[1]
				if not row.rate:
					# try if there is a buying price list in default currency
					buying_rate = get_item_variant_price(row.item, variant_uom=row.uom)
					if buying_rate:
						row.rate = buying_rate

			# if not row.rate:
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
			item = frappe.get_cached_value("Item Variant", item, "item")

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
			"Material Consumed",
			"Stock Dispatch",
			"DC Completion",
		]

		target_mandatory = [
			"Material Receipt",
			"Send to Warehouse",
			"Receive at Warehouse",
			"DC Completion",
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
		self.total_amount = sum([flt(item.amount) for item in self.get("items")]) + flt(self.additional_amount)

	def on_submit(self):
		self.update_stock_ledger()
		self.make_repost_action()
		self.update_transferred_qty()
		if self.purpose == "DC Completion" or self.purpose == "GRN Completion":
			if self.purpose == "DC Completion":
				res = frappe.db.sql(
					f"""
						Select sum(delivered_quantity) as total, sum(delivered_quantity - ste_delivered_quantity) as delivered from
						`tabDelivery Challan Item` where parent = '{self.against_id}'
					""", as_dict=True
				)
			else:
				res = frappe.db.sql(
					f"""
						Select sum(quantity) as total, sum(ste_delivered_quantity) as delivered from
						`tabGoods Received Note Item` where parent = '{self.against_id}'
					""", as_dict=True
				)
			total_quantity = res[0].total
			now_delivered = total_quantity - res[0].delivered
			doc = frappe.get_doc(self.against, self.against_id)	
			qty = 0
			for ste_item in self.items:
				for item in doc.items:
					if ste_item.against_id_detail == item.name:
						check = True
						if self.purpose == "GRN Completion":
							check = ste_item.received_type == item.received_type
						if check:	
							item.ste_delivered_quantity += ste_item.qty
							qty += ste_item.qty
							break
						
			if round(qty - now_delivered,3) > round(total_quantity,3):
				frappe.throw("High Amount of Items Received")
			x = qty / total_quantity
			x = x * 100
			self.per_transferred += x
			doc.ste_transferred_percent = doc.ste_transferred_percent + x
			doc.ste_transferred += qty
			if round(doc.ste_transferred,2) == round(doc.total_delivered_qty,2):
				doc.transfer_complete = 1
			doc.ste_transferred_percent = round(doc.ste_transferred_percent, 2)
			doc.save()
		if self.cut_panel_movement:
			cpm_doc = frappe.get_doc("Cut Panel Movement", self.cut_panel_movement)	
			cpm_doc.against = self.doctype
			cpm_doc.against_id = self.name
			cpm_doc.save()
			from_warehouse, to_warehouse = self.get_from_and_to_warehouse()

			from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import get_cut_bundle_entry
			bundles, collapsed_details = get_cut_bundle_entry(cpm_doc, self, from_warehouse, -1)
			make_cut_bundle_ledger(bundles, collapsed_details)
			bundles, collapsed_details = get_cut_bundle_entry(cpm_doc, self, to_warehouse, 1)
			make_cut_bundle_ledger(bundles, collapsed_details)

	def get_from_and_to_warehouse(self):
		from_warehouse = None
		to_warehouse = None
		if self.purpose == "Send to Warehouse":
			from_warehouse = self.from_warehouse
			if self.skip_transit:
				to_warehouse = self.to_warehouse
			else:	
				to_warehouse = frappe.get_single("Stock Settings").transit_warehouse
		else:
			from_warehouse = frappe.get_single("Stock Settings").transit_warehouse
			to_warehouse = self.to_warehouse

		return from_warehouse, to_warehouse

	def before_cancel(self):
		self.ignore_linked_doctypes = ("Stock Ledger Entry", "Stock Reservation Entry", "Delivery Challan", "Repost Item Valuation", "Cut Bundle Movement Ledger")
		self.update_stock_ledger()
		self.make_repost_action()
		self.update_transferred_qty()
		if self.purpose == "DC Completion" or self.purpose == "GRN Completion":
			doctype = "tabGoods Received Note Item"
			field = "quantity"
			if self.purpose == "DC Completion":
				doctype = "tabDelivery Challan Item"
				field = "delivered_quantity"

			res = frappe.db.sql(
				f"""
					Select sum({field}) as total from `{doctype}` where parent = '{self.against_id}'
				""", as_dict=True
			)
			total_quantity = res[0].total
			doc = frappe.get_doc(self.against, self.against_id)
			qty = 0
			for ste_item in self.items:
				for item in doc.items:
					if ste_item.against_id_detail == item.name:
						check = True
						if self.purpose == "GRN Completion":
							check = ste_item.received_type == item.received_type
						if check:
							item.ste_delivered_quantity -= ste_item.qty
							qty += ste_item.qty
							break
			x = qty / total_quantity
			x = x * 100
			doc.ste_transferred_percent = doc.ste_transferred_percent - x
			doc.ste_transferred = doc.ste_transferred - qty
			self.per_transferred -= x
			if doc.ste_transferred < doc.total_delivered_qty:
				doc.transfer_complete = 0
			doc.ste_transferred_percent = round(doc.ste_transferred_percent, 2)
			doc.save()
		if self.cut_panel_movement:
			cpm_doc = frappe.get_doc("Cut Panel Movement", self.cut_panel_movement)	
			if self.purpose == "Send to Warehouse":
				cpm_doc.against = None
				cpm_doc.against_id = None
				cpm_doc.save()
			from_warehouse, to_warehouse = self.get_from_and_to_warehouse()

			from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import get_cut_bundle_entry
			bundles, collapsed_bundles = get_cut_bundle_entry(cpm_doc, self, from_warehouse, -1, cancelled=1)
			cancel_cut_bundle_ledger(bundles)
			bundles, collapsed_bundles = get_cut_bundle_entry(cpm_doc, self, to_warehouse, 1, cancelled=1)
			cancel_cut_bundle_ledger(bundles)

		self.revert_stock_transfer_entries()
	
	def make_repost_action(self):
		from production_api.mrp_stock.stock_ledger import repost_future_stock_ledger_entry
		repost_future_stock_ledger_entry(self)

	def revert_stock_transfer_entries(self):
		sre_list = frappe.get_list("Stock Reservation Entry" , {
			"stock_entry" : self.name
		}, pluck = 'name')

		for sre in sre_list:
			doc = frappe.get_doc("Stock Reservation Entry", sre)
			doc.delivered_qty = 0
			doc.db_update()
			doc.update_status()
			doc.update_reserved_stock_in_bin()

	def update_stock_ledger(self):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		if self.docstatus == 0:
			return
		
		sl_entries = []

		from_warehouse = None
		if self.purpose == "Receive at Warehouse" or self.purpose == "DC Completion" or self.purpose == "GRN Completion":
			from_warehouse = frappe.get_single("Stock Settings").transit_warehouse
		# make sl entries for source warehouse first
		self.get_sle_for_source_warehouse(sl_entries, warehouse=from_warehouse)
		to_warehouse = None
		if self.purpose == "Send to Warehouse" and not self.skip_transit:
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
						"qty": -flt(d.stock_qty),
						"rate": 0,
						"outgoing_rate": flt(d.stock_uom_rate)
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
						"qty": flt(d.stock_qty),
						"rate": flt(d.stock_uom_rate),
					},
				)

				sl_entries.append(sle)

	def get_sl_entries(self, d, args):
		sl_dict = frappe._dict(
			{
				"item": d.get("item", None),
				"warehouse": d.get("warehouse", None),
				"received_type":d.get("received_type",None),
				"lot": d.get("lot"),
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"voucher_detail_no": d.name,
				"qty": (self.docstatus == 1 and 1 or -1) * flt(d.get("stock_qty", 0)),
				"uom": d.stock_uom,
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
def fetch_stock_entry_items(items, ipd=None):
	if len(items) > 0 and type(items[0]) != dict:
		items = [item.as_dict() for item in items]
	item_details = []
	ipd_doc = None
	if ipd:
		ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
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
			'received_type':variants[0]['received_type'],
			'remarks': variants[0].get('remarks', None),
		}
		if ipd:
			item['item_keys'] = {}
			item["is_set_item"] = ipd_doc.is_set_item,
			item["set_attr"] = ipd_doc.set_item_attribute,
			item["pack_attr"] = ipd_doc.packing_attribute,
			item["major_attr_value"] = ipd_doc.major_attribute_value,

		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_doc("Item Variant", variant['item'])
				
				if ipd:
					set_combination = update_if_string_instance(variant['set_combination'])
					if set_combination:
						if set_combination.get("major_part"):
							item['item_keys']['major_part'] = set_combination.get("major_part")
						if set_combination.get("major_colour"):
							item['item_keys']['major_colour'] = set_combination.get("major_colour")		

				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'qty': variant.get('qty',0),
							'rate': variant.get('rate',0),
							'against_id_detail': variant.get("against_id_detail", None),
							'against_stock_entry': variant.get("against_stock_entry", None),
							'ste_detail': variant.get("ste_detail", None),
							'transferred_qty': variant.get("transferred_qty", None),
							'secondary_qty': variant.get("secondary_qty", 0),
							'secondary_uom': variant.get('secondary_uom', None)
						}
						if ipd:
							if not variant.get('set_combination'):
								item['values'][attr.attribute_value]['set_combination'] = {}
							else:
								item['values'][attr.attribute_value]['set_combination'] = variant.get('set_combination')
						break
		else:
			item['values']['default'] = {
				'qty': variants[0].get('qty', 0),
				'rate': variants[0].get('rate', 0),
				'against_id_detail':variants[0].get("against_id_detail",None),
				'against_stock_entry': variants[0].get("against_stock_entry", None),
				'ste_detail': variants[0].get("ste_detail", None),
				'transferred_qty': variants[0].get("transferred_qty", None),
				"secondary_qty": variants[0].get("secondary_qty", 0),
				"secondary_uom": variants[0].get('secondary_uom', None),
				# 'tax': variants[0].tax
			}
			if not variants[0].get('set_combination'):
				item['values']['default']['set_combination'] = {}
			else:
				item['values']['default']['set_combination'] = variants[0].get('set_combination')

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
						variant_name = get_variant(item_name, item_attributes)
						if not variant_name:
							variant1 = create_variant(item_name, item_attributes)
							variant1.insert()
							variant_name = variant1.name
						item1['item'] = variant_name
						item1['against_id_detail'] = item.get('against_id_detail')
						if values.get('set_combination'):
							item1['set_combination'] = values.get('set_combination')
						else:	
							item1['set_combination'] = {}
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
						item1['received_type'] = item.get('received_type')
						item1['secondary_qty'] = values.get('secondary_qty')
						item1['secondary_uom'] = values.get('secondary_uom')
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
					item1['against_id_detail'] = item['values']['default'].get('against_id_detail')
					if item['values']['default'].get('set_combination'):
						item1['set_combination'] = item['values']['default'].get('set_combination')
					else:	
						item1['set_combination'] = {}
					item1['rate'] = item['values']['default'].get('rate')
					item1['against_stock_entry'] = item['values']['default'].get("against_stock_entry", None)
					item1['ste_detail'] = item['values']['default'].get("ste_detail", None)
					item1['transferred_qty'] = item['values']['default'].get("transferred_qty", None)
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['remarks'] = item.get('remarks')
					item1['received_type'] = item.get('received_type')
					item1['secondary_qty'] = item['values']['default'].get('secondary_qty')
					item1['secondary_uom'] = item['values']['default'].get('secondary_uom')
					items.append(item1)
			row_index += 1
	return items

def get_uom_details(item_variant, uom, qty):
	"""Returns dict `{"conversion_factor": [value], "transfer_qty": qty * [value]}`
	:param args: dict with `item_code`, `uom` and `qty`"""
	detail = get_conversion_factor(item_variant, uom)
	conversion_factor = detail.get("conversion_factor")

	if not conversion_factor:
		frappe.msgprint(_("UOM conversion factor required for UOM: {0} in Item: {1}").format(uom, item_variant))
		ret = {"uom": ""}
	else:
		ret = {
			"stock_uom": detail["stock_uom"],
			"conversion_factor": flt(conversion_factor),
			"stock_qty": flt(qty) * flt(conversion_factor),
		}
	return ret

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