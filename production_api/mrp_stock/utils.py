import frappe
from frappe.utils import nowdate, nowtime, flt

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
			conversion_factor = flt(cd["coversion_factor"])
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