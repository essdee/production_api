# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from itertools import groupby
import frappe
from frappe import _
from frappe.utils import money_in_words, flt, cstr, date_diff
from frappe.model.document import Document
from six import string_types
from itertools import zip_longest

import json

from production_api.production_api.doctype.item.item import get_variant, create_variant, get_attribute_details
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index

class GoodsReceivedNote(Document):
	def onload(self):
		if self.against == "Work Order":
			item_details = fetch_wo_grn_item_details(self.get('items'), self.docstatus)
		else:
			item_details = fetch_grn_item_details(self.get('items'), docstatus=self.docstatus)
		self.set('print_item_details', json.dumps(item_details))
		self.set_onload('item_details', item_details)
	
	def before_save(self):
		if self.against == 'Purchase Order': 
			self.calculate_amount()

	def before_submit(self):
		doc = frappe.get_doc(self.against, self.against_id)
		against_docstatus = doc.docstatus
		if against_docstatus != 1:
			frappe.throw(f'{self.against} is not submitted.', title='GRN')
		# Remove all item rows quantity is zero
		for item in self.items:
			if item.quantity == 0 and self.against == 'Purchase Order':
				self.items.remove(item)
		if self.against == 'Purchase Order':		
			self.validate_quantity()
			self.calculate_amount()
		else:
			table_name = None
			table_data = None

			if self.return_of_materials:
				table_name = "Work Order Deliverables"
				table_data = doc.deliverables
			else:
				table_name = "Work Order Receivables"
				table_data = doc.receivables

			for item in self.items:
				docname = frappe.db.get_value(table_name,item.ref_docname, 'name')
				if docname == item.ref_docname:
					for work_order_item in table_data:
						if work_order_item.name == item.ref_docname:
							work_order_item.pending_quantity = work_order_item.pending_quantity - item.get('quantity')
								
			doc.save()
			doc.submit()
		self.set('approved_by', frappe.get_user().doc.name)
		

	
	def on_submit(self):
		if self.against == 'Purchase Order':
			self.update_purchase_order()
		self.update_stock_ledger()	
	
	def on_cancel(self):
		if self.purchase_invoice_name:
			frappe.throw(f'Please remove this GRN from Purchase Invoice {self.purchase_invoice_name} before cancelling. Please Contact Purchase Department.')
		settings = frappe.get_single('MRP Settings')
		cancel_before_days = settings.grn_cancellation_in_days
		if cancel_before_days == 0:
			frappe.throw('GRN cancellation is not allowed.', title='GRN')
		if cancel_before_days and not settings.allow_grn_cancellation:
			if date_diff(frappe.utils.nowdate(), self.creation) > cancel_before_days:
				frappe.throw(f'GRN cannot be cancelled after {cancel_before_days} days of creation.', title='GRN')
		if self.against == 'Purchase Order':
			status = frappe.get_value('Purchase Order', self.against_id, 'open_status')
			if status != 'Open':
				frappe.throw('Purchase order is not open.', title='GRN')
		self.ignore_linked_doctypes = ("Stock Ledger Entry")
		if self.against == 'Purchase Order':
			self.update_purchase_order()
			self.update_stock_ledger()

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
					if self.docstatus == 1 and self.against == 'Purchase Order':
						validate_quantity_tolerance(i.item_variant, i.qty, i.pending_qty, quantity)
					i.set('pending_qty', i.pending_qty - quantity)
					break
		po.save(ignore_permissions=True)

	def before_validate(self):
		if(self.get('item_details')):
			if self.against == "Work Order":
				items = save_wo_grn_items(self.item_details)
			else:	
				items = save_grn_item_details(self.item_details)
			self.set('items', items)
		elif self.is_new() or not self.get('items'):
			frappe.throw('Add items to GRN.', title='GRN')
	
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
		if self.against == 'Purchase Order':
			self.validate_quantity()
	
	def validate_quantity(self):
		total_quantity = 0
		for item in self.items:
			total_quantity += item.quantity
		if total_quantity == 0:
			frappe.throw('Quantity cannot be zero.', title='GRN')
	
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

	def update_stock_ledger(self):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		if self.docstatus == 0:
			return
		sl_entries = []
		for item in self.items:
			sl_entries.append(self.get_sl_entries(item, {}))
		if self.docstatus == 2:
			sl_entries.reverse()
		make_sl_entries(sl_entries)
	
	def get_sl_entries(self, d, args):
		sl_dict = frappe._dict(
			{
				"item": d.get("item_variant", None),
				"warehouse": self.delivery_location,
				"lot": cstr(d.get("lot")).strip(),
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"voucher_detail_no": d.name,
				"qty": flt(d.get("quantity")),
				"uom": d.uom,
				"rate": d.rate,
				"is_cancelled": 1 if self.docstatus == 2 else 0,
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
			}
		)

		sl_dict.update(args)
		return sl_dict


def save_grn_item_details(item_details):
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
					if values.get('qty') or values.get('pending_qty') or values.get('received'):
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						variant_name = get_variant(item_name, item_attributes)
						if not variant_name:
							variant1 = create_variant(item_name, item_attributes)
							variant1.insert()
							variant_name = variant1.name
						validate_quantity_tolerance(variant_name, values.get('qty'), values.get('pending_qty'), values.get('received'))
						item1['item_variant'] = variant_name
						item1['lot'] = item.get('lot')
						# Convert to number if string
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
					variant_name = get_variant(item_name, item_attributes)
					if not variant_name:
						variant1 = create_variant(item_name, item_attributes)
						variant1.insert()
						variant_name = variant1.name
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

def save_wo_grn_items(item_details):
	
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
	items = []
	row_index = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				if(item.get('created')):
					item['created'] = 1
				for attr, values in item['values'].items():	
					if values.get('qty') or values.get('pending_qty') or values.get('received'):
						item_attributes[item.get('primary_attribute')] = attr
						if values.get('rework_details'):
							for rework in values.get('rework_details'):
								variant_name = get_variant(item_name, item_attributes)
								if not variant_name:
									variant1 = create_variant(item_name, item_attributes)
									variant1.insert()
									variant_name = variant1.name
								item1 = {}
								item1['item_variant'] = variant_name
								item1['lot'] = item.get('lot')
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
								item1['item_type'] = rework['item_type']
								item1['type'] = rework['type']
								item1['quantity'] = rework['quantity']
								items.append(item1)
			else:
				if item.get('created'):
					item['created'] = 1
				if item['values'].get('default'):
					if item['values']['default'].get('rework_details'):
						for rework in item['values']['default'].get('rework_details'):
							variant_name = get_variant(item_name, item_attributes)
							if not variant_name:
								variant1 = create_variant(item_name, item_attributes)
								variant1.insert()
								variant_name = variant1.name
							item1 = {}
							item1['item_variant'] = variant_name
							item1['lot'] = item.get('lot')
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
							item1['item_type'] = rework['item_type']
							item1['type'] = rework['type']
							item1['quantity'] = rework['quantity']
							items.append(item1)
			row_index += 1
	return items

def validate_quantity_tolerance(item_variant, total_qty, pending_qty, received_qty):
	item = frappe.get_value("Item Variant", item_variant, "item")
	tolerance_percentage = frappe.get_value("Item", item, "over_delivery_receipt_allowance") or 0
	tolerance = total_qty * (tolerance_percentage / 100)
	if (received_qty - pending_qty) > tolerance:
		frappe.throw(_("Quantity tolerance exceeded for item {0}. Received Quantity must not exceed {1}").format(item, pending_qty + tolerance))
	return True

def fetch_grn_item_details(items, docstatus=0):
	items = [item.as_dict() for item in items]
	if docstatus != 0:
		items = [item for item in items if item.get('quantity') > 0]
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
						doc = frappe.get_doc("Purchase Order Item", variant.ref_docname)
						item['values'][attr.attribute_value]['pending_qty'] = doc.pending_qty
						item['values'][attr.attribute_value]['qty'] = doc.qty  
						item['values'][attr.attribute_value]['secondary_qty'] = doc.secondary_qty
						item['values'][attr.attribute_value]['ref_doctype'] = variant.ref_doctype
						item['values'][attr.attribute_value]['ref_docname'] = variant.ref_docname
						break
		else:
			item['values']['default'] = {
				'received': variants[0].quantity,
				'secondary_received': variants[0].secondary_qty,
				'rate': variants[0].rate,
				'tax': variants[0].tax,
			}
			doc = frappe.get_doc("Purchase Order Item", variants[0].ref_docname)
			item['values']['default']['pending_qty'] = doc.pending_qty
			item['values']['default']['qty'] = doc.qty
			item['values']['default']['secondary_qty'] = doc.secondary_qty
			item['values']['default']['ref_doctype'] = variants[0].ref_doctype
			item['values']['default']['ref_docname'] = variants[0].ref_docname
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

def fetch_wo_grn_item_details(items, docstatus):
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
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
			'created' :1 if variants[0]['quantity'] > 0 else 0 
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			v = []	
			for variant in variants:
				x = {
					"item_type" : variant.item_type, 
					"type" : variant.type,
					"quantity" : variant.quantity
				}	
				current_variant = frappe.get_doc("Item Variant", variant['item_variant'])
				if variant['item_variant'] in v:
					for attr in current_variant.attributes:
						if attr.attribute == item.get('primary_attribute'):
							item['values'][attr.attribute_value]['rework_details'].append(x)
							if docstatus != 1:
								item['values'][attr.attribute_value]['qty'] -= variant.quantity
				else:
					v.append(variant['item_variant'])	
					for attr in current_variant.attributes:
						if attr.attribute == item.get('primary_attribute'):
							item['values'][attr.attribute_value] = {
								'received': variant.quantity,
								'secondary_received': variant.secondary_qty,
								'rate': variant.rate,
								'tax': variant.tax,
								'rework_details' : []
							}
							item['values'][attr.attribute_value]['rework_details'].append(x)
							doc = frappe.get_doc(variant.ref_doctype, variant.ref_docname)
							if docstatus == 1:
								item['values'][attr.attribute_value]['qty'] = flt(doc.pending_quantity)
							else:
								item['values'][attr.attribute_value]['qty'] = flt(doc.pending_quantity) - variant.quantity

							item['values'][attr.attribute_value]['secondary_qty'] = doc.secondary_qty
							item['values'][attr.attribute_value]['ref_doctype'] = variant.ref_doctype
							item['values'][attr.attribute_value]['ref_docname'] = variant.ref_docname	

		else:
			item['values']['default'] = {
				'received': variants[0].quantity,
				'secondary_received': variants[0].secondary_qty,
				'rate': variants[0].rate,
				'tax': variants[0].tax,
				'rework_details': []
			}
			qty = 0.0
			for variant in variants:
				x = {
					"item_type" : variant.item_type, 
					"type" : variant.type,
					"quantity" : variant.quantity
				}
				qty += variant.quantity
				item['values']['default']['rework_details'].append(x)	
			doc = frappe.get_doc(variants[0].ref_doctype, variants[0].ref_docname)
			if docstatus == 1:
				item['values']['default']['qty'] = flt(doc.pending_quantity)
			else:
				item['values']['default']['qty'] = flt(doc.pending_quantity)-flt(qty)
			item['values']['default']['secondary_qty'] = doc.secondary_qty
			item['values']['default']['ref_doctype'] = variants[0].ref_doctype
			item['values']['default']['ref_docname'] = variants[0].ref_docname
		index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				'created' : 1 if variants[0]['quantity'] > 0 else 0  ,
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return item_details


@frappe.whitelist()
def create_rework(doc_name,work_order, return_materials):
	doc = frappe.get_doc("Work Order", work_order)
	grn_doc = frappe.get_doc('Goods Received Note', doc_name)
	receivable = []
	for item in grn_doc.items:
		row = item.as_dict()
		item1 = {}
		item1['item_variant'] = row.item_variant
		item1['lot'] = row.lot
		item1['qty'] = row.quantity
		item1['uom'] = row.uom
		item1['comments'] = row.comments
		item1['pending_qty'] = row.pending_quantity
		item1['table_index'] = row.table_index
		item1['row_index'] = row.row_index
		receivable.append(item1)
	table_data = None
	if return_materials:
		table_data = doc.deliverables
	else:		
		table_data = doc.receivables
	data = {}
	data['parent_wo'] = grn_doc.against_id
	data['deliverables'] = table_data
	data['supplier'] = doc.supplier
	data['process_name'] = doc.process_name
	data['ppo'] = doc.ppo
	data['planned_start_date'] = doc.planned_start_date
	data['planned_end_date'] = doc.planned_end_date
	data['expected_delivery_date'] = doc.expected_delivery_date
	data['supplier_address'] = doc.supplier_address
	data['receivables'] = receivable
	return data