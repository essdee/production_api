# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class GRNDeliverable(Document):
	pass


def on_doctype_update():
	frappe.db.add_index("GRN Deliverable", ["item_variant"])