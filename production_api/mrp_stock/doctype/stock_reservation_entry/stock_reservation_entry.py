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
		bin_name = get_or_make_bin(self.item_code, self.warehouse, self.lot)
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
	items = []
	if items_details:
		for item in items_details:
			
			ps_item = {}
			ps_item['item_name'] = item.get("item_name")
			ps_item['warehouse'] = item.get("warehouse")
			ps_item['voucher_detail_no'] = item.get("uuid")
			ps_item['lot'] = get_default_fg_lot()
			ps_item['uom'] = item.get("uom")
			ps_item['qty_to_reserve'] = (
				flt(item.get("qty"))
			)

			items.append(ps_item)
	reserved_qty_details = get_sre_reserved_qty_details_for_voucher(voucher_type, voucher_no)
	
	savepoint = f"srecreate"
	frappe.db.savepoint(savepoint)
 
	response_dict = {}
	out_of_stock_items = set()
	item_quantity_dict = {}
	for item in items :

		unreserved_qty = get_unreserved_qty(item, reserved_qty_details)

		if unreserved_qty <= 0:
			out_of_stock_items.add(item['item_name'])

		available_qty_to_reserve = get_available_qty_to_reserve(item['item_name'], item['warehouse'], item['lot'])

		if available_qty_to_reserve <= 0:
	
			out_of_stock_items.add(item['item_name'])

		qty_to_be_reserved = min(unreserved_qty, available_qty_to_reserve)
		item_details = get_uom_details(item['item_name'], item['uom'], item['qty_to_reserve'])
		item_quantity_dict[item['item_name']] = item_details
		item['qty_to_reserve'] = item_details.get("conversion_factor") * item['qty_to_reserve']

		if 'qty_to_reserve' in item:
			if item['qty_to_reserve'] <= 0:
				warning_msg += f"""<br> Quantity to reserve for the Item {item['item_name']} should be greater than 0."""
				continue

		if item['qty_to_reserve'] > qty_to_be_reserved:
	
			out_of_stock_items.add(item['item_name'])
		else:
			qty_to_be_reserved = min(qty_to_be_reserved, item['qty_to_reserve'])
	
	if len(out_of_stock_items) > 0:
		frappe.db.rollback()
		return {
			"status" : 422,
			"error" : True,
			"message" : "Stock Not Available For Items <br>"+"<br>".join(list(out_of_stock_items)),
			"warning" : warning_msg
		}

	for item in items:
		sre = frappe.new_doc("Stock Reservation Entry")

		sre.item_code = item['item_name']
		sre.warehouse = item['warehouse']
		sre.lot = item['lot']
		item_details = item_quantity_dict[item['item_name']]
		sre.voucher_type = voucher_type
		sre.voucher_no = voucher_no
		sre.voucher_detail_no = item['voucher_detail_no']
		sre.available_qty = available_qty_to_reserve
		
		sre.stock_uom = item_details.get('stock_uom')
		sre.reserved_qty = item['qty_to_reserve']
		sre.voucher_qty = sre.reserved_qty
		sre.save()
		sre.submit()
		response_dict[item['voucher_detail_no']] = sre.name
  
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
	item_code: str, warehouse: str,lot :str, ignore_sre=None
) -> float:
	"""Returns `Available Qty to Reserve (Actual Qty - Reserved Qty)` for Item, Warehouse and Batch combination."""
 
	available_qty = get_stock_balance(item_code,warehouse=warehouse,lot=lot)

	if available_qty:
		sre = frappe.qb.DocType("Stock Reservation Entry")
		query = (
			frappe.qb.from_(sre)
			.select(Sum(sre.reserved_qty - sre.delivered_qty))
			.where(
				(sre.docstatus == 1)
				& (sre.item_code == item_code)
				& (sre.warehouse == warehouse)
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

def get_sre_reserved_qty_for_item_and_warehouse(item_code: str, warehouse: str | None = None, lot: str | None = None) -> float:
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
		.groupby(sre.item_code, sre.warehouse, sre.lot)
	)

	if warehouse:
		query = query.where(sre.warehouse == warehouse)
	if lot:
		query = query.where(sre.lot == lot)

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