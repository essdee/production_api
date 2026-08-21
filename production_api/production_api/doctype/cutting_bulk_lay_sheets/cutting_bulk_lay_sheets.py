# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, nowtime


class CuttingBulkLaySheets(Document):
	def autoname(self):
		self.naming_series = "CBLS-.YY..MM.-.{#####}."

	def before_validate(self):
		self._validate_lot_rows()
		self._save_active_laysheet_editor()
		self.status = get_bulk_status(self.lot_details)

	def onload(self):
		for row in self.lot_details:
			row.status = get_entry_status(row)
		self.status = get_bulk_status(self.lot_details)
		if self.active_cutting_laysheet:
			self.set_onload(
				"active_laysheet",
				get_laysheet_editor_data(self.name, self.active_cutting_laysheet),
			)

	def _validate_lot_rows(self):
		if not self.lot_details:
			frappe.throw(_("Add at least one split Lot."))

		existing_rows = {}
		if not self.is_new():
			old_setup = frappe.db.get_value(
				self.doctype,
				self.name,
				["main_lot", "from_location", "posting_date", "cutting_spreader", "cutter"],
				as_dict=True,
			)
			existing_rows = {
				row.name: row
				for row in frappe.get_all(
					"Cutting Bulk Lay Sheet Detail",
					filters={"parent": self.name, "parenttype": self.doctype},
					fields=[
						"name", "lot", "cutting_plan", "cutting_marker",
						"cutting_laysheet", "lot_transfer", "delivery_challan",
					],
				)
			}
			if any(row.cutting_laysheet for row in existing_rows.values()):
				for fieldname, label in (
					("main_lot", "Main Stock Lot"),
					("from_location", "Stock Location"),
					("posting_date", "Posting Date"),
					("cutting_spreader", "Cutting Spreader"),
					("cutter", "Cutter"),
				):
					if old_setup and self.get(fieldname) != old_setup.get(fieldname):
						frappe.throw(
							_("{0} cannot change after Lay Sheets are created.").format(label)
						)

		seen_lots = set()
		seen_plans = set()
		current_names = {row.name for row in self.lot_details if row.name}
		for old_row in existing_rows.values():
			if old_row.cutting_laysheet and old_row.name not in current_names:
				frappe.throw(
					_("Split Lot row {0} cannot be removed after its Lay Sheet is created.").format(
						old_row.lot
					)
				)

		for row in self.lot_details:
			if row.lot == self.main_lot:
				frappe.throw(
					_("Row {0}: Split Lot must be different from the Main Stock Lot.").format(row.idx)
				)
			if row.lot in seen_lots:
				frappe.throw(_("Row {0}: Split Lot {1} is repeated.").format(row.idx, row.lot))
			if row.cutting_plan in seen_plans:
				frappe.throw(
					_("Row {0}: Cutting Plan {1} is repeated.").format(row.idx, row.cutting_plan)
				)
			seen_lots.add(row.lot)
			seen_plans.add(row.cutting_plan)

			plan = frappe.db.get_value(
				"Cutting Plan",
				row.cutting_plan,
				["lot", "work_order", "docstatus", "cp_status"],
				as_dict=True,
			)
			if not plan or plan.docstatus != 1:
				frappe.throw(_("Row {0}: Select a submitted Cutting Plan.").format(row.idx))
			if plan.lot != row.lot:
				frappe.throw(
					_("Row {0}: Cutting Plan {1} belongs to Lot {2}, not {3}.").format(
						row.idx, row.cutting_plan, plan.lot, row.lot
					)
				)
			if plan.cp_status == "Completed":
				frappe.throw(_("Row {0}: Cutting Plan {1} is completed.").format(row.idx, row.cutting_plan))
			if not plan.work_order:
				frappe.throw(_("Row {0}: Cutting Plan {1} has no Work Order.").format(row.idx, row.cutting_plan))

			marker = frappe.db.get_value(
				"Cutting Marker",
				row.cutting_marker,
				["cutting_plan", "docstatus"],
				as_dict=True,
			)
			if not marker or marker.docstatus != 1:
				frappe.throw(_("Row {0}: Select a submitted Cutting Marker.").format(row.idx))
			if marker.cutting_plan != row.cutting_plan:
				frappe.throw(
					_("Row {0}: Cutting Marker {1} is not against Cutting Plan {2}.").format(
						row.idx, row.cutting_marker, row.cutting_plan
					)
				)
			row.work_order = plan.work_order

			old_row = existing_rows.get(row.name)
			if old_row and old_row.cutting_laysheet:
				for fieldname, label in (
					("lot", "Split Lot"),
					("cutting_plan", "Cutting Plan"),
					("cutting_marker", "Cutting Marker"),
				):
					if row.get(fieldname) != old_row.get(fieldname):
						frappe.throw(
							_("Row {0}: {1} cannot change after its Lay Sheet is created.").format(
								row.idx, label
							)
						)
				row.cutting_laysheet = old_row.cutting_laysheet
				row.lot_transfer = old_row.lot_transfer
				row.delivery_challan = old_row.delivery_challan

	def _save_active_laysheet_editor(self):
		if not self.active_cutting_laysheet or not self.get("item_details"):
			return
		entry = get_entry_for_laysheet(self.name, self.active_cutting_laysheet)
		if entry.lot_transfer and get_docstatus("Lot Transfer", entry.lot_transfer) != 2:
			frappe.throw(
				_("Lay Sheet {0} cannot be edited after its Lot Transfer is created.").format(
					self.active_cutting_laysheet
				)
			)
		laysheet = frappe.get_doc("Cutting LaySheet", self.active_cutting_laysheet)
		laysheet.item_details = self.item_details
		laysheet.item_accessory_details = self.get("item_accessory_details") or "[]"
		laysheet.save()


def get_docstatus(doctype, name):
	if not name:
		return None
	return frappe.db.get_value(doctype, name, "docstatus")


def get_entry_status(row):
	if not row.cutting_laysheet:
		return "Create Lay Sheet"
	lay_status = frappe.db.get_value("Cutting LaySheet", row.cutting_laysheet, "status")
	if not lay_status:
		return "Lay Sheet Missing"
	if lay_status == "Label Printed":
		return "Completed"
	if lay_status == "Approval Pending":
		return "Approval Pending"
	if lay_status not in ("Bundles Generated",):
		return {
			"Started": "Enter Lay Details",
			"Completed": "Ready to Generate",
		}.get(lay_status, lay_status)

	if not row.lot_transfer:
		return "Create Lot Transfer"
	transfer_status = get_docstatus("Lot Transfer", row.lot_transfer)
	if transfer_status is None:
		return "Lot Transfer Missing"
	if transfer_status == 0:
		return "Submit Lot Transfer"
	if transfer_status == 2:
		return "Lot Transfer Cancelled"

	if not row.delivery_challan:
		return "Make Delivery Challan"
	dc_status = get_docstatus("Delivery Challan", row.delivery_challan)
	if dc_status is None:
		return "Delivery Challan Missing"
	if dc_status == 0:
		return "Submit Delivery Challan"
	if dc_status == 2:
		return "Delivery Challan Cancelled"
	return "Ready to Print"


def get_bulk_status(rows):
	statuses = [get_entry_status(row) for row in rows]
	if not statuses or all(status == "Create Lay Sheet" for status in statuses):
		return "Setup"
	if all(status == "Completed" for status in statuses):
		return "Completed"
	if all(status in ("Ready to Print", "Completed") for status in statuses):
		return "Ready to Print"
	if all(status != "Create Lay Sheet" for status in statuses):
		if all(status == "Enter Lay Details" for status in statuses):
			return "Lay Sheets Created"
		return "In Progress"
	return "In Progress"


def get_laysheet_editor_data(bulk_name, laysheet_name):
	entry = get_entry_for_laysheet(bulk_name, laysheet_name)
	from production_api.production_api.doctype.cutting_laysheet.cutting_laysheet import (
		fetch_manual_item_details,
	)

	laysheet = frappe.get_doc("Cutting LaySheet", laysheet_name)
	manual_items = {}
	if laysheet.is_manual_entry:
		manual_items = fetch_manual_item_details(
			laysheet.cutting_laysheet_manual_items, laysheet.name
		)
	return {
		"context": {
			"name": laysheet.name,
			"cutting_plan": laysheet.cutting_plan,
			"cutting_order": laysheet.cutting_order,
			"cutting_marker": laysheet.cutting_marker,
			"is_manual_entry": laysheet.is_manual_entry,
			"is_set_item": laysheet.is_set_item,
			"status": laysheet.status,
			"docstatus": laysheet.docstatus,
			"is_new": False,
			"read_only": bool(
				entry.lot_transfer and get_docstatus("Lot Transfer", entry.lot_transfer) != 2
			),
		},
		"item_details": {
			"manual_items": manual_items,
			"cloth_items": [row.as_dict() for row in laysheet.cutting_laysheet_details],
		},
		"item_accessories": [
			row.as_dict() for row in laysheet.cutting_laysheet_accessory_details
		],
		"bundles": [row.as_dict() for row in laysheet.cutting_laysheet_bundles],
	}


def get_bulk_doc(name):
	doc = frappe.get_doc("Cutting Bulk Lay Sheets", name)
	doc.check_permission("write")
	return doc


def get_entry(bulk_doc, detail_name):
	for row in bulk_doc.lot_details:
		if row.name == detail_name:
			return row
	frappe.throw(_("The selected split-lot row does not belong to {0}.").format(bulk_doc.name))


def get_entry_for_laysheet(bulk_name, laysheet_name):
	entry = frappe.db.get_value(
		"Cutting Bulk Lay Sheet Detail",
		{
			"parent": bulk_name,
			"parenttype": "Cutting Bulk Lay Sheets",
			"cutting_laysheet": laysheet_name,
		},
		[
			"name", "parent", "lot", "cutting_plan", "cutting_marker", "work_order",
			"cutting_laysheet", "lot_transfer", "delivery_challan",
		],
		as_dict=True,
	)
	if not entry:
		frappe.throw(_("Lay Sheet {0} does not belong to {1}.").format(laysheet_name, bulk_name))
	return entry


def refresh_bulk_status(bulk_name):
	rows = frappe.get_all(
		"Cutting Bulk Lay Sheet Detail",
		filters={"parent": bulk_name, "parenttype": "Cutting Bulk Lay Sheets"},
		fields=["name", "cutting_laysheet", "lot_transfer", "delivery_challan"],
		order_by="idx",
	)
	for row in rows:
		frappe.db.set_value(
			"Cutting Bulk Lay Sheet Detail",
			row.name,
			"status",
			get_entry_status(row),
			update_modified=False,
		)
	frappe.db.set_value(
		"Cutting Bulk Lay Sheets",
		bulk_name,
		"status",
		get_bulk_status(rows),
		update_modified=False,
	)


@frappe.whitelist()
def create_laysheets(doc_name):
	doc = get_bulk_doc(doc_name)
	doc._validate_lot_rows()
	created = []
	for row in doc.lot_details:
		if row.cutting_laysheet and frappe.db.exists("Cutting LaySheet", row.cutting_laysheet):
			continue
		laysheet = frappe.new_doc("Cutting LaySheet")
		laysheet.cutting_plan = row.cutting_plan
		laysheet.cutting_marker = row.cutting_marker
		laysheet.cutting_spreader = doc.cutting_spreader
		laysheet.cutter = doc.cutter
		laysheet.posting_date = doc.posting_date
		laysheet.posting_time = nowtime()
		laysheet.cutting_bulk_lay_sheet = doc.name
		laysheet.cutting_bulk_lay_sheet_detail = row.name
		laysheet.insert()
		frappe.db.set_value(
			"Cutting Bulk Lay Sheet Detail",
			row.name,
			"cutting_laysheet",
			laysheet.name,
			update_modified=False,
		)
		created.append(laysheet.name)

	if not doc.active_cutting_laysheet:
		active = created[0] if created else frappe.db.get_value(
			"Cutting Bulk Lay Sheet Detail",
			{"parent": doc.name, "cutting_laysheet": ["is", "set"]},
			"cutting_laysheet",
		)
		if active:
			frappe.db.set_value(
				"Cutting Bulk Lay Sheets", doc.name, "active_cutting_laysheet", active
			)
	refresh_bulk_status(doc.name)
	return created


@frappe.whitelist()
def set_active_laysheet(doc_name, cutting_laysheet):
	doc = get_bulk_doc(doc_name)
	get_entry_for_laysheet(doc.name, cutting_laysheet)
	doc.db_set("active_cutting_laysheet", cutting_laysheet)
	return cutting_laysheet


def build_lot_transfer_items(laysheet, main_lot, target_lot, warehouse, received_type):
	quantities = defaultdict(float)
	for row in laysheet.cutting_laysheet_details:
		if row.cloth_item_variant and flt(row.weight) > 0:
			quantities[row.cloth_item_variant] += flt(row.weight)
	for row in laysheet.cutting_laysheet_accessory_details:
		if row.cloth_item_variant and flt(row.weight) > 0:
			quantities[row.cloth_item_variant] += flt(row.weight)
	if not quantities:
		frappe.throw(_("Enter cloth or accessory items before creating the Lot Transfer."))

	items = []
	for item_variant, qty in sorted(quantities.items()):
		item = frappe.get_cached_value("Item Variant", item_variant, "item")
		uom = frappe.get_cached_value("Item", item, "default_unit_of_measure")
		if not uom:
			frappe.throw(_("Default UOM is not configured for Item {0}.").format(item))
		idx = len(items)
		items.append(
			{
				"item": item_variant,
				"qty": flt(qty, 3),
				"uom": uom,
				"from_lot": main_lot,
				"to_lot": target_lot,
				"warehouse": warehouse,
				"received_type": received_type,
				"table_index": idx,
				"row_index": idx,
			}
		)
	return items


def validate_source_stock(items, main_lot, reserved=None):
	from production_api.mrp_stock.utils import get_stock_balance

	reserved = reserved or {}
	shortages = []
	for row in items:
		available = get_stock_balance(
			row["item"],
			row["warehouse"],
			row["received_type"],
			lot=main_lot,
			uom=row["uom"],
		)
		required = flt(row["qty"], 3) + flt(reserved.get(row["item"]), 3)
		if flt(available, 3) < required:
			shortages.append(
				_("{0}: required {1} {2}, available {3} {2}").format(
					row["item"], required, row["uom"], flt(available, 3)
				)
			)
	if shortages:
		frappe.throw(
			_("Insufficient stock in Main Stock Lot {0}:<br>{1}").format(
				main_lot, "<br>".join(shortages)
			)
		)


@frappe.whitelist()
def create_lot_transfer(doc_name, detail_name):
	doc = get_bulk_doc(doc_name)
	row = get_entry(doc, detail_name)
	if not row.cutting_laysheet:
		frappe.throw(_("Create the Lay Sheet first."))
	if row.delivery_challan and get_docstatus("Delivery Challan", row.delivery_challan) != 2:
		frappe.throw(_("A Delivery Challan already exists for this row."))
	if row.lot_transfer and get_docstatus("Lot Transfer", row.lot_transfer) != 2:
		return row.lot_transfer

	laysheet = frappe.get_doc("Cutting LaySheet", row.cutting_laysheet)
	if not laysheet.cutting_laysheet_bundles or laysheet.status not in (
		"Bundles Generated", "Approval Pending"
	):
		frappe.throw(_("Generate bundles before creating the Lot Transfer."))
	received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	items = build_lot_transfer_items(
		laysheet, doc.main_lot, row.lot, doc.from_location, received_type
	)
	draft_transfers = frappe.get_all(
		"Lot Transfer",
		filters={"cutting_bulk_lay_sheet": doc.name, "docstatus": 0},
		pluck="name",
	)
	reserved = defaultdict(float)
	if draft_transfers:
		for transfer_row in frappe.get_all(
			"Lot Transfer Item",
			filters={"parent": ["in", draft_transfers], "from_lot": doc.main_lot},
			fields=["item", "qty"],
		):
			reserved[transfer_row.item] += flt(transfer_row.qty)
	validate_source_stock(items, doc.main_lot, reserved)

	transfer = frappe.new_doc("Lot Transfer")
	transfer.flags.allow_from_cutting_plan = True
	transfer.posting_date = doc.posting_date
	transfer.posting_time = nowtime()
	transfer.cutting_bulk_lay_sheet = doc.name
	transfer.cutting_bulk_lay_sheet_detail = row.name
	transfer.comments = _("Cloth for {0} / {1} from {2}").format(
		row.cutting_plan, row.cutting_laysheet, doc.name
	)
	transfer.set("items", items)
	transfer.save()
	frappe.db.set_value(
		"Cutting Bulk Lay Sheet Detail",
		row.name,
		"lot_transfer",
		transfer.name,
		update_modified=False,
	)
	refresh_bulk_status(doc.name)
	return transfer.name


@frappe.whitelist()
def prepare_delivery_challan(doc_name, detail_name):
	doc = get_bulk_doc(doc_name)
	row = get_entry(doc, detail_name)
	if row.delivery_challan and get_docstatus("Delivery Challan", row.delivery_challan) != 2:
		return {"existing_delivery_challan": row.delivery_challan}
	if not row.lot_transfer or get_docstatus("Lot Transfer", row.lot_transfer) != 1:
		frappe.throw(_("Submit the Lot Transfer before making the Delivery Challan."))

	from production_api.mrp_stock.doctype.lot_transfer.lot_transfer import (
		get_delivery_challan_details,
	)

	data = get_delivery_challan_details(
		row.lot_transfer, row.work_order, doc.from_location
	)
	data["cutting_bulk_lay_sheet"] = doc.name
	data["cutting_bulk_lay_sheet_detail"] = row.name
	data["comments"] = _("Created from Cutting Bulk Lay Sheets {0}").format(doc.name)
	return data


def record_delivery_challan(doc):
	if not doc.cutting_bulk_lay_sheet or not doc.cutting_bulk_lay_sheet_detail:
		return
	entry = frappe.db.get_value(
		"Cutting Bulk Lay Sheet Detail",
		doc.cutting_bulk_lay_sheet_detail,
		["parent", "work_order", "lot"],
		as_dict=True,
	)
	if not entry or entry.parent != doc.cutting_bulk_lay_sheet:
		frappe.throw(_("Invalid Cutting Bulk Lay Sheets reference."))
	if entry.work_order != doc.work_order or entry.lot != doc.lot:
		frappe.throw(_("Delivery Challan Work Order or Lot does not match the bulk row."))
	frappe.db.set_value(
		"Cutting Bulk Lay Sheet Detail",
		doc.cutting_bulk_lay_sheet_detail,
		"delivery_challan",
		doc.name,
		update_modified=False,
	)
	refresh_bulk_status(doc.cutting_bulk_lay_sheet)


def validate_bulk_print_prerequisites(laysheet_name):
	laysheet = frappe.get_doc("Cutting LaySheet", laysheet_name)
	if not laysheet.cutting_bulk_lay_sheet:
		return None
	entry = get_entry_for_laysheet(laysheet.cutting_bulk_lay_sheet, laysheet.name)
	if not entry.lot_transfer or get_docstatus("Lot Transfer", entry.lot_transfer) != 1:
		frappe.throw(_("Submit the linked Lot Transfer before printing labels."))
	bulk = frappe.get_doc("Cutting Bulk Lay Sheets", laysheet.cutting_bulk_lay_sheet)
	transfer = frappe.get_doc("Lot Transfer", entry.lot_transfer)
	if (
		transfer.cutting_bulk_lay_sheet != bulk.name
		or transfer.cutting_bulk_lay_sheet_detail != entry.name
	):
		frappe.throw(_("The linked Lot Transfer does not match this bulk Lay Sheet."))
	received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	expected_items = build_lot_transfer_items(
		laysheet, bulk.main_lot, entry.lot, bulk.from_location, received_type
	)
	expected = {
		(
			row["item"], row["from_lot"], row["to_lot"], row["warehouse"],
			row["received_type"], row["uom"],
		): flt(row["qty"], 3)
		for row in expected_items
	}
	actual = defaultdict(float)
	for row in transfer.items:
		key = (
			row.item, row.from_lot, row.to_lot, row.warehouse, row.received_type,
			row.uom,
		)
		actual[key] += flt(row.qty, 3)
	if expected != dict(actual):
		frappe.throw(_("The submitted Lot Transfer items no longer match the Lay Sheet entries."))
	if not entry.delivery_challan or get_docstatus("Delivery Challan", entry.delivery_challan) != 1:
		frappe.throw(_("Submit the linked Delivery Challan before printing labels."))
	dc = frappe.db.get_value(
		"Delivery Challan",
		entry.delivery_challan,
		["work_order", "lot", "cutting_bulk_lay_sheet", "cutting_bulk_lay_sheet_detail"],
		as_dict=True,
	)
	if (
		not dc
		or dc.work_order != entry.work_order
		or dc.lot != entry.lot
		or dc.cutting_bulk_lay_sheet != laysheet.cutting_bulk_lay_sheet
		or dc.cutting_bulk_lay_sheet_detail != entry.name
	):
		frappe.throw(_("The linked Delivery Challan does not match this bulk Lay Sheet."))
	return entry


def validate_cutting_plan_stock(laysheet):
	required = defaultdict(float)
	for row in laysheet.cutting_laysheet_details:
		required[(row.colour, row.cloth_type, row.actual_dia)] += flt(row.weight) - flt(
			row.balance_weight
		)
	for row in laysheet.cutting_laysheet_accessory_details:
		required[(row.colour, row.cloth_type, row.actual_dia)] += flt(row.weight)

	plan = frappe.get_doc("Cutting Plan", laysheet.cutting_plan)
	available = {
		(row.colour, row.cloth_type, row.dia): flt(row.weight) - flt(row.used_weight)
		for row in plan.cutting_plan_cloth_details
	}
	shortages = []
	for key, qty in required.items():
		if key not in available:
			shortages.append(_("{0} / {1} / {2}: not present in Cutting Plan").format(*key))
		elif flt(available[key], 3) < flt(qty, 3):
			shortages.append(
				_("{0} / {1} / {2}: required {3} Kg, available {4} Kg").format(
					key[0], key[1], key[2], flt(qty, 3), flt(available[key], 3)
				)
			)
	if shortages:
		frappe.throw(
			_("Transferred/DC stock is insufficient in Cutting Plan {0}:<br>{1}").format(
				laysheet.cutting_plan, "<br>".join(shortages)
			)
		)


@frappe.whitelist()
def get_label_print_context(doc_name, detail_name):
	doc = get_bulk_doc(doc_name)
	row = get_entry(doc, detail_name)
	if not row.cutting_laysheet:
		frappe.throw(_("Create the Lay Sheet first."))
	validate_bulk_print_prerequisites(row.cutting_laysheet)
	laysheet = frappe.get_doc("Cutting LaySheet", row.cutting_laysheet)
	if not laysheet.cutting_laysheet_bundles:
		frappe.throw(_("Generate bundles before printing labels."))
	validate_cutting_plan_stock(laysheet)

	from production_api.production_api.doctype.cutting_laysheet.cutting_laysheet import (
		get_laysheet_piece_weight_tolerance,
	)

	tolerance = get_laysheet_piece_weight_tolerance(laysheet)
	difference = abs(flt(laysheet.piece_weight) - flt(laysheet.required_pcs_weight))
	if difference > tolerance and not laysheet.approved_by:
		laysheet.db_set("status", "Approval Pending")
		refresh_bulk_status(doc.name)
		return {
			"approval_required": True,
			"difference": difference,
			"tolerance": tolerance,
			"cutting_laysheet": laysheet.name,
		}
	if not laysheet.approved_by:
		laysheet.db_set("approved_by", frappe.session.user)
	return {
		"approval_required": False,
		"cutting_laysheet": laysheet.name,
		"cutting_plan": laysheet.cutting_plan,
		"lay_no": laysheet.lay_no,
		"print_items": [row.as_dict() for row in laysheet.cutting_laysheet_bundles],
	}


@frappe.whitelist()
def approve_laysheet_grammage(doc_name, detail_name):
	doc = get_bulk_doc(doc_name)
	row = get_entry(doc, detail_name)
	from production_api.production_api.doctype.cutting_laysheet.cutting_laysheet import (
		approve_grammage,
	)

	approve_grammage(row.cutting_laysheet)
	refresh_bulk_status(doc.name)


@frappe.whitelist()
def mark_labels_printed(doc_name, detail_name, goods_received_note=None):
	doc = get_bulk_doc(doc_name)
	row = get_entry(doc, detail_name)
	validate_bulk_print_prerequisites(row.cutting_laysheet)
	laysheet = frappe.get_doc("Cutting LaySheet", row.cutting_laysheet)
	laysheet.printed_time = now_datetime()
	laysheet.status = "Label Printed"
	laysheet.goods_received_note = goods_received_note
	laysheet.save()
	refresh_bulk_status(doc.name)
	return laysheet.name
