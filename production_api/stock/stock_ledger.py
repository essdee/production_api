import json
from typing import Set, Tuple

import frappe
from frappe import _
from frappe.utils import now, cint, flt, nowdate, get_link_to_form
from frappe.query_builder.functions import CombineDatetime
from production_api.production_api.doctype.item_price.item_price import get_item_variant_price
from production_api.stock.utils import get_incoming_outgoing_rate_for_cancel

from production_api.stock.valuation import FIFOValuation, round_off_if_near_zero


class NegativeStockError(frappe.ValidationError):
	pass


def make_sl_entries(sl_entries):
	"""Create SL entries from SL entry dicts"""

	if sl_entries:
		cancel = sl_entries[0].get("is_cancelled")
		if cancel:
			set_as_cancelled(sl_entries[0].get("voucher_type"), sl_entries[0].get("voucher_no"))
		
		for sle in sl_entries:
			if sle.get("voucher_type") != "Stock Reconciliation" and not sle["qty"]:
				continue
			if cancel:
				sle["qty"] = -flt(sle.get("qty"))

				if sle["qty"] < 0 and not sle.get("outgoing_rate"):
					sle["outgoing_rate"] = get_incoming_outgoing_rate_for_cancel(
						sle.item, sle.voucher_type, sle.voucher_no, sle.voucher_detail_no
					)
					sle["rate"] = 0.0

				if sle["qty"] > 0 and not sle.get("rate"):
					sle["rate"] = get_incoming_outgoing_rate_for_cancel(
						sle.item, sle.voucher_type, sle.voucher_no, sle.voucher_detail_no
					)
					sle["outgoing_rate"] = 0.0

			if sle.get("qty") or sle.get("voucher_type") == "Stock Reconciliation":
				sle_doc = make_entry(sle)
			
			args = sle_doc.as_dict()

			if sle.get("voucher_type") == "Stock Reconciliation":
				# preserve previous_qty_after_transaction for qty reposting
				args.previous_qty_after_transaction = sle.get("previous_qty_after_transaction")

			item = frappe.get_cached_value("Item Variant", args.get("item"), "item")
			is_stock_item = frappe.get_cached_value("Item", item, "is_stock_item")
			if is_stock_item:
				repost_current_voucher(args)
			else:
				frappe.msgprint(
					_("Item {0} ignored since it is not a stock item").format(args.get("item"))
				)

def repost_current_voucher(args, allow_negative_stock=False, via_landed_cost_voucher=False):
	if args.get("qty") or args.get("voucher_type") == "Stock Reconciliation":
		if not args.get("posting_date"):
			args["posting_date"] = nowdate()

		if not (args.get("is_cancelled") and via_landed_cost_voucher):
			# Reposts only current voucher SL Entries
			# Updates valuation rate, stock value, stock queue for current transaction
			update_entries_after(
				{
					"item": args.get("item"),
					"warehouse": args.get("warehouse"),
					"lot": args.get("lot"),
					"posting_date": args.get("posting_date"),
					"posting_time": args.get("posting_time"),
					"voucher_type": args.get("voucher_type"),
					"voucher_no": args.get("voucher_no"),
					"sle_id": args.get("name"),
					"creation": args.get("creation"),
				},
				# allow_negative_stock=allow_negative_stock,
				# via_landed_cost_voucher=via_landed_cost_voucher,
			)

		# update qty in future sle and Validate negative qty
		# For LCV: update future balances with -ve LCV SLE, which will be balanced by +ve LCV SLE
		update_qty_in_future_sle(args, allow_negative_stock)

def make_entry(args, allow_negative_stock=False, via_landed_cost_voucher=False):
	args["doctype"] = "Stock Ledger Entry"
	sle = frappe.get_doc(args)
	sle.flags.ignore_permissions = 1
	# sle.allow_negative_stock = allow_negative_stock
	# sle.via_landed_cost_voucher = via_landed_cost_voucher
	sle.submit()
	return sle

def set_as_cancelled(voucher_type, voucher_no):
	frappe.db.sql(
		"""update `tabStock Ledger Entry` set is_cancelled=1,
		modified=%s, modified_by=%s
		where voucher_type=%s and voucher_no=%s and is_cancelled = 0""",
		(now(), frappe.session.user, voucher_type, voucher_no),
	)

def update_qty_in_future_sle(args, allow_negative_stock=False):
	"""Recalculate Qty after Transaction in future SLEs based on current SLE."""
	datetime_limit_condition = ""
	qty_shift = args.qty

	args["time_format"] = "%H:%i:%s"

	# find difference/shift in qty caused by stock reconciliation
	if args.voucher_type == "Stock Reconciliation":
		qty_shift = get_stock_reco_qty_shift(args)

	# find the next nearest stock reco so that we only recalculate SLEs till that point
	next_stock_reco_detail = get_next_stock_reco(args)
	if next_stock_reco_detail:
		detail = next_stock_reco_detail[0]
		# if detail.batch_no:
		# 	regenerate_sle_for_batch_stock_reco(detail)

		# add condition to update SLEs before this date & time
		datetime_limit_condition = get_datetime_limit_condition(detail)
	# frappe.db.sql(
	# 	f"""
	# 	update `tabStock Ledger Entry`
	# 	set qty_after_transaction = qty_after_transaction + {qty_shift}
	# 	where
	# 		item = %(item)s
	# 		and warehouse = %(warehouse)s
	# 		and voucher_no != %(voucher_no)s
	# 		and is_cancelled = 0
	# 		and (
	# 			posting_date > %(posting_date)s or
	# 			(
	# 				posting_date = %(posting_date)s and
	# 				time_format(posting_time, %(time_format)s) > time_format(%(posting_time)s, %(time_format)s)
	# 			)
	# 		)
	# 	{datetime_limit_condition}
	# 	""",
	# 	args,
	# )

	validate_negative_qty_in_future_sle(args, allow_negative_stock)

class update_entries_after(object):
	"""
	update valuation rate and qty after transaction
	from the current time-bucket onwards

	:param args: args as dict

	        args = {
	                "item": "ABC",
	                "warehouse": "XYZ",
                    "lot": "JKL",
	                "posting_date": "2012-12-12",
	                "posting_time": "12:00"
	        }
	"""
    
	def __init__(
		self,
		args,
		allow_zero_rate=False,
		# allow_negative_stock=None,
		verbose=1,
	):
		self.exceptions = {}
		self.verbose = verbose
		self.allow_zero_rate = allow_zero_rate
		self.item = args.get("item")
		# self.allow_negative_stock = allow_negative_stock or is_negative_stock_allowed(
		# 	item=self.item
		# )

		self.args = frappe._dict(args)
		if self.args.sle_id:
			self.args["name"] = self.args.sle_id

		# self.company = frappe.get_cached_value("Warehouse", self.args.warehouse, "company")
		self.set_precision()
		# Valuation method is always FIFO
		self.valuation_method = "FIFO"

		self.new_items_found = False
		self.distinct_item_warehouses = args.get("distinct_item_warehouses", frappe._dict())
		self.affected_transactions: Set[Tuple[str, str]] = set()

		self.data = frappe._dict()
		self.initialize_previous_data(self.args)
		self.build()
    
	def set_precision(self):
		self.flt_precision = cint(frappe.db.get_default("float_precision")) or 2
		self.currency_precision = 2

	def initialize_previous_data(self, args):
		"""
		Get previous sl entries for current item for each related warehouse and lot
		and assigns into self.data dict

		:Data Structure:

		self.data = {
		        (warehouse1, lot1): {
		                'previous_sle': {},
		                'qty_after_transaction': 10,
		                'valuation_rate': 100,
		                'stock_value': 1000,
		                'prev_stock_value': 1000,
		                'stock_queue': '[[10, 100]]',
		                'stock_value_difference': 1000
		        }
		}

		"""
		data_key = (args.warehouse, args.lot)
		self.data.setdefault(data_key, frappe._dict())
		warehouse_dict = self.data[data_key]
		previous_sle = get_previous_sle_of_current_voucher(args)
		warehouse_dict.previous_sle = previous_sle

		for key in ("qty_after_transaction", "valuation_rate", "stock_value"):
			setattr(warehouse_dict, key, flt(previous_sle.get(key)))

		warehouse_dict.update(
			{
				"prev_stock_value": previous_sle.stock_value or 0.0,
				"stock_queue": json.loads(previous_sle.stock_queue or "[]"),
				"stock_value_difference": 0.0,
			}
		)
	
	def build(self):
		entries_to_fix = self.get_future_entries_to_fix()
		i = 0
		while i < len(entries_to_fix):
			sle = entries_to_fix[i]
			i += 1
			self.process_sle(sle)
			# if sle.dependant_sle_voucher_detail_no:
				# entries_to_fix = self.get_dependent_entries_to_fix(entries_to_fix, sle)

		if self.exceptions:
			self.raise_exceptions()

	def get_future_entries_to_fix(self):
		# includes current entry!
		args = self.data[(self.args.warehouse, self.args.lot)].previous_sle or frappe._dict(
			{"item": self.item, "warehouse": self.args.warehouse, "lot": self.args.lot}
		)
		return list(self.get_sle_after_datetime(args))

	def get_sle_after_datetime(self, args):
		"""get Stock Ledger Entries after a particular datetime, for reposting"""
		return get_stock_ledger_entries(args, ">", "asc", for_update=True)

	def process_sle(self, sle):
		# previous sle data for this warehouse
		self.wh_data = self.data[(sle.warehouse, sle.lot)]
		self.affected_transactions.add((sle.voucher_type, sle.voucher_no))

		# if (sle.serial_no and not self.via_landed_cost_voucher) or not cint(self.allow_negative_stock):
		# 	# validate negative stock for serialized items, fifo valuation
		# 	# or when negative stock is not allowed for moving average
		if not self.validate_negative_stock(sle):
			self.wh_data.qty_after_transaction += flt(sle.qty)
			return

		# Get dynamic incoming/outgoing rate
		if not self.args.get("sle_id"):
			self.get_dynamic_incoming_outgoing_rate(sle)

		# if (
		# 	sle.voucher_type == "Stock Reconciliation"
		# 	and sle.voucher_detail_no
		# 	and sle.actual_qty < 0
		# ):
		# 	self.reset_actual_qty_for_stock_reco(sle)

		# if (
		# 	sle.voucher_type in ["Purchase Receipt", "Purchase Invoice"]
		# 	and sle.voucher_detail_no
		# 	and sle.actual_qty < 0
		# 	and is_internal_transfer(sle)
		# ):
		# 	sle.outgoing_rate = get_incoming_rate_for_inter_company_transfer(sle)

		# if get_serial_nos(sle.serial_no):
		# 	self.get_serialized_values(sle)
		# 	self.wh_data.qty_after_transaction += flt(sle.actual_qty)
		# 	if sle.voucher_type == "Stock Reconciliation":
		# 		self.wh_data.qty_after_transaction = sle.qty_after_transaction

		# 	self.wh_data.stock_value = flt(self.wh_data.qty_after_transaction) * flt(
		# 		self.wh_data.valuation_rate
		# 	)
		# elif sle.batch_no and frappe.db.get_value(
		# 	"Batch", sle.batch_no, "use_batchwise_valuation", cache=True
		# ):
		# 	self.update_batched_values(sle)
		# else:
		if sle.voucher_type == "Stock Reconciliation":
			# assert
			self.wh_data.valuation_rate = sle.valuation_rate
			self.wh_data.qty_after_transaction = sle.qty_after_transaction
			self.wh_data.stock_value = flt(self.wh_data.qty_after_transaction) * flt(
				self.wh_data.valuation_rate
			)
			self.wh_data.stock_queue = [[self.wh_data.qty_after_transaction, self.wh_data.valuation_rate]]
		else:
			# if self.valuation_method == "Moving Average":
			# 	self.get_moving_average_values(sle)
			# 	self.wh_data.qty_after_transaction += flt(sle.actual_qty)
			# 	self.wh_data.stock_value = flt(self.wh_data.qty_after_transaction) * flt(
			# 		self.wh_data.valuation_rate
			# 	)
			# else:
			self.update_queue_values(sle)

		# rounding as per precision
		self.wh_data.stock_value = flt(self.wh_data.stock_value, self.currency_precision)
		if not self.wh_data.qty_after_transaction:
			self.wh_data.stock_value = 0.0
		stock_value_difference = self.wh_data.stock_value - self.wh_data.prev_stock_value
		self.wh_data.prev_stock_value = self.wh_data.stock_value

		# update current sle
		sle.qty_after_transaction = self.wh_data.qty_after_transaction
		sle.valuation_rate = self.wh_data.valuation_rate
		sle.stock_value = self.wh_data.stock_value
		sle.stock_queue = json.dumps(self.wh_data.stock_queue)
		sle.stock_value_difference = stock_value_difference
		sle.doctype = "Stock Ledger Entry"
		frappe.get_doc(sle).db_update()

		if not self.args.get("sle_id"):
			self.update_outgoing_rate_on_transaction(sle)
	
	# def reset_actual_qty_for_stock_reco(self, sle):
	# 	current_qty = frappe.get_cached_value(
	# 		"Stock Reconciliation Item", sle.voucher_detail_no, "current_qty"
	# 	)

	# 	if current_qty:
	# 		sle.actual_qty = current_qty * -1
	# 	elif current_qty == 0:
	# 		sle.is_cancelled = 1
	
	def validate_negative_stock(self, sle):
		"""
		validate negative stock for entries current datetime onwards
		will not consider cancelled entries
		"""
		diff = self.wh_data.qty_after_transaction + flt(sle.qty)
		diff = flt(diff, self.flt_precision)  # respect system precision

		if diff < 0 and abs(diff) > 0.0001:
			# negative stock!
			exc = sle.copy().update({"diff": diff})
			self.exceptions.setdefault(sle.warehouse, []).append(exc)
			return False
		else:
			return True

	def get_dynamic_incoming_outgoing_rate(self, sle):
		# Get updated incoming/outgoing rate from transaction
		if sle.recalculate_rate:
			rate = 0
			# rate = self.get_incoming_outgoing_rate_from_transaction(sle)
			if flt(sle.qty) >= 0:
				sle.rate = rate # incoming_rate
			else:
				sle.outgoing_rate = rate

	# def get_incoming_outgoing_rate_from_transaction(self, sle):
	# 	rate = 0
	# 	# Material Transfer, Repack, Manufacturing
	# 	if sle.voucher_type == "Stock Entry":
	# 		self.recalculate_amounts_in_stock_entry(sle.voucher_no)
	# 		rate = frappe.db.get_value("Stock Entry Detail", sle.voucher_detail_no, "valuation_rate")
	# 	# Sales and Purchase Return
	# 	elif sle.voucher_type in (
	# 		"Purchase Receipt",
	# 		"Purchase Invoice",
	# 		"Delivery Note",
	# 		"Sales Invoice",
	# 		"Subcontracting Receipt",
	# 	):
	# 		if frappe.get_cached_value(sle.voucher_type, sle.voucher_no, "is_return"):
	# 			from erpnext.controllers.sales_and_purchase_return import (
	# 				get_rate_for_return,  # don't move this import to top
	# 			)

	# 			rate = get_rate_for_return(
	# 				sle.voucher_type,
	# 				sle.voucher_no,
	# 				sle.item,
	# 				voucher_detail_no=sle.voucher_detail_no,
	# 				sle=sle,
	# 			)

	# 		elif (
	# 			sle.voucher_type in ["Purchase Receipt", "Purchase Invoice"]
	# 			and sle.voucher_detail_no
	# 			and is_internal_transfer(sle)
	# 		):
	# 			rate = get_incoming_rate_for_inter_company_transfer(sle)
	# 		else:
	# 			if sle.voucher_type in ("Purchase Receipt", "Purchase Invoice"):
	# 				rate_field = "valuation_rate"
	# 			elif sle.voucher_type == "Subcontracting Receipt":
	# 				rate_field = "rate"
	# 			else:
	# 				rate_field = "incoming_rate"

	# 			# check in item table
	# 			item, incoming_rate = frappe.db.get_value(
	# 				sle.voucher_type + " Item", sle.voucher_detail_no, ["item", rate_field]
	# 			)

	# 			if item == sle.item:
	# 				rate = incoming_rate
	# 			else:
	# 				if sle.voucher_type in ("Delivery Note", "Sales Invoice"):
	# 					ref_doctype = "Packed Item"
	# 				elif sle == "Subcontracting Receipt":
	# 					ref_doctype = "Subcontracting Receipt Supplied Item"
	# 				else:
	# 					ref_doctype = "Purchase Receipt Item Supplied"

	# 				rate = frappe.db.get_value(
	# 					ref_doctype,
	# 					{"parent_detail_docname": sle.voucher_detail_no, "item": sle.item},
	# 					rate_field,
	# 				)

	# 	return rate

	def update_queue_values(self, sle):
		incoming_rate = flt(sle.rate)
		qty = flt(sle.qty)
		outgoing_rate = flt(sle.outgoing_rate)

		self.wh_data.qty_after_transaction = round_off_if_near_zero(
			self.wh_data.qty_after_transaction + qty
		)

		stock_queue = FIFOValuation(self.wh_data.stock_queue)

		_prev_qty, prev_stock_value = stock_queue.get_total_stock_and_value()

		if qty > 0:
			stock_queue.add_stock(qty=qty, rate=incoming_rate)
		else:

			def rate_generator() -> float:
				allow_zero_valuation_rate = self.check_if_allow_zero_valuation_rate(
					sle.voucher_type, sle.voucher_detail_no
				)
				if not allow_zero_valuation_rate:
					return self.get_fallback_rate(sle)
				else:
					return 0.0

			stock_queue.remove_stock(
				qty=abs(qty), outgoing_rate=outgoing_rate, rate_generator=rate_generator
			)

		_qty, stock_value = stock_queue.get_total_stock_and_value()

		stock_value_difference = stock_value - prev_stock_value

		self.wh_data.stock_queue = stock_queue.state
		self.wh_data.stock_value = round_off_if_near_zero(
			self.wh_data.stock_value + stock_value_difference
		)

		if not self.wh_data.stock_queue:
			self.wh_data.stock_queue.append(
				[0, sle.rate or sle.outgoing_rate or self.wh_data.valuation_rate]
			)

		if self.wh_data.qty_after_transaction:
			self.wh_data.valuation_rate = self.wh_data.stock_value / self.wh_data.qty_after_transaction
	
	def check_if_allow_zero_valuation_rate(self, voucher_type, voucher_detail_no):
		ref_item_dt = ""

		if voucher_type == "Stock Entry":
			ref_item_dt = voucher_type + " Detail"
		elif voucher_type in ["Purchase Invoice", "Sales Invoice", "Delivery Note", "Purchase Receipt"]:
			ref_item_dt = voucher_type + " Item"

		if ref_item_dt:
			return frappe.db.get_value(ref_item_dt, voucher_detail_no, "allow_zero_valuation_rate")
		else:
			return 0

	def get_fallback_rate(self, sle) -> float:
		"""When exact incoming rate isn't available use any of other "average" rates as fallback.
		This should only get used for negative stock."""
		return get_valuation_rate(
			sle.item,
			sle.warehouse,
			sle.voucher_type,
			sle.voucher_no,
			allow_zero_rate=True,
			raise_error_if_no_rate=False,
		)

	def raise_exceptions(self):
		msg_list = []
		for warehouse, exceptions in self.exceptions.items():
			deficiency = min(e["diff"] for e in exceptions)

			if (
				exceptions[0]["voucher_type"],
				exceptions[0]["voucher_no"],
			) in frappe.local.flags.currently_saving:

				msg = _("{0} units of {1} needed in {2} to complete this transaction.").format(
					abs(deficiency),
					frappe.get_desk_link("Item", exceptions[0]["item"]),
					frappe.get_desk_link("Warehouse", warehouse),
				)
			else:
				msg = _(
					"{0} units of {1} needed in {2} on {3} {4} for {5} to complete this transaction."
				).format(
					abs(deficiency),
					frappe.get_desk_link("Item", exceptions[0]["item"]),
					frappe.get_desk_link("Warehouse", warehouse),
					exceptions[0]["posting_date"],
					exceptions[0]["posting_time"],
					frappe.get_desk_link(exceptions[0]["voucher_type"], exceptions[0]["voucher_no"]),
				)

			if msg:
				msg_list.append(msg)

		if msg_list:
			message = "\n\n".join(msg_list)
			if self.verbose:
				frappe.throw(message, NegativeStockError, title=_("Insufficient Stock"))
			else:
				raise NegativeStockError(message)

def get_valuation_rate(
	item,
	warehouse,
	voucher_type,
	voucher_no,
	allow_zero_rate=False,
	raise_error_if_no_rate=True,
):
	valuation_rate = None

	# Get valuation rate from last sle for the same item and warehouse
	valuation_rate = frappe.db.sql(
		"""select valuation_rate
		from `tabStock Ledger Entry`
		where
			item = %s
			AND warehouse = %s
			AND valuation_rate >= 0
			AND is_cancelled = 0
			AND NOT (voucher_no = %s AND voucher_type = %s)
		order by posting_date desc, posting_time desc, name desc limit 1""",
		(item, warehouse, voucher_no, voucher_type),
	)

	if valuation_rate:
		return flt(valuation_rate[0][0])

	# If negative stock allowed, and item delivered without any incoming entry,
	# system does not found any SLE, then take valuation rate from Item
	valuation_rate = get_item_variant_price(item)

	if (
		not allow_zero_rate
		and not valuation_rate
		and raise_error_if_no_rate
	):
		form_link = get_link_to_form("Item", item)

		message = _(
			"Valuation Rate for the Item {0}, is required to do accounting entries for {1} {2}."
		).format(form_link, voucher_type, voucher_no)
		message += "<br><br>" + _("Here are the options to proceed:")
		solutions = (
			"<li>"
			+ _(
				"If the item is transacting as a Zero Valuation Rate item in this entry, please enable 'Allow Zero Valuation Rate' in the {0} Item table."
			).format(voucher_type)
			+ "</li>"
		)
		solutions += (
			"<li>"
			+ _("If not, you can Cancel / Submit this entry")
			+ " {0} ".format(frappe.bold("after"))
			+ _("performing either one below:")
			+ "</li>"
		)
		sub_solutions = "<ul><li>" + _("Create an incoming stock transaction for the Item.") + "</li>"
		sub_solutions += "<li>" + _("Mention Valuation Rate in the Item master.") + "</li></ul>"
		msg = message + solutions + sub_solutions + "</li>"

		frappe.throw(msg=msg, title=_("Valuation Rate Missing"))

	return valuation_rate
            
def get_previous_sle_of_current_voucher(args, operator="<", exclude_current_voucher=False):
	"""get stock ledger entries filtered by specific posting datetime conditions"""

	args["time_format"] = "%H:%i:%s"
	if not args.get("posting_date"):
		args["posting_date"] = "1900-01-01"
	if not args.get("posting_time"):
		args["posting_time"] = "00:00"

	voucher_condition = ""
	if exclude_current_voucher:
		voucher_no = args.get("voucher_no")
		voucher_condition = f"and voucher_no != '{voucher_no}'"

	sle = frappe.db.sql(
		"""
		select *, timestamp(posting_date, posting_time) as "timestamp"
		from `tabStock Ledger Entry`
		where item = %(item)s
			and warehouse = %(warehouse)s
			and lot = %(lot)s
			and is_cancelled = 0
			{voucher_condition}
			and (
				posting_date < %(posting_date)s or
				(
					posting_date = %(posting_date)s and
					time_format(posting_time, %(time_format)s) {operator} time_format(%(posting_time)s, %(time_format)s)
				)
			)
		order by timestamp(posting_date, posting_time) desc, creation desc
		limit 1
		for update""".format(
			operator=operator, voucher_condition=voucher_condition
		),
		args,
		as_dict=1,
	)

	return sle[0] if sle else frappe._dict()

def get_stock_reco_qty_shift(args):
	stock_reco_qty_shift = 0
	if args.get("is_cancelled"):
		if args.get("previous_qty_after_transaction"):
			# get qty (balance) that was set at submission
			last_balance = args.get("previous_qty_after_transaction")
			stock_reco_qty_shift = flt(args.qty_after_transaction) - flt(last_balance)
		else:
			stock_reco_qty_shift = flt(args.qty)
	else:
		# reco is being submitted
		last_balance = get_previous_sle_of_current_voucher(args, "<=", exclude_current_voucher=True).get(
			"qty_after_transaction"
		)

		if last_balance is not None:
			stock_reco_qty_shift = flt(args.qty_after_transaction) - flt(last_balance)
		else:
			stock_reco_qty_shift = args.qty_after_transaction

	return stock_reco_qty_shift

def get_next_stock_reco(kwargs):
	"""Returns next nearest stock reconciliation's details."""

	sle = frappe.qb.DocType("Stock Ledger Entry")

	query = (
		frappe.qb.from_(sle)
		.select(
			sle.name,
			sle.posting_date,
			sle.posting_time,
			sle.creation,
			sle.voucher_no,
			sle.item,
			sle.qty,
		)
		.where(
			(sle.item == kwargs.get("item"))
			& (sle.warehouse == kwargs.get("warehouse"))
			& (sle.voucher_type == "Stock Reconciliation")
			& (sle.voucher_no != kwargs.get("voucher_no"))
			& (sle.is_cancelled == 0)
			& (
				(
					CombineDatetime(sle.posting_date, sle.posting_time)
					> CombineDatetime(kwargs.get("posting_date"), kwargs.get("posting_time"))
				)
				| (
					(
						CombineDatetime(sle.posting_date, sle.posting_time)
						== CombineDatetime(kwargs.get("posting_date"), kwargs.get("posting_time"))
					)
					& (sle.creation > kwargs.get("creation"))
				)
			)
		)
		.orderby(CombineDatetime(sle.posting_date, sle.posting_time))
		.orderby(sle.creation)
		.limit(1)
	)

	if kwargs.get("lot"):
		query = query.where(sle.lot == kwargs.get("lot"))

	return query.run(as_dict=True)

def get_datetime_limit_condition(detail):
	return f"""
		and
		(timestamp(posting_date, posting_time) < timestamp('{detail.posting_date}', '{detail.posting_time}')
			or (
				timestamp(posting_date, posting_time) = timestamp('{detail.posting_date}', '{detail.posting_time}')
				and creation < '{detail.creation}'
			)
		)"""

def validate_negative_qty_in_future_sle(args, allow_negative_stock=False):
	# if allow_negative_stock or is_negative_stock_allowed(item=args.item):
	# 	return
	if not (args.qty < 0 or args.voucher_type == "Stock Reconciliation"):
		return

	neg_sle = get_future_sle_with_negative_qty(args)

	if is_negative_with_precision(neg_sle):
		message = _(
			"{0} units of {1} needed in {2} on {3} {4} for {5} to complete this transaction."
		).format(
			abs(neg_sle[0]["qty_after_transaction"]),
			frappe.get_desk_link("Item", args.item),
			frappe.get_desk_link("Warehouse", args.warehouse),
			neg_sle[0]["posting_date"],
			neg_sle[0]["posting_time"],
			frappe.get_desk_link(neg_sle[0]["voucher_type"], neg_sle[0]["voucher_no"]),
		)

		frappe.throw(message, NegativeStockError, title=_("Insufficient Stock"))

def is_negative_with_precision(neg_sle, is_batch=False):
	"""
	Returns whether system precision rounded qty is insufficient.
	E.g: -0.0003 in precision 3 (0.000) is sufficient for the user.
	"""

	if not neg_sle:
		return False

	field = "cumulative_total" if is_batch else "qty_after_transaction"
	precision = cint(frappe.db.get_default("float_precision")) or 2
	qty_deficit = flt(neg_sle[0][field], precision)

	return qty_deficit < 0 and abs(qty_deficit) > 0.0001


def get_future_sle_with_negative_qty(args):
	return frappe.db.sql(
		"""
		select
			name, qty_after_transaction, posting_date, posting_time,
			voucher_type, voucher_no
		from `tabStock Ledger Entry`
		where
			item = %(item)s
			and warehouse = %(warehouse)s
			and voucher_no != %(voucher_no)s
			and timestamp(posting_date, posting_time) >= timestamp(%(posting_date)s, %(posting_time)s)
			and is_cancelled = 0
			and qty_after_transaction < 0
		order by timestamp(posting_date, posting_time) asc
		limit 1
	""",
		args,
		as_dict=1,
	)

def get_previous_sle(args, for_update=False):
	"""
	get the last sle on or before the current time-bucket,
	to get actual qty before transaction, this function
	is called from various transaction like stock entry, reco etc

	args = {
	        "item": "ABC",
	        "warehouse": "XYZ",
	        "posting_date": "2012-12-12",
	        "posting_time": "12:00",
	        "sle": "name of reference Stock Ledger Entry"
	}
	"""
	args["name"] = args.get("sle", None) or ""
	sle = get_stock_ledger_entries(args, "<=", "desc", "limit 1", for_update=for_update)
	return sle and sle[0] or {}

def get_stock_ledger_entries(
	previous_sle,
	operator=None,
	order="desc",
	limit=None,
	for_update=False,
	debug=True,
	# check_serial_no=True,
):
	"""get stock ledger entries filtered by specific posting datetime conditions"""
	conditions = " and timestamp(posting_date, posting_time) {0} timestamp(%(posting_date)s, %(posting_time)s)".format(
		operator
	)
	if previous_sle.get("warehouse"):
		conditions += " and warehouse = %(warehouse)s"
	elif previous_sle.get("warehouse_condition"):
		conditions += " and " + previous_sle.get("warehouse_condition")
	
	if previous_sle.get("lot"):
		conditions += " and lot = %(lot)s"

	if not previous_sle.get("posting_date"):
		previous_sle["posting_date"] = "1900-01-01"
	if not previous_sle.get("posting_time"):
		previous_sle["posting_time"] = "00:00"

	if operator in (">", "<=") and previous_sle.get("name"):
		conditions += " and name!=%(name)s"
	return frappe.db.sql(
		"""
		select *, timestamp(posting_date, posting_time) as "timestamp"
		from `tabStock Ledger Entry`
		where item = %%(item)s
		and is_cancelled = 0
		%(conditions)s
		order by timestamp(posting_date, posting_time) %(order)s, creation %(order)s
		%(limit)s %(for_update)s"""
		% {
			"conditions": conditions,
			"limit": limit or "",
			"for_update": for_update and "for update" or "",
			"order": order,
		},
		previous_sle,
		as_dict=1,
		debug=debug,
	)