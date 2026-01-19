# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class StockEntryDetail(Document):
	pass

def on_doctype_update():
	frappe.db.add_index("Stock Entry Detail", ["item","lot"])
