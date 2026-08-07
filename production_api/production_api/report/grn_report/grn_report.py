# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint

from production_api.dynamic_packing import packing_batch_label

def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_data(filters):
	filters = frappe._dict(filters or {})
	d = {}
	conditions = ""
	if filters.from_date:
		conditions += f" AND t2.posting_date >= %(from_date)s"
		d['from_date'] = filters.from_date

	if filters.to_date:
		conditions += f" AND t2.posting_date <= %(to_date)s"
		d['to_date'] = filters.to_date

	if filters.lot:
		conditions += f" AND t2.lot = %(lot)s"
		d['lot'] = filters.lot	

	if filters.supplier:
		conditions += f" AND t2.supplier = %(supplier)s"
		d['supplier'] = filters.supplier		

	if filters.delivery_location:
		conditions += f" AND t2.delivery_location = %(delivery_location)s"
		d['delivery_location'] = filters.delivery_location		 

	data = frappe.db.sql(
		f"""
			SELECT t2.name as goods_received_note, t2.supplier, t2.supplier_name, t2.delivery_location, 
			t2.delivery_location_name, t2.lot, t2.process_name, t1.item_variant, t1.quantity, t1.uom,
			t1.received_type, t2.packing_calculation_version, t2.total_packing_boxes,
			t2.total_packing_pieces
			FROM `tabGoods Received Note Item` as t1 JOIN `tabGoods Received Note` as t2 ON t2.name = t1.parent 
			WHERE t2.against = 'Work Order' AND t2.docstatus = 1 AND t1.quantity > 0 {conditions}
		""", d, as_dict=True
	)
	batches_by_grn = {}
	dynamic_grns = [
		row.goods_received_note for row in data
		if cint(row.packing_calculation_version) >= 2
	]
	if dynamic_grns:
		for batch in frappe.get_all(
			"GRN Packing Batch",
			filters={"parent": ["in", list(set(dynamic_grns))]},
			fields=[
				"parent", "batch_id", "colour", "box_quantity", "pieces_per_box",
				"total_pieces", "ratio_json",
			],
			order_by="parent, idx",
		):
			label = (
				f"{batch.batch_id}: {packing_batch_label(batch)} · "
				f"{cint(batch.box_quantity)} boxes / {cint(batch.total_pieces)} pieces"
			)
			batches_by_grn.setdefault(batch.parent, []).append(label)

	shown_batch_totals = set()
	for row in data:
		item = frappe.get_cached_value("Item Variant", row['item_variant'], "item")
		row['item'] = item
		if (
			cint(row.packing_calculation_version) >= 2
			and row.goods_received_note not in shown_batch_totals
		):
			row['packing_ratio_details'] = "\n".join(
				batches_by_grn.get(row.goods_received_note, [])
			)
			shown_batch_totals.add(row.goods_received_note)
		elif cint(row.packing_calculation_version) >= 2:
			# GRN rows are size-wise; show physical batch totals once so exports do not
			# accidentally multiply the same boxes and pieces by the number of sizes.
			row['total_packing_boxes'] = None
			row['total_packing_pieces'] = None
			row['packing_ratio_details'] = ""
		else:
			row['packing_ratio_details'] = ""
		
	return data

def get_columns():
	return [
		{"fieldname": "goods_received_note","fieldtype": "Link","options": "Goods Received Note", 
   			"label": "Goods Received Note", "width": 100},
		{"fieldname": "supplier","fieldtype": "Link","options": "Supplier","label": "Supplier", "width": 100},
		{"fieldname": "supplier_name","fieldtype": "Data","label": "Supplier Name", "width": 150},
		{"fieldname": "delivery_location","fieldtype": "Link","options": "Supplier","label": "Delivery Location", "width": 100},
		{"fieldname": "delivery_location_name","fieldtype": "Data","label": "Delivery Location Name", "width": 150},
		{"fieldname": "lot","fieldtype": "Link","options": "Lot","label": "Lot", "width": 100},
		{"fieldname": "process_name","fieldtype": "Link","options": "Process","label": "Process", "width": 100},
		{"fieldname": "item","fieldtype": "Link","options": "Item","label": "Item", "width": 200},
		{"fieldname": "item_variant","fieldtype": "Link","options": "Item Variant","label": "Item Variant", "width": 200},
		{"fieldname": "quantity","fieldtype": "Float","label": "Quantity", "width": 100},
		{"fieldname": "total_packing_boxes", "fieldtype": "Int", "label": "Packing Boxes", "width": 110},
		{"fieldname": "total_packing_pieces", "fieldtype": "Int", "label": "Packing Pieces", "width": 110},
		{"fieldname": "packing_ratio_details", "fieldtype": "Small Text", "label": "Packing Ratios", "width": 320},
		{"fieldname": "received_type","fieldtype": "Link","options": "GRN Item Type","label": "Received Type", "width": 100},
		{"fieldname": "uom","fieldtype": "Link","options": "UOM","label": "UOM", "width": 100},
	]
