# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import bold
from frappe.model.document import Document
from production_api.mrp_stock.utils import get_stock_balance
from production_api.mrp_stock.stock_ledger import make_sl_entries
from production_api.production_api.doctype.item.item import get_or_create_variant

class RecutandPrintPanel(Document):
	def before_cancel(self):
		cloth = {}
		for item in self.recut_and_print_panel_details:
			key = (item.colour, item.cloth_type, item.dia)
			cloth.setdefault(key,0)
			cloth[key] += item.weight

		cp_doc = frappe.get_doc("Cutting Plan",self.cutting_plan)
		for item in cp_doc.cutting_plan_cloth_details:
			key = (item.colour, item.cloth_type, item.dia)
			if key in cloth:
				item.used_weight -= cloth[key]
				item.balance_weight = item.weight - item.used_weight
		cp_doc.save(ignore_permissions=True)
		
	def on_cancel(self):
		self.ignore_linked_doctypes = ('Stock Ledger Entry', 'Repost Item Valuation')
		items = self.get_sl_entries()
		make_sl_entries(items)	

	def before_submit(self):
		cloth = {}
		for item in self.recut_and_print_panel_details:
			key = (item.colour, item.cloth_type, item.dia)
			cloth.setdefault(key,0)
			cloth[key] += item.weight
	
		cp_doc = frappe.get_doc("Cutting Plan",self.cutting_plan)
		for item in cp_doc.cutting_plan_cloth_details:
			key = (item.colour, item.cloth_type, item.dia)
			if key in cloth:
				item.used_weight += cloth[key]
				item.balance_weight = item.weight - item.used_weight
				if item.balance_weight < 0:
					frappe.throw(f"{bold(item.dia)} {bold(item.colour)}, {bold(item.cloth_type)} was used more than the received weight")
					return
		cp_doc.save(ignore_permissions=True)			

		items = self.get_sl_entries()
		make_sl_entries(items)	

	def get_sl_entries(self):	
		items = []
		for row in self.recut_and_print_panel_details:
			sl_dict = frappe._dict({
				"item": row.item_variant,
				"warehouse": self.supplier,
				"received_type": row.received_type,
				"lot": self.lot,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"voucher_detail_no": row.name,
				"qty": row.weight * -1,
				"uom": row.stock_uom,
				"rate": row.rate,
				"valuation_rate": row.rate,
				"is_cancelled": 1 if self.docstatus == 2 else 0,
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
			})
			items.append(sl_dict)
		return items
		
	def before_validate(self):
		ipd = frappe.get_value("Lot", self.lot, "production_detail")
		pack_attr = frappe.get_value("Item Production Detail", ipd, "packing_attribute")
		cloth_details = frappe.db.sql(
			f"""
				SELECT name1, cloth FROM `tabItem Production Detail Cloth Detail`
				WHERE parent = {frappe.db.escape(ipd)}
			""", as_dict=True
		)
		cloth_dict = {}
		for row in cloth_details:
			cloth_dict[row['name1']] = row['cloth']
		uom_dict = {}
		received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
		for row in self.recut_and_print_panel_details:
			item_name = cloth_dict[row.cloth_type]
			if item_name not in uom_dict:
				uom_dict[item_name] = frappe.get_value("Item", item_name, "default_unit_of_measure")
			row.uom = uom_dict[item_name]	
			row.stock_uom = uom_dict[item_name]
			variant = get_or_create_variant(cloth_dict[row.cloth_type], {
				"Dia": row.dia,
				pack_attr: row.colour,
			})	
			row.item_variant = variant
			row.received_type = received_type
			row.rate = get_stock_balance(
				row.item_variant, None, received_type, posting_date=self.posting_date, 
					posting_time=self.posting_time, with_valuation_rate=True, uom=row.uom,
			)[1]
