# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, nowtime

class StockLedgerEntry(Document):
	def validate(self):
		self.flags.ignore_submit_comment = True

		self.scrub_posting_time()
		self.set_posting_time()
		self.validate_mandatory()
	
	def set_posting_datetime(self, save=False):
		from production_api.mrp_stock.utils import get_combine_datetime

		if save:
			posting_datetime = get_combine_datetime(self.posting_date, self.posting_time)
			if not self.posting_datetime or self.posting_datetime != posting_datetime:
				self.db_set("posting_datetime", posting_datetime)
		else:
			self.posting_datetime = get_combine_datetime(self.posting_date, self.posting_time)

	def on_submit(self):
		self.set_posting_datetime(save=True)
		# self.check_stock_frozen_date()
		# self.calculate_batch_qty()
		pass
	
	def validate_mandatory(self):
		mandatory = ["warehouse", "posting_date", "voucher_type", "voucher_no", "lot", "item"]
		for k in mandatory:
			if not self.get(k):
				frappe.throw(_("{0} is required").format(self.meta.get_label(k)))
		
		if self.voucher_type != "Stock Reconciliation" and not self.qty:
			frappe.throw(_("Qty is required"))

	
	def scrub_posting_time(self):
		if not self.posting_time or self.posting_time == "00:0":
			self.posting_time = "00:00"
	
	def set_posting_time(self):
		if not self.posting_date:
			self.set("posting_date", nowdate())
		if not self.posting_time or self.posting_time == "00:00":
			self.set("posting_time", nowtime())

	def on_cancel(self):
		msg = _("Individual Stock Ledger Entry cannot be cancelled.")
		msg += "<br>" + _("Please cancel related transaction.")
		frappe.throw(msg)

def on_doctype_update():
	frappe.db.add_index("Stock Ledger Entry", ["voucher_no", "voucher_type"])
	frappe.db.add_index("Stock Ledger Entry", ["lot", "item", "warehouse"], "item_warehouse_lot")
	frappe.db.add_index("Stock Ledger Entry", ["warehouse", "item"], "item_warehouse")
	frappe.db.add_index("Stock Ledger Entry", ["posting_datetime", "creation"])
