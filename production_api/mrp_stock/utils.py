import frappe
from frappe.utils import flt, get_time, getdate, nowdate, nowtime

@frappe.whitelist()
def get_stock_balance(
	item,
	warehouse,
	posting_date=None,
	posting_time=None,
	with_valuation_rate=False,
	lot=None,
	uom=None
):
	"""Returns stock balance quantity at given warehouse on given posting date or current date.

	If `with_valuation_rate` is True, will return tuple (qty, rate)"""

	from production_api.mrp_stock.stock_ledger import get_previous_sle

	if posting_date is None:
		posting_date = nowdate()
	if posting_time is None:
		posting_time = nowtime()

	args = {
		"item": item,
		"warehouse": warehouse,
		"posting_date": posting_date,
		"posting_time": posting_time,
		"posting_datetime": get_combine_datetime(posting_date, posting_time),
		"lot":lot,
	}

	last_entry = get_previous_sle(args)
	qty = 0.0
	rate = 0.0

	if last_entry:
		qty = last_entry.qty_after_transaction
		rate = last_entry.valuation_rate
		if uom:
			cd = get_conversion_factor(item, uom)
			conversion_factor = flt(cd["conversion_factor"])
			qty = qty / conversion_factor
			rate = rate * conversion_factor

	if with_valuation_rate:
		return (
            (qty, rate)
        )
	else:
		return qty

def get_incoming_outgoing_rate_for_cancel(item, voucher_type, voucher_no, voucher_detail_no):
	outgoing_rate = frappe.db.sql(
		"""SELECT CASE WHEN qty = 0 THEN 0 ELSE abs(stock_value_difference / qty) END
		FROM `tabStock Ledger Entry`
		WHERE voucher_type = %s and voucher_no = %s
			and item = %s and voucher_detail_no = %s
			ORDER BY CREATION DESC limit 1""",
		(voucher_type, voucher_no, item, voucher_detail_no),
	)

	outgoing_rate = outgoing_rate[0][0] if outgoing_rate else 0.0

	return outgoing_rate

def get_conversion_factor(item_variant, uom):
	variant_of = frappe.db.get_value("Item Variant", item_variant, "item", cache=True)
	filters = {"parent": variant_of, "uom": uom}

	conversion_factor = frappe.db.get_value("UOM Conversion Detail", filters, "conversion_factor")

	return {
		"conversion_factor": conversion_factor or 1.0,
		"stock_uom": frappe.db.get_value("Item", variant_of, "default_unit_of_measure", cache=True)
	}

def future_sle_exists(args, sl_entries=None, allow_force_reposting=True):
	# and frappe.db.get_single_value(
	# 	"Stock Reposting Settings", "do_reposting_for_each_stock_transaction"
	# ):
	if allow_force_reposting:
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

	data = frappe.db.sql(
		"""
		select item, warehouse, lot, count(name) as total_row
		from `tabStock Ledger Entry` force index (item_warehouse_lot)
		where
			({})
			and posting_datetime >= timestamp(%(posting_date)s, %(posting_time)s)
			and voucher_no != %(voucher_no)s
			and is_cancelled = 0
		GROUP BY
			item, warehouse, lot
		""".format(" or ".join(or_conditions)),
		args,
		as_dict=1,
	)

	for d in data:
		frappe.local.future_sle[key][(d.item_code, d.warehouse, d.lot)] = d.total_row

	return len(data)

def validate_future_sle_not_exists(args, key, sl_entries=None):
	item_key = ""
	if args.get("item"):
		item_key = (args.get("item"), args.get("warehouse"), args.get("lot"))

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
		item_key = (args.get("item"), args.get("warehouse"), args.get("lot"))
		count = frappe.local.future_sle[key].get(item_key)

		return True if (count or count == 0) else False
	else:
		return frappe.local.future_sle[key]


def get_sle_entries_against_voucher(args):
	return frappe.get_all(
		"Stock Ledger Entry",
		filters={"voucher_type": args.voucher_type, "voucher_no": args.voucher_no},
		fields=["item", "warehouse", "lot"],
		order_by="creation asc",
	)


def get_conditions_to_validate_future_sle(sl_entries):
	warehouse_items_map = {}
	for entry in sl_entries:
		key = (entry.warehouse, entry.lot)
		if key not in warehouse_items_map:
			warehouse_items_map[key] = set()

		warehouse_items_map[key].add(entry.item)

	or_conditions = []
	for key, items in warehouse_items_map.items():
		or_conditions.append(
			f"""warehouse = {frappe.db.escape(key[0])} and lot = {frappe.db.escape(key[1])}
				and item_code in ({', '.join(frappe.db.escape(item) for item in items)})"""
		)

	return or_conditions

def get_combine_datetime(posting_date, posting_time):
	import datetime

	if isinstance(posting_date, str):
		posting_date = getdate(posting_date)

	if isinstance(posting_time, str):
		posting_time = get_time(posting_time)

	if isinstance(posting_time, datetime.timedelta):
		posting_time = (datetime.datetime.min + posting_time).time()

	return datetime.datetime.combine(posting_date, posting_time).replace(microsecond=0)