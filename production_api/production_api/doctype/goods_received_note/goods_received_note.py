# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe,json, sys
from frappe import _, bold
from six import string_types
from datetime import datetime
from itertools import groupby, zip_longest
from frappe.model.document import Document
from frappe.utils import money_in_words, flt, cstr, date_diff
from production_api.production_api.logger import get_module_logger
from production_api.mrp_stock.doctype.stock_entry.stock_entry import get_uom_details
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant
from production_api.production_api.doctype.work_order.work_order import get_bom_structure, get_work_order_items
from production_api.utils import get_part_list, get_panel_list, get_stich_details, update_if_string_instance, update_variant
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_calculated_bom, get_cloth_combination, get_or_create_ipd_variant

class GoodsReceivedNote(Document):
	def before_cancel(self):
		if self.against == "Work Order" and not self.is_return:
			ste_list = frappe.get_list("Stock Entry", filters={
				"against":self.doctype,
				"against_id":self.name,
				"purpose":"GRN Completion",
				"docstatus":1,
			}, pluck="name")
			for name in ste_list:
				doc = frappe.get_doc("Stock Entry", name)
				doc.cancel()

	def onload(self):
		if self.against == "Purchase Order":
			item_details = fetch_grn_purchase_item_details(self.get('items'), docstatus=self.docstatus)
			self.set_onload('item_details', item_details)
		elif self.against == "Work Order" and self.is_return:
			item_details = fetch_grn_return_item(self.get('items'))
			self.set_onload('item_details', item_details)
		else:
			items = self.get('items')
			if self.docstatus != 0:
				items = self.get('items_json')
			ipd = frappe.get_cached_value("Work Order", self.against_id, "production_detail")	
			item_details = fetch_grn_item_details(items, ipd, self.lot, docstatus=self.docstatus)
			self.set_onload('item_details', item_details)
			if self.is_manual_entry:
				items = self.get("grn_deliverables") 
				item_details = fetch_consumed_item_details(items)
				self.set_onload("consumed_items", item_details)

	def before_save(self):
		if self.against == 'Purchase Order': 
			self.calculate_amount()
		elif not self.is_return and self.against == "Work Order":
			self.dump_items()	

	def before_submit(self):
		self.letter_head = frappe.db.get_single_value("MRP Settings","dc_grn_letter_head")
		against_docstatus = frappe.get_value(self.against, self.against_id, 'docstatus')
		if against_docstatus != 1:
			frappe.throw(f'{self.against} is not submitted.', title='GRN')
		
		if self.against == 'Purchase Order':		
			for item in self.items:
				if item.quantity == 0:
					self.items.remove(item)
			self.validate_quantity()
			self.calculate_amount()
		else:
			if self.is_return:
				from production_api.mrp_stock.stock_ledger import make_sl_entries
				lot = frappe.get_cached_value(self.against, self.against_id, "lot")
				stock_settings = frappe.get_single("Stock Settings")
				default_received_type = stock_settings.default_received_type
				reduce_stock_list = []
				add_stock_list = []
				for item in self.items:
					received_type = default_received_type
					if item.received_type:
						received_type = item.received_type
					reduce_stock_list.append(self.get_return_deliverables(item, lot, {}, -1, received_type, self.supplier))
					add_stock_list.append(self.get_return_deliverables(item, lot, {}, 1, received_type, self.delivery_location))
				make_sl_entries(reduce_stock_list)
				make_sl_entries(add_stock_list)
			else:		
				if not self.is_manual_entry and not self.flags.from_cls and not self.is_rework:
					self.calculate_grn_deliverables()
				self.split_items()

		self.set('approved_by', frappe.get_user().doc.name)

	def on_submit(self):
		logger = get_module_logger("goods_received_note")
		if self.against == 'Purchase Order':
			logger.debug(f"Purchase Order {datetime.now()}")
			self.update_purchase_order()
			logger.debug(f"{self.name} PO Updated {datetime.now()}")
			self.update_stock_ledger()
			logger.debug(f"{self.name} SLE Updated {datetime.now()}")
		elif not self.is_return and self.against == "Work Order":
			from production_api.production_api.doctype.delivery_challan.delivery_challan import get_variant_stock_details
			logger.debug(f"{self.name} Work Order {datetime.now()}")
			res = get_variant_stock_details()
			self.update_work_order_receivables()
			logger.debug(f"{self.name} WO Receivables Updated {datetime.now()}")
			self.update_wo_stock_ledger(res)
			logger.debug(f"{self.name} Items Added to Delivery Location {datetime.now()}")
			if self.is_rework:
				self.reduce_rework_stock()				
			else:
				self.reduce_uncalculated_stock(res)
				logger.debug(f"{self.name} Deliverables Reduced from Supplier {datetime.now()}")
				if self.supplier_address == self.delivery_address and self.is_internal_unit:
					self.db_set("ste_transferred_percent", 100)
					self.db_set("ste_transferred", self.total_delivered_qty)
					self.db_set("transfer_complete", 1)
				self.piece_calculation()

	def piece_calculation(self):
		# calculate_pieces(self.name)
		frappe.enqueue(calculate_pieces, "short", doc_name=self.name, enqueue_after_commit=True)
	
	def reduce_rework_stock(self):
		wo_doc = frappe.get_doc(self.against, self.against_id)
		variant_received_types = {}
		for item in self.items:
			quantity = item.quantity
			for wo_item in wo_doc.deliverables:
				set1 = update_if_string_instance(item.set_combination)
				set2 = update_if_string_instance(wo_item.set_combination)
				valid_qty = wo_item.qty - wo_item.pending_quantity - wo_item.stock_update
				if item.item_variant == wo_item.item_variant and set1 == set2 and valid_qty > 0:
					variant_received_types.setdefault((item.item_variant, item.name), {})
					variant_received_types[(item.item_variant, item.name)].setdefault(wo_item.item_type, {
						"qty": 0,
						"uom": item.uom
					})
					variant_received_types[(item.item_variant, item.name)][wo_item.item_type]['qty'] += valid_qty
					wo_item.stock_update += valid_qty
					quantity -= valid_qty
				if quantity <= 0:
					break	
		wo_doc.save(ignore_permissions=True)
		sl_entries = []
		for (variant, detail_no) in variant_received_types:
			for received_type in variant_received_types[(variant, detail_no)]:
				sl_entries.append(self.get_rework_deliverables(variant, received_type, detail_no, variant_received_types, -1))

		from production_api.mrp_stock.stock_ledger import make_sl_entries
		make_sl_entries(sl_entries)		

	def get_rework_deliverables(self, variant, received_type, detail_no, variant_received_types, multiplier):
		return frappe._dict({
			"item": variant,
			"warehouse": self.supplier,
			"received_type":received_type,
			"lot": self.lot,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": detail_no,
			"qty": variant_received_types[(variant, detail_no)][received_type]['qty'] * multiplier,
			"uom": variant_received_types[(variant, detail_no)][received_type]['uom'],
			"rate": 0,
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			"valuation_rate": 0,
		})

	def split_items(self):
		items_list = []
		total_delivered = flt(0)
		for item in self.items:
			total_delivered += item.quantity
			received_types = update_if_string_instance(item.received_types)
			x = {
				"item_variant":item.item_variant,
				"tax":item.tax,
				"lot":item.lot,
				"secondary_qty":item.secondary_qty,
				"uom":item.uom,
				"secondary_uom":item.secondary_uom,
				"stock_uom":item.stock_uom,
				"conversion_factor":item.conversion_factor,
				"rate":item.rate,
				"table_index":item.table_index,
				"row_index":item.row_index,
				"ref_doctype":item.ref_doctype,
				"ref_docname":item.ref_docname,
				"comments":item.comments,
				"set_combination":item.set_combination
			}
			secondary_qty_json = update_if_string_instance(item.secondary_qty_json)

			if not received_types:
				x['quantity'] = 0
				x['amount'] = 0
				if not secondary_qty_json:
					x['secondary_qty'] = 0
					x['secondary_uom'] = None
				m = x.copy()
				items_list.append(m)
			else:
				for type1, qty1 in received_types.items():
					x['quantity'] = qty1
					x['amount'] = item.rate * qty1
					x['received_type'] = type1
					if secondary_qty_json:
						for type2, qty2 in secondary_qty_json.items():
							if type1 == type2:
								x['secondary_qty'] = qty2
								m = x.copy()
								items_list.append(m)
					else:
						m = x.copy()
						items_list.append(m)
						
		self.total_delivered_qty = total_delivered			
		self.set("items",items_list)

	def dump_items(self):
		items = []
		for item in self.items:
			items.append({
				"item_variant":item.item_variant,
				"tax":item.tax,
				"lot":item.lot,
				"quantity":item.quantity,
				"secondary_qty":item.secondary_qty,
				"stock_qty":item.stock_qty,
				"uom":item.uom,
				"secondary_uom":item.secondary_uom,
				"stock_uom":item.stock_uom,
				"conversion_factor":item.conversion_factor,
				"rate":item.rate,
				"amount":item.amount,
				"stock_uom_rate":item.stock_uom_rate,
				"table_index":item.table_index,
				"row_index":item.row_index,
				"ref_doctype":item.ref_doctype,
				"ref_docname":item.ref_docname,
				"comments":item.comments,
				"received_types":item.received_types,
				"secondary_qty_json":item.secondary_qty_json,
				"set_combination": item.set_combination,
			})	
		x = json.dumps(items)
		self.db_set("items_json",x)

	def update_work_order_receivables(self):
		if self.docstatus == 0:
			return
		wo = frappe.get_cached_doc(self.against, self.against_id)
		for item in self.items:
			for i in wo.receivables:
				if i.name == item.ref_docname:
					qty = i.pending_quantity - item.quantity 
					i.set('pending_quantity', qty)
					break
		wo.save(ignore_permissions=True)

	def calculate_grn_deliverables(self):
		total_received_qty = 0
		for item in self.items:
			total_received_qty += item.quantity	

		wo_doc = frappe.get_cached_doc(self.against, self.against_id)
		diff = wo_doc.total_quantity - total_received_qty
		percentage = (total_received_qty / wo_doc.total_quantity) * 100
		calculated_items = {}
		for item in self.grn_deliverables:
			item_keys = update_if_string_instance(item.set_combination)
			item_keys.update({"variant":item.item_variant})
			item_keys = item_keys.copy()
			item_keys = frozenset(item_keys)
			calculated_items[item_keys] = item.quantity

		for item in wo_doc.deliverables:
			check = True
			keys = update_if_string_instance(item.set_combination)
			keys.update({"variant":item.item_variant})
			keys = keys.copy()
			keys = frozenset(keys)
			x = calculated_items.get(keys)
			if x == 0:
				check = True
			elif not x:
				check = False	
			if item.is_calculated and check:
				if calculated_items[keys] != 0:
					if item.qty < calculated_items[keys]:
						item.stock_update += item.qty
					else:
						item.stock_update += calculated_items[keys]
					if item.stock_update > item.qty:
						item.stock_update = item.qty
			elif not item.is_calculated:
				total_delivered_qty = item.qty  - item.pending_quantity - item.stock_update
				new_delivered_qty = None
				if diff < 0:
					new_delivered_qty = total_delivered_qty
				else:
					new_delivered_qty = total_delivered_qty / 100
					new_delivered_qty = new_delivered_qty * percentage
				
				item.stock_update += new_delivered_qty
				if item.stock_update > item.qty:
					item.stock_update = item.qty
				self.append("grn_deliverables",{
					"item_variant":item.item_variant,
					"quantity":new_delivered_qty,
					"uom":item.uom,
					"valuation_rate":item.valuation_rate,
					"set_combination": item.set_combination,
				})
		if diff < 0:
			diff = 0
		wo_doc.total_quantity = diff
		wo_doc.save(ignore_permissions = True)	

	def update_wo_stock_ledger(self, res):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		deliverables_rate = 0
		for item in self.grn_deliverables:
			if res.get(item.item_variant) and item.quantity:
				deliverables_rate = deliverables_rate + (item.valuation_rate * item.quantity)
		avg = deliverables_rate / self.total_received_quantity
		# frappe.throw(str(avg))
		supplier = self.delivery_location
		if self.supplier_address != self.delivery_address and self.is_internal_unit:
			transit_warehouse = frappe.db.get_single_value("Stock Settings","transit_warehouse")
			supplier = transit_warehouse

		sl_entries = []
		for item in self.items:
			if item.quantity > 0 and res.get(item.item_variant):
				sl_entries.append(self.get_sl_entries(item, supplier, {}, 1, self.against, item.received_type, valuation_rate=avg))
		make_sl_entries(sl_entries)

	def reduce_uncalculated_stock(self, res):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		lot = frappe.get_cached_value(self.against, self.against_id, "lot")
		stock_settings = frappe.get_single("Stock Settings")
		received_type = stock_settings.default_received_type
		sl_entries = []
		for item in self.grn_deliverables:
			if res.get(item.item_variant):
				sl_entries.append(self.get_deliverables_data(item, lot, {}, -1, received_type))
		make_sl_entries(sl_entries)
	
	def get_deliverables_data(self, d, lot, args, multiplier, received_type):
		sl_dict = frappe._dict({
			"item": d.item_variant,
			"warehouse": self.supplier,
			"received_type":received_type,
			"lot": lot,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": d.name,
			"qty": d.get('quantity') * multiplier,
			"uom": d.uom,
			"rate": d.valuation_rate,
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			"valuation_rate":d.valuation_rate,
		})
		sl_dict.update(args)
		return sl_dict
	
	def get_return_deliverables(self, d, lot, args, multiplier, received_type, supplier):
		sl_dict = frappe._dict({
			"item": d.item_variant,
			"warehouse": supplier,
			"received_type":received_type,
			"lot": lot,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": d.name,
			"qty": d.get('quantity') * multiplier,
			"uom": d.uom,
			"rate": d.get('valuation_rate', 0),
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			"valuation_rate":d.get('valuation_rate', 0),
		})
		sl_dict.update(args)
		return sl_dict
	
	def get_sl_entries(self, d, from_location, args, multiplier, order, received_type, valuation_rate = 0.0):
		qty = None
		if order == "Work Order":
			qty = flt(d.get("quantity")) * multiplier
			rate = valuation_rate + d.get("rate")
		else:
			rate = d.rate or 0.0
			qty = flt(d.get("quantity")) * multiplier
		
		sl_dict = frappe._dict({
			"item": d.get("item_variant", None),
			"warehouse": from_location,
			"received_type":received_type,
			"lot": cstr(d.get("lot")).strip(),
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": d.get('name'),
			"qty": qty,
			"uom": d.get('uom'),
			"rate": rate,
			"valuation_rate":rate,
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
		})
		sl_dict.update(args)
		return sl_dict
	
	def on_cancel(self):
		logger = get_module_logger("goods_received_note")
		self.ignore_linked_doctypes = ("Stock Ledger Entry")
		if self.against == 'Purchase Order':
			logger.debug(f"{self.name} On Cancel Purchase Order {datetime.now()}")
			if self.purchase_invoice_name:
				frappe.throw(f'Please remove this GRN from Purchase Invoice {self.purchase_invoice_name} before cancelling. Please Contact Purchase Department.')
			settings = frappe.get_single('MRP Settings')
			cancel_before_days = settings.grn_cancellation_in_days
			if cancel_before_days == 0:
				frappe.throw('GRN cancellation is not allowed.', title='GRN')
			if cancel_before_days and not settings.allow_grn_cancellation:
				if date_diff(frappe.utils.nowdate(), self.creation) > cancel_before_days:
					frappe.throw(f'GRN cannot be cancelled after {cancel_before_days} days of creation.', title='GRN')
				status = frappe.get_value('Purchase Order', self.against_id, 'open_status')
				if status != 'Open':
					frappe.throw('Purchase order is not open.', title='GRN')
			self.update_purchase_order()
			logger.debug(f"{self.name} PO Updated {datetime.now()}")
			self.update_stock_ledger()	
			logger.debug(f"{self.name} Stock Updated {datetime.now()}")
		else:
			if self.is_return:
				from production_api.mrp_stock.stock_ledger import make_sl_entries
				lot = frappe.get_cached_value(self.against,self.against_id, "lot")
				stock_settings = frappe.get_single("Stock Settings")
				default_received_type = stock_settings.default_received_type
				reduce_stock_list = []
				add_stock_list = []
				for item in self.items:
					received_type = default_received_type
					if item.received_type:
						received_type = item.received_type
					reduce_stock_list.append(self.get_return_deliverables(item, lot, {}, -1, received_type, self.delivery_location))
					add_stock_list.append(self.get_return_deliverables(item, lot, {}, 1, received_type, self.supplier))
				make_sl_entries(reduce_stock_list)
				make_sl_entries(add_stock_list)
			else:	
				logger.debug(f"{self.name} On Cancel {self.against} {datetime.now()}")
				wo_doc = frappe.get_cached_doc(self.against, self.against_id)
				items = update_if_string_instance(self.items_json)
				for item in items:
					for receivable in wo_doc.receivables:
						if item['ref_docname'] == receivable.name and flt(item['quantity']) > flt(0):
							receivable.pending_quantity += item['quantity']
							break
				wo_doc.save(ignore_permissions=True)
				logger.debug(f"{self.name} WO Receivable Updated {datetime.now()}")
				from production_api.production_api.doctype.delivery_challan.delivery_challan import get_variant_stock_details
				res = get_variant_stock_details()
				self.reupdate_stock_ledger(res)
				logger.debug(f"{self.name} Stock Updated {datetime.now()}")
				if self.is_rework:
					self.reupdate_rework_stock()
				else:	
					self.reupdate_wo_deliverables(res)
					logger.debug(f"{self.name} Deliverables Updated {datetime.now()}")	
				
				if self.supplier_address == self.delivery_address and self.is_internal_unit:
					self.db_set("ste_transferred_percent", 0)
					self.db_set("ste_transferred", 0)
					self.db_set("transfer_complete", 0)
				self.piece_calculation()	

	def reupdate_rework_stock(self):
		wo_doc = frappe.get_doc(self.against, self.against_id)
		variant_received_types = {}
		for item in self.items:
			quantity = item.quantity
			for wo_item in wo_doc.deliverables:
				set1 = update_if_string_instance(item.set_combination)
				set2 = update_if_string_instance(wo_item.set_combination)
				valid_qty = wo_item.stock_update
				if valid_qty > quantity:
					valid_qty = quantity
				if item.item_variant == wo_item.item_variant and set1 == set2 and valid_qty > 0:
					variant_received_types.setdefault((item.item_variant, item.name), {})
					variant_received_types[(item.item_variant, item.name)].setdefault(wo_item.item_type, {
						"qty": 0,
						"uom": item.uom
					})
					variant_received_types[(item.item_variant, item.name)][wo_item.item_type]['qty'] += valid_qty
					wo_item.stock_update -= valid_qty
					quantity -= valid_qty
				if quantity <= 0:
					break	
		wo_doc.save(ignore_permissions=True)
		sl_entries = []
		for (variant, detail_no) in variant_received_types:
			for received_type in variant_received_types[(variant, detail_no)]:
				sl_entries.append(self.get_rework_deliverables(variant, received_type, detail_no, variant_received_types, 1))

		from production_api.mrp_stock.stock_ledger import make_sl_entries
		make_sl_entries(sl_entries)		

	def reupdate_stock_ledger(self, res):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		sl_entries = []
		avg = self.total_receivable_cost / self.total_received_quantity
		items = update_if_string_instance(self.items_json)
		for item in items:
			if item['quantity'] > 0 and res.get(item['item_variant']):
				received_types = update_if_string_instance(item.get("received_types"))
				for type, qty in received_types.items():
					x = item
					x['quantity'] = qty
					sl_entries.append(self.get_sl_entries(item, self.delivery_location, {}, -1, self.against,type,valuation_rate=avg))
		make_sl_entries(sl_entries)	

	def reupdate_wo_deliverables(self, res):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		total_received_qty = 0
		items = update_if_string_instance(self.items_json)
		for item in items:
			total_received_qty += item['quantity']

		wo_doc = frappe.get_cached_doc(self.against,self.against_id)
		wo_doc.total_quantity += total_received_qty
		diff = wo_doc.total_quantity - total_received_qty
		percentage = (total_received_qty / wo_doc.total_quantity) * 100
		calculated_items = {}
		for item in self.grn_deliverables:
			item_keys = update_if_string_instance(item.set_combination)
			item_keys.update({"variant":item.item_variant})
			item_keys = item_keys.copy()
			item_keys = frozenset(item_keys)
			calculated_items[item_keys] = item.quantity

		for item in wo_doc.deliverables:
			check = True
			keys = update_if_string_instance(item.set_combination)
			keys.update({"variant":item.item_variant})
			keys = keys.copy()
			keys = frozenset(keys)
			x = calculated_items.get(keys)
			if x == 0:
				check = True
			elif not x:
				check = False
			if item.is_calculated and check:
				if item.qty < calculated_items[keys]:
					item.stock_update = 0
				else:
					item.stock_update -= calculated_items[keys]
			elif check:
				total_delivered_qty = item.qty - item.stock_update
				new_delivered_qty = None
				if diff < 0:
					new_delivered_qty = total_delivered_qty
				else:
					new_delivered_qty = total_delivered_qty / 100
					new_delivered_qty = new_delivered_qty * percentage

				if item.qty < new_delivered_qty:
					item.stock_update = 0
				else:
					item.stock_update -= new_delivered_qty

				if item.stock_update < 0:
					item.stock_update = 0	

				self.append("grn_deliverables",{
					"item_variant":item.item_variant,
					"quantity":new_delivered_qty,
					"uom":item.uom,
					"set_combination": item.set_combination
				})
		lot = wo_doc.lot
		wo_doc.save(ignore_permissions = True)	
		sl_entries = []
		received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
		for item in self.grn_deliverables:
			if res.get(item.item_variant):
				sl_entries.append(self.get_deliverables_data(item, lot, {}, 1, received_type))
		make_sl_entries(sl_entries)

	def update_purchase_order(self):
		if self.docstatus == 0:
			return
		multiplier = 1
		if self.docstatus == 2:
			multiplier = -1
		po = frappe.get_cached_doc(self.against, self.against_id)
		for item in self.items:
			# find the po item with the same ref_docname
			for i in po.items:
				if i.name == item.ref_docname:
					quantity = item.quantity * multiplier
					if self.docstatus == 1:
						validate_quantity_tolerance(i.item_variant, i.qty, i.pending_qty, quantity)
					i.set('pending_qty', i.pending_qty - quantity)
					break
		po.save(ignore_permissions=True)

	def update_stock_ledger(self):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		if self.docstatus == 0:
			return
		sl_entries = []
		received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
		for item in self.items:
			self.received_type = received_type
			sl_entries.append(self.get_sl_entries(item, self.delivery_location, {}, 1, self.against, received_type))

		if self.docstatus == 2:
			sl_entries.reverse()
		make_sl_entries(sl_entries)

	def before_validate(self):
		if self.docstatus == 1:
			return
		
		if self.delivery_date > self.posting_date:
			frappe.throw("Delivery Date is Higher than Posting Date")
		if self.against == 'Purchase Order':
			if(self.get('item_details')):
				items = save_grn_purchase_item_details(self.item_details)
				self.set('items', items)
		elif not self.is_return and self.against == "Work Order":
			if self.flags.from_cls:
				wo_items = get_work_order_items(self.against_id, True)
				self.item_details = wo_items				

			lot, process, internal, ipd = frappe.get_cached_value(self.against, self.against_id, ["lot","process_name","is_internal_unit", "production_detail"])
			is_manual_entry = frappe.get_value("Process", process, "is_manual_entry_in_grn")
			if self.is_rework:
				is_manual_entry = False
			self.process_name = process
			self.is_manual_entry = is_manual_entry
			self.is_internal_unit = internal
			self.lot = lot	
			check = False
			if self.is_new():
				check = True
			else:
				check = self.get('is_edited')

			if(self.get('item_details')) and check:
				items, total_rate, total_qty = save_grn_item_details(self.item_details, self.process_name, ipd)
				self.set('items', items)
				if len(self.items) > 0:
					doc = frappe.get_cached_doc(self.against, self.against_id)
					wo_deliverables = {}
					for row in doc.deliverables:
						wo_deliverables[row.item_variant] = row.valuation_rate
					if not self.is_manual_entry and not self.flags.from_cls and not self.is_rework:
						deliverables = calculate_deliverables(self)
						items = []
						for row in deliverables:
							if wo_deliverables.get(row['item_variant']):
								items.append({
									"item_variant": row['item_variant'],
									"quantity": row['qty'],
									"uom": row['uom'],
									"valuation_rate": wo_deliverables[row['item_variant']],
									"set_combination": row['set_combination'],
								})
						self.set("grn_deliverables", items)
					self.total_receivable_cost = total_rate
			total_qty = 0
			for item in self.items:
				total_qty += item.quantity
			self.total_received_quantity = total_qty
			if self.get('consumed_item_details'):
				items = save_grn_consumed_item_details(self.consumed_item_details, ipd)
				self.set("grn_deliverables", items)

	def validate(self):
		if self.against == 'Purchase Order':
			status = frappe.get_value('Purchase Order', self.against_id, 'open_status')
			if status != 'Open':
				frappe.throw('Purchase order is closed.', title='GRN')
			
			supplier = frappe.get_value('Purchase Order', self.against_id, 'supplier')
			if supplier != self.supplier:
				frappe.throw('Supplier cannot be changed.', title='GRN')
			
			po_docstatus = frappe.get_value('Purchase Order', self.against_id, 'docstatus')
			if po_docstatus != 1:
				frappe.throw('Purchase order is not submitted.', title='GRN')
			self.validate_quantity()
			self.validate_data()

	def validate_quantity(self):
		total_quantity = 0
		for item in self.items:
			total_quantity += item.quantity
		if total_quantity == 0:
			frappe.throw('Quantity cannot be zero.', title='GRN')
	
	def validate_data(self):
		for row in self.items:
			item_details = get_uom_details(row.item_variant, row.uom, row.quantity)
			row.set("stock_uom", item_details.get("stock_uom"))
			row.set("conversion_factor", item_details.get("conversion_factor"))
			row.stock_qty = flt(
				flt(row.quantity) * flt(row.conversion_factor), self.precision("stock_qty", row)
			)
			row.stock_uom_rate = flt(
				flt(row.rate) / flt(row.conversion_factor), self.precision("stock_uom_rate", row)
			)
			row.amount = flt(flt(row.rate) * flt(row.quantity), self.precision("amount", row))

	def calculate_amount(self):
		total_amount = 0
		total_tax = 0
		grand_total = 0
		for item in self.items:
			item_total = item.rate * item.quantity
			total_amount += item_total
			tax = item_total * (float(item.tax or 0) / 100)
			total_tax += tax
			total = item_total + tax
			grand_total += total
		self.set('total', total_amount)
		self.set('total_tax', total_tax)
		self.set('grand_total', grand_total)
		self.set('in_words', money_in_words(grand_total))

def save_grn_purchase_item_details(item_details):
	item_details = update_if_string_instance(item_details)
	items = []
	row_index = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():
					if values.get('qty') or values.get('pending_qty') or values.get('received'):
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						variant_name = get_or_create_variant(item_name, item_attributes)
						validate_quantity_tolerance(variant_name, values.get('qty'), values.get('pending_qty'), values.get('received'))
						item1['item_variant'] = variant_name
						item1['lot'] = item.get('lot')

						if isinstance(values.get('received'), string_types) and values.get('received') != '':
							values['received'] = float(values.get('received'))
						else:
							values['received'] = values.get('received') or 0
						item1['quantity'] = values.get('received')
						item1['uom'] = item.get('default_uom')
						if isinstance(values.get('secondary_received'), string_types) and values.get('secondary_received') != '':
							values['secondary_received'] = float(values.get('secondary_received'))
						else:
							values['secondary_received'] = values.get('secondary_received') or 0
						item1['secondary_qty'] = values.get('secondary_received')
						item1['secondary_uom'] = item.get('secondary_uom')
						item1['rate'] = values.get('rate')
						item1['tax'] = values.get('tax')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['comments'] = item.get('comments')
						item1['ref_doctype'] = values.get('ref_doctype')
						item1['ref_docname'] = values.get('ref_docname')
						items.append(item1)
			else:
				if item['values'].get('default'):
					item1 = {}
					variant_name = get_or_create_variant(item_name, item_attributes)
					validate_quantity_tolerance(variant_name, item['values']['default'].get('qty'), item['values']['default'].get('pending_qty'), item['values']['default'].get('received'))
					item1['item_variant'] = variant_name
					item1['lot'] = item.get('lot')
					item1['quantity'] = item['values']['default'].get('received')
					item1['uom'] = item.get('default_uom')
					item1['secondary_qty'] = item['values']['default'].get('secondary_received')
					item1['secondary_uom'] = item.get('secondary_uom')
					item1['rate'] = item['values']['default'].get('rate')
					item1['tax'] = item['values']['default'].get('tax')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments')
					item1['ref_doctype'] = item['values']['default'].get('ref_doctype')
					item1['ref_docname'] = item['values']['default'].get('ref_docname')
					items.append(item1)
			row_index += 1
	return items

def save_grn_consumed_item_details(item_details, ipd):
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	item_variants = update_if_string_instance(ipd_doc.variants_json)
	item_details = update_if_string_instance(item_details)
	items = []
	row_index = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():
					item_attributes[item.get('primary_attribute')] = attr
					item1 = {}
					tup = tuple(sorted(item_attributes.items()))
					variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, item_attributes)
					item_variants = update_variant(item_variants, variant_name, item_name, str_tup)
					item1['quantity'] = values.get('qty')
					item1['item_variant'] = variant_name
					item1['uom'] = item.get('default_uom')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments') 
					items.append(item1)
			else:
				if item['values'].get('default') and item['values']['default'].get('qty'):
					item1 = {}
					tup = tuple(sorted(item_attributes.items()))
					variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, item_attributes)
					str_tup = str(tup) 
					item_variants = update_variant(item_variants, variant_name, item_name, str_tup)
					item1['quantity'] = item['values']['default'].get('qty')
					item1['item_variant'] = variant_name
					item1['uom'] = item.get('default_uom')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments') 
					items.append(item1)
			row_index += 1
	ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)		
	return items

def fetch_consumed_item_details(items):
	items = [item.as_dict() for item in items]
	item_details = []
	items = sorted(items, key = lambda i: i['row_index'])
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			"dependent_attribute": current_item_attribute_details['dependent_attribute'],
			"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
			'values': {},
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'comments': variants[0]['comments'],
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {'qty': variant.quantity}
						break
		else:
			item['values']['default'] = {'qty': variants[0].quantity}

		index = get_item_group_index(item_details, current_item_attribute_details)
		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				"dependent_attribute": current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return item_details

def save_grn_item_details(item_details, process_name, ipd):
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	item_variants = update_if_string_instance(ipd_doc.variants_json) 
	item_details = update_if_string_instance(item_details)
	allowance = frappe.db.get_value("Process",process_name,"additional_allowance")
	items = []
	row_index = 0
	table_index = 1
	total_rate = 0
	total_qty = 0
	for group in item_details:
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():	
					if values.get('ref_docname'):	
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						tup = tuple(sorted(item_attributes.items()))
						variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, item_attributes)
						str_tup = str(tup)
						item_variants = update_variant(item_variants, variant_name, item_name, str_tup)
						received = values.get('received', 0)
						total_quantity, pending_qty = frappe.get_value(values.get('ref_doctype'), values.get('ref_docname'), ["qty","pending_quantity"])
						x = total_quantity / 100
						x = x * allowance
						total_quantity = pending_qty + x
						if total_quantity < received:
							frappe.throw(f"Received more than the allowed quantity for {bold(variant_name)}")

						item1['item_variant'] = variant_name
						item1['lot'] = item.get('lot')
						item1['quantity'] = received
						item1['received_types'] = values.get('types')
						item1['secondary_qty_json'] = values.get('secondary_qty_json')
						item1['uom'] = item.get('default_uom')
						item1['secondary_qty'] = values.get('secondary_received')
						item1['secondary_uom'] = item.get('secondary_uom')
						item1['rate'] = values.get('rate')
						item1['tax'] = values.get('tax')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['comments'] = item.get('comments')
						item1['ref_doctype'] = values.get('ref_doctype')
						item1['ref_docname'] = values.get('ref_docname')
						item1['set_combination'] = values.get('set_combination', {})
						items.append(item1)
						if received:
							total_qty = total_qty + received
							total_rate = total_rate + (received * values.get('rate'))	
			else:
				if item['values'].get('default') and item['values']['default'].get('ref_docname'):
					item1 = {}
					tup = tuple(sorted(item_attributes.items()))
					variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, item_attributes)
					str_tup = str(tup)
					item_variants = update_variant(item_variants, variant_name, item_name, str_tup)
					doctype = item['values']['default'].get('ref_doctype')
					docname = item['values']['default'].get('ref_docname')
					received = item['values']['default'].get('received', 0)
					total_quantity, pending_qty = frappe.get_value(doctype, docname, ["qty","pending_quantity"])
					x = total_quantity / 100
					x = x * allowance
					total_quantity = total_quantity + x
					if total_quantity < received:
						frappe.throw(f"Received more than the allowed quantity for {bold(variant_name)}")

					item1['item_variant'] = variant_name
					item1['lot'] = item.get('lot')
					item1['quantity'] = received
					item1['received_types'] = item['values']['default'].get('types')
					item1['secondary_qty_json'] = item['values']['default'].get('secondary_qty_json')
					item1['uom'] = item.get('default_uom')
					item1['secondary_qty'] = item['values']['default'].get('secondary_received')
					item1['secondary_uom'] = item.get('secondary_uom')
					item1['rate'] = item['values']['default'].get('rate')
					item1['tax'] = item['values']['default'].get('tax')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments')
					item1['ref_doctype'] = doctype
					item1['ref_docname'] = docname
					item1['set_combination'] = item['values']['default'].get('set_combination', {})
					items.append(item1)
					if received:
						total_qty = total_qty + received
						total_rate = total_rate + (received * item['values']['default'].get('rate'))	
			row_index += 1
	ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)		
	return items, total_rate, total_qty

def validate_quantity_tolerance(item_variant, total_qty, pending_qty, received_qty):
	item = frappe.get_value("Item Variant", item_variant, "item")
	# tolerance percentage
	tolerance_percentage = frappe.get_value("Item", item, "over_delivery_receipt_allowance") or 0
	tolerance = total_qty * (tolerance_percentage / 100)
	# Check if the tolerance is exceeded
	if (received_qty - pending_qty) > tolerance:
		frappe.throw(_("Quantity tolerance exceeded for item {0}. Received Quantity must not exceed {1}").format(item, pending_qty + tolerance))
	return True

def fetch_grn_item_details(items, ipd, lot, docstatus = 0):	
	if isinstance(items, string_types):
		items = json.loads(items)
	else:	
		items = [item.as_dict() for item in items]
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	item_details = []
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			"item_keys": {},
			"is_set_item": ipd_doc.is_set_item,
			"set_attr": ipd_doc.set_item_attribute,
			"pack_attr": ipd_doc.packing_attribute,
			"major_attr_value": ipd_doc.major_attribute_value,
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			'values': {},
			'types':[],
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				set_combination = update_if_string_instance(variant.get('set_combination', {}))
				if set_combination:
					if set_combination.get("major_part"):
						item['item_keys']['major_part'] = set_combination.get("major_part")

					if set_combination.get("major_colour"):
						item['item_keys']['major_colour'] = set_combination.get("major_colour")		

				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'primary_attr': attr.attribute_value,
							'secondary_uom':variant['secondary_uom'],
							'secondary_qty': variant['secondary_qty'],
							'rate': variant['rate'],
							'tax': variant['tax'],
							'types': variant['received_types'] if variant['received_types'] else {},
							'secondary_qty_json': variant['secondary_qty_json'] if variant['secondary_qty_json'] else {},
							'set_combination': variant.get('set_combination', {})
						}
						x = item['values'][attr.attribute_value]['types']
						if x:
							x = update_if_string_instance(x)

						for t, qty in x.items():
							if t not in item['types']:
								item['types'].append(t)

						qty = frappe.get_value(variant['ref_doctype'], variant['ref_docname'], "pending_quantity")
						if docstatus == 0:
							item['values'][attr.attribute_value]['qty'] = round(qty - variant['quantity'], 3) 
						else:
							item['values'][attr.attribute_value]['qty'] = qty
						item['values'][attr.attribute_value]['received'] = round(variant['quantity'], 3)
						item['values'][attr.attribute_value]['ref_doctype'] = variant['ref_doctype']
						item['values'][attr.attribute_value]['ref_docname'] = variant['ref_docname']
						break
		else:
			item['values']['default'] = {
				'secondary_qty': variants[0]['secondary_qty'],
				'secondary_uom': variants[0]['secondary_uom'],
				'rate': variants[0]['rate'],
				'tax': variants[0]['tax'],
				'types': variants[0]['received_types'] if variants[0]['received_types'] else {},
				'secondary_qty_json': variants[0]['secondary_qty_json'] if variants[0]['secondary_qty_json'] else {},
				'set_combination': variants[0].get('set_combination', {})
			}
			x = item['values']['default']['types']
			if x:
				x = update_if_string_instance(x)

			for t, qty in x.items():
				if t not in item['types']:
					item['types'].append(t)

			qty = frappe.get_value( variants[0]['ref_doctype'], variants[0]['ref_docname'], "pending_quantity")
			if docstatus == 0:
				item['values']['default']['qty'] = round(qty - variants[0]['quantity'], 3) 
			else:
				item['values']["default"]['qty'] = qty
			item['values']['default']['received'] = round(variants[0]['quantity'], 3)
			item['values']['default']['ref_doctype'] = variants[0]['ref_doctype']
			item['values']['default']['ref_docname'] = variants[0]['ref_docname']
		
		index = -1
		if item_details:
			index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				"lot":lot,
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				'dependent_attribute': current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)	

	return item_details

def fetch_grn_purchase_item_details(items, docstatus=0):
	items = [item.as_dict() for item in items]
	if docstatus != 0:
		items = [item for item in items if item.get('quantity') > 0]
	item_details = []
	items = sorted(items, key = lambda i: i['row_index'])
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			'values': {},
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'received': variant.quantity,
							'secondary_received': variant.secondary_qty,
							'rate': variant.rate,
							'tax': variant.tax,
						}
						if docstatus == 0:
							doc = frappe.get_cached_doc("Purchase Order Item", variant.ref_docname)
							item['values'][attr.attribute_value]['qty'] = doc.qty
							item['values'][attr.attribute_value]['secondary_qty'] = doc.secondary_qty
							item['values'][attr.attribute_value]['pending_qty'] = doc.pending_qty
							item['values'][attr.attribute_value]['ref_doctype'] = variant.ref_doctype
							item['values'][attr.attribute_value]['ref_docname'] = variant.ref_docname
						break
		else:
			item['values']['default'] = {
				'received': variants[0].quantity,
				'secondary_received': variants[0].secondary_qty,
				'rate': variants[0].rate,
				'tax': variants[0].tax
			}
			if docstatus == 0:
				doc = frappe.get_cached_doc("Purchase Order Item", variants[0].ref_docname)
				item['values']['default']['qty'] = doc.qty
				item['values']['default']['secondary_qty'] = doc.secondary_qty
				item['values']['default']['pending_qty'] = doc.pending_qty
				item['values']['default']['ref_doctype'] = variants[0].ref_doctype
				item['values']['default']['ref_docname'] = variants[0].ref_docname
		index = -1
		if item_details:
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

def fetch_grn_return_item(items):
	items = [item.as_dict() for item in items]
	item_details = []
	items = sorted(items, key = lambda i: i['table_index'])
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			'values': {},
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
			"received_type": variants[0]['received_type'],
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'received': variant.quantity,
							'secondary_received': variant.secondary_qty,
							'rate': variant.rate,
							'tax': variant.tax,
						}
						item['values'][attr.attribute_value]['qty'] = variant.quantity
						item['values'][attr.attribute_value]['ref_doctype'] = variant.ref_doctype
						item['values'][attr.attribute_value]['ref_docname'] = variant.ref_docname
						break
		else:
			item['values']['default'] = {
				'received': variants[0].quantity,
				'secondary_received': variants[0].secondary_qty,
				'rate': variants[0].rate,
				'tax': variants[0].tax
			}
			item['values']['default']['qty'] = variants[0].quantity
			item['values']['default']['ref_doctype'] = variants[0].ref_doctype
			item['values']['default']['ref_docname'] = variants[0].ref_docname
		index = -1
		if item_details:
			index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				"dependent_attribute": current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return item_details


@frappe.whitelist()
def calculate_deliverables(grn_doc):
	wo_doc = frappe.get_cached_doc("Work Order", grn_doc.against_id)
	ipd_doc = frappe.get_cached_doc("Item Production Detail",wo_doc.production_detail)
	process = wo_doc.process_name
	final_value = {}
	if process == ipd_doc.packing_process:
		final_value = get_packing_process_deliverables(grn_doc, wo_doc, ipd_doc)
	elif process == ipd_doc.stiching_process:
		final_value = get_stiching_process_deliverables(grn_doc, wo_doc, ipd_doc)
	elif process == ipd_doc.cutting_process:
		final_value = get_cutting_process_deliverables(grn_doc,ipd_doc)
	else:
		final_value = get_other_deliverables(grn_doc, wo_doc)
	return final_value	

def get_other_deliverables(grn_doc, wo_doc):
	process = wo_doc.process_name
	final_value = []
	is_group = frappe.get_value("Process",process,"is_group")
	if not is_group:
		for item in grn_doc.items:
			final_value.append({
				"item_variant": item.item_variant,
				"qty": item.quantity,
				"uom":item.uom,
				"set_combination": item.set_combination,
			})
		return final_value
	else:
		return []

def get_cutting_process_deliverables(grn_doc, ipd_doc):
	final_value = {}
	cloth_combination = get_cloth_combination(ipd_doc)
	panel_qty = 0
	for i in ipd_doc.stiching_item_details:
		panel_qty += i.quantity

	cloth_detail = {}
	for cloth in ipd_doc.cloth_detail:
		cloth_detail[cloth.name1] = cloth.cloth
	item_attr_detail_dict = {}
	cloths = {}
	stich_details = {}
	if ipd_doc.is_set_item:
		stich_details = get_stich_details(ipd_doc)

	accessory_json = update_if_string_instance(ipd_doc.accessory_clothtype_json)

	for item in grn_doc.items:
		if not item.quantity > 0:
			continue
		variant_doc = frappe.get_cached_doc("Item Variant", item.item_variant)	
		item_attribute_details = None
		if item_attr_detail_dict.get(variant_doc.item):
			item_attribute_details = item_attr_detail_dict[variant_doc.item]
		else:
			item_attribute_details = get_attribute_details(variant_doc.item)
			item_attr_detail_dict[variant_doc.item] = item_attribute_details
		attributes = get_receivable_item_attribute_details(variant_doc, item_attribute_details, ipd_doc.stiching_in_stage)
		if ipd_doc.is_set_item and not attributes.get(ipd_doc.set_item_attribute):
			attributes[ipd_doc.set_item_attribute] = stich_details[attributes[ipd_doc.stiching_attribute]]
		cut_attr_key = get_key(attributes, cloth_combination["cutting_attributes"])
		dia, cloth_weight = cloth_combination["cutting_combination"].get(cut_attr_key)
		cloth_attr_key = get_key(attributes, cloth_combination["cloth_attributes"])
		cloth_type = cloth_combination["cloth_combination"].get(cloth_attr_key)
		if ipd_doc.stiching_attribute not in cloth_combination['cutting_attributes']:
			cloth_weight = cloth_weight / panel_qty
		cloth_name = cloth_detail[cloth_type]
		cloth_weight = cloth_weight * item.quantity
		t = (cloth_name,attributes[ipd_doc.packing_attribute],dia)
		if cloths.get(t):
			cloths[t] += cloth_weight
		else:
			cloths[t] = cloth_weight

		for accessory_name, accessory_cloth in accessory_json.items():
			attributes["Accessory"] = accessory_name
			acc_attr_key = get_key(attributes, cloth_combination["accessory_attributes"])
			if cloth_combination["accessory_combination"].get(acc_attr_key):
				dia, accessory_weight = cloth_combination["accessory_combination"][acc_attr_key]
				if ipd_doc.stiching_attribute not in cloth_combination["accessory_attributes"]:
					accessory_weight = accessory_weight / panel_qty
				accessory_weight = accessory_weight * item.quantity
				accessory_colour, cloth = get_accessory_colour(ipd_doc,attributes,accessory_name)
				t = (cloth_detail[cloth],accessory_colour, dia)
				if cloths.get(t):
					cloths[t] += accessory_weight
				else:
					cloths[t] = accessory_weight

	additional = False
	add_percent = 0
	if ipd_doc.additional_cloth:
		additional = True
		add_percent = ipd_doc.additional_cloth

	for cloth, weight in cloths.items():
		name, colour, dia = cloth
		attributes = {ipd_doc.packing_attribute:colour,"Dia":dia}
		item_name = name
		tup = tuple(sorted(attributes.items()))
		new_variant = get_or_create_ipd_variant(item_variants, item_name, tup, attributes)
		str_tup = str(tup) 
		item_variants = update_variant(item_variants, new_variant, item_name, str_tup)
		uom = frappe.get_cached_value("Item",name,"default_unit_of_measure")
		if additional:
			x = weight / 100
			x = x * add_percent
			weight = weight + x
		if final_value.get(new_variant):
			final_value[new_variant]['qty'] += weight
		else:
			final_value[new_variant] = {"qty":weight,"uom": uom}	

	final_list = []
	for variant, attr in final_value.items():
		final_list.append({
			"item_variant": variant,
			"quantity": attr['qty'],
			"uom": attr['uom'],
			"set_combination": {},
		})	
	ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)
	return final_list

def item_attribute_details(variant, item_attributes):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute != item_attributes['dependent_attribute']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

def get_stiching_process_deliverables(grn_doc, wo_doc, ipd_doc):
	lot_doc = frappe.get_cached_doc("Lot", wo_doc.lot)
	ipd = lot_doc.production_detail
	process = wo_doc.process_name
	final_value = []
	items = []
	for item in grn_doc.items:
		items.append({
			"item_variant":item.item_variant,
			"quantity":item.quantity,
			"row_index":item.row_index,
			"table_index":item.table_index,
			"set_combination": item.set_combination,
		})
	variant_doc = frappe.get_cached_doc("Item Variant", items[0]['item_variant'])		
	uom = lot_doc.packing_uom
	item_list, row_index, table_index = get_item_structure(items, variant_doc.item, process, uom)	
	bom = get_calculated_bom(lot_doc.production_detail, items, lot_doc.name, process_name=process,doctype="Work Order")	
	bom = get_bom_structure(bom, row_index, table_index)
	attributes = get_attributes(item_list,variant_doc.item,ipd_doc.stiching_in_stage,ipd_doc.dependent_attribute,ipd)
	attributes.update(bom)
	for item, variants in attributes.items():
		for variant_details in variants:
			variant = variant_details['item_variant']
			qty = variant_details['qty']
			uom = variant_details['uom']
			set_combination = variant_details.get('set_combination', {})
			final_value.append({
				"item_variant":variant,
				"qty": qty,
				"uom": uom,
				"set_combination": set_combination,
			})
	return final_value

def get_packing_process_deliverables(grn_doc, wo_doc, ipd_doc):
	item_variants = update_if_string_instance(ipd_doc.variants_json)
	lot_doc = frappe.get_cached_doc("Lot", wo_doc.lot)
	process = wo_doc.process_name
	final_value = []
	items = []
	if ipd_doc.auto_calculate:
		ratio = len(ipd_doc.packing_attribute_details)

	item_attr_detail_dict = {}
	pack_combo = ipd_doc.packing_combo
	part_list = []
	set_combination_colours = {}

	if ipd_doc.is_set_item:
		for detail in ipd_doc.set_item_combination_details:
			key = (detail.major_attribute_value, detail.set_item_attribute_value)
			set_combination_colours.setdefault(key, {})
			set_combination_colours[key] = detail.attribute_value
		part_list = get_part_list(ipd_doc)

	for item in grn_doc.items:
		items.append({
			"item_variant": item.item_variant,
			"quantity": item.quantity / pack_combo,
			"row_index": item.row_index,
			"table_index": item.table_index
		})
		variant_doc = frappe.get_cached_doc("Item Variant", item.item_variant)	
		item_attribute_details = None
		if item_attr_detail_dict.get(variant_doc.item):
			item_attribute_details = item_attr_detail_dict[variant_doc.item]
		else:
			item_attribute_details = get_attribute_details(variant_doc.item)
			item_attr_detail_dict[variant_doc.item] = item_attribute_details

		attributes = get_receivable_item_attribute_details(variant_doc, item_attribute_details, ipd_doc.pack_in_stage)
		if item_attribute_details['dependent_attribute']:
			attributes[item_attribute_details['dependent_attribute']] = ipd_doc.pack_in_stage

		for colour in ipd_doc.packing_attribute_details:
			attributes[ipd_doc.packing_attribute] = colour.attribute_value
			if ipd_doc.is_set_item:
				for part in part_list:
					attributes[ipd_doc.set_item_attribute] = part
					attributes[ipd_doc.packing_attribute] = set_combination_colours[(colour.attribute_value, part)]
					tup = tuple(sorted(attributes.items()))
					item_name = variant_doc.item
					new_variant = get_or_create_ipd_variant(item_variants, item_name, tup, attributes)
					str_tup = str(tup) 
					item_variants = update_variant(item_variants, new_variant, item_name, str_tup)
					x = item.quantity
					if ipd_doc.auto_calculate:
						qty = x / ratio
					else:
						qty = x / ipd_doc.packing_attribute_no
						qty = qty * colour.quantity
					set_combination = {"major_colour": colour.attribute_value, "major_part": ipd_doc.major_attribute_value}
					final_value.append({
						"item_variant":new_variant,
						"qty": qty,
						"uom": lot_doc.packing_uom, 
						"set_combination": set_combination
					})	
			else:
				tup = tuple(sorted(attributes.items()))
				item_name = variant_doc.item
				new_variant = get_or_create_ipd_variant(item_variants, item_name, tup, attributes)
				str_tup = str(tup) 
				item_variants = update_variant(item_variants, new_variant, item_name, str_tup)
				x = item.quantity
				if ipd_doc.auto_calculate:
					qty = x / ratio
				else:
					qty = x / ipd_doc.packing_attribute_no
					qty = qty * colour.quantity
				set_combination = {"major_colour": colour.attribute_value}
				final_value.append({
					"item_variant":new_variant,
					"qty": qty,
					"uom": lot_doc.packing_uom, 
					"set_combination": set_combination
				})

	bom = get_calculated_bom(lot_doc.production_detail, items, lot_doc.name, process_name=process, doctype="Work Order")	
	bom = get_bom_structure(bom, 0, 0)	
	for itemname, variants in bom.items():
		for variant_details in variants:
			variant_name = variant_details['item_variant']
			qty = variant_details['qty']
			uom = variant_details['uom']
			final_value.append({
				"item_variant":variant_name,
				"qty": qty, 
				"uom": uom, 
				"set_combination": {} 
			})	
	ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)			
	return final_value	

def get_accessory_colour(ipd_doc,variant_attrs,accessory):
	for acce in json.loads(ipd_doc.stiching_accessory_json)["items"]:
		if acce['major_attr_value'] == variant_attrs[ipd_doc.packing_attribute]:
			return acce['accessories'][accessory]["colour"],acce['accessories'][accessory]["cloth_type"] 
		
def get_item_structure(items,item_name, process, uom):
	item_list = {
		item_name: {}
	}
	row_index = 0
	table_index = 0
	for item in items:
		row_index = item['row_index']
		table_index = item['table_index']
		item_list[item_name][item['item_variant']] = {
			"qty":item['quantity'],
			"process":process,
			"uom":uom,
			"row_index":row_index,
			"table_index":table_index,
			"set_combination": item['set_combination']
		}
	return item_list, row_index, table_index

def get_attributes(items, itemname, stage, dependent_attribute, ipd):
	item_list = {
		itemname: []
	}
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	item_variants = update_if_string_instance(ipd_doc.variants_json)
	for item_name,variants in items.items():
		item_attribute_details = get_attribute_details(item_name)
		for variant, details in variants.items():
			current_variant = frappe.get_cached_doc("Item Variant", variant)
			attributes = get_receivable_item_attribute_details(current_variant, item_attribute_details, stage)

			if item_attribute_details['dependent_attribute']:
				attributes[dependent_attribute] = stage
			itemname = current_variant.item
			set_item_stitching_attrs = {}
			if ipd_doc.is_set_item:
				part = None
				for attr in current_variant.attributes:
					if attr.attribute == ipd_doc.set_item_attribute:
						part = attr.attribute_value
						break
				set_item_stitching_attrs = get_stich_details(ipd_doc)
				for id, item in enumerate(ipd_doc.stiching_item_details):
					attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value
					v = True
					panel_part = set_item_stitching_attrs[item.stiching_attribute_value]
					if panel_part != part:
						v = False							
					if v:
						tup = tuple(sorted(attributes.items()))
						new_variant = get_or_create_ipd_variant(item_variants, itemname, tup, attributes)
						str_tup = str(tup) 
						item_variants = update_variant(item_variants, new_variant, itemname, str_tup)
						item_list[itemname].append({
							"item_variant": new_variant,
							'qty': details['qty']*item.quantity,
							'uom':details['uom'],
							'set_combination': details['set_combination']
						})
			else:
				for id,item in enumerate(ipd_doc.stiching_item_details):
					attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value
					tup = tuple(sorted(attributes.items()))
					new_variant = get_or_create_ipd_variant(item_variants, itemname, tup, attributes)
					str_tup = str(tup) 
					item_variants = update_variant(item_variants, new_variant, itemname, str_tup)
					item_list[itemname].append({
						"item_variant": new_variant,
						'qty': details['qty']*item.quantity,
						'uom':details['uom'],
						'set_combination': details['set_combination']
					})
	ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)
	return item_list

def get_receivable_item_attribute_details(variant, item_attributes, stage):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute in item_attributes['dependent_attribute_details']['attr_list'][stage]['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

def get_key(item, attrs):
	key = []
	for attr in attrs:
		if item.get(attr):
			key.append(item[attr])
	return tuple(key)	

@frappe.whitelist()
def get_grn_structure(doc_name):
	doc = frappe.get_doc("Goods Received Note", doc_name)
	ipd = frappe.get_cached_value("Work Order", doc.against_id, "production_detail")
	item_details = fetch_grn_item_details(doc.items_json, ipd, doc.lot)
	return item_details

@frappe.whitelist()
def update_calculated_receivables(doc_name, receivables, received_type):
	receivables = update_if_string_instance(receivables)
	grn_doc = frappe.get_doc("Goods Received Note", doc_name)
	total_qty = 0
	total_cost = 0
	default_received = frappe.db.get_single_value("Stock Settings", "default_received_type")
	for received_item in receivables:
		for item in grn_doc.items:
			set1 = update_if_string_instance(received_item.get('set_combination', {}))
			set2 = update_if_string_instance(item.set_combination)
			if received_item['item_variant'] == item.item_variant and set1 == set2:
				received_types = update_if_string_instance(item.received_types)
				secondary_qty_json = update_if_string_instance(item.secondary_qty_json)
				rec_type = received_type	
				if received_item.get('is_accessory'):
					rec_type = default_received	
					if received_types.get(rec_type):
						received_types[rec_type] += received_item['qty']
						item.quantity += received_item['qty']
						item.received_types = received_types
					else:
						secondary_qty_json[rec_type] = 0
						item.secondary_qty_json = secondary_qty_json
						received_types[rec_type] = received_item['qty']
						item.quantity += received_item['qty']
						item.received_types = received_types
				else:	
					if received_types.get(rec_type):
						item.quantity -= received_types.get(rec_type)
						received_types[rec_type] = received_item['qty']
						item.quantity += received_item['qty']
						item.received_types = received_types
					else:
						secondary_qty_json[rec_type] = 0
						item.secondary_qty_json = secondary_qty_json
						received_types[rec_type] = received_item['qty']
						item.quantity += received_item['qty']
						item.received_types = received_types
				total_cost += (item.rate * received_item['qty'])
				total_qty += item.quantity
				break	
	grn_doc.total_received_quantity = total_qty	
	grn_doc.total_receivable_cost = total_cost
	grn_doc.save()
	if not grn_doc.is_manual_entry:
		wo_doc = frappe.get_cached_doc(grn_doc.against, grn_doc.against_id)
		wo_deliverables = {}
		for row in wo_doc.deliverables:
			wo_deliverables[row.item_variant] = row.valuation_rate

		deliverables = calculate_deliverables(grn_doc)
		items = []
		for row in deliverables:
			check = True
			x = wo_deliverables.get(row['item_variant'])
			if x == flt(0):
				check = True
			elif not x:
				check = False
			if check:	
				items.append({
					"item_variant": row['item_variant'],
					"quantity": row['qty'],
					"uom": row['uom'],
					"valuation_rate": wo_deliverables[row['item_variant']],
					"set_combination": row['set_combination'],
				})
		grn_doc.set("grn_deliverables", items)
		grn_doc.save()

@frappe.whitelist()
def get_receivables(items,doc_name, wo_name,receivable):
	from production_api.production_api.doctype.work_order.work_order import get_deliverable_receivable
	logger = get_module_logger("goods_received_note")
	logger.debug(f"{doc_name} Deliverables Calculation Started {datetime.now()}")
	items = get_deliverable_receivable(items, wo_name, receivable=receivable)
	logger.debug(f"{doc_name} Deliverables Calculation Completed {datetime.now()}")
	return items

@frappe.whitelist()
def construct_stock_entry_data(doc_name):
	import random
	doc = frappe.get_doc("Goods Received Note", doc_name)
	stock_settings = frappe.get_single("Stock Settings")
	items = []
	received_types = {}
	for item in doc.items:
		if item.quantity - item.ste_delivered_quantity > 0:
			if item.received_type not in received_types:
				index = random.randint(11,99)
				received_types[item.received_type] = index
				index = index + item.row_index
			else:
				index = received_types[item.received_type] + item.row_index
			items.append({
				"item": item.item_variant,
				"lot": item.lot,
				"qty": item.quantity - item.ste_delivered_quantity ,
				"uom": item.uom,
				"received_type": item.received_type,
				"secondary_qty":item.secondary_qty,
				"secondary_uom":item.secondary_uom,
				"against_id_detail": item.name,
				"table_index": 0,
				"row_index": index,
				"remarks": item.comments,
				"set_combination": item.set_combination
			})
	ste = frappe.new_doc("Stock Entry")
	ste.purpose = "GRN Completion"
	ste.against = "Goods Received Note"
	ste.against_id = doc_name
	ste.from_warehouse = doc.supplier
	ste.to_warehouse = doc.delivery_location
	ste.set("items", items)
	ste.flags.allow_from_grn = True
	ste.save()
	return ste.name

@frappe.whitelist()
def calculate_pieces(doc_name):
	grn_doc = frappe.get_doc("Goods Received Note",doc_name)
	doc_status = grn_doc.docstatus
	ipd = frappe.get_cached_value("Lot", grn_doc.lot,"production_detail")
	ipd_doc = frappe.get_cached_doc("Item Production Detail",ipd)
	received_types = {}
	total_received = 0
	incomplete_items = {}
	process_name = grn_doc.process_name
	prs_doc = frappe.get_cached_doc("Process", process_name)
	final_calculation = []
	if prs_doc.is_group:
		for detail in prs_doc.process_details:
			process_name = detail.process_name

	if process_name == ipd_doc.cutting_process:
		panel_list = get_panel_list(ipd_doc)
		incomplete_items, completed_items, received_types, total_received, qty_list = calculate_cutting_piece(grn_doc, received_types, panel_list)
	elif process_name == ipd_doc.stiching_process:
		final_calculation, received_types, total_received = calculate_piece_stage(grn_doc, received_types, doc_status, total_received, final_calculation)

	elif process_name == ipd_doc.packing_process:
		final_calculation, received_types, total_received = calculate_pack_stage(ipd_doc, grn_doc, received_types, doc_status, total_received, final_calculation)
	else:
		emb = update_if_string_instance(ipd_doc.get("emblishment_details_json"))
		stage = None
		for process in ipd_doc.ipd_processes:
			if process.process_name == process_name:
				stage = process.stage
				break
		
		check = True
		panel_list = None
		if emb and emb.get(process_name):
			if len(emb.get(process_name)) == 1:
				check = False
				for item in grn_doc.items:
					qty = item.quantity
					if doc_status == 2:
						qty = qty * -1
					set_combination = update_if_string_instance(item.set_combination)
					if item.received_type:
						final_calculation.append({
							"item_variant": item.item_variant,
							"quantity": qty,
							"type":item.received_type,
							"set_combination":set_combination
						})
					received_types.setdefault(item.received_type, 0)
					received_types[item.received_type] += qty
					total_received += qty
			else:
				if stage == ipd_doc.stiching_in_stage:
					panel_list = emb.get(process_name)

		if stage and check:
			if stage == ipd_doc.pack_in_stage:
				final_calculation, received_types, total_received = calculate_piece_stage(grn_doc, received_types, doc_status, total_received, final_calculation)

			elif stage == ipd_doc.pack_out_stage:
				final_calculation, received_types, total_received = calculate_pack_stage(ipd_doc, grn_doc, received_types, doc_status, total_received, final_calculation)

			elif stage == ipd_doc.stiching_in_stage:
				if not panel_list:	
					panel_list = get_panel_list(ipd_doc)
					incomplete_items, completed_items, received_types, total_received, qty_list = calculate_cutting_piece(grn_doc, received_types, panel_list)
				elif panel_list:
					incomplete_items, completed_items, received_types, total_received, qty_list = calculate_cutting_piece(grn_doc, received_types, panel_list)
				else:
					return

	wo_doc = frappe.get_cached_doc("Work Order", grn_doc.against_id)
	if not wo_doc.first_grn_date:
		wo_doc.first_grn_date = grn_doc.posting_date
		wo_doc.last_grn_date = grn_doc.posting_date
	else:
		wo_doc.last_grn_date = grn_doc.posting_date

	wo_doc.total_no_of_pieces_received += total_received
	received_json = update_if_string_instance(wo_doc.received_types_json)	
	for type, qty in received_types.items():
		if received_json.get(type):
			received_json[type] += qty
		else:
			received_json[type] = qty

	wo_doc.received_types_json = received_json
	if incomplete_items:
		wo_doc.incompleted_items_json = incomplete_items
		wo_doc.completed_items_json = completed_items			
		lot_doc = frappe.get_cached_doc("Lot",wo_doc.lot)
		for qty_data in qty_list:
			for item in wo_doc.work_order_calculated_items:
				set_combination = update_if_string_instance(item.set_combination)
				if item.item_variant == qty_data['item_variant'] and set_combination == qty_data['set_combination']:
					qty = qty_data['quantity']
					if doc_status == 2:
						qty = qty * -1
					item.received_qty += qty
					wo_types = update_if_string_instance(item.received_type_json)
					if wo_types.get(type):
						wo_types[qty_data['type']] += qty
					else:
						wo_types[qty_data['type']] = qty		
					item.received_type_json = wo_types
					break 
			for item in lot_doc.lot_order_details:
				set_combination = update_if_string_instance(item.set_combination)
				if item.item_variant == qty_data['item_variant'] and set_combination == qty_data['set_combination']:
					qty = qty_data['quantity']
					if doc_status == 2:
						qty = qty * -1
					current_qty = getattr(item, "cut_qty", 0)
					setattr(item, "cut_qty", current_qty + qty)
		lot_doc.save()	
	else:
		lot_doc = None
		if process_name in [ipd_doc.cutting_process, ipd_doc.stiching_process, ipd_doc.packing_process]:
			lot_doc = frappe.get_cached_doc("Lot",wo_doc.lot)
			field = "cut_qty" if process_name == ipd_doc.cutting_process else "stich_qty" if process_name == ipd_doc.stiching_process else "pack_qty"

		for data in final_calculation:
			for item in wo_doc.work_order_calculated_items:
				set_combination = update_if_string_instance(item.set_combination)
				if item.item_variant == data['item_variant'] and set_combination == data['set_combination']:
					item.received_qty += data['quantity']
					wo_types = update_if_string_instance(item.received_type_json)
					
					if wo_types.get(data['type']):
						wo_types[data['type']] += data['quantity']
					else:
						wo_types[data['type']] = data['quantity']

					item.received_type_json = wo_types
			if lot_doc:
				for item in lot_doc.lot_order_details:
					set_combination = update_if_string_instance(item.set_combination)
					if item.item_variant == data['item_variant'] and set_combination == data['set_combination']:
						qty = data['quantity']
						current_qty = getattr(item, field, 0)
						setattr(item, field, current_qty + qty)	
		if lot_doc:
			lot_doc.save()
	wo_doc.save(ignore_permissions=True)

def calculate_piece_stage(grn_doc, received_types, doc_status, total_received, final_calculation):
	for item in grn_doc.items:
		# final_calculation.setdefault(item.item_variant, {"types": {}, "qty": 0 })
		qty = item.quantity
		if doc_status == 2:
			qty = qty * -1
		set_combination = update_if_string_instance(item.set_combination)
		if item.received_type:
			final_calculation.append({
				"item_variant": item.item_variant,
				"quantity": qty,
				"type":item.received_type,
				"set_combination":set_combination
			})
		received_types.setdefault(item.received_type, 0)
		received_types[item.received_type] += qty
		total_received += qty
	return final_calculation, received_types, total_received

def calculate_pack_stage(ipd_doc, grn_doc, received_types, doc_status, total_received, final_calculation):
	item_variants = update_if_string_instance(ipd_doc.variants_json)
	attrs = []
	if ipd_doc.is_set_item:
		for row in ipd_doc.set_item_combination_details:
			attrs.append({
				ipd_doc.packing_attribute: row.attribute_value,
				ipd_doc.set_item_attribute: row.set_item_attribute_value,
				"major_attr_value": row.major_attribute_value,
			})
	else:
		for row in ipd_doc.packing_attribute_details:
			attrs.append({ipd_doc.packing_attribute: row.attribute_value})

	for item in grn_doc.items:
		for attr in attrs:
			qty = item.quantity
			if doc_status == 2:
				qty = qty * -1
			variant_doc = frappe.get_cached_doc("Item Variant", item.item_variant)
			variant_attrs = get_variant_attributes(variant_doc)
			major_colour = attr[ipd_doc.packing_attribute]
			if ipd_doc.is_set_item:
				major_colour = attr["major_attr_value"]
				del attr['major_attr_value']
			variant_attrs.update(attr)
			item_name = variant_doc.item
			variant_attrs[ipd_doc.dependent_attribute] = ipd_doc.pack_in_stage
			tup = tuple(sorted(variant_attrs.items()))
			new_variant = get_or_create_ipd_variant(item_variants, item_name, tup, variant_attrs)
			set_combination = {
				"major_colour": major_colour
			}
			if ipd_doc.is_set_item:
				set_combination["major_part"] = ipd_doc.major_attribute_value

			final_calculation.append({
				"item_variant": new_variant,
				"quantity": qty,
				"type":item.received_type,
				"set_combination":set_combination
			})

			received_types.setdefault(item.received_type, 0)
			received_types[item.received_type] += qty
			total_received += qty

	return final_calculation, received_types, total_received		

def calculate_cutting_piece(grn_doc, received_types, panel_list):
	panel_list = update_if_string_instance(panel_list)		
	production_detail, incomplete_items_json, completed_items_json = frappe.get_cached_value("Work Order", grn_doc.against_id,['production_detail',"incompleted_items_json","completed_items_json"])
	ipd_doc = frappe.get_cached_doc("Item Production Detail",production_detail)
	incomplete_items = json.loads(incomplete_items_json)
	completed_items = json.loads(completed_items_json)
	item_variants = update_if_string_instance(ipd_doc.variants_json)
	panel_qty = {}
	set_comb = {}
	for row in ipd_doc.stiching_item_details:
		if ipd_doc.is_set_item:
			set_comb[row.stiching_attribute_value] = row.set_item_attribute_value
		panel_qty[row.stiching_attribute_value] = row.quantity

	types = []
	for item in grn_doc.items:
		variant = frappe.get_cached_doc("Item Variant", item.item_variant)
		attrs = get_variant_attributes(variant)
		if not attrs.get(ipd_doc.stiching_attribute):
			continue
		set_combination = update_if_string_instance(item.set_combination)
		for i in incomplete_items['items']:
			con1 = True
			if ipd_doc.is_set_item:
				con1 = i['attributes'][ipd_doc.set_item_attribute] == set_comb[attrs[ipd_doc.stiching_attribute]]
			# con2 = i['attributes'][ipd_doc.packing_attribute] == attrs[ipd_doc.packing_attribute]
			item_keys = update_if_string_instance(i['item_keys'])
			set_combination = update_if_string_instance(item.set_combination)
			con2 = item_keys == set_combination
			if con1 and con2 and item.quantity > 0:
				if item.received_type and item.received_type not in types:
					types.append(item.received_type)
				received_types.setdefault(item.received_type, 0)
				primary_attr = attrs[ipd_doc.primary_item_attribute]
				x = i['values'][primary_attr][attrs[ipd_doc.stiching_attribute]]
				y = i.copy()
				if not x:
					i['values'][attrs[ipd_doc.primary_item_attribute]][attrs[ipd_doc.stiching_attribute]] = {item.received_type:item.quantity}
				else:
					m = x.copy()
					if m.get(item.received_type):
						y['values'][attrs[ipd_doc.primary_item_attribute]][attrs[ipd_doc.stiching_attribute]][item.received_type] += item.quantity	
					else:
						y['values'][attrs[ipd_doc.primary_item_attribute]][attrs[ipd_doc.stiching_attribute]][item.received_type] = item.quantity
				i = y

	total_qty = 0
	for ty in types:
		for item1, item2 in zip_longest(completed_items['items'], incomplete_items['items']):
			for size in item2['values']:
				min = sys.maxsize
				for panel in item2['values'][size]:
					if panel in panel_list:
						if item2['values'][size][panel]:
							if item2['values'][size][panel].get(ty):
								if item2['values'][size][panel][ty] < min:
									min = item2['values'][size][panel][ty]
						else:
							min = 0
				if min > 0 and min != sys.maxsize:
					if item1['values'][size]:
						if item1['values'][size].get(ty):
							item1['values'][size][ty] += min									
						else:
							item1['values'][size][ty] = min
					else:
						item1['values'][size] = {}
						item1['values'][size] = {ty :min}	
					received_types[ty] += min
					total_qty += min

					for panel in item2['values'][size]:
						if panel in panel_list:
							if item2['values'][size][panel] and item2['values'][size][panel].get(ty):
								item2['values'][size][panel][ty] -= (min * panel_qty[panel])

	qty_list = []
	for ty in types:
		for item in completed_items['items']: 
			attrs = item['attributes']
			for val in item['values']:
				attrs[ipd_doc.primary_item_attribute] = val
				if item['values'][val]:
					if item['values'][val].get(ty):
						tup = tuple(sorted(attrs.items()))
						item_name = item['name']
						variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, attrs)
						str_tup = str(tup) 
						item_variants = update_variant(item_variants, variant_name, item_name, str_tup)
						qty = item['values'][val][ty]
						set_combination = update_if_string_instance(item['item_keys'])
						qty_list.append({
							"item_variant": variant_name,
							"quantity": qty,
							"type":ty,
							"set_combination":set_combination
						})
						item['values'][val][ty] -= qty
	ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)				
	return incomplete_items, completed_items, received_types, total_qty, qty_list

def get_variant_attributes(variant):
	attribute_details = {}
	for attr in variant.attributes:
		attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details
