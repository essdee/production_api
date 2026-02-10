# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe, json, math, requests, base64
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

		headers = data[0]
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
		
		# Generate print preview for first row across all DPI versions
		if rows:
			self.generate_print_preview(rows[0])

	def generate_print_preview(self, first_row):
		"""Generate print preview HTML for first row across all available DPI versions"""
		if not self.print_format:
			return
		
		try:
			print_format_doc = frappe.get_doc("Essdee Raw Print Format", self.print_format)
		except Exception:
			return
		
		width = print_format_doc.width or 4
		height = print_format_doc.height or 6
		
		preview_html = '<div class="print-preview-container" style="margin: 20px 0;">'
		preview_html += '<h4 style="margin-bottom: 15px;">Print Preview (First Row Data)</h4>'
		
		# Get all available DPI versions from the print format
		dpi_versions = []
		for p in print_format_doc.raw_print_format_details:
			if p.printer_type and p.raw_code:
				dpi_versions.append({
					'dpi': p.printer_type,
					'raw_code': p.raw_code
				})
		
		if not dpi_versions:
			preview_html += '<p class="text-muted">No print format templates found in the selected format.</p>'
		else:
			preview_html += '<div style="display: flex; flex-wrap: wrap; gap: 20px;">'
			
			for dpi_version in dpi_versions:
				dpi = dpi_version['dpi']
				raw_code = dpi_version['raw_code']
				
				# Get DPI value for context (203 for 200dpi, 300 for 300dpi)
				dpi_value = 203 if '200' in dpi else 300
				dpmm = 8 if '200' in dpi else 12
				
				# Generate template for single label
				context = {
					'print_quantity': 1,
					'dpi': dpi_value
				}
				context.update(first_row)
				
				try:
					template_output = frappe.render_template(raw_code, context)
					
					# Call Labelary API for image preview
					url = f"http://api.labelary.com/v1/printers/{dpmm}dpmm/labels/{width}x{height}/0/"
					image_html = ""
					try:
						response = requests.post(url, data=template_output, timeout=10)
						if response.status_code == 200:
							img_base64 = base64.b64encode(response.content).decode()
							image_html = f'''
								<div style="text-align: center; margin-bottom: 15px; background: white; padding: 10px; border: 1px solid #eee;">
									<img src="data:image/png;base64,{img_base64}" style="max-width: 100%; height: auto; border: 1px solid #ddd;">
								</div>
							'''
						else:
							image_html = f'<div class="alert alert-warning" style="font-size: 11px;">Labelary Preview Failed (HTTP {response.status_code})</div>'
					except Exception as ex:
						image_html = f'<div class="alert alert-danger" style="font-size: 11px;">Labelary Connection Error: {str(ex)}</div>'

					preview_html += f'''
					<div style="border: 1px solid #d1d8dd; border-radius: 4px; padding: 15px; background: #fafbfc; flex: 1; min-width: 300px;">
						<h5 style="margin-top: 0; margin-bottom: 10px; color: #36414c; border-bottom: 1px solid #eee; padding-bottom: 5px;">{dpi} Preview</h5>
						{image_html}
						<details>
							<summary style="cursor: pointer; color: #5e64ff; font-size: 12px; margin-bottom: 5px;">Show ZPL Code</summary>
							<div style="background: white; border: 1px solid #e5e7eb; padding: 10px; font-family: monospace; font-size: 11px; overflow-x: auto; white-space: pre-wrap; word-break: break-all; max-height: 150px; overflow-y: auto;">
								{template_output}
							</div>
						</details>
					</div>
					'''
				except Exception as e:
					preview_html += f'''
					<div style="border: 1px solid #d1d8dd; border-radius: 4px; padding: 15px; background: #fafbfc; flex: 1; min-width: 300px;">
						<h5 style="margin-top: 0; margin-bottom: 10px; color: #36414c;">{dpi}</h5>
						<p class="text-danger">Error rendering template: {str(e)}</p>
					</div>
					'''
			
			preview_html += '</div>'
		
		# Show first row data for reference
		preview_html += '<div style="margin-top: 20px; padding: 15px; background: #f5f7fa; border-radius: 4px;">'
		preview_html += '<h5 style="margin-top: 0; margin-bottom: 10px;">First Row Data (Source for Preview):</h5>'
		preview_html += '<div style="max-height: 200px; overflow-y: auto;">'
		preview_html += '<table class="table table-bordered table-condensed" style="background: white; font-size: 12px;">'
		preview_html += '<thead><tr style="background: #f0f0f0;"><th>Field</th><th>Value</th></tr></thead><tbody>'
		for key, value in first_row.items():
			preview_html += f'<tr><td style="font-weight: bold; width: 30%;">{key}</td><td>{value if value is not None else ""}</td></tr>'
		preview_html += '</tbody></table></div></div>'
		
		preview_html += '</div>'
		
		self.print_preview_html = preview_html
		self.db_set("print_preview_html", self.print_preview_html)

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

	label_count = print_format_doc.labels_per_row or 1
	data = json.loads(doc.serialized_data)

	templates = ""
	dpi_value = 203 if '200' in printer_res else 300
	
	for row in data:
		qty = 0
		# Search for quantity column
		for key in row.keys():
			if key and str(key).lower() in ["qty", "quantity", "print count", "print_count", "count"]:
				try:
					qty = int(float(row[key]))
					break
				except:
					qty = 0

		if qty > 0:
			templates += get_template(row, raw_code, label_count, qty, dpi_value)

	return templates

def get_template(row, raw_code, label_count, qty, dpi_value=203):
	print_quantity = int(math.ceil(float(qty) / int(label_count)))
	
	# Inject row data into template context
	context = {
		'print_quantity': print_quantity,
		'dpi': dpi_value
	}
	context.update(row)
	
	template = frappe.render_template(raw_code, context)
	return template