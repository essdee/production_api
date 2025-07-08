# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import nowdate, nowtime
from frappe.model.document import Document
from production_api.mrp_stock.utils import get_combine_datetime
from production_api.production_api.doctype.item.item import get_or_create_variant

class CutBundleMovementLedger(Document):
	def set_posting_datetime(self):
		if not self.posting_date:
			self.posting_date = nowdate()
		if not self.posting_time:
			self.posting_time = nowtime()
		posting_datetime = get_combine_datetime(self.posting_date, self.posting_time)
		self.posting_datetime = posting_datetime

	def update_item_variant(self):
		ipd = frappe.get_value("Lot", self.lot, "production_detail")
		if not ipd:
			return
		ipd_fields = ["stiching_in_stage", "primary_item_attribute", "packing_attribute", "stiching_attribute", "dependent_attribute"]
		stich_stage, primary_attr, pack_attr, stich_attr, dept_attr= frappe.get_value("Item Production Detail", ipd, ipd_fields)
		attrs = {
			dept_attr: stich_stage,
			primary_attr: self.size,
			pack_attr: self.colour,
			stich_attr: self.panel,
		}
		variant = get_or_create_variant(self.item, attrs)
		self.item_variant = variant

	def set_key(self):
		parts = [
			str(self.lot), str(self.supplier), str(self.lay_no), str(self.bundle_no),
			str(self.shade), str(self.item), str(self.size), str(self.colour), str(self.panel),
		]
		self.cbm_key = "-".join(parts)

def get_cut_bundle_entry(cpm_doc, doc, target_warehouse, multiplier, cancelled=0):
	x = frappe.json.loads(cpm_doc.cut_panel_movement_json)
	items = []
	supplier = target_warehouse
	item = frappe.get_value("Lot", cpm_doc.lot, "item")
	for colour in x['data'].keys():
		part = x['data'][colour]['part']
		panels = x['panels'][part] if part else x['panels']
		for row in x['data'][colour]['data']:
			for panel in panels:
				if row.get(panel) and row[panel+"_moved"]:
					items.append({
						"lot": cpm_doc.lot,
						"supplier": supplier,
						"lay_no": row['lay_no'],
						"bundle_no": row['bundle_no'],
						"panel": panel,
						"shade": row['shade'],
						"posting_date": doc.posting_date,
						"posting_time": doc.posting_time,
						"size": row['size'],
						"colour": row[panel+'_colour'],
						"quantity": row[panel] * multiplier,
						"item": item,
						"voucher_type": doc.doctype,
						"voucher_no": doc.name,
						"is_cancelled": cancelled,
						"set_combination": frappe.json.dumps(row['set_combination']),	
					})
	collapsed_details = None
	if x['collapsed_details']:
		collapsed_details = []

	return items, collapsed_details				

def make_cut_bundle_ledger(entries, collapsed_entries=[]):
	if len(entries) == 0:
		return
	if entries[0]['is_cancelled']:
		frappe.throw("Can't cancel the documents")
	else:	 
		for entry in entries:
			previous = get_previous_entry(entry)
			future = get_future_entry(entry)
			if future:
				frappe.throw("Change the date and time to complete Stock Movement")

			if previous:
				entry['quantity_after_transaction'] = entry['quantity'] + previous[0]['quantity_after_transaction']
			else:
				entry['quantity_after_transaction'] = entry['quantity']

			make_cut_bundle_entry(entry)

def make_cut_bundle_entry(entry):
	new_doc = frappe.new_doc("Cut Bundle Movement Ledger")
	new_doc.update(entry)
	new_doc.save()
	new_doc.set_posting_datetime()
	new_doc.set_key()
	new_doc.submit()

def get_future_entry(entry):
	posting_datetime = get_combine_datetime(entry['posting_date'], entry['posting_time'])
	key = get_cbm_key(entry)
	future = frappe.db.sql(
		"""
			SELECT name, quantity_after_transaction FROM `tabCut Bundle Movement Ledger`
			WHERE cbm_key = %(key)s AND posting_datetime > %(datetime)s AND is_cancelled = 0 AND is_collapsed = 0
			ORDER BY posting_datetime DESC
		""",{
			"key": key,
			"datetime": posting_datetime,
		}, as_dict=True 
	)
	return future if future else None

def get_previous_entry(entry):
	posting_datetime = get_combine_datetime(entry['posting_date'], entry['posting_time'])
	key = get_cbm_key(entry)
	previous = frappe.db.sql(
		"""
			SELECT name, quantity_after_transaction FROM `tabCut Bundle Movement Ledger`
			WHERE cbm_key = %(key)s AND posting_datetime <= %(datetime)s AND is_cancelled = 0 AND is_collapsed = 0 
			ORDER BY posting_datetime DESC LIMIT 1
		""", {
			"key": key,
			"datetime": posting_datetime,
		}, as_dict=True
	)
	return previous if previous else None

def get_cbm_key(entry):
	parts = [
		str(entry['lot']),
		str(entry['supplier']),
		str(entry['lay_no']),
		str(entry['bundle_no']),
		str(entry['shade']),
		str(entry['item']),
		str(entry['size']),
		str(entry['colour']),
		str(entry['panel']),
	]
	cbm_key = "-".join(parts)
	return cbm_key

def cancel_cut_bundle_ledger(entries):
	if len(entries) == 0:
		return
	if entries[0]['is_cancelled'] == 0:
		frappe.throw("Can't create the documents")
	else:
		for entry in entries:
			previous = get_previous_entry(entry)
			future = get_future_entry(entry)
			if previous and not future:
				frappe.db.sql(
					"""
						UPDATE `tabCut Bundle Movement Ledger` SET is_cancelled = 1 WHERE name = %(name)s
					""", {
						"name": previous[0]['name'],
					}
				)
			elif not previous and not future:
				frappe.throw("Cancel the GRN's against this Work Order to Cancel this Document")
			else:
				frappe.throw("Stock is Not Available")

def update_collapsed_bundle(doctype, docname, event):
	doc = frappe.get_doc(doctype, docname)
	from_location = doc.supplier
	new_bundles = {}
	ipd = frappe.get_value("Lot", doc.lot, "production_detail")
	if not ipd:
		return
	bundle_entries = frappe.db.sql(
		""" 
			SELECT name FROM `tabCut Bundle Movement Ledger` WHERE lot = %(lot)s 
		""", {
			"lot": doc.lot
		}, as_dict=True
	)
	if not bundle_entries:
		return
	ipd_fields = ["primary_item_attribute", "packing_attribute", "stiching_attribute", "stiching_in_stage"]
	primary_attr, pack_attr, stich_attr, stich_stage = frappe.get_value("Item Production Detail", ipd, ipd_fields)

	items = doc.grn_deliverables
	if doc.is_return:
		items = doc.items

	for row in items:
		item = frappe.get_value("Item Variant", row.item_variant, "item")
		dept_attr = frappe.get_value("Item", item, "dependent_attribute")
		if not dept_attr:
			continue
		if check_cut_stage_variant(row.item_variant, dept_attr, stich_stage):
			d = get_variant_attr_details(row.item_variant)
			if event == "on_submit":
				cb_future_entries = get_future_cbm_list(doc.posting_date, doc.posting_time, doc.supplier, row.item_variant, limit=False)
				cb_previous_entries = get_previous_cbm_list(doc.posting_date, doc.posting_time, doc.supplier, row.item_variant)
				if not cb_previous_entries and not cb_future_entries:
					row_panel = d[stich_attr]
					d[stich_attr] = "%"+d[stich_attr]+"%"

					cbm_list = get_latest_cbml_for_variant(from_location, doc.lot, d[primary_attr], d[pack_attr], d[stich_attr], item)
					for bundle in cbm_list:
						cbm_doc = frappe.get_doc("Cut Bundle Movement Ledger", bundle['name'])	
						panels = cbm_doc.panel.split(",")	
						for panel in panels:
							panel = panel.strip()
							key = [ str(cbm_doc.lot), str(cbm_doc.item), str(cbm_doc.size), str(cbm_doc.colour), str(panel)]		
							key = "|".join(key)
							if key not in new_bundles:
								new_bundles[key] = { "qty": 0, "bundle_qty": 0 }
							new_bundles[key]['bundle_qty'] += cbm_doc.quantity_after_transaction

					key = [ str(doc.lot), str(item), str(d[primary_attr]), str(d[pack_attr]), str(row_panel)]		
					key = "|".join(key)
					new_bundles[key]['qty'] += row.quantity
					if cbm_list:
						update_is_collapsed(from_location, doc.lot, d[primary_attr], d[pack_attr], d[stich_attr], item)
		
				elif cb_previous_entries and not cb_future_entries:
					create_inter_cbml_doc(cb_previous_entries[0]['name'], doctype, docname, row.quantity, -1, doc.posting_date, doc.posting_time)

				elif not cb_previous_entries and cb_future_entries:
					frappe.throw("Stock is not Available")	

				elif cb_previous_entries and cb_future_entries:
					if cb_future_entries[0]['quantity_after_transaction'] >= row.quantity:
						for entry in cb_future_entries:
							qty = entry['quantity_after_transaction'] - row.quantity
							update_future_entries_qty_after_transaction(entry['name'], qty)

						create_inter_cbml_doc(cb_previous_entries[0]['name'], doctype, docname, row.quantity, -1, doc.posting_date, doc.posting_time)	
					else:
						frappe.throw("Stock is not Available")	
			else:
				cb_future_entries = get_future_cbm_list(doc.posting_date, doc.posting_time, doc.supplier, row.item_variant, limit=False)
				cb_previous_entries = get_previous_cbm_list(doc.posting_date, doc.posting_time, doc.supplier, row.item_variant, limit=False)
				if cb_previous_entries and not cb_future_entries:
					if len(cb_previous_entries) == 1:
						update_is_collapsed(from_location, doc.lot, d[primary_attr], d[pack_attr], d[stich_attr], item, is_collapsed=0)
						update_is_cancelled_cbml(cb_previous_entries[0]['name'])
					else:
						update_is_cancelled_cbml(cb_previous_entries[0]['name'])
						
				elif cb_previous_entries and cb_future_entries:
					if len(cb_previous_entries) == 1:
						frappe.throw("Stock Not Available")
					else:
						update_is_cancelled_cbml(cb_previous_entries[0]['name'])
						previous_qty = row.quantity * -1
						for entry in cb_future_entries:
							qty = entry['quantity_after_transaction'] + previous_qty
							update_future_entries_qty_after_transaction(entry['name'], qty)

	for bundle_key in new_bundles.keys():
		bundle_total_qty = new_bundles[bundle_key]['bundle_qty']
		stock_moved_qty = new_bundles[bundle_key]['qty']
		create_new_collapsed_bundle(bundle_key, bundle_total_qty, stock_moved_qty, from_location, doc)

def create_new_collapsed_bundle(bundle_key, bundle_total_qty, stock_moved_qty, from_location, doc):
	lot, item, size, colour, panel = bundle_key.split("|")

	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	panel_qty_dict = {}
	for row in ipd_doc.stiching_item_details:
		panel_qty_dict[row.stiching_attribute_value] = row.quantity
	
	panel_qty = panel_qty_dict[panel]
	stock_moved_qty = stock_moved_qty / panel_qty
	bundle_qty = bundle_total_qty - stock_moved_qty

	lay_no = bundle_no = 0
	d = {
		"lot" : lot,
		"item" : item,
		"size" : size,
		"colour" : colour,
		"panel" : panel,
		"lay_no" : lay_no,
		"bundle_no" : bundle_no,
		"quantity" : bundle_qty * panel_qty_dict[panel],
		"supplier" : from_location,
		"posting_date": doc.posting_date,
		"posting_time": doc.posting_time,
		"voucher_type": doc.doctype,
		"voucher_no": doc.name,
		"collapsed_bundle": 1,
		"shade": "NA",
		"quantity_after_transaction": bundle_qty * panel_qty_dict[panel],
		"set_combination": frappe.json.dumps({}),
	}
	new_doc = frappe.new_doc("Cut Bundle Movement Ledger")
	new_doc.update(d)
	new_doc.save()
	new_doc.set_posting_datetime()
	new_doc.set_key()
	new_doc.update_item_variant()
	new_doc.submit()

def get_future_cbm_list(posting_date, posting_time, supplier, variant, limit=True):
	query = """
		SELECT name, quantity_after_transaction, quantity FROM `tabCut Bundle Movement Ledger` WHERE collapsed_bundle = 1 
		AND is_cancelled = 0 AND posting_datetime > %(datetime)s AND supplier = %(supplier)s AND item_variant = %(variant)s
		ORDER BY posting_datetime DESC
	"""	
	if limit:
		query += " LIMIT 1"

	datetime = get_combine_datetime(posting_date,posting_time)
	cbm_list = frappe.db.sql(query, {
		"datetime": datetime, 
		"supplier": supplier,
		"variant": variant
	}, as_dict=True)

	return cbm_list

def get_previous_cbm_list(posting_date, posting_time, supplier, variant, limit=True):
	query = """
		SELECT name, quantity_after_transaction, quantity FROM `tabCut Bundle Movement Ledger` WHERE collapsed_bundle = 1 
		AND is_cancelled = 0 AND posting_datetime <= %(datetime)s AND supplier = %(supplier)s AND item_variant = %(variant)s
		ORDER BY posting_datetime DESC
	"""
	if limit:
		query += " LIMIT 1"

	datetime = get_combine_datetime(posting_date,posting_time)
	cbm_list = frappe.db.sql(query, {
		"datetime": datetime, 
		"supplier": supplier,
		"variant": variant,
	}, as_dict=True)

	return cbm_list

def update_is_cancelled_cbml(docname):
	frappe.db.sql(
		"""
			UPDATE `tabCut Bundle Movement Ledger` SET is_cancelled = 1 WHERE name = %(docname)s
		""", {
			"docname": docname
		}
	)

def update_is_collapsed(from_location, lot, primary_val, pack_val, stich_val, item, is_collapsed=1):
	collapsed_val = 0
	if is_collapsed == 0:
		collapsed_val = 1
	frappe.db.sql(
		"""
			UPDATE `tabCut Bundle Movement Ledger` SET is_collapsed = %(collapsed)s WHERE size = %(size)s 
			AND colour = %(colour)s AND item = %(item)s AND lot = %(lot)s 
			AND panel like %(panel)s AND is_cancelled = 0 AND is_collapsed = %(collapsed_val)s
		""", {
			"lot": lot, 
			"size": primary_val, 
			"colour": pack_val, 
			"panel": "%"+stich_val+"%", 
			"item": item, 
			"collapsed": is_collapsed,
			"collapsed_val": collapsed_val,
		}
	)

def create_inter_cbml_doc(previous_docname, doctype, docname, quantity, multiplier, posting_date, posting_time):
	collapsed_doc = frappe.get_doc("Cut Bundle Movement Ledger", previous_docname)
	new_doc = frappe.new_doc("Cut Bundle Movement Ledger")
	new_doc.lot = collapsed_doc.lot
	new_doc.supplier = collapsed_doc.supplier 
	new_doc.supplier_name = collapsed_doc. supplier_name
	new_doc.lay_no = collapsed_doc.lay_no 
	new_doc.bundle_no = collapsed_doc.bundle_no
	new_doc.panel = collapsed_doc.panel 
	new_doc.shade = collapsed_doc.shade 
	new_doc.collapsed_bundle = 1 
	new_doc.item_variant = collapsed_doc.item_variant 
	new_doc.item = collapsed_doc.item 
	new_doc.voucher_type = doctype 
	new_doc.voucher_no = docname 
	new_doc.size = collapsed_doc.size 
	new_doc.colour = collapsed_doc.colour 
	new_doc.quantity = quantity * multiplier
	new_doc.quantity_after_transaction = collapsed_doc.quantity_after_transaction + (quantity * multiplier ) 
	new_doc.set_combination = collapsed_doc.set_combination
	new_doc.posting_date = posting_date
	new_doc.posting_time = posting_time
	new_doc.save()
	new_doc.set_posting_datetime()
	new_doc.set_key()
	new_doc.submit()

def update_future_entries_qty_after_transaction(docname, qty):
	frappe.db.sql(
		"""
			UPDATE `tabCut Bundle Movement Ledger` SET quantity_after_transaction = %(quantity)s 
			WHERE name = %(docname)s
		""", {
			"docname": docname,
			"quantity": qty,
		}
	)

def get_latest_cbml_for_variant(from_location,lot, primary_value, pack_value, stich_value, item):
	cbm_list = frappe.db.sql("""
		SELECT cbml.name FROM `tabCut Bundle Movement Ledger` cbml
			INNER JOIN (
				SELECT cbm_key, MAX(posting_datetime) AS max_posting_datetime, lay_no FROM `tabCut Bundle Movement Ledger`
				WHERE is_cancelled = 0 AND is_collapsed = 0 AND is_accessory = 0  AND supplier = %(from_location)s  
				AND lot = %(lot)s AND size = %(size)s AND colour = %(colour)s AND item = %(item)s AND panel like %(panel)s 
				GROUP BY cbm_key
			) latest_cbml
		ON cbml.cbm_key = latest_cbml.cbm_key AND cbml.posting_datetime = latest_cbml.max_posting_datetime
		ORDER BY latest_cbml.lay_no asc
	""", {
		"from_location": from_location, 
		"lot": lot, 
		"size": primary_value, 
		"colour": pack_value, 
		"panel": stich_value, 
		"item": item,
	}, as_dict=True)

	return cbm_list

def check_cut_stage_variant(variant, dependent_attribute, dependent_attribute_value):
	attr_details = frappe.db.sql(
		"""
			SELECT attribute, attribute_value FROM `tabItem Variant Attribute` WHERE parent = %(parent)s 
			AND attribute = %(dependent)s AND attribute_value = %(stich_stage)s
		""", {
			"parent": variant, 
			"dependent": dependent_attribute, 
			"stich_stage": dependent_attribute_value
		}, as_dict=True
	)
	if attr_details:
		return True
	return False

def get_variant_attr_details(variant):
	attr_details = frappe.db.sql(
		""" SELECT attribute, attribute_value FROM `tabItem Variant Attribute` WHERE parent = %(parent)s 
		""", {
			"parent": variant
		}, as_dict=True
	)
	d = {}
	for attr_detail in attr_details:
		d[attr_detail['attribute']] = attr_detail['attribute_value']
	return d