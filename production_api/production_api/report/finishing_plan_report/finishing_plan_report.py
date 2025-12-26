# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from production_api.utils import get_variant_attr_details

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"fieldname": "item",
			"fieldtype": "Link",
			"label": "Style",
			"options": "Item",
		},
		{
			"fieldname": "description",
			"fieldtype": "Data",
			"label": "Description",
		},
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"label": "Lot",
			"options": "Lot",
		},
		{
			"fieldname": "pieces_per_box",
			"fieldtype": "Int",
			"label": "Pieces Per Box"
		},
		{
			"fieldname": "cut_qty",
			"fieldtype": "Int",
			"label": "Cut Qty",
		},
		{
			"fieldname": "sewing_received",
			"fieldtype": "Int",
			"label": "Sewing Received",
		},
		{
			"fieldname": "sewing_diff",
			"fieldtype": "Int",
			"label": "Sewing Difference",
		},
		{
			"fieldname": "old_lot",
			"fieldtype": "Int",
			"label": "Old Lot",
		},
		{
			"fieldname": "ironing_excess",
			"fieldtype": "Int",
			"label": "Ironing Excess",
		},
		{
			"fieldname": "finishing_inward",
			"fieldtype": "Int",
			"label": "Finishing Inward",
		},
		{
			"fieldname": "cut_to_finishing_diff",
			"fieldtype": "Int",
			"label": "Cut to Finishing Inward Difference",
		},
		{
			"fieldname": "dispatch_box_qty",
			"fieldtype": "Int",
			"label": "Dispatch ",
			"options": "",
		},
		{
			"fieldname": "dispatch_piece_qty",
			"fieldtype": "Int",
			"label": "Dispatch Piece Qty",
		},
		{
			"fieldname": "unaccountable",
			"fieldtype": "Int",
			"label": "Unaccountable",
		},
		{
			"fieldname": "unaccountable_percentage",
			"fieldtype": "Percent",
			"label": "Unaccountable Percentage",
		},
		{
			"fieldname": "loose_piece",
			"fieldtype": "Int",
			"label": "Loose Piece",
		},
		{
			"fieldname": "rejection",
			"fieldtype": "Int",
			"label": "Rejection",
		},
		{
			"fieldname": "rework",
			"fieldtype": "Int",
			"label": "Rework",
		},
		{
			"fieldname": "cut_to_dispatch_diff",
			"fieldtype": "Int",
			"label": "Cut to Dispatch Difference",
			"options": "",
		},
		{
			"fieldname": "cut_to_dispatch_diff_percent",
			"fieldtype": "Percent",
			"label": "Cut to Dispatch Difference Percentage",
		},
		{
			"fieldname": "finishing_inward_to_dispatch_diff",
			"fieldtype": "Int",
			"label": "Finishing Inward to Dispatch Difference",
		},
		{
			"fieldname": "finishing_inward_to_dispatch_diff_percent",
			"fieldtype": "Percent",
			"label": "Finishing Inward to Dispatch Difference Percentage",
		},
	]

def get_data(filters):
	data = []
	fil = {}
	if filters.get('lot'):
		fil['lot'] = filters.get('lot')
	if filters.get('item'):
		fil['item'] = filters.get('item')
	if filters.get('season'):
		lot_list = frappe.get_all("Lot", filters={"season": filters.get('season')}, pluck="name")			
		fil['lot'] = ['in', lot_list]

	fp_list = frappe.get_all("Finishing Plan",filters=fil, pluck="name")
	for fp_name in fp_list:
		fp_doc = frappe.get_doc("Finishing Plan", fp_name)
		d = {
			"item": fp_doc.item,
			"lot": fp_doc.lot,
			"pieces_per_box": fp_doc.pieces_per_box,
		}
		if fp_doc.is_set_item:
			set_dict = {}
			set_attr = frappe.get_value("Item Production Detail", fp_doc.production_detail, "set_item_attribute")
			for row in fp_doc.finishing_plan_details:
				attrs = get_variant_attr_details(row.item_variant)
				set_attr_value = attrs[set_attr]
				set_dict.setdefault(set_attr_value, {
					"item": fp_doc.item,
					"lot": fp_doc.lot,
					"pieces_per_box": fp_doc.pieces_per_box,
					"description": set_attr_value,
					"cut_qty" : 0,
					"sewing_received" : 0,
					"sewing_diff" : 0,
					"old_lot" : 0,
					"ironing_excess" : 0,
					"finishing_inward" : 0,
					"loose_piece" : 0,
					"cut_to_finishing_diff" : 0,
					"dispatch_box_qty" : 0,
					"dispatch_piece_qty" : 0,
					"cut_to_dispatch_diff" : 0,
					"finishing_inward_to_dispatch_diff" : 0,
					"rejection" : 0,
					"rework" : 0,
					"unaccountable": 0,
					"cut_to_dispatch_diff_percent": 0,
				})
				set_dict[set_attr_value]['cut_qty'] += row.cutting_qty
				set_dict[set_attr_value]['sewing_received'] += row.delivered_quantity
				set_dict[set_attr_value]['old_lot'] += row.lot_transferred
				set_dict[set_attr_value]['ironing_excess'] += row.ironing_excess
				set_dict[set_attr_value]['loose_piece'] += (row.return_qty + row.pack_return_qty)
				set_dict[set_attr_value]['finishing_inward'] += row.dc_qty

			for row in fp_doc.finishing_plan_reworked_details:
				attrs = get_variant_attr_details(row.item_variant)
				set_attr_value = attrs[set_attr]	
				set_dict[set_attr_value]['rejection'] += row.rejected_qty
				set_dict[set_attr_value]['rework'] += ( row.quantity - (row.reworked_quantity + row.rejected_qty) )

			for row in fp_doc.finishing_plan_grn_details:
				for set_key in set_dict:
					set_dict[set_key]['dispatch_box_qty'] += row.dispatched
					set_dict[set_key]['dispatch_piece_qty'] +=  (row.dispatched * fp_doc.pieces_per_box)

			for set_key in set_dict:
				set_dict[set_key]['sewing_diff'] = set_dict[set_key]['sewing_received'] - set_dict[set_key]['cut_qty']
				set_dict[set_key]['cut_to_finishing_diff'] = set_dict[set_key]['finishing_inward'] - set_dict[set_key]['cut_qty']
				set_dict[set_key]['cut_to_dispatch_diff'] = set_dict[set_key]['dispatch_piece_qty'] - set_dict[set_key]['cut_qty']
				set_dict[set_key]['finishing_inward_to_dispatch_diff'] = set_dict[set_key]['dispatch_piece_qty'] - set_dict[set_key]['finishing_inward']
				sum1 = set_dict[set_key]['dispatch_piece_qty'] + set_dict[set_key]['rejection'] +set_dict[set_key]['loose_piece'] + set_dict[set_key]['rework']
				sum2 = set_dict[set_key]['sewing_received'] + set_dict[set_key]['old_lot'] + set_dict[set_key]['ironing_excess']
				set_dict[set_key]['unaccountable'] = sum1 - sum2
				if sum1 != 0:
					set_dict[set_key]['unaccountable_percentage'] = 100 - round(sum2 / sum1, 2)
				else:
					set_dict[set_key]['unaccountable_percentage'] = 100

				sum1 = set_dict[set_key]['cut_qty'] + set_dict[set_key]['old_lot'] + set_dict[set_key]['ironing_excess']
				if sum1 != 0:
					set_dict[set_key]['cut_to_dispatch_diff_percent'] = 100 - round(set_dict[set_key]['dispatch_piece_qty'] / sum1, 2)
				else:
					set_dict[set_key]['cut_to_dispatch_diff_percent'] = 100	 
				sum1 = set_dict[set_key]['sewing_received'] + set_dict[set_key]['old_lot'] + set_dict[set_key]['ironing_excess']
				if sum1 != 0:
					set_dict[set_key]['finishing_inward_to_dispatch_diff_percent'] = 100 - round(set_dict[set_key]['dispatch_piece_qty'] / sum1, 2)
				else:
					set_dict[set_key]['finishing_inward_to_dispatch_diff_percent'] = 100

			for set_key in set_dict:
				data.append(set_dict[set_key])

		else:	
			fp_detail_data = frappe.db.sql(
				f"""
					SELECT SUM(cutting_qty) AS cut_qty, SUM(delivered_quantity) AS sewing_received,
					sum(dc_qty) as dc_qty, SUM(lot_transferred) as old_lot, SUM(ironing_excess) as ironing_excess,
					SUM(return_qty) + SUM(pack_return_qty) AS loose_piece 
					FROM `tabFinishing Plan Detail` WHERE parent = {frappe.db.escape(fp_name)}
				""", as_dict=True
			)
			d['cut_qty'] = fp_detail_data[0]['cut_qty']
			d['sewing_received'] = fp_detail_data[0]['sewing_received']
			d['sewing_diff'] = fp_detail_data[0]['sewing_received'] - fp_detail_data[0]['cut_qty']
			d['old_lot'] = fp_detail_data[0]['old_lot']
			d['ironing_excess'] = fp_detail_data[0]['ironing_excess']
			d['finishing_inward'] = fp_detail_data[0]['dc_qty']
			d['loose_piece'] = fp_detail_data[0]['loose_piece']
			d['cut_to_finishing_diff'] = fp_detail_data[0]['dc_qty'] - fp_detail_data[0]['cut_qty']
			dispatch_detail = frappe.db.sql(
				f"""
					SELECT sum(dispatched) as dispatched_box FROM `tabFinishing Plan GRN Detail`
					WHERE parent = {frappe.db.escape(fp_name)} 
				""", as_dict=True
			)
			d['dispatch_box_qty'] = dispatch_detail[0]['dispatched_box']
			d['dispatch_piece_qty'] = dispatch_detail[0]['dispatched_box'] * fp_doc.pieces_per_box
			d['cut_to_dispatch_diff'] = (dispatch_detail[0]['dispatched_box'] * fp_doc.pieces_per_box) - fp_detail_data[0]['cut_qty']
			d['finishing_inward_to_dispatch_diff'] = (dispatch_detail[0]['dispatched_box'] * fp_doc.pieces_per_box) - fp_detail_data[0]['dc_qty']
			rework_detail = frappe.db.sql(
				f"""
					SELECT SUM(quantity) as rework_quantity, SUM(reworked_quantity) as reworked,
					SUM(rejected_qty) as rejected FROM `tabFinishing Plan Reworked Detail`
					WHERE parent = {frappe.db.escape(fp_name)}
				""", as_dict=True
			)
			d['rejection'] = rework_detail[0].get('rejected') or 0
			d['rework'] = (
				(rework_detail[0].get('rework_quantity') or 0)
				- (rework_detail[0].get('reworked') or 0)
				- (rework_detail[0].get('rejected') or 0)
			)
			sum1 = d['dispatch_piece_qty'] + d['rejection'] + d['loose_piece'] +d['rework']
			sum2 = d['sewing_received'] + d['old_lot'] + d['ironing_excess']
			d['unaccountable'] = sum1 - sum2
			if sum1 != 0:
				d['unaccountable_percentage'] = 100 - round(sum2 / sum1, 2)
			else:
				d['unaccountable_percentage'] = 100	
			sum1 = d['cut_qty'] + d['old_lot'] + d['ironing_excess']
			if sum1 != 0:
				d['cut_to_dispatch_diff_percent'] = 100 - round(d['dispatch_piece_qty'] / sum1, 2)
			else:
				d['cut_to_dispatch_diff_percent'] = 100

			sum1 = d['sewing_received'] + d['old_lot'] + d['ironing_excess']
			if sum1 != 0:
				d['finishing_inward_to_dispatch_diff_percent'] = 100 - round(d['dispatch_piece_qty'] / sum1, 2)
			else:
				d['finishing_inward_to_dispatch_diff_percent'] = 100

			data.append(d)
	return data				

