# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from production_api.utils import update_if_string_instance
from production_api.mrp_stock.utils import get_combine_datetime

class CutBundleEdit(Document):
	def onload(self):
		onload_data = {
			"json_data": {},
			"inputs": [],
			"outputs": []
		}
		if self.cut_panel_movement_json:
			onload_data['json_data'] = frappe.json.loads(self.cut_panel_movement_json)
		if self.input_json:	
			onload_data['inputs'] = frappe.json.loads(self.input_json)
		if self.output_json:
			onload_data['outputs'] = frappe.json.loads(self.output_json)

		if onload_data:
			self.set_onload("movement_json", onload_data)

	def before_validate(self):
		if self.get('movement_data'):
			self.cut_panel_movement_json = frappe.json.dumps(self.movement_data.get("bundles"))
			self.input_json = frappe.json.dumps(self.movement_data.get("inputs"))
			self.output_json = frappe.json.dumps(self.movement_data.get("outputs"))
			self.colour = self.movement_data.get("selected_colour")

	def before_submit(self):
		if not self.input_json:
			frappe.throw("There is no Input Bundles")
		if not self.output_json:
			frappe.throw("There is no output Bundles")

		input_qty = self.get_json_panel_qty(self.input_json)
		output_qty = self.get_json_panel_qty(self.output_json)
		if(len(input_qty) != len(output_qty)):
			frappe.throw("Quantity Mismatch Between Input and Output")

		for key in input_qty:
			if key not in output_qty:
				frappe.throw("Combination Mismatch Between Input and Output")
			if input_qty[key] != output_qty[key]:
				frappe.throw("Quantity Mismatch Between Input and Output")

	def before_cancel(self):
		self.ignore_linked_doctypes = ("Cut Bundle Movement Ledger",)
		posting_datetime = get_combine_datetime(self.posting_date, self.posting_time)
		output_json = frappe.json.loads(self.output_json)
		for row in output_json:
			parts = [
				str(self.lot),
				str(self.warehouse),
				str(row['lay_no']),
				str(row['bundle_no']),
				str(row['shade']),
				str(self.item),
				str(row['size']),
				str(row['colour']),
				str(row['panel']),
			]
			key = "-".join(parts)
			future = frappe.db.sql(
				"""
					SELECT name, quantity_after_transaction FROM `tabCut Bundle Movement Ledger`
					WHERE cbm_key = %(key)s AND posting_datetime > %(datetime)s AND is_cancelled = 0 AND is_collapsed = 0 
					AND transformed = 0 ORDER BY posting_datetime DESC
				""",{
					"key": key,
					"datetime": posting_datetime,
				}, as_dict=True 
			)
			if future:
				frappe.throw("Stock was moved")

	def on_cancel(self):
		input_json = frappe.json.loads(self.input_json)
		for row in input_json:
			d = {
				"modified": frappe.utils.now(),
				"user": frappe.session.user,
				"docname": self.name,
				"lot": self.lot,
				"lay_no": row['lay_no'],
				"bundle": row['bundle_no'],
				"size": row['size'],
				"shade": row['shade'],
				"item": self.item,
				"panel": row['panel'],
				"colour": row['colour'],
			}
			if row['is_collapsed']:
				frappe.db.sql(
					"""
						UPDATE `tabCut Bundle Movement Ledger` SET transformed = 0, modified = %(modified)s, 
						modified_by = %(user)s WHERE lot = %(lot)s AND is_cancelled = 0 AND is_collapsed = 0 
						AND collapsed_bundle = 1 AND lay_no = %(lay_no)s AND bundle_no = %(bundle)s AND size = %(size)s 
						AND colour = %(colour)s AND panel = %(panel)s AND shade = %(shade)s AND item = %(item)s 
					""", d
				)
			else:	
				frappe.db.sql(
					"""
						UPDATE `tabCut Bundle Movement Ledger` SET transformed = 0, modified = %(modified)s, 
						modified_by = %(user)s WHERE lot = %(lot)s AND is_cancelled = 0 AND is_collapsed = 0 
						AND collapsed_bundle = 0 AND lay_no = %(lay_no)s AND bundle_no = %(bundle)s AND size = %(size)s 
						AND colour = %(colour)s AND panel = %(panel)s AND shade = %(shade)s AND item = %(item)s
					""", d
				)

		frappe.db.sql(
			"""
				UPDATE `tabCut Bundle Movement Ledger` SET is_cancelled = 1 ,modified = %(modified)s, 
				modified_by = %(user)s WHERE transformed_from = %(docname)s
			""", {
				"modified": frappe.utils.now(),
				"user": frappe.session.user,
				"docname": self.name,
			}
		)	

	def on_submit(self):
		input_json = frappe.json.loads(self.input_json)
		for row in input_json:
			d = {
				"modified": frappe.utils.now(),
				"user": frappe.session.user,
				"docname": self.name,
				"lot": self.lot,
				"lay_no": row['lay_no'],
				"bundle": row['bundle_no'],
				"size": row['size'],
				"shade": row['shade'],
				"item": self.item,
				"panel": row['panel'],
				"colour": row['colour'],
			}
			if row['is_collapsed']:
				frappe.db.sql(
					"""
						UPDATE `tabCut Bundle Movement Ledger` SET transformed = 1, modified = %(modified)s, 
						modified_by = %(user)s WHERE lot = %(lot)s AND is_cancelled = 0 
						AND collapsed_bundle = 1 AND lay_no = %(lay_no)s AND bundle_no = %(bundle)s 
						AND size = %(size)s AND colour = %(colour)s AND panel = %(panel)s
						AND shade = %(shade)s AND item = %(item)s
					""", d 
				)
			else:
				frappe.db.sql(
					"""
						UPDATE `tabCut Bundle Movement Ledger` SET transformed = 1, modified = %(modified)s, 
						modified_by = %(user)s WHERE lot = %(lot)s AND is_cancelled = 0 
						AND is_collapsed = 0 AND collapsed_bundle = 0 AND lay_no = %(lay_no)s AND bundle_no = %(bundle)s 
						AND size = %(size)s AND colour = %(colour)s AND panel = %(panel)s
						AND shade = %(shade)s AND item = %(item)s
					""", d 
				)
		self.create_new_bundles(self.output_json)

	def create_new_bundles(self, output_json):
		output_json = frappe.json.loads(output_json)
		for row in output_json:
			self.create_new_bundle(row)

	def create_new_bundle(self, row):
		d = {
			"lot" : self.lot,
			"item" : self.item,
			"size" : row['size'],
			"colour" : row['colour'],
			"panel" : row['panel'],
			"lay_no" : row['lay_no'],
			"bundle_no" : row['bundle_no'],
			"quantity" : row['qty'],
			"supplier" : self.warehouse,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"shade": row['shade'],
			"quantity_after_transaction": row['qty'],
			"set_combination": frappe.json.dumps(row['set_combination']),
			"transformed_from": self.name,
		}
		new_doc = frappe.new_doc("Cut Bundle Movement Ledger")
		new_doc.update(d)
		new_doc.save()
		new_doc.set_posting_datetime()
		new_doc.set_key()
		new_doc.submit()

	def get_json_panel_qty(self, json_value):
		json_value = frappe.json.loads(json_value)
		d = {}
		for row in json_value:
			panels = row['panel'].split(",")
			for panel in panels:
				key = (row['size'], row['colour'], panel)
				d.setdefault(key, 0)
				d[key] += row['qty']
		return d

@frappe.whitelist()
def get_major_colours(posting_date, posting_time, from_location, lot):
	posting_datetime = get_combine_datetime(posting_date, posting_time)
	cb_list = frappe.db.sql("""
		SELECT cbml.name FROM `tabCut Bundle Movement Ledger` cbml
			INNER JOIN (
				SELECT cbm_key, MAX(posting_datetime) AS max_posting_datetime, lay_no FROM `tabCut Bundle Movement Ledger`
				WHERE posting_datetime <= %(datetime_value)s AND is_cancelled = 0 AND supplier = %(from_location)s 
				AND lot = %(lot)s AND transformed = 0 GROUP BY cbm_key
			) latest_cbml
		ON cbml.cbm_key = latest_cbml.cbm_key AND cbml.posting_datetime = latest_cbml.max_posting_datetime
		WHERE cbml.posting_datetime <= %(datetime_value)s ORDER BY latest_cbml.lay_no asc
	""", {
		"datetime_value": posting_datetime,
		"from_location": from_location,
		"lot": lot,
	}, as_dict=True)

	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	panels = []
	for row in ipd_doc.stiching_item_details:
		panels.append(row.stiching_attribute_value)

	sizes = []
	colours = []
	for cb in cb_list:
		cb_doc = frappe.get_doc("Cut Bundle Movement Ledger", cb['name'])
		if cb_doc.size not in sizes:
			sizes.append(cb_doc.size)

		set_combination = update_if_string_instance(cb_doc.set_combination)
		if not set_combination:
			continue

		major_colour = set_combination['major_colour']
		parts = cb_doc.panel
		if parts not in panels:
			panels.append(parts)
		if ipd_doc.is_set_item:
			if set_combination.get('set_part'):
				major_colour = "("+ major_colour +")" + set_combination["set_colour"] +"-"+set_combination.get('set_part')
			else:
				major_colour = major_colour +"-"+set_combination.get('major_part')

		if major_colour not in colours:
			colours.append(major_colour)

	return {
		"colours": colours,
		"panels": panels,
		"sizes": sizes,
	}		

@frappe.whitelist()
def get_major_set_colours(colour, panel, lot):
	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	d = {
		"is_set_item": ipd_doc.is_set_item,
		"is_same_packing_attribute": ipd_doc.is_same_packing_attribute,
		'major_panel' : ipd_doc.stiching_major_attribute_value
	}

	if ipd_doc.is_set_item:
		d['major_part'] = ipd_doc.major_attribute_value
		panel = panel.split(",")
		panel = panel[0].strip()
		part = None
		default_panel = None 
		for row in ipd_doc.stiching_item_details:
			if row.stiching_attribute_value == panel:
				part = row.set_item_attribute_value
				break
		for row in ipd_doc.stiching_item_details:
			if row.set_item_attribute_value == part and row.is_default:
				default_panel = row.stiching_attribute_value
				break

		if part == ipd_doc.major_attribute_value:
			if ipd_doc.is_same_packing_attribute:
				d['major_colour'] = colour
			else:
				d['major_colour'] = colour
		else:
			d['set_part'] = part
			d['set_panel'] = default_panel
			if ipd_doc.is_same_packing_attribute:
				d['set_colour'] = colour
			else:
				d['set_colour'] = None
	else:
		if ipd_doc.is_same_packing_attribute:
			d['major_colour'] = colour
		else:
			d['major_colour'] = None

	return d		