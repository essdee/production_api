# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import nowdate, nowtime
from frappe.model.document import Document
from production_api.utils import update_if_string_instance
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
		lot_hash = frappe.get_cached_value("Lot", self.lot, "lot_hash_value")
		item_hash = frappe.get_cached_value("Item", self.item, "item_hash_value")
		parts = [
			str(lot_hash), str(self.supplier), str(self.lay_no), str(self.bundle_no),
			str(self.shade), str(item_hash), str(self.size), str(self.colour), str(self.panel),
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
			
			if entry['quantity_after_transaction'] < 0:
				frappe.throw("Stock is not Avaliable in Source")
			
			make_cut_bundle_entry(entry)

def make_cut_bundle_entry(entry):
	entry['doctype'] = "Cut Bundle Movement Ledger"
	new_doc = frappe.get_doc(entry)
	new_doc.flags.ignore_permissions = 1
	new_doc.set_posting_datetime()
	new_doc.set_key()
	new_doc.submit()

def get_future_entry(entry, collapsed_bundle=0):
	posting_datetime = get_combine_datetime(entry['posting_date'], entry['posting_time'])
	key = get_cbm_key(entry)
	future = frappe.db.sql(
		"""
			SELECT name, quantity_after_transaction FROM `tabCut Bundle Movement Ledger`
			WHERE cbm_key = %(key)s AND posting_datetime > %(datetime)s AND is_cancelled = 0 AND is_collapsed = 0 
			AND collapsed_bundle = %(collapsed)s AND transformed = 0 ORDER BY posting_datetime DESC
		""",{
			"key": key,
			"datetime": posting_datetime,
			"collapsed": collapsed_bundle,
		}, as_dict=True 
	)
	return future if future else None

def get_previous_entry(entry, collapsed_bundle=0):
	posting_datetime = get_combine_datetime(entry['posting_date'], entry['posting_time'])
	key = get_cbm_key(entry)
	previous = frappe.db.sql(
		"""
			SELECT name, quantity_after_transaction FROM `tabCut Bundle Movement Ledger`
			WHERE cbm_key = %(key)s AND posting_datetime <= %(datetime)s AND is_cancelled = 0 AND is_collapsed = 0 
			AND collapsed_bundle = %(collapsed)s AND transformed = 0 ORDER BY posting_datetime DESC LIMIT 1
		""", {
			"key": key,
			"datetime": posting_datetime,
			"collapsed": collapsed_bundle,
		}, as_dict=True
	)
	return previous if previous else None

def get_cbm_key(entry):
	lot_hash = frappe.get_cached_value("Lot", entry['lot'], "lot_hash_value")
	item_hash = frappe.get_cached_value("Item", entry['item'], "item_hash_value")
	parts = [
		str(lot_hash),
		str(entry['supplier']),
		str(entry['lay_no']),
		str(entry['bundle_no']),
		str(entry['shade']),
		str(item_hash),
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
			else:
				frappe.throw("Stock is Not Available")

def update_collapsed_bundle(doctype, docname, event, non_stich_process=False):
	doc = frappe.get_doc(doctype, docname)
	from_location = doc.supplier
	if doctype == "Delivery Challan":
		from_location = doc.from_location

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
	ipd_fields = ["primary_item_attribute", "packing_attribute", "stiching_attribute", "stiching_in_stage", "dependent_attribute"]
	primary_attr, pack_attr, stich_attr, stich_stage, dependent = frappe.get_value("Item Production Detail", ipd, ipd_fields)
	attrs = {
		"primary": primary_attr,
		"pack": pack_attr,
		"stich": stich_attr,
		"stich_stage": stich_stage,
		"stage": dependent,
	}
	items = None
	if doctype == "Delivery Challan":
		items = doc.items
	elif non_stich_process:
		items = doc.items	
	else:	
		items = doc.grn_deliverables
		if doc.is_return:
			items = doc.items

	for row in items:
		item = frappe.get_value("Item Variant", row.item_variant, "item")
		dept_attr = frappe.get_value("Item", item, "dependent_attribute")
		if not dept_attr:
			continue
		if check_dependent_stage_variant(row.item_variant, dept_attr, stich_stage):
			quantity = 0
			if doctype == "Delivery Challan":
				quantity = row.delivered_quantity
			else:
				quantity = row.quantity
			if quantity > 0:
				d = get_variant_attr_details(row.item_variant)
				if event == "on_submit":
					new_bundles = on_submit_collapsed_bundles(doc, doctype, docname, from_location, row.item_variant, row.set_combination, d, attrs, item, quantity, new_bundles)
				else:
					cancel_collapse_bundles(doc, row.item_variant, row.set_combination, quantity, from_location, d, attrs, item)
	
	if doctype ==  "Delivery Challan" and new_bundles:
		for key in new_bundles:
			key['qty'] = key['qty'] * -1

	to_new_bundles = {}
	to_location = None
	if doctype == "Delivery Challan":
		to_location = doc.supplier
		if doc.is_internal_unit and doc.from_location != doc.supplier:
			to_location = frappe.db.get_single_value("Stock Settings", "transit_warehouse")
		for row in items:
			item = frappe.get_value("Item Variant", row.item_variant, "item")
			dept_attr = frappe.get_value("Item", item, "dependent_attribute")
			if not dept_attr:
				continue

			if check_dependent_stage_variant(row.item_variant, dept_attr, stich_stage):
				quantity = row.delivered_quantity
				if quantity > 0:
					d = get_variant_attr_details(row.item_variant)
					if event == "on_submit":
						to_new_bundles = on_submit_collapsed_bundles(doc, doctype, docname, to_location, row.item_variant, row.set_combination, d, attrs, item, quantity, to_new_bundles, add=True)
					else:
						cancel_collapse_bundles(doc, row.item_variant, row.set_combination, quantity, to_location, d, attrs, item)

	if non_stich_process:
		to_location = doc.delivery_location
		for row in items:
			quantity = row.qty
			if quantity > 0:
				item = frappe.get_value("Item Variant", row.item_variant, "item")
				dept_attr = frappe.get_value("Item", item, "dependent_attribute")
				if not dept_attr:
					continue

				if check_dependent_stage_variant(row.item_variant, dept_attr, stich_stage):
					d = get_variant_attr_details(row.item_variant)
					if event == "on_submit":
						to_new_bundles = on_submit_collapsed_bundles(doc, doctype, docname, to_location, row.item_variant, row.set_combination, d, attrs, item, quantity, to_new_bundles, add=True)
					else:
						cancel_collapse_bundles(doc, row.item_variant, row.set_combination, quantity, to_location, d, attrs, item)

	for bundle_key in new_bundles.keys():
		bundle_total_qty = new_bundles[bundle_key]['bundle_qty']
		stock_moved_qty = new_bundles[bundle_key]['qty']
		create_new_collapsed_bundle(bundle_key, bundle_total_qty, stock_moved_qty, from_location, doc, d, attrs)

	if doctype == "Delivery Challan":
		for bundle_key in to_new_bundles.keys():
			bundle_total_qty = to_new_bundles[bundle_key]['bundle_qty']
			stock_moved_qty = to_new_bundles[bundle_key]['qty']
			create_new_collapsed_bundle(bundle_key, bundle_total_qty, stock_moved_qty, to_location, doc)	

def on_submit_collapsed_bundles(doc, doctype, docname, location, item_variant, set_combination, d, attrs, item, quantity, bundles_dict, add=False):
	cb_previous_entries = get_collapsed_previous_cbm_list(doc.posting_date, doc.posting_time, location, item_variant)
	cb_future_entries = get_collapsed_future_cbm_list(doc.posting_date, doc.posting_time, location, item_variant, limit=False)
	if not cb_previous_entries and not cb_future_entries:
		row_panel = d[attrs['stich']]
		d[attrs['stich']] = "%"+d[attrs['stich']]+"%"
		row_set_comb = update_if_string_instance(set_combination)
		tuple_key = sorted(row_set_comb.items())
		row_set_str = frappe.json.dumps(tuple_key)	
		cbm_list = get_latest_cbml_for_variant(location, doc.lot, d[attrs['primary']], d[attrs['pack']], d[attrs['stich']], item)
		for bundle in cbm_list:
			cbm_doc = frappe.get_doc("Cut Bundle Movement Ledger", bundle['name'])	
			panels = cbm_doc.panel.split(",")	
			cbm_set_comb = update_if_string_instance(cbm_doc.set_combination)
			set_comb = {
				"major_colour": cbm_set_comb['major_colour']
			}
			if cbm_set_comb.get("major_part"):
				set_comb["major_part"] = cbm_set_comb['major_part']
			if set_comb != row_set_comb:
				continue
			tuple_key = sorted(set_comb.items())
			set_comb_str = frappe.json.dumps(tuple_key)
			for panel in panels:
				panel = panel.strip()
				key = [ str(cbm_doc.lot), str(cbm_doc.item), str(cbm_doc.size), str(cbm_doc.colour), str(panel), set_comb_str]		
				key = "|".join(key)
				if key not in bundles_dict:
					bundles_dict[key] = { "qty": 0, "bundle_qty": 0 }
				bundles_dict[key]['bundle_qty'] += cbm_doc.quantity_after_transaction
			
			frappe.db.sql(
				"""
					UPDATE `tabCut Bundle Movement Ledger` SET is_collapsed = 1 WHERE name = %(cbm_docname)s
				""", {
					"cbm_docname": bundle['name']
				}
			)
		bundles_key = [ str(doc.lot), str(item), str(d[attrs['primary']]), str(d[attrs['pack']]), str(row_panel), row_set_str]		
		key = "|".join(bundles_key)
		if key not in bundles_dict:
			bundles_dict[key] = { "qty": 0, "bundle_qty": 0 }
		bundles_dict[key]['qty'] += quantity

	elif cb_previous_entries and not cb_future_entries:
		x = -1
		if add:
			x = 1
		create_inter_cbml_doc(cb_previous_entries[0]['name'], doctype, docname, quantity, x, doc.posting_date, doc.posting_time)

	elif not cb_previous_entries and cb_future_entries:
		frappe.throw("Change the Date and Time for Panel Movement")	

	elif cb_previous_entries and cb_future_entries:
		if cb_future_entries[0]['quantity_after_transaction'] >= quantity:
			for entry in cb_future_entries:
				qty = entry['quantity_after_transaction'] - quantity
				if add:
					qty = entry['quantity_after_transaction'] + quantity
				update_future_entries_qty_after_transaction(entry['name'], qty)
			x = -1
			if add:
				x = 1
			create_inter_cbml_doc(cb_previous_entries[0]['name'], doctype, docname, quantity, x, doc.posting_date, doc.posting_time)	
		else:
			frappe.throw("Stock is not Available")	

	return bundles_dict		

def cancel_collapse_bundles(doc, item_variant, set_combination, quantity, location, d, attrs, item):
	cb_previous_entries = get_collapsed_previous_cbm_list(doc.posting_date, doc.posting_time, location, item_variant, limit=False)
	cb_future_entries = get_collapsed_future_cbm_list(doc.posting_date, doc.posting_time, location, item_variant, limit=False)
	if cb_previous_entries and not cb_future_entries:
		if len(cb_previous_entries) == 1:
			update_uncollapsed(location, set_combination, doc.lot, d[attrs['primary']], d[attrs['pack']], d[attrs['stich']], item)
			update_is_cancelled_cbml(cb_previous_entries[0]['name'])
		else:
			update_is_cancelled_cbml(cb_previous_entries[0]['name'])
			
	elif cb_previous_entries and cb_future_entries:
		if len(cb_previous_entries) == 1:
			frappe.throw("Stock Not Available")
		else:
			update_is_cancelled_cbml(cb_previous_entries[0]['name'])
			previous_qty = quantity * -1
			for entry in cb_future_entries:
				qty = entry['quantity_after_transaction'] + previous_qty
				update_future_entries_qty_after_transaction(entry['name'], qty)	

def create_new_collapsed_bundle(bundle_key, bundle_total_qty, stock_moved_qty, from_location, doc, d, attrs):
	from production_api.utils import get_tuple_attributes
	lot, item, size, colour, panel, set_combination = bundle_key.split("|")
	set_combination = frappe.json.loads(set_combination)
	ipd = frappe.get_value("Lot", lot, "production_detail")
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	panel_qty_dict = {}
	for row in ipd_doc.stiching_item_details:
		panel_qty_dict[row.stiching_attribute_value] = row.quantity
	
	panel_qty = panel_qty_dict[panel]
	stock_moved_qty = stock_moved_qty / panel_qty
	bundle_qty = 0
	if doc.doctype == "Delivery Challan":
		bundle_qty = bundle_total_qty + stock_moved_qty
	else:	
		bundle_qty = bundle_total_qty - stock_moved_qty

	if bundle_qty < 0:
		frappe.throw("Stock is not Available")

	lay_no = bundle_no = 0
	variant = get_or_create_variant(item, {
		attrs['primary']: size,
		attrs['pack']: colour,
		attrs['stich']: panel,
		attrs['stage']: attrs['stich_stage'],
	})
	set_combination = get_tuple_attributes(set_combination)
	d = {
		"lot" : lot,
		"item" : item,
		"item_variant": variant,
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
		"set_combination": frappe.json.dumps(set_combination),
	}
	d['doctype'] = "Cut Bundle Movement Ledger"
	new_doc = frappe.get_doc(d)
	new_doc.flags.ignore_permissions = 1
	new_doc.set_posting_datetime()
	new_doc.set_key()
	new_doc.submit()

def get_collapsed_future_cbm_list(posting_date, posting_time, supplier, variant, limit=True):
	query = """
		SELECT name, quantity_after_transaction, set_combination, quantity FROM `tabCut Bundle Movement Ledger` 
		WHERE collapsed_bundle = 1 AND is_cancelled = 0 AND transformed = 0 AND posting_datetime > %(datetime)s 
		AND supplier = %(supplier)s AND item_variant = %(variant)s
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

def get_collapsed_previous_cbm_list(posting_date, posting_time, supplier, variant, limit=True):
	query = """
		SELECT name, quantity_after_transaction, quantity, set_combination FROM `tabCut Bundle Movement Ledger` 
		WHERE collapsed_bundle = 1 AND is_cancelled = 0 AND transformed = 0 AND posting_datetime <= %(datetime)s 
		AND supplier = %(supplier)s AND item_variant = %(variant)s
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

def update_uncollapsed(from_location, set_combination, lot, primary_val, pack_val, stich_val, item):
	row_set_comb = update_if_string_instance(set_combination)
	cbm_list = frappe.db.sql(
		"""
			SELECT name, set_combination FROM `tabCut Bundle Movement Ledger` WHERE size = %(size)s AND supplier = %(supplier)s
			AND colour = %(colour)s AND item = %(item)s AND lot = %(lot)s AND transformed = 0 
			AND panel like %(panel)s AND is_cancelled = 0 AND is_collapsed = 1
		""", {
			"supplier": from_location,
			"lot": lot, 
			"size": primary_val, 
			"colour": pack_val, 
			"panel": "%"+stich_val+"%", 
			"item": item, 
		}, as_dict=True
	)
	for bundle in cbm_list:
		cbm_doc = frappe.get_doc("Cut Bundle Movement Ledger", bundle['name'])	
		cbm_set_comb = update_if_string_instance(cbm_doc.set_combination)
		set_comb = {
			"major_colour": cbm_set_comb['major_colour']
		}
		if cbm_set_comb.get("major_part"):
			set_comb["major_part"] = cbm_set_comb['major_part']
		if set_comb == row_set_comb:
			frappe.db.sql(
				"""
					UPDATE `tabCut Bundle Movement Ledger` SET is_collapsed = 0 WHERE name = %(cbml_name)s
				""", {
					"cbml_name": bundle['name']
				}
			)

def create_inter_cbml_doc(previous_docname, doctype, docname, quantity, multiplier, posting_date, posting_time):
	collapsed_doc = frappe.get_doc("Cut Bundle Movement Ledger", previous_docname)
	d = {
		"lot": collapsed_doc.lot,
		"supplier": collapsed_doc.supplier, 
		"supplier_name": collapsed_doc. supplier_name,
		"lay_no": collapsed_doc.lay_no, 
		"bundle_no": collapsed_doc.bundle_no,
		"panel": collapsed_doc.panel, 
		"shade": collapsed_doc.shade, 
		"collapsed_bundle": 1, 
		"item_variant": collapsed_doc.item_variant, 
		"item": collapsed_doc.item, 
		"voucher_type": doctype, 
		"voucher_no": docname, 
		"size": collapsed_doc.size, 
		"colour": collapsed_doc.colour, 
		"quantity": quantity * multiplier,
		"quantity_after_transaction": collapsed_doc.quantity_after_transaction + (quantity * multiplier), 
		"set_combination": collapsed_doc.set_combination,
		"posting_date": posting_date,
		"posting_time": posting_time,
	}
	d['doctype'] = "Cut Bundle Movement Ledger"
	new_doc = frappe.get_doc(d)
	new_doc.flags.ignore_permissions = 1
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
				WHERE is_cancelled = 0 AND is_collapsed = 0 AND transformed = 0 AND collapsed_bundle = 0 
				AND supplier = %(from_location)s AND lot = %(lot)s AND size = %(size)s AND colour = %(colour)s 
				AND item = %(item)s AND panel like %(panel)s GROUP BY cbm_key
			) latest_cbml
		ON cbml.cbm_key = latest_cbml.cbm_key AND cbml.posting_datetime = latest_cbml.max_posting_datetime 
		AND cbml.is_cancelled = 0 AND cbml.is_collapsed = 0 AND cbml.transformed = 0 AND cbml.collapsed_bundle = 0 
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

def check_dependent_stage_variant(variant, dependent_attribute, dependent_attribute_value):
	attr_details = frappe.db.sql(
		"""
			SELECT attribute, attribute_value FROM `tabItem Variant Attribute` WHERE parent = %(parent)s 
			AND attribute = %(dependent)s AND attribute_value = %(stage_value)s
		""", {
			"parent": variant, 
			"dependent": dependent_attribute, 
			"stage_value": dependent_attribute_value
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