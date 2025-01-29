# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt, nowdate, nowtime
from production_api.api.stock import get_default_fg_lot
from frappe import _
from production_api.mrp_stock.utils import get_stock_balance


class StockReservationEntry(Document):
	def validate(self) -> None:
		self.validate_mandatory()
		self.validate_uom_is_integer()
  
	def on_submit(self) -> None:
		self.update_status()
		self.update_reserved_stock_in_bin()
	
	def on_update_after_submit(self) -> None:
		self.can_be_updated()
		self.validate_uom_is_integer()
		self.update_status()
		self.update_reserved_stock_in_bin()
		self.reload()

	def on_cancel(self) -> None:
		self.update_status()
		self.update_reserved_stock_in_bin()
 
	def validate_mandatory(self) -> None:
		"""Raises an exception if mandatory fields are not set."""

		mandatory = [
			"item_code",
			"warehouse",
			"voucher_type",
			"voucher_no",
			"received_type",
			"lot",
			"available_qty",
			"stock_uom",
			"reserved_qty",
		]
		for d in mandatory:
			if not self.get(d):
				msg = _("{0} is required").format(self.meta.get_label(d))
				frappe.throw(msg)
    
	def validate_uom_is_integer(self) -> None:
		"""Validates `Reserved Qty` with Stock UOM."""

		if cint(frappe.db.get_value("UOM", self.stock_uom, "must_be_whole_number", cache=True)):
			if cint(self.reserved_qty) != flt(self.reserved_qty, self.precision("reserved_qty")):
				msg = _(
					"Reserved Qty ({0}) cannot be a fraction. To allow this, disable '{1}' in UOM {3}."
				).format(
					flt(self.reserved_qty, self.precision("reserved_qty")),
					frappe.bold(_("Must be Whole Number")),
					frappe.bold(self.stock_uom),
				)
				frappe.throw(msg)
	
	def update_status(self, status: str | None = None, update_modified: bool = True) -> None:
		"""Updates status based on Voucher Qty, Reserved Qty and Delivered Qty."""
		if not self.delivered_qty :
			self.delivered_qty = 0
		if not self.reserved_qty:
			self.reserved_qty = 0
		if self.delivered_qty > self.reserved_qty :
			frappe.throw("Can't Deliver More Than Required")
		if not status:
			if self.docstatus == 2:
				status = "Cancelled"
			elif self.docstatus == 1:
				if self.reserved_qty == self.delivered_qty:
					status = "Delivered"
				elif self.delivered_qty and self.delivered_qty < self.reserved_qty:
					status = "Partially Delivered"
				elif self.reserved_qty == self.voucher_qty:
					status = "Reserved"
				else:
					status = "Partially Reserved"
			else:
				status = "Draft"

		frappe.db.set_value(self.doctype, self.name, "status", status, update_modified=update_modified)
  
	def update_reserved_stock_in_bin(self) -> None:
		"""Updates `Reserved Stock` in Bin."""
		from production_api.utils import get_or_make_bin
		received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
		bin_name = get_or_make_bin(self.item_code, self.warehouse, self.lot, received_type)
		bin_doc = frappe.get_cached_doc("Bin", bin_name)
		bin_doc.update_reserved_stock()
	
	def can_be_updated(self) -> None:
		"""Raises an exception if `Stock Reservation Entry` is not allowed to be updated."""

		if self.status in ("Partially Delivered", "Delivered"):
			msg = _(
				"{0} {1} cannot be updated. If you need to make changes, we recommend canceling the existing entry and creating a new one."
			).format(self.status, self.doctype)
			frappe.throw(msg)

		if self.delivered_qty > 0:
			msg = _("Stock Reservation Entry cannot be updated as it has been delivered.")
			frappe.throw(msg)

def create_stock_reservation_entries_for_so_items(
    voucher_type,
	voucher_no,
	items_details,
) -> None:
	received_type = frappe.db.get_single_value("Stock Settings","default_received_type")	
	
	"""Creates Stock Reservation Entries for Sales Order Items."""


	from production_api.utils import get_unreserved_qty
	from production_api.mrp_stock.doctype.stock_entry.stock_entry import get_uom_details
 
	warning_msg = ""

	if len(items_details) == 0:
		return {
			"status" : 422,
			"error" : True,
			"message" : "Stock Allocation Requires Items",
			"warning" : warning_msg
		}
	common_item_map = {}
	voucher_detail_dict = {}
	
	for item in items_details:
		
		if item.get("item_name") not in common_item_map:
			common_item_map[item.get("item_name")] = {
				"item_name" : item.get("item_name"),
				"voucher_detail_no" : item.get("uuid"),
				"qty_to_reserve" : 0,
				"lot" : get_default_fg_lot(),
				"received_type":received_type,
				"uom" : item.get('uom'),
				'warehouse' : item.get('warehouse')
			}
		common_item_map[item.get("item_name")]['qty_to_reserve'] += flt(item.get("qty"))

		has_error = False
		error_str = ""

		if item.get("uom") != common_item_map[item.get('item_name')]['uom'] :
			error_str += "<br>UOM Can't Be Different"
			has_error = True

		if item.get("warehouse") != common_item_map[item.get('item_name')]['warehouse']:
			error_str += "<br>Warehouse Can't Be Different"
			has_error = True
		
		if has_error:
			return {
			"status" : 422,
			"error" : True,
			"message" : error_str,
			"warning" : warning_msg
		}
		
	# reserved_qty_details = get_sre_reserved_qty_details_for_voucher(voucher_type, voucher_no)
	savepoint = f"srecreate"
	frappe.db.savepoint(savepoint)
 
	response_dict = {}
	out_of_stock_items = set()

	for item_name, item in common_item_map.items() :

		unreserved_qty = get_unreserved_qty(item)

		if unreserved_qty <= 0:
			out_of_stock_items.add(item_name)

		available_qty_to_reserve = get_available_qty_to_reserve(item_name, item['warehouse'], item['lot'], received_type)

		if available_qty_to_reserve <= 0:
	
			out_of_stock_items.add(item['item_name'])

		qty_to_be_reserved = min(unreserved_qty, available_qty_to_reserve)
		item_uom_detail = get_uom_details(item_name, item['uom'], item['qty_to_reserve'])
		item['qty_to_reserve'] = item_uom_detail.get("conversion_factor") * item['qty_to_reserve']

		
		if item['qty_to_reserve'] <= 0:
			frappe.db.rollback()
			return {
				"status" : 422,
				"error" : True,
				"message" : f"Quantity Can't Be Zero For Item {item['item_name']}"
			}

		if item['qty_to_reserve'] > qty_to_be_reserved:
			out_of_stock_items.add(item['item_name'])
	if len(out_of_stock_items) > 0:
		frappe.db.rollback()
		return {
			"status" : 422,
			"error" : True,
			"message" : "Stock Not Available For Items <br>"+"<br>".join(list(out_of_stock_items)),
			"warning" : warning_msg
		}
	for item_name, item in common_item_map.items():
		available_qty_to_reserve = get_available_qty_to_reserve(item_name, item['warehouse'], item['lot'], received_type)
		sre = frappe.new_doc("Stock Reservation Entry")
		sre.item_code = item_name
		sre.warehouse = item['warehouse']
		sre.received_type = received_type
		sre.lot = item['lot']
		sre.voucher_type = voucher_type
		sre.voucher_no = voucher_no
		sre.voucher_detail_no = item['voucher_detail_no']
		sre.available_qty = available_qty_to_reserve
		
		sre.stock_uom = item_uom_detail.get('stock_uom')
		sre.reserved_qty = item['qty_to_reserve']
		sre.voucher_qty = sre.reserved_qty
		sre.save()
		sre.submit()
		voucher_detail_dict[item_name] = sre.name


	for item in items_details:
		response_dict[item.get('uuid')] = voucher_detail_dict[item.get('item_name')]  
	return response_dict
	

def get_sre_reserved_qty_details_for_voucher(voucher_type: str, voucher_no: str) -> dict:
	"""Returns a dict like {"voucher_detail_no": "reserved_qty", ... }."""

	sre = frappe.qb.DocType("Stock Reservation Entry")
	data = (
		frappe.qb.from_(sre)
		.select(
			sre.voucher_detail_no,
			(Sum(sre.reserved_qty) - Sum(sre.delivered_qty)).as_("reserved_qty"),
		)
		.where(
			(sre.docstatus == 1)
			& (sre.voucher_type == voucher_type)
			& (sre.voucher_no == voucher_no)
			& (sre.status.notin(["Delivered", "Cancelled"]))
		)
		.groupby(sre.voucher_detail_no)
	).run(as_list=True)

	data =  frappe._dict(data)
	return data

def get_available_qty_to_reserve(
	item_code: str, warehouse: str,lot :str, received_type: str,ignore_sre=None
) -> float:
	"""Returns `Available Qty to Reserve (Actual Qty - Reserved Qty)` for Item, Warehouse and Batch combination."""
 
	available_qty = get_stock_balance(item_code,warehouse=warehouse,received_type=received_type,lot=lot)

	if available_qty:
		sre = frappe.qb.DocType("Stock Reservation Entry")
		query = (
			frappe.qb.from_(sre)
			.select(Sum(sre.reserved_qty - sre.delivered_qty))
			.where(
				(sre.docstatus == 1)
				& (sre.item_code == item_code)
				& (sre.warehouse == warehouse)
				& (sre.received_type == received_type)
				& (sre.reserved_qty >= sre.delivered_qty)
				& (sre.status.notin(["Delivered", "Cancelled"]))
			)
		)

		if ignore_sre:
			query = query.where(sre.name != ignore_sre)

		reserved_qty = query.run()[0][0] or 0.0

		if reserved_qty:
			return available_qty - reserved_qty

	return available_qty

def get_sre_reserved_qty_for_item_and_warehouse(item_code: str, warehouse: str | None = None, lot: str | None = None, received_type : str | None = None) -> float:
	"""Returns current `Reserved Qty` for Item and Warehouse combination."""

	sre = frappe.qb.DocType("Stock Reservation Entry")
	query = (
		frappe.qb.from_(sre)
		.select(Sum(sre.reserved_qty - sre.delivered_qty).as_("reserved_qty"))
		.where(
			(sre.docstatus == 1)
			& (sre.item_code == item_code)
			& (sre.status.notin(["Delivered", "Cancelled"]))
		)
		.groupby(sre.item_code, sre.warehouse, sre.lot, sre.received_type)
	)

	if warehouse:
		query = query.where(sre.warehouse == warehouse)
	if lot:
		query = query.where(sre.lot == lot)
	if received_type:
		query = query.where(sre.received_type == received_type)

	reserved_qty = query.run(as_list=True)
	return flt(reserved_qty[0][0]) if reserved_qty else 0.0

def cancel_stock_reservation_entries(
	voucher_type: str | None = None,
	voucher_no: str | None = None,
	sre_list: list | None = None,
	notify: bool = True,
) -> None:
	"""Cancel Stock Reservation Entries."""

	if not sre_list:
		sre_list = {}

		if voucher_type and voucher_no:
			sre_list = get_stock_reservation_entries_for_voucher(
				voucher_type, voucher_no, fields=["name"]
			)


		sre_list = [d.name for d in sre_list]

	if sre_list:
		for sre in sre_list:
			frappe.get_doc("Stock Reservation Entry", sre).cancel()

		if notify:
			msg = _("Stock Reservation Entries Cancelled")
			frappe.msgprint(msg, alert=True, indicator="red")

@frappe.whitelist()
def get_stock_reservation_entries_for_voucher(
	voucher_type: str,
	voucher_no: str,
	voucher_detail_no: str | None = None,
	fields: list[str] | None = None,
	ignore_status: bool = False,
) -> list[dict]:
	"""Returns list of Stock Reservation Entries against a Voucher."""

	if not fields or not isinstance(fields, list):
		fields = [
			"name",
			"item_code",
			"warehouse",
			"lot",
			"receive_type",
			"reserved_qty",
			"delivered_qty",
		]

	sre = frappe.qb.DocType("Stock Reservation Entry")
	query = (
		frappe.qb.from_(sre)
		.where((sre.docstatus == 1) & (sre.voucher_type == voucher_type) & (sre.voucher_no == voucher_no))
		.orderby(sre.creation)
	)

	for field in fields:
		query = query.select(sre[field])

	if voucher_detail_no:
		query = query.where(sre.voucher_detail_no == voucher_detail_no)

	if ignore_status:
		query = query.where(sre.status.notin(["Delivered", "Cancelled"]))

	return query.run(as_dict=True)

def update_stock_reservation_entries(voucher_type, voucher_no, item_details):
    
    cancel_stock_reservation_entries(voucher_type,voucher_no)
    
    return create_stock_reservation_entries_for_so_items(voucher_type, voucher_no,item_details)