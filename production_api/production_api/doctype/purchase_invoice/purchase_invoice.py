# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt
import frappe, json
import urllib.parse
from six import string_types
from itertools import groupby
from frappe.model.document import Document
from frappe.utils.data import money_in_words
from production_api.production_api.doctype.item.item import get_or_create_variant
from production_api.utils import update_if_string_instance, get_variant_attr_details
from production_api.production_api.doctype.mrp_settings.mrp_settings import get_purchase_invoice_series, post_erp_request

class PurchaseInvoice(Document):
	def onload(self):
		if self.against == 'Work Order' and len(self.pi_work_order_billed_details) > 0:
			items = fetch_work_order_items(self.pi_work_order_billed_details)
			self.set_onload("item_details", items)

	def validate(self):
		self.validate_grn()
		self.calculate_total()

	def validate_grn(self):
		# if not len(self.grn):
		# 	frappe.throw("Please set atleast one GRN")
		grns = [g.grn for g in self.grn]
		old_grns = []
		if not self.is_new():
			old = frappe.get_doc("Purchase Invoice", self.name)
			old_grns = [g.grn for g in old.grn]
			removed = [g for g in old_grns if g not in grns]
			added = [g for g in grns if g not in old_grns]
			for g in removed:
				grn = frappe.get_doc("Goods Received Note", g)
				grn.purchase_invoice_name = None
				grn.save(ignore_permissions=True)
			for g in added:
				grn = frappe.get_doc("Goods Received Note", g)
				grn.purchase_invoice_name = self.name
				grn.save(ignore_permissions=True)
	
	def calculate_total(self):
		total_amount = 0
		total_tax = 0
		grand_total = 0
		total_quantity = 0
		for item in self.items:
			# Item Total
			item_total = item.rate * item.qty
			total_amount += item_total
			# Item Tax after discount
			tax = (item_total * (float(item.tax or 0) / 100))
			total_tax += tax
			# Item Total after tax
			total = item_total + tax
			grand_total += total
			total_quantity += item.qty

		if grand_total > self.grn_grand_total:
			frappe.throw("Total amount is greater than GRN total amount")	

		if self.against == 'Work Order' and total_quantity != self.total_quantity and not self.is_new():
			frappe.throw("Not Allowed to Change Quantity")

		self.set('total', total_amount)
		self.set('total_tax', total_tax)
		self.set('grand_total', grand_total)
		self.set('in_words', money_in_words(grand_total))
	
	def after_insert(self):
		if self.vendor_bill_tracking:
			self.set_vendor_bill_purchase_invoice()
		grns = [g.grn for g in self.grn]
		for g in grns:
			grn = frappe.get_doc("Goods Received Note", g)
			grn.purchase_invoice_name = self.name
			grn.save(ignore_permissions=True)
	
	def set_vendor_bill_purchase_invoice(self):
		doc = frappe.get_doc("Vendor Bill Tracking", self.vendor_bill_tracking)
		doc.mrp_purchase_invoice = self.name
		doc.save(ignore_permissions = True)

	def remove_vendor_bill_purchase_invoce(self):
		frappe.db.set_value("Vendor Bill Tracking", self.vendor_bill_tracking, 'mrp_purchase_invoice', None, update_modified=False)
	
	def before_cancel(self):
		self.ignore_linked_doctypes = ("Vendor Bill Tracking")
		grns = [g.grn for g in self.grn]
		for g in grns:
			grn = frappe.get_doc("Goods Received Note", g)
			grn.purchase_invoice_name = None
			grn.save(ignore_permissions=True)
		if not self.cancel_without_cancelling_erp_inv:
			self.erp_inv_docstatus = 2
			res = post_erp_request("/api/method/essdee.essdee.utils.mrp.purchase_invoice.cancel", {"name": self.erp_inv_name})
			if res.status_code == 200:
				pass
			else:
				data = res.json()
				error = frappe.log_error("Purchase Inv Cancel Error", json.dumps(data), self.doctype, self.name)
				frappe.throw(data.get('exception') or f"Unknown Error - {frappe.get_desk_link(error.doctype, error.name)}")
		if self.vendor_bill_tracking:
			self.remove_vendor_bill_purchase_invoce()
		update_wo_billed_qty(self, docstatus=2)	
	
	def before_submit(self):
		if not len(self.grn) or not len(self.items):
			frappe.throw("Please set at least 1 grn and item row.")
		
		if self.against == 'Work Order' and not self.approved_by:
			frappe.throw("Invoice is not Approved")

		data = self.as_dict(convert_dates_to_str=True)
		mapped_series = get_purchase_invoice_series(data['naming_series'])
		if mapped_series:
			data['mapped_series'] = mapped_series
		p = "/api/method/essdee.essdee.utils.mrp.purchase_invoice.create"
		res = post_erp_request(p, {'data': data})
		if res.status_code == 200:
			data = res.json()['message']
			self.update({
				'erp_inv_name': data['name'],
				'erp_inv_docstatus': data['docstatus'],
				'final_amount': data['amount'],
				'due_date': data['due_date']
			})
		else:
			data = res.json()
			error = frappe.log_error("Purchase Inv Submit Error", json.dumps(data), self.doctype, self.name)
			frappe.throw(res.json().get('exception') or f"Unknown Error - {frappe.get_desk_link(error.doctype, error.name)}")
		
		if self.against == 'Work Order':
			update_wo_billed_qty(self)

def update_wo_billed_qty(self, docstatus=1):
	wo_doc_dict = {}
	for row in self.pi_work_order_billed_details:
		if not wo_doc_dict.get(row.work_order):
			wo_doc_dict[row.work_order] = frappe.get_doc("Work Order", row.work_order)

		wo_doc = wo_doc_dict[row.work_order]
		for wo_item in wo_doc.work_order_calculated_items:
			if wo_item.item_variant ==  row.item_variant:
				set1 = update_if_string_instance(row.set_combination)	
				set2 = update_if_string_instance(wo_item.set_combination)
				if set1 == set2:
					if docstatus == 2:
						wo_item.billed_qty -= row.quantity
					else:
						wo_item.billed_qty += row.quantity

	for wo in wo_doc_dict:
		wo.save(ignore_permissions=True)

@frappe.whitelist()
def submit_erp_invoice(name):
	inv = frappe.get_doc("Purchase Invoice", name)
	if inv.docstatus == 0:
		frappe.throw("Document not submitted")
	elif inv.docstatus == 2:
		frappe.throw("Document already cancelled")
	
	if inv.erp_inv_docstatus != 0:
		frappe.throw(f"ERP Invoice {inv.erp_inv_name} already submitted")
	
	res = post_erp_request("/api/method/essdee.essdee.utils.mrp.purchase_invoice.submit", {"name": inv.erp_inv_name})
	if res.status_code == 200:
		data = res.json()['message']
		inv.update({
			'erp_inv_name': data['name'],
			'erp_inv_docstatus': data['docstatus'],
			'final_amount': data['amount'],
			'due_date': data['due_date']
		})
		inv.save()
	else:
		data = res.json()
		error = frappe.log_error("Purchase Inv Submit Error", json.dumps(data), inv.doctype, inv.name)
		frappe.throw(res.json().get('exception') or f"Unknown Error - {frappe.get_desk_link(error.doctype, error.name)}")

	if inv.against == 'Work Order':
		update_wo_billed_qty(inv)

def get_item_variant_item_group(item_variant):
	item_group = frappe.db.sql("""SELECT t2.item_group, t1.item FROM `tabItem Variant` t1
			   		JOIN `tabItem` t2 on t2.name = t1.item where t1.name=%(item_variant)s
			   """, {
				   "item_variant" : item_variant
			   }, as_dict=True)
	if not item_group:
		return None, None
	return item_group[0]['item_group'], item_group[0]['item']
	
def fetch_work_order_items(items):
	items = [item.as_dict() for item in items]
	item_details = []
	for key, wo_items in groupby(items, lambda i: i['work_order']):
		wo_items = list(wo_items)
		work_order = wo_items[0]['work_order']
		bill_data = frappe.db.sql(
			"""
				SELECT parent as pi_name FROM `tabPI Work Order Billed Detail` 
				WHERE work_order = %(wo)s AND docstatus = 1 
				GROUP BY parent, work_order
			""", {
				"wo": work_order
			}, as_dict=True
		)
		lot = frappe.get_value("Work Order", work_order, "lot")
		ipd = frappe.get_value("Lot", lot, "production_detail")
		ipd_fields = ['is_set_item', 'primary_item_attribute', 'packing_attribute', 'set_item_attribute']
		is_set_item, primary, pack_attr, set_attr = frappe.get_value("Item Production Detail", ipd, ipd_fields)
		data = {
			"work_order": work_order,
			"sizes": [],
			"colours": {},
			"total_qty": {},
			"is_set_item": is_set_item,
			"primary_attribute": primary,
			"set_attr": set_attr,
			"packing_attr": pack_attr,
			"bills": bill_data,
		}
		for row in wo_items:
			attr_details = get_variant_attr_details(row['item_variant'])
			set_comb = update_if_string_instance(row['set_combination'])
			major_colour = set_comb['major_colour']
			colour = major_colour
			size = attr_details[primary]
			if size not in data['sizes']:
				data['sizes'].append(size)

			part = None
			if is_set_item:
				variant_colour = attr_details[pack_attr]
				part = attr_details[set_attr]
				colour = variant_colour+"("+ major_colour+") @"+ part

			data['total_qty'].setdefault(colour, {
				"total_delivered": 0,
				"total_received": 0,
				"total_billed": 0,
				"total_quantity": 0,
			})
			data['colours'].setdefault(colour, {
				"part": part,
				"data": {}
			})
			data['colours'][colour]['data'].setdefault(size, {
				"total_delivered": 0,
				"total_received": 0,
				"billed": 0,
				"quantity": 0,
			})
			data['colours'][colour]['data'][size]['total_delivered'] += row['total_delivered']
			data['colours'][colour]['data'][size]['total_received'] += row['total_received']
			data['colours'][colour]['data'][size]['billed'] += row['billed']
			data['colours'][colour]['data'][size]['quantity'] += row['quantity']
			data['total_qty'][colour]['total_delivered'] += row['total_delivered']
			data['total_qty'][colour]['total_received'] += row['total_received']
			data['total_qty'][colour]['total_billed'] += row['billed']
			data['total_qty'][colour]['total_quantity'] += row['quantity']
		item_details.append(data)

	return item_details

@frappe.whitelist()
def fetch_grn_details(grns, against, supplier):
	if isinstance(grns, string_types):
		grns = json.loads(grns)
	grns = list(set(grns))
	items = {}
	exception_item_set = set()
	total_quantity = 0
	wo_items = {}
	if against == 'Purchase Order':
		for grn in grns:
			grn_doc = frappe.get_doc("Goods Received Note", grn)
			for grn_item in grn_doc.items:
				rate = grn_item.rate
				if grn_doc.against == 'Purchase Order':
					discount_percentage = frappe.get_value(grn_item.ref_doctype, grn_item.ref_docname, "discount_percentage")
					if discount_percentage:
						rate = rate - (rate * (discount_percentage / 100))
				key = (grn_item.item_variant, grn_item.uom, rate, grn_item.tax, grn_item.lot)
				item_group, item = get_item_variant_item_group(grn_item.item_variant)
				if not item_group:
					exception_item_set.add(item)
				items.setdefault(key, {
					"item": grn_item.item_variant,
					"lot": grn_item.lot,
					"item_group" : item_group,
					"qty": 0,
					"uom": grn_item.uom,
					"rate": rate,
					"amount": 0,
					"tax": grn_item.tax,
				})
				items[key]["qty"] += grn_item.quantity
				items[key]["amount"] += (grn_item.quantity * rate)
	else:
		has_gst = frappe.get_value("Supplier", supplier, "gstin")
		grn_groups = {}
		for grn in grns:
			wo = frappe.get_value("Goods Received Note", grn, "against_id")
			grn_groups.setdefault(wo, [])
			grn_groups[wo].append(grn)
		
		for wo in grn_groups:
			items_list, process_docname = calculate_grns(grn_groups[wo], wo)
			process_cost_doc = frappe.get_doc("Process Cost", process_docname)
			order_qty_dict = {} 
			tax = None
			if has_gst:
				tax = process_cost_doc.tax_slab
			for row in process_cost_doc.process_cost_values:
				order_qty_dict.setdefault(str(int(row.min_order_qty)), 0)
				order_qty_dict[str(int(row.min_order_qty))] += row.price
			
			sorted_dict = dict(sorted(order_qty_dict.items(), key=lambda x: float(x[0]), reverse=True))
			length = len(sorted_dict)

			qty_list = []
			cost_list = []
			for order_qty in sorted_dict:
				qty_list.append(int(order_qty))
				cost_list.append(order_qty_dict[order_qty])

			wo_doc = frappe.get_doc("Work Order", wo)
			for key_val in items_list:
				variant, major_colour = key_val
				qty = items_list[key_val]['current_grn_received']
				rate = 0
				if length == 1:
					rate = cost_list[0]
				else:
					for idx, order_qty in enumerate(qty_list):
						if order_qty < qty:
							rate = cost_list[idx]
							break 
				items_list[key_val]['rate'] = rate

			item_name = frappe.get_cached_value("Process", wo_doc.process_name, "item")
			item_group, uom = frappe.get_cached_value("Item", item_name, ["item_group", "default_unit_of_measure"])
			get_or_create_variant(item_name, {})
			if not item_group:
				exception_item_set.add(item_name)
				continue
			
			for key_val in items_list:
				variant, major_colour = key_val
				rate = items_list[key_val]['rate']
				key = (item_name, uom, rate, tax, wo_doc.lot)
				items.setdefault(key, {
					"item": item_name,
					"lot": wo_doc.lot,
					"item_group" : item_group,
					"qty": 0,
					"uom": uom,
					"rate": rate,
					"amount": 0,
					"tax": tax,
				})
				wo_items.setdefault(wo, {})
				wo_items[wo].setdefault(key_val, {
					"item_variant": variant,
					"set_combination": frappe.json.dumps(items_list[key_val]['set_combination']),
					"work_order": wo,
					"billed": 0,
					"total_delivered": 0,
					"total_received": 0,
					"quantity": 0,
				})
				wo_items[wo][key_val]['billed'] += items_list[key_val]['billed']
				wo_items[wo][key_val]['total_delivered'] += items_list[key_val]['delivered']
				wo_items[wo][key_val]['total_received'] += items_list[key_val]['received']
				wo_items[wo][key_val]['quantity'] += items_list[key_val]['current_grn_received']
				total_quantity += items_list[key_val]['current_grn_received']
				items[key]['qty'] += items_list[key_val]['current_grn_received']

	work_order_items = []

	for wo in wo_items:
		for key_val in wo_items[wo]:
			work_order_items.append(wo_items[wo][key_val])

	if exception_item_set and len(exception_item_set) > 0:
		exception = "The Below Items Does Not Have Item Group<br>"
		exception += "<br>".join([ f"<a href='/app/item/{_}' target='_blank'>{_}</a>" for _ in list(exception_item_set)])
		frappe.throw(exception)		

	grand_total = 0
	for item in items.values():
		item_total = item['rate'] * item['qty']
		tax = (item_total * (float(item['tax'] or 0) / 100))
		total = item_total + tax
		grand_total += total

	return {
		"items": list(items.values()),
		"total": grand_total,
		"total_quantity": total_quantity,
		"wo_items": work_order_items
	}		

def calculate_grns(grn_list, wo):
	wo_doc = frappe.get_doc("Work Order", wo)
	from production_api.production_api.doctype.cutting_plan.cutting_plan import get_complete_incomplete_structure
	from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details
	from production_api.production_api.doctype.goods_received_note.goods_received_note import calculate_pieces

	ipd_doc = frappe.get_doc("Item Production Detail", wo_doc.production_detail)
	is_group = frappe.get_value("Process", wo_doc.process_name, "is_group")
	final_process = None
	first_process = None

	if is_group:
		process_doc = frappe.get_doc("Process", wo_doc.process_name)
		for p in process_doc.process_details:
			if not first_process:
				first_process = p.process_name
			final_process = p.process_name
			break

	received_json = False

	stage = ipd_doc.stiching_in_stage
	if is_group:
		if ipd_doc.cutting_process == final_process:
			received_json = True	
		for row in ipd_doc.ipd_processes:
			if row.process_name == final_process and stage == row.stage:
				received_json = True
				break
	else:	
		if wo_doc.process_name == ipd_doc.cutting_process:
			received_json = True	
		else:
			for row in ipd_doc.ipd_processes:
				if row.process_name == wo_doc.process_name and stage == row.stage:
					received_json = True
					break
	
	incomplete = None
	complete = None
	items_list = {}
	grn_total_received = {}
	process_docname = wo_doc.calc_receivable_rate(get_name=True)
	if received_json:
		items = fetch_order_item_details(wo_doc.work_order_calculated_items, wo_doc.production_detail)
		complete, incomplete = get_complete_incomplete_structure(wo_doc.production_detail, items)

	for row in wo_doc.work_order_calculated_items:
		set_comb = update_if_string_instance(row.set_combination)
		key = (row.item_variant, set_comb['major_colour'])
		items_list[key] = {
			"item_variant": row.item_variant,
			"set_combination": set_comb,
			"delivered": row.delivered_quantity,
			"received": row.received_qty,
			"billed": row.billed_qty,
			"current_grn_received": 0,
			"difference": 0
		}

	for grn in grn_list:
		if received_json:
			complete, incomplete = calculate_pieces(grn, complete_json=complete, incomplete_json=incomplete, from_pi=True)	
		else:
			grn_doc = frappe.get_doc("Goods Received Note", grn)
			for row in grn_doc.items:
				set_comb = update_if_string_instance(row.set_combination)
				key = (row.item_variant, set_comb['major_colour'])
				items_list[key]['current_grn_received'] += row.quantity
				grn_total_received.setdefault(key, {
					"item_variant": row.item_variant,
					"qty": 0
				})
				grn_total_received[key]['qty'] += row.quantity
	
	if received_json:
		for row in complete['items']:
			attrs = row['attributes']
			set_comb = row['item_keys']
			for size in row['values']:
				attrs[row['primary_attribute']] = size
				variant = get_or_create_variant(row['name'], attrs)
				for rec_type in row['values'][size]:
					key = (variant, set_comb['major_colour'])
					items_list[key]['current_grn_received'] += row['values'][size][rec_type]
					grn_total_received.setdefault(key, {
						"item_variant": variant,
						"qty": 0
					})
					grn_total_received[key]["qty"] += row['values'][size][rec_type]
	
	for key_val in items_list:
		items_list[key_val]['difference'] = items_list[key_val]['received'] - items_list[key_val]['billed']

	return items_list, process_docname

@frappe.whitelist()
def get_erp_inv_link(name):
	d = frappe.get_doc("Purchase Invoice", name)
	if d.docstatus == 1 and d.erp_inv_name:
		erp_url = frappe.get_single("MRP Settings").erp_site_url
		return f"{erp_url}/app/purchase-invoice/{urllib.parse.quote(d.erp_inv_name, safe='')}"
	else:
		frappe.throw("Document not submitted")
