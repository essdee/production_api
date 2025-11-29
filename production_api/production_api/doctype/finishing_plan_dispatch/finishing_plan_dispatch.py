# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from itertools import groupby
from operator import itemgetter
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_or_create_variant
from production_api.utils import get_variant_attr_details, update_if_string_instance

class FinishingPlanDispatch(Document):
	def before_cancel(self):
		if self.stock_entry:
			stock_entry = frappe.get_doc("Stock Entry", self.stock_entry)
			stock_entry.cancel()

	def onload(self):
		items = [row.as_dict() for row in self.finishing_plan_dispatch_items]
		items.sort(key=itemgetter('lot', 'item'))
		item_detail = []
		for (lot, item), variants in groupby(items, key=itemgetter('lot', 'item')):
			variants_list = list(variants)
			item1 = {}
			item1['lot'] = lot
			item1['item'] = item
			item1['doc_name'] = variants_list[0]['against_id']
			item1['uom'] = variants_list[0]['uom']
			item1['values'] = {}
			item1['total'] = {
				"total_qty": 0,
				"total_dispatch": 0,
			}
			ipd = frappe.get_value("Lot", lot, "production_detail")
			primary, dependent, pack_out_stage = frappe.get_value("Item Production Detail", ipd, ["primary_item_attribute", "dependent_attribute", "pack_out_stage"])
			item1['primary_attribute'] = primary
			item1['dependent_attribute'] = dependent
			item1['stage'] = pack_out_stage
			for variant in variants_list:
				attr_details = get_variant_attr_details(variant['item_variant'])
				item1['values'][attr_details[primary]] = {
					"qty": variant['balance_qty'],
					"row_detail": variant['against_id_detail'],
					"dispatch_qty": variant['quantity'],
				}
				item1['total']['total_qty'] += variant['balance_qty']
				item1['total']['total_dispatch'] += variant['quantity']

			item_detail.append(item1)
		self.set_onload("items", item_detail)		

	def before_validate(self):
		if self.get('finishing_items'):
			finishing_items = update_if_string_instance(self.finishing_items)
			items = []
			for row in finishing_items:
				for val in row['values']:
					attrs = {
						row['primary_attribute']: val,
						row['dependent_attribute']: row['stage'] 
					}
					variant = get_or_create_variant(row['item'], attrs)
					items.append({
						"item_variant": variant,
						"lot": row['lot'],
						"balance_qty": row['values'][val]['qty'],
						"quantity": row['values'][val]['dispatch_qty'],
						"uom": row['uom'],
						"item": row['item'],
						"against_id": row['doc_name'],
						"against_id_detail": row['values'][val]['row_detail']
					})
			self.set("finishing_plan_dispatch_items", items)	

	def before_submit(self):
		group = {}
		for row in self.finishing_plan_dispatch_items:
			key = (row.lot, row.item)
			group.setdefault(key, {
				"items": [],
				"check": False,
			})
			if row.quantity > 0:
				group[key]['check'] = True
			group[key]['items'].append({
				"item_variant": row.item_variant,
				"lot": row.lot,
				"balance_qty": row.balance_qty,
				"quantity": row.quantity,
				"uom": row.uom,
				"item": row.item,
				"against_id": row.against_id,
				"against_id_detail": row.against_id_detail
			})	
		items = []	
		for grp in group:
			if group[grp]['check']:
				items = items + group[grp]['items']
		self.set("finishing_plan_dispatch_items", items)		

@frappe.whitelist()
def fetch_fp_items():
	fp_list = frappe.get_all("Finishing Plan", pluck="name")
	item_detail = []	
	for fp in fp_list:
		fp_doc = frappe.get_doc("Finishing Plan", fp)
		uom = frappe.get_value("Lot", fp_doc.lot, "uom")
		item = {}
		item['lot'] = fp_doc.lot
		item['item'] = fp_doc.item
		item['doc_name'] = fp
		item['uom'] = uom
		item['values'] = {}
		ipd = frappe.get_value("Lot", fp_doc.lot, "production_detail")
		primary, dependent, pack_out_stage = frappe.get_value("Item Production Detail", ipd, ["primary_item_attribute", "dependent_attribute", "pack_out_stage"])
		item['primary_attribute'] = primary
		item['dependent_attribute'] = dependent
		item['stage'] = pack_out_stage
		check = False
		for row in fp_doc.finishing_plan_grn_details:
			attr_details = get_variant_attr_details(row.item_variant)
			if row.quantity - row.dispatched > 0:
				check = True
			item['values'][attr_details[primary]] = {
				"qty": row.quantity - row.dispatched,
				"row_detail": row.name,
				"dispatch_qty": 0,
			}
		if check:	
			item_detail.append(item)

	return item_detail

@frappe.whitelist()
def create_stock_dispatch(doc_name, from_location, to_location, vehicle_no, goods_value):
	self = frappe.get_doc("Finishing Plan Dispatch", doc_name)
	items = [row.as_dict() for row in self.finishing_plan_dispatch_items]
	items.sort(key=itemgetter('lot', 'item'))
	item_list = []
	table_index = 0
	row_index = 0
	for (lot, item), variants in groupby(items, key=itemgetter('lot', 'item')):
		variants_list = list(variants)
		default_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
		for variant in variants_list:
			item_list.append({
				"item": variant['item_variant'],
				"qty": variant['quantity'],
				"lot": lot,
				"received_type": default_type,
				"uom": variant['uom'],
				'table_index': table_index,
				'row_index': row_index,
				'set_combination': {},
			})
		table_index += 1
		row_index += 1	
		
	doc = frappe.new_doc("Stock Entry")	
	doc.purpose = "Material Issue"
	doc.against = "Finishing Plan Dispatch"
	doc.against_id = doc_name
	doc.from_warehouse = from_location
	doc.transfer_supplier = to_location
	from production_api.mrp_stock.doctype.stock_entry.stock_entry import fetch_stock_entry_items
	item_details = fetch_stock_entry_items(item_list)
	doc.item_details = item_details
	doc.vehicle_no = vehicle_no
	doc.additional_amount = goods_value
	doc.save()
	doc.submit()