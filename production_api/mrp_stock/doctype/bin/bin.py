# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe.query_builder.functions import Coalesce, CombineDatetime, Sum
from frappe.query_builder import Case, Order


class Bin(Document):
    
	def before_save(self):
		if self.get("__islocal") or not self.stock_uom:
			o_item = frappe.get_cached_value("Item Variant",self.item_code,"item")
			self.stock_uom = frappe.get_cached_value("Item", o_item, "default_unit_of_measure")
  
	def update_reserved_stock(self):
		"""Update `Reserved Stock` on change in Reserved Qty of Stock Reservation Entry"""

		from production_api.mrp_stock.doctype.stock_reservation_entry.stock_reservation_entry import (
			get_sre_reserved_qty_for_item_and_warehouse,
		)

		reserved_stock = get_sre_reserved_qty_for_item_and_warehouse(self.item_code, self.warehouse, self.lot, self.received_type)
		if reserved_stock < 0:
			frappe.throw("Reserved Stock Can't Be Negative")
		if reserved_stock > self.actual_qty :
			frappe.throw("Reserved Stock Can't Be Greater Than The Current Stock")
		self.db_set("reserved_qty", flt(reserved_stock), update_modified=True)

def get_bin_details(bin_name):
	return frappe.db.get_value(
		"Bin",
		bin_name,
		[
			"actual_qty",
			"reserved_qty",
		],
		as_dict=1,
	)

def update_qty(bin_name, args):

	bin_details = get_bin_details(bin_name)
	actual_qty = bin_details.actual_qty or 0.0
	sle = frappe.qb.DocType("Stock Ledger Entry")

	last_sle_qty = (
		frappe.qb.from_(sle)
		.select(sle.qty_after_transaction)
		.where(
			(sle.item == args.get("item"))
			& (sle.warehouse == args.get("warehouse"))
			& (sle.lot == args.get("lot"))
			& (sle.received_type == args.get("received_type"))
			& (sle.is_cancelled == 0)
		)
		.orderby(CombineDatetime(sle.posting_date, sle.posting_time), order=Order.desc)
		.orderby(sle.creation, order=Order.desc)
		.limit(1)
		.run()
	)
	actual_qty = 0.0
	if last_sle_qty:
		actual_qty = last_sle_qty[0][0]

	frappe.db.set_value(
		"Bin",
		bin_name,
		{
			"actual_qty": actual_qty,
		},
		update_modified=True,
	)
 
def get_stock_balance_bin(warehouse, lot, item, received_type, remove_zero_balance_item = False):
    
    bin = frappe.qb.DocType("Bin")
    
    query = (
		frappe.qb.from_(bin)
		.select(
			bin.item_code.as_('item'),
			(bin.actual_qty - bin.reserved_qty).as_("bal_qty"),
			bin.stock_uom.as_("uom")
		)
		.where((bin.lot == lot))
	)
    
    if warehouse and len(warehouse) != 0:
        query = query.where(bin.warehouse.isin(warehouse))
    if received_type:
        query = query.where(bin.received_type == received_type)		
    if item and len(item) != 0:
        query = query.where(bin.item_code.isin(item))
        
    if remove_zero_balance_item:
        
        query = query.where((bin.actual_qty - bin.reserved_qty) > 0)
    
    return query.run(as_dict = True)

def on_doctype_update():
	if frappe.db.sql(
		f"""
			SELECT CONSTRAINT_NAME
			FROM information_schema.TABLE_CONSTRAINTS
			WHERE table_name= 'tabBin'
			AND constraint_type='UNIQUE'
			AND CONSTRAINT_NAME= 'unique_item_warehouse_lot'
		"""
	):
		frappe.db.sql(
			"""
				ALTER TABLE `tabBin` DROP CONSTRAINT `unique_item_warehouse_lot`;
			"""
		)
	frappe.db.add_unique("Bin", ["item_code", "warehouse", "lot", "received_type"], constraint_name="unique_item_warehouse_lot_type")