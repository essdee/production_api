# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from frappe import _, bold
from six import string_types
import frappe,json, sys, math
from datetime import datetime
from itertools import groupby, zip_longest
from frappe.model.document import Document
from production_api.mrp_stock.utils import get_stock_balance
from frappe.utils import money_in_words, flt, cstr, date_diff
from production_api.production_api.logger import get_module_logger
from production_api.mrp_stock.doctype.stock_entry.stock_entry import get_uom_details
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant
from production_api.production_api.doctype.work_order.work_order import get_bom_structure, get_work_order_items
from production_api.production_api.doctype.purchase_order.purchase_order import (
    							get_item_attribute_details, get_item_group_index)
from production_api.utils import (
    			get_panel_list, get_stich_details, update_if_string_instance, get_lpiece_variant, get_finishing_plan_dict,
				get_finishing_plan_list)
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import (
    														get_calculated_bom, get_cloth_combination)
from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import (
										get_cut_bundle_entry, make_cut_bundle_ledger, cancel_cut_bundle_ledger)

class GoodsReceivedNote(Document):
	def before_cancel(self):
		if self.against == "Work Order" and not self.is_return:
			ste_list = frappe.get_list("Stock Entry", filters={
				"against":self.doctype,
				"against_id":self.name,
				"purpose":"GRN Completion",
				"docstatus":1,
			}, pluck="name")
			for name in ste_list:
				doc = frappe.get_doc("Stock Entry", name)
				doc.cancel()

	def onload(self):
		if self.against == "Purchase Order":
			item_details = fetch_grn_purchase_item_details(self.get('items'), docstatus=self.docstatus)
			self.set_onload('item_details', item_details)
		elif self.against == "Work Order" and self.is_return:
			item_details = fetch_grn_return_item(self.get('items'))
			self.set_onload('item_details', item_details)
		else:
			items = self.get('items')
			if self.docstatus != 0:
				items = self.get('items_json')
			if self.includes_packing:
				item_details = fetch_grn_packing_items(self.items)
				self.set_onload("pack_items", item_details)
			else:		
				ipd = frappe.get_cached_value("Work Order", self.against_id, "production_detail")	
				item_details = fetch_grn_item_details(items, ipd, self.lot, docstatus=self.docstatus)
				self.set_onload('item_details', item_details)
				if self.is_manual_entry and not self.additional_grn:
					items = self.get("grn_deliverables") 
					item_details = fetch_consumed_item_details(items)
					self.set_onload("consumed_items", item_details)

	def before_save(self):
		if self.against == 'Purchase Order': 
			self.calculate_amount()
		elif not self.is_return and self.against == "Work Order":
			self.dump_items()	
		if self.includes_packing:
			deliverables, excess_list = get_packing_process_deliverables(self)	
			self.set("grn_deliverables", deliverables)
			self.set("grn_excess_usage_items", excess_list)	

	def before_submit(self):
		if not self.vehicle_no:
			frappe.throw("Enter Vehicle No")
		if not self.supplier_document_no:
			frappe.throw("Enter Supplier Document No")

		if self.against == "Work Order" and self.additional_grn or self.allow_non_bundle:
			role = frappe.db.get_single_value("MRP Settings", "additional_grn_submit_role")
			if not role:
				frappe.throw("Set the role for additional GRN submit in MRP Settings", title='GRN')
			user_roles = frappe.get_roles(frappe.session.user)
			if role not in user_roles:
				frappe.throw(f"Only {role} can submit this document.", title='GRN')

		self.letter_head = frappe.db.get_single_value("MRP Settings","dc_grn_letter_head")
		against_docstatus = frappe.get_value(self.against, self.against_id, 'docstatus')
		if against_docstatus != 1:
			frappe.throw(f'{self.against} is not submitted.', title='GRN')
		
		if self.against == 'Purchase Order':		
			total_qty = 0	
			for item in self.items:
				total_qty += item.quantity
			for item in self.items:
				if item.quantity == 0:
					self.items.remove(item)		
			self.validate_quantity()
			self.freight_charge_per_product = round(self.freight_charges/total_qty, 2)
			self.calculate_amount()
		else:
			if self.additional_grn:
				self.set("grn_deliverables", [])
			items = []
			for item in self.items:
				if item.quantity > 0:
					items.append(item.as_dict())
			if len(items) == 0:
				frappe.throw("There is No Received Items in this GRN")		
			self.set("items", items)	
			check = False
			if not self.cut_panel_movement and not self.cutting_laysheet and not self.is_return and not self.allow_non_bundle and not self.includes_packing:
				cancelled_str = frappe.db.get_single_value("MRP Settings", "cut_bundle_cancelled_lot")
				cancelled_list = cancelled_str.split(",")
				if self.lot not in cancelled_list:
					check = check_cut_stage_items(self.items, self.lot)
					if check:
						frappe.throw("Create this Using Cut Panel Movement")			

			self.dump_items()	
			if self.is_return:
				from production_api.mrp_stock.stock_ledger import make_sl_entries
				lot = frappe.get_cached_value(self.against, self.against_id, "lot")
				stock_settings = frappe.get_single("Stock Settings")
				default_received_type = stock_settings.default_received_type
				reduce_stock_list = []
				add_stock_list = []
				wo_doc = frappe.get_doc("Work Order", self.against_id)
				for item in self.items:
					quantity = item.quantity
					if quantity <= 0:
						continue
					for wo_item in wo_doc.deliverables:
						set1 = update_if_string_instance(item.set_combination)
						set2 = update_if_string_instance(wo_item.set_combination)
						if item.item_variant == wo_item.item_variant and set1 == set2:
							wo_item.pending_quantity += quantity
							break
				wo_doc.save(ignore_permissions=True)		
				for item in self.items:
					received_type = item.received_type
					reduce_stock_list.append(self.get_return_deliverables(item, lot, {}, -1, default_received_type, self.supplier))
					add_stock_list.append(self.get_return_deliverables(item, lot, {}, 1, received_type, self.delivery_location))
				if self.includes_packing:
					pack_attr, dept_attr, stich_stage = frappe.get_value("Item Production Detail", wo_doc.production_detail, ["packing_attribute", "dependent_attribute", "stiching_out_stage"])
					from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import (
						check_dependent_stage_variant
					)
					for reduce_item in reduce_stock_list:
						if check_dependent_stage_variant(reduce_item['item'], dept_attr, stich_stage):
							variant = get_lpiece_variant(pack_attr, dept_attr, reduce_item['item'])
							reduce_item['item'] = variant
				make_sl_entries(reduce_stock_list)
				make_sl_entries(add_stock_list)
				
			else:		
				if not self.is_manual_entry and not self.flags.from_cls and not self.is_rework and not self.additional_grn and not self.includes_packing:
					self.calculate_grn_deliverables()
				elif self.includes_packing:
					self.update_pack_variant_items()
				self.split_items()
			self.validate_deliverables()

		self.set('approved_by', frappe.get_user().doc.name)
	
	def update_pack_variant_items(self):
		from production_api.production_api.doctype.item.item import get_or_create_variant
		pack_out_stage, ipd, itemname = frappe.get_value("Lot", self.lot, ["pack_out_stage", "production_detail", "item"])
		dept_attr = frappe.get_value("Item Production Detail", ipd, "dependent_attribute")
		for item in self.items:
			variant = frappe.get_doc("Item Variant", item.item_variant)
			attr_details = get_variant_attributes(variant)
			attr_details[dept_attr] = pack_out_stage
			new_variant = get_or_create_variant(itemname, attr_details)
			item.item_variant = new_variant

		sl_entries = []
		default_received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
		for d in self.grn_excess_usage_items:			
			sl_entries.append(frappe._dict({
				"item": d.get("item_variant", None),
				"warehouse": self.supplier,
				"received_type": default_received_type,
				"lot": cstr(self.lot).strip(),
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"voucher_detail_no": d.get('name'),
				"qty": d.excess_quantity,
				"uom": d.get('uom'),
				"rate": d.get('rate'),
				"valuation_rate":d.get('rate'),
				"is_cancelled": 0,
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
			}))
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		make_sl_entries(sl_entries)	

	def make_repost_action(self):
		from production_api.mrp_stock.stock_ledger import repost_future_stock_ledger_entry
		repost_future_stock_ledger_entry(self)

	def on_submit(self):
		logger = get_module_logger("goods_received_note")
		make_piece_calculation = False
		if self.against == 'Purchase Order':
			logger.debug(f"Purchase Order {datetime.now()}")
			self.update_purchase_order()
			logger.debug(f"{self.name} PO Updated {datetime.now()}")
			self.update_stock_ledger()
			logger.debug(f"{self.name} SLE Updated {datetime.now()}")
		elif not self.is_return and self.against == "Work Order":
			from production_api.production_api.doctype.delivery_challan.delivery_challan import get_variant_stock_details
			logger.debug(f"{self.name} Work Order {datetime.now()}")
			res = get_variant_stock_details()
			self.update_work_order_receivables()
			logger.debug(f"{self.name} WO Receivables Updated {datetime.now()}")
			self.update_wo_stock_ledger(res)
			logger.debug(f"{self.name} Items Added to Delivery Location {datetime.now()}")
			if self.is_rework:
				self.reduce_rework_stock()				
			else:
				self.reduce_uncalculated_stock(res)
				logger.debug(f"{self.name} Deliverables Reduced from Supplier {datetime.now()}")
				if self.supplier_address == self.delivery_address and self.is_internal_unit:
					self.db_set("ste_transferred_percent", 100)
					self.db_set("ste_transferred", self.total_delivered_qty)
					self.db_set("transfer_complete", 1)
				make_piece_calculation = True	

		cancelled_str = frappe.db.get_single_value("MRP Settings", "cut_bundle_cancelled_lot")
		cancelled_list = cancelled_str.split(",")
		if self.lot not in cancelled_list:
			if not self.additional_grn and self.against == "Work Order":
				from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import (
					update_collapsed_bundle
				)	
				if not self.allow_non_bundle:
					if self.is_return and not self.cut_panel_movement:
						check = check_cut_stage_items(self.items, self.lot)
						if check:
							update_collapsed_bundle(self.doctype, self.name, "on_submit")
					elif self.cut_panel_movement:
						cpm_doc = frappe.get_doc("Cut Panel Movement", self.cut_panel_movement)	
						cpm_doc.against = self.doctype
						cpm_doc.against_id = self.name
						cpm_doc.save()
						from_warehouse = self.supplier
						to_warehouse = self.get_to_warehouse()

						bundles, collapsed_details = get_cut_bundle_entry(cpm_doc, self, from_warehouse, -1)
						self.check_bundle_qty(bundles)
						make_cut_bundle_ledger(bundles, collapsed_details)
						bundles, collapsed_details = get_cut_bundle_entry(cpm_doc, self, to_warehouse, 1)
						make_cut_bundle_ledger(bundles, collapsed_details)
					else:
						ipd = frappe.get_value("Lot", self.lot, "production_detail")	
						stich_process = frappe.get_value("Item Production Detail", ipd, "stiching_process")
						if stich_process == self.process_name:
							update_collapsed_bundle(self.doctype, self.name, "on_submit")
				else:
					update_collapsed_bundle(self.doctype, self.name, "on_submit", non_stich_process=True)
		self.make_repost_action()

		if make_piece_calculation:
			self.piece_calculation()
		self.generate_rework_docs()
		self.update_finishing_doc()
	
	def update_finishing_doc(self):
		finishing_inward_process = frappe.db.get_single_value("MRP Settings", "finishing_inward_process")
		if self.includes_packing:
			finishing_doc = frappe.get_all("Finishing Plan", filters={
				"lot": self.lot, 
			}, pluck="name", limit=1)
			if finishing_doc:
				frappe.enqueue(
					update_finishing_item_doc, 
					"short", 
					doc_name=self.name, 
					finishing_doc_name=finishing_doc[0],
				  	update_finishing=True,
					enqueue_after_commit=True
				)
				# update_finishing_item_doc(self.name, finishing_doc[0], update_finishing=True)
		else:
			is_group = frappe.get_value("Process", self.process_name, "is_group")
			check = False
			if is_group:
				process = None
				doc = frappe.get_doc("Process", self.process_name)
				for row in doc.process_details:
					process = row.process_name
				check = process == finishing_inward_process
			else:
				check = self.process_name == finishing_inward_process

			if check:
				finishing_doc = frappe.get_all("Finishing Plan", filters={
					"lot": self.lot, 
				}, pluck="name", limit=1)
				if finishing_doc:
					# update_finishing_item_doc(self.name, finishing_doc[0], update_finishing=False)
					frappe.enqueue(
						update_finishing_item_doc, 
						"short", 
						doc_name=self.name, 
						finishing_doc_name=finishing_doc[0],
						update_finishing=False,
						enqueue_after_commit=True
					)

	def check_bundle_qty(self, bundles):
		ipd = frappe.get_value("Lot", self.lot, "production_detail")
		ipd_doc = frappe.get_doc("Item Production Detail", ipd)
		panel_count = {}
		for panel in ipd_doc.stiching_item_details:
			panel_count[panel.stiching_attribute_value] = panel.quantity

		bundle_variant_d = {} 
		for bundle in bundles:
			for panel in bundle['panel'].split(","):
				variant = get_or_create_variant(bundle['item'], {
					ipd_doc.dependent_attribute: ipd_doc.stiching_in_stage,
					ipd_doc.primary_item_attribute: bundle['size'],
					ipd_doc.packing_attribute: bundle['colour'],
					ipd_doc.stiching_attribute: panel
				})
				bundle_variant_d.setdefault(variant, 0)
				bundle_variant_d[variant] += (bundle['quantity'] * panel_count[panel]) * -1

		challan_variant_d = {}
		for item in self.items:
			if item.quantity > 0:
				challan_variant_d.setdefault(item.item_variant, 0)
				challan_variant_d[item.item_variant] += item.quantity

		for variant in bundle_variant_d:
			if variant not in challan_variant_d:
				frappe.throw("Unwanted bundles are selected in Cut Panel Movement")
			
			if bundle_variant_d[variant] != challan_variant_d[variant]:
				frappe.throw(f"Quantity Mismatch on Variant {variant}")
	
	def generate_rework_docs(self):
		# generate_rework(self.name)
		frappe.enqueue(generate_rework, "short", doc_name=self.name, enqueue_after_commit=True)

	def get_to_warehouse(self):
		to_warehouse = self.delivery_location
		if self.is_internal_unit and self.supplier_address != self.delivery_address:
			to_warehouse = frappe.get_single("Stock Settings").transit_warehouse
		
		return to_warehouse	

	def piece_calculation(self):
		# calculate_pieces(self.name)
		frappe.enqueue(calculate_pieces, "short", doc_name=self.name, enqueue_after_commit=True)
	
	def reduce_rework_stock(self):
		wo_doc = frappe.get_doc(self.against, self.against_id)
		variant_received_types = {}
		for item in self.items:
			quantity = item.quantity
			if quantity <= 0:
				continue
			for wo_item in wo_doc.deliverables:
				set1 = update_if_string_instance(item.set_combination)
				set2 = update_if_string_instance(wo_item.set_combination)
				valid_qty = wo_item.qty - wo_item.pending_quantity - wo_item.stock_update
				if item.item_variant == wo_item.item_variant and set1 == set2 and valid_qty > 0:
					variant_received_types.setdefault((item.item_variant, item.name), {})
					variant_received_types[(item.item_variant, item.name)].setdefault(wo_item.item_type, {
						"qty": 0,
						"uom": item.uom
					})
					variant_received_types[(item.item_variant, item.name)][wo_item.item_type]['qty'] += valid_qty
					wo_item.stock_update += valid_qty
					quantity -= valid_qty
				if quantity <= 0:
					break	
		wo_doc.save(ignore_permissions=True)
		sl_entries = []
		for (variant, detail_no) in variant_received_types:
			for received_type in variant_received_types[(variant, detail_no)]:
				sl_entries.append(self.get_rework_deliverables(variant, received_type, detail_no, variant_received_types, -1))

		from production_api.mrp_stock.stock_ledger import make_sl_entries
		make_sl_entries(sl_entries)		

	def get_rework_deliverables(self, variant, received_type, detail_no, variant_received_types, multiplier):
		uom = variant_received_types[(variant, detail_no)][received_type]['uom']
		rate = get_stock_balance(
			variant, None, received_type, posting_date=self.posting_date, 
				posting_time=self.posting_time, with_valuation_rate=True, uom=uom,
		)[1]
		return frappe._dict({
			"item": variant,
			"warehouse": self.supplier,
			"received_type":received_type,
			"lot": self.lot,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": detail_no,
			"qty": variant_received_types[(variant, detail_no)][received_type]['qty'] * multiplier,
			"uom": uom,
			"rate": rate,
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			"valuation_rate": rate,
		})

	def split_items(self):
		items_list = []
		total_delivered = flt(0)
		for item in self.items:
			total_delivered += item.quantity
			received_types = update_if_string_instance(item.received_types)
			x = {
				"item_variant":item.item_variant,
				"tax":item.tax,
				"lot":item.lot,
				"secondary_qty":item.secondary_qty,
				"uom":item.uom,
				"secondary_uom":item.secondary_uom,
				"stock_uom":item.stock_uom,
				"conversion_factor":item.conversion_factor,
				"rate":item.rate,
				"table_index":item.table_index,
				"row_index":item.row_index,
				"ref_doctype":item.ref_doctype,
				"ref_docname":item.ref_docname,
				"comments":item.comments,
				"set_combination":item.set_combination,
				"stock_uom_rate":item.stock_uom_rate,
			}
			secondary_qty_json = update_if_string_instance(item.secondary_qty_json)

			if not received_types:
				x['quantity'] = 0
				x['amount'] = 0
				if not secondary_qty_json:
					x['secondary_qty'] = 0
					x['secondary_uom'] = None
				m = x.copy()
				items_list.append(m)
			else:
				for type1, qty1 in received_types.items():
					x['quantity'] = qty1
					x['stock_qty'] =  flt(flt(qty1) * flt(item.conversion_factor))
					x['amount'] = item.rate * qty1
					x['received_type'] = type1
					if secondary_qty_json:
						for type2, qty2 in secondary_qty_json.items():
							if type1 == type2:
								x['secondary_qty'] = qty2
								m = x.copy()
								items_list.append(m)
					else:
						m = x.copy()
						items_list.append(m)
						
		self.total_delivered_qty = total_delivered			
		self.set("items",items_list)

	def dump_items(self):
		items = []
		for item in self.items:
			items.append({
				"item_variant":item.item_variant,
				"tax":item.tax,
				"lot":item.lot,
				"quantity":item.quantity,
				"secondary_qty":item.secondary_qty,
				"stock_qty":item.stock_qty,
				"uom":item.uom,
				"secondary_uom":item.secondary_uom,
				"stock_uom":item.stock_uom,
				"conversion_factor":item.conversion_factor,
				"rate":item.rate,
				"amount":item.amount,
				"stock_uom_rate":item.stock_uom_rate,
				"table_index":item.table_index,
				"row_index":item.row_index,
				"ref_doctype":item.ref_doctype,
				"ref_docname":item.ref_docname,
				"comments":item.comments,
				"received_types":item.received_types,
				"secondary_qty_json":item.secondary_qty_json,
				"set_combination": item.set_combination,
			})	
		x = json.dumps(items)
		self.db_set("items_json",x)

	def update_work_order_receivables(self):
		if self.docstatus == 0:
			return
		wo = frappe.get_doc(self.against, self.against_id)
		for item in self.items:
			if item.quantity <= 0:
				continue
			for i in wo.receivables:
				if i.name == item.ref_docname:
					qty = i.pending_quantity - item.quantity 
					i.set('pending_quantity', qty)
					break
		d = {}
		for item in wo.work_order_excess_usage_items:		
			d.setdefault(item.item_variant, {
				"quantity": item.excess_quantity,
				"uom": item.uom,
				"rate": item.rate,
			})
		for item in self.grn_excess_usage_items:
			if item.item_variant in d:
				d[item.item_variant]['quantity'] += item.excess_quantity
			else:
				d[item.item_variant] = {
					"quantity": item.excess_quantity,
					"uom": item.uom,
					"rate": item.rate,
				}
		excess_items = []		
		for key in d:
			excess_items.append({
				"item_variant": key,
				"excess_quantity": d[key]['quantity'],
				"uom": d[key]['uom'],
				"rate": d[key]['rate'],
			})
		wo.set("work_order_excess_usage_items", excess_items)
		wo.save(ignore_permissions=True)

	def calculate_grn_deliverables(self):
		total_received_qty = 0
		for item in self.items:
			total_received_qty += item.quantity	

		wo_doc = frappe.get_cached_doc(self.against, self.against_id)
		calculated_items = {}
		for item in self.grn_deliverables:
			item_keys = update_if_string_instance(item.set_combination)
			item_keys.update({"variant":item.item_variant})
			item_keys = item_keys.copy()
			item_keys = frozenset(item_keys)
			calculated_items[item_keys] = item.quantity

		for item in wo_doc.deliverables:
			check = True
			keys = update_if_string_instance(item.set_combination)
			keys.update({"variant":item.item_variant})
			keys = keys.copy()
			keys = frozenset(keys)
			x = calculated_items.get(keys)
			if x == 0:
				check = True
			elif not x:
				check = False	
			if item.is_calculated and check:
				item.stock_update += calculated_items[keys]

		wo_doc.save(ignore_permissions = True)	

	def update_wo_stock_ledger(self, res):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		deliverables_rate = 0
		for item in self.grn_deliverables:
			if res.get(item.item_variant) and item.quantity:
				deliverables_rate = deliverables_rate + (item.valuation_rate * item.quantity)
		avg = deliverables_rate / self.total_received_quantity
		# frappe.throw(str(avg))
		supplier = self.get_to_warehouse()
		sl_entries = []
		for item in self.items:
			if item.quantity > 0 and res.get(item.item_variant):
				sl_entries.append(self.get_sl_entries(item, supplier, {}, 1, item.received_type, valuation_rate=avg))
		make_sl_entries(sl_entries)

	def reduce_uncalculated_stock(self, res):
		if self.additional_grn:
			return
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		lot = frappe.get_cached_value(self.against, self.against_id, "lot")
		stock_settings = frappe.get_single("Stock Settings")
		received_type = stock_settings.default_received_type
		sl_entries = []
		item_name, ipd = frappe.get_value("Lot", lot, ["item", "production_detail"])
		is_set = frappe.get_value("Item Production Detail", ipd, "is_set_item")
		for item in self.grn_deliverables:
			if res.get(item.item_variant):
				variant_item = frappe.get_value("Item Variant", item.item_variant, "item")
				multiplier = -1
				if variant_item == item_name and self.includes_packing and is_set:
					multiplier = -2
				sl_entries.append(self.get_deliverables_data(item, lot, {}, multiplier, received_type))
		make_sl_entries(sl_entries)
	
	def get_deliverables_data(self, d, lot, args, multiplier, received_type):
		rate = get_stock_balance(
			d.item_variant, None, received_type, posting_date=self.posting_date, 
				posting_time=self.posting_time, with_valuation_rate=True, uom=d.uom,
		)[1]
		sl_dict = frappe._dict({
			"item": d.item_variant,
			"warehouse": self.supplier,
			"received_type":received_type,
			"lot": lot,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": d.name,
			"qty": d.get('stock_qty') * multiplier,
			"uom": d.get('stock_uom'),
			"rate": rate,
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			"valuation_rate": rate,
		})
		sl_dict.update(args)
		return sl_dict
	
	def get_return_deliverables(self, d, lot, args, multiplier, received_type, supplier):
		rate = get_stock_balance(
			d.item_variant, None, received_type, posting_date=self.posting_date, 
				posting_time=self.posting_time, with_valuation_rate=True, uom=d.get('stock_uom'),
		)[1]
		sl_dict = frappe._dict({
			"item": d.item_variant,
			"warehouse": supplier,
			"received_type":received_type,
			"lot": lot,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": d.name,
			"qty": d.get('stock_qty') * multiplier,
			"uom": d.get('stock_uom'),
			"rate": rate,
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			"valuation_rate": rate,
		})
		sl_dict.update(args)
		return sl_dict
	
	def get_sl_entries(self, d, from_location, args, multiplier, received_type, valuation_rate = 0.0):
		qty = None
		if self.against == "Work Order":
			qty = flt(d.get("stock_qty")) * multiplier
			rate = get_stock_balance(
				d.get('item_variant'), None, received_type, posting_date=self.posting_date, 
				posting_time=self.posting_time, with_valuation_rate=True, uom=d.get('stock_uom'),
			)[1]
			rate = valuation_rate + rate
		else:
			rate = d.rate or 0.0
			rate += self.freight_charge_per_product
			qty = flt(d.get("stock_qty")) * multiplier
		
		sl_dict = frappe._dict({
			"item": d.get("item_variant", None),
			"warehouse": from_location,
			"received_type":received_type,
			"lot": cstr(d.get("lot")).strip(),
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": d.get('name'),
			"qty": qty,
			"uom": d.get('stock_uom'),
			"rate": rate,
			"valuation_rate":rate,
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
		})
		sl_dict.update(args)
		return sl_dict
	
	def on_cancel(self):
		logger = get_module_logger("goods_received_note")
		self.ignore_linked_doctypes = ("Stock Ledger Entry", "Repost Item Valuation", "Cut Panel Movement", "Cut Bundle Movement Ledger")
		make_piece_calculation = False
		if self.against == 'Purchase Order':
			logger.debug(f"{self.name} On Cancel Purchase Order {datetime.now()}")
			if self.purchase_invoice_name:
				frappe.throw(f'Please remove this GRN from Purchase Invoice {self.purchase_invoice_name} before cancelling. Please Contact Purchase Department.')
			settings = frappe.get_single('MRP Settings')
			cancel_before_days = settings.grn_cancellation_in_days
			if cancel_before_days == 0:
				frappe.throw('GRN cancellation is not allowed.', title='GRN')
			if cancel_before_days and not settings.allow_grn_cancellation:
				if date_diff(frappe.utils.nowdate(), self.creation) > cancel_before_days:
					frappe.throw(f'GRN cannot be cancelled after {cancel_before_days} days of creation.', title='GRN')
				status = frappe.get_value('Purchase Order', self.against_id, 'open_status')
				if status != 'Open':
					frappe.throw('Purchase order is not open.', title='GRN')
			self.update_purchase_order()
			logger.debug(f"{self.name} PO Updated {datetime.now()}")
			self.update_stock_ledger()	
			logger.debug(f"{self.name} Stock Updated {datetime.now()}")
		else:
			if self.is_return:
				from production_api.mrp_stock.stock_ledger import make_sl_entries
				lot = frappe.get_cached_value(self.against,self.against_id, "lot")
				stock_settings = frappe.get_single("Stock Settings")
				default_received_type = stock_settings.default_received_type
				reduce_stock_list = []
				add_stock_list = []
				wo_doc = frappe.get_doc("Work Order", self.against_id)
				for item in self.items:
					quantity = item.quantity
					if quantity <= 0:
						continue
					for wo_item in wo_doc.deliverables:
						set1 = update_if_string_instance(item.set_combination)
						set2 = update_if_string_instance(wo_item.set_combination)
						if item.item_variant == wo_item.item_variant and set1 == set2:
							wo_item.pending_quantity -= quantity
							break
				wo_doc.save(ignore_permissions=True)		
				for item in self.items:
					received_type = item.received_type
					reduce_stock_list.append(self.get_return_deliverables(item, lot, {}, 1, received_type, self.delivery_location))
					add_stock_list.append(self.get_return_deliverables(item, lot, {}, -1, default_received_type, self.supplier))
				if self.includes_packing:
					pack_attr, dept_attr, stich_stage = frappe.get_value("Item Production Detail", wo_doc.production_detail, ["packing_attribute", "dependent_attribute", "stiching_out_stage"])
					from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import (
						check_dependent_stage_variant
					)
					for add_item in add_stock_list:
						if check_dependent_stage_variant(add_item['item'], dept_attr, stich_stage):
							variant = get_lpiece_variant(pack_attr, dept_attr, add_item['item'])
							add_item['item'] = variant

				make_sl_entries(reduce_stock_list)
				make_sl_entries(add_stock_list)
			else:	
				logger.debug(f"{self.name} On Cancel {self.against} {datetime.now()}")
				wo_doc = frappe.get_doc(self.against, self.against_id)
				items = update_if_string_instance(self.items_json)
				for item in items:
					for receivable in wo_doc.receivables:
						if item['ref_docname'] == receivable.name and flt(item['quantity']) > flt(0):
							receivable.pending_quantity += item['quantity']
							break
				wo_doc.save(ignore_permissions=True)
				logger.debug(f"{self.name} WO Receivable Updated {datetime.now()}")
				from production_api.production_api.doctype.delivery_challan.delivery_challan import get_variant_stock_details
				res = get_variant_stock_details()
				self.reupdate_stock_ledger(res)
				logger.debug(f"{self.name} Stock Updated {datetime.now()}")
				if self.is_rework:
					self.reupdate_rework_stock()
				else:	
					self.reupdate_wo_deliverables(res)
					logger.debug(f"{self.name} Deliverables Updated {datetime.now()}")	
				
				if self.supplier_address == self.delivery_address and self.is_internal_unit:
					self.db_set("ste_transferred_percent", 0)
					self.db_set("ste_transferred", 0)
					self.db_set("transfer_complete", 0)
				make_piece_calculation = True

		cancelled_str = frappe.db.get_single_value("MRP Settings", "cut_bundle_cancelled_lot")
		cancelled_list = cancelled_str.split(",")
		if self.lot not in cancelled_list:
			if not self.additional_grn and self.against == "Work Order":	
				from production_api.production_api.doctype.cut_bundle_movement_ledger.cut_bundle_movement_ledger import (
					update_collapsed_bundle
				)
				if not self.allow_non_bundle:
					if self.is_return and not self.cut_panel_movement:
						check = check_cut_stage_items(self.items, self.lot)
						if check:
							update_collapsed_bundle(self.doctype, self.name, "on_cancel")

					elif self.cut_panel_movement:
						cpm_doc = frappe.get_doc("Cut Panel Movement", self.cut_panel_movement)	
						cpm_doc.against = None
						cpm_doc.against_id = None
						cpm_doc.save()
						from_warehouse = self.supplier
						to_warehouse = self.get_to_warehouse()

						bundles, collapsed_bundles = get_cut_bundle_entry(cpm_doc, self, to_warehouse, -1, cancelled=1)
						cancel_cut_bundle_ledger(bundles)
						bundles, collapsed_bundles = get_cut_bundle_entry(cpm_doc, self, from_warehouse, 1, cancelled=1)
						cancel_cut_bundle_ledger(bundles)
					else:
						ipd = frappe.get_value("Lot", self.lot, "production_detail")	
						stich_process = frappe.get_value("Item Production Detail", ipd, "stiching_process")
						if stich_process == self.process_name:
							update_collapsed_bundle(self.doctype, self.name, "on_cancel")						
				else:
					update_collapsed_bundle(self.doctype, self.name, "on_cancel", non_stich_prcoess=True)						

		self.make_repost_action()
		if make_piece_calculation:
			self.piece_calculation()
			frappe.db.sql(
				"""
					DELETE FROM `tabGRN Rework Item` WHERE grn_number = %(grn)s
				""", {
					"grn": self.name
				}
			)
		self.generate_rework_docs()	
		self.update_finishing_doc()	
			
	def reupdate_rework_stock(self):
		wo_doc = frappe.get_doc(self.against, self.against_id)
		variant_received_types = {}
		for item in self.items:
			quantity = item.quantity
			if quantity <= 0:
				continue
			for wo_item in wo_doc.deliverables:
				set1 = update_if_string_instance(item.set_combination)
				set2 = update_if_string_instance(wo_item.set_combination)
				valid_qty = wo_item.stock_update
				if valid_qty > quantity:
					valid_qty = quantity
				if item.item_variant == wo_item.item_variant and set1 == set2 and valid_qty > 0:
					variant_received_types.setdefault((item.item_variant, item.name), {})
					variant_received_types[(item.item_variant, item.name)].setdefault(wo_item.item_type, {
						"qty": 0,
						"uom": item.uom
					})
					variant_received_types[(item.item_variant, item.name)][wo_item.item_type]['qty'] += valid_qty
					wo_item.stock_update -= valid_qty
					quantity -= valid_qty
				if quantity <= 0:
					break	
		wo_doc.save(ignore_permissions=True)
		sl_entries = []
		for (variant, detail_no) in variant_received_types:
			for received_type in variant_received_types[(variant, detail_no)]:
				sl_entries.append(self.get_rework_deliverables(variant, received_type, detail_no, variant_received_types, 1))

		from production_api.mrp_stock.stock_ledger import make_sl_entries
		make_sl_entries(sl_entries)		

	def reupdate_stock_ledger(self, res):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		sl_entries = []
		avg = self.total_receivable_cost / self.total_received_quantity
		items = update_if_string_instance(self.items_json)
		for item in items:
			if item['quantity'] > 0 and res.get(item['item_variant']):
				received_types = update_if_string_instance(item.get("received_types"))
				for type, qty in received_types.items():
					x = item
					x['quantity'] = qty
					sl_entries.append(self.get_sl_entries(item, self.delivery_location, {}, 1, type, valuation_rate=avg))
		make_sl_entries(sl_entries)	

	def reupdate_wo_deliverables(self, res):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		total_received_qty = 0
		items = update_if_string_instance(self.items_json)
		for item in items:
			total_received_qty += item['quantity']

		wo_doc = frappe.get_cached_doc(self.against,self.against_id)
		calculated_items = {}
		for item in self.grn_deliverables:
			item_keys = update_if_string_instance(item.set_combination)
			item_keys.update({"variant":item.item_variant})
			item_keys = item_keys.copy()
			item_keys = frozenset(item_keys)
			calculated_items[item_keys] = item.quantity

		for item in wo_doc.deliverables:
			check = True
			keys = update_if_string_instance(item.set_combination)
			keys.update({"variant":item.item_variant})
			keys = keys.copy()
			keys = frozenset(keys)
			x = calculated_items.get(keys)
			if x == 0:
				check = True
			elif not x:
				check = False
			if item.is_calculated and check:
				item.stock_update -= calculated_items[keys]

		lot = wo_doc.lot
		if self.includes_packing:
			d = {}
			for item in wo_doc.work_order_excess_usage_items:
				if item.item_variant in d:
					d[item.item_variant]['quantity'] += item.excesss_quantity
				else:
					d[item.item_variant] = {
						"quantity": item.excess_quantity,
						"uom": item.uom,
						"rate": item.rate,
					}
			for item in self.grn_excess_usage_items:
				d[item.item_variant]['quantity'] -= item.excess_quantity

			excess_items = []		
			for key in d:
				excess_items.append({
					"item_variant": key,
					"excess_quantity": d[key]['quantity'],
					"uom": d[key]['uom'],
					"rate": d[key]['rate'],
				})
			wo_doc.set("work_order_excess_usage_items", excess_items)
		wo_doc.save(ignore_permissions = True)	
		if self.additional_grn:
			return
		sl_entries = []
		received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
		item_name, ipd = frappe.get_value("Lot", lot, ["item", "production_detail"])
		is_set = frappe.get_value("Item Production Detail", ipd, "is_set_item")
		for item in self.grn_deliverables:
			if res.get(item.item_variant):
				variant_item = frappe.get_value("Item Variant", item.item_variant, "item")
				multiplier = -1
				if variant_item == item_name and self.includes_packing and is_set:
					multiplier = -2
				sl_entries.append(self.get_deliverables_data(item, lot, {}, multiplier, received_type))
		make_sl_entries(sl_entries)

	def update_purchase_order(self):
		if self.docstatus == 0:
			return
		multiplier = 1
		if self.docstatus == 2:
			multiplier = -1
		po = frappe.get_cached_doc(self.against, self.against_id)
		for item in self.items:
			# find the po item with the same ref_docname
			for i in po.items:
				if i.name == item.ref_docname:
					quantity = item.quantity * multiplier
					if self.docstatus == 1:
						validate_quantity_tolerance(i.item_variant, i.qty, i.pending_qty, quantity)
					i.set('pending_qty', i.pending_qty - quantity)
					break
		po.save(ignore_permissions=True)

	def update_stock_ledger(self):
		from production_api.mrp_stock.stock_ledger import make_sl_entries
		if self.docstatus == 0:
			return
		sl_entries = []
		received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
		for item in self.items:
			self.received_type = received_type
			sl_entries.append(self.get_sl_entries(item, self.delivery_location, {}, 1, received_type))

		if self.docstatus == 2:
			sl_entries.reverse()
		make_sl_entries(sl_entries)

	def before_validate(self):
		if self.docstatus == 1:
			return
		
		if self.delivery_date > self.posting_date:
			frappe.throw("Delivery Date is Higher than Posting Date")
		if self.against == 'Purchase Order':
			if(self.get('item_details')):
				items = save_grn_purchase_item_details(self.item_details)
				self.set('items', items)
		elif not self.is_return and self.against == "Work Order":
			lot, process, internal, includes_packing = frappe.get_cached_value(self.against, self.against_id, ["lot","process_name","is_internal_unit", "includes_packing"])
			if includes_packing and self.get('item_details'):
				self.includes_packing = includes_packing
				items, total_qty = save_grn_packing_item_details(self.item_details, self.lot)
				self.set('items', items)
				self.total_received_quantity = total_qty
			else:	
				docstatus = frappe.get_value("Work Order", self.against_id, "docstatus")
				if docstatus != 1:
					frappe.throw("Select the Valid Work Order")
				
				if self.flags.from_cls:
					wo_items = get_work_order_items(self.against_id, True)
					self.item_details = wo_items				

				is_manual_entry = frappe.get_value("Process", process, "is_manual_entry_in_grn")
				if self.is_rework:
					is_manual_entry = False
				self.process_name = process
				self.is_manual_entry = is_manual_entry
				self.is_internal_unit = internal
				self.lot = lot	
				check = False
				if self.is_new():
					check = True
				else:
					check = self.get('is_edited')

				if(self.get('item_details')) and check:
					items, total_rate, total_qty = save_grn_item_details(self.item_details, self.process_name)
					self.set('items', items)
					if len(self.items) > 0:
						doc = frappe.get_cached_doc(self.against, self.against_id)
						wo_deliverables = {}
						for row in doc.deliverables:
							wo_deliverables[row.item_variant] = row.valuation_rate
						if not self.is_manual_entry and not self.flags.from_cls and not self.is_rework and not self.additional_grn:
							deliverables = calculate_deliverables(self)
							items = []
							if deliverables:
								for row in deliverables:
									if row['item_variant'] in wo_deliverables:
										items.append({
											"item_variant": row['item_variant'],
											"quantity": row['qty'],
											"uom": row['uom'],
											"valuation_rate": wo_deliverables[row['item_variant']],
											"set_combination": row['set_combination'],
										})
							self.set("grn_deliverables", items)
						self.total_receivable_cost = total_rate
				total_qty = 0
				for item in self.items:
					total_qty += item.quantity
				self.total_received_quantity = total_qty
				if self.get('consumed_item_details'):
					items = save_grn_consumed_item_details(self.consumed_item_details)
					self.set("grn_deliverables", items)

	def validate(self):
		if self.against == 'Purchase Order':
			status = frappe.get_value('Purchase Order', self.against_id, 'open_status')
			if status != 'Open':
				frappe.throw('Purchase order is closed.', title='GRN')
			
			supplier = frappe.get_value('Purchase Order', self.against_id, 'supplier')
			if supplier != self.supplier:
				frappe.throw('Supplier cannot be changed.', title='GRN')
			
			po_docstatus = frappe.get_value('Purchase Order', self.against_id, 'docstatus')
			if po_docstatus != 1:
				frappe.throw('Purchase order is not submitted.', title='GRN')
			self.validate_quantity()
		self.validate_data()

	def validate_quantity(self):
		total_quantity = 0
		for item in self.items:
			total_quantity += item.quantity
		if total_quantity == 0:
			frappe.throw('Quantity cannot be zero.', title='GRN')
	
	def validate_data(self):
		for row in self.items:
			item_details = get_uom_details(row.item_variant, row.uom, row.quantity)
			row.set("stock_uom", item_details.get("stock_uom"))
			row.set("conversion_factor", item_details.get("conversion_factor"))
			row.stock_qty = flt(
				flt(row.quantity) * flt(row.conversion_factor), self.precision("stock_qty", row)
			)
			row.stock_uom_rate = flt(
				flt(row.rate) / flt(row.conversion_factor), self.precision("stock_uom_rate", row)
			)
			row.amount = flt(flt(row.rate) * flt(row.quantity), self.precision("amount", row))

	def validate_deliverables(self):
		for row in self.grn_deliverables:
			item_details = get_uom_details(row.item_variant, row.uom, row.quantity)
			row.set("stock_uom", item_details.get("stock_uom"))
			row.set("conversion_factor", item_details.get("conversion_factor"))
			row.stock_qty = flt(
				flt(row.quantity) * flt(row.conversion_factor), self.precision("stock_qty", row)
			)

	def calculate_amount(self):
		if not self.freight_charges:
			self.freight_charges = 0
		total_amount = 0
		total_tax = 0
		grand_total = 0
		for item in self.items:
			item_total = item.rate * item.quantity
			total_amount += item_total
			tax = item_total * (float(item.tax or 0) / 100)
			total_tax += tax
			total = item_total + tax
			grand_total += total

		grand_total	+= self.freight_charges
		self.set('total', total_amount)
		self.set('total_tax', total_tax)
		self.set('grand_total', grand_total)
		self.set('in_words', money_in_words(grand_total))

def check_cut_stage_items(items, lot):
	ipd = frappe.get_value("Lot", lot, "production_detail")
	stich_stage = frappe.get_value("Item Production Detail", ipd, "stiching_in_stage")
	for item in items:
		item_name = frappe.get_value("Item Variant", item.item_variant, "item")
		dept_attr = frappe.get_value("Item", item_name, "dependent_attribute")
		if not dept_attr:
			continue
		attr_details = frappe.db.sql(
			"""
				SELECT name FROM `tabItem Variant Attribute` WHERE parent = %(parent)s
				AND attribute = %(dependent)s AND attribute_value = %(dependent_value)s
			""", {
				"parent": item.item_variant,
				"dependent" : dept_attr,
				"dependent_value": stich_stage
			}, as_dict=True
		)	
		if attr_details:
			return True
	return False

def save_grn_purchase_item_details(item_details):
	item_details = update_if_string_instance(item_details)
	items = []
	row_index = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():
					if values.get('qty') or values.get('pending_qty') or values.get('received'):
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						variant_name = get_or_create_variant(item_name, item_attributes)
						validate_quantity_tolerance(variant_name, values.get('qty'), values.get('pending_qty'), values.get('received'))
						item1['item_variant'] = variant_name
						item1['lot'] = item.get('lot')

						if isinstance(values.get('received'), string_types) and values.get('received') != '':
							values['received'] = float(values.get('received'))
						else:
							values['received'] = values.get('received') or 0
						item1['quantity'] = values.get('received')
						item1['uom'] = item.get('default_uom')
						if isinstance(values.get('secondary_received'), string_types) and values.get('secondary_received') != '':
							values['secondary_received'] = float(values.get('secondary_received'))
						else:
							values['secondary_received'] = values.get('secondary_received') or 0
						item1['secondary_qty'] = values.get('secondary_received')
						item1['secondary_uom'] = item.get('secondary_uom')
						item1['rate'] = values.get('rate')
						item1['tax'] = values.get('tax')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['comments'] = item.get('comments')
						item1['ref_doctype'] = values.get('ref_doctype')
						item1['ref_docname'] = values.get('ref_docname')
						items.append(item1)
			else:
				if item['values'].get('default'):
					item1 = {}
					variant_name = get_or_create_variant(item_name, item_attributes)
					validate_quantity_tolerance(variant_name, item['values']['default'].get('qty'), item['values']['default'].get('pending_qty'), item['values']['default'].get('received'))
					item1['item_variant'] = variant_name
					item1['lot'] = item.get('lot')
					item1['quantity'] = item['values']['default'].get('received')
					item1['uom'] = item.get('default_uom')
					item1['secondary_qty'] = item['values']['default'].get('secondary_received')
					item1['secondary_uom'] = item.get('secondary_uom')
					item1['rate'] = item['values']['default'].get('rate')
					item1['tax'] = item['values']['default'].get('tax')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments')
					item1['ref_doctype'] = item['values']['default'].get('ref_doctype')
					item1['ref_docname'] = item['values']['default'].get('ref_docname')
					items.append(item1)
			row_index += 1
	return items

def save_grn_consumed_item_details(item_details):
	item_details = update_if_string_instance(item_details)
	items = []
	row_index = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():
					item_attributes[item.get('primary_attribute')] = attr
					item1 = {}
					variant_name = get_or_create_variant(item_name, item_attributes)
					item1['quantity'] = values.get('qty')
					item1['item_variant'] = variant_name
					item1['uom'] = item.get('default_uom')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments') 
					items.append(item1)
			else:
				if item['values'].get('default') and item['values']['default'].get('qty'):
					item1 = {}
					variant_name = get_or_create_variant(item_name, item_attributes)
					item1['quantity'] = item['values']['default'].get('qty')
					item1['item_variant'] = variant_name
					item1['uom'] = item.get('default_uom')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments') 
					items.append(item1)
			row_index += 1
	return items

def fetch_consumed_item_details(items):
	items = [item.as_dict() for item in items]
	item_details = []
	items = sorted(items, key = lambda i: i['row_index'])
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			"dependent_attribute": current_item_attribute_details['dependent_attribute'],
			"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
			'values': {},
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'comments': variants[0]['comments'],
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {'qty': variant.quantity}
						break
		else:
			item['values']['default'] = {'qty': variants[0].quantity}

		index = get_item_group_index(item_details, current_item_attribute_details)
		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				"dependent_attribute": current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return item_details

def save_grn_item_details(item_details, process_name):
	item_details = update_if_string_instance(item_details)
	allowance = frappe.db.get_value("Process",process_name,"additional_allowance")
	items = []
	row_index = 0
	table_index = 1
	total_rate = 0
	total_qty = 0
	for group in item_details:
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():	
					if values.get('ref_docname'):	
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						variant_name = get_or_create_variant(item_name, item_attributes)
						received = values.get('received', 0)
						if received > 0:
							total_quantity, pending_qty = frappe.get_value(values.get('ref_doctype'), values.get('ref_docname'), ["qty","pending_quantity"])
							x = total_quantity / 100
							x = x * allowance
							max_qty = total_quantity + x
							before_received = total_quantity - pending_qty
							if max_qty - before_received < received:
								frappe.throw(f"Received more than the allowed quantity for {bold(variant_name)}")

						item1['item_variant'] = variant_name
						item1['lot'] = item.get('lot')
						item1['quantity'] = received
						item1['received_types'] = values.get('types')
						item1['secondary_qty_json'] = values.get('secondary_qty_json')
						item1['uom'] = item.get('default_uom')
						item1['secondary_qty'] = values.get('secondary_received')
						item1['secondary_uom'] = item.get('secondary_uom')
						item1['rate'] = values.get('rate')
						item1['tax'] = values.get('tax')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['comments'] = item.get('comments')
						item1['ref_doctype'] = values.get('ref_doctype')
						item1['ref_docname'] = values.get('ref_docname')
						item1['set_combination'] = values.get('set_combination', {})
						items.append(item1)
						if received:
							total_qty = total_qty + received
							total_rate = total_rate + (received * values.get('rate'))	
			else:
				if item['values'].get('default') and item['values']['default'].get('ref_docname'):
					item1 = {}
					variant_name = get_or_create_variant(item_name, item_attributes)
					doctype = item['values']['default'].get('ref_doctype')
					docname = item['values']['default'].get('ref_docname')
					received = item['values']['default'].get('received', 0)
					total_quantity, pending_qty = frappe.get_value(doctype, docname, ["qty","pending_quantity"])
					x = total_quantity / 100
					x = x * allowance
					max_qty = total_quantity + x
					before_received = total_quantity - pending_qty
					if max_qty - before_received < received:
						frappe.throw(f"Received more than the allowed quantity for {bold(variant_name)}")

					item1['item_variant'] = variant_name
					item1['lot'] = item.get('lot')
					item1['quantity'] = received
					item1['received_types'] = item['values']['default'].get('types')
					item1['secondary_qty_json'] = item['values']['default'].get('secondary_qty_json')
					item1['uom'] = item.get('default_uom')
					item1['secondary_qty'] = item['values']['default'].get('secondary_received')
					item1['secondary_uom'] = item.get('secondary_uom')
					item1['rate'] = item['values']['default'].get('rate')
					item1['tax'] = item['values']['default'].get('tax')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments')
					item1['ref_doctype'] = doctype
					item1['ref_docname'] = docname
					item1['set_combination'] = item['values']['default'].get('set_combination', {})
					items.append(item1)
					if received:
						total_qty = total_qty + received
						total_rate = total_rate + (received * item['values']['default'].get('rate'))	
			row_index += 1
	return items, total_rate, total_qty

def save_grn_packing_item_details(item_details, lot):
	item_details = update_if_string_instance(item_details)
	items = []
	itemname, ipd, uom = frappe.get_value("Lot", lot, ["item", "production_detail", "uom"])
	primary, dependent = frappe.get_value("Item Production Detail", ipd, ["primary_item_attribute", "dependent_attribute"])
	total_qty = 0
	default_received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	for item in item_details:
		variant = get_or_create_variant(itemname, {dependent: "Loose Piece",primary: item})
		item1 = {}
		item1['item_variant'] = variant
		item1['lot'] = lot
		item1['quantity'] = item_details[item]
		item1['received_types'] = {default_received_type: item_details[item]}
		item1['secondary_qty_json'] = {}
		item1['uom'] = uom
		item1['secondary_qty'] = None
		item1['secondary_uom'] = None
		item1['rate'] = 0
		item1['tax'] = 0
		item1['table_index'] = 0
		item1['row_index'] = 0
		item1['comments'] = None
		item1['ref_doctype'] = None
		item1['ref_docname'] = None
		item1['set_combination'] = {}
		total_qty += item1['quantity']
		items.append(item1)
	return items, total_qty

def validate_quantity_tolerance(item_variant, total_qty, pending_qty, received_qty):
	item = frappe.get_value("Item Variant", item_variant, "item")
	# tolerance percentage
	tolerance_percentage = frappe.get_value("Item", item, "over_delivery_receipt_allowance") or 0
	tolerance = total_qty * (tolerance_percentage / 100)
	# Check if the tolerance is exceeded
	if (received_qty - pending_qty) > tolerance:
		frappe.throw(_("Quantity tolerance exceeded for item {0}. Received Quantity must not exceed {1}").format(item, pending_qty + tolerance))
	return True

def fetch_grn_item_details(items, ipd, lot, docstatus = 0):	
	if isinstance(items, string_types):
		items = json.loads(items)
	else:	
		items = [item.as_dict() for item in items]
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	item_details = []
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			"item_keys": {},
			"is_set_item": ipd_doc.is_set_item,
			"set_attr": ipd_doc.set_item_attribute,
			"pack_attr": ipd_doc.packing_attribute,
			"major_attr_value": ipd_doc.major_attribute_value,
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			'values': {},
			'types':[],
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0, "types": {}}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				set_combination = update_if_string_instance(variant.get('set_combination', {}))
				if set_combination:
					if set_combination.get("major_part"):
						item['item_keys']['major_part'] = set_combination.get("major_part")

					if set_combination.get("major_colour"):
						item['item_keys']['major_colour'] = set_combination.get("major_colour")		

				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'primary_attr': attr.attribute_value,
							'secondary_uom':variant['secondary_uom'],
							'secondary_qty': variant['secondary_qty'],
							'rate': variant['rate'],
							'tax': variant['tax'],
							'types': variant['received_types'] if variant['received_types'] else {},
							'secondary_qty_json': variant['secondary_qty_json'] if variant['secondary_qty_json'] else {},
							'set_combination': variant.get('set_combination', {})
						}
						x = item['values'][attr.attribute_value]['types']
						if x:
							x = update_if_string_instance(x)

						for t, qty in x.items():
							if t not in item['types']:
								item['types'].append(t)

						qty = frappe.get_value(variant['ref_doctype'], variant['ref_docname'], "pending_quantity")
						if docstatus == 0:
							item['values'][attr.attribute_value]['qty'] = round(qty - variant['quantity'], 3) 
						else:
							item['values'][attr.attribute_value]['qty'] = qty
						item['values'][attr.attribute_value]['received'] = round(variant['quantity'], 3)
						item['values'][attr.attribute_value]['ref_doctype'] = variant['ref_doctype']
						item['values'][attr.attribute_value]['ref_docname'] = variant['ref_docname']
						break
		else:
			item['values']['default'] = {
				'secondary_qty': variants[0]['secondary_qty'],
				'secondary_uom': variants[0]['secondary_uom'],
				'rate': variants[0]['rate'],
				'tax': variants[0]['tax'],
				'types': variants[0]['received_types'] if variants[0]['received_types'] else {},
				'secondary_qty_json': variants[0]['secondary_qty_json'] if variants[0]['secondary_qty_json'] else {},
				'set_combination': variants[0].get('set_combination', {})
			}
			x = item['values']['default']['types']
			if x:
				x = update_if_string_instance(x)

			for t, qty in x.items():
				if t not in item['types']:
					item['types'].append(t)

			qty = frappe.get_value( variants[0]['ref_doctype'], variants[0]['ref_docname'], "pending_quantity")
			if docstatus == 0:
				item['values']['default']['qty'] = round(qty - variants[0]['quantity'], 3) 
			else:
				item['values']["default"]['qty'] = qty
			item['values']['default']['received'] = round(variants[0]['quantity'], 3)
			item['values']['default']['ref_doctype'] = variants[0]['ref_doctype']
			item['values']['default']['ref_docname'] = variants[0]['ref_docname']
		
		index = -1
		if item_details:
			index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				"lot":lot,
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				'dependent_attribute': current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				"is_set_item": ipd_doc.is_set_item,
				"set_attr": ipd_doc.set_item_attribute,
				"pack_attr": ipd_doc.packing_attribute,
				"major_attr_value": ipd_doc.major_attribute_value,
				'items': [item],
				"types": item['types'],
			})
		else:
			item_details[index]['items'].append(item)	
	for item in item_details:
		table_total = 0
		size_wise_total = {}
		for row_item in item['items']:
			total_json = {}
			for key in row_item['values']:
				types_json = update_if_string_instance(row_item['values'][key]["types"])
				for type in row_item['types']:
					if types_json.get(type):
						total_json.setdefault(type, 0)
						size_wise_total.setdefault(key, 0)
						size_wise_total[key] += types_json.get(type)
						table_total += types_json.get(type)
						total_json[type] += types_json.get(type)
			row_item['total_qty'] = total_json
		item['total_sum'] = table_total
		item['size_wise_total'] = size_wise_total
	return item_details

def fetch_grn_packing_items(items):
	items = [item.as_dict() for item in items]
	box_qty = {}
	for row in items:
		current_variant = frappe.get_cached_doc("Item Variant", row['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		primary_attribute = current_item_attribute_details['primary_attribute']
		for attr in current_variant.attributes:
			if attr.attribute == primary_attribute:
				box_qty.setdefault(attr.attribute_value, 0)
				box_qty[attr.attribute_value] += row['quantity']
				break	
	return box_qty

def fetch_grn_purchase_item_details(items, docstatus=0):
	items = [item.as_dict() for item in items]
	if docstatus != 0:
		items = [item for item in items if item.get('quantity') > 0]
	item_details = []
	items = sorted(items, key = lambda i: i['row_index'])
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			'values': {},
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'received': variant.quantity,
							'secondary_received': variant.secondary_qty,
							'rate': variant.rate,
							'tax': variant.tax,
						}
						if docstatus == 0:
							doc = frappe.get_cached_doc("Purchase Order Item", variant.ref_docname)
							item['values'][attr.attribute_value]['qty'] = doc.qty
							item['values'][attr.attribute_value]['secondary_qty'] = doc.secondary_qty
							item['values'][attr.attribute_value]['pending_qty'] = doc.pending_qty
							item['values'][attr.attribute_value]['ref_doctype'] = variant.ref_doctype
							item['values'][attr.attribute_value]['ref_docname'] = variant.ref_docname
						break
		else:
			item['values']['default'] = {
				'received': variants[0].quantity,
				'secondary_received': variants[0].secondary_qty,
				'rate': variants[0].rate,
				'tax': variants[0].tax
			}
			if docstatus == 0:
				doc = frappe.get_cached_doc("Purchase Order Item", variants[0].ref_docname)
				item['values']['default']['qty'] = doc.qty
				item['values']['default']['secondary_qty'] = doc.secondary_qty
				item['values']['default']['pending_qty'] = doc.pending_qty
				item['values']['default']['ref_doctype'] = variants[0].ref_doctype
				item['values']['default']['ref_docname'] = variants[0].ref_docname
		index = -1
		if item_details:
			index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return item_details

def fetch_grn_return_item(items):
	items = [item.as_dict() for item in items]
	item_details = []
	items = sorted(items, key = lambda i: i['table_index'])
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			'values': {},
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
			"received_type": variants[0]['received_type'],
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'received': variant.quantity,
							'secondary_received': variant.secondary_qty,
							'rate': variant.rate,
							'tax': variant.tax,
						}
						item['values'][attr.attribute_value]['qty'] = variant.quantity
						item['values'][attr.attribute_value]['ref_doctype'] = variant.ref_doctype
						item['values'][attr.attribute_value]['ref_docname'] = variant.ref_docname
						break
		else:
			item['values']['default'] = {
				'received': variants[0].quantity,
				'secondary_received': variants[0].secondary_qty,
				'rate': variants[0].rate,
				'tax': variants[0].tax
			}
			item['values']['default']['qty'] = variants[0].quantity
			item['values']['default']['ref_doctype'] = variants[0].ref_doctype
			item['values']['default']['ref_docname'] = variants[0].ref_docname
		index = -1
		if item_details:
			index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				"dependent_attribute": current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return item_details


@frappe.whitelist()
def calculate_deliverables(grn_doc):
	wo_doc = frappe.get_cached_doc("Work Order", grn_doc.against_id)
	ipd_doc = frappe.get_cached_doc("Item Production Detail",wo_doc.production_detail)
	process = wo_doc.process_name
	final_value = {}
	if process == ipd_doc.stiching_process:
		final_value = get_stiching_process_deliverables(grn_doc, wo_doc, ipd_doc)
	elif process == ipd_doc.cutting_process:
		final_value = get_cutting_process_deliverables(grn_doc,ipd_doc)
	else:
		final_value = get_other_deliverables(grn_doc, wo_doc)
	return final_value	

def get_other_deliverables(grn_doc, wo_doc):
	process = wo_doc.process_name
	final_value = []
	is_group = frappe.get_value("Process",process,"is_group")
	if not is_group:
		for item in grn_doc.items:
			if item.quantity <= 0:
				continue
			final_value.append({
				"item_variant": item.item_variant,
				"qty": item.quantity,
				"uom":item.uom,
				"set_combination": item.set_combination,
			})
		return final_value
	else:
		return []

def get_cutting_process_deliverables(grn_doc, ipd_doc):
	final_value = {}
	cloth_combination = get_cloth_combination(ipd_doc)
	panel_qty = 0
	for i in ipd_doc.stiching_item_details:
		panel_qty += i.quantity

	cloth_detail = {}
	for cloth in ipd_doc.cloth_detail:
		cloth_detail[cloth.name1] = cloth.cloth
	item_attr_detail_dict = {}
	cloths = {}
	stich_details = {}
	if ipd_doc.is_set_item:
		stich_details = get_stich_details(ipd_doc)

	accessory_json = update_if_string_instance(ipd_doc.accessory_clothtype_json)

	for item in grn_doc.items:
		if not item.quantity > 0:
			continue
		variant_doc = frappe.get_cached_doc("Item Variant", item.item_variant)	
		item_attribute_details = None
		if item_attr_detail_dict.get(variant_doc.item):
			item_attribute_details = item_attr_detail_dict[variant_doc.item]
		else:
			item_attribute_details = get_attribute_details(variant_doc.item)
			item_attr_detail_dict[variant_doc.item] = item_attribute_details
		attributes = get_receivable_item_attribute_details(variant_doc, item_attribute_details, ipd_doc.stiching_in_stage)
		if ipd_doc.is_set_item and not attributes.get(ipd_doc.set_item_attribute):
			attributes[ipd_doc.set_item_attribute] = stich_details[attributes[ipd_doc.stiching_attribute]]
		cut_attr_key = get_key(attributes, cloth_combination["cutting_attributes"])
		dia, cloth_weight = cloth_combination["cutting_combination"].get(cut_attr_key)
		cloth_attr_key = get_key(attributes, cloth_combination["cloth_attributes"])
		cloth_type = cloth_combination["cloth_combination"].get(cloth_attr_key)
		if ipd_doc.stiching_attribute not in cloth_combination['cutting_attributes']:
			cloth_weight = cloth_weight / panel_qty
		cloth_name = cloth_detail[cloth_type]
		cloth_weight = cloth_weight * item.quantity
		t = (cloth_name,attributes[ipd_doc.packing_attribute],dia)
		if cloths.get(t):
			cloths[t] += cloth_weight
		else:
			cloths[t] = cloth_weight

		for accessory_name, accessory_cloth in accessory_json.items():
			attributes["Accessory"] = accessory_name
			acc_attr_key = get_key(attributes, cloth_combination["accessory_attributes"])
			if cloth_combination["accessory_combination"].get(acc_attr_key):
				dia, accessory_weight = cloth_combination["accessory_combination"][acc_attr_key]
				if ipd_doc.stiching_attribute not in cloth_combination["accessory_attributes"]:
					accessory_weight = accessory_weight / panel_qty
				accessory_weight = accessory_weight * item.quantity
				accessory_colour, cloth = get_accessory_colour(ipd_doc,attributes,accessory_name)
				t = (cloth_detail[cloth],accessory_colour, dia)
				if cloths.get(t):
					cloths[t] += accessory_weight
				else:
					cloths[t] = accessory_weight

	for cloth, weight in cloths.items():
		name, colour, dia = cloth
		attributes = {ipd_doc.packing_attribute:colour,"Dia":dia}
		item_name = name
		new_variant = get_or_create_variant(item_name, attributes)
		uom = frappe.get_cached_value("Item",name,"default_unit_of_measure")
		if final_value.get(new_variant):
			final_value[new_variant]['qty'] += weight
		else:
			final_value[new_variant] = {"qty":weight,"uom": uom}	

	final_list = []
	for variant, attr in final_value.items():
		final_list.append({
			"item_variant": variant,
			"quantity": attr['qty'],
			"uom": attr['uom'],
			"set_combination": {},
		})	
	return final_list

def item_attribute_details(variant, item_attributes):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute != item_attributes['dependent_attribute']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

def get_stiching_process_deliverables(grn_doc, wo_doc, ipd_doc):
	lot_doc = frappe.get_cached_doc("Lot", wo_doc.lot)
	ipd = lot_doc.production_detail
	process = wo_doc.process_name
	final_value = []
	items = []
	for item in grn_doc.items:
		if item.quantity <= 0:
			continue
		items.append({
			"item_variant":item.item_variant,
			"quantity":item.quantity,
			"row_index":item.row_index,
			"table_index":item.table_index,
			"set_combination": item.set_combination,
		})
	if not items:
		return	
	variant_doc = frappe.get_cached_doc("Item Variant", items[0]['item_variant'])		
	uom = lot_doc.packing_uom
	item_list, row_index, table_index = get_item_structure(items, variant_doc.item, process, uom)	
	bom = get_calculated_bom(lot_doc.production_detail, items, lot_doc.name, process_name=process,doctype="Work Order")	
	bom = get_bom_structure(bom, row_index, table_index)
	attributes = get_attributes(item_list,variant_doc.item,ipd_doc.stiching_in_stage,ipd_doc.dependent_attribute,ipd)
	attributes.update(bom)
	for item, variants in attributes.items():
		for variant_details in variants:
			variant = variant_details['item_variant']
			qty = variant_details['qty']
			uom = variant_details['uom']
			set_combination = variant_details.get('set_combination', {})
			final_value.append({
				"item_variant":variant,
				"qty": qty,
				"uom": uom,
				"set_combination": set_combination,
			})
	return final_value

def get_packing_process_deliverables(grn_doc):
	default_received_type = frappe.get_single("Stock Settings").default_received_type
	ipd, item = frappe.get_value("Lot", grn_doc.lot, ["production_detail","item"])
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	lot_doc = frappe.get_doc("Lot", grn_doc.lot)
	deliverables = []
	total_box_quantity = 0
	packing_combo = ipd_doc.packing_combo
	lot_item_detail = frappe.get_cached_doc("Item", item)
	for item in grn_doc.items:
		rate = get_stock_balance(
			item.item_variant, None, default_received_type, posting_date=grn_doc.posting_date, 
				posting_time=grn_doc.posting_time, with_valuation_rate=True, uom=item.uom,
		)[1]
		stock = get_stock_balance(
			item.item_variant, None, default_received_type, posting_date=grn_doc.posting_date, 
				posting_time=grn_doc.posting_time, with_valuation_rate=False, uom=item.uom,
		)
		total_box_quantity += item.quantity
		deliverables.append({
			"item_variant": item.item_variant,
			"quantity": item.stock_qty,
			"uom": item.stock_uom,
			"valuation_rate": rate,
			"set_combination": item.set_combination,
			"stock": stock
		})

	total_piece_qty = total_box_quantity * packing_combo
	prs_doc = frappe.get_doc("Process", grn_doc.process_name)	
	bom_items = {}
	if prs_doc.is_group:
		for process in prs_doc.process_details:
			for bom_item in ipd_doc.item_bom:
				if bom_item.process_name == process.process_name and not bom_item.based_on_attribute_mapping:
					quantity, uom = get_bom(bom_item, total_piece_qty, lot_item_detail, lot_doc, ipd_doc, packing_combo)
					bom_items.setdefault(bom_item.item, {
						"qty": 0,
						"uom": uom
					})
					bom_items[bom_item.item]["qty"] += math.ceil(quantity)
	else:		
		for bom in ipd_doc.bom:
			if bom.process_name == grn_doc.process_name and not bom.based_on_attribute_mapping:
				quantity, uom = get_bom(bom_item, total_piece_qty, lot_item_detail, lot_doc, ipd_doc, packing_combo)
				bom_items.setdefault(bom_item.item, {
					"qty": 0,
					"uom": uom
				})
				bom_items[bom_item.item]["qty"] += math.ceil(quantity)

	for bom in bom_items:
		rate = get_stock_balance(
			bom, None, default_received_type, posting_date=grn_doc.posting_date, posting_time=grn_doc.posting_time, 
			with_valuation_rate=True, uom=bom_items[bom]['uom'],
		)[1]
		deliverables.append({
			"item_variant": bom,
			"quantity": bom_items[bom]['qty'],
			"uom": bom_items[bom]['uom'],
			"valuation_rate": rate,
			"set_combination": {},
			"stock": 0,
		})
	item_name = frappe.get_value(grn_doc.against, grn_doc.against_id, "item")
	excess_items = {}
	for d in deliverables:
		if d['quantity'] > d['stock']:
			item = frappe.get_value("Item Variant", d['item_variant'], "item")
			if item == item_name:
				excess_items.setdefault(d['item_variant'], {
					"qty": 0,
					"uom": d['uom'],
					"rate": d['valuation_rate'],
				})
				excess_items[d['item_variant']]['qty'] += d['quantity'] - d['stock']
				d['quantity'] -= (d['quantity'] - d['stock'])
	
	excess_items_list = []
	default_received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	for d in excess_items:			
		excess_items_list.append({
			"item_variant": d,
			"excess_quantity": excess_items[d]['qty'],
			"uom": excess_items[d]['uom'],
			"rate": excess_items[d]['rate'],
		})
	return deliverables, excess_items_list

def get_bom(bom_item, total_piece_qty, lot_item_detail, lot_doc, ipd_doc, packing_combo):
	from production_api.essdee_production.doctype.lot.lot import get_uom_conversion_factor
	qty_of_product = bom_item.qty_of_product
	qty_of_bom = bom_item.qty_of_bom_item
	temp_qty = total_piece_qty
	if bom_item.dependent_attribute_value and bom_item.dependent_attribute_value != lot_doc.pack_in_stage:
		dependent_attr_uom = lot_item_detail.default_unit_of_measure
		qty_of_product = get_uom_conversion_factor(lot_item_detail.uom_conversion_details, dependent_attr_uom, lot_doc.packing_uom)
		if bom_item.dependent_attribute_value == lot_doc.pack_out_stage:
			if ipd_doc.is_set_item:
				temp_qty = temp_qty / 2
			qty_of_product = qty_of_product * packing_combo

	qty_of_product = qty_of_product/qty_of_bom
	uom = frappe.get_value("Item", bom_item.item, "default_unit_of_measure")
	quantity = temp_qty / qty_of_product

	return quantity, uom

def get_accessory_colour(ipd_doc,variant_attrs,accessory):
	for acce in json.loads(ipd_doc.stiching_accessory_json)["items"]:
		if acce['major_attr_value'] == variant_attrs[ipd_doc.packing_attribute]:
			return acce['accessories'][accessory]["colour"],acce['accessories'][accessory]["cloth_type"] 
		
def get_item_structure(items,item_name, process, uom):
	item_list = {
		item_name: {}
	}
	row_index = 0
	table_index = 0
	for item in items:
		row_index = item['row_index']
		table_index = item['table_index']
		item_list[item_name][item['item_variant']] = {
			"qty":item['quantity'],
			"process":process,
			"uom":uom,
			"row_index":row_index,
			"table_index":table_index,
			"set_combination": item['set_combination']
		}
	return item_list, row_index, table_index

def get_attributes(items, itemname, stage, dependent_attribute, ipd):
	item_list = {
		itemname: []
	}
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	panel_colour_comb = get_panel_colour(ipd_doc)
	for item_name,variants in items.items():
		item_attribute_details = get_attribute_details(item_name)
		for variant, details in variants.items():
			current_variant = frappe.get_cached_doc("Item Variant", variant)
			attributes = get_receivable_item_attribute_details(current_variant, item_attribute_details, stage)

			if item_attribute_details['dependent_attribute']:
				attributes[dependent_attribute] = stage
			itemname = current_variant.item
			set_item_stitching_attrs = {}
			if ipd_doc.is_set_item:
				part = None
				for attr in current_variant.attributes:
					if attr.attribute == ipd_doc.set_item_attribute:
						part = attr.attribute_value
						break
				set_item_stitching_attrs = get_stich_details(ipd_doc)
				variant_colour = attributes[ipd_doc.packing_attribute]
				for id, item in enumerate(ipd_doc.stiching_item_details):
					attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value
					v = True
					panel_part = set_item_stitching_attrs[item.stiching_attribute_value]
					if panel_part != part:
						v = False							
					if v:
						attributes[ipd_doc.packing_attribute] = panel_colour_comb[part][variant_colour][item.stiching_attribute_value]
						new_variant = get_or_create_variant(itemname, attributes)
						item_list[itemname].append({
							"item_variant": new_variant,
							'qty': details['qty']*item.quantity,
							'uom':details['uom'],
							'set_combination': details['set_combination']
						})
			else:
				variant_colour = attributes[ipd_doc.packing_attribute]
				for id,item in enumerate(ipd_doc.stiching_item_details):
					attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value
					attributes[ipd_doc.packing_attribute] = panel_colour_comb[variant_colour][item.stiching_attribute_value]
					new_variant = get_or_create_variant(itemname, attributes)
					item_list[itemname].append({
						"item_variant": new_variant,
						'qty': details['qty']*item.quantity,
						'uom':details['uom'],
						'set_combination': details['set_combination']
					})
	return item_list

def get_panel_colour(ipd_doc):
	d = {}
	if ipd_doc.is_set_item:
		stich_panel_set_comb = get_stich_details(ipd_doc)
		for row in ipd_doc.stiching_item_combination_details:
			part = stich_panel_set_comb[row.set_item_attribute_value]
			d.setdefault(part, {})
			d[part].setdefault(row.major_attribute_value, {})
			d[part][row.major_attribute_value].setdefault(row.set_item_attribute_value, row.attribute_value)
	else:
		for row in ipd_doc.stiching_item_combination_details:
			d.setdefault(row.major_attribute_value, {})
			d[row.major_attribute_value].setdefault(row.set_item_attribute_value, row.attribute_value)
	return d

def get_receivable_item_attribute_details(variant, item_attributes, stage):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute in item_attributes['dependent_attribute_details']['attr_list'][stage]['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

def get_key(item, attrs):
	key = []
	for attr in attrs:
		if item.get(attr):
			key.append(item[attr])
	return tuple(key)	

@frappe.whitelist()
def get_grn_structure(doc_name):
	doc = frappe.get_doc("Goods Received Note", doc_name)
	ipd = frappe.get_cached_value("Work Order", doc.against_id, "production_detail")
	item_details = fetch_grn_item_details(doc.items_json, ipd, doc.lot)
	return item_details

@frappe.whitelist()
def update_calculated_receivables(doc_name, receivables, received_type):
	receivables = update_if_string_instance(receivables)
	grn_doc = frappe.get_doc("Goods Received Note", doc_name)
	total_qty = 0
	total_cost = 0
	default_received = frappe.db.get_single_value("Stock Settings", "default_received_type")
	for received_item in receivables:
		for item in grn_doc.items:
			set1 = update_if_string_instance(received_item.get('set_combination', {}))
			set2 = update_if_string_instance(item.set_combination)
			if received_item['item_variant'] == item.item_variant and set1 == set2:
				received_types = update_if_string_instance(item.received_types)
				secondary_qty_json = update_if_string_instance(item.secondary_qty_json)
				rec_type = received_type	
				if received_item.get('is_accessory'):
					rec_type = default_received	
					if received_types.get(rec_type):
						received_types[rec_type] += received_item['qty']
						item.quantity += received_item['qty']
						item.received_types = received_types
					else:
						secondary_qty_json[rec_type] = 0
						item.secondary_qty_json = secondary_qty_json
						received_types[rec_type] = received_item['qty']
						item.quantity += received_item['qty']
						item.received_types = received_types
				else:	
					if received_types.get(rec_type):
						item.quantity -= received_types.get(rec_type)
						received_types[rec_type] = received_item['qty']
						item.quantity += received_item['qty']
						item.received_types = received_types
					else:
						secondary_qty_json[rec_type] = 0
						item.secondary_qty_json = secondary_qty_json
						received_types[rec_type] = received_item['qty']
						item.quantity += received_item['qty']
						item.received_types = received_types
				total_cost += (item.rate * received_item['qty'])
				total_qty += item.quantity
				break	
	grn_doc.total_received_quantity = total_qty	
	grn_doc.total_receivable_cost = total_cost
	grn_doc.save()
	if not grn_doc.is_manual_entry and not grn_doc.additional_grn and not grn_doc.is_rework:
		wo_doc = frappe.get_cached_doc(grn_doc.against, grn_doc.against_id)
		wo_deliverables = {}
		for row in wo_doc.deliverables:
			wo_deliverables[row.item_variant] = row.valuation_rate

		deliverables = calculate_deliverables(grn_doc)
		items = []
		for row in deliverables:
			check = True
			x = wo_deliverables.get(row['item_variant'])
			if x == flt(0):
				check = True
			elif not x:
				check = False
			if check:	
				items.append({
					"item_variant": row['item_variant'],
					"quantity": row['qty'],
					"uom": row['uom'],
					"valuation_rate": wo_deliverables[row['item_variant']],
					"set_combination": row['set_combination'],
				})
		grn_doc.set("grn_deliverables", items)
		grn_doc.save()

@frappe.whitelist()
def get_receivables(items,doc_name, wo_name,receivable):
	from production_api.production_api.doctype.work_order.work_order import get_deliverable_receivable
	logger = get_module_logger("goods_received_note")
	logger.debug(f"{doc_name} Deliverables Calculation Started {datetime.now()}")
	items = get_deliverable_receivable(items, wo_name, receivable=receivable)
	logger.debug(f"{doc_name} Deliverables Calculation Completed {datetime.now()}")
	return items

@frappe.whitelist()
def construct_stock_entry_data(doc_name):
	import random
	doc = frappe.get_doc("Goods Received Note", doc_name)
	stock_settings = frappe.get_single("Stock Settings")
	items = []
	received_types = {}
	for item in doc.items:
		if item.quantity - item.ste_delivered_quantity > 0:
			if item.received_type not in received_types:
				index = random.randint(11,99)
				received_types[item.received_type] = index
				index = index + item.row_index
			else:
				index = received_types[item.received_type] + item.row_index
			items.append({
				"item": item.item_variant,
				"lot": item.lot,
				"qty": item.quantity - item.ste_delivered_quantity ,
				"uom": item.uom,
				"received_type": item.received_type,
				"secondary_qty":item.secondary_qty,
				"secondary_uom":item.secondary_uom,
				"against_id_detail": item.name,
				"table_index": 0,
				"row_index": index,
				"remarks": item.comments,
				"set_combination": item.set_combination
			})
	ste = frappe.new_doc("Stock Entry")
	ste.purpose = "GRN Completion"
	ste.against = "Goods Received Note"
	ste.cut_panel_movement = doc.cut_panel_movement
	ste.against_id = doc_name
	ste.from_warehouse = doc.supplier
	ste.to_warehouse = doc.delivery_location
	ste.set("items", items)
	ste.flags.allow_from_grn = True
	ste.save()
	return ste.name

@frappe.whitelist()
def calculate_pieces(doc_name):
	grn_doc = frappe.get_doc("Goods Received Note",doc_name)
	doc_status = grn_doc.docstatus
	if doc_status == 2:
		from production_api.production_api.doctype.work_order.work_order import calculate_completed_pieces
		calculate_completed_pieces(grn_doc.against_id)
		return
	ipd = frappe.get_cached_value("Lot", grn_doc.lot,"production_detail")
	ipd_doc = frappe.get_cached_doc("Item Production Detail",ipd)
	received_types = {}
	total_received = 0
	incomplete_items = {}
	completed_items = {}
	process_name = grn_doc.process_name
	prs_doc = frappe.get_cached_doc("Process", process_name)
	final_calculation = []
	if prs_doc.is_group:
		for detail in prs_doc.process_details:
			process_name = detail.process_name

	if process_name == ipd_doc.cutting_process:
		panel_list = get_panel_list(ipd_doc)
		incomplete_items, completed_items, received_types, total_received, qty_list = calculate_cutting_piece(grn_doc, received_types, panel_list)
	elif process_name == ipd_doc.stiching_process:
		final_calculation, received_types, total_received = calculate_piece_stage(grn_doc, received_types, doc_status, total_received, final_calculation)

	elif process_name == ipd_doc.packing_process:
		final_calculation, received_types, total_received = calculate_pack_stage(ipd_doc, grn_doc, received_types, doc_status, total_received, final_calculation)
	else:
		emb = update_if_string_instance(ipd_doc.get("emblishment_details_json"))
		stage = None
		for process in ipd_doc.ipd_processes:
			if process.process_name == process_name:
				stage = process.stage
				break
		
		panel_list = None
		if emb and emb.get(process_name):
			if stage == ipd_doc.stiching_in_stage:
				panel_list = emb.get(process_name)

		if stage:
			if stage == ipd_doc.pack_in_stage:
				final_calculation, received_types, total_received = calculate_piece_stage(grn_doc, received_types, doc_status, total_received, final_calculation)

			elif stage == ipd_doc.pack_out_stage:
				final_calculation, received_types, total_received = calculate_pack_stage(ipd_doc, grn_doc, received_types, doc_status, total_received, final_calculation)

			elif stage == ipd_doc.stiching_in_stage:
				if not panel_list:	
					panel_list = get_panel_list(ipd_doc)
					incomplete_items, completed_items, received_types, total_received, qty_list = calculate_cutting_piece(grn_doc, received_types, panel_list)
				elif panel_list:
					incomplete_items, completed_items, received_types, total_received, qty_list = calculate_cutting_piece(grn_doc, received_types, panel_list)
				else:
					return

	wo_doc = frappe.get_doc("Work Order", grn_doc.against_id)
	if not wo_doc.first_grn_date:
		wo_doc.first_grn_date = grn_doc.posting_date
		wo_doc.last_grn_date = grn_doc.posting_date
	else:
		wo_doc.last_grn_date = grn_doc.posting_date
	wo_doc.end_date = grn_doc.posting_date	

	wo_doc.total_no_of_pieces_received += total_received
	received_json = update_if_string_instance(wo_doc.received_types_json)	
	for type, qty in received_types.items():
		if received_json.get(type):
			received_json[type] += qty
		else:
			received_json[type] = qty

	wo_doc.received_types_json = received_json
	field = None
	lot_doc = None
	if process_name in [ipd_doc.cutting_process, ipd_doc.stiching_process, ipd_doc.packing_process]:
		lot_doc = frappe.get_cached_doc("Lot",wo_doc.lot)
		field = "cut_qty" if process_name == ipd_doc.cutting_process else "stich_qty" if process_name == ipd_doc.stiching_process else "pack_qty"

	if incomplete_items:
		wo_doc.incompleted_items_json = incomplete_items
		wo_doc.completed_items_json = completed_items
		for qty_data in qty_list:
			for item in wo_doc.work_order_calculated_items:
				set_combination = update_if_string_instance(item.set_combination)
				if item.item_variant == qty_data['item_variant'] and set_combination == qty_data['set_combination']:
					qty = qty_data['quantity']
					if doc_status == 2:
						qty = qty * -1
					item.received_qty += qty
					wo_types = update_if_string_instance(item.received_type_json)
					if wo_types.get(type):
						wo_types[qty_data['type']] += qty
					else:
						wo_types[qty_data['type']] = qty		
					item.received_type_json = wo_types
					break 
			if lot_doc:
				for item in lot_doc.lot_order_details:
					set_combination = update_if_string_instance(item.set_combination)
					if item.item_variant == qty_data['item_variant'] and set_combination == qty_data['set_combination']:
						qty = qty_data['quantity']
						if doc_status == 2:
							qty = qty * -1
						current_qty = getattr(item, "cut_qty", 0)
						setattr(item, "cut_qty", current_qty + qty)
		if lot_doc:
			lot_doc.save(ignore_permissions=True)	
	else:
		for data in final_calculation:
			for item in wo_doc.work_order_calculated_items:
				set_combination = update_if_string_instance(item.set_combination)
				if item.item_variant == data['item_variant'] and set_combination == data['set_combination']:
					item.received_qty += data['quantity']
					wo_types = update_if_string_instance(item.received_type_json)
					
					if wo_types.get(data['type']):
						wo_types[data['type']] += data['quantity']
					else:
						wo_types[data['type']] = data['quantity']

					item.received_type_json = wo_types
			if lot_doc:
				for item in lot_doc.lot_order_details:
					set_combination = update_if_string_instance(item.set_combination)
					if item.item_variant == data['item_variant'] and set_combination == data['set_combination']:
						qty = data['quantity']
						current_qty = getattr(item, field, 0)
						setattr(item, field, current_qty + qty)	
		if lot_doc:
			lot_doc.save(ignore_permissions=True)
	wo_doc.save(ignore_permissions=True)

def calculate_piece_stage(grn_doc, received_types, doc_status, total_received, final_calculation):
	for item in grn_doc.items:
		if item.quantity <= 0:
			continue
		# final_calculation.setdefault(item.item_variant, {"types": {}, "qty": 0 })
		qty = item.quantity
		if doc_status == 2:
			qty = qty * -1
		set_combination = update_if_string_instance(item.set_combination)
		if item.received_type:
			final_calculation.append({
				"item_variant": item.item_variant,
				"quantity": qty,
				"type":item.received_type,
				"set_combination":set_combination
			})
		received_types.setdefault(item.received_type, 0)
		received_types[item.received_type] += qty
		total_received += qty
	return final_calculation, received_types, total_received

def calculate_pack_stage(ipd_doc, grn_doc, received_types, doc_status, total_received, final_calculation):
	attrs = []
	if ipd_doc.is_set_item:
		for row in ipd_doc.set_item_combination_details:
			attrs.append({
				ipd_doc.packing_attribute: row.attribute_value,
				ipd_doc.set_item_attribute: row.set_item_attribute_value,
				"major_attr_value": row.major_attribute_value,
			})
	else:
		for row in ipd_doc.packing_attribute_details:
			attrs.append({ipd_doc.packing_attribute: row.attribute_value})

	for item in grn_doc.items:
		if item.quantity <= 0:
			continue
		for attr in attrs:
			qty = item.quantity
			if doc_status == 2:
				qty = qty * -1
			variant_doc = frappe.get_cached_doc("Item Variant", item.item_variant)
			variant_attrs = get_variant_attributes(variant_doc)
			major_colour = attr[ipd_doc.packing_attribute]
			if ipd_doc.is_set_item:
				major_colour = attr["major_attr_value"]
				del attr['major_attr_value']
			variant_attrs.update(attr)
			item_name = variant_doc.item
			variant_attrs[ipd_doc.dependent_attribute] = ipd_doc.pack_in_stage
			new_variant = get_or_create_variant(item_name, variant_attrs)
			set_combination = {
				"major_colour": major_colour
			}
			if ipd_doc.is_set_item:
				set_combination["major_part"] = ipd_doc.major_attribute_value

			final_calculation.append({
				"item_variant": new_variant,
				"quantity": qty,
				"type":item.received_type,
				"set_combination":set_combination
			})

			received_types.setdefault(item.received_type, 0)
			received_types[item.received_type] += qty
			total_received += qty

	return final_calculation, received_types, total_received		

def calculate_cutting_piece(grn_doc, received_types, panel_list):
	panel_list = update_if_string_instance(panel_list)		
	production_detail, incomplete_items_json, completed_items_json = frappe.get_value("Work Order", grn_doc.against_id,['production_detail',"incompleted_items_json","completed_items_json"])
	ipd_doc = frappe.get_cached_doc("Item Production Detail",production_detail)
	incomplete_items = json.loads(incomplete_items_json)
	completed_items = json.loads(completed_items_json)
	panel_qty = {}
	set_comb = {}
	for row in ipd_doc.stiching_item_details:
		if ipd_doc.is_set_item:
			set_comb[row.stiching_attribute_value] = row.set_item_attribute_value
		panel_qty[row.stiching_attribute_value] = row.quantity

	types = []
	for item in grn_doc.items:
		if item.quantity <= 0:
			continue
		variant = frappe.get_cached_doc("Item Variant", item.item_variant)
		attrs = get_variant_attributes(variant)
		if not attrs.get(ipd_doc.stiching_attribute):
			continue
		set_combination = update_if_string_instance(item.set_combination)
		for i in incomplete_items['items']:
			con1 = True
			if ipd_doc.is_set_item:
				con1 = i['attributes'][ipd_doc.set_item_attribute] == set_comb[attrs[ipd_doc.stiching_attribute]]
			# con2 = i['attributes'][ipd_doc.packing_attribute] == attrs[ipd_doc.packing_attribute]
			item_keys = update_if_string_instance(i['item_keys'])
			set_combination = update_if_string_instance(item.set_combination)
			con2 = item_keys == set_combination
			if con1 and con2:
				if item.received_type and item.received_type not in types:
					types.append(item.received_type)
				received_types.setdefault(item.received_type, 0)
				primary_attr = attrs[ipd_doc.primary_item_attribute]
				x = i['values'][primary_attr][attrs[ipd_doc.stiching_attribute]]
				y = i.copy()
				if not x:
					i['values'][attrs[ipd_doc.primary_item_attribute]][attrs[ipd_doc.stiching_attribute]] = {item.received_type:item.quantity}
				else:
					m = x.copy()
					if m.get(item.received_type):
						y['values'][attrs[ipd_doc.primary_item_attribute]][attrs[ipd_doc.stiching_attribute]][item.received_type] += item.quantity	
					else:
						y['values'][attrs[ipd_doc.primary_item_attribute]][attrs[ipd_doc.stiching_attribute]][item.received_type] = item.quantity
				i = y
				break

	total_qty = 0
	for ty in types:
		for item1, item2 in zip_longest(completed_items['items'], incomplete_items['items']):
			for size in item2['values']:
				min = sys.maxsize
				for panel in item2['values'][size]:
					if panel in panel_list:
						if item2['values'][size][panel]:
							if item2['values'][size][panel].get(ty):
								if item2['values'][size][panel][ty] < min:
									min = item2['values'][size][panel][ty]
							else:
								min = 0
								break		
						else:
							min = 0
							break
				if min > 0 and min != sys.maxsize:
					if item1['values'][size]:
						if item1['values'][size].get(ty):
							item1['values'][size][ty] += min									
						else:
							item1['values'][size][ty] = min
					else:
						item1['values'][size] = {}
						item1['values'][size] = {ty :min}	
					received_types[ty] += min
					total_qty += min

					for panel in item2['values'][size]:
						if panel in panel_list:
							if item2['values'][size][panel] and ty in item2['values'][size][panel]:
								item2['values'][size][panel][ty] -= (min * panel_qty[panel])

	qty_list = []
	for ty in types:
		for item in completed_items['items']: 
			attrs = item['attributes']
			for val in item['values']:
				attrs[ipd_doc.primary_item_attribute] = val
				if item['values'][val]:
					if item['values'][val].get(ty):
						item_name = item['name']
						variant_name = get_or_create_variant(item_name, attrs)
						qty = item['values'][val][ty]
						set_combination = update_if_string_instance(item['item_keys'])
						qty_list.append({
							"item_variant": variant_name,
							"quantity": qty,
							"type":ty,
							"set_combination":set_combination
						})
						item['values'][val][ty] -= qty
	return incomplete_items, completed_items, received_types, total_qty, qty_list

def get_variant_attributes(variant):
	attribute_details = {}
	for attr in variant.attributes:
		attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

@frappe.whitelist()
def get_primary_values(lot):
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	ipd = frappe.get_cached_value("Lot", lot, "production_detail")
	primary_values = get_ipd_primary_values(ipd)
	return primary_values

def generate_rework(doc_name):
	self = frappe.get_doc("Goods Received Note", doc_name)
	if self.docstatus == 2:
		frappe.db.sql(
			"""
				DELETE FROM `tabGRN Rework Item` WHERE grn_number = %(grn)s
			""", {
				"grn": doc_name
			}
		)
		return
	
	single_doc = frappe.get_single("Stock Settings")
	types = [single_doc.default_received_type, single_doc.default_rejected_type]
	items = update_if_string_instance(self.items_json)
	if self.is_return:
		items = [item.as_dict() for item in self.items]
	for key, variants in groupby(items, lambda i: i['row_index']):
		received_data = {}
		for item in variants:
			if self.is_return:
				if item.received_type in types:
					continue 
				received_data.setdefault(item.received_type, [])
				received_data[item.received_type].append({
					"item_variant": item.item_variant,
					"received_type": item.received_type,
					"quantity": item.quantity,
					"uom": item['stock_uom'],
					"set_combination": frappe.json.dumps(item['set_combination']),
				})
			else:	
				received_types = update_if_string_instance(item['received_types'])
				for rec_type in received_types:
					if rec_type in types:
						continue 
					received_data.setdefault(rec_type, [])
					received_data[rec_type].append({
						"item_variant": item['item_variant'],
						"received_type": rec_type,
						"quantity": received_types[rec_type],
						"uom": item['stock_uom'],
						"set_combination": frappe.json.dumps(item['set_combination']),
					})
		data = []
		for ty in received_data:
			data = data + received_data[ty]
		if data:	
			doc = frappe.new_doc("GRN Rework Item")	
			doc.grn_number = self.name
			doc.warehouse = self.delivery_location
			doc.lot = self.lot
			doc.set('grn_rework_item_details', data)
			doc.save(ignore_permissions=True)

def update_finishing_item_doc(doc_name, finishing_doc_name, update_finishing:bool):
	default_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	default_rejected_type = frappe.db.get_single_value("Stock Settings", "default_rejected_type")

	self = frappe.get_doc("Goods Received Note", doc_name)
	docstatus = self.docstatus
	items = update_if_string_instance(self.items_json)
	if self.is_return:
		items = [item.as_dict() for item in self.items]
	
	if update_finishing and not self.is_return:
		finishing_doc = frappe.get_doc("Finishing Plan", finishing_doc_name)	
		finishing_items = {}
		for row in finishing_doc.finishing_plan_grn_details:
			finishing_items.setdefault(row.item_variant, {
				"quantity": 0,
				"dispatched": 0,
			})
			finishing_items[row.item_variant]['quantity'] += row.quantity
			finishing_items[row.item_variant]['dispatched'] += row.dispatched

		for row in self.items:
			if row.item_variant in finishing_items:
				qty = row.quantity
				if docstatus == 2:
					qty = qty * -1
				finishing_items[row.item_variant]['quantity'] += qty

		finshing_items_list = []
		for variant in finishing_items:
			finshing_items_list.append({
				"item_variant": variant,
				"quantity": finishing_items[variant]['quantity'],
				"dispatched": finishing_items[variant]['dispatched'],
			})
		finishing_doc.set("finishing_plan_grn_details", finshing_items_list)
		grn_list = update_if_string_instance(finishing_doc.grn_list)
		if docstatus == 2:
			del grn_list[doc_name]
		else:
			grn_list[doc_name] = frappe.utils.now_datetime().strftime("%d-%m-%Y %H:%M:%S")
		finishing_doc.grn_list = frappe.json.dumps(grn_list)
		finishing_doc.save()	
		
	elif update_finishing and self.is_return:
		finishing_doc = frappe.get_doc("Finishing Plan", finishing_doc_name)
		finishing_items = get_finishing_plan_dict(finishing_doc)
		finishing_rework_items = {}

		for row in finishing_doc.finishing_plan_reworked_details:
			set_comb = update_if_string_instance(row.set_combination)
			key = (row.item_variant, tuple(sorted(set_comb.items())))
			finishing_rework_items.setdefault(key, {
				"quantity": row.quantity,
				"reworked_quantity": row.reworked_quantity,
				"rejected_qty": row.rejected_qty,
				"set_combination": row.set_combination,
			})	

		for key, variants in groupby(items, lambda i: i['row_index']):
			for item in variants:
				set_comb = update_if_string_instance(item['set_combination'])
				key = (item['item_variant'], tuple(sorted(set_comb.items())))
				if finishing_items.get(key):
					received_types = update_if_string_instance(item['received_types'])
					ty = item['received_type']
					qty = item['quantity']
					rework_qty = item['quantity']
					if docstatus != 2:
						qty =  qty * -1
					else:
						rework_qty = rework_qty * -1	

					if ty != default_type:
						if not finishing_rework_items.get(key):
							finishing_rework_items[key] = {
								"quantity": 0,
								"reworked_quantity": 0,
								"rejected_qty": 0,
								"set_combination": item['set_combination'],
							}
						if ty ==  default_rejected_type:
							finishing_rework_items[key]['quantity'] += rework_qty
							finishing_rework_items[key]['rejected_qty'] += rework_qty
						else:	
							finishing_rework_items[key]['quantity'] += rework_qty

					finishing_items[key]['dc_qty'] += qty
		
		finshing_items_list = get_finishing_plan_list(finishing_items)
		finishing_rework_items_list = []
		for key in finishing_rework_items:
			variant, tuple_attrs = key
			finishing_rework_items_list.append({
				"item_variant": variant,
				"quantity": finishing_rework_items[key]['quantity'],
				"reworked_quantity": finishing_rework_items[key]['reworked_quantity'],
				"rejected_qty": finishing_rework_items[key]['rejected_qty'],
				"set_combination": finishing_rework_items[key]['set_combination'],
			})

		finishing_doc.set("finishing_plan_details", finshing_items_list)
		finishing_doc.set("finishing_plan_reworked_details", finishing_rework_items_list)
		finishing_doc.save()		
	else:		
		finishing_doc = frappe.get_doc("Finishing Plan", finishing_doc_name)
		finishing_items = get_finishing_plan_dict(finishing_doc)
		finishing_rework_items = {}

		for row in finishing_doc.finishing_plan_reworked_details:
			set_comb = update_if_string_instance(row.set_combination)
			key = (row.item_variant, tuple(sorted(set_comb.items())))
			finishing_rework_items.setdefault(key, {
				"quantity": row.quantity,
				"reworked_quantity": row.reworked_quantity,
				"rejected_qty": row.rejected_qty,
				"set_combination": row.set_combination,
			})	

		for key, variants in groupby(items, lambda i: i['row_index']):
			for item in variants:
				set_comb = update_if_string_instance(item['set_combination'])
				key = (item['item_variant'], tuple(sorted(set_comb.items())))
				if finishing_items.get(key):
					received_types = update_if_string_instance(item['received_types'])
					for ty in received_types:
						if ty not in finishing_items[key]['received_types']:
							finishing_items[key]['received_types'][ty] = 0
						qty = received_types[ty]
						if self.is_return or docstatus == 2:
							qty =  qty * -1

						if ty == default_type:
							finishing_items[key]['accepted_qty'] += qty

						if ty != default_type:
							if not finishing_rework_items.get(key):
								finishing_rework_items[key] = {
									"quantity": 0,
									"reworked_quantity": 0,
									"rejected_qty": 0,
									"set_combination": item['set_combination'],
								}
							if ty ==  default_rejected_type:
								finishing_rework_items[key]['quantity'] += qty
								finishing_rework_items[key]['rejected_qty'] += qty
							else:	
								finishing_rework_items[key]['quantity'] += qty

						finishing_items[key]['delivered_quantity'] += qty
						finishing_items[key]['received_types'][ty] += qty	
						
		finshing_items_list = get_finishing_plan_list(finishing_items)
		finishing_rework_items_list = []
		for key in finishing_rework_items:
			variant, tuple_attrs = key
			finishing_rework_items_list.append({
				"item_variant": variant,
				"quantity": finishing_rework_items[key]['quantity'],
				"reworked_quantity": finishing_rework_items[key]['reworked_quantity'],
				"rejected_qty": finishing_rework_items[key]['rejected_qty'],
				"set_combination": finishing_rework_items[key]['set_combination'],
			})

		finishing_doc.set("finishing_plan_details", finshing_items_list)
		finishing_doc.set("finishing_plan_reworked_details", finishing_rework_items_list)
		finishing_doc.save()		