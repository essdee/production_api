# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from itertools import groupby
from frappe.model.document import Document
from production_api.production_api.doctype.supplier.supplier import get_primary_address
from production_api.production_api.doctype.work_order.work_order import create_finishing_detail
from production_api.production_api.doctype.item.item import get_or_create_variant, get_attribute_details
from production_api.utils import update_if_string_instance, get_finishing_plan_dict, get_finishing_plan_list
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index
from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import get_variant_attr_details

class FinishingPlan(Document):
	def onload(self):
		data = self.get_finishing_plans()
		packed_qty = self.get_packed_qty()
		self.set_onload("finishing_plan_data", {
			"primary_values": data['primary_values'],
			"data": data['finishing_inward'],
			"is_set_item": data['is_set_item'],
			"set_attr": data['set_attr'],
		})
		rework_details = self.get_rework_item_details()
		inward_details = self.get_inward_details()
		ocr_details = self.get_ocr_details()
		self.set_onload("finishing_qty_data", {
			"primary_values": data['primary_values'],
			"data": data['finishing_qty'],
			"rework_details": rework_details,
			"is_set_item": data['is_set_item'],
			"set_attr": data['set_attr'],
		})
		self.set_onload("inward_details", {
			"primary_values": data['primary_values'],
			"data": inward_details,
			"is_set_item": data['is_set_item'],
			"set_attr": data['set_attr'],
		})
		self.set_onload("pack_items", packed_qty)
		self.set_onload("finishing_ironing", {
			"primary_values": data['primary_values'],
			"data": data['finishing_ironing'],
			"is_set_item": data['is_set_item'],
			"set_attr": data['set_attr'],
		})
		self.set_onload("pack_return", {
			"primary_values": data['primary_values'],
			"data": data['pack_return'],
			"is_set_item": data['is_set_item'],
			"set_attr": data['set_attr'],
		})
		self.set_onload("ocr_details", {
			"ocr_data":ocr_details,
			"primary_values": data['primary_values']
		})

	def get_ocr_details(self):
		ipd = frappe.get_value("Lot", self.lot, "production_detail")
		ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
		is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)
		ocr_data = {}
		for row in self.finishing_plan_details:
			attr_details = get_variant_attr_details(row.item_variant)
			part_value = "Item"
			if is_set_item:
				part_value = attr_details[set_attr]

			ocr_data.setdefault(part_value, {
				"data": {},
				"total": {},
				"cutting": 0,
				"dc_qty": 0,
				"packed_box": 0,
				"packed_box_qty": 0,
				"rejected": 0,
				"loose_piece": 0,
				"loose_piece_set": 0,
				"pending": 0,
				"sewing_received": 0,
			})
			size = attr_details[primary_attr]
			ocr_data[part_value]['total'].setdefault(size, {
				"cutting_qty": 0,
				"dc_qty": 0,
				"packed_box": 0,
				"packed_box_qty": 0,
				"rejected": 0,
				"loose_piece": 0,
				"loose_piece_set": 0,
				"pending": 0,
				"sewing_received": 0,
			})
			
			set_comb = update_if_string_instance(row.set_combination)
			major_colour = set_comb["major_colour"]
			colour = major_colour
			size = attr_details[primary_attr]
			part = None
			if is_set_item:
				variant_colour = attr_details[pack_attr]
				part = attr_details[set_attr]
				colour = f"{variant_colour} ({major_colour}) @ "+part
			
			ocr_data[part_value]['data'].setdefault(colour, {
				"values": {},
				"colour": attr_details[pack_attr],
				"part": part,
				"colour_total": {
					"loose_piece": 0, "pending": 0, "rejected": 0, "loose_piece_set": 0, "sewing_received": 0,
				}
			})
			ocr_data[part_value]['cutting'] += row.cutting_qty
			ocr_data[part_value]['dc_qty'] += (row.dc_qty + row.return_qty + row.pack_return_qty)
			ocr_data[part_value]['total'][size]['cutting_qty'] += row.cutting_qty
			ocr_data[part_value]['total'][size]['dc_qty'] += (row.dc_qty + row.return_qty + row.pack_return_qty)
			ocr_data[part_value]['data'][colour]['values'].setdefault(size, {
				"loose_piece": 0, "pending": 0, "rejected": 0, "loose_piece_set": 0, "sewing_received": 0,
			})

			ocr_data[part_value]['data'][colour]['values'][size]['sewing_received'] += row.delivered_quantity
			ocr_data[part_value]['data'][colour]['colour_total']['sewing_received'] += row.delivered_quantity
			ocr_data[part_value]['total'][size]['sewing_received'] += row.delivered_quantity
			ocr_data[part_value]['sewing_received'] += row.delivered_quantity

			ocr_data[part_value]['data'][colour]['values'][size]['loose_piece'] += row.return_qty
			ocr_data[part_value]['data'][colour]['colour_total']['loose_piece'] += row.return_qty
			ocr_data[part_value]['total'][size]['loose_piece'] += row.return_qty
			ocr_data[part_value]['loose_piece'] += row.return_qty

			ocr_data[part_value]['data'][colour]['values'][size]['loose_piece_set'] += row.pack_return_qty
			ocr_data[part_value]['data'][colour]['colour_total']['loose_piece_set'] += row.pack_return_qty
			ocr_data[part_value]['total'][size]['loose_piece_set'] += row.pack_return_qty
			ocr_data[part_value]['loose_piece_set'] += row.pack_return_qty

		part_value = ["Item"]
		if is_set_item:
			part_value = get_part_value(set_attr, ipd)
		for row in self.finishing_plan_grn_details:
			attr_details = get_variant_attr_details(row.item_variant)
			for par in part_value:
				size = attr_details[primary_attr]
				ocr_data[par]['packed_box'] += row.quantity
				ocr_data[par]['packed_box_qty'] += (row.quantity * self.pieces_per_box)
				ocr_data[par]['total'][size]['packed_box'] += row.quantity
				ocr_data[par]['total'][size]['packed_box_qty'] += (row.quantity * self.pieces_per_box)	
		
		for row in self.finishing_plan_reworked_details:
			set_comb = update_if_string_instance(row.set_combination)
			major_colour = set_comb["major_colour"]
			colour = major_colour
			attr_details = get_variant_attr_details(row.item_variant)
			size = attr_details[primary_attr]
			part_value = "Item"
			if is_set_item:
				part_value = attr_details[set_attr]
			part = None
			if is_set_item:
				variant_colour = attr_details[pack_attr]
				part = attr_details[set_attr]
				colour = f"{variant_colour} ({major_colour}) @ "+part
			ocr_data[part_value]['data'][colour]['colour_total']['rejected'] += row.rejected_qty
			ocr_data[part_value]['total'][size]['rejected'] += row.rejected_qty	
			ocr_data[part_value]['data'][colour]['values'][size]['rejected'] += row.rejected_qty
			ocr_data[part_value]['data'][colour]['values'][size]['pending'] += (row.quantity - row.reworked_quantity - row.rejected_qty)
			ocr_data[part_value]['data'][colour]['colour_total']['pending'] += (row.quantity - row.reworked_quantity - row.rejected_qty)
			ocr_data[part_value]['total'][size]['pending'] += (row.quantity - row.reworked_quantity - row.rejected_qty)	
			ocr_data[part_value]['rejected'] += row.rejected_qty
			ocr_data[part_value]['pending'] += (row.quantity - row.reworked_quantity - row.rejected_qty)

		return ocr_data	

	def get_inward_details(self):
		ipd = frappe.get_value("Lot", self.lot, "production_detail")
		ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
		is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)

		inward_details = {"data": {}, "total": {}}
		for item in self.finishing_plan_details:
			set_comb = update_if_string_instance(item.set_combination)
			major_colour = set_comb["major_colour"]
			colour = major_colour
			attr_details = get_variant_attr_details(item.item_variant)
			size = attr_details[primary_attr]
			part = None
			if is_set_item:
				variant_colour = attr_details[pack_attr]
				part = attr_details[set_attr]
				colour = f"{variant_colour} ({major_colour}) @ "+part
			
			inward_details["data"].setdefault(colour, {
				"values": {},
				"colour": attr_details[pack_attr],
				"part": part,
				"colour_total": {
					"accepted": 0, "reworked": 0, "pending": 0, "rejected": 0,
				},
			})
			
			inward_details["data"][colour]["values"].setdefault(size, {
				"accepted": 0, "reworked": 0, "pending": 0, "rejected": 0
			})
			qty = item.accepted_qty + item.lot_transferred + item.ironing_excess
			inward_details["total"].setdefault(size, 0)
			inward_details["data"][colour]["colour_total"]["accepted"] += qty
			inward_details["data"][colour]["values"][size]["accepted"] += qty

		for item in self.finishing_plan_reworked_details:
			set_comb = update_if_string_instance(item.set_combination)
			major_colour = set_comb["major_colour"]
			colour = major_colour
			attr_details = get_variant_attr_details(item.item_variant)
			size = attr_details[primary_attr]
			part = None
			if is_set_item:
				variant_colour = attr_details[pack_attr]
				part = attr_details[set_attr]
				colour = f"{variant_colour} ({major_colour}) @ "+part
			
			inward_details["total"].setdefault(size, 0)
			inward_details["data"][colour]["colour_total"]["reworked"] += item.reworked_quantity
			inward_details["data"][colour]["values"][size]["reworked"] += item.reworked_quantity

			inward_details["data"][colour]["colour_total"]["rejected"] += item.rejected_qty
			inward_details["data"][colour]["values"][size]["rejected"] += item.rejected_qty

			inward_details["data"][colour]["colour_total"]["pending"] += item.quantity - (item.reworked_quantity + item.rejected_qty)
			inward_details["data"][colour]["values"][size]["pending"] += item.quantity - (item.reworked_quantity + item.rejected_qty)

		return inward_details


	def get_packed_qty(self):
		items = [item.as_dict() for item in self.finishing_plan_grn_details]
		box_qty = {}
		for row in items:
			current_variant = frappe.get_cached_doc("Item Variant", row['item_variant'])
			current_item_attribute_details = get_attribute_details(current_variant.item)
			primary_attribute = current_item_attribute_details['primary_attribute']
			for attr in current_variant.attributes:
				if attr.attribute == primary_attribute:
					box_qty.setdefault(attr.attribute_value, {
						"packed": 0,
						"dispatched": 0,
						"cur_dispatch": 0,
					})
					box_qty[attr.attribute_value]['packed'] += row['quantity']
					box_qty[attr.attribute_value]['dispatched'] += row['dispatched']
					break	
		return box_qty

	def get_rework_item_details(self):
		ipd = frappe.get_value("Lot", self.lot, "production_detail")
		ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
		is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)

		finishing_rework = {"data": {}, "total": {}}
		for item in self.finishing_plan_reworked_details:
			set_comb = update_if_string_instance(item.set_combination)
			major_colour = set_comb["major_colour"]
			colour = major_colour
			attr_details = get_variant_attr_details(item.item_variant)
			size = attr_details[primary_attr]
			part = None
			if is_set_item:
				variant_colour = attr_details[pack_attr]
				part = attr_details[set_attr]
				colour = f"{variant_colour} ({major_colour}) @ "+part
			
			finishing_rework["data"].setdefault(colour, {
				"values": {},
				"colour": attr_details[pack_attr],
				"part": part,
				"colour_total": {
					"rework_qty": 0, "reworked": 0, "pending": 0, "rejected": 0,
				},
			})
			
			finishing_rework["data"][colour]["values"].setdefault(size, {
				"rework_qty": 0, "reworked": 0, "pending": 0, "rejected": 0
			})

			finishing_rework["total"].setdefault(size, 0)
			finishing_rework["data"][colour]["colour_total"]["rework_qty"] += item.quantity
			finishing_rework["data"][colour]["colour_total"]["reworked"] += item.reworked_quantity
			finishing_rework["data"][colour]["colour_total"]["pending"] += item.quantity - item.reworked_quantity - item.rejected_qty
			finishing_rework["data"][colour]["colour_total"]["rejected"] += item.rejected_qty
			
			finishing_rework["data"][colour]["values"][size]["rework_qty"] += item.quantity
			finishing_rework["data"][colour]["values"][size]["reworked"] += item.reworked_quantity
			finishing_rework["data"][colour]["values"][size]["pending"] += item.quantity - item.reworked_quantity - item.rejected_qty
			finishing_rework["data"][colour]["values"][size]["rejected"] += item.rejected_qty

		return finishing_rework
	
	def before_save(self):
		finishing_plans = get_finishing_plan_dict(self)
		for key in finishing_plans:
			finishing_plans[key]['reworked'] = 0
			
		for row in self.finishing_plan_reworked_details:
			set_comb = update_if_string_instance(row.set_combination)
			key = (row.item_variant, tuple(sorted(set_comb.items())))
			finishing_plans[key]['reworked'] += row.reworked_quantity

		finshing_items_list = get_finishing_plan_list(finishing_plans)
		self.set("finishing_plan_details", finshing_items_list)

	def get_finishing_plans(self):
		ipd = frappe.get_value("Lot", self.lot, "production_detail")
		ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
		is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)

		finishing_inward = {"data": {}, "total": {}}
		finishing_qty = {"data": {}, "total": {}}
		finishing_ironing = {"data": {}, "total": {}, "total_qty": {
			"ironing": 0
		}}
		finishing_pack_return = {"data": {}, "total": {}, "total_qty": 0}

		for item in self.finishing_plan_details:
			set_comb = update_if_string_instance(item.set_combination)
			major_colour = set_comb["major_colour"]
			colour = major_colour
			attr_details = get_variant_attr_details(item.item_variant)
			size = attr_details[primary_attr]
			part = None

			if is_set_item:
				variant_colour = attr_details[pack_attr]
				part = attr_details[set_attr]
				colour = f"{variant_colour} ({major_colour}) @ "+part
			
			finishing_inward["data"].setdefault(colour, {
				"values": {},
				"part": part,
				"colour": attr_details[pack_attr],
				"set_combination": set_comb,
				"colour_total": {
					"delivered": 0, "received": 0, "cutting": 0, "difference": 0, "cut_sew_diff": 0,
				},
			})
			finishing_qty['data'].setdefault(colour, {
				"values": {},
				"part": part,
				"check_value": True,
				"colour": attr_details[pack_attr],
				"set_combination": set_comb,
				"colour_total": {
					"accepted": 0, "dc_qty": 0, "balance": 0, "balance_dc": 0
				},
			})
			finishing_ironing['data'].setdefault(colour, {
				"values": {},
				"part": part,
				"colour": attr_details[pack_attr],
				"set_combination": set_comb,
				"colour_total": {
					"ironing": 0,
					"ironing_dc": 0,
				},
			})
			finishing_pack_return['data'].setdefault(colour, {
				"values": {},
				"part": part,
				"colour": attr_details[pack_attr],
				"set_combination": set_comb,
				"colour_total": 0,
			})
			
			finishing_inward["data"][colour]["values"].setdefault(size, {
				"delivered": 0, "received": 0, "cutting": 0, "difference": 0, "cut_sew_diff": 0,
			})
			finishing_qty["data"][colour]["values"].setdefault(size, {
				"accepted": 0, "dc_qty": 0, "balance": 0, "balance_dc": 0, "return_qty": 0,
			})
			finishing_ironing["data"][colour]["values"].setdefault(size, {
				"ironing": 0, "ironing_dc": 0, 
			})
			finishing_pack_return["data"][colour]["values"].setdefault(size, {
				"pack_returned_qty": 0,
				"pack_return": 0,
			})

			finishing_inward["total"].setdefault(size, 0)
			finishing_qty["total"].setdefault(size, 0)
			finishing_ironing['total'].setdefault(size, {"ironing": 0})
			finishing_pack_return['total'].setdefault(size, 0)

			finishing_inward["data"][colour]["colour_total"]["cutting"] += item.cutting_qty
			finishing_inward["data"][colour]["colour_total"]["received"] += item.delivered_quantity
			finishing_inward["data"][colour]["colour_total"]["delivered"] += item.inward_quantity
			finishing_inward["data"][colour]["colour_total"]["difference"] += item.delivered_quantity - item.inward_quantity
			finishing_inward["data"][colour]["colour_total"]['cut_sew_diff'] += item.inward_quantity - item.cutting_qty 

			finishing_inward["data"][colour]["values"][size]["received"] += item.delivered_quantity
			finishing_inward["data"][colour]["values"][size]["delivered"] += item.inward_quantity
			finishing_inward["data"][colour]["values"][size]["cutting"] += item.cutting_qty
			finishing_inward["data"][colour]["values"][size]["difference"] += item.delivered_quantity - item.inward_quantity
			finishing_inward["data"][colour]["values"][size]['cut_sew_diff'] += item.inward_quantity - item.cutting_qty 
			finishing_inward["total"][size] += item.delivered_quantity

			qty = item.accepted_qty + item.reworked + item.lot_transferred + item.ironing_excess
			finishing_qty["data"][colour]["colour_total"]["accepted"] += qty
			finishing_qty["data"][colour]["colour_total"]["dc_qty"] += item.dc_qty
			finishing_qty["data"][colour]["colour_total"]["balance"] += qty - item.dc_qty
			finishing_qty["data"][colour]["colour_total"]["balance_dc"] += qty - item.dc_qty
			finishing_qty["data"][colour]["values"][size]["accepted"] += qty
			finishing_qty["data"][colour]["values"][size]["dc_qty"] += item.dc_qty
			finishing_qty["data"][colour]["values"][size]["balance"] += qty - item.dc_qty
			finishing_qty["data"][colour]["values"][size]["balance_dc"] += qty - item.dc_qty

			finishing_ironing['data'][colour]['values'][size]['ironing'] += item.ironing_excess
			finishing_ironing['data'][colour]['colour_total']['ironing'] += item.ironing_excess
			finishing_ironing['total'][size]['ironing'] += item.ironing_excess
			finishing_ironing['total_qty']['ironing'] += item.ironing_excess

			finishing_pack_return['data'][colour]['values'][size]['pack_returned_qty'] += item.pack_return_qty
			finishing_pack_return['data'][colour]['colour_total'] += item.pack_return_qty
			finishing_pack_return['total'][size] += item.pack_return_qty
			finishing_pack_return['total_qty'] += item.pack_return_qty

		primary_values = get_ipd_primary_values(ipd)
		return {
			"primary_values": primary_values,
			"finishing_inward": finishing_inward,
			"finishing_qty": finishing_qty,
			"finishing_ironing": finishing_ironing,
			"is_set_item": is_set_item,
			"set_attr": set_attr,
			"pack_return": finishing_pack_return,
		}

@frappe.whitelist()
def fetch_quantity(doc_name, work_order):
	items = create_finishing_detail(work_order, from_finishing=True)
	doc = frappe.get_doc("Finishing Plan", doc_name)
	doc.set("finishing_plan_details", items[0])
	doc.set("finishing_plan_reworked_details", items[1])
	doc.set("finishing_plan_grn_details", items[2])
	doc.save()

@frappe.whitelist()
def create_delivery_challan(data, item_name, work_order, lot, from_location, vehicle_no):
	data = update_if_string_instance(data)
	dc_doc = frappe.new_doc("Delivery Challan")
	wo_doc = frappe.get_doc("Work Order", work_order)
	dc_doc.work_order = work_order
	dc_doc.lot = lot
	dc_doc.from_location = from_location
	dc_doc.from_address = get_primary_address(from_location)
	dc_doc.vehicle_no = vehicle_no
	dc_doc.supplier = wo_doc.supplier
	dc_doc.supplier_address = get_primary_address(wo_doc.supplier)
	items = []
	ipd = frappe.get_value("Lot", lot, "production_detail")
	delivery_challan_item_list = get_delivery_challan_item_list(lot, item_name, data)
	for item in wo_doc.deliverables:
		item = item.as_dict()
		set_comb = update_if_string_instance(item['set_combination'])
		key = (item['item_variant'], tuple(sorted(set_comb.items())))
		if delivery_challan_item_list.get(key):
			item['delivered_quantity'] = delivery_challan_item_list[key]['qty']
		else:
			item['delivered_quantity'] = 0	
		items.append(item)

	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
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
			"is_set_item": ipd_doc.is_set_item,
			"set_attr": ipd_doc.set_item_attribute,
			"pack_attr": ipd_doc.packing_attribute,
			"major_attr_value": ipd_doc.major_attribute_value,
			"item_keys": {},
			'values': {},
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': None,
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
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
							'set_combination':set_combination,
							'qty': variant['qty'],
							'delivered_quantity': variant['delivered_quantity'],
							'ref_docname': variant['name']
						}
						break
		else:
			item['values']['default'] = {
				'rate': variants[0]['rate'],
				"ref_doctype":"Work Order Deliverables",
				"is_calculated":variants[0].is_calculated,
				'qty': variants[0]['qty'],
				'delivered_quantity': variants[0]['delivered_quantity'],
				'ref_docname': variants[0]['name']
			}
		index = get_item_group_index(item_details, current_item_attribute_details)
		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				"lot": lot,
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details["primary_attribute_values"],
				'dependent_attribute': current_item_attribute_details['dependent_attribute'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)		
	dc_doc.deliverable_item_details = item_details
	dc_doc.from_finishing = 1
	dc_doc.save()
	dc_doc.submit()

def get_delivery_challan_item_list(lot, item_name, data):
	ipd = frappe.get_value("Lot", lot, "production_detail")  # to check if lot exists
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute", "dependent_attribute", "stiching_out_stage"]
	is_set_item, pack_attr, primary_attr, set_attr, dept_attr, stich_out = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	items = {}
	for colour in data['data']['data']:
		colour_value = data['data']['data'][colour]['colour']
		if not data['data']['data'][colour]['check_value']:
			continue
		for size in data['data']['data'][colour]['values']:
			if data['data']['data'][colour]['values'][size]['balance_dc'] > 0:
				attrs = {
					primary_attr: size,
					pack_attr: colour_value,
					dept_attr: stich_out,
				}
				if is_set_item:
					attrs[set_attr] = data['data']['data'][colour]['part']
				item_variant = get_or_create_variant(item_name, attrs)
				set_comb = update_if_string_instance(data['data']['data'][colour]['set_combination'])
				key = (item_variant, tuple(sorted(set_comb.items())))
				items.setdefault(key, {
					"set_combination": set_comb,
					"qty": 0
				})
				items[key]['qty'] += data['data']['data'][colour]['values'][size]['balance_dc']
	return items

@frappe.whitelist()
def create_grn(work_order, lot, item_name, data, delivery_location):
	box_qty = {}
	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_fields = ["primary_item_attribute", "dependent_attribute"]
	primary_attr, dept_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)

	data = update_if_string_instance(data)
	for size in data:
		variant = get_or_create_variant(item_name, {
			primary_attr: size,
			dept_attr: "Loose Piece",
		})
		current_variant = frappe.get_cached_doc("Item Variant", variant)
		current_item_attribute_details = get_attribute_details(current_variant.item)
		primary_attribute = current_item_attribute_details['primary_attribute']
		for attr in current_variant.attributes:
			if attr.attribute == primary_attribute:
				box_qty.setdefault(attr.attribute_value, 0)
				box_qty[attr.attribute_value] += data[size]
				break	
	
	doc = frappe.new_doc("Goods Received Note")
	doc.against = "Work Order"
	doc.against_id = work_order
	doc.lot = lot
	doc.supplier = frappe.get_value("Work Order", work_order, "supplier")
	doc.supplier_address = frappe.get_value("Work Order", work_order, "supplier_address")
	doc.delivery_location = delivery_location
	doc.delivery_address = get_primary_address(delivery_location)
	doc.supplier_document_no = "NA"
	doc.vehicle_no = "NA"
	doc.dc_no = "NA"
	doc.item_details = box_qty
	doc.process_name = frappe.get_value("Work Order", work_order, "process_name")
	doc.from_finishing = 1
	doc.save()
	doc.submit()

@frappe.whitelist()
def return_items(data, work_order, lot, item_name, popup_values, is_pack:bool=False):
	data = update_if_string_instance(data)
	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute", "dependent_attribute", "stiching_out_stage"]
	is_set_item, pack_attr, primary_attr, set_attr, dept_attr, stich_out = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	return_items = {}
	return_key = "return_qty"
	if is_pack:
		return_key = "pack_return"
	row_index = 0
	for colour in data['data']['data']:
		colour_value = data['data']['data'][colour]['colour']
		for size in data['data']['data'][colour]['values']:
			if data['data']['data'][colour]['values'][size][return_key] > 0:
				attrs = {
					primary_attr: size,
					pack_attr: colour_value,
					dept_attr: stich_out,
				}
				if is_set_item:
					attrs[set_attr] = data['data']['data'][colour]['part']
				item_variant = get_or_create_variant(item_name, attrs)
				set_comb = update_if_string_instance(data['data']['data'][colour]['set_combination'])
				key = (item_variant, tuple(sorted(set_comb.items())))
				return_items.setdefault(key, {
					"set_combination": set_comb,
					"return_qty": 0,
					"ref_doctype": "Work Order Deliverables",
					"ref_docname": None,
					"row_index": row_index,
				})
				return_items[key]['return_qty'] += data['data']['data'][colour]['values'][size][return_key]
		row_index += 1

	wo_doc = frappe.get_doc("Work Order", work_order)
	for row in wo_doc.deliverables:
		row = row.as_dict()
		set_comb = update_if_string_instance(row.set_combination)
		key = (row.item_variant, tuple(sorted(set_comb.items())))
		if return_items.get(key):
			return_items[key]['ref_docname'] = row.name

	uom = frappe.get_value("Item", item_name, "default_unit_of_measure")
	popup_values = update_if_string_instance(popup_values)	
	grn_items = []
	for item in return_items:
		variant, tuple_attrs = item
		grn_items.append({
			"item_variant": variant,
			"lot": wo_doc.lot,
			"quantity": return_items[item]['return_qty'],
			"uom": uom,
			"received_type": popup_values.get('received_type'),
			"ref_docname": return_items[item]['ref_docname'],
			"ref_doctype": return_items[item]['ref_doctype'],
			"table_index": 0,
			"row_index": return_items[item]['row_index'],
			"set_combination": return_items[item]['set_combination'],
		})
	new_doc = frappe.new_doc("Goods Received Note")
	new_doc.update({
		"against": "Work Order",
		"is_return": 1,
		"is_rework": 0,
		"includes_packing": wo_doc.includes_packing,
		"against_id": wo_doc.name,
		"lot": wo_doc.lot,
		"process_name": wo_doc.process_name,
		"posting_date": frappe.utils.nowdate(),
		"posting_time": frappe.utils.now(),
		"delivery_date": frappe.utils.nowdate(),
		"is_internal_unit": 0,
		"is_manual_entry": 0,
		"delivery_location": popup_values.get('delivery_location'),
		"supplier": popup_values.get('from_location'),
		"vehicle_no":popup_values.get('vehicle_no'),
		"supplier_document_no":"NA",
		"dc_no": "NA",
		"is_pack": is_pack,
		"supplier_address": get_primary_address(popup_values.get('from_location')),
		"delivery_address": get_primary_address(popup_values.get('delivery_location')),
	})
	new_doc.set("items", grn_items)
	new_doc.save()
	new_doc.from_finishing = 1
	new_doc.submit()

@frappe.whitelist()
def create_stock_entry(data, item_name, doc_name, lot, from_location, to_location, goods_value):
	data = update_if_string_instance(data)
	ipd, uom = frappe.get_value("Lot", lot, ["production_detail", "uom"])
	ipd_fields = ["primary_item_attribute", "dependent_attribute", "pack_out_stage"]
	primary_attr, dept_attr, pack_out = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	default_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	item_list = []
	for size in data:
		variant = get_or_create_variant(item_name, {
			primary_attr: size,
			dept_attr: pack_out
		})
		item_list.append({
			"item": variant,
			"qty": data[size]['cur_dispatch'],
			"lot": lot,
			"received_type": default_type,
			"uom": uom,
			'table_index': 0,
			'row_index': 0,
			'set_combination': {},
		})
	doc = frappe.new_doc("Stock Entry")	
	doc.purpose = "Material Issue"
	doc.against = "Finishing Plan"
	doc.against_id = doc_name
	doc.from_warehouse = from_location
	doc.transfer_supplier = to_location
	from production_api.mrp_stock.doctype.stock_entry.stock_entry import fetch_stock_entry_items
	item_details = fetch_stock_entry_items(item_list, ipd=ipd)
	doc.item_details = item_details
	doc.additional_amount = goods_value
	doc.save()
	doc.submit()
	return doc.name

@frappe.whitelist()
def cancel_document(doctype, docname):
	doc = frappe.get_doc(doctype, docname)
	doc.cancel()

@frappe.whitelist()
def fetch_from_old_lot(lot, item, location):
	from production_api.mrp_stock.report.item_balance.item_balance import execute as get_item_balance
	filters = {
		"remove_zero_balance_item":1,
		"item": item,
		"warehouse": location
	}
	data = get_item_balance(filters)[1]
	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	old_lot_data = {} 
	default_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	for d in data:
		if d['lot'] != lot and d['received_type'] == default_type:
			if pack_stage_variant(d['item_variant'], ipd_doc.dependent_attribute, ipd_doc.pack_in_stage):
				key = (d['lot'], d['warehouse'], d['warehouse_name'])
				old_lot_data.setdefault(key, {})
				old_lot_data[key].setdefault(d['item_variant'], 0)
				old_lot_data[key][d['item_variant']] += d['bal_qty']

	data = []
	primary_values = get_ipd_primary_values(ipd)
	for key in old_lot_data:
		lot_value, warehouse, warehouse_name = key
		old_lot_inward = {"data": {}, "total": {}}
		for variant in old_lot_data[key]:	
			attr_details = get_variant_attr_details(variant)
			size = attr_details[ipd_doc.primary_item_attribute]
			part = None
			colour = attr_details[ipd_doc.packing_attribute]	
			if ipd_doc.is_set_item:
				part = attr_details[ipd_doc.set_item_attribute]

			set_value = None
			if ipd_doc.is_set_item:
				if ipd_doc.major_attribute_value == part:
					set_value = colour
			else:		
				set_value = colour
			old_lot_inward["data"].setdefault(colour, {
				"values": {},
				"part": part,
				"colour": attr_details[ipd_doc.packing_attribute],
				"set_combination": set_value,
				"colour_total": {
					"balance": 0, "transfer": 0
				},
			})
			old_lot_inward["data"][colour]["values"].setdefault(size, {
				"balance": 0, "transfer": 0
			})
			old_lot_inward["total"].setdefault(size, 0)
			qty = old_lot_data[key][variant]
			old_lot_inward["data"][colour]["colour_total"]["balance"] += qty
			old_lot_inward["data"][colour]["values"][size]["balance"] += qty
			old_lot_inward['total'][size] += qty

		data.append({
			"lot": lot_value,
			"warehouse": warehouse,
			"warehouse_name": warehouse_name,
			"primary_values": primary_values,
			"old_lot_inward": old_lot_inward,
			"is_set_item": ipd_doc.is_set_item,
			"set_attr": ipd_doc.set_item_attribute,
		})
	colours = []
	for row in ipd_doc.packing_attribute_details:
		colours.append(row.attribute_value)

	return {
		"data": data,
		"colours": colours
	}	

def pack_stage_variant(variant, dept_attr, pack_in_stage):
	from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import get_variant_attr_details
	attr_details = get_variant_attr_details(variant)
	if attr_details[dept_attr] == pack_in_stage:
		return True
	return False

@frappe.whitelist()
def create_lot_transfer(data, item_name, ipd, lot, doc_name):
	data = update_if_string_instance(data)
	ipd_fields = ["primary_item_attribute", "packing_attribute", "is_set_item", "set_item_attribute", "dependent_attribute", "stiching_out_stage", "major_attribute_value"]
	primary, pack_attr, is_set, set_attr, dept_attr, stich_out, major_part = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	items = []
	row_index = 0
	uom = frappe.get_value("Item", item_name, "default_unit_of_measure")
	received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	for table_index, group in enumerate(data):
		for colour in group['old_lot_inward']['data']:
			for size in group['old_lot_inward']['data'][colour]['values']:
				item_attributes = {
					primary: size,
					pack_attr: colour,
					dept_attr: stich_out
				}
				if is_set:
					item_attributes[set_attr] = group['old_lot_inward']['data'][colour]['part']
				if group['old_lot_inward']['data'][colour]['values'][size]['transfer'] > 0:
					item1 = {}
					variant_name = get_or_create_variant(item_name, item_attributes)
					item1['item'] = variant_name
					item1['from_lot'] = group['lot']
					item1['to_lot'] = lot
					item1['warehouse'] = group['warehouse']
					item1['uom'] = uom
					item1['qty'] = group['old_lot_inward']['data'][colour]['values'][size]['transfer']
					item1['rate'] = 0
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['received_type'] = received_type
					set_comb = {
						"major_colour": group['old_lot_inward']['data'][colour]['set_combination']
					}
					if is_set:
						set_comb['major_part'] = major_part
					item1['set_combination'] = set_comb
					items.append(item1)
			row_index += 1

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
		}
		for attr in current_item_attribute_details['primary_attribute_values']:
			item['values'][attr] = {'qty': 0, 'rate': 0}
		for variant in variants:
			current_variant = frappe.get_doc("Item Variant", variant['item'])
			for attr in current_variant.attributes:
				if attr.attribute == item.get('primary_attribute'):
					item['values'][attr.attribute_value] = {
						'qty': variant.get('qty'),
						'rate': variant.get('rate'),
						"set_combination": variant.get('set_combination'),
					}
					break
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
	doc = frappe.new_doc("Lot Transfer")
	doc.item_details = item_details
	doc.finishing_plan = doc_name
	doc.save()
	doc.submit()

@frappe.whitelist()
def create_material_receipt(data, item_name, lot, ipd, doc_name, location):
	data = update_if_string_instance(data)
	received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	uom = frappe.get_value("Item", item_name, "default_unit_of_measure")
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute", "dependent_attribute", "stiching_out_stage"]
	is_set_item, pack_attr, primary_attr, set_attr, dept_attr, stich_out = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	row_index = -1
	item_list = []
	for colour in data['data']['data']:
		row_index += 1
		for size in data['data']['data'][colour]['values']:
			if not data['data']['data'][colour]['values'][size]['ironing_dc'] > 0:
				continue
			attrs = {
				primary_attr: size,
				pack_attr: data['data']['data'][colour]['colour'],
				dept_attr: stich_out,
			}
			if is_set_item:
				attrs[set_attr] = data['data']['data'][colour]['part']
			item_list.append({
				"item": get_or_create_variant(item_name, attrs),
				"qty": data['data']['data'][colour]['values'][size]['ironing_dc'],
				"lot": lot,
				"received_type": received_type,
				"uom": uom,
				'table_index': 0,
				'row_index': row_index,
				'set_combination': update_if_string_instance(data['data']['data'][colour]['set_combination']),
			})	
	doc = frappe.new_doc("Stock Entry")	
	doc.purpose = "Material Receipt"
	doc.against = "Finishing Plan"
	doc.against_id = doc_name
	doc.to_warehouse = location
	doc.transfer_supplier = location
	from production_api.mrp_stock.doctype.stock_entry.stock_entry import fetch_stock_entry_items
	item_details = fetch_stock_entry_items(item_list, ipd=ipd)
	doc.item_details = item_details
	doc.save()
	doc.submit()

def get_part_value(set_attr, ipd):
	doc = frappe.get_doc("Item Production Detail", ipd)
	mapping = None
	for row in doc.item_attributes:
		if row.attribute == set_attr:
			mapping = row.mapping
			break

	if mapping:
		map_doc = frappe.get_doc("Item Item Attribute Mapping", mapping)	
		values = []
		for row in map_doc.values:
			values.append(row.attribute_value)
		return values	