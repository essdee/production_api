# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe, math
from frappe.model.document import Document

class SalesPieceStickerPrint(Document):
	pass

@frappe.whitelist()
def get_print_format(doc_name):
	doc = frappe.get_single("Sales Piece Sticker Print")
	print_format_doc = frappe.get_doc("Essdee Raw Print Format", doc.print_format)
	if doc.brand == 'Essdee':
		res = "200dpi"
	else:
		res = "300dpi"

	raw_code = None
	for p in print_format_doc.raw_print_format_details:
		if p.printer_type == res:
			raw_code = p.raw_code
	
	if not raw_code:
		frappe.throw("Print Format Res not defined")

	label_count = print_format_doc.labels_per_row

	templates = ""
	for item in doc.sales_piece_sticker_print_details:
		templates += get_template(item, raw_code, label_count, doc.brand)

	return templates

def get_template(item, raw_code, label_count, brand):
	mrp = "{:.2f}".format(float(item.mrp_price))
	offer_price = "{:.2f}".format(float(item.offer_price))
	print_quantity = int(math.ceil(item.quantity) / int(label_count))

	template = frappe.render_template(raw_code, {
		'print_quantity': print_quantity,
		'mrp_price': str(mrp),
		'offer_price': str(offer_price),
		'sku': str(item.sku),
		'dpi':203,
		"brand": brand
	})
	return template