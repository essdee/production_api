# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from mimetypes import guess_type
import frappe
from frappe.utils import cint, get_url
from frappe.model.document import Document
from production_api.utils import update_if_string_instance
import os
import fitz

class Product(Document):
	def load_costing_list(self):
		"""Load Lotwise Item Profit List into `__onload`"""
		fields = ["name", "product", "total_qty", "avg_rate_per_piece", "profit_percent_markdown"]
		filters = {"product": self.name}
		costing_list = frappe.get_list("Lotwise Item Profit", fields=fields, filters=filters)
		self.set_onload('costing_list', costing_list)

	def onload(self):
		"""Load Attribute List into `__onload`"""
		self.load_costing_list()
		if len(self.product_placement) > 0:
			upload_data = get_table_onload_data(self.product_placement)
			self.set_onload("placement_images", upload_data)	
		
		if len(self.trims) > 0:
			upload_data = get_table_onload_data(self.trims)
			self.set_onload("trims_images", upload_data)	

		if len(self.product_trim_combination) > 0:
			upload_data = get_table_onload_data(self.product_trim_combination, with_list=True)
			self.set_onload("trims_combination", upload_data)	

		if len(self.product_accessories) > 0:
			upload_data = get_table_onload_data(self.product_accessories)
			self.set_onload("accessory_images", upload_data)	

		if len(self.product_measurement_descriptions) > 0:
			measurement_details = {}
			for row in self.product_measurement_descriptions:
				measurement_details.setdefault(row.group, [])
				measurement_details[row.group].append(row.description)
			self.set_onload("measurement_details", measurement_details)	

	def before_validate(self):
		colours = []
		if self.is_set_item:
			if self.top_measurement:
				if frappe.get_value("Product Measurement", self.top_measurement, "docstatus") != 1:
					frappe.throw("Top Measurement is not submitted")
			if self.bottom_measurement:
				if frappe.get_value("Product Measurement", self.bottom_measurement, "docstatus") != 1:
					frappe.throw("Bottom Measurement is not submitted")
			for row in self.product_set_colours:
				if row.top_colour not in colours:
					colours.append(row.top_colour)
				if row.bottom_colour not in colours:
					colours.append(row.bottom_colour)	
		else:
			if self.measurement:
				if frappe.get_value("Product Measurement", self.measurement, "docstatus") != 1:
					frappe.throw("Measurement is not submitted")
			for row in self.product_colours:
				if row.product_colour not in colours:
					colours.append(row.product_colour)	

		if self.get('placement_images') not in [None]:
			placement_images = update_if_string_instance(self.placement_images)
			image_list = get_tabel_struct_data(placement_images)
			self.set("product_placement", image_list)	
		
		if self.get('product_trims_images') not in [None]:
			trims = update_if_string_instance(self.product_trims_images)
			image_list = get_tabel_struct_data(trims)
			self.set("trims", image_list)	
		
		if self.get("trim_comb") not in [None]:
			trim_comb = update_if_string_instance(self.trim_comb)
			image_list = get_tabel_struct_data(trim_comb, with_list=True, colour_list=colours)	
			self.set("product_trim_combination", image_list)

		if self.get('accessory_images') not in [None]:
			accessory_images = update_if_string_instance(self.accessory_images)
			image_list = get_tabel_struct_data(accessory_images)
			self.set("product_accessories", image_list)	

		if self.get("measurement_details") not in [None]:
			measurement_details = update_if_string_instance(self.measurement_details)
			items_list = []
			for key in measurement_details:
				for val in measurement_details[key]:
					items_list.append({
						"description": val,
						"group": key
					})
			self.set("product_measurement_descriptions", items_list)	

		if self.is_set_item:
			is_cord = True
			for row in self.product_set_colours:
				if row.top_colour != row.bottom_colour:
					is_cord = False
					break
			self.is_cord = 1 if is_cord else 0	
			items = []
			if self.top_measurement:
				doc = frappe.get_doc("Product Measurement", self.top_measurement)
				for row in doc.product_measurement_descriptions:
					items.append({
						"description": row.description,
						"group": "Top",
					})
			if self.bottom_measurement:		
				doc = frappe.get_doc("Product Measurement", self.bottom_measurement)
				for row in doc.product_measurement_descriptions:
					items.append({
						"description": row.description,
						"group": "Bottom",
					})	
			self.set("product_measurement_descriptions", items)		
		else:
			self.is_cord = 0	
			items = []
			if self.measurement:
				doc = frappe.get_doc("Product Measurement", self.measurement)
				for row in doc.product_measurement_descriptions:
					items.append({
						"description": row.description,
						"group": "Part",
					})	
			self.set("product_measurement_descriptions", items)					

def get_table_onload_data(table, with_list=False):
	upload_data = []
	for row in table:
		d = {
			"image_url": get_url(frappe.get_value("Product Image", row.product_image, "image")),
			"image_title": row.title_header,
			"image_name": row.product_image
		}
		if with_list:
			if row.get('part'):
				d['selected_part'] = row.part
			d['selected_colours'] = row.selected_colours.split(",")
		upload_data.append(d)
	return upload_data
	
def get_tabel_struct_data(data, with_list=False, colour_list=[]):
	image_list = []
	for row in data:
		d = {
			"product_image": row['image_name'],
			"url": row['image_url'],
			"title_header": row['image_title'],
		}
		if with_list:
			if row.get('selected_part'):
				d['part'] = row.get('selected_part')
			selected_colours = row.get("selected_colours") or []
			colour_list = []
			for colour in selected_colours:
				if colour not in colour_list:
					colour_list.append(colour)
			d['selected_colours'] = ",".join(colour_list)
		image_list.append(d)
	return image_list

@frappe.whitelist()
def upload_product_file():
	files = frappe.request.files
	is_private = frappe.form_dict.is_private
	doctype = frappe.form_dict.doctype
	docname = frappe.form_dict.docname
	fieldname = frappe.form_dict.fieldname
	file_url = frappe.form_dict.file_url
	folder = frappe.form_dict.folder or "Home"
	method = frappe.form_dict.method
	filename = frappe.form_dict.file_name
	optimize = frappe.form_dict.optimize
	content = frappe.local.uploaded_file

	file_type = filename.split("_")[1]

	product = frappe.get_doc(doctype, docname)
	product_files = product.get("product_file_versions")
	if not product_files:
		product_files = []
		product.set("product_file_versions", product_files)
	
	files_of_type = [f for f in product_files if f.product_upload_type == file_type]
	version = len(files_of_type) + 1

	extension = filename.split(".")[-1]
	filename = f"{product.name}_{file_type}_{version}"
	if extension:
		filename = f"{filename}.{extension}"
	
	folder = get_or_create_product_folder(doctype, docname)
	file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"attached_to_doctype": doctype,
				"attached_to_name": docname,
				"attached_to_field": fieldname,
				"folder": folder,
				"file_name": filename,
				"file_url": file_url,
				"is_private": cint(is_private),
				"content": content,
			}
		)
	file_doc.save(ignore_permissions=True)
	# create a new row in product_file_versions
	product_file_row = {
		"product_upload_type": file_type,
		"file": file_doc.name,
		"filename": filename,
		"file_url": file_doc.file_url,
		"version_number": version,
		"timestamp": file_doc.creation,
	}
	if product.get("product_file_versions"):
		product.append("product_file_versions", product_file_row)
	else:
		product.set("product_file_versions", [product_file_row])
	product.save()
	return file_doc

def get_or_create_product_folder(doctype, docname):
	# Convert doctype and docname to lowercase and remove spaces and other characters not allowed in folder names
	# Check if doctype folder exists
	# If not create it
	# Check if docname folder exists
	# If not create it
	# Return the folder name

	doctype = doctype.lower().replace(" ", "_")
	docname = docname.lower().replace(" ", "_")
	doctype_folder_name = frappe.get_value(
		"File",
		{
			"file_name": doctype,
			"is_folder": 1,
			"folder": "Home",
		},
		"name",
	)
	if not doctype_folder_name:
		doctype_folder = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": doctype,
				"is_folder": 1,
				"folder": "Home",
			}
		)
		doctype_folder.save(ignore_permissions=True)
		doctype_folder_name = doctype_folder.name

	# Create folder for docname with parent folder as doctype
	docname_folder_name = frappe.db.exists(
		"File",
		{
			"file_name": docname,
			"is_folder": 1,
			"folder": doctype_folder_name,
		},
	)
	if not docname_folder_name:
		docname_folder = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": docname,
				"is_folder": 1,
				"folder": doctype_folder_name,
			}
		)
		docname_folder.save(ignore_permissions=True)
		docname_folder_name = docname_folder.name

	return docname_folder_name

def get_latest_product_images(product_name):
	product = frappe.get_doc("Product", product_name)
	product_files = product.get("product_file_versions")
	# return latest image of each upload type
	grouped_files = get_grouped_files(product_files)
	latest_files = [ group[0] for group in grouped_files.values() ]
	product_images = []
	for file in latest_files:
		content_type = guess_type(file.filename)[0]
		if content_type and content_type.startswith("image/"):
			product_images.append(file)

	return product_images

def get_grouped_files(files):
	# Group files by product_upload_type
	grouped_files = {}
	for file in files:
		if file.product_upload_type not in grouped_files:
			grouped_files[file.product_upload_type] = []
		grouped_files[file.product_upload_type].append(file)
	# sort files by version number in descending order
	for key in grouped_files:
		grouped_files[key].sort(key=lambda x: x.version_number, reverse=True)
	return grouped_files

@frappe.whitelist()
def get_product_colour_codes(doctype, docname):
	doc = frappe.get_doc(doctype, docname)
	colour_codes = {}
	if doc.is_set_item:
		for row in doc.product_set_colours:
			colour_codes[row.top_colour] = row.top_colour_code
			colour_codes[row.bottom_colour] = row.bottom_colour_code
	else:
		for row in doc.product_colours:
			colour_codes[row.product_colour] = row.colour_code
	return colour_codes		

@frappe.whitelist()
def delete_and_update_file(file_url, fieldname, doctype, docname, updated_url, file_name):
	if file_url:
		files = frappe.get_all("File", filters={
			"attached_to_name": docname,
			"file_url": file_url,
			"attached_to_field": fieldname
		}, pluck="name")
		for file in files:
			frappe.delete_doc("File", file)
	if updated_url:
		file_doc = frappe.get_doc("File", file_name)
		file_doc.attached_to_doctype = doctype
		file_doc.attached_to_name = docname
		file_doc.attached_to_field = fieldname
		file_doc.save()
		doc = frappe.get_doc(doctype, docname)	
		doc.db_set(fieldname, updated_url)

@frappe.whitelist()
def upload_graphics_file():
	files = frappe.request.files

	is_private = frappe.form_dict.is_private
	doctype = frappe.form_dict.doctype
	docname = frappe.form_dict.docname
	fieldname = frappe.form_dict.fieldname
	file_url = frappe.form_dict.file_url
	folder = frappe.form_dict.folder or "Home"
	method = frappe.form_dict.method
	filename = frappe.form_dict.file_name
	optimize = frappe.form_dict.optimize
	content = frappe.local.uploaded_file
	box_detail = frappe.form_dict.box_data
	file_type = filename.split("_")[1]
	product = frappe.get_doc(doctype, docname)
	table_name = "product_designs"
	if box_detail:
		table_name = "product_box_details"

	product_files = product.get(table_name)
	if not product_files:
		product_files = []
		product.set(table_name, product_files)
	
	extension = filename.split(".")[-1]
	filename = f"{product.name}_{file_type}"
	if extension:
		filename = f"{filename}.{extension}"
	
	folder = get_or_create_product_folder(doctype, docname)
	file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"attached_to_doctype": doctype,
				"attached_to_name": docname,
				"attached_to_field": fieldname,
				"folder": folder,
				"file_name": filename,
				"file_url": file_url,
				"is_private": cint(is_private),
				"content": content,
			}
		)
	file_doc.save(ignore_permissions=True)
	product_file_row = {
		"graphic_image": file_doc.file_url,
		"upload_name": file_type,
		"file": file_doc.name,
		"filename": filename,
	}
	
	if product.get(table_name):
		product.append(table_name, product_file_row)
	else:
		product.set(table_name, [product_file_row])
	product.save()
	return file_doc

@frappe.whitelist()
def remove_graphic_image(detail, docname):
	data = update_if_string_instance(detail)
	frappe.db.sql(
		f"""
			DELETE FROM `tabProduct Design` WHERE parent = {frappe.db.escape(data['parent'])}
			AND name = {frappe.db.escape(data['name'])}
		"""
	)
	frappe.delete_doc("File", data['file'])

@frappe.whitelist()
def release_tech_pack(doc_name):
	product_doc = frappe.get_doc("Product", doc_name)
	if product_doc.is_set_item:
		for row in product_doc.product_trim_combination:
			if not row.selected_colours:
				frappe.throw(f"Please select colours in trim colour combination for {row.title_header}")
			if not row.part:
				frappe.throw(f"Please select part in trim colour combination for {row.title_header}")
			
	d = {
		"product": doc_name,
		"is_cord": product_doc.is_cord,
		"item_name": product_doc.item_name,
		"style_no": product_doc.style_no,
		"brand": product_doc.brand,
		"product_group": product_doc.product_group,
		"fabric_details": product_doc.fabric_details,
		"description": product_doc.description,
		"season": product_doc.season,
		"gsm": product_doc.gsm,
		"size_range": product_doc.size_range,
		"is_set_item": product_doc.is_set_item,
		"category": product_doc.category,
		"sub_brand": product_doc.sub_brand,
		"dia": product_doc.dia,
		"product_image": product_doc.product_image,
		"top_image": product_doc.top_image,
		"bottom_image": product_doc.bottom_image,
		"measurement": product_doc.measurement,
		"top_measurement": product_doc.top_measurement,
		"bottom_measurement": product_doc.bottom_measurement,
		"tech_pack_no": product_doc.tech_pack_no + 1
	}
	new_doc = frappe.new_doc("Product Release")
	new_doc.update(d)
	new_doc.set('sizes', get_list_dict(product_doc, "sizes"))
	new_doc.set("product_fabric_composition_details", get_list_dict(product_doc, "product_fabric_composition_details"))
	new_doc.set("product_placement", get_list_dict(product_doc, "product_placement"))
	new_doc.set("trims", get_list_dict(product_doc, "trims"))
	new_doc.set("product_colours", get_list_dict(product_doc, "product_colours"))
	new_doc.set("product_set_colours", get_list_dict(product_doc, "product_set_colours"))
	new_doc.set("product_trim_combination", get_list_dict(product_doc, "product_trim_combination"))
	product_designs = get_list_dict(product_doc, "product_designs")
	new_doc.set("product_designs", product_designs)
	new_doc.set("product_measurement_descriptions", get_list_dict(product_doc, "product_measurement_descriptions"))
	new_doc.set("product_accessories", get_list_dict(product_doc, "product_accessories"))
	box_list = get_list_dict(product_doc, "product_box_details")
	new_doc.set("product_box_details", box_list)
	new_doc.save(ignore_permissions=True)
	for design in product_designs:
		duplicate_and_attach(design, new_doc.name)
	for box in box_list:
		duplicate_and_attach(box, new_doc.name)	
	product_doc.db_set("tech_pack_no", product_doc.tech_pack_no + 1)

@frappe.whitelist()
def duplicate_and_attach(row, new_docname):
	if isinstance(row, str):
		row = frappe.parse_json(row)

	original_file_id = row.get("file")
	if not original_file_id:
		frappe.throw("File docname is missing")
	original_file = frappe.get_doc("File", original_file_id)
	new_file = frappe.copy_doc(original_file)
	new_file.attached_to_doctype = "Product Release"       
	new_file.attached_to_name = new_docname 
	new_file.attached_to_field = "file"
	new_file.save(ignore_permissions=True)
	return {
		"new_file_name": new_file.name,
		"file_url": new_file.file_url
	}


def get_list_dict(doc, table_name):
    list_data = []
    table = getattr(doc, table_name)

    for row in table:
        list_data.append(row.as_dict())

    return list_data

@frappe.whitelist()
def process_pdf_to_images(file_url, docname, table_name):
    product = frappe.get_doc("Product", docname)
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    content = file_doc.get_content()
    doc = fitz.open(stream=content, filetype="pdf")
    folder = get_or_create_product_folder("Product", docname)
    zoom = 2 
    mat = fitz.Matrix(zoom, zoom)
    
    for page_number in range(len(doc)):
        page = doc[page_number]
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        filename = f"{docname}_page_{page_number + 1}.png"
        new_file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "folder": folder,
            "content": img_bytes,
            "is_private": file_doc.is_private,
            "attached_to_doctype": "Product",
            "attached_to_name": docname,
            "attached_to_field": table_name
        })
        new_file_doc.save(ignore_permissions=True)
        product.append(table_name, {
            "upload_name": f"Page {page_number + 1}",
            "graphic_image": new_file_doc.file_url,
            "filename": filename,
            "file": new_file_doc.name
        })
    
    product.save()
    return True

@frappe.whitelist()
def process_single_page_pdf(file_url, doctype, docname, fieldname):
	product = frappe.get_doc(doctype, docname)
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	doc = fitz.open(stream=content, filetype="pdf")

	if len(doc) != 1:
		frappe.throw("The PDF must contain exactly 1 page.")

	zoom = 2 
	mat = fitz.Matrix(zoom, zoom)
	page = doc[0]
	pix = page.get_pixmap(matrix=mat)
	img_bytes = pix.tobytes("png")

	old_files = frappe.get_all("File", filters={
		"attached_to_name": docname,
		"attached_to_doctype": doctype,
		"attached_to_field": fieldname
	}, pluck="name")
	for f in old_files:
		frappe.delete_doc("File", f)
	doctype_str = doctype.replace(" ", "_")
	filename = f"{doctype_str}_{docname}_{fieldname}.png"
	new_file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": filename,
		"content": img_bytes,
		"is_private": file_doc.is_private,
		"attached_to_doctype": doctype,
		"attached_to_name": docname,
		"attached_to_field": fieldname
	})
	new_file_doc.save(ignore_permissions=True)	
	product.db_set(fieldname, new_file_doc.file_url)
	frappe.delete_doc("File", file_doc.name)

	return True
