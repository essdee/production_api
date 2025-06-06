# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe, json, sys
from itertools import groupby
from datetime import datetime
from itertools import zip_longest
from frappe.model.document import Document
from frappe.utils import flt, nowdate, now
from production_api.mrp_stock.utils import get_stock_balance
from production_api.mrp_stock.stock_ledger import make_sl_entries, repost_future_stock_ledger_entry
from production_api.production_api.logger import get_module_logger
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant
from production_api.utils import get_panel_list, update_if_string_instance, update_variant
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index

class DeliveryChallan(Document):
	def before_cancel(self):
		if self.is_internal_unit:
			ste_list = frappe.get_list("Stock Entry", filters={
				"against":self.doctype,
				"against_id":self.name,
				"purpose":"DC Completion",
				"docstatus":1,
			}, pluck="name")
			for name in ste_list:
				doc = frappe.get_doc("Stock Entry", name)
				doc.cancel()
	
	def on_cancel(self):
		logger = get_module_logger("delivery_challan")
		logger.debug(f"On Cancel {datetime.now()}")
		wo_doc = frappe.get_doc("Work Order",self.work_order)
		for item in self.items:
			for deliverable in wo_doc.deliverables:
				if item.ref_docname == deliverable.name:
					deliverable.pending_quantity += item.delivered_quantity
					item.delivered_quantity = 0
					break
		logger.debug(f"{self.name} Work Order Deliverables Updated {datetime.now()}")
		self.ignore_linked_doctypes = ('Stock Ledger Entry', 'Repost Item Valuation')
		add_sl_entries = []
		reduce_sl_entries = []
		stock_settings = frappe.get_single("Stock Settings")
		received_type = stock_settings.default_received_type
		transit_warehouse = stock_settings.transit_warehouse
		res = get_variant_stock_details()
		self.total_delivered_qty = 0
		for row in self.items:
			if res.get(row.item_variant):
				add_sl_entries.append(self.get_sle_data(row, self.from_location, 1, {}, received_type))	
				supplier = transit_warehouse if self.is_internal_unit else self.supplier
				reduce_sl_entries.append(self.get_sle_data(row, supplier, -1, {}, received_type))
		logger.debug(f"{self.name} SLE data construction {datetime.now()}")
		make_sl_entries(add_sl_entries)
		logger.debug(f"{self.name} Stock Added to From Location {datetime.now()}")
		make_sl_entries(reduce_sl_entries)
		logger.debug(f"{self.name} Stock reduced From Supplier {datetime.now()}")
		self.make_repost_action()
		wo_doc.save(ignore_permissions=True)	
		if self.cut_panel_movement:
			cpm_doc = frappe.get_doc("Cut Panel Movement", self.cut_panel_movement)	
			cpm_doc.against = None
			cpm_doc.against_id = None
			cpm_doc.save()	
		frappe.enqueue(calculate_pieces,"short", doc_name=self.name, enqueue_after_commit=True )		

	def on_submit(self):
		# calculate_pieces(self.name)
		if self.cut_panel_movement:
			cpm_doc = frappe.get_doc("Cut Panel Movement", self.cut_panel_movement)	
			cpm_doc.against = self.doctype
			cpm_doc.against_id = self.name
			cpm_doc.save()		
		frappe.enqueue(calculate_pieces,"short", doc_name=self.name, enqueue_after_commit=True )

	def before_submit(self):
		if not self.vehicle_no:
			frappe.throw("Enter the Vehicle Number")

		self.letter_head = frappe.db.get_single_value("MRP Settings","dc_grn_letter_head")
		logger = get_module_logger("delivery_challan")
		logger.debug(f"On Submit {datetime.now()}")
		add_sl_entries = []
		reduce_sl_entries = []
		res = get_variant_stock_details()
		stock_settings = frappe.get_single("Stock Settings")
		default_received_type = stock_settings.default_received_type
		transit_warehouse = stock_settings.transit_warehouse
		total_delivered = flt(0)
		items = []
		for row in self.items:
			if res.get(row.item_variant) and row.delivered_quantity > 0:
				items.append(row.as_dict())
				received_type = default_received_type
				if row.item_type:
					received_type = row.item_type
				quantity, rate = get_stock_balance(row.item_variant, self.from_location,received_type, with_valuation_rate=True, lot=self.lot)
				if flt(quantity) < flt(row.delivered_quantity):
					frappe.throw(f"Required quantity is {row.delivered_quantity} but stock quantity is {quantity} for {row.item_variant}")
				row.rate = rate	
				total_delivered += row.delivered_quantity	
				reduce_sl_entries.append(self.get_sle_data(row, self.from_location, -1, {}, received_type))
				supplier = transit_warehouse if self.is_internal_unit else self.supplier
				add_sl_entries.append(self.get_sle_data(row, supplier, 1, {}, received_type))
		if len(items) == 0:
			frappe.throw("There is no deliverables in this DC")
		self.set("items", items)
		self.total_delivered_qty = total_delivered
		logger.debug(f"{self.name} Stock check and SLE data construction {datetime.now()}")
		wo_doc = frappe.get_cached_doc("Work Order", self.work_order)
		for deliverable in wo_doc.deliverables:
			for item in self.items:
				if item.ref_docname == deliverable.name:
					deliverable.pending_quantity ='{0:.3f}'.format(deliverable.pending_quantity - item.get('delivered_quantity'))
					if item.get('delivered_quantity'):
						deliverable.valuation_rate = item.get('rate')
					break
		wo_doc.save(ignore_permissions=True)
		logger.debug(f"{self.name} Work Order deliverables updated {datetime.now()}")
		make_sl_entries(reduce_sl_entries)
		logger.debug(f"{self.name} Stock reduced from From Location {datetime.now()}")
		make_sl_entries(add_sl_entries)
		logger.debug(f"{self.name} Stock Added to Supplier {datetime.now()}")
		self.make_repost_action()

	def make_repost_action(self):
		repost_future_stock_ledger_entry(self)
	
	def before_save(self):
		if self.docstatus == 1:
			return
		for row in self.items:
			if row.delivered_quantity:
				if row.delivered_quantity < 0:
					frappe.throw("Only positive")
	
	def onload(self):
		if self.get('items'):
			if self.is_rework:
				deliverable_item_details = fetch_rework_dc_item_details(self.get('items'), self.production_detail,self.lot)
			else:	
				deliverable_item_details = fetch_item_details(self.get('items'), self.production_detail,self.lot)
			self.set_onload('deliverable_item_details', deliverable_item_details)
	
	def before_validate(self):
		if self.docstatus == 1:
			return
		docstatus = frappe.get_value("Work Order", self.work_order, "docstatus")
		if docstatus != 1:
			frappe.throw("Select the Valid Work Order")

		if(self.get('deliverable_item_details')):
			deliverables = stock_value = None
			if self.is_rework:
				deliverables,stock_value = save_rework_deliverables(self.deliverable_item_details,self.from_location, self.production_detail)
			else:	
				deliverables,stock_value = save_deliverables(self.deliverable_item_details,self.from_location, self.production_detail)
			self.set('items',deliverables)
			self.stock_value = stock_value
			self.total_value = stock_value
		
		if self.additional_goods_value:
			self.total_value = self.stock_value + self.additional_goods_value	

	def get_sle_data(self, row, location, multiplier, args, received_type):
		sl_dict = frappe._dict({
			"doctype": "Stock Ledger Entry",
			"item": row.item_variant,
			"lot": row.lot,
			"warehouse": location,
			"received_type":received_type,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": row.name,
			"qty": row.delivered_quantity * multiplier,
			"uom": row.uom,
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"rate": flt(row.rate, row.precision("rate")),
			"valuation_rate": flt(row.rate, row.precision("rate")),
		})
		sl_dict.update(args)
		return sl_dict

def save_rework_deliverables(item_details, from_location, ipd):
	item_details = update_if_string_instance(item_details)
	items_list = []
	total_stock_value = 0
	for received_type in item_details:
		items, stock_value = save_deliverables(item_details[received_type], from_location, ipd, received_type=received_type)
		items_list = items_list + items
		total_stock_value += stock_value
	return items_list, total_stock_value

def save_deliverables(item_details, from_location, ipd, received_type=None):
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_or_create_ipd_variant
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	item_variants = update_if_string_instance(ipd_doc.variants_json)
	item_details = update_if_string_instance(item_details)
	items = []
	row_index = 0
	stock_value = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				comments = item.get('comments', None)
				for attr, values in item['values'].items():	
					if values.get('qty') or values.get('delivered_quantity'):
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						# tup = tuple(sorted(item_attributes.items()))
						variant_name = get_or_create_variant(item_name, item_attributes)
						# variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, item_attributes)
						# str_tup = str(tup)
						# item_variants = update_variant(item_variants, variant_name, item_name, str_tup)
						item1['item_variant'] = variant_name
						item1['lot'] = item.get('lot')
						item1['qty'] = values.get('qty')
						item1['secondary_qty'] = values.get('secondary_qty')
						item1['secondary_uom'] = values.get('secondary_uom')						
						item1['delivered_quantity'] = values.get('delivered_quantity')
						item1['pending_quantity'] = item1['qty'] - item1['delivered_quantity']
						item1['uom'] = item.get('default_uom')
						item1['rate'] = values.get('rate')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						if values.get("row_index"):
							item1['row_index'] = values.get("row_index")
						if values.get("table_index"):
							item1['table_index'] = values.get("table_index")
						item1['ref_doctype'] = values.get('ref_doctype')
						item1['ref_docname'] = values.get('ref_docname')
						item1['is_calculated'] = values.get('is_calculated')
						item1['set_combination'] = values.get('set_combination', {})
						item1['comments'] = comments
						if received_type:
							item1['item_type'] = received_type
						stock = get_stock_value(variant_name, item.get('lot'), from_location)
						item1['stock_value'] = stock
						stock_value += stock
						items.append(item1)		
			else:
				if item['values']['default'].get('qty') or item['values']['default'].get('delivered_quantity'):	
					item1 = {}
					# tup = tuple(sorted(item_attributes.items()))
					variant_name = get_or_create_variant(item_name, item_attributes)

					# variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, item_attributes)
					# str_tup = str(tup)
					# item_variants = update_variant(item_variants, variant_name, item_name, str_tup)
					item1['item_variant'] = variant_name
					item1['qty'] = item['values']['default'].get('qty')
					item1['secondary_qty'] = item['values']['default'].get('secondary_qty')
					item1['secondary_uom'] = item['values']['default'].get('secondary_uom')
					item1['lot'] = item.get('lot')
					item1['delivered_quantity'] = item['values']['default'].get('delivered_quantity')
					item1['pending_quantity'] = item1['qty'] - item1['delivered_quantity']
					item1['uom'] = item.get('default_uom')
					item1['rate'] = item['values']['default'].get('rate')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['ref_doctype'] = item['values']['default'].get('ref_doctype')
					item1['ref_docname'] = item['values']['default'].get('ref_docname')
					item1['is_calculated'] = item['values']['default'].get('is_calculated')
					item1['set_combination'] = item['values']['default'].get('set_combination', {})
					item1['comments'] = item['values']['default'].get('comments', None)
					stock = get_stock_value(variant_name,item.get('lot'),from_location)
					item1['stock_value'] = stock
					stock_value += stock
					items.append(item1)		
			row_index += 1	
	ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)		
	return items, stock_value

def fetch_rework_dc_item_details(items, ipd, lot):
	items = [item.as_dict() for item in items]
	items = update_if_string_instance(items)
	grouped_items = {}
	for received_type, grp_variants in groupby(items, lambda i: i['item_type']):
		item_details = fetch_item_details(grp_variants, ipd, lot, is_rework=True)
		grouped_items[received_type] = item_details
	return grouped_items

def fetch_item_details(items, ipd, lot, is_new=False, is_rework=False):
	if not is_rework:
		items = [item.as_dict() for item in items]
	items = update_if_string_instance(items)
	items = sorted(items, key = lambda i: i['row_index'])
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
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
		}

		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0, 'delivered_quantity': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				set_combination = update_if_string_instance(variant['set_combination'])
				if set_combination:
					if set_combination.get("major_part"):
						item['item_keys']['major_part'] = set_combination.get("major_part")
					if set_combination.get("major_colour"):
						item['item_keys']['major_colour'] = set_combination.get("major_colour")		

				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'rate': variant['rate'],
							'ref_doctype':"Work Order Deliverables",
							"is_calculated":variant.is_calculated,
							'set_combination':variant.set_combination,
							"table_index": variant.table_index,
							"row_index": variant.row_index,
						}
						if is_new:
							item['values'][attr.attribute_value]['qty'] = variant['pending_quantity']
							item['values'][attr.attribute_value]['delivered_quantity'] = 0
							item['values'][attr.attribute_value]['ref_docname'] = variant['name']
						else:
							item['values'][attr.attribute_value]['qty'] = variant['qty']
							item['values'][attr.attribute_value]['secondary_uom'] = variant['secondary_uom']
							item['values'][attr.attribute_value]['secondary_qty'] = variant['secondary_qty']
							item['values'][attr.attribute_value]['delivered_quantity'] = variant.get("delivered_quantity", 0)							
							item['values'][attr.attribute_value]['ref_docname'] = variant['ref_docname']
							item['comments'] = variants[0]['comments']
						break
		else:
			item['values']['default'] = {
				'rate': variants[0]['rate'],
				"ref_doctype":"Work Order Deliverables",
				"is_calculated":variants[0].is_calculated,
				"table_index": variants[0].table_index,
				"row_index": variants[0].row_index,
			}
			if is_new:
				item['values']['default']['qty'] = variants[0]['pending_quantity']
				item['values']['default']['delivered_quantity'] = 0
				item['values']['default']['ref_docname'] = variants[0]['name']
			else:
				item['values']['default']['qty'] = variants[0]['qty']
				item['values']['default']['secondary_uom'] = variants[0]['secondary_uom']
				item['values']['default']['secondary_qty'] = variants[0]['secondary_qty']
				item['values']['default']['delivered_quantity'] = variants[0].get("delivered_quantity", 0)
				item['values']['default']['ref_docname'] = variants[0]['ref_docname']
				item['values']['default']['comments'] = variants[0]['comments']

		index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				"lot":lot,
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details["primary_attribute_values"],
				'dependent_attribute': current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				"is_set_item": ipd_doc.is_set_item,
				"set_attr": ipd_doc.set_item_attribute,
				"pack_attr": ipd_doc.packing_attribute,
				"major_attr_value": ipd_doc.major_attribute_value,
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	print(item_details)
	return item_details
			
@frappe.whitelist()
def get_deliverables(work_order):
	from production_api.production_api.doctype.work_order.work_order import fetch_rework_item_details
	doc = frappe.get_cached_doc("Work Order",work_order)
	if doc.is_rework:
		items = fetch_rework_item_details(doc.deliverables, doc.production_detail, is_dc=True)
	else:	
		items = fetch_item_details(doc.deliverables, doc.production_detail, doc.lot, is_new=True)	
	return {
		"items":items,
		"supplier":doc.supplier,
		"supplier_address":doc.supplier_address,
	}

def get_stock_value(variant, lot, from_location):
	query_result = frappe.db.sql(
        """ 
			SELECT stock_value, valuation_rate FROM `tabStock Ledger Entry`
			WHERE item = %s AND warehouse = %s and lot = %s ORDER BY posting_date DESC, posting_time DESC LIMIT 1
        """, (variant, from_location, lot), as_dict=True
    )
	if query_result:
		return query_result[0]['stock_value']
	return 0

def get_variant_stock_details():
	result = frappe.db.sql(
		"""
			SELECT `tabItem Variant`.name as variant, `tabItem`.is_stock_item as is_stock FROM `tabItem Variant` JOIN `tabItem` 
			ON `tabItem`.name = `tabItem Variant`.item WHERE `tabItem`.is_stock_item = 1;
		"""
	)		
	res = {}
	for row in result:
		res[row[0]] = row[1]
	return res	 

@frappe.whitelist()
def get_dc_structure(doc_name):
	doc = frappe.get_doc("Delivery Challan", doc_name)
	item_details = fetch_item_details(doc.items, doc.production_detail, doc.lot)
	return item_details

@frappe.whitelist()
def get_current_user_time():
	d = datetime.now()
	d = datetime.fromtimestamp(d.timestamp()).strftime("%c")
	return [frappe.session.user, d]

@frappe.whitelist()
def get_calculated_items(doc_name,work_order):
	from production_api.production_api.doctype.work_order.work_order import fetch_order_item_details
	doc = frappe.get_doc("Work Order", work_order)
	items = fetch_order_item_details(doc.work_order_calculated_items, doc.production_detail)
	return items

@frappe.whitelist()
def get_calculated_deliverables(items,wo_name, doc_name, deliverable):
	from production_api.production_api.doctype.work_order.work_order import get_deliverable_receivable
	logger = get_module_logger("delivery_challan")
	logger.debug(f"{doc_name} Deliverable Calculation Started {datetime.now()}")
	items = get_deliverable_receivable(items, wo_name, deliverable=deliverable)
	logger.debug(f"{doc_name} Deliverables Calculated {datetime.now()}")
	doc = frappe.get_doc("Delivery Challan", doc_name)
	for item1 in doc.items:
		for item2 in items:
			set1 = update_if_string_instance(item1.set_combination)
			set2 = update_if_string_instance(item2['set_combination'])
			if item1.item_variant == item2['item_variant'] and set1 == set2:
				item1.delivered_quantity = item2['qty']
				item1.set_combination = item2.get('set_combination', {})
				break
	doc.save()

@frappe.whitelist()
def construct_stock_entry_details(doc_name):
	doc = frappe.get_doc("Delivery Challan", doc_name)
	stock_settings = frappe.get_single("Stock Settings")
	received_type = stock_settings.default_received_type
	items = []
	for item in doc.items:
		if item.delivered_quantity - item.ste_delivered_quantity > 0:
			items.append({
				"item": item.item_variant,
				"lot": item.lot,
				"qty": item.delivered_quantity - item.ste_delivered_quantity,
				"uom": item.uom,
				"received_type": received_type,
				"secondary_qty": item.secondary_qty,
				"secondary_uom": item.secondary_uom,
				"against_id_detail": item.name,
				"table_index": item.table_index,
				"row_index": item.row_index,
				"remarks": item.comments,
				"set_combination": item.set_combination,
			})
	ste = frappe.new_doc("Stock Entry")
	ste.purpose = "DC Completion"
	ste.against = "Delivery Challan"
	ste.against_id = doc_name
	ste.from_warehouse = doc.from_location
	ste.to_warehouse = doc.supplier
	ste.set("items", items)
	ste.flags.allow_from_dc = True
	ste.save()
	return ste.name

@frappe.whitelist()
def calculate_pieces(doc_name):
	dc_doc = frappe.get_doc("Delivery Challan",doc_name)
	doc_status = dc_doc.docstatus
	ipd = frappe.get_cached_value("Lot", dc_doc.lot,"production_detail")
	ipd_doc = frappe.get_cached_doc("Item Production Detail",ipd)
	total_delivered = 0
	incomplete_items = {}
	process_name = dc_doc.process_name
	prs_doc = frappe.get_cached_doc("Process", process_name)
	if prs_doc.is_manual_entry_in_grn:
		return
	
	final_calculation = []
	if prs_doc.is_group:
		for detail in prs_doc.process_details:
			process_name = detail.process_name
			break
	
	if process_name == ipd_doc.cutting_process:
		return
	elif process_name == ipd_doc.stiching_process:
		panel_list = get_panel_list(ipd_doc)
		incomplete_items, completed_items, total_delivered, qty_list = calculate_cutting_piece(dc_doc, panel_list)

	elif process_name == ipd_doc.packing_process:
		final_calculation, total_delivered = calculate_piece_stage(dc_doc, doc_status, total_delivered, final_calculation)
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
				for item in dc_doc.items:
					qty = item.delivered_quantity
					if doc_status == 2:
						qty = qty * -1
					set_combination = update_if_string_instance(item.set_combination)
					final_calculation.append({
						"item_variant": item.item_variant,
						"quantity": qty,
						"set_combination":set_combination
					})
					total_delivered += qty
			else:
				if stage == ipd_doc.stiching_in_stage:
					panel_list = emb.get(process_name)

		if stage and check:
			if stage == ipd_doc.pack_in_stage:
				final_calculation, total_delivered = calculate_piece_stage(dc_doc, doc_status, total_delivered, final_calculation)

			elif stage == ipd_doc.stiching_in_stage:
				if not panel_list:	
					panel_list = get_panel_list(ipd_doc)
					incomplete_items, completed_items, total_delivered, qty_list = calculate_cutting_piece(dc_doc, panel_list)
				elif panel_list:
					incomplete_items, completed_items, total_delivered, qty_list = calculate_cutting_piece(dc_doc, panel_list)
				else:
					return

	wo_doc = frappe.get_cached_doc("Work Order", dc_doc.work_order)
	if not wo_doc.first_dc_date:
		wo_doc.start_date = dc_doc.posting_date
		wo_doc.first_dc_date = dc_doc.posting_date
		wo_doc.last_dc_date = dc_doc.posting_date
	else:
		wo_doc.last_dc_date = dc_doc.posting_date

	wo_doc.total_no_of_pieces_delivered += total_delivered
	if incomplete_items:
		wo_doc.wo_delivered_incompleted_json = incomplete_items
		wo_doc.wo_delivered_completed_json = completed_items			
		for qty_data in qty_list:
			for item in wo_doc.work_order_calculated_items:
				set_combination = update_if_string_instance(item.set_combination)
				if item.item_variant == qty_data['item_variant'] and set_combination == qty_data['set_combination']:
					qty = qty_data['quantity']
					if doc_status == 2:
						qty = qty * -1
					item.delivered_quantity += qty
					break 
	else:
		for data in final_calculation:
			for item in wo_doc.work_order_calculated_items:
				set_combination = update_if_string_instance(item.set_combination)
				if item.item_variant == data['item_variant'] and set_combination == data['set_combination']:
					item.delivered_quantity += data['quantity']
	wo_doc.save(ignore_permissions=True)

def calculate_piece_stage(dc_doc, doc_status, total_delivered, final_calculation):
	for item in dc_doc.items:
		qty = item.delivered_quantity
		if doc_status == 2:
			qty = qty * -1
		set_combination = update_if_string_instance(item.set_combination)
		final_calculation.append({
			"item_variant": item.item_variant,
			"quantity": qty,
			"set_combination":set_combination
		})
		total_delivered += qty
	return final_calculation, total_delivered

def calculate_cutting_piece(dc_doc, panel_list):
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_or_create_ipd_variant
	panel_list = update_if_string_instance(panel_list)		
	production_detail, incomplete_items_json, completed_items_json = frappe.get_cached_value("Work Order", dc_doc.work_order,['production_detail',"wo_delivered_incompleted_json","wo_delivered_completed_json"])
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

	for item in dc_doc.items:
		variant = frappe.get_cached_doc("Item Variant", item.item_variant)
		attrs = get_variant_attributes(variant)
		if not attrs.get(ipd_doc.stiching_attribute):
			continue
		set_combination = update_if_string_instance(item.set_combination)
		for i in incomplete_items['items']:
			con1 = True
			if ipd_doc.is_set_item:
				con1 = i['attributes'][ipd_doc.set_item_attribute] == set_comb[attrs[ipd_doc.stiching_attribute]]
			item_keys = update_if_string_instance(i['item_keys'])
			set_combination = update_if_string_instance(item.set_combination)
			con2 = item_keys == set_combination
			if con1 and con2 and item.delivered_quantity > 0:
				primary_attr = attrs[ipd_doc.primary_item_attribute]
				x = i['values'][primary_attr][attrs[ipd_doc.stiching_attribute]]
				y = i.copy()
				if not x:
					i['values'][attrs[ipd_doc.primary_item_attribute]][attrs[ipd_doc.stiching_attribute]] = item.delivered_quantity
				else:
					y['values'][attrs[ipd_doc.primary_item_attribute]][attrs[ipd_doc.stiching_attribute]] += item.delivered_quantity	
				i = y

	total_qty = 0
	for item1, item2 in zip_longest(completed_items['items'], incomplete_items['items']):
		for size in item2['values']:
			min = sys.maxsize
			for panel in item2['values'][size]:
				if panel in panel_list:
					if item2['values'][size][panel]:
						if item2['values'][size][panel]:
							if item2['values'][size][panel] < min:
								min = item2['values'][size][panel]
					else:
						min = 0
			if min > 0 and min != sys.maxsize:
				if item1['values'][size]:
					item1['values'][size] += min									
				else:
					item1['values'][size] = min

				total_qty += min

				for panel in item2['values'][size]:
					if panel in panel_list:
						if item2['values'][size][panel]:
							item2['values'][size][panel] -= (min * panel_qty[panel])

	qty_list = []
	for item in completed_items['items']: 
		attrs = item['attributes']
		for val in item['values']:
			attrs[ipd_doc.primary_item_attribute] = val
			if item['values'][val]:
				# tup = tuple(sorted(attrs.items()))
				item_name = item['name']
				variant_name = get_or_create_variant(item_name, attrs)
				# variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, attrs)
				# str_tup = str(tup) 
				# item_variants = update_variant(item_variants, variant_name, item_name, str_tup)
				qty = item['values'][val]
				set_combination = update_if_string_instance(item['item_keys'])
				qty_list.append({
					"item_variant": variant_name,
					"quantity": qty,
					"set_combination":set_combination
				})
				item['values'][val] -= qty
	ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)				
	return incomplete_items, completed_items, total_qty, qty_list

def get_variant_attributes(variant):
	attribute_details = {}
	
	for attr in variant.attributes:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

@frappe.whitelist()
def get_return_delivery_items(doc_name):
	doc = frappe.get_doc("Delivery Challan", doc_name)
	item_details = fetch_return_popup_items(doc.items, doc.lot)
	return item_details

@frappe.whitelist()
def create_return_grn(doc_name, items, ipd):
	dc_doc = frappe.get_doc("Delivery Challan", doc_name)
	items = update_if_string_instance(items)
	items_list = get_return_popup_items(items, ipd)
	grn_items = []
	for item in items_list:
		if item['return_quantity']:
			grn_items.append({
				"item_variant": item['item_variant'],
				"lot": dc_doc.lot,
				"quantity": item['return_quantity'],
				"uom": item['uom'],
				"valuation_rate": 0.0,
				"received_type": item['received_type'],
				"ref_docname": item['ref_docname'],
				"ref_doctype": item['ref_doctype'],
				"table_index": item['table_index'],
				"row_index": item['row_index'],
				"set_combination": item['set_combination'],
			})
	new_doc = frappe.new_doc("Goods Received Note")
	new_doc.update({
		"against": "Work Order",
		"is_return": 1,
		"is_rework": dc_doc.is_rework,
		"against_id": dc_doc.work_order,
		"posting_date": nowdate(),
		"posting_time": now(),
		"delivery_date": nowdate(),
		"is_internal_unit": 0,
		"is_manual_entry": 0,
		"delivery_location": dc_doc.from_location,
		"delivery_location_name": dc_doc.from_location_name,
		"supplier": dc_doc.supplier,
		"supplier_name": dc_doc.supplier_name,
		"vehicle_no":"NA",
		"supplier_document_no":"NA",
		"dc_no": dc_doc.name,
		"supplier_address": dc_doc.supplier_address,
		"supplier_address_display": dc_doc.supplier_address_details,
		"delivery_address": dc_doc.from_address,
		"deliverey_address_display": dc_doc.from_address_details,
	})
	new_doc.set("items", grn_items)
	new_doc.save()
	return new_doc.name

def fetch_return_popup_items(items, lot):
	items = [item.as_dict() for item in items]
	items = update_if_string_instance(items)
	items = sorted(items, key = lambda i: i['row_index'])
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
			"item_type": variants[0].get('item_type', None),
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				set_combination = update_if_string_instance(variant['set_combination'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'ref_doctype':"Work Order Deliverables",
							"is_calculated":variant.is_calculated,
							'set_combination':set_combination,
							"delivered_quantity" : variant['delivered_quantity'],		
							"return_quantity" : 0,
							"ref_docname" : variant['ref_docname'],
						}
						break
		else:
			item['values']['default'] = {
				"ref_doctype":"Work Order Deliverables",
				"is_calculated":variants[0].is_calculated,
				"set_combination": {},
				'delivered_quantity' : variants[0]['delivered_quantity'],
				'return_quantity' : 0,
				'ref_docname' : variants[0]['ref_docname'],
			}
		index = get_item_group_index(item_details, current_item_attribute_details)
		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				"lot":lot,
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details["primary_attribute_values"],
				'dependent_attribute': current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return item_details

def get_return_popup_items(item_details, ipd):
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_variant
	variants_json = frappe.get_cached_value("Item Production Detail", ipd, "variants_json")
	item_variants = update_if_string_instance(variants_json)
	item_details = update_if_string_instance(item_details)
	items = []
	default_received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	row_index = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():	
					if values.get('return_quantity'):
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						tup = tuple(sorted(item_attributes.items()))
						variant_name = get_ipd_variant(item_variants, item_name, tup)
						item1['item_variant'] = variant_name
						item1['lot'] = item.get('lot')
						item1['return_quantity'] = values.get('return_quantity')
						item1['uom'] = item.get('default_uom')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['ref_doctype'] = values.get('ref_doctype')
						item1['ref_docname'] = values.get('ref_docname')
						item1['is_calculated'] = values.get('is_calculated')
						item1['set_combination'] = values.get('set_combination', {})
						item1['received_type'] = item.get("item_type", default_received_type)
						items.append(item1)		
			else:
				if item['values']['default'].get('return_quantity'):	
					item1 = {}
					tup = tuple(sorted(item_attributes.items()))
					variant_name = get_ipd_variant(item_variants, item_name, tup)
					item1['item_variant'] = variant_name
					item1['lot'] = item.get('lot')
					item1['return_quantity'] = item['values']['default'].get('return_quantity')
					item1['uom'] = item.get('default_uom')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['ref_doctype'] = item['values']['default'].get('ref_doctype')
					item1['received_type'] = item.get("item_type", default_received_type)
					item1['ref_docname'] = item['values']['default'].get('ref_docname')
					item1['is_calculated'] = item['values']['default'].get('is_calculated')
					item1['set_combination'] = item['values']['default'].get('set_combination', {})
					items.append(item1)		
			row_index += 1	
	return items