# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DeliveryChallanItem(Document):
	pass

def on_doctype_update():
	frappe.db.add_index("Delivery Challan Item", ["item_variant","lot"])
