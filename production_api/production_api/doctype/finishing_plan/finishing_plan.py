# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from itertools import groupby
from frappe.utils import flt
from frappe.model.document import Document
from production_api.production_api.doctype.supplier.supplier import get_primary_address
from production_api.production_api.doctype.item.item import get_or_create_variant, get_attribute_details
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index
from production_api.utils import update_if_string_instance, get_finishing_plan_dict, get_finishing_plan_list, get_variant_attr_details, get_tuple_attributes, get_process_wo_list

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
		ocr_details = get_ocr_details(self)
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
		self.set_onload("finishing_rejection_data", self.get_rejection_details(
			primary_values=data['primary_values'],
			is_set_item=data['is_set_item'],
			set_attr=data['set_attr'],
		))
		if self.finishing_old_lot_items:
			self.set_onload("old_lot_data", _reshape_old_lot_rows_for_ui(self))
		else:
			self.set_onload("old_lot_data", {"data": [], "colours": []})
		primary_values = data['primary_values'] if data else []

		def _build_matrix(rows, counterpart_fp_field, counterpart_lot_field, lp_field, lps_field):
			# group by (fp, lot, colour, part) -> {lp: {size: qty}, lps: {size: qty}, lts: set}
			groups = {}
			for r in rows:
				key = (getattr(r, counterpart_fp_field), getattr(r, counterpart_lot_field), r.colour, r.part or "")
				g = groups.setdefault(key, {
					"fp": getattr(r, counterpart_fp_field),
					"lot": getattr(r, counterpart_lot_field),
					"colour": r.colour,
					"part": r.part,
					"lp": {s: 0 for s in primary_values},
					"lps": {s: 0 for s in primary_values},
					"lts": [],
					"lp_total": 0,
					"lps_total": 0,
				})
				if r.size in g["lp"]:
					g["lp"][r.size] += flt(getattr(r, lp_field))
					g["lps"][r.size] += flt(getattr(r, lps_field))
					g["lp_total"] += flt(getattr(r, lp_field))
					g["lps_total"] += flt(getattr(r, lps_field))
				if r.lot_transfer and r.lot_transfer not in g["lts"]:
					g["lts"].append(r.lot_transfer)
			return list(groups.values())

		self.set_onload("old_lot_given_matrix", {
			"primary_values": primary_values,
			"groups": _build_matrix(
				self.get("finishing_old_lot_given_items") or [],
				"destination_fp", "destination_lot",
				"loose_piece_given", "loose_piece_set_given",
			),
		})
		self.set_onload("old_lot_received_matrix", {
			"primary_values": primary_values,
			"groups": _build_matrix(
				self.get("finishing_old_lot_received_items") or [],
				"source_fp", "source_lot",
				"loose_piece_taken", "loose_piece_set_taken",
			),
		})

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
		box_qty = {
			"sizes": {},
			"total_packed": 0,
			"total_dispatched": 0
		}
		for row in items:
			current_variant = frappe.get_cached_doc("Item Variant", row['item_variant'])
			current_item_attribute_details = get_attribute_details(current_variant.item)
			primary_attribute = current_item_attribute_details['primary_attribute']
			for attr in current_variant.attributes:
				if attr.attribute == primary_attribute:
					box_qty['sizes'].setdefault(attr.attribute_value, {
						"packed": 0,
						"dispatched": 0,
						"cur_dispatch": 0,
					})
					box_qty['sizes'][attr.attribute_value]['packed'] += row['quantity']
					box_qty['sizes'][attr.attribute_value]['dispatched'] += row['dispatched']
					box_qty['total_packed'] += row['quantity']
					box_qty['total_dispatched'] += row['dispatched']
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

	def get_rejection_details(self, primary_values=None, is_set_item=None, set_attr=None):
		ipd = frappe.get_value("Lot", self.lot, "production_detail")
		ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
		ipd_is_set_item, pack_attr, primary_attr, ipd_set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)
		if is_set_item is None:
			is_set_item = ipd_is_set_item
		if set_attr is None:
			set_attr = ipd_set_attr
		if primary_values is None:
			primary_values = get_ipd_primary_values(ipd)

		rework_item_names = frappe.get_all(
			"GRN Rework Item", filters={"lot": self.lot}, pluck="name"
		)

		data = {}
		grand_rejection_total = 0

		for name in rework_item_names:
			doc = frappe.get_doc("GRN Rework Item", name)
			for row in doc.grn_rework_item_details:
				rework_qty = row.quantity or 0
				rejection_qty = row.rejection or 0
				if rework_qty == 0 and rejection_qty == 0:
					continue

				received_type = row.received_type or "Unspecified"

				set_comb = update_if_string_instance(row.set_combination)
				if not isinstance(set_comb, dict):
					set_comb = {}
				major_colour = set_comb.get("major_colour", "")
				attr_details = get_variant_attr_details(row.item_variant)
				size = attr_details.get(primary_attr)
				part = None
				if is_set_item:
					variant_colour = attr_details.get(pack_attr, "")
					part = attr_details.get(set_attr)
					colour = f"{variant_colour} ({major_colour}) @ " + (part or "")
				else:
					colour = major_colour or attr_details.get(pack_attr, "")

				data.setdefault(received_type, {})
				data[received_type].setdefault(colour, {
					"part": part,
					"rework": {"values": {}, "total": 0},
					"rejection": {"values": {}, "total": 0},
				})
				block = data[received_type][colour]
				block["rework"]["values"].setdefault(size, 0)
				block["rework"]["values"][size] += rework_qty
				block["rework"]["total"] += rework_qty

				block["rejection"]["values"].setdefault(size, 0)
				block["rejection"]["values"][size] += rejection_qty
				block["rejection"]["total"] += rejection_qty

				grand_rejection_total += rejection_qty

		return {
			"primary_values": primary_values,
			"data": data,
			"grand_rejection_total": grand_rejection_total,
			"is_set_item": is_set_item,
			"set_attr": set_attr,
		}

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

		finishing_inward = {"data": {}, "total": {}, "over_all": {}}
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
					"accepted": 0, "dc_qty": 0, "balance": 0, "balance_dc": 0, "return_qty": 0, "pack_return": 0,
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
				"accepted": 0, "dc_qty": 0, "balance": 0, "balance_dc": 0, "return_qty": 0, "pack_return": 0,
			})
			finishing_ironing["data"][colour]["values"].setdefault(size, {
				"ironing": 0, "ironing_dc": 0, 
			})
			finishing_pack_return["data"][colour]["values"].setdefault(size, {
				"pack_returned_qty": 0,
				"pack_return": 0,
			})
			if not part:
				part = "item"
			finishing_inward["total"].setdefault(part, {})
			finishing_inward['over_all'].setdefault(part, {
				"cutting": 0, "received": 0, "delivered": 0, "difference": 0, "cut_sew_diff": 0,
			})
			finishing_inward["total"][part].setdefault(size, {
				"cutting": 0, "received": 0, "delivered": 0, "difference": 0, "cut_sew_diff": 0,
			})
			finishing_qty["total"].setdefault(size, 0)
			finishing_ironing['total'].setdefault(size, {"ironing": 0})
			finishing_pack_return['total'].setdefault(size, 0)

			finishing_inward["data"][colour]["colour_total"]["cutting"] += item.cutting_qty
			finishing_inward["data"][colour]["colour_total"]["received"] += item.delivered_quantity
			finishing_inward["data"][colour]["colour_total"]["delivered"] += item.inward_quantity
			finishing_inward["data"][colour]["colour_total"]["difference"] += item.delivered_quantity - item.inward_quantity
			finishing_inward["data"][colour]["colour_total"]['cut_sew_diff'] += item.inward_quantity - item.cutting_qty 
			finishing_inward['total'][part][size]['delivered'] += item.inward_quantity
			finishing_inward['total'][part][size]['received'] += item.delivered_quantity
			finishing_inward['total'][part][size]['cutting'] += item.cutting_qty
			finishing_inward['total'][part][size]['difference'] += item.delivered_quantity - item.inward_quantity
			finishing_inward['total'][part][size]['cut_sew_diff'] += item.inward_quantity - item.cutting_qty  
			finishing_inward['over_all'][part]['delivered'] += item.inward_quantity
			finishing_inward['over_all'][part]['received'] += item.delivered_quantity
			finishing_inward['over_all'][part]['cutting'] += item.cutting_qty
			finishing_inward['over_all'][part]['difference'] += item.delivered_quantity - item.inward_quantity
			finishing_inward['over_all'][part]['cut_sew_diff'] += item.inward_quantity - item.cutting_qty
			finishing_inward["data"][colour]["values"][size]["received"] += item.delivered_quantity
			finishing_inward["data"][colour]["values"][size]["delivered"] += item.inward_quantity
			finishing_inward["data"][colour]["values"][size]["cutting"] += item.cutting_qty
			finishing_inward["data"][colour]["values"][size]["difference"] += item.delivered_quantity - item.inward_quantity
			finishing_inward["data"][colour]["values"][size]['cut_sew_diff'] += item.inward_quantity - item.cutting_qty 

			qty = item.accepted_qty + item.reworked + item.lot_transferred + item.ironing_excess
			finishing_qty["data"][colour]["colour_total"]["accepted"] += qty
			finishing_qty["data"][colour]["colour_total"]["dc_qty"] += item.dc_qty
			finishing_qty["data"][colour]["colour_total"]["balance"] += qty - item.dc_qty - item.return_qty - item.pack_return_qty
			finishing_qty["data"][colour]["colour_total"]["balance_dc"] += qty - item.dc_qty - item.return_qty - item.pack_return_qty
			finishing_qty["data"][colour]["colour_total"]['return_qty'] += item.return_qty
			finishing_qty["data"][colour]["colour_total"]['pack_return'] += item.pack_return_qty
			finishing_qty["data"][colour]["values"][size]["accepted"] += qty
			finishing_qty["data"][colour]["values"][size]["dc_qty"] += item.dc_qty
			finishing_qty["data"][colour]["values"][size]["balance"] += qty - item.dc_qty - item.return_qty - item.pack_return_qty
			finishing_qty["data"][colour]["values"][size]["balance_dc"] += qty - item.dc_qty - item.return_qty - item.pack_return_qty
			finishing_qty["data"][colour]["values"][size]['return_qty'] += item.return_qty
			finishing_qty["data"][colour]["values"][size]['pack_return'] += item.pack_return_qty

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
def get_fp_ocr_details(doc_name):
	doc = frappe.get_doc("Finishing Plan", doc_name)
	primary_values = get_ipd_primary_values(doc.production_detail)
	ocr_data = get_ocr_details(doc)
	d = {
		"get_total_difference": {},
		"get_total": {},
		"get_ocr_value": {},
		"get_cut_to_dispatch": {},
		"get_cut_to_inward": {},
		"get_inward_to_dispatch": {},
		"get_loose_piece": {},
		"get_rejection": {},
		"get_rework": {},
		"get_not_received": {},
		"get_unaccountable": {},
		"get_order_to_dispatch": {},
	}
	def get_total(part_value, ocr_data):
		return ((ocr_data[part_value]['packed_box_qty'] +
			ocr_data[part_value]['rejected'] + 
			ocr_data[part_value]['loose_piece_set'] +
			ocr_data[part_value]['loose_piece'] +
			ocr_data[part_value]['pending']) -
			(ocr_data[part_value]['sewing_received'] +
			ocr_data[part_value]['old_lot'] + 
			ocr_data[part_value]['ironing_excess']))
		
	def get_cut_to_dispatch(part_value, ocr_data):
		return {
			"val1": ocr_data[part_value]['cutting'] + 
					ocr_data[part_value]['old_lot'] + 
					ocr_data[part_value]['ironing_excess'] - 
					ocr_data[part_value]['transferred'] ,
			"val2": ocr_data[part_value]['dispatched_piece'],
		}
	
	def get_cut_to_inward(part_value, ocr_data):
		return {
			"val1": ocr_data[part_value]['cutting'],
			"val2": ocr_data[part_value]['sewing_received'],
		}

	def get_inward_to_dispatch(part_value, ocr_data):
		return {
			"val1": ocr_data[part_value]['sewing_received'] +
					ocr_data[part_value]['old_lot'] + 
					ocr_data[part_value]['ironing_excess'] - 
					ocr_data[part_value]['transferred'] , 
			"val2": ocr_data[part_value]['dispatched_piece']
		}
	
	def get_loose_piece(part_value, ocr_data):
		return {
			"val1": ocr_data[part_value]['cutting'] +
					ocr_data[part_value]['old_lot'] + 
					ocr_data[part_value]['ironing_excess'], 
			"val2": ocr_data[part_value]['loose_piece'] +
					ocr_data[part_value]['loose_piece_set'], 
		}
	
	def get_rejection(part_value, ocr_data):
		return {
			"val1": ocr_data[part_value]['cutting'] +
					ocr_data[part_value]['old_lot'] + 
					ocr_data[part_value]['ironing_excess'], 
			"val2": ocr_data[part_value]['rejected'],
		}

	def get_rework(part_value, ocr_data):
		return {
			"val1": ocr_data[part_value]['cutting'] +
					ocr_data[part_value]['old_lot'] + 
					ocr_data[part_value]['ironing_excess'], 
			"val2": ocr_data[part_value]['pending']
		}

	def get_not_received(part_value, ocr_data):
		return {
			"val1": ocr_data[part_value]['cutting'] +
					ocr_data[part_value]['old_lot'] + 
					ocr_data[part_value]['ironing_excess'],
			"val2": ocr_data[part_value]['sewing_received'] - ocr_data[part_value]['cutting']
		}

	def get_order_to_dispatch(part_value, ocr_data):
		return {
			"val1": ocr_data[part_value].get('order_qty', 0),
			"val2": ocr_data[part_value]['dispatched_piece'],
		}

	def get_unaccountable(part_value, ocr_data):
		return {
			"val1": ocr_data[part_value]['cutting'] +
					ocr_data[part_value]['old_lot'] + 
					ocr_data[part_value]['ironing_excess'],
			"val2": ocr_data[part_value]['sewing_received'] +
					ocr_data[part_value]['old_lot'] + 
					ocr_data[part_value]['ironing_excess'] -
					(ocr_data[part_value]['dispatched_piece'] + 
					ocr_data[part_value]['rejected'] + 
					ocr_data[part_value]['loose_piece_set'] +
					ocr_data[part_value]['loose_piece'] +
					ocr_data[part_value]['pending'] +
					ocr_data[part_value]['transferred'])
		}
	
	def get_total_difference(part_value, size, ocr_data):
		return  ((ocr_data[part_value]['total'][size]['packed_box_qty'] + 
				ocr_data[part_value]['total'][size]['rejected'] + 
				ocr_data[part_value]['total'][size]['loose_piece_set'] +
				ocr_data[part_value]['total'][size]['loose_piece'] +
				ocr_data[part_value]['total'][size]['pending']) - 
				(ocr_data[part_value]['total'][size]['sewing_received'] +
				ocr_data[part_value]['total'][size]['old_lot'] + 
				ocr_data[part_value]['total'][size]['ironing_excess']))
	
	def get_ocr_value(part_value, ocr_data):
		return round(
			get_ocr_percentage(get_cut_to_dispatch(part_value, ocr_data)) +
			get_ocr_percentage(get_loose_piece(part_value, ocr_data)) +
			get_ocr_percentage(get_rejection(part_value, ocr_data)) +
			get_ocr_percentage(get_rework(part_value, ocr_data)) +
			get_ocr_percentage(get_not_received(part_value, ocr_data), make_pos=True)
		, 2)

	for part_value in ocr_data:
		d["get_total"].setdefault(part_value, get_total(part_value, ocr_data))
		d["get_ocr_value"].setdefault(part_value, get_ocr_value(part_value, ocr_data))
		d["get_cut_to_dispatch"].setdefault(part_value, get_cut_to_dispatch(part_value, ocr_data))
		d["get_cut_to_inward"].setdefault(part_value, get_cut_to_inward(part_value, ocr_data))
		d["get_inward_to_dispatch"].setdefault(part_value, get_inward_to_dispatch(part_value, ocr_data))
		d["get_loose_piece"].setdefault(part_value, get_loose_piece(part_value, ocr_data))
		d["get_rejection"].setdefault(part_value, get_rejection(part_value, ocr_data))
		d["get_rework"].setdefault(part_value, get_rework(part_value, ocr_data))
		d["get_not_received"].setdefault(part_value, get_not_received(part_value, ocr_data))
		d["get_unaccountable"].setdefault(part_value, get_unaccountable(part_value, ocr_data))
		d["get_order_to_dispatch"].setdefault(part_value, get_order_to_dispatch(part_value, ocr_data))
		d['get_total_difference'].setdefault(part_value, {})
		for colour in ocr_data[part_value]['data']:
			for size in ocr_data[part_value]['data'][colour]['values']:
				d['get_total_difference'][part_value].setdefault(size, 0)
				d['get_total_difference'][part_value][size] = get_total_difference(part_value, size, ocr_data)
			break	

	return ocr_data, d, primary_values

def get_ocr_details(doc):
	ipd = frappe.get_value("Lot", doc.lot, "production_detail")
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute"]
	is_set_item, pack_attr, primary_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	ocr_data = {}
	for row in doc.finishing_plan_details:
		attr_details = get_variant_attr_details(row.item_variant)
		part_value = "Item"
		if is_set_item:
			part_value = attr_details[set_attr]

		ocr_data.setdefault(part_value, {
			"data": {},
			"total": {},
			"cutting": 0,
			"dc_qty": 0,
			"transferred": 0,
			"packed_box": 0,
			"packed_box_qty": 0,
			"dispatched_box": 0,
			"dispatched_piece": 0,
			"rejected": 0,
			"loose_piece": 0,
			"loose_piece_set": 0,
			"pending": 0,
			"sewing_received": 0,
			"old_lot": 0,
			"ironing_excess": 0,
			"total_inward": 0,
			"order_qty": 0,
		})
		size = attr_details[primary_attr]
		ocr_data[part_value]['total'].setdefault(size, {
			"cutting_qty": 0,
			"dc_qty": 0,
			"transferred": 0,
			"packed_box": 0,
			"packed_box_qty": 0,
			"dispatched_box": 0,
			"dispatched_piece": 0,
			"rejected": 0,
			"loose_piece": 0,
			"loose_piece_set": 0,
			"pending": 0,
			"sewing_received": 0,
			"old_lot": 0,
			"ironing_excess": 0,
			"total_inward": 0,
			"order_qty": 0,
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
		ocr_data[part_value]['dc_qty'] += row.dc_qty 
		ocr_data[part_value]['transferred'] += row.transferred_qty
		ocr_data[part_value]['total'][size]['cutting_qty'] += row.cutting_qty
		ocr_data[part_value]['total'][size]['dc_qty'] += row.dc_qty 
		ocr_data[part_value]['total'][size]['transferred'] += row.transferred_qty 
		ocr_data[part_value]['total'][size]['ironing_excess'] += row.ironing_excess
		ocr_data[part_value]['total'][size]['old_lot'] += row.lot_transferred
		ocr_data[part_value]['total'][size]['total_inward'] += row.delivered_quantity + row.ironing_excess + row.lot_transferred
		ocr_data[part_value]['old_lot'] += row.lot_transferred
		ocr_data[part_value]['ironing_excess'] += row.ironing_excess
		ocr_data[part_value]['total_inward'] += row.delivered_quantity + row.ironing_excess + row.lot_transferred

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

		ocr_data[part_value]['data'][colour]['values'][size]['rejected'] += row.rejected_qty
		ocr_data[part_value]['data'][colour]['colour_total']['rejected'] += row.rejected_qty
		ocr_data[part_value]['total'][size]['rejected'] += row.rejected_qty
		ocr_data[part_value]['rejected'] += row.rejected_qty

	part_value = ["Item"]
	if is_set_item:
		part_value = get_part_value(set_attr, ipd)
	for row in doc.finishing_plan_grn_details:
		attr_details = get_variant_attr_details(row.item_variant)
		for par in part_value:
			size = attr_details[primary_attr]
			ocr_data[par]['packed_box'] += row.quantity
			ocr_data[par]['packed_box_qty'] += (row.quantity * doc.pieces_per_box)
			ocr_data[par]['total'][size]['packed_box'] += row.quantity
			ocr_data[par]['total'][size]['packed_box_qty'] += (row.quantity * doc.pieces_per_box)
			ocr_data[par]['dispatched_box'] += row.dispatched
			ocr_data[par]['dispatched_piece'] += (row.dispatched * doc.pieces_per_box)
			ocr_data[par]['total'][size]['dispatched_box'] += row.dispatched
			ocr_data[par]['total'][size]['dispatched_piece'] += (row.dispatched * doc.pieces_per_box)	
	
	major_part = frappe.db.get_value("Item Production Detail", ipd, "major_attribute_value") if is_set_item else None

	def _colour_key(attr_details, set_combination_str, part):
		colour = attr_details.get(pack_attr)
		if is_set_item and part != major_part:
			set_comb = update_if_string_instance(set_combination_str) or {}
			major_col = set_comb.get("major_colour") if isinstance(set_comb, dict) else None
			if major_col:
				colour = f"{colour} ({major_col})"
		return colour

	def _bump_loose(part_key, colour, size, lp_delta, lps_delta):
		if part_key not in ocr_data:
			return
		if colour not in ocr_data[part_key]['data']:
			return
		if size not in ocr_data[part_key]['data'][colour]['values']:
			return
		cell = ocr_data[part_key]['data'][colour]['values'][size]
		cell['loose_piece'] += lp_delta
		cell['loose_piece_set'] += lps_delta
		ocr_data[part_key]['data'][colour]['colour_total']['loose_piece'] += lp_delta
		ocr_data[part_key]['data'][colour]['colour_total']['loose_piece_set'] += lps_delta
		ocr_data[part_key]['total'][size]['loose_piece'] += lp_delta
		ocr_data[part_key]['total'][size]['loose_piece_set'] += lps_delta
		ocr_data[part_key]['loose_piece'] += lp_delta
		ocr_data[part_key]['loose_piece_set'] += lps_delta

	# GIVEN transfers out -> subtract from source FP's loose counts
	for g in doc.get("finishing_old_lot_given_items") or []:
		if not g.item_variant:
			continue
		attr_details = get_variant_attr_details(g.item_variant)
		size_g = attr_details.get(primary_attr)
		part_g = attr_details.get(set_attr) if is_set_item else "Item"
		colour_g = _colour_key(attr_details, g.set_combination, part_g)
		_bump_loose(part_g, colour_g, size_g, -flt(g.loose_piece_given), -flt(g.loose_piece_set_given))

	# RECEIVED transfers in -> add to destination FP's loose counts
	for t in doc.get("finishing_old_lot_received_items") or []:
		if not t.item_variant:
			continue
		attr_details = get_variant_attr_details(t.item_variant)
		size_t = attr_details.get(primary_attr)
		part_t = attr_details.get(set_attr) if is_set_item else "Item"
		colour_t = _colour_key(attr_details, t.set_combination, part_t)
		_bump_loose(part_t, colour_t, size_t, flt(t.loose_piece_taken), flt(t.loose_piece_set_taken))

	for row in doc.finishing_plan_reworked_details:
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

	lot_doc = frappe.get_cached_doc("Lot", doc.lot)
	for row in lot_doc.lot_order_details:
		if not row.item_variant:
			continue
		attr_details = get_variant_attr_details(row.item_variant)
		size = attr_details.get(primary_attr)
		part_key = "Item"
		if is_set_item:
			part_key = attr_details.get(set_attr)
		if part_key not in ocr_data:
			continue
		ocr_data[part_key]['total'].setdefault(size, {
			"cutting_qty": 0, "dc_qty": 0, "transferred": 0, "packed_box": 0,
			"packed_box_qty": 0, "dispatched_box": 0, "dispatched_piece": 0,
			"rejected": 0, "loose_piece": 0, "loose_piece_set": 0,
			"pending": 0, "sewing_received": 0, "old_lot": 0,
			"ironing_excess": 0, "total_inward": 0, "order_qty": 0,
		})
		ocr_data[part_key]['order_qty'] += flt(row.quantity)
		ocr_data[part_key]['total'][size]['order_qty'] += flt(row.quantity)

	return ocr_data


@frappe.whitelist()
def get_fp_consumption_details(doc_name):
	doc = frappe.get_doc("Finishing Plan", doc_name)
	if not doc.lot:
		return {"lot": doc.lot, "processes": []}

	from production_api.production_api.report.jobwork_issued_items.jobwork_issued_items import (
		get_data as get_jobwork_issued_items,
	)

	filters = frappe._dict({"lot": doc.lot})
	default_received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	rows = []
	for row in get_jobwork_issued_items(filters):
		row = frappe._dict(row)
		if row.get("item") == doc.item:
			continue
		if not row.get("received_type"):
			row.received_type = default_received_type
		row.source_report = "Jobwork"
		rows.append(row)

	rows.extend(_get_fp_grn_deduction_rows(doc))

	return {
		"lot": doc.lot,
		"processes": _group_fp_item_rows(
			rows,
			group_field="process",
			default_group="Non Process",
			merge_received_type=True,
			clamp_negative=True,
			remove_zero_items=True,
		),
	}


def _get_fp_grn_deduction_rows(doc):
	if not doc.work_order:
		return []

	params = {
		"lot": doc.lot,
		"work_order": doc.work_order,
		"fp_item": doc.item,
	}
	conditions = [
		"grn.docstatus = 1",
		"gri.docstatus = 1",
		"grn.against = 'Work Order'",
		"grn.against_id = %(work_order)s",
		"(grn.lot = %(lot)s OR gri.lot = %(lot)s)",
		"IFNULL(gri.quantity, 0) > 0",
	]
	if doc.item:
		conditions.append("(iv.item IS NULL OR iv.item != %(fp_item)s)")

	query = """
		SELECT
			'Work Order' AS against,
			grn.against_id AS against_id,
			'Goods Received Note' AS source_doctype,
			grn.name AS source_name,
			COALESCE(gri.lot, grn.lot) AS lot,
			COALESCE(grn.process_name, wo.process_name) AS process,
			iv.item AS item,
			gri.item_variant AS item_variant,
			-gri.quantity AS quantity,
			gri.received_type AS received_type,
			gri.comments AS remarks,
			grn.posting_date AS posting_date,
			grn.posting_time AS posting_time
		FROM `tabGoods Received Note Item` gri
		INNER JOIN `tabGoods Received Note` grn ON grn.name = gri.parent
		LEFT JOIN `tabWork Order` wo ON wo.name = grn.against_id
		LEFT JOIN `tabItem Variant` iv ON iv.name = gri.item_variant
		WHERE {conditions}
	""".format(conditions=" AND ".join(conditions))

	rows = frappe.db.sql(query, params, as_dict=True)
	for row in rows:
		row.source_report = "GRN"
		row.is_grn_deduction = 1
	return rows


def _group_fp_item_rows(
	rows,
	group_field,
	default_group=None,
	group_name_field=None,
	item_key_fields=None,
	merge_received_type=False,
	clamp_negative=False,
	remove_zero_items=False,
):
	group_map = {}
	variant_cache = {}
	item_attribute_cache = {}
	item_key_fields = tuple(item_key_fields or [])

	for row in rows:
		if not row.get("item_variant"):
			continue

		group_value = row.get(group_field) or default_group or ""
		top_group = group_map.setdefault(group_value, {
			group_field: group_value,
			"groups": [],
			"_group_index": {},
		})
		if group_name_field:
			top_group[group_name_field] = row.get(group_name_field) or group_value

		variant = variant_cache.get(row.item_variant)
		if not variant:
			variant = frappe.get_cached_doc("Item Variant", row.item_variant)
			variant_cache[row.item_variant] = variant

		item_name = row.get("item") or variant.item
		item_attribute_details = item_attribute_cache.get(item_name)
		if not item_attribute_details:
			item_attribute_details = get_attribute_details(item_name)
			item_attribute_cache[item_name] = item_attribute_details

		attributes = get_item_attribute_details(variant, item_attribute_details)
		attribute_names = item_attribute_details.get("attributes") or []
		primary_attribute = item_attribute_details.get("primary_attribute")
		primary_values = list(item_attribute_details.get("primary_attribute_values") or [])
		primary_value = _get_primary_attribute_value(variant, primary_attribute)

		group_key = (
			primary_attribute or "",
			tuple(attribute_names),
		)
		group = top_group["_group_index"].get(group_key)
		if not group:
			group = {
				"attributes": attribute_names,
				"primary_attribute": primary_attribute,
				"primary_attribute_values": primary_values,
				"items": [],
				"total_details": {value: 0 for value in primary_values} if primary_attribute else {"default": 0},
				"overall_total": 0,
				"_item_index": {},
			}
			top_group["_group_index"][group_key] = group
			top_group["groups"].append(group)

		if primary_attribute and primary_value and primary_value not in group["primary_attribute_values"]:
			group["primary_attribute_values"].append(primary_value)
			group["total_details"][primary_value] = 0
			for item in group["items"]:
				item["values"][primary_value] = {"quantity": 0, "sources": []}

		row_key = (
			item_name,
			*(row.get(field) or "" for field in item_key_fields),
			tuple((attribute, attributes.get(attribute)) for attribute in attribute_names),
		)
		item = group["_item_index"].get(row_key)
		if not item:
			item = {
				"source_report": row.get("source_report"),
				"item": item_name,
				"attributes": attributes,
				"received_type": row.get("received_type") if "received_type" in item_key_fields else None,
				"stock_uom": row.get("stock_uom"),
				"values": {},
				"total_quantity": 0,
			}
			if primary_attribute:
				for value in group["primary_attribute_values"]:
					item["values"][value] = {"quantity": 0, "sources": []}
			else:
				item["values"]["default"] = {"quantity": 0, "sources": []}
			group["_item_index"][row_key] = item
			group["items"].append(item)

		if merge_received_type and not row.get("is_grn_deduction"):
			_update_fp_consumption_received_type(item, row.get("received_type"))

		value_key = primary_value if primary_attribute else "default"
		if primary_attribute and not value_key:
			continue

		quantity = flt(row.get("quantity"))
		source = {
			"source_doctype": row.get("source_doctype"),
			"source_name": row.get("source_name"),
		}
		item["values"][value_key]["quantity"] += quantity
		item["values"][value_key]["sources"].append(source)
		item["total_quantity"] += quantity

	grouped_rows = list(group_map.values())
	for top_group in grouped_rows:
		top_group["groups"].sort(key=lambda group: group.get("primary_attribute") or "")
		for group in top_group["groups"]:
			_recalculate_fp_item_group_totals(
				group,
				clamp_negative=clamp_negative,
				remove_zero_items=remove_zero_items,
			)
			group["items"].sort(key=lambda item: (item.get("item") or "", item.get("received_type") or ""))
			group.pop("_item_index", None)
		top_group["groups"] = [group for group in top_group["groups"] if group.get("items")]
		top_group.pop("_group_index", None)

	grouped_rows = [top_group for top_group in grouped_rows if top_group.get("groups")]
	if group_field == "process":
		grouped_rows.sort(key=lambda row: (row[group_field] == "Non Process", row[group_field]))
	elif group_name_field:
		grouped_rows.sort(key=lambda row: (row.get(group_name_field) or "", row.get(group_field) or ""))
	else:
		grouped_rows.sort(key=lambda row: row.get(group_field) or "")
	return grouped_rows


def _update_fp_consumption_received_type(item, received_type):
	if not received_type:
		return
	if not item.get("received_type"):
		item["received_type"] = received_type
		return

	received_types = [value.strip() for value in item["received_type"].split(",") if value.strip()]
	if received_type not in received_types:
		received_types.append(received_type)
	item["received_type"] = ", ".join(received_types)


def _recalculate_fp_item_group_totals(group, clamp_negative=False, remove_zero_items=False):
	total_details = {value: 0 for value in group.get("primary_attribute_values") or []}
	if not group.get("primary_attribute"):
		total_details = {"default": 0}

	items = []
	for item in group.get("items") or []:
		total_quantity = 0
		for value_key, value in (item.get("values") or {}).items():
			quantity = flt(value.get("quantity"))
			if clamp_negative:
				quantity = max(quantity, 0)
			value["quantity"] = quantity
			total_quantity += quantity
			total_details.setdefault(value_key, 0)
			total_details[value_key] += quantity

		item["total_quantity"] = total_quantity
		if not remove_zero_items or total_quantity:
			items.append(item)

	group["items"] = items
	group["total_details"] = total_details
	group["overall_total"] = sum(total_details.values())


def _get_primary_attribute_value(variant, primary_attribute):
	if not primary_attribute:
		return None
	for attr in variant.attributes:
		if attr.attribute == primary_attribute:
			return attr.attribute_value
	return None


@frappe.whitelist()
def get_fp_stock_balance_details(doc_name):
	doc = frappe.get_doc("Finishing Plan", doc_name)
	if not doc.lot:
		return {"lot": doc.lot, "warehouses": []}

	from production_api.mrp_stock.report.item_balance.item_balance import get_data as get_item_balance

	rows = []
	for row in get_item_balance(frappe._dict({
		"lot": doc.lot,
		"remove_zero_balance_item": 1,
	})):
		row = frappe._dict(row)
		if row.get("item") == doc.item:
			continue
		if not flt(row.get("bal_qty")):
			continue
		row.quantity = row.bal_qty
		rows.append(row)

	return {
		"lot": doc.lot,
		"warehouses": _group_fp_item_rows(
			rows,
			group_field="warehouse",
			group_name_field="warehouse_name",
			item_key_fields=("received_type", "stock_uom"),
		),
	}


@frappe.whitelist()
def fetch_rejected_quantity(doc_name):
	fp_doc = frappe.get_doc("Finishing Plan", doc_name)
	rework_item_list = frappe.get_all("GRN Rework Item", filters={
		"lot": fp_doc.lot
	}, pluck="name")
	finishing_rework_items = {}

	for rework_item in rework_item_list:
		doc = frappe.get_doc("GRN Rework Item", rework_item)
		for row in doc.grn_rework_item_details:
			if row.quantity == 0:
				continue
			set_comb = update_if_string_instance(row.set_combination)
			set_comb = update_if_string_instance(set_comb)
			key = (row.item_variant, tuple(sorted(set_comb.items())))
			finishing_rework_items.setdefault(key, {
				"item_variant": row.item_variant,
				"quantity": 0,
				"reworked_quantity": 0,
				"rejected_qty": 0,
				"set_combination": frappe.json.dumps(set_comb),
			})
			finishing_rework_items[key]['quantity'] += row.quantity
			if row.completed:
				finishing_rework_items[key]['rejected_qty'] += row.rejection

		for row in doc.grn_reworked_item_details:
			if row.quantity == 0:
				continue
			set_comb = update_if_string_instance(row.set_combination)
			set_comb = update_if_string_instance(set_comb)
			key = (row.item_variant, tuple(sorted(set_comb.items())))
			finishing_rework_items.setdefault(key, {
				"item_variant": row.item_variant,
				"quantity": 0,
				"reworked_quantity": 0,
				"rejected_qty": 0,
				"set_combination": frappe.json.dumps(set_comb),
			})
			finishing_rework_items[key]['reworked_quantity'] += row.quantity

	rework_list = []
	for key in finishing_rework_items:
		rework_list.append(finishing_rework_items[key])
	fp_doc.set("finishing_plan_reworked_details", rework_list)
	
	wo_list = frappe.get_all("Work Order", filters={
		"docstatus": 1,
		"lot": fp_doc.lot,
		"process_name": "Cutting",
	}, pluck="name")

	cut_key_dict = {} 
	for wo in wo_list:
		wo_doc = frappe.get_doc("Work Order", wo)
		for row in wo_doc.work_order_calculated_items:
			if row.received_qty > 0:
				set_comb = update_if_string_instance(row.set_combination)
				key = (row.item_variant, tuple(sorted(set_comb.items())))
				if cut_key_dict.get(key):
					cut_key_dict[key] += row.received_qty
				else:
					cut_key_dict[key] = row.received_qty

	for row in fp_doc.finishing_plan_details:
		set_comb = update_if_string_instance(row.set_combination)
		key = (row.item_variant, tuple(sorted(set_comb.items())))
		row.reworked = finishing_rework_items[key]['reworked_quantity'] if finishing_rework_items.get(key) else 0
		if cut_key_dict.get(key):
			row.cutting_qty = cut_key_dict[key]

	fp_doc.save()	

@frappe.whitelist()
def create_delivery_challan(data, item_name, work_order, lot, from_location, vehicle_no, fp_name):
	data = update_if_string_instance(data)
	selected_type = data['selected_type']
	data = data['items']
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
		
	dc_doc.deliverable_item_details = get_dc_vue_structure(ipd, lot, items)
	dc_doc.from_finishing = 1
	if selected_type == 'return_qty':
		dc_doc.loose_piece_dc = 1
	elif selected_type == 'pack_return':
		dc_doc.pack_piece_dc = 1
	dc_doc.save()
	dc_doc.submit()

def get_dc_vue_structure(ipd, lot, items):
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

	return item_details		

def get_delivery_challan_item_list(lot, item_name, data, is_loose_piece=False):
	ipd = frappe.get_value("Lot", lot, "production_detail")  # to check if lot exists
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute", "dependent_attribute", "stiching_out_stage"]
	is_set_item, pack_attr, primary_attr, set_attr, dept_attr, stich_out = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	items = {}
	for colour in data['data']['data']:
		colour_value = data['data']['data'][colour]['colour']
		if not data['data']['data'][colour]['check_value']:
			continue
		for size in data['data']['data'][colour]['values']:
			dict_key = "balance_dc"
			if is_loose_piece:
				dict_key = "return_qty" 
			if data['data']['data'][colour]['values'][size][dict_key] > 0:
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
				items[key]['qty'] += data['data']['data'][colour]['values'][size][dict_key]
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
				if data[size]:
					box_qty[attr.attribute_value] += data.get(size, 0)
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
def create_stock_entry(data, item_name, doc_name, lot, from_location, to_location, goods_value, vehicle_no):
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
	doc.vehicle_no = vehicle_no
	doc.additional_amount = goods_value
	doc.save()
	doc.submit()
	return doc.name

@frappe.whitelist()
def cancel_document(doctype, docname):
	doc = frappe.get_doc(doctype, docname)
	doc.cancel()

@frappe.whitelist()
def fetch_from_old_lot(doc_name):
	"""Fetch leftover pieces from sibling Finishing Plans whose fp_status='OCR Completed' for the same item.

	Replaces the earlier stock-based fetch. The fetched rows are persisted to
	finishing_old_lot_items so they survive reload.
	"""
	doc = frappe.get_doc("Finishing Plan", doc_name)
	if doc.fp_status == "OCR Completed":
		frappe.throw("Fetch Items is disabled for Finishing Plans in OCR Completed status.")

	ipd = frappe.get_value("Lot", doc.lot, "production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)

	open_fps = frappe.get_all(
		"Finishing Plan",
		filters={
			"item": doc.item,
			"name": ("!=", doc.name),
			"fp_status": ("not in", ["OCR Completed", "P&L Submitted"]),
		},
		fields=["name", "lot", "fp_status"],
	)
	if open_fps:
		rows = "".join(
			f"<tr><td>{frappe.utils.escape_html(fp.name)}</td>"
			f"<td>{frappe.utils.escape_html(fp.lot)}</td>"
			f"<td>{frappe.utils.escape_html(fp.fp_status)}</td></tr>"
			for fp in open_fps
		)
		frappe.throw(
			"Close Other Finishing Plan's to fetch the Items.<br><br>"
			"<table class='table table-bordered'>"
			"<thead><tr><th>Finishing Plan</th><th>Lot</th><th>Status</th></tr></thead>"
			f"<tbody>{rows}</tbody></table>",
			title="Other Finishing Plans Still Open",
		)

	sibling_fps = frappe.get_all(
		"Finishing Plan",
		filters={"item": doc.item, "fp_status": "OCR Completed", "name": ("!=", doc.name)},
		pluck="name",
	)

	# restrict to colours that actually belong to the CURRENT lot's FP
	current_colours = set()
	for row in doc.finishing_plan_details:
		attrs = get_variant_attr_details(row.item_variant)
		c = attrs.get(ipd_doc.packing_attribute)
		if c:
			current_colours.add(c)

	# aggregate loose_piece (return_qty) and loose_piece_set (pack_return_qty) per (fp, lot, variant)
	aggregated = {}
	for sp_name in sibling_fps:
		sp_doc = frappe.get_doc("Finishing Plan", sp_name)
		wh_name = frappe.db.get_value("Supplier", sp_doc.delivery_location, "supplier_name") or sp_doc.delivery_location
		# subtract quantities already given to other FPs from this source FP (per variant)
		given_loose = {}
		given_loose_set = {}
		for g in sp_doc.get("finishing_old_lot_given_items") or []:
			given_loose[g.item_variant] = given_loose.get(g.item_variant, 0) + flt(g.loose_piece_given)
			given_loose_set[g.item_variant] = given_loose_set.get(g.item_variant, 0) + flt(g.loose_piece_set_given)
		for row in sp_doc.finishing_plan_details:
			lp = flt(row.return_qty) - given_loose.get(row.item_variant, 0)
			lps = flt(row.pack_return_qty) - given_loose_set.get(row.item_variant, 0)
			if lp <= 0 and lps <= 0:
				continue
			# filter to colours that exist in the CURRENT lot's FP
			src_attrs = get_variant_attr_details(row.item_variant)
			if src_attrs.get(ipd_doc.packing_attribute) not in current_colours:
				continue
			key = (sp_name, sp_doc.lot, sp_doc.delivery_location, wh_name, row.item_variant)
			prev = aggregated.get(key, (0.0, 0.0))
			aggregated[key] = (prev[0] + max(lp, 0), prev[1] + max(lps, 0))

	# Persist into child table (replace previous rows)
	doc.set("finishing_old_lot_items", [])
	primary_values = get_ipd_primary_values(ipd)
	for (sp_name, src_lot, warehouse, wh_name, variant), (loose_bal, loose_set_bal) in aggregated.items():
		attrs = get_variant_attr_details(variant)
		size = attrs.get(ipd_doc.primary_item_attribute)
		colour = attrs.get(ipd_doc.packing_attribute)
		part = attrs.get(ipd_doc.set_item_attribute) if ipd_doc.is_set_item else None
		set_value = None
		if ipd_doc.is_set_item:
			if ipd_doc.major_attribute_value == part:
				set_value = colour
		else:
			set_value = colour
		doc.append("finishing_old_lot_items", {
			"source_fp": sp_name,
			"source_lot": src_lot,
			"warehouse": warehouse,
			"warehouse_name": wh_name,
			"item_variant": variant,
			"colour": colour,
			"part": part,
			"set_combination": set_value,
			"size": size,
			"balance_loose_piece": loose_bal,
			"balance_loose_piece_set": loose_set_bal,
			"transfer_loose_piece": 0,
			"transfer_loose_piece_set": 0,
		})
	doc.save(ignore_permissions=True)

	return _reshape_old_lot_rows_for_ui(doc, ipd_doc)


def _reshape_old_lot_rows_for_ui(doc, ipd_doc=None):
	"""Turn the persisted finishing_old_lot_items rows into the matrix structure the Vue component expects."""
	if ipd_doc is None:
		ipd = frappe.get_value("Lot", doc.lot, "production_detail")
		ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	primary_values = get_ipd_primary_values(ipd_doc.name)
	groups = {}
	for r in doc.finishing_old_lot_items:
		key = (r.source_lot, r.warehouse, r.warehouse_name)
		groups.setdefault(key, {"data": {}, "total": {}})
		old_lot_inward = groups[key]
		colour = r.colour
		old_lot_inward["data"].setdefault(colour, {
			"values": {},
			"part": r.part,
			"colour": colour,
			"set_combination": r.set_combination,
			"colour_total": {
				"balance_loose_piece": 0, "balance_loose_piece_set": 0,
				"transfer_loose_piece": 0, "transfer_loose_piece_set": 0,
			},
		})
		for s in primary_values:
			old_lot_inward["data"][colour]["values"].setdefault(s, {
				"balance_loose_piece": 0, "balance_loose_piece_set": 0,
				"transfer_loose_piece": 0, "transfer_loose_piece_set": 0,
			})
			old_lot_inward["total"].setdefault(s, 0)
		if r.size in primary_values:
			cell = old_lot_inward["data"][colour]["values"][r.size]
			cell["balance_loose_piece"] += flt(r.balance_loose_piece)
			cell["balance_loose_piece_set"] += flt(r.balance_loose_piece_set)
			cell["transfer_loose_piece"] += flt(r.transfer_loose_piece)
			cell["transfer_loose_piece_set"] += flt(r.transfer_loose_piece_set)
			ct = old_lot_inward["data"][colour]["colour_total"]
			ct["balance_loose_piece"] += flt(r.balance_loose_piece)
			ct["balance_loose_piece_set"] += flt(r.balance_loose_piece_set)
			ct["transfer_loose_piece"] += flt(r.transfer_loose_piece)
			ct["transfer_loose_piece_set"] += flt(r.transfer_loose_piece_set)
			old_lot_inward["total"][r.size] += flt(r.balance_loose_piece) + flt(r.balance_loose_piece_set)

	data = []
	for (src_lot, warehouse, wh_name), old_lot_inward in groups.items():
		data.append({
			"lot": src_lot,
			"warehouse": warehouse,
			"warehouse_name": wh_name,
			"primary_values": primary_values,
			"old_lot_inward": old_lot_inward,
			"is_set_item": ipd_doc.is_set_item,
			"set_attr": ipd_doc.set_item_attribute,
		})
	colours = [row.attribute_value for row in ipd_doc.packing_attribute_details]
	return {"data": data, "colours": colours}

def pack_stage_variant(variant, dept_attr, pack_in_stage):
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
	# split_contributions: used after LT is submitted to update source FP's "given" table + stamp destination rows
	# key: (variant, set_comb) -> {loose_piece, loose_piece_set, colour, part, size, source_fp, source_lot}
	split_contributions = []
	row_index = 0
	uom = frappe.get_value("Item", item_name, "default_unit_of_measure")
	received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	for table_index, group in enumerate(data):
		for colour in group['old_lot_inward']['data']:
			colour_entry = group['old_lot_inward']['data'][colour]
			for size in colour_entry['values']:
				cell = colour_entry['values'][size]
				t_loose = flt(cell.get('transfer_loose_piece'))
				t_loose_set = flt(cell.get('transfer_loose_piece_set'))
				total_transfer = t_loose + t_loose_set
				if total_transfer <= 0:
					continue
				item_attributes = {
					primary: size,
					pack_attr: colour,
					dept_attr: stich_out,
				}
				if is_set:
					item_attributes[set_attr] = colour_entry['part']
				variant_name = get_or_create_variant(item_name, item_attributes)
				set_comb = {"major_colour": colour_entry['set_combination']}
				if is_set:
					set_comb['major_part'] = major_part
				items.append({
					"item": variant_name,
					"from_lot": group['lot'],
					"to_lot": lot,
					"warehouse": group['warehouse'],
					"uom": uom,
					"qty": total_transfer,
					"rate": 0,
					"table_index": table_index,
					"row_index": row_index,
					"received_type": received_type,
					"set_combination": set_comb,
				})
				split_contributions.append({
					"source_lot": group['lot'],
					"variant": variant_name,
					"colour": colour,
					"part": colour_entry.get('part'),
					"set_combination": set_comb,
					"size": size,
					"loose_piece": t_loose,
					"loose_piece_set": t_loose_set,
				})
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

	# --- Split-tracking: record loose_piece / loose_piece_set split on both FPs ---
	import json as _json
	dest_fp_doc = frappe.get_doc("Finishing Plan", doc_name)
	for entry in split_contributions:
		# locate the matching available-row on the destination to decrement its balance
		source_fp_name = None
		for r in dest_fp_doc.finishing_old_lot_items:
			if r.source_lot == entry['source_lot'] and r.item_variant == entry['variant']:
				source_fp_name = r.source_fp
				# reduce available balance by what was just taken; reset the editable transfer fields
				r.balance_loose_piece = flt(r.balance_loose_piece) - flt(entry['loose_piece'])
				r.balance_loose_piece_set = flt(r.balance_loose_piece_set) - flt(entry['loose_piece_set'])
				if r.balance_loose_piece < 0:
					r.balance_loose_piece = 0
				if r.balance_loose_piece_set < 0:
					r.balance_loose_piece_set = 0
				r.transfer_loose_piece = 0
				r.transfer_loose_piece_set = 0
				r.lot_transfer = None
				break
		if not source_fp_name:
			continue
		# record the take on destination's received-history
		dest_fp_doc.append("finishing_old_lot_received_items", {
			"source_fp": source_fp_name,
			"source_lot": entry['source_lot'],
			"item_variant": entry['variant'],
			"colour": entry['colour'],
			"part": entry['part'],
			"set_combination": _json.dumps(entry['set_combination']),
			"size": entry['size'],
			"loose_piece_taken": entry['loose_piece'],
			"loose_piece_set_taken": entry['loose_piece_set'],
			"lot_transfer": doc.name,
		})
		# record the give on source FP's given-history
		source_fp = frappe.get_doc("Finishing Plan", source_fp_name)
		source_fp.append("finishing_old_lot_given_items", {
			"destination_fp": doc_name,
			"destination_lot": lot,
			"item_variant": entry['variant'],
			"colour": entry['colour'],
			"part": entry['part'],
			"set_combination": _json.dumps(entry['set_combination']),
			"size": entry['size'],
			"loose_piece_given": entry['loose_piece'],
			"loose_piece_set_given": entry['loose_piece_set'],
			"lot_transfer": doc.name,
		})
		source_fp.save(ignore_permissions=True)
	# drop fully-consumed rows so the UI only shows what's still available
	dest_fp_doc.finishing_old_lot_items = [
		r for r in dest_fp_doc.finishing_old_lot_items
		if flt(r.balance_loose_piece) > 0 or flt(r.balance_loose_piece_set) > 0
	]
	dest_fp_doc.save(ignore_permissions=True)
	frappe.db.commit()

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

@frappe.whitelist()
def get_incomplete_transfer_docs(lot, doc_name):
	finishing_inward_process = frappe.db.get_single_value("MRP Settings", "finishing_inward_process")
	if not finishing_inward_process:
		frappe.throw("Set Finishing Inward Process")
	from production_api.utils import get_process_wo_list
	wo_list = get_process_wo_list(finishing_inward_process, lot)
	grn_list = frappe.get_all("Goods Received Note", filters={
		"docstatus": 1,
		"against": "Work Order",
		"against_id": ['in', wo_list],
		"lot": lot,
		"is_internal_unit": 1,
		"transfer_complete": 0, 
	}, pluck="name")
	
	grn_list_dict = {}
	for grn in grn_list:
		grn_list_dict[grn] = True

	dc_list = frappe.get_all("Delivery Challan", filters={
		"docstatus": 1,
		"includes_packing": 1,
		"lot": lot,
		"is_internal_unit": 1,
		"transfer_complete": 0, 
	}, pluck="name")

	dc_list_dict = {}

	for dc in dc_list:
		dc_list_dict[dc] = True

	fp_doc = frappe.get_doc("Finishing Plan", doc_name)	
	fp_doc.incomplete_transfer_grn_list = frappe.json.dumps(grn_list_dict)
	fp_doc.incomplete_transfer_dc_list = frappe.json.dumps(dc_list_dict)
	fp_doc.save()

@frappe.whitelist()
def fetch_quantity(doc_name):
	doc = frappe.get_doc("Finishing Plan", doc_name)
	wo_doc = frappe.get_doc("Work Order", doc.work_order)
	finishing_items = {}
	default_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	default_rejected = frappe.db.get_single_value("Stock Settings", "default_rejected_type")
	for row in wo_doc.work_order_calculated_items:
		set_comb = update_if_string_instance(row.set_combination)
		key = (row.item_variant, tuple(sorted(set_comb.items())))
		finishing_items.setdefault(key, {
			"inward_quantity": 0,
			"delivered_quantity": 0,
			"received_types": {},
			"cutting_qty": 0,
			"accepted_qty": 0,
			"rework_qty": 0,
			"item_variant": row.item_variant,
			"set_combination": row.set_combination,
			"received_type_json": {},
			"lot_transferred": 0,
			"ironing_excess": 0,
			"reworked": 0,
			"dc_qty": 0,
			"return_qty": 0,
			"pack_return_qty": 0,
			"return_dc_qty": 0,
			"pack_dc_qty": 0,
			"rejected_qty": 0,
		})
	finishing_inward_process = frappe.db.get_single_value("MRP Settings", "finishing_inward_process")
	if not finishing_inward_process:
		frappe.throw("Set Finishing Inward Process")

	wo_list = get_process_wo_list(finishing_inward_process, doc.lot)
	for wo in wo_list:
		stich_wo_doc = frappe.get_doc("Work Order", wo)
		for row in stich_wo_doc.work_order_calculated_items:
			if row.quantity > 0:
				set_comb = update_if_string_instance(row.set_combination)
				key = (row.item_variant, tuple(sorted(set_comb.items())))
				finishing_items[key]['delivered_quantity'] += row.received_qty
				finishing_items[key]['inward_quantity'] += row.delivered_quantity
				received_types = update_if_string_instance(row.received_type_json)
				for ty in received_types:
					if ty not in finishing_items[key]['received_types']:
						finishing_items[key]['received_types'][ty] = 0
					if ty == default_type:
						finishing_items[key]['accepted_qty'] += received_types[ty]
					elif ty == default_rejected:
						finishing_items[key]['rejected_qty'] += received_types[ty]
					elif ty not in [default_type, default_rejected]:
						finishing_items[key]['rework_qty'] += received_types[ty]	

					finishing_items[key]['received_types'][ty] += received_types[ty]	

	cut_wo_list = get_process_wo_list("Cutting", doc.lot)
	for wo in cut_wo_list:
		cut_wo_doc = frappe.get_doc("Work Order", wo)
		for row in cut_wo_doc.work_order_calculated_items:
			if row.received_qty > 0:
				set_comb = update_if_string_instance(row.set_combination)
				key = (row.item_variant, tuple(sorted(set_comb.items())))
				finishing_items[key]['cutting_qty'] += row.received_qty

	finishing_rework_items = {}
	rework_list = frappe.get_all("GRN Rework Item", filters={"lot": wo_doc.lot}, pluck="name")
	for rework in rework_list:
		rework_doc = frappe.get_doc("GRN Rework Item", rework)
		from_finishing = frappe.get_value("Goods Received Note", rework_doc.grn_number, "from_finishing")
		for row in rework_doc.grn_rework_item_details:
			set_comb = update_if_string_instance(row.set_combination)
			key = (row.item_variant, tuple(sorted(update_if_string_instance(set_comb).items())))
			finishing_rework_items.setdefault(key, {
				"quantity": 0,
				"reworked": 0,
				"rejected": 0,
			})
			if from_finishing:
				finishing_items[key]['rework_qty'] += row.quantity	
			finishing_rework_items[key]['quantity'] += row.quantity
			finishing_rework_items[key]['rejected'] += row.rejection

		for row in rework_doc.grn_reworked_item_details:
			set_comb = update_if_string_instance(row.set_combination)
			key = (row.item_variant, tuple(sorted(update_if_string_instance(set_comb).items())))
			finishing_rework_items[key]['reworked'] += row.quantity	

	fp_dc_list = update_if_string_instance(doc.dc_list)
	dc_list = [dc for dc in fp_dc_list]
	for dc in dc_list:
		dc_doc = frappe.get_doc("Delivery Challan", dc)
		for item in dc_doc.items:
			set_comb = update_if_string_instance(item.set_combination)
			key = (item.item_variant, tuple(sorted(set_comb.items())))
			if finishing_items.get(key):
				finishing_items[key]['dc_qty'] += item.stock_qty
				if dc_doc.loose_piece_dc:
					finishing_items[key]['return_dc_qty'] += item.stock_qty
				if dc_doc.pack_piece_dc:
					finishing_items[key]['pack_dc_qty'] += item.stock_qty
	
	lot_transfer = update_if_string_instance(doc.lot_transfer_list)
	lot_transfer_list = [lot_t for lot_t in lot_transfer]
	for lot_t in lot_transfer_list:
		lot_t_doc = frappe.get_doc("Lot Transfer", lot_t)
		for row in lot_t_doc.items:
			set_comb = update_if_string_instance(row.set_combination)
			key = (row.item, tuple(sorted(set_comb.items())))
			qty = row.qty
			finishing_items[key]['lot_transferred'] += qty	

	return_grn_list = update_if_string_instance(doc.return_grn_list)
	pack_return_list = update_if_string_instance(doc.pack_return_list)
	return_grns = [grn for grn in return_grn_list]
	finishing_items, finishing_rework_items = get_updated_return(return_grns, finishing_items, finishing_rework_items)
	pack_return_grns = [grn for grn in pack_return_list]
	finishing_items, finishing_rework_items = get_updated_return(pack_return_grns, finishing_items, finishing_rework_items)
	
	ironing_excess = update_if_string_instance(doc.ironing_excess_list)
	ironing_excess_list = [ste for ste in ironing_excess]

	for ironing in ironing_excess_list:
		ste_doc = frappe.get_doc("Stock Entry", ironing)
		for row in ste_doc.items:
			qty = row.qty
			key = (row.item, tuple(sorted(update_if_string_instance(row.set_combination).items())))
			finishing_items[key]['ironing_excess'] += qty	

	finishing_items_list = []
	finishing_rework_items_list = []
	for key in finishing_items:
		variant, tuple_attrs = key
		comb = get_tuple_attributes(tuple_attrs)
		reworked_qty = 0
		finishing_items[key]['return_qty'] = finishing_items[key]['return_qty'] - finishing_items[key]['return_dc_qty']
		finishing_items[key]['pack_return_qty'] = finishing_items[key]['pack_return_qty'] - finishing_items[key]['pack_dc_qty']
		if finishing_items[key]['rework_qty'] > 0:
			reworked = 0
			rejected = 0
			if finishing_rework_items.get(key):
				reworked = finishing_rework_items[key]['reworked']
				rejected = finishing_rework_items[key]['rejected']
				reworked_qty = finishing_rework_items[key]['reworked']
			finishing_rework_items_list.append({
				"item_variant": variant,
				"set_combination": frappe.json.dumps(comb),
				"quantity": finishing_items[key]['rework_qty'],
				"reworked_quantity": reworked,
				"rejected_qty": rejected,
			})
		finishing_items_list.append({
			"item_variant": variant,
			"delivered_quantity": finishing_items[key]['delivered_quantity'],
			"inward_quantity": finishing_items[key]['inward_quantity'],
			"set_combination": frappe.json.dumps(comb),
			"received_type_json": frappe.json.dumps(finishing_items[key]['received_types']),
			"cutting_qty": finishing_items[key]['cutting_qty'],
			"accepted_qty": finishing_items[key]['accepted_qty'],
			"lot_transferred": finishing_items[key]['lot_transferred'],
			"ironing_excess": finishing_items[key]['ironing_excess'],
			"reworked": reworked_qty,
			"dc_qty": finishing_items[key]['dc_qty'],
			"return_qty": finishing_items[key]['return_qty'],
			"pack_return_qty": finishing_items[key]['pack_return_qty'],
			"return_dc_qty": finishing_items[key]['return_dc_qty'],
			"pack_dc_qty": finishing_items[key]['pack_dc_qty'],
			"rejected_qty": finishing_items[key]['rejected_qty'],
		})		
	doc.set("finishing_plan_details", finishing_items_list)
	doc.save()
	doc.set("finishing_plan_reworked_details", finishing_rework_items_list)
	doc.save()

def get_updated_return(grn_list, finishing_items, finishing_rework_items):
	default_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	default_rejected_type = frappe.db.get_single_value("Stock Settings", "default_rejected_type")
	for grn in grn_list:
		grn_doc = frappe.get_doc("Goods Received Note", grn)
		items = update_if_string_instance(grn_doc.items_json)
		items = [item.as_dict() for item in grn_doc.items]
		for key, variants in groupby(items, lambda i: i['row_index']):
			for item in variants:
				set_comb = update_if_string_instance(item['set_combination'])
				key = (item['item_variant'], tuple(sorted(set_comb.items())))
				if finishing_items.get(key):
					ty = item['received_type']
					qty = item['quantity'] * -1
					rework_qty = item['quantity']
					if ty != default_type:
						if not finishing_rework_items.get(key):
							finishing_rework_items[key] = {
								"quantity": 0,
								"reworked_quantity": 0,
								"rejected_qty": 0,
								"set_combination": item['set_combination'],
							}
						if ty ==  default_rejected_type:
							finishing_rework_items[key]['rejected_qty'] += rework_qty
						finishing_rework_items[key]['quantity'] += rework_qty
						finishing_items[key]['accepted_qty'] += qty 
					else:
						q = item['quantity']
						if grn_doc.is_pack:
							finishing_items[key]['pack_return_qty'] += q		
						else:	
							finishing_items[key]['return_qty'] += q		

					finishing_items[key]['dc_qty'] += qty
	return finishing_items, finishing_rework_items

@frappe.whitelist()
def cache_selected_size(key, size, finishing_id):
	check_eqi_status(size, finishing_id)
	key += frappe.session.user
	frappe.cache.set_value(key, size)

def check_eqi_status(print_size, finishing_id):
	lot = frappe.get_value("Finishing Plan", finishing_id, "lot")
	process = frappe.db.get_single_value("MRP Settings", "finishing_inward_process") 
	wo_list = get_process_wo_list(process, lot)
	from production_api.utils import get_eqi_status
	eqi_data = get_eqi_status(wo_list)
	sup_list = []
	for sup in eqi_data:
		for colour in eqi_data[sup]:
			if eqi_data[sup][colour].get(print_size) and eqi_data[sup][colour][print_size] != 'Pass':
				sup_list.append(sup)
	if sup_list:
		frappe.throw(f"EQI not passed for Size {print_size}: {', '.join(sup_list)}")

@frappe.whitelist()
def get_finishing_plan_inward_details(key, lot):
	key += frappe.session.user
	selected_size = frappe.cache.get_value(key)
	if not selected_size:
		return {}
	frappe.cache().delete_value(key)
	rejected_type = frappe.db.get_single_value("Stock Settings", "default_rejected_type")
	process = frappe.db.get_single_value("MRP Settings", "finishing_inward_process") 
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	wo_list = get_process_wo_list(process, lot)
	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_fields = ["is_set_item", "packing_attribute", "primary_item_attribute", "set_item_attribute", "major_attribute_value"]
	is_set_item, pack_attr, primary_attr, set_attr, major_attr_val = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	inward_qty = {
		"data": {},
	}
	type_list = [frappe.db.get_single_value("Stock Settings", "default_received_type")]
	for wo in wo_list:
		items = frappe.db.sql(
			"""
				SELECT * FROM `tabWork Order Calculated Item` WHERE parent = %(work_order)s
			""", {
				"work_order": wo
			}, as_dict=True,
		)
		for item in items:
			attr_details = get_variant_attr_details(item['item_variant'])
			size = attr_details[primary_attr]
			if size != selected_size:
				continue
			set_comb = update_if_string_instance(item['set_combination'])
			major_colour = set_comb['major_colour']
			colour = major_colour
			part = None
			if is_set_item:
				variant_colour = attr_details[pack_attr]
				part = attr_details[set_attr]
				colour = variant_colour+"("+ major_colour+")"
			if not part:
				part = "item"
			inward_qty["data"].setdefault(part, {
				"colours": {},
				"colour_type": {},
				"type_wise": {},
				"cut_detail": {},
				"total_sew": 0,
				"total_cut": 0,
				"part_colours": [],
			})
			received_types = update_if_string_instance(item['received_type_json'])
			if colour not in inward_qty["data"][part]['part_colours']:
				inward_qty["data"][part]['part_colours'].append(colour)
				inward_qty["data"][part]['colours'].setdefault(colour, {})
				inward_qty['data'][part]['colours'][colour]['sewing_received'] = 0
				inward_qty["data"][part]['colour_type'].setdefault(colour, {})
				inward_qty['data'][part]['colour_type'][colour]['type_wise'] = {}

			for received_type in received_types:
				if received_type == rejected_type:
					continue
				if received_type not in type_list:
					type_list.append(received_type)
				qty = received_types[received_type]
				inward_qty['data'][part]['total_sew'] += qty

				inward_qty["data"][part]['colours'][colour]['sewing_received'] += qty
				inward_qty["data"][part]['colour_type'][colour]['type_wise'].setdefault(received_type, 0)
				inward_qty["data"][part]['colour_type'][colour]['type_wise'][received_type] += qty

				inward_qty['data'][part]['type_wise'].setdefault(received_type, 0)
				inward_qty['data'][part]['type_wise'][received_type] += qty	

	cut_wo_list = get_process_wo_list("Cutting", lot)
	total_cut = 0
	for wo in cut_wo_list:
		items = frappe.db.sql(
			"""
				SELECT * FROM `tabWork Order Calculated Item` WHERE parent = %(work_order)s
			""", {
				"work_order": wo
			}, as_dict=True,
		)
		for item in items:
			attr_details = get_variant_attr_details(item['item_variant'])
			size = attr_details[primary_attr]
			if size != selected_size:
				continue
			set_comb = update_if_string_instance(item['set_combination'])
			major_colour = set_comb['major_colour']
			colour = major_colour
			part = None
			if is_set_item:
				variant_colour = attr_details[pack_attr]
				part = attr_details[set_attr]
				colour = variant_colour+"("+ major_colour+")"
			if not part:
				part = "item"

			received_types = update_if_string_instance(item['received_type_json'])
			inward_qty['data'][part]['cut_detail'].setdefault(colour, 0)

			for received_type in received_types:
				if received_type == rejected_type:
					continue
				if received_type not in type_list:
					type_list.append(received_type)
				qty = received_types[received_type]
				inward_qty['data'][part]['cut_detail'][colour] += qty
				inward_qty['data'][part]['total_cut'] += qty

				total_cut += qty
	return {
		"selected_size": selected_size,
		"types": type_list,
		"data": inward_qty['data'],
		"is_set_item": is_set_item,
		"set_attr": set_attr
	}

@frappe.whitelist()
def convert_to_loose_piece_items(data, work_order, lot, item_name, from_location):
	data = update_if_string_instance(data)
	dc_doc = frappe.new_doc("Delivery Challan")
	wo_doc = frappe.get_doc("Work Order", work_order)
	dc_doc.work_order = work_order
	dc_doc.lot = lot
	dc_doc.from_location = from_location
	dc_doc.from_address = get_primary_address(from_location)
	dc_doc.vehicle_no = "NA"
	dc_doc.supplier = wo_doc.supplier
	dc_doc.supplier_address = get_primary_address(wo_doc.supplier)
	items = []
	ipd = frappe.get_value("Lot", lot, "production_detail")
	delivery_challan_item_list = get_delivery_challan_item_list(lot, item_name, data, is_loose_piece=True)
	for item in wo_doc.deliverables:
		item = item.as_dict()
		set_comb = update_if_string_instance(item['set_combination'])
		key = (item['item_variant'], tuple(sorted(set_comb.items())))
		if delivery_challan_item_list.get(key):
			item['delivered_quantity'] = delivery_challan_item_list[key]['qty']
		else:
			item['delivered_quantity'] = 0	
		items.append(item)
		
	dc_doc.deliverable_item_details = get_dc_vue_structure(ipd, lot, items)
	dc_doc.from_finishing = 1
	dc_doc.save()
	dc_doc.submit()
	return_items(data, work_order, lot, item_name, {
		"from_location": from_location,
		"received_type": "Accepted",
		"vehicle_no": "NA",
		"delivery_location": from_location
	})

def get_ocr_percentage(val_dict, make_pos = False):
	val1 = val_dict['val1']
	val2 = val_dict['val2']
	if val1 == 0:
		val1 = 1
	x = val2/val1
	if not x:
		x = 0
	x = x * 100

	if make_pos and x < 0:
		x = x * -1

	return round(x, 2)

def get_ocr_style(val):
	if val < 0:
		return "background: #f57f87;"
	elif val > 0:
		return "background:#98ebae";
	return "background:#ebc96e;"

@frappe.whitelist()
def create_alternative_fp(doc_name, alternative_item, production_detail, lot_name, qty_details):
	qty_details = update_if_string_instance(qty_details)
	fp_doc = frappe.get_doc("Finishing Plan", doc_name)
	converting_colours = []
	converting_sizes = []
	for colour in qty_details['data']['data']:
		if not qty_details['data']['data'][colour]['check_value']:
			continue
		for size in qty_details['data']['data'][colour]['values']:
			qty = qty_details['data']['data'][colour]['values'][size]['conversion_qty']
			if qty > 0:
				if colour not in converting_colours:
					converting_colours.append(colour)
				if size not in converting_sizes:
					converting_sizes.append(size)

	check_colours_and_sizes(production_detail, converting_colours, converting_sizes)
	supplier, process = frappe.get_value("Work Order", fp_doc.work_order, ["supplier", "process_name"])
	check_process_cost(process, alternative_item, supplier)
	## LOT CREATION
	lot_doc = frappe.new_doc("Lot")
	lot_doc.lot_name = lot_name
	lot_doc.production_detail = production_detail
	lot_doc.item = alternative_item
	from production_api.essdee_production.doctype.lot.lot import get_isfinal_uom
	response = get_isfinal_uom(production_detail, get_pack_stage=True)
	lot_doc.uom = response['uom']
	lot_doc.pack_in_stage = response['pack_in_stage']
	lot_doc.packing_uom = response['packing_uom']
	lot_doc.pack_out_stage = response['pack_out_stage']
	lot_doc.dependent_attribute_mapping = response['dependent_attr_mapping']
	lot_doc.tech_pack_version = response['tech_pack_version']
	lot_doc.pattern_version = response['pattern_version']
	lot_doc.packing_combo = response['packing_combo']
	lot_doc.is_transferred = 1
	lot_doc.transferred_lot = fp_doc.lot
	lot_doc.save()
	ipd_fields = ["packing_combo", "pack_out_stage", "primary_item_attribute", "dependent_attribute", 'packing_attribute', 'pack_in_stage']
	pcs_per_box, pack_stage, primary_attr, dependent_attr, packing_attr, pack_in_stage = frappe.get_value("Item Production Detail", production_detail, ipd_fields)

	size_wise_detail = {}
	row_index = 0
	for colour in qty_details['data']['data']:
		if not qty_details['data']['data'][colour]['check_value']:
			continue
		for size in qty_details['data']['data'][colour]['values']:
			size_wise_detail.setdefault(size, 0)
			qty = qty_details['data']['data'][colour]['values'][size]['conversion_qty']
			size_wise_detail[size] += qty
			
			order_detail = frappe.new_doc("Lot Order Detail")
			order_detail.item_variant = get_or_create_variant(alternative_item, {
				primary_attr: size,
				dependent_attr: pack_in_stage,
				packing_attr: colour,
			})
			order_detail.quantity = qty
			order_detail.cut_qty = qty
			order_detail.pack_qty = 0
			order_detail.parent = lot_doc.name
			order_detail.parentfield = "lot_order_details"
			order_detail.parenttype = "Lot"
			order_detail.row_index = row_index
			order_detail.set_combination = frappe.json.dumps({"major_colour": colour})
			order_detail.stich_qty = 0
			order_detail.table_index = 0	
			order_detail.save()
		row_index += 1	
	
	items = save_item_details(size_wise_detail, alternative_item, pcs_per_box, pack_stage, primary_attr, dependent_attr)
	for row in items:
		lot_order_item = frappe.new_doc("Lot Order Item")
		lot_order_item.mrp = row['mrp']
		lot_order_item.parent = lot_doc.name
		lot_order_item.parentfield = "items"
		lot_order_item.parenttype = "Lot"
		lot_order_item.row_index = row['row_index']
		lot_order_item.table_index = row['table_index']
		lot_order_item.ratio = row['ratio']
		lot_order_item.qty = row['qty']
		lot_order_item.item_variant = row['item_variant']
		lot_order_item.save(ignore_permissions=True)

	old_wo = frappe.get_doc("Work Order", fp_doc.work_order)
	wo_doc = frappe.new_doc("Work Order")
	wo_doc.lot = lot_doc.name
	wo_doc.supplier = old_wo.supplier
	wo_doc.supplier_address = old_wo.supplier_address
	wo_doc.delivery_address = old_wo.delivery_address
	wo_doc.item = alternative_item
	wo_doc.process_name = old_wo.process_name
	wo_doc.delivery_location = old_wo.delivery_location
	wo_doc.planned_start_date = old_wo.planned_start_date
	wo_doc.planned_end_date = old_wo.planned_end_date
	wo_doc.expected_delivery_date = old_wo.expected_delivery_date
	wo_doc.save()

	from production_api.production_api.doctype.work_order.work_order import get_lot_items, get_deliverable_receivable
	items = get_lot_items(
		wo_doc.lot,wo_doc.name,wo_doc.process_name,wo_doc.includes_packing,
	)
	for item in items:
		idx = 0
		for row in item['items']:
			d = {}
			for size in row['values']:
				d[size] = row['values'][size]['qty']
			item['items'][idx]['work_order_qty'] = d
			idx += 1	
	new_wo_name = get_deliverable_receivable(items, wo_doc.name, is_alternate=True)
	frappe.db.set_value("Lot", fp_doc.lot, "has_transferred", 1)
	return new_wo_name

def save_item_details(item_details, alternative_item, pcs_per_box, pack_stage, primary_attr, dependent_attr):
	item_details = update_if_string_instance(item_details)
	items = []
	idx = 0
	for size in item_details:
		attributes = {
			primary_attr: size,
			dependent_attr: pack_stage
		}
		item1 = {}
		variant_name = get_or_create_variant(alternative_item, attributes)
		item1['item_variant'] = variant_name
		item1['qty'] = round(item_details[size]/pcs_per_box)
		item1['ratio'] = 1
		item1['mrp'] = 0
		item1['table_index'] = 0
		item1['row_index'] = idx
		idx += 1
		items.append(item1)
	return items	

def check_colours_and_sizes(ipd, converting_colours, converting_sizes):
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	if ipd_doc.is_set_item:
		frappe.throw("Set Item is not applicable for Alternative Items")

	pack_attr = ipd_doc.packing_attribute
	primary_attr = ipd_doc.primary_item_attribute
	pack_attr_mapping = None
	primary_attr_mapping = None
	for row in ipd_doc.item_attributes:
		if row.attribute == pack_attr:
			pack_attr_mapping = row.mapping
		if row.attribute == primary_attr:
			primary_attr_mapping = row.mapping

	if not pack_attr_mapping or not primary_attr_mapping:
		frappe.throw("Not a valid Production Detail")

	doc = frappe.get_doc("Item Item Attribute Mapping", pack_attr_mapping)
	colours = [row.attribute_value for row in doc.values]
	doc = frappe.get_doc("Item Item Attribute Mapping", primary_attr_mapping)
	sizes = [row.attribute_value for row in doc.values]	

	for colour in converting_colours:
		if colour not in colours:
			frappe.throw(f"Selected Item Production Detail not contains the {pack_attr} {colour}")

	for size in sizes:
		if size not in converting_sizes:
			frappe.throw(f"Selected Item Production Detail not contains the {primary_attr} {size}")

def check_process_cost(process_name, item, supplier):
	fil = {
		"process_name": process_name,
		"item": item,
		"is_expired": 0,
		"from_date": ["<=", frappe.utils.nowdate()],
		"docstatus": 1,
		"workflow_state": "Approved",
		"is_rework": 0,
		"supplier": supplier
	}

	filter_variants = [fil.copy()]

	f1 = fil.copy()
	filter_variants.append(f1)

	docname = None
	for f in filter_variants:
		docs = frappe.get_list("Process Cost", filters=f)
		if docs:
			docname = docs[0].name
			break
	
	if not docname:
		frappe.throw('No process cost was defined')

@frappe.whitelist()
def get_alternative_details(lot):
	from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details
	lot_list = frappe.get_all("Lot", filters={"transferred_lot": lot}, pluck="name")
	lot_dict = {}
	for lot in lot_list:
		lot_doc = frappe.get_doc("Lot", lot)
		details = fetch_order_item_details(lot_doc.lot_order_details, lot_doc.production_detail)
		lot_dict[lot] = {
			"item": lot_doc.item,
			"ipd": lot_doc.production_detail,
			"details": details
		}
	return lot_dict

@frappe.whitelist()
def check_is_alternative_item(item):
	items = frappe.db.get_all("Item Alternative", filters={
		"item": item
	}, pluck="alternative_item")

	return items


@frappe.whitelist()
def get_finishing_packed_details(date, lot_list=None, item_list=None):
	"""Get lot/item-wise, size-wise box quantities from packing GRNs for a given date."""
	import json
	if isinstance(lot_list, str):
		lot_list = json.loads(lot_list)
	if isinstance(item_list, str):
		item_list = json.loads(item_list)

	grns = frappe.get_all("Goods Received Note", filters={
		"against": "Work Order",
		"includes_packing": 1,
		"docstatus": 1,
		"posting_date": date,
	}, fields=["name", "lot"])

	lot_grns = {}
	for grn in grns:
		lot_grns.setdefault(grn.lot, []).append(grn.name)

	# Filter by lot_list
	if lot_list:
		lot_grns = {k: v for k, v in lot_grns.items() if k in lot_list}

	result = []
	for lot, grn_names in lot_grns.items():
		lot_item = frappe.get_value("Lot", lot, "item")
		# Filter by item_list
		if item_list and lot_item not in item_list:
			continue
		ipd = frappe.get_value("Lot", lot, "production_detail")
		if not ipd:
			continue

		ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
		primary_attr = ipd_doc.primary_item_attribute
		pieces_per_box = ipd_doc.packing_combo or 0
		sizes = get_ipd_primary_values(ipd)

		size_qty = {}
		for size in sizes:
			size_qty[size] = 0

		for grn_name in grn_names:
			grn_items = frappe.get_all("Goods Received Note Item", filters={
				"parent": grn_name,
			}, fields=["item_variant", "quantity"])

			for gi in grn_items:
				attr_details = get_variant_attr_details(gi.item_variant)
				size = attr_details.get(primary_attr)
				if size:
					size_qty.setdefault(size, 0)
					size_qty[size] += gi.quantity

		total_boxes = sum(size_qty.values())
		total_pieces = total_boxes * pieces_per_box if pieces_per_box else 0

		result.append({
			"lot": lot,
			"item": lot_item,
			"sizes": sizes,
			"size_qty": size_qty,
			"pieces_per_box": pieces_per_box,
			"total_boxes": total_boxes,
			"total_pieces": total_pieces,
		})

	all_sizes = []
	seen = set()
	for row in result:
		for s in row["sizes"]:
			if s not in seen:
				seen.add(s)
				all_sizes.append(s)

	return {"data": result, "sizes": all_sizes}


@frappe.whitelist()
def get_finishing_dispatch_report(from_date, to_date, lot_list=None, item_list=None):
	"""Get lot/item-wise, size-wise packed and dispatched quantities for a date range."""
	import json
	if isinstance(lot_list, str):
		lot_list = json.loads(lot_list)
	if isinstance(item_list, str):
		item_list = json.loads(item_list)

	# --- Packed (same as get_finishing_packed_details but with date range) ---
	grns = frappe.get_all("Goods Received Note", filters={
		"against": "Work Order",
		"includes_packing": 1,
		"docstatus": 1,
		"is_return": 0,
		"posting_date": ["between", [from_date, to_date]],
	}, fields=["name", "lot"])

	lot_grns = {}
	for grn in grns:
		lot_grns.setdefault(grn.lot, []).append(grn.name)

	# Filter by lot_list
	if lot_list:
		lot_grns = {k: v for k, v in lot_grns.items() if k in lot_list}

	packed_result = []
	for lot, grn_names in lot_grns.items():
		lot_item = frappe.get_value("Lot", lot, "item")
		# Filter by item_list
		if item_list and lot_item not in item_list:
			continue
		ipd = frappe.get_value("Lot", lot, "production_detail")
		if not ipd:
			continue

		ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
		primary_attr = ipd_doc.primary_item_attribute
		pieces_per_box = ipd_doc.packing_combo or 0
		sizes = get_ipd_primary_values(ipd)

		size_qty = {size: 0 for size in sizes}

		for grn_name in grn_names:
			grn_items = frappe.get_all("Goods Received Note Item", filters={
				"parent": grn_name,
			}, fields=["item_variant", "quantity"])

			for gi in grn_items:
				attr_details = get_variant_attr_details(gi.item_variant)
				size = attr_details.get(primary_attr)
				if size:
					size_qty.setdefault(size, 0)
					size_qty[size] += gi.quantity

		total_boxes = sum(size_qty.values())
		total_pieces = total_boxes * pieces_per_box if pieces_per_box else 0

		packed_result.append({
			"lot": lot,
			"item": lot_item,
			"sizes": sizes,
			"size_qty": size_qty,
			"pieces_per_box": pieces_per_box,
			"total_boxes": total_boxes,
			"total_pieces": total_pieces,
		})

	# --- Dispatched (Stock Entry Material Issue) ---
	stock_entries = frappe.get_all("Stock Entry", filters={
		"against": ["in", ["Finishing Plan", "Finishing Plan Dispatch"]],
		"purpose": "Material Issue",
		"docstatus": 1,
		"posting_date": ["between", [from_date, to_date]],
	}, fields=["name"])

	lot_dispatched = {}
	for se in stock_entries:
		se_items = frappe.get_all("Stock Entry Detail", filters={
			"parent": se.name,
		}, fields=["item", "qty", "lot"])

		for si in se_items:
			if not si.lot:
				continue
			lot_dispatched.setdefault(si.lot, []).append(si)

	# Filter by lot_list
	if lot_list:
		lot_dispatched = {k: v for k, v in lot_dispatched.items() if k in lot_list}

	dispatched_result = []
	for lot, items in lot_dispatched.items():
		lot_item = frappe.get_value("Lot", lot, "item")
		# Filter by item_list
		if item_list and lot_item not in item_list:
			continue
		ipd = frappe.get_value("Lot", lot, "production_detail")
		if not ipd:
			continue

		ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
		primary_attr = ipd_doc.primary_item_attribute
		pieces_per_box = ipd_doc.packing_combo or 0
		sizes = get_ipd_primary_values(ipd)

		size_qty = {size: 0 for size in sizes}

		for si in items:
			attr_details = get_variant_attr_details(si.item)
			size = attr_details.get(primary_attr)
			if size:
				size_qty.setdefault(size, 0)
				size_qty[size] += si.qty

		total_boxes = sum(size_qty.values())
		total_pieces = total_boxes * pieces_per_box if pieces_per_box else 0

		dispatched_result.append({
			"lot": lot,
			"item": lot_item,
			"sizes": sizes,
			"size_qty": size_qty,
			"pieces_per_box": pieces_per_box,
			"total_boxes": total_boxes,
			"total_pieces": total_pieces,
		})

	# Merge packed and dispatched by lot
	lot_data = {}
	for row in packed_result:
		lot_data[row["lot"]] = {
			"lot": row["lot"],
			"item": row["item"],
			"sizes": row["sizes"],
			"pieces_per_box": row["pieces_per_box"],
			"packed_qty": row["size_qty"],
			"packed_total_boxes": row["total_boxes"],
			"packed_total_pieces": row["total_pieces"],
			"dispatched_qty": {},
			"dispatched_total_boxes": 0,
			"dispatched_total_pieces": 0,
		}

	for row in dispatched_result:
		if row["lot"] in lot_data:
			lot_data[row["lot"]]["dispatched_qty"] = row["size_qty"]
			lot_data[row["lot"]]["dispatched_total_boxes"] = row["total_boxes"]
			lot_data[row["lot"]]["dispatched_total_pieces"] = row["total_pieces"]
			# Merge sizes
			existing_sizes = lot_data[row["lot"]]["sizes"]
			for s in row["sizes"]:
				if s not in existing_sizes:
					existing_sizes.append(s)
		else:
			lot_data[row["lot"]] = {
				"lot": row["lot"],
				"item": row["item"],
				"sizes": row["sizes"],
				"pieces_per_box": row["pieces_per_box"],
				"packed_qty": {},
				"packed_total_boxes": 0,
				"packed_total_pieces": 0,
				"dispatched_qty": row["size_qty"],
				"dispatched_total_boxes": row["total_boxes"],
				"dispatched_total_pieces": row["total_pieces"],
			}

	# Collect all unique sizes
	all_sizes = []
	seen = set()
	for entry in lot_data.values():
		for s in entry["sizes"]:
			if s not in seen:
				seen.add(s)
				all_sizes.append(s)

	return {
		"data": list(lot_data.values()),
		"sizes": all_sizes,
	}

AUTO_FP_STATUSES = ("", "Planned", "Partially Received", "Ready to Pack", "Partially Dispatched", "Dispatched", "Fully Dispatched")
FULLY_DISPATCHED_PCT = 97.0


def get_set_item_parts_count(finishing_doc):
	ipd = finishing_doc.production_detail or frappe.get_value("Lot", finishing_doc.lot, "production_detail")
	if not ipd:
		return 1

	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	if not ipd_doc.is_set_item:
		return 1

	parts = {
		row.set_item_attribute_value
		for row in ipd_doc.set_item_combination_details
		if row.set_item_attribute_value
	}
	if parts:
		return len(parts)

	parts = set()
	if ipd_doc.set_item_attribute:
		for row in finishing_doc.finishing_plan_details:
			attr_details = get_variant_attr_details(row.item_variant)
			part = attr_details.get(ipd_doc.set_item_attribute)
			if part:
				parts.add(part)

	return len(parts) or 1


def get_finishing_dispatch_totals(finishing_doc):
	if isinstance(finishing_doc, str):
		finishing_doc = frappe.get_doc("Finishing Plan", finishing_doc)

	total_cutting = 0.0
	total_dispatched_pieces = 0.0
	for row in finishing_doc.finishing_plan_details:
		total_cutting += flt(row.cutting_qty)

	pieces_per_box = flt(finishing_doc.pieces_per_box) or 0
	if pieces_per_box:
		set_item_parts_count = get_set_item_parts_count(finishing_doc)
		for row in finishing_doc.finishing_plan_grn_details:
			total_dispatched_pieces += (
				flt(row.dispatched) * pieces_per_box * set_item_parts_count
			)

	dispatch_percentage = 0.0
	if total_cutting:
		dispatch_percentage = (total_dispatched_pieces / total_cutting) * 100.0

	return frappe._dict({
		"total_cutting": total_cutting,
		"total_dispatched_pieces": total_dispatched_pieces,
		"dispatch_percentage": dispatch_percentage,
	})


def record_finishing_dispatch_log(finishing_doc, stock_entry, dispatch_boxes, source_doctype=None, source_name=None):
	if not frappe.get_meta("Finishing Plan").has_field("finishing_plan_dispatch_logs"):
		return
	if flt(dispatch_boxes) <= 0:
		return

	source_doctype = source_doctype or stock_entry.against
	source_name = source_name or stock_entry.against_id
	set_item_parts_count = get_set_item_parts_count(finishing_doc)
	dispatch_pieces = flt(dispatch_boxes) * flt(finishing_doc.pieces_per_box) * set_item_parts_count
	totals = get_finishing_dispatch_totals(finishing_doc)
	previous_dispatched = max(flt(totals.total_dispatched_pieces) - dispatch_pieces, 0)
	previous_percentage = 0.0
	if totals.total_cutting:
		previous_percentage = (previous_dispatched / flt(totals.total_cutting)) * 100.0

	log_data = {
		"stock_entry": stock_entry.name,
		"source_doctype": source_doctype,
		"source_name": source_name,
		"posting_date": stock_entry.posting_date,
		"posting_time": stock_entry.posting_time,
		"dispatch_boxes": dispatch_boxes,
		"dispatch_pieces": dispatch_pieces,
		"total_dispatched_pieces_after": totals.total_dispatched_pieces,
		"cutting_qty": totals.total_cutting,
		"dispatch_percentage_before": previous_percentage,
		"dispatch_percentage_after": totals.dispatch_percentage,
		"cancelled": 0,
	}

	for row in finishing_doc.get("finishing_plan_dispatch_logs") or []:
		if (
			row.stock_entry == stock_entry.name
			and row.source_doctype == source_doctype
			and row.source_name == source_name
		):
			row.update(log_data)
			return

	finishing_doc.append("finishing_plan_dispatch_logs", log_data)


def cancel_finishing_dispatch_log(finishing_doc, stock_entry_name):
	if not frappe.get_meta("Finishing Plan").has_field("finishing_plan_dispatch_logs"):
		return
	for row in finishing_doc.get("finishing_plan_dispatch_logs") or []:
		if row.stock_entry == stock_entry_name:
			row.cancelled = 1


def _total_unaccountable(finishing_doc):
	try:
		ocr_data = get_ocr_details(finishing_doc)
	except Exception:
		return None
	total = 0
	for part_value in ocr_data:
		total += (
			ocr_data[part_value]['sewing_received']
			+ ocr_data[part_value]['old_lot']
			+ ocr_data[part_value]['ironing_excess']
			- (
				ocr_data[part_value]['dispatched_piece']
				+ ocr_data[part_value]['rejected']
				+ ocr_data[part_value]['loose_piece_set']
				+ ocr_data[part_value]['loose_piece']
				+ ocr_data[part_value]['pending']
				+ ocr_data[part_value]['transferred']
			)
		)
	return total


def compute_received_status(finishing_doc):
	total_cutting = 0.0
	total_received = 0.0
	for row in finishing_doc.finishing_plan_details:
		total_cutting += flt(row.cutting_qty)
		total_received += flt(row.delivered_quantity)

	if not total_cutting:
		return None

	settings = frappe.get_cached_doc("MRP Settings")
	total_dispatched_pieces = get_finishing_dispatch_totals(finishing_doc).total_dispatched_pieces

	if total_dispatched_pieces > 0:
		disp_pct = (total_dispatched_pieces / total_cutting) * 100.0
		disp_threshold = flt(settings.partially_dispatched_percentage) or 0
		if disp_pct < disp_threshold:
			return "Partially Dispatched"
		if disp_pct > FULLY_DISPATCHED_PCT:
			unaccountable = _total_unaccountable(finishing_doc)
			if unaccountable is not None and unaccountable == 0:
				return "Fully Dispatched"
		return "Dispatched"

	if not total_received:
		return None
	recv_pct = (total_received / total_cutting) * 100.0
	recv_threshold = flt(settings.partial_received_percentage) or 0
	return "Ready to Pack" if recv_pct >= recv_threshold else "Partially Received"


def apply_auto_fp_status(finishing_doc):
	new_status = compute_received_status(finishing_doc)
	if not new_status:
		return
	current = finishing_doc.fp_status or ""
	if current in AUTO_FP_STATUSES:
		finishing_doc.fp_status = new_status


@frappe.whitelist()
def get_p_and_l_documents(doc_name):
	return frappe.get_all(
		"P and L Document",
		filters={"against": "Finishing Plan", "against_id": doc_name},
		fields=["name", "file", "comments", "modified", "owner"],
		order_by="creation desc",
	)


@frappe.whitelist()
def add_p_and_l_document(doc_name, file_url, comments=None):
	if not frappe.db.exists("Finishing Plan", doc_name):
		frappe.throw(f"Finishing Plan {doc_name} not found")
	pld = frappe.new_doc("P and L Document")
	pld.against = "Finishing Plan"
	pld.against_id = doc_name
	pld.file = file_url
	pld.comments = comments
	pld.insert(ignore_permissions=True)
	return pld.name


@frappe.whitelist()
def delete_p_and_l_document(name):
	pld = frappe.get_doc("P and L Document", name)
	if pld.against != "Finishing Plan":
		frappe.throw("Not a Finishing Plan P&L document")
	frappe.delete_doc("P and L Document", name, ignore_permissions=True)
	return True


@frappe.whitelist()
def approve_ocr_request(doc_name):
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only System Manager can approve OCR requests.")
	doc = frappe.get_doc("Finishing Plan", doc_name)
	if doc.fp_status != "OCR Requested":
		frappe.throw(f"Finishing Plan is not in OCR Requested state (current: {doc.fp_status}).")
	doc.fp_status = "OCR Completed"
	doc.save(ignore_permissions=True)
	return {"fp_status": doc.fp_status}


@frappe.whitelist()
def complete_ocr(doc_name):
	doc = frappe.get_doc("Finishing Plan", doc_name)
	unaccountable = _total_unaccountable(doc)
	if unaccountable is None:
		frappe.throw("Unable to compute unaccountable pieces. Please check the OCR tab.")
	new_status = "OCR Completed" if unaccountable == 0 else "OCR Requested"
	doc.fp_status = new_status
	doc.save(ignore_permissions=True)
	return {"fp_status": new_status, "unaccountable": unaccountable}
