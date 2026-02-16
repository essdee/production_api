# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe, json, math
from frappe.model.document import Document
from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file
from frappe.utils.file_manager import get_file_path

class ExcelStickerPrint(Document):
	def on_submit(self):
		self.process_excel()

	def process_excel(self):
		if not self.excel_file:
			frappe.throw("Please upload an Excel file")

		file_path = get_file_path(self.excel_file)
		with open(file_path, "rb") as f:
			content = f.read()

		data = read_xlsx_file_from_attached_file(fcontent=content)
		if not data:
			frappe.throw("Excel file is empty")

		headers = [
			str(h).strip().lower().replace(' ', '_') if h else f'column_{i}'
			for i, h in enumerate(data[0])
		]
		rows = []
		for row_data in data[1:]:
			row_dict = {}
			for i, header in enumerate(headers):
				if i < len(row_data):
					row_dict[header] = row_data[i]
				else:
					row_dict[header] = None
			rows.append(row_dict)

		self.serialized_data = json.dumps(rows)
		self.db_set("serialized_data", self.serialized_data)

@frappe.whitelist()
def get_raw_code(doc_name):
	doc = frappe.get_doc("Excel Sticker Print", doc_name)
	if not doc.serialized_data:
		frappe.throw("No data found. Please ensure the document is submitted.")

	print_format_doc = frappe.get_doc("Essdee Raw Print Format", doc.print_format)
	raw_code = None
	for p in print_format_doc.raw_print_format_details:
		if p.printer_type == "300dpi":
			raw_code = p.raw_code
			break

	if not raw_code and print_format_doc.raw_print_format_details:
		raw_code = print_format_doc.raw_print_format_details[0].raw_code

	if not raw_code:
		frappe.throw("Print Format is not defined")

	data = json.loads(doc.serialized_data)
	if not data:
		frappe.throw("No rows in data")

	first_row = data[0]
	context = {
		'print_quantity': 1,
		'dpi': 300,
	}
	context.update(first_row)

	code = frappe.render_template(raw_code, context)
	return {
		"code": code,
		"height": print_format_doc.height,
		"width": print_format_doc.width,
	}

@frappe.whitelist()
def get_print_format(doc_name, printer_res="200dpi"):
	doc = frappe.get_doc("Excel Sticker Print", doc_name)
	if not doc.serialized_data:
		frappe.throw("No data found to print. Please ensure the document is submitted.")

	print_format_doc = frappe.get_doc("Essdee Raw Print Format", doc.print_format)
	
	raw_code = None
	for p in print_format_doc.raw_print_format_details:
		if p.printer_type == printer_res:
			raw_code = p.raw_code
	
	if not raw_code:
		# Fallback to the first available if requested not found
		if print_format_doc.raw_print_format_details:
			raw_code = print_format_doc.raw_print_format_details[0].raw_code
			printer_res = print_format_doc.raw_print_format_details[0].printer_type
		else:
			frappe.throw("Print Format Res not defined")

	data = json.loads(doc.serialized_data)

	templates = ""
	dpi_value = 203 if '200' in printer_res else 300
	
	for row in data:
		if row['print_quantity'] > 0:
			templates += get_template(row, raw_code, dpi_value=dpi_value)

	return templates

def get_template(row, raw_code, dpi_value=203):
	context = {
		'dpi': dpi_value
	}
	context.update(row)
	
	template = frappe.render_template(raw_code, context)
	return template