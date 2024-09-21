# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from itertools import zip_longest
from frappe.utils import add_to_date,nowdate, add_months, getdate
import math

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
	if mrp is None:
		mrp = ""
	mrp = mrp.split(",")
	fg_data = []
	for x, y in zip_longest(sizes, mrp, fillvalue=None):
		fg_data.append({
			'size':x,
			'mrp':y
		})
	return fg_data

@frappe.whitelist()
def get_print_format(print_format, quantity, size, mrp, piece_per_box, fg_item, printer, doc_name,lot, use_item_name:int):
	label_count, raw_code, sizepad,piece_price_pad,box_price_pad,mfd_pad = frappe.get_value('Essdee Raw Print Format', print_format, ['labels_per_row', 'raw_code','size_pad','piece_price_pad','box_price_pad','mfd_pad'])
	piece_per_box = int(piece_per_box)
	if doc_name:
		print_qty, qty , allow_excess, allow_excess_percent= frappe.get_value('Box Sticker Print Detail',doc_name,['printed_quantity','quantity','allow_excess_quantity','allow_excess_percentage'])
		print_qty = int(print_qty) + int(quantity)
		
		if print_qty > qty and not allow_excess:
			if allow_excess_percent:
				allowed_qty = int(math.ceil((qty/100) * allow_excess_percent))
				qty = allowed_qty + qty
				if print_qty > qty:
					frappe.msgprint("Not applicable to print more than the required quantity")
					return None
			else:
				frappe.msgprint("Not applicable to print more than the required quantity")
				return None
		
	if len(size) < sizepad:
		length = sizepad - len(size)
		size = size.ljust(sizepad, ' ')
	
	box_mrp = str(piece_per_box * int(mrp)) + ".00"
	
	if len(box_mrp) < box_price_pad:
		length = box_price_pad - len(box_mrp)
		box_mrp = box_mrp.ljust(length, ' ')
	
	mrp = str(mrp) + ".00"
	if len(mrp) < piece_price_pad:
		length = piece_price_pad - len(mrp)
		mrp = mrp.ljust(length, ' ')
	
	print_quantity = int(math.ceil(int(quantity) / int(label_count)))
	now = add_to_date(nowdate(), days=15)
	date = getdate(now)
	months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
	mfd = str(months[date.month-1])+"/"+str(date.year)+"/"+str(lot)
	mddate_year = str(months[date.month-1])+"/"+str(date.year)
	if len(mfd) < mfd_pad:
		length = mfd_pad - len(mfd)
		mfd = mfd.ljust(length, ' ')

	if use_item_name == 0:
		display_name = frappe.get_value("FG Item Master", fg_item,'display_name')
		if display_name:
			fg_item = display_name

	item_name_len = 35 if len(fg_item) > 20 else 45
	template = frappe.render_template(raw_code, {
		'print_quantity': print_quantity,
        'item_name': fg_item,
        'piece_price': mrp,
        'box_price': box_mrp,
        'piece_size': size,
		'mfdate':mfd,
		'item_size':item_name_len,
		'mfdateyear':mddate_year,
    })
	
	if doc_name:
		m = print_qty % label_count
		frappe.db.set_value('Box Sticker Print Detail',doc_name,'printed_quantity',print_qty+m)
		frappe.db.commit()
	printer = printer[1:-1]

	return {
		"print_format":template,
		"printer":printer
	}

@frappe.whitelist()
def override_print_quantity(quantity, doc_name):
	print_qty = frappe.get_value('Box Sticker Print Detail',doc_name,'printed_quantity')
	frappe.db.set_value('Box Sticker Print Detail',doc_name,'printed_quantity',int(print_qty)-int(quantity))
	frappe.db.commit()

@frappe.whitelist()
def get_raw_code(print_format, doc_name, use_item_name):
	doc = frappe.get_doc("Box Sticker Print", doc_name)
	width , height = frappe.get_value("Essdee Raw Print Format", print_format,['width','height'])
	# code = get_print_format(print_format, 5, "1200CM", 1000, 5, doc.fg_item, "printer", None,doc.lot)
	code = get_print_format(print_format, 5, doc.box_sticker_print_details[0].size, int(doc.box_sticker_print_details[0].mrp), 5, doc.fg_item, "printer", None,doc.lot, use_item_name)
	
	return {
		"code":code['print_format'],
		"height": height,
		"width":width,
	}