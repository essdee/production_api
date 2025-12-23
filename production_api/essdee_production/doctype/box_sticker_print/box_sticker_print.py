# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe, json
from frappe.model.document import Document
from itertools import zip_longest
from frappe.utils import add_to_date,nowdate, add_months, getdate
import math
from six import string_types

class BoxStickerPrint(Document):
	def before_validate(self):
		sum = 0
		for item in self.box_sticker_print_details:
			sum = sum+item.quantity
		if sum == 0:
			frappe.throw("Enter the quantity")	

@frappe.whitelist()
def get_fg_details(fg_item):
	sizes, mrp = frappe.get_value("FG Item Master",fg_item,['available_sizes','mrp'])
	sizes = sizes.split(",")
	fg_data = []
	if mrp is None or mrp == "":
		box_print_list = frappe.get_list("Box Sticker Print",filters= {"fg_item":fg_item}, order_by='creation desc',pluck='name',limit=1)
		if len(box_print_list) > 0:
			box_sticker_doc = frappe.get_doc('Box Sticker Print', box_print_list[0])
			for item in box_sticker_doc.box_sticker_print_details:
				fg_data.append({
					'size':item.size,
					'mrp':item.mrp,
				})
			return fg_data
		else:
			mrp = ""
	
	mrp = mrp.split(",")
	
	for x, y in zip_longest(sizes, mrp, fillvalue=None):
		fg_data.append({
			'size':x,
			'mrp':y
		})
	return fg_data

@frappe.whitelist()
def get_print_format(doc, print_items, printer_type):
	doc = frappe.get_doc("Box Sticker Print", doc)
	fg_item = doc.fg_item

	print_format_doc = frappe.get_doc("Essdee Raw Print Format", doc.print_format)
	res = printer_type
	raw_code = None
	for p in print_format_doc.raw_print_format_details:
		if p.printer_type == res:
			raw_code = p.raw_code
	
	if not raw_code:
		frappe.throw("Print Format Res not defined")

	label_count = print_format_doc.labels_per_row
	if isinstance(print_items, string_types):
		print_items = json.loads(print_items)
	
	templates = ""
	for item in print_items:
		print_qty, qty , allow_excess, allow_excess_percent= frappe.get_value('Box Sticker Print Detail',item['doc_name'],['printed_quantity','quantity','allow_excess_quantity','allow_excess_percentage'])
		check_print_qty = int(print_qty) + int(item['quantity'])
		
		if check_print_qty > qty and not allow_excess:
			if allow_excess_percent:
				allowed_qty = int(math.ceil((qty/100) * allow_excess_percent))
				qty = allowed_qty + qty
				if check_print_qty > qty:
					frappe.msgprint("Not applicable to print more than the required quantity")
					return None
			else:
				frappe.msgprint("Not applicable to print more than the required quantity")
				return None
		
		print_quantity = int(math.ceil(int(item['quantity']) / int(label_count)))
		if doc.size and len(doc.size) > 0:
			item['size'] = doc.size
		templates += get_template(doc, item, raw_code, label_count, fg_item)
	
		frappe.db.set_value('Box Sticker Print Detail',item['doc_name'],'printed_quantity',print_qty + (print_quantity * label_count))
		frappe.db.commit()
	
	return templates

def get_template(doc, item, raw_code,label_count, fg_item):
	box_mrp = "{:.2f}".format(doc.piece_per_box * float(item['mrp']))
	mrp = "{:.2f}".format(float(item['mrp']))
	print_quantity = int(math.ceil(int(item['quantity']) / int(label_count)))
	now = add_to_date(nowdate(), days=15)
	date = getdate(now)
	months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
	mddate_year = str(months[date.month-1])+"/"+str(date.year)
	mfd = mddate_year+"/"+str(doc.lot)		
	if doc.use_item_name == 0:
		display_name = frappe.get_value("FG Item Master", fg_item,'display_name')
		if display_name:
			fg_item = display_name

	template = frappe.render_template(raw_code, {
		'print_quantity': print_quantity,
		'item_name': fg_item,
		'piece_price': str(mrp),
		'box_price': str(box_mrp),
		'piece_size': item['size'],
		'mfdate':mfd,
		'mfdateyear':mddate_year,
		'dpi':203,
	})
	return template

@frappe.whitelist()
def override_print_quantity(print_items, print_format):
	if isinstance(print_items, string_types):
		print_items = json.loads(print_items)
	label_count = frappe.get_value("Essdee Raw Print Format", print_format,'labels_per_row')
	for item in print_items:
		print_quantity = int(math.ceil(int(item['quantity']) / int(label_count)))
		print_qty = frappe.get_value('Box Sticker Print Detail',item['doc_name'],'printed_quantity')
		frappe.db.set_value('Box Sticker Print Detail',item['doc_name'],'printed_quantity',int(print_qty)- (print_quantity*label_count))
		frappe.db.commit()

@frappe.whitelist()
def get_raw_code(doc_name):
	doc = frappe.get_doc("Box Sticker Print", doc_name)
	print_format_doc = frappe.get_doc("Essdee Raw Print Format", doc.print_format)
	res = "300dpi"
	raw_code = None
	for p in print_format_doc.raw_print_format_details:
		if p.printer_type == res:
			raw_code = p.raw_code
	
	if not raw_code:
		frappe.throw("Print Format is not defined")
	# width , height, labels_count = frappe.get_value("Essdee Raw Print Format", doc.print_format,['width','height','labels_per_row'])
	item_dict = doc.box_sticker_print_details[0].as_dict()
	item_dict.quantity = 1
	if doc.size and len(doc.size) > 0:
		item_dict['size'] = doc.size
	code = get_template(doc, item_dict, raw_code, print_format_doc.labels_per_row, doc.fg_item)
	return {
		"code":code,
		"height": print_format_doc.height,
		"width": print_format_doc.width,
	}

@frappe.whitelist()
def get_printer(printers):
	mrp_printer = frappe.db.get_single_value("MRP Settings", "printer_list")
	if isinstance(printers, string_types):
		printers = json.loads(printers)
	if not mrp_printer or mrp_printer == "":
		return printers
	printer_list = mrp_printer.split(",")
	final_printers_list = []
	for printer in printer_list:
		if printer and printer.strip() != "" and printer.strip() in printers:
			final_printers_list.append(printer.strip())

	if len(final_printers_list) > 0:
		return final_printers_list
	else:
		return []
		