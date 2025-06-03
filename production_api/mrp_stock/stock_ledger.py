import copy
import gzip
import json

import frappe
from frappe import _, scrub
from frappe.utils import (
	cint,
	flt,
	get_link_to_form,
	now,
	nowdate,
	parse_json,
)
from production_api.production_api.doctype.item_price.item_price import get_item_variant_price
from production_api.mrp_stock.utils import (
    get_combine_datetime,
    get_incoming_outgoing_rate_for_cancel,
)

from production_api.mrp_stock.valuation import FIFOValuation, round_off_if_near_zero
from production_api.utils import get_or_make_bin
from production_api.mrp_stock.doctype.bin.bin import update_qty as update_bin_qty


class NegativeStockError(frappe.ValidationError):
	pass


def make_sl_entries(sl_entries, allow_negative_stock=False, via_landed_cost_voucher=False):
	"""Create SL entries from SL entry dicts"""
	from production_api.mrp_stock.utils import future_sle_exists

	if sl_entries:
		cancel = sl_entries[0].get("is_cancelled")
		if cancel:
			validate_cancellation(sl_entries)
			set_as_cancelled(sl_entries[0].get("voucher_type"), sl_entries[0].get("voucher_no"))

		args = get_args_for_future_sle(sl_entries[0])
		future_sle_exists(args, sl_entries)
		received_type = frappe.db.get_single_value("Stock Settings","default_received_type")
		for sle in sl_entries:
			item = frappe.get_cached_value("Item Variant", sle.get("item"), "item")
			is_stock_item = frappe.get_cached_value("Item", item, "is_stock_item")

			if not is_stock_item:
				continue

			if sle.get("voucher_type") != "Stock Reconciliation" and not sle["qty"]:
				continue

			if sle.get("received_type") in [None,""]:
				sle.received_type = received_type
				
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
			args["posting_datetime"] = get_combine_datetime(args.posting_date, args.posting_time)

			if sle.get("voucher_type") == "Stock Reconciliation":
				# preserve previous_qty_after_transaction for qty reposting
				args.previous_qty_after_transaction = sle.get("previous_qty_after_transaction")

			# item = frappe.get_cached_value("Item Variant", args.get("item"), "item")
			# is_stock_item = frappe.get_cached_value("Item", item, "is_stock_item")
			if is_stock_item:
				bin_name = get_or_make_bin(args.get("item"),args.get("warehouse"),args.get("lot"), args.get("received_type"))
				args.reserved_stock = flt(frappe.db.get_value("Bin", bin_name, "reserved_qty"))
				repost_current_voucher(args)
				update_bin_qty(bin_name, args)
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
					"received_type":args.get("received_type"),
					"posting_date": args.get("posting_date"),
					"posting_time": args.get("posting_time"),
					"voucher_type": args.get("voucher_type"),
					"voucher_no": args.get("voucher_no"),
					"sle_id": args.get("name"),
					"creation": args.get("creation"),
					"reserved_stock": args.get("reserved_stock"),
				},
				# allow_negative_stock=allow_negative_stock,
				# via_landed_cost_voucher=via_landed_cost_voucher,
			)

		# update qty in future sle and Validate negative qty
		# For LCV: update future balances with -ve LCV SLE, which will be balanced by +ve LCV SLE
		update_qty_in_future_sle(args, allow_negative_stock)


def get_args_for_future_sle(row):
	return frappe._dict(
		{
			"voucher_type": row.get("voucher_type"),
			"voucher_no": row.get("voucher_no"),
			"posting_date": row.get("posting_date"),
			"posting_time": row.get("posting_time"),
		}
	)

def repost_future_stock_ledger_entry(self, force=False, via_landed_cost_voucher=False):
		args = frappe._dict(
			{
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"via_landed_cost_voucher": via_landed_cost_voucher,
			}
		)

		if self.docstatus == 2:
			force = True

		if force or future_sle_exists(args) or repost_required_for_queue(self):
			item_based_reposting = cint(
				frappe.db.get_single_value("Stock Reposting Settings", "item_based_reposting")
			)
			if item_based_reposting:
				create_item_wise_repost_entries(
					voucher_type=self.doctype,
					voucher_no=self.name,
					via_landed_cost_voucher=via_landed_cost_voucher,
				)
			else:
				create_repost_item_valuation_entry(args)

def future_sle_exists(args, sl_entries=None, allow_force_reposting=True):
	from production_api.mrp_stock.utils import get_combine_datetime

	if allow_force_reposting and frappe.db.get_single_value(
		"Stock Reposting Settings", "do_reposting_for_each_stock_transaction"
	):
		return True

	key = (args.voucher_type, args.voucher_no)
	if not hasattr(frappe.local, "future_sle"):
		frappe.local.future_sle = {}

	if validate_future_sle_not_exists(args, key, sl_entries):
		return False
	elif get_cached_data(args, key):
		return True

	if not sl_entries:
		sl_entries = get_sle_entries_against_voucher(args)
		if not sl_entries:
			return

	or_conditions = get_conditions_to_validate_future_sle(sl_entries)

	args["posting_datetime"] = get_combine_datetime(args["posting_date"], args["posting_time"])

	data = frappe.db.sql(
		"""
		select item, warehouse, lot, received_type, count(name) as total_row
		from `tabStock Ledger Entry`
		where
			({})
			and posting_datetime >= %(posting_datetime)s
			and voucher_no != %(voucher_no)s
			and is_cancelled = 0
		GROUP BY
			item, warehouse, lot, received_type
		""".format(" or ".join(or_conditions)),
		args,
		as_dict=1,
	)

	for d in data:
		frappe.local.future_sle[key][(d.item, d.warehouse, d.lot, d.received_type)] = d.total_row

	return len(data)

def validate_future_sle_not_exists(args, key, sl_entries=None):
	item_key = ""
	if args.get("item"):
		item_key = (args.get("item"), args.get("warehouse"), args.get("lot"), args.get("received_type"))

	if not sl_entries and hasattr(frappe.local, "future_sle"):
		if key not in frappe.local.future_sle:
			return False

		if not frappe.local.future_sle.get(key) or (
			item_key and item_key not in frappe.local.future_sle.get(key)
		):
			return True

def get_cached_data(args, key):
	if key not in frappe.local.future_sle:
		frappe.local.future_sle[key] = frappe._dict({})

	if args.get("item"):
		item_key = (args.get("item"), args.get("warehouse"), args.get("lot"), args.get("received_type"))
		count = frappe.local.future_sle[key].get(item_key)

		return True if (count or count == 0) else False
	else:
		return frappe.local.future_sle[key]

def get_conditions_to_validate_future_sle(sl_entries):
	warehouse_items_map = {}
	for entry in sl_entries:
		key = (entry.get("warehouse"), entry.get("lot"), entry.get("received_type"))
		if key not in warehouse_items_map:
			warehouse_items_map[key] = set()

		warehouse_items_map[key].add(entry.item)

	or_conditions = []
	for key, items in warehouse_items_map.items():
		warehouse, lot, received_type = key
		or_conditions.append(
			f"""warehouse = {frappe.db.escape(warehouse)}
				and lot = {frappe.db.escape(lot)}
				and received_type = {frappe.db.escape(received_type)}
				and item in ({', '.join(frappe.db.escape(item) for item in items)})"""
		)

	return or_conditions
	
def get_sle_entries_against_voucher(args):
	return frappe.get_all(
		"Stock Ledger Entry",
		filters={"voucher_type": args.voucher_type, "voucher_no": args.voucher_no},
		fields=["item", "warehouse", "lot", "received_type"],
		order_by="creation asc",
	)

def repost_required_for_queue(doc) -> bool:
	"""check if stock document contains repeated item-warehouse with queue based valuation.

	if queue exists for repeated items then SLEs need to reprocessed in background again.
	"""

	consuming_sles = frappe.db.get_all(
		"Stock Ledger Entry",
		filters={
			"voucher_type": doc.doctype,
			"voucher_no": doc.name,
			"qty": ("<", 0),
			"is_cancelled": 0,
		},
		fields=["item", "warehouse", "stock_queue", "lot", "received_type"],
	)
	item_warehouses = [(sle.item, sle.warehouse, sle.lot, sle.received_type) for sle in consuming_sles]

	unique_item_warehouses = set(item_warehouses)

	if len(unique_item_warehouses) == len(item_warehouses):
		return False

	for sle in consuming_sles:
		if sle.stock_queue != "[]":  # using FIFO/LIFO valuation
			return True
	return False


def validate_cancellation(kargs):
	if kargs[0].get("is_cancelled"):
		repost_entry = frappe.db.get_value(
			"Repost Item Valuation",
			{
				"voucher_type": kargs[0].voucher_type,
				"voucher_no": kargs[0].voucher_no,
				"docstatus": 1,
			},
			["name", "status"],
			as_dict=1,
		)

		if repost_entry:
			if repost_entry.status == "In Progress":
				frappe.throw(
					_(
						"Cannot cancel the transaction. Reposting of item valuation on submission is not completed yet."
					)
				)
			if repost_entry.status == "Queued":
				doc = frappe.get_doc("Repost Item Valuation", repost_entry.name)
				doc.status = "Skipped"
				doc.flags.ignore_permissions = True
				doc.cancel()


def create_repost_item_valuation_entry(args):
	args = frappe._dict(args)
	repost_entry = frappe.new_doc("Repost Item Valuation")
	repost_entry.based_on = args.based_on
	if not args.based_on:
		repost_entry.based_on = "Transaction" if args.voucher_no else "Item and Warehouse"
	repost_entry.voucher_type = args.voucher_type
	repost_entry.voucher_no = args.voucher_no
	repost_entry.item = args.item
	repost_entry.warehouse = args.warehouse
	repost_entry.lot = args.lot
	repost_entry.received_type = args.received_type
	repost_entry.posting_date = args.posting_date
	repost_entry.posting_time = args.posting_time
	repost_entry.allow_zero_rate = args.allow_zero_rate
	repost_entry.flags.ignore_links = True
	repost_entry.flags.ignore_permissions = True
	repost_entry.via_landed_cost_voucher = args.via_landed_cost_voucher
	repost_entry.save()
	repost_entry.submit()


def create_item_wise_repost_entries(
	voucher_type, voucher_no, allow_zero_rate=False, via_landed_cost_voucher=False
):
	"""Using a voucher create repost item valuation records for all item-warehouse pairs."""

	stock_ledger_entries = get_items_to_be_repost(voucher_type, voucher_no)

	distinct_item_warehouses = set()
	repost_entries = []

	for sle in stock_ledger_entries:
		item_wh = (sle.item, sle.warehouse, sle.lot, sle.received_type)
		if item_wh in distinct_item_warehouses:
			continue
		distinct_item_warehouses.add(item_wh)

		repost_entry = frappe.new_doc("Repost Item Valuation")
		repost_entry.based_on = "Item and Warehouse"

		repost_entry.item = sle.item
		repost_entry.warehouse = sle.warehouse
		repost_entry.lot = sle.lot
		repost_entry.received_type = sle.received_type
		repost_entry.posting_date = sle.posting_date
		repost_entry.posting_time = sle.posting_time
		repost_entry.allow_zero_rate = allow_zero_rate
		repost_entry.flags.ignore_links = True
		repost_entry.flags.ignore_permissions = True
		repost_entry.via_landed_cost_voucher = via_landed_cost_voucher
		repost_entry.submit()
		repost_entries.append(repost_entry)

	return repost_entries

def set_as_cancelled(voucher_type, voucher_no):
	frappe.db.sql(
		"""update `tabStock Ledger Entry` set is_cancelled=1,
		modified=%s, modified_by=%s
		where voucher_type=%s and voucher_no=%s and is_cancelled = 0""",
		(now(), frappe.session.user, voucher_type, voucher_no),
	)


def make_entry(args, allow_negative_stock=False, via_landed_cost_voucher=False):
	args["doctype"] = "Stock Ledger Entry"
	sle = frappe.get_doc(args)
	sle.flags.ignore_permissions = 1
	# sle.allow_negative_stock = allow_negative_stock
	# sle.via_landed_cost_voucher = via_landed_cost_voucher
	sle.set_posting_datetime()
	sle.submit()
	return sle


def repost_future_sle(
	args=None,
	voucher_type=None,
	voucher_no=None,
	allow_negative_stock=None,
	via_landed_cost_voucher=False,
	doc=None,
):
	if not args:
		args = []  # set args to empty list if None to avoid enumerate error

	reposting_data = {}
	if doc and doc.reposting_data_file:
		reposting_data = get_reposting_data(doc.reposting_data_file)

	items_to_be_repost = get_items_to_be_repost(
		voucher_type=voucher_type, voucher_no=voucher_no, doc=doc, reposting_data=reposting_data
	)
	if items_to_be_repost:
		args = items_to_be_repost

	distinct_item_warehouses = get_distinct_item_warehouse(args, doc, reposting_data=reposting_data)
	affected_transactions = get_affected_transactions(doc, reposting_data=reposting_data)

	i = get_current_index(doc) or 0
	while i < len(args):
		validate_item_warehouse(args[i])

		obj = update_entries_after(
			{
				"item": args[i].get("item"),
				"warehouse": args[i].get("warehouse"),
				"lot": args[i].get("lot"),
				"received_type":args[i].get("received_type"),
				"posting_date": args[i].get("posting_date"),
				"posting_time": args[i].get("posting_time"),
				"creation": args[i].get("creation"),
				"distinct_item_warehouses": distinct_item_warehouses,
				"items_to_be_repost": args,
				"current_index": i,
			},
			# allow_negative_stock=allow_negative_stock,
			# via_landed_cost_voucher=via_landed_cost_voucher,
		)
		affected_transactions.update(obj.affected_transactions)

		key = (args[i].get("item"), args[i].get("warehouse"), args[i].get("lot"), args[i].get("received_type"))
		if distinct_item_warehouses.get(key):
			distinct_item_warehouses[key].reposting_status = True

		if obj.new_items_found:
			for _item_wh, data in distinct_item_warehouses.items():
				if ("args_idx" not in data and not data.reposting_status) or (
					data.sle_changed and data.reposting_status
				):
					data.args_idx = len(args)
					args.append(data.sle)
				elif data.sle_changed and not data.reposting_status:
					args[data.args_idx] = data.sle

				data.sle_changed = False
		i += 1

		if doc:
			update_args_in_repost_item_valuation(
				doc, i, args, distinct_item_warehouses, affected_transactions
			)


def get_reposting_data(file_path) -> dict:
	file_name = frappe.db.get_value(
		"File",
		{
			"file_url": file_path,
			"attached_to_field": "reposting_data_file",
		},
		"name",
	)

	if not file_name:
		return frappe._dict()

	attached_file = frappe.get_doc("File", file_name)

	content = attached_file.get_content()
	if isinstance(content, str):
		content = content.encode("utf-8")

	try:
		data = gzip.decompress(content)
	except Exception:
		return frappe._dict()

	if data := json.loads(data.decode("utf-8")):
		data = data

	return parse_json(data)


def validate_item_warehouse(args):
	for field in ["item", "warehouse", "lot", "received_type", "posting_date", "posting_time"]:
		if args.get(field) in [None, ""]:
			validation_msg = f"The field {frappe.unscrub(field)} is required for the reposting"
			frappe.throw(_(validation_msg))


def update_args_in_repost_item_valuation(doc, index, args, distinct_item_warehouses, affected_transactions):
	if not doc.items_to_be_repost:
		file_name = ""
		if doc.reposting_data_file:
			file_name = get_reposting_file_name(doc.doctype, doc.name)
			# frappe.delete_doc("File", file_name, ignore_permissions=True, delete_permanently=True)

		doc.reposting_data_file = create_json_gz_file(
			{
				"items_to_be_repost": args,
				"distinct_item_and_warehouse": {str(k): v for k, v in distinct_item_warehouses.items()},
				"affected_transactions": affected_transactions,
			},
			doc,
			file_name,
		)

		doc.db_set(
			{
				"current_index": index,
				"total_reposting_count": len(args),
				"reposting_data_file": doc.reposting_data_file,
			}
		)

	else:
		doc.db_set(
			{
				"items_to_be_repost": json.dumps(args, default=str),
				"distinct_item_and_warehouse": json.dumps(
					{str(k): v for k, v in distinct_item_warehouses.items()}, default=str
				),
				"current_index": index,
				"affected_transactions": frappe.as_json(affected_transactions),
			}
		)

	if not frappe.flags.in_test:
		frappe.db.commit()

	frappe.publish_realtime(
		"item_reposting_progress",
		{
			"name": doc.name,
			"items_to_be_repost": json.dumps(args, default=str),
			"current_index": index,
			"total_reposting_count": len(args),
		},
		doctype=doc.doctype,
		docname=doc.name,
	)


def get_reposting_file_name(dt, dn):
	return frappe.db.get_value(
		"File",
		{
			"attached_to_doctype": dt,
			"attached_to_name": dn,
			"attached_to_field": "reposting_data_file",
		},
		"name",
	)


def create_json_gz_file(data, doc, file_name=None) -> str:
	encoded_content = frappe.safe_encode(frappe.as_json(data))
	compressed_content = gzip.compress(encoded_content)

	if not file_name:
		json_filename = f"{scrub(doc.doctype)}-{scrub(doc.name)}.json.gz"
		_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": json_filename,
				"attached_to_doctype": doc.doctype,
				"attached_to_name": doc.name,
				"attached_to_field": "reposting_data_file",
				"content": compressed_content,
				"is_private": 1,
			}
		)
		_file.save(ignore_permissions=True)

		return _file.file_url
	else:
		file_doc = frappe.get_doc("File", file_name)
		path = file_doc.get_full_path()

		with open(path, "wb") as f:
			f.write(compressed_content)

		return doc.reposting_data_file


def get_items_to_be_repost(voucher_type=None, voucher_no=None, doc=None, reposting_data=None):
	if not reposting_data and doc and doc.reposting_data_file:
		reposting_data = get_reposting_data(doc.reposting_data_file)

	if reposting_data and reposting_data.items_to_be_repost:
		return reposting_data.items_to_be_repost

	items_to_be_repost = []

	if doc and doc.items_to_be_repost:
		items_to_be_repost = json.loads(doc.items_to_be_repost) or []

	if not items_to_be_repost and voucher_type and voucher_no:
		items_to_be_repost = frappe.db.get_all(
			"Stock Ledger Entry",
			filters={"voucher_type": voucher_type, "voucher_no": voucher_no},
			fields=["item", "warehouse", "lot", "received_type", "posting_date", "posting_time", "creation"],
			order_by="creation asc",
			group_by="item, warehouse, lot, received_type",
		)

	return items_to_be_repost or []


def get_distinct_item_warehouse(args=None, doc=None, reposting_data=None):
	if not reposting_data and doc and doc.reposting_data_file:
		reposting_data = get_reposting_data(doc.reposting_data_file)

	if reposting_data and reposting_data.distinct_item_and_warehouse:
		return parse_distinct_items_and_warehouses(reposting_data.distinct_item_and_warehouse)

	distinct_item_warehouses = {}

	if doc and doc.distinct_item_and_warehouse:
		distinct_item_warehouses = json.loads(doc.distinct_item_and_warehouse)
		distinct_item_warehouses = {
			frappe.safe_eval(k): frappe._dict(v) for k, v in distinct_item_warehouses.items()
		}
	else:
		for i, d in enumerate(args):
			distinct_item_warehouses.setdefault(
				(d.item, d.warehouse, d.lot, d.received_type), frappe._dict({"reposting_status": False, "sle": d, "args_idx": i})
			)

	return distinct_item_warehouses


def parse_distinct_items_and_warehouses(distinct_items_and_warehouses):
	new_dict = frappe._dict({})

	# convert string keys to tuple
	for k, v in distinct_items_and_warehouses.items():
		new_dict[frappe.safe_eval(k)] = frappe._dict(v)

	return new_dict


def get_affected_transactions(doc, reposting_data=None) -> set[tuple[str, str]]:
	if not reposting_data and doc and doc.reposting_data_file:
		reposting_data = get_reposting_data(doc.reposting_data_file)

	if reposting_data and reposting_data.affected_transactions:
		return {tuple(transaction) for transaction in reposting_data.affected_transactions}

	if not doc.affected_transactions:
		return set()

	transactions = frappe.parse_json(doc.affected_transactions)
	return {tuple(transaction) for transaction in transactions}


def get_current_index(doc=None):
	if doc and doc.current_index:
		return doc.current_index


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
		# via_landed_cost_voucher=False,
		verbose=1,
	):
		self.exceptions = {}
		self.verbose = verbose
		self.allow_zero_rate = allow_zero_rate
		# self.via_landed_cost_voucher = via_landed_cost_voucher
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
		self.affected_transactions: set[tuple[str, str]] = set()
		self.reserved_stock = flt(self.args.reserved_stock)

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
		data_key = (args.warehouse, args.lot, args.received_type)
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
		from production_api.mrp_stock.utils import future_sle_exists

		if self.args.get("sle_id"):
			self.process_sle_against_current_timestamp()
			if not future_sle_exists(self.args):
				self.update_bin()
		else:
			entries_to_fix = self.get_future_entries_to_fix()

			i = 0
			while i < len(entries_to_fix):
				sle = entries_to_fix[i]
				i += 1

				self.process_sle(sle)
				self.update_bin_data(sle)

				# if sle.dependant_sle_voucher_detail_no:
					# entries_to_fix = self.get_dependent_entries_to_fix(entries_to_fix, sle)

		if self.exceptions:
			self.raise_exceptions()
	
	def process_sle_against_current_timestamp(self):
		sl_entries = self.get_sle_against_current_voucher()
		for sle in sl_entries:
			self.process_sle(sle)

	def get_sle_against_current_voucher(self):
		self.args["posting_datetime"] = get_combine_datetime(self.args.posting_date, self.args.posting_time)

		return frappe.db.sql(
			"""
			select
				*, posting_datetime as "timestamp"
			from
				`tabStock Ledger Entry`
			where
				item = %(item)s
				and warehouse = %(warehouse)s
				and lot = %(lot)s
				and received_type = %(received_type)s
				and is_cancelled = 0
				and (
					posting_datetime = %(posting_datetime)s
				)
				and creation = %(creation)s
			order by
				creation ASC
			for update
		""",
			self.args,
			as_dict=1,
		)

	def get_future_entries_to_fix(self):
		# includes current entry!
		args = self.data[(self.args.warehouse, self.args.lot, self.args.received_type)].previous_sle or frappe._dict(
			{"item": self.item, "warehouse": self.args.warehouse, "lot": self.args.lot, "received_type":self.args.received_type}
		)

		return list(self.get_sle_after_datetime(args))

	def get_sle_after_datetime(self, args):
		"""get Stock Ledger Entries after a particular datetime, for reposting"""
		return get_stock_ledger_entries(args, ">", "asc", for_update=True)

	def process_sle(self, sle):
		# previous sle data for this warehouse
		self.wh_data = self.data[(sle.warehouse, sle.lot, sle.received_type)]
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

		# if not self.args.get("sle_id"):
		# 	self.update_outgoing_rate_on_transaction(sle)
	
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
		diff = self.wh_data.qty_after_transaction + flt(sle.qty) - flt(self.reserved_stock)
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
		self.wh_data.stock_value = round_off_if_near_zero(self.wh_data.stock_value + stock_value_difference)

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
					frappe.bold(abs(deficiency)),
					frappe.get_desk_link("Item Variant", exceptions[0]["item"]),
					frappe.get_desk_link("Supplier", warehouse),
				)
			else:
				msg = _(
					"{0} units of {1} needed in {2} on {3} {4} for {5} to complete this transaction."
				).format(
					frappe.bold(abs(deficiency)),
					frappe.get_desk_link("Item Variant", exceptions[0]["item"]),
					frappe.get_desk_link("Supplier", warehouse),
					exceptions[0]["posting_date"],
					exceptions[0]["posting_time"],
					frappe.get_desk_link(exceptions[0]["voucher_type"], exceptions[0]["voucher_no"]),
				)

			if msg:
				if self.reserved_stock:
					allowed_qty = abs(exceptions[0]["qty"]) - abs(exceptions[0]["diff"])

					if allowed_qty > 0:
						msg = "{} As {} units are reserved for other sales orders, you are allowed to consume only {} units.".format(
							msg, frappe.bold(self.reserved_stock), frappe.bold(allowed_qty)
						)
					else:
						msg = f"{msg} As the full stock is reserved for other sales orders, you're not allowed to consume the stock."

				msg_list.append(msg)

		if msg_list:
			message = "\n\n".join(msg_list)
			if self.verbose:
				frappe.throw(message, NegativeStockError, title=_("Insufficient Stock"))
			else:
				raise NegativeStockError(message)

	def update_bin_data(self, sle):
		bin_name = get_or_make_bin(sle.item, sle.warehouse, sle.lot, sle.received_type)
		values_to_update = {
			"actual_qty": sle.qty_after_transaction,
		}

		# if sle.valuation_rate is not None:
		# 	values_to_update["valuation_rate"] = sle.valuation_rate

		frappe.db.set_value("Bin", bin_name, values_to_update)

	def update_bin(self):
		# update bin for each warehouse
		for key, data in self.data.items():
			bin_name = get_or_make_bin(self.item, key[0], key[1], key[2])

			updated_values = {"actual_qty": data.qty_after_transaction}
			# if data.valuation_rate is not None:
			# 	updated_values["valuation_rate"] = data.valuation_rate
			frappe.db.set_value("Bin", bin_name, updated_values, update_modified=True)


def get_previous_sle_of_current_voucher(args, operator="<", exclude_current_voucher=False):
	"""get stock ledger entries filtered by specific posting datetime conditions"""

	if not args.get("posting_date"):
		args["posting_datetime"] = "1900-01-01 00:00:00"

	if not args.get("posting_datetime"):
		args["posting_datetime"] = get_combine_datetime(args["posting_date"], args["posting_time"])

	voucher_condition = ""
	if exclude_current_voucher:
		voucher_no = args.get("voucher_no")
		voucher_condition = f"and voucher_no != '{voucher_no}'"

	elif args.get("creation") and args.get("sle_id"):
		creation = args.get("creation")
		operator = "<="
		voucher_condition = f"and creation < '{creation}'"

	sle = frappe.db.sql(  # nosemgrep
		f"""
		select *, posting_datetime as "timestamp"
		from `tabStock Ledger Entry`
		where item = %(item)s
			and warehouse = %(warehouse)s
			and lot = %(lot)s
			and received_type = %(received_type)s
			and is_cancelled = 0
			{voucher_condition}
			and (
				posting_datetime {operator} %(posting_datetime)s
			)
		order by posting_datetime desc, creation desc
		limit 1
		for update""",
		{
			"item": args.get("item"),
			"warehouse": args.get("warehouse"),
			"lot": args.get("lot"),
			"received_type":args.get("received_type"),
			"posting_datetime": args.get("posting_datetime"),
		},
		as_dict=1,
	)

	return sle[0] if sle else frappe._dict()


def get_previous_sle(args, for_update=False, extra_cond=None):
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
	sle = get_stock_ledger_entries(
		args, "<=", "desc", "limit 1", for_update=for_update, extra_cond=extra_cond
	)
	return sle and sle[0] or {}


def get_stock_ledger_entries(
	previous_sle,
	operator=None,
	order="desc",
	limit=None,
	for_update=False,
	debug=False,
	# check_serial_no=True,
	extra_cond=None,
):
	"""get stock ledger entries filtered by specific posting datetime conditions"""
	conditions = f" and posting_datetime {operator} %(posting_datetime)s"
	if previous_sle.get("warehouse"):
		conditions += " and warehouse = %(warehouse)s"
	elif previous_sle.get("warehouse_condition"):
		conditions += " and " + previous_sle.get("warehouse_condition")

	if previous_sle.get("lot"):
		conditions += " and lot = %(lot)s"
	
	if previous_sle.get('received_type'):
		conditions += " and received_type = %(received_type)s"

	if not previous_sle.get("posting_date"):
		previous_sle["posting_datetime"] = "1900-01-01 00:00:00"
	else:
		posting_time = previous_sle.get("posting_time")
		if not posting_time:
			posting_time = "00:00:00"

		previous_sle["posting_datetime"] = get_combine_datetime(previous_sle["posting_date"], posting_time)

	if operator in (">", "<=") and previous_sle.get("name"):
		conditions += " and name!=%(name)s"

	if extra_cond:
		conditions += f"{extra_cond}"

	# nosemgrep
	return frappe.db.sql(
		"""
		select *, posting_datetime as "timestamp"
		from `tabStock Ledger Entry`
		where item = %(item)s
		and is_cancelled = 0
		{conditions}
		order by posting_datetime {order}, creation {order}
		{limit} {for_update}""".format(
			conditions=conditions,
			limit=limit or "",
			for_update=for_update and "for update" or "",
			order=order,
		),
		previous_sle,
		as_dict=1,
		debug=debug,
	)
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


def update_qty_in_future_sle(args, allow_negative_stock=False):
	"""Recalculate Qty after Transaction in future SLEs based on current SLE."""
	datetime_limit_condition = ""
	qty_shift = args.qty

	# args["time_format"] = "%H:%i:%s"
	args["posting_datetime"] = get_combine_datetime(args["posting_date"], args["posting_time"])

	# find difference/shift in qty caused by stock reconciliation
	if args.voucher_type == "Stock Reconciliation":
		qty_shift = get_stock_reco_qty_shift(args)

	# find the next nearest stock reco so that we only recalculate SLEs till that point
	next_stock_reco_detail = get_next_stock_reco(args)
	if next_stock_reco_detail:
		detail = next_stock_reco_detail[0]
		# add condition to update SLEs before this date & time
		datetime_limit_condition = get_datetime_limit_condition(detail)

	frappe.db.sql(
		f"""
		update `tabStock Ledger Entry`
		set qty_after_transaction = qty_after_transaction + {qty_shift}
		where
			item = %(item)s
			and warehouse = %(warehouse)s
			and lot = %(lot)s
			and received_type = %(received_type)s
			and voucher_no != %(voucher_no)s
			and is_cancelled = 0
			and (
				posting_datetime > %(posting_datetime)s
			)
			{datetime_limit_condition}
		""",
		args,
	)

	validate_negative_qty_in_future_sle(args, allow_negative_stock)


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
		.force_index("item_warehouse_lot")
		.where(
			(sle.item == kwargs.get("item"))
			& (sle.warehouse == kwargs.get("warehouse"))
			& (sle.voucher_type == "Stock Reconciliation")
			& (sle.voucher_no != kwargs.get("voucher_no"))
			& (sle.is_cancelled == 0)
			& (
				sle.posting_datetime
				>= get_combine_datetime(kwargs.get("posting_date"), kwargs.get("posting_time"))
			)
		)
		.orderby(sle.posting_datetime)
		.orderby(sle.creation)
		.limit(1)
	)

	if kwargs.get("lot"):
		query = query.where(sle.lot == kwargs.get("lot"))
	
	if kwargs.get("received_type"):
		query = query.where(sle.received_type == kwargs.get("received_type"))

	return query.run(as_dict=True)


def get_datetime_limit_condition(detail):
	posting_datetime = get_combine_datetime(detail.posting_date, detail.posting_time)

	return f"""
		and
		(posting_datetime < '{posting_datetime}'
			or (
				posting_datetime = '{posting_datetime}'
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
			frappe.get_desk_link("Item Variant", args.item),
			frappe.get_desk_link("Supplier", args.warehouse),
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
			and posting_datetime >= %(posting_datetime)s
			and is_cancelled = 0
			and qty_after_transaction < 0
		order by posting_datetime asc
		limit 1
	""",
		args,
		as_dict=1,
	)

