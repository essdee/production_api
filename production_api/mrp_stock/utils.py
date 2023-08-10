import frappe
from frappe.utils import nowdate, nowtime

@frappe.whitelist()
def get_stock_balance(
	item,
	warehouse,
	posting_date=None,
	posting_time=None,
	with_valuation_rate=False,
	lot=None,
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

	if with_valuation_rate:
		return (
            (last_entry.qty_after_transaction, last_entry.valuation_rate) if last_entry else (0.0, 0.0)
        )
	else:
		return last_entry.qty_after_transaction if last_entry else 0.0

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