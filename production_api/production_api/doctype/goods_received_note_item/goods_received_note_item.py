# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class GoodsReceivedNoteItem(Document):
	pass

def on_doctype_update():
	frappe.db.add_index("Goods Received Note Item", ["item_variant","lot"])
