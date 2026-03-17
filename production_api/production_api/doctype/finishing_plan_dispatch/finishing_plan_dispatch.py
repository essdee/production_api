# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from itertools import groupby
from operator import itemgetter
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_or_create_variant, get_attribute_details
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

		# Freeze dispatch snapshot data for print format
		fp_cache = {}
		for row in self.finishing_plan_dispatch_items:
			fp_name = row.against_id
			if fp_name not in fp_cache:
				fp_doc = frappe.get_doc("Finishing Plan", fp_name)
				ipd = frappe.get_value("Lot", fp_doc.lot, "production_detail")
				primary = frappe.get_value("Item Production Detail", ipd, "primary_item_attribute")
				cutting_by_size = {}
				for fp_row in fp_doc.finishing_plan_details:
					va = get_variant_attr_details(fp_row.item_variant)
					size = va.get(primary, "")
					cutting_by_size[size] = fp_row.cutting_qty
				fp_cache[fp_name] = {"primary": primary, "cutting_by_size": cutting_by_size}

			cache = fp_cache[fp_name]
			grn_dispatched = frappe.get_value("Finishing Plan GRN Detail", row.against_id_detail, "dispatched") or 0
			va = get_variant_attr_details(row.item_variant)
			size = va.get(cache["primary"], "")
			cutting_qty = cache["cutting_by_size"].get(size, 0)

			row.total_dispatched = grn_dispatched + row.quantity
			row.dispatch_pct = round((row.total_dispatched / cutting_qty * 100), 2) if cutting_qty > 0 else 0

		self.fp_total_dispatched = sum(row.total_dispatched for row in self.finishing_plan_dispatch_items)

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
		item['total'] = {
			"total_qty": 0,
			"total_dispatch": 0,
		}
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
			item['total']['total_qty'] += row.quantity - row.dispatched
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

def get_fpd_print_data(doc_name):
	"""Return structured print data for a Finishing Plan Dispatch."""
	fpd = frappe.get_doc("Finishing Plan Dispatch", doc_name)
	is_submitted = fpd.docstatus == 1
	items = [row.as_dict() for row in fpd.finishing_plan_dispatch_items]
	items.sort(key=itemgetter('lot', 'item'))

	result = []
	for (lot, item_name), variants in groupby(items, key=itemgetter('lot', 'item')):
		variants_list = list(variants)
		against_id = variants_list[0]['against_id']
		uom = variants_list[0]['uom']

		# Get primary attribute and ordered sizes from the Item
		attr_details = get_attribute_details(item_name)
		primary = attr_details.get("primary_attribute", "")
		ordered_sizes = attr_details.get("primary_attribute_values", [])

		# Get pack_out_stage from IPD
		ipd = frappe.get_value("Lot", lot, "production_detail")
		pack_out_stage = frappe.get_value("Item Production Detail", ipd, "pack_out_stage") if ipd else ""

		# Build dispatch qty per size from this FPD's items
		dispatch_by_size = {}
		frozen_by_size = {}
		for v in variants_list:
			va = get_variant_attr_details(v['item_variant'])
			size = va.get(primary, "")
			dispatch_by_size[size] = v['quantity']
			if is_submitted:
				frozen_by_size[size] = {
					"total_dispatched": v.get('total_dispatched', 0),
					"dispatch_pct": v.get('dispatch_pct', 0),
				}

		if is_submitted:
			# Use frozen snapshot data from child table
			all_sizes = set(dispatch_by_size.keys())
			sizes = [s for s in ordered_sizes if s in all_sizes]

			size_data = {}
			total_dispatch = 0
			total_dispatched_all = 0
			for size in sizes:
				dq = dispatch_by_size.get(size, 0)
				frozen = frozen_by_size.get(size, {})
				size_data[size] = {
					"dispatch_qty": dq,
					"dispatch_pct": round(frozen.get("dispatch_pct", 0), 1),
					"total_dispatched": frozen.get("total_dispatched", 0),
				}
				total_dispatch += dq
				total_dispatched_all += frozen.get("total_dispatched", 0)
		else:
			# Draft: compute live from Finishing Plan
			fp_doc = frappe.get_doc("Finishing Plan", against_id)

			cutting_by_size = {}
			for row in fp_doc.finishing_plan_details:
				va = get_variant_attr_details(row.item_variant)
				size = va.get(primary, "")
				cutting_by_size[size] = row.cutting_qty

			dispatched_by_size = {}
			for row in fp_doc.finishing_plan_grn_details:
				va = get_variant_attr_details(row.item_variant)
				size = va.get(primary, "")
				dispatched_by_size[size] = row.dispatched

			all_sizes = set(dispatch_by_size.keys()) | set(cutting_by_size.keys())
			sizes = [s for s in ordered_sizes if s in all_sizes]

			size_data = {}
			total_dispatch = 0
			total_dispatched_all = 0
			for size in sizes:
				dq = dispatch_by_size.get(size, 0)
				cum_dispatched = dispatched_by_size.get(size, 0)
				cutting = cutting_by_size.get(size, 0)
				pct = (cum_dispatched / cutting * 100) if cutting else 0
				size_data[size] = {
					"dispatch_qty": dq,
					"dispatch_pct": round(pct, 1),
					"total_dispatched": cum_dispatched,
				}
				total_dispatch += dq
				total_dispatched_all += cum_dispatched

		result.append({
			"lot": lot,
			"item": item_name,
			"stage": pack_out_stage or "",
			"uom": uom or "",
			"sizes": sizes,
			"size_data": size_data,
			"total_dispatch": total_dispatch,
			"total_dispatched_all": total_dispatched_all,
		})

	return result