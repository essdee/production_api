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

	def on_submit(self):
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
