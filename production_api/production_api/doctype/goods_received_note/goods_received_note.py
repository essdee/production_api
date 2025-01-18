# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe,json
from frappe import _, bold
from six import string_types
from itertools import groupby
from frappe.model.document import Document
from frappe.utils import money_in_words, flt, cstr, date_diff, nowtime
from production_api.mrp_stock.doctype.stock_entry.stock_entry import get_uom_details
from production_api.production_api.doctype.work_order.work_order import get_bom_structure
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant
from production_api.production_api.doctype.delivery_challan.delivery_challan import get_variant_stock_details
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_calculated_bom, get_cloth_combination

class GoodsReceivedNote(Document):
	def onload(self):
		if self.against == "Purchase Order":
			item_details = fetch_grn_purchase_item_details(self.get('items'), docstatus=self.docstatus)
			self.set_onload('item_details', item_details)
		else:
			item_details = fetch_grn_item_details(self.get('items'), self.lot)
			self.set_onload('item_details', item_details)

	def before_save(self):
		if self.against == 'Purchase Order': 
			self.calculate_amount()

	def before_submit(self):
		against_docstatus = frappe.get_value(self.against, self.against_id, 'docstatus')
		if against_docstatus != 1:
			frappe.throw(f'{self.against} is not submitted.', title='GRN')
		
		if self.against == 'Purchase Order':		
			for item in self.items:
				if item.quantity == 0:
					self.items.remove(item)
			self.validate_quantity()
			self.calculate_amount()
		self.set('approved_by', frappe.get_user().doc.name)

	def on_submit(self):
		if self.against == 'Purchase Order':
			self.update_purchase_order()
			self.update_stock_ledger()
		else:
			res = get_variant_stock_details()
			self.update_work_order_receivables()
			self.calculate_grn_deliverables()
			self.update_wo_stock_ledger(res)
			self.reduce_uncalculated_stock(res)
	
	def update_work_order_receivables(self):
		if self.docstatus == 0:
			return
		wo = frappe.get_cached_doc(self.against, self.against_id)
		for item in self.items:
			for i in wo.receivables:
				if i.name == item.ref_docname:
					i.set('pending_quantity', item.quantity)
					break
		wo.save(ignore_permissions=True)

	def calculate_grn_deliverables(self):
		total_received_qty = 0
		for item in self.items:
			total_received_qty += item.received_quantity

		wo_doc = frappe.get_cached_doc(self.against, self.against_id)
		diff = wo_doc.total_quantity - total_received_qty
		percentage = (total_received_qty / wo_doc.total_quantity) * 100
		calculated_items = {}
		for item in self.grn_deliverables:
			calculated_items[item.item_variant] = item.quantity

		for item in wo_doc.deliverables:
			check = True
			x = calculated_items.get(item.item_variant)
			if x == 0:
				check = True
			elif not x:
				check = False	
			if item.is_calculated and check:
				if calculated_items[item.item_variant] != 0:
					if item.qty < calculated_items[item.item_variant]:
						item.stock_update += item.qty
					else:
						item.stock_update += calculated_items[item.item_variant]
					if item.stock_update > item.qty:
						item.stock_update = item.qty
			else:
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
				})
		if diff < 0:
			diff = 0

		wo_doc.total_quantity = diff
		wo_doc.save(ignore_permissions = True)	

	def update_wo_stock_ledger(self, res):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		total_rate = 0
		for item in self.grn_deliverables:
			if res.get(item.item_variant):
				total_rate = total_rate + (item.valuation_rate * item.quantity)

		total_rate = total_rate + self.total_receivable_cost
		avg = total_rate / self.total_received_quantity
		self.total_receivable_cost = total_rate
		sl_entries = []
		for item in self.items:
			if item.received_types and item.received_quantity > 0 and res.get(item.item_variant):
				sl_entries.append(self.get_sl_entries(item, {}, 1, self.against, valuation_rate=avg))
		make_sl_entries(sl_entries)

	def reduce_uncalculated_stock(self, res):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		lot = frappe.get_value(self.against,self.against_id,"lot")
		sl_entries = []
		for item in self.grn_deliverables:
			if res.get(item.item_variant):
				sl_entries.append(self.get_deliverables_data(item, lot, {}, -1))
		make_sl_entries(sl_entries)
	
	def get_deliverables_data(self, d, lot, args, multiplier):
		sl_dict = frappe._dict({
			"item": d.item_variant,
			"warehouse": self.supplier,
			"lot": lot,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": d.name,
			"qty": d.quantity * multiplier,
			"uom": d.uom,
			"rate": 0.0,
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"posting_date": self.delivery_date,
			"posting_time": nowtime(),
			"valuation_rate":d.valuation_rate,
		})
		sl_dict.update(args)
		return sl_dict
	
	def get_sl_entries(self, d, args, multiplier, order, valuation_rate = 0.0):
		qty = None
		if order == "Work Order":
			qty = flt(d.get("received_quantity")) * multiplier
			rate = valuation_rate
		else:
			rate = d.rate or 0.0
			qty = flt(d.get("quantity")) * multiplier
		
		sl_dict = frappe._dict({
			"item": d.get("item_variant", None),
			"warehouse": self.delivery_location,
			"lot": cstr(d.get("lot")).strip(),
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": d.name,
			"qty": qty,
			"uom": d.uom,
			"rate": rate,
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"posting_date": self.delivery_date,
			"posting_time": nowtime(),
		})
		sl_dict.update(args)
		return sl_dict
	
	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Ledger Entry")
		if self.against == 'Purchase Order':
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
			self.update_stock_ledger()	
		else:
			wo_doc = frappe.get_cached_doc(self.against, self.against_id)
			for item in self.items:
				for receivable in wo_doc.receivables:
					if item.ref_docname == receivable.name and flt(item.received_quantity) > flt(0):
						receivable.pending_quantity += item.received_quantity
						break
			wo_doc.save(ignore_permissions=True)
			res = get_variant_stock_details()
			self.reupdate_stock_ledger(res)
			self.reupdate_wo_deliverables(res)

	def reupdate_stock_ledger(self, res):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		sl_entries = []
		avg = self.total_receivable_cost / self.total_received_quantity
		for item in self.items:
			if item.received_quantity > 0 and res.get(item.item_variant):
				sl_entries.append(self.get_sl_entries(item, {}, -1, self.against, valuation_rate=avg))
		make_sl_entries(sl_entries)	

	def reupdate_wo_deliverables(self, res):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		total_received_qty = 0
		for item in self.items:
			total_received_qty += item.received_quantity

		wo_doc = frappe.get_cached_doc(self.against,self.against_id)
		wo_doc.total_quantity += total_received_qty
		diff = wo_doc.total_quantity - total_received_qty
		percentage = (total_received_qty / wo_doc.total_quantity) * 100
		calculated_items = {}
		for item in self.grn_deliverables:
			calculated_items[item.item_variant] = item.quantity

		for item in wo_doc.deliverables:
			check = True
			x = calculated_items.get(item.item_variant)
			if x == 0:
				check = False	
			if item.is_calculated and calculated_items.get(item.item_variant):
				if item.qty < calculated_items[item.item_variant]:
					item.stock_update = 0
				else:
					item.stock_update -= calculated_items[item.item_variant]
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

				self.append("grn_deliverables",{
					"item_variant":item.item_variant,
					"quantity":new_delivered_qty,
					"uom":item.uom
				})
		lot = wo_doc.lot
		wo_doc.save(ignore_permissions = True)	
		sl_entries = []
		for item in self.grn_deliverables:
			if res.get(item.item_variant):
				sl_entries.append(self.get_deliverables_data(item, lot, {}, 1))
		make_sl_entries(sl_entries)

	def update_purchase_order(self):
		if self.docstatus == 0:
			return
		multiplier = 1
		if self.docstatus == 2:
			multiplier = -1
		po = frappe.get_doc(self.against, self.against_id)
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
		for item in self.items:
			sl_entries.append(self.get_sl_entries(item, {}, 1, self.against))

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
		else:
			lot, process = frappe.get_value(self.against, self.against_id, ["lot","process_name"])
			self.process_name = process
			self.lot = lot	
			check = False
			if self.is_new():
				check = True
			else:
				check = self.get('is_edited')

			if(self.get('item_details')) and check:
				items, total_rate, total_qty = save_grn_item_details(self.item_details, self.process_name)
				self.set('items', items)
				
				if len(self.items) > 0:
					doc = frappe.get_doc(self.against, self.against_id)
					wo_deliverables = {}
					for row in doc.deliverables:
						wo_deliverables[row.item_variant] = row.valuation_rate

					deliverables = calculate_deliverables(self)
					items = []
					for variant, attr in deliverables.items():
						if wo_deliverables.get(variant):
							items.append({
								"item_variant": variant,
								"quantity": attr['qty'],
								"uom": attr['uom'],
								"valuation_rate": wo_deliverables[variant]
							})
					self.set("grn_deliverables", items)
					self.total_received_quantity = total_qty
					self.total_receivable_cost = total_rate

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

def save_grn_item_details(item_details, process_name):
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
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
						variant_name = get_or_create_variant(item_name, item_attributes)
						total_qty = values.get('qty') + values.get('received_quantity')
						received = values.get('received_quantity')
						x = total_qty / 100
						x = x * allowance
						total_qty = total_qty + x
						if total_qty < received:
							frappe.throw(f"Received more than the allowed quantity for {bold(variant_name)}")

						item1['item_variant'] = variant_name
						item1['lot'] = item.get('lot')
						item1['quantity'] = values.get('qty')
						item1['received_quantity'] = values.get('received_quantity')
						item1['received_types'] = values.get('types')
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
						items.append(item1)
						if values.get('received_quantity'):
							total_qty = total_qty + values.get('received_quantity')
							total_rate = total_rate + (values.get('received_quantity') * values.get('rate'))	
			else:
				if item['values'].get('default') and item['values']['default'].get('ref_docname'):
					item1 = {}
					variant_name = get_or_create_variant(item_name, item_attributes)
					item1['item_variant'] = variant_name
					item1['lot'] = item.get('lot')
					item1['quantity'] = item['values']['default'].get('qty')
					item1['received_quantity'] = item['values']['default'].get('received_quantity')
					item1['received_types'] = item['values']['default'].get('types')
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
					if item['values']['default'].get('received_quantity'):
						total_rate = total_rate + (item['values']['default'].get('received_quantity') * item['values']['default'].get('rate'))	
						total_qty = total_qty + item['values']['default'].get('received_quantity')
			row_index += 1	
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

def fetch_grn_item_details(items, lot):
	items = [item.as_dict() for item in items]
	item_details = []
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
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'secondary_received': variant.secondary_qty,
							'rate': variant.rate,
							'tax': variant.tax,
							'types': variant.received_types if variant.received_types else {}
						}
						x = item['values'][attr.attribute_value]['types']
						if x:
							if isinstance(x, string_types):
								x = json.loads(x)

						for type, qty in x.items():
							if type not in item['types']:
								item['types'].append(type)

						item['values'][attr.attribute_value]['qty'] = variant.quantity
						item['values'][attr.attribute_value]['received_quantity'] = variant.received_quantity
						item['values'][attr.attribute_value]['ref_doctype'] = variant.ref_doctype
						item['values'][attr.attribute_value]['ref_docname'] = variant.ref_docname
						break
		else:
			item['values']['default'] = {
				'secondary_received': variants[0].secondary_qty,
				'rate': variants[0].rate,
				'tax': variants[0].tax,
				'types': variants[0].received_types if variants[0].received_types else {}
			}
			x = item['values']['default']['types']
			if x:
				if isinstance(x, string_types):
					x = json.loads(x)

			for type, qty in x.items():
				if type not in item['types']:
					item['types'].append(type)

			item['values']['default']['qty'] = variants[0].quantity
			item['values']['default']['received_quantity'] = variants[0].received_quantity
			item['values']['default']['ref_doctype'] = variants[0].ref_doctype
			item['values']['default']['ref_docname'] = variants[0].ref_docname
		
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
				current_variant = frappe.get_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'received': variant.quantity,
							'secondary_received': variant.secondary_qty,
							'rate': variant.rate,
							'tax': variant.tax,
						}
						if docstatus == 0:
							doc = frappe.get_doc("Purchase Order Item", variant.ref_docname)
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
				doc = frappe.get_doc("Purchase Order Item", variants[0].ref_docname)
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

from production_api.production_api.doctype.purchase_order.purchase_order import get_address_display
@frappe.whitelist()
def get_grn_rework_items(doc_name, supplier,supplier_address, delivery_address, rework_type, supplier_type):
	doc = frappe.get_doc("Goods Received Note",doc_name)
	wo_doc = frappe.get_doc("Work Order",doc.against_id)
	items = []
	for item in doc.items:
		x = item.received_types
		if isinstance(x, string_types):
			x = json.loads(x)
		for received_type, qty in x.items():
			type = frappe.get_value("GRN Item Type",received_type,"type")
			if type == "Mistake":
				items.append({
					"item_variant":item.item_variant,
					"lot":item.lot,
					"qty":qty,
					"uom":item.uom,
					"pending_quantity":qty,
					"table_index":item.table_index,
					"row_index":item.row_index,
					"cost":0,
					"total_cost":0,	
				})
	item_dict = {}
	for item in items:
		if item_dict.get(item['item_variant']):
			item_dict[item['item_variant']]['qty'] += item['qty']
			item_dict[item['item_variant']]['pending_quantity'] += item['qty']
		else:
			item_dict[item['item_variant']] = {
				"lot":item['lot'],
				"qty":item['qty'],
				"uom":item['uom'],
				"pending_quantity":item['qty'],
				"table_index":item['table_index'],
				"row_index":item['row_index'],
				"cost":0,
				"total_cost":0,		
			}	
	if item_dict:
		doc.rework_created = 1
		doc.save()
		deliverables = []
		for item_name, value in item_dict.items():
			deliverables.append({
				"item_variant":item_name,
				"lot":value['lot'],
				"qty":value['qty'],
				"uom":value['uom'],
				"pending_quantity":value['pending_quantity'],
				"table_index":value['table_index'],
				"row_index":value['row_index'],
				"cost":0,
				"total_cost":0,
			})
		x = frappe.new_doc("Work Order")	
		x.is_rework = True
		x.parent_wo = doc.against_id
		x.production_detail = wo_doc.production_detail
		x.naming_series = "WO-"
		x.supplier = supplier
		x.process_name = wo_doc.process_name
		x.planned_start_date = wo_doc.planned_start_date
		x.planned_end_date = wo_doc.planned_end_date
		x.expected_delivery_date = wo_doc.expected_delivery_date
		x.item = wo_doc.item
		x.lot = wo_doc.lot
		x.supplier_address = supplier_address
		x.supplier_address_details = get_address_display(supplier_address)
		x.delivery_address = delivery_address
		x.delivery_address_details = get_address_display(delivery_address)
		x.open_status = "Open"
		x.rework_type = rework_type
		x.supplier_type = supplier_type
		x.set("deliverables",deliverables)
		x.set("receivables",deliverables)
		x.save()	
		return x.name
	else:
		return None		

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
	final_value = {}
	is_group = frappe.get_value("Process",process,"is_group")
	if not is_group:
		for item in grn_doc.items:
			if final_value.get(item.item_variant):
				final_value[item.item_variant]['qty'] += item.received_quantity
			else:
				final_value[item.item_variant] = {"qty":item.received_quantity,"uom": item.uom}	
		return final_value		
	else:
		return {}	

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
	for item in grn_doc.items:
		variant_doc = frappe.get_cached_doc("Item Variant", item.item_variant)	
		item_attribute_details = None
		if item_attr_detail_dict.get(variant_doc.item):
			item_attribute_details = item_attr_detail_dict[variant_doc.item]
		else:
			item_attribute_details = get_attribute_details(variant_doc.item)
			item_attr_detail_dict[variant_doc.item] = item_attribute_details

		attributes = get_receivable_item_attribute_details(variant_doc, item_attribute_details, ipd_doc.stiching_in_stage)
		cut_attr_key = get_key(attributes, cloth_combination["cutting_attributes"])
		dia, cloth_weight = cloth_combination["cutting_combination"].get(cut_attr_key)
		cloth_attr_key = get_key(attributes, cloth_combination["cloth_attributes"])
		cloth_type = cloth_combination["cloth_combination"].get(cloth_attr_key)
		if ipd_doc.stiching_attribute not in cloth_combination['cutting_attributes']:
			cloth_weight = cloth_weight / panel_qty
		cloth_name = cloth_detail[cloth_type]
		cloth_weight = cloth_weight * item.received_quantity
		t = (cloth_name,attributes[ipd_doc.packing_attribute],dia)
		if cloths.get(t):
			cloths[t] += cloth_weight
		else:
			cloths[t] = cloth_weight
		accessory_json = ipd_doc.accessory_clothtype_json
		if isinstance(accessory_json, string_types):
			accessory_json = json.loads(accessory_json)

		for accessory_name, accessory_cloth in accessory_json.items():
			attributes["Accessory"] = accessory_name
			acc_attr_key = get_key(attributes, cloth_combination["accessory_attributes"])
			if cloth_combination["accessory_combination"].get(acc_attr_key):
				dia, accessory_weight = cloth_combination["accessory_combination"][acc_attr_key]
				if ipd_doc.stiching_attribute not in cloth_combination["accessory_attributes"]:
					accessory_weight = accessory_weight / panel_qty
				accessory_weight = accessory_weight * item.received_quantity
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
	for cloth,weight in cloths.items():
		name, colour, dia = cloth
		new_variant = get_or_create_variant(name, {ipd_doc.packing_attribute:colour,"Dia":dia})
		uom = frappe.get_value("Item",name,"default_unit_of_measure")
		if additional:
			x = weight / 100
			x = x * add_percent
			weight = weight + x
		if final_value.get(new_variant):
			final_value[new_variant]['qty'] += weight
		else:
			final_value[new_variant] = {"qty":weight,"uom": uom}	
	return final_value

def get_stiching_process_deliverables(grn_doc, wo_doc, ipd_doc):
	lot_doc = frappe.get_cached_doc("Lot", wo_doc.lot)
	ipd = lot_doc.production_detail
	process = wo_doc.process_name
	final_value = {}
	items = []
	for item in grn_doc.items:
		items.append({
			"item_variant":item.item_variant,
			"quantity":item.received_quantity,
			"row_index":item.row_index,
			"table_index":item.table_index
		})
	variant_doc = frappe.get_cached_doc("Item Variant", items[0]['item_variant'])		
	uom = lot_doc.packing_uom
	item_list, row_index, table_index = get_item_structure(items, variant_doc.item, process, uom)	
	bom = get_calculated_bom(lot_doc.production_detail, items, lot_doc.name, process_name=process,doctype="Work Order")	
	bom = get_bom_structure(bom, row_index, table_index)
	attributes = get_attributes(item_list,variant_doc.item,ipd_doc.stiching_in_stage,ipd_doc.dependent_attribute,ipd)
	attributes.update(bom)
	for item, variants in attributes.items():
		for variant, variant_attr in variants.items():
			if final_value.get(variant):
				final_value[variant] += variant_attr['qty']
			else:		 
				final_value[variant] = {
					"qty":variant_attr['qty'],
					"uom":variant_attr['uom']
				}
	return final_value

def get_packing_process_deliverables(grn_doc, wo_doc, ipd_doc):
	lot_doc = frappe.get_cached_doc("Lot", wo_doc.lot)
	process = wo_doc.process_name
	final_value = {}
	items = []
	if ipd_doc.auto_calculate:
		ratio = len(ipd_doc.packing_attribute_details)

	item_attr_detail_dict = {}
	pack_combo = ipd_doc.packing_combo
	for item in grn_doc.items:
		items.append({
			"item_variant": item.item_variant,
			"quantity": item.received_quantity * pack_combo,
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
			new_variant = get_or_create_variant(variant_doc.item, attributes)
			x = item.received_quantity * pack_combo
			if ipd_doc.auto_calculate:
				qty = x / ratio
			else:
				qty = x / ipd_doc.packing_attribute_no
				qty = qty * colour.quantity

			if final_value.get(new_variant):
				final_value[new_variant]['qty'] += qty
			else:
				final_value[new_variant] = {"qty": qty,"uom": lot_doc.packing_uom}	

	bom = get_calculated_bom(lot_doc.production_detail, items, lot_doc.name, process_name=process, doctype="Work Order")	
	bom = get_bom_structure(bom, 0, 0)	
	for itemname, variants in bom.items():
		for variant_name, attrs in variants.items():
			if final_value.get(variant_name):
				final_value[variant_name] += attrs['qty']
			else:
				final_value[variant_name] = {"qty": attrs['qty'], "uom": attrs['uom']}	
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
			"table_index":table_index
		}
	return item_list, row_index, table_index

def get_attributes(items, itemname, stage, dependent_attribute, ipd):
	item_list = {
		itemname: {}
	}
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)

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

				for i in ipd_doc.stiching_item_details:
					set_item_stitching_attrs[i.stiching_attribute_value] = i.set_item_attribute_value

				for id, item in enumerate(ipd_doc.stiching_item_details):
					attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value
					v = True
					panel_part = set_item_stitching_attrs[item.stiching_attribute_value]
					if panel_part != part:
						v = False							
					if v:
						new_variant = get_or_create_variant(itemname, attributes)
						if item_list[itemname].get(new_variant):
							item_list[itemname][new_variant]['qty'] += (details['qty']*item.quantity)
						else:	
							item_list[itemname][new_variant] = {
								'qty': details['qty']*item.quantity,
								'uom':details['uom'],
							}
			else:
				for id,item in enumerate(ipd_doc.stiching_item_details):
					attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value
					new_variant = get_or_create_variant(itemname, attributes)
					if item_list[itemname].get(new_variant):
						item_list[itemname][new_variant]['qty'] += (details['qty']*item.quantity)
					else:	
						item_list[itemname][new_variant] = {
							'qty': details['qty']*item.quantity,
							'uom':details['uom'],
						}
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
		key.append(item[attr])
	return tuple(key)	

@frappe.whitelist()
def get_grn_structure(doc_name):
	doc = frappe.get_doc("Goods Received Note", doc_name)
	item_details = fetch_grn_item_details(doc.items, doc.lot)
	return item_details

@frappe.whitelist()
def update_calculated_receivables(doc_name, receivables, received_type):
	if isinstance(receivables, string_types):
		receivables = json.loads(receivables)

	grn_doc = frappe.get_doc("Goods Received Note", doc_name)
	for received_item in receivables:
		for item in grn_doc.items:
			if received_item['item_variant'] == item.item_variant:
				received_types = item.received_types
				if not received_types:
					received_types = {}
				if isinstance(received_types, string_types):
					received_types = json.loads(received_types)
						
				if received_types.get(received_type):
					item.received_quantity -= received_types.get(received_type)
					item.quantity += received_types.get(received_type)
					received_types[received_type] = received_item['qty']
					item.received_quantity += received_item['qty']
					item.quantity -= received_item['qty']
					item.received_types = received_types
				else:
					received_types[received_type] = received_item['qty']
					item.received_quantity += received_item['qty']
					item.quantity -= received_item['qty']
					item.received_types = received_types
				break	
	grn_doc.save()

