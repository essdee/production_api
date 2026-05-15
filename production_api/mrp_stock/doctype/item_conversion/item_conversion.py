# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import json
from itertools import groupby

import frappe
from frappe import _, msgprint
from frappe.model.document import Document
from frappe.utils import cstr, flt

from production_api.mrp_stock.doctype.stock_entry.stock_entry import get_uom_details
from production_api.mrp_stock.utils import get_stock_balance
from production_api.production_api.doctype.item.item import (
	create_variant,
	get_attribute_details,
	get_variant,
)
from production_api.production_api.doctype.purchase_order.purchase_order import (
	get_item_attribute_details,
	get_item_group_index,
)
from production_api.utils import update_if_string_instance


class ItemConversion(Document):
	def onload(self):
		from_item_details = fetch_item_conversion_items(self.get("from_items"))
		to_item_details = fetch_item_conversion_items(self.get("to_items"))

		self.set("print_from_item_details", json.dumps(from_item_details))
		self.set("print_to_item_details", json.dumps(to_item_details))
		self.set_onload("from_item_details", from_item_details)
		self.set_onload("to_item_details", to_item_details)

	def before_validate(self):
		if self.get("from_item_details"):
			self.set("from_items", save_item_conversion_items(self.from_item_details))

		if self.get("to_item_details"):
			self.set("to_items", save_item_conversion_items(self.to_item_details))

		if not self.get("from_items"):
			frappe.throw(_("Add From Items to continue"), title=_("Item Conversion"))

		if not self.get("to_items"):
			frappe.throw(_("Add To Items to continue"), title=_("Item Conversion"))

	def validate(self):
		if not self.warehouse:
			frappe.throw(_("Location is mandatory"))
		if not self.from_item:
			frappe.throw(_("From Item is mandatory"))
		if not self.to_item:
			frappe.throw(_("To Item is mandatory"))

		self.validate_items(
			"from_items",
			_("From Items"),
			self.from_item,
			rate_source="stock_valuation",
		)
		self.validate_items("to_items", _("To Items"), self.to_item, rate_source="user")
		self.calculate_totals()

	def before_submit(self):
		self.validate_valuation_match()
		from production_api.utils import validate_supplier_user

		validate_supplier_user(supplier1=self.warehouse)

	def on_submit(self):
		self.update_stock_ledger()
		self.make_repost_action()

	def before_cancel(self):
		self.ignore_linked_doctypes = ("Stock Ledger Entry", "Repost Item Valuation")
		self.update_stock_ledger()

	def on_cancel(self):
		self.make_repost_action()

	def validate_items(self, table_field, table_label, expected_item, rate_source):
		def _get_msg(row_num, msg):
			return _("Table {0} Row # {1}:").format(table_label, row_num) + " " + msg

		validation_messages = []

		for row in self.get(table_field):
			item_template = self.validate_item(row.item, row, validation_messages)
			if item_template and item_template != expected_item:
				validation_messages.append(
					_get_msg(
						row.idx,
						_("Item {0} does not match selected item {1}").format(item_template, expected_item),
					)
				)

			if row.qty in ["", None, 0]:
				validation_messages.append(_get_msg(row.idx, _("Quantity is mandatory")))

			if flt(row.qty) < 0:
				validation_messages.append(_get_msg(row.idx, _("Negative Quantity is not allowed")))

			if flt(row.rate) < 0:
				validation_messages.append(_get_msg(row.idx, _("Negative Valuation Rate is not allowed")))

			if row.qty and rate_source == "stock_valuation":
				row.rate = self.get_existing_valuation_rate(row)
				if not row.rate:
					validation_messages.append(
						_get_msg(
							row.idx,
							_("Could not find existing valuation rate for Item {0}, Lot {1}").format(
								row.item, row.lot
							),
						)
					)

			if row.qty and row.rate in ["", None, 0] and rate_source == "user":
				validation_messages.append(_get_msg(row.idx, _("Rate is mandatory")))

			item_details = get_uom_details(row.item, row.uom, row.qty)
			row.set("stock_uom", item_details.get("stock_uom"))
			row.set("conversion_factor", item_details.get("conversion_factor"))
			row.stock_qty = flt(
				flt(row.qty) * flt(row.conversion_factor), self.precision("stock_qty", row)
			)
			row.stock_uom_rate = flt(
				flt(row.rate) / flt(row.conversion_factor), self.precision("stock_uom_rate", row)
			)
			row.amount = flt(flt(row.rate) * flt(row.qty), self.precision("amount", row))

		if validation_messages:
			for msg in validation_messages:
				msgprint(msg)

			raise frappe.ValidationError(validation_messages)

	def validate_item(self, item, row, validation_messages):
		from production_api.production_api.doctype.item.item import (
			validate_cancelled_item,
			validate_disabled,
			validate_is_stock_item,
		)

		try:
			item_template = frappe.get_cached_value("Item Variant", item, "item")
			validate_disabled(item_template)
			validate_is_stock_item(item_template)
			validate_cancelled_item(item_template)
			return item_template
		except Exception as e:
			validation_messages.append(_("Row #") + " " + ("%d: " % (row.idx)) + cstr(e))

	def get_existing_valuation_rate(self, row):
		return get_stock_balance(
			row.item,
			self.warehouse,
			row.received_type,
			self.posting_date,
			self.posting_time,
			with_valuation_rate=True,
			lot=row.lot,
			uom=row.uom,
		)[1]

	def calculate_totals(self):
		self.from_total_amount = flt(
			sum(flt(item.amount) for item in self.get("from_items")),
			self.precision("from_total_amount"),
		)
		self.to_total_amount = flt(
			sum(flt(item.amount) for item in self.get("to_items")),
			self.precision("to_total_amount"),
		)
		self.difference_amount = flt(
			flt(self.from_total_amount) - flt(self.to_total_amount),
			self.precision("difference_amount"),
		)

	def validate_valuation_match(self):
		if flt(self.difference_amount, self.precision("difference_amount")):
			frappe.throw(
				_(
					"From Items total ({0}) must match To Items total ({1}). Difference: {2}"
				).format(self.from_total_amount, self.to_total_amount, self.difference_amount)
			)

	def update_stock_ledger(self):
		from production_api.mrp_stock.stock_ledger import make_sl_entries

		if self.docstatus == 0:
			return

		sl_entries = []
		self.get_sle_for_from_items(sl_entries)
		self.get_sle_for_to_items(sl_entries)

		if self.docstatus == 2:
			sl_entries.reverse()

		make_sl_entries(sl_entries)

	def get_sle_for_from_items(self, sl_entries):
		for row in self.get("from_items"):
			sl_entries.append(
				self.get_sl_entries(
					row,
					{
						"qty": -flt(row.stock_qty),
						"rate": 0,
						"outgoing_rate": flt(row.stock_uom_rate),
					},
				)
			)

	def get_sle_for_to_items(self, sl_entries):
		for row in self.get("to_items"):
			sl_entries.append(
				self.get_sl_entries(
					row,
					{
						"qty": flt(row.stock_qty),
						"rate": flt(row.stock_uom_rate),
					},
				)
			)

	def get_sl_entries(self, row, args):
		sl_dict = frappe._dict(
			{
				"item": row.get("item"),
				"warehouse": self.warehouse,
				"received_type": row.get("received_type"),
				"lot": row.get("lot"),
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"voucher_detail_no": row.name,
				"uom": row.stock_uom,
				"rate": 0,
				"is_cancelled": 1 if self.docstatus == 2 else 0,
				"remarks": row.remarks,
			}
		)
		sl_dict.update(args)
		return sl_dict

	def make_repost_action(self):
		from production_api.mrp_stock.stock_ledger import repost_future_stock_ledger_entry

		repost_future_stock_ledger_entry(self)


@frappe.whitelist()
def get_item_conversion_valuation_rate(
	item,
	attributes=None,
	lot=None,
	received_type=None,
	uom=None,
	warehouse=None,
	posting_date=None,
	posting_time=None,
):
	attributes = update_if_string_instance(attributes) or {}
	variant_name = get_variant(item, attributes)
	if not variant_name or not warehouse:
		return {"item_variant": variant_name, "qty": 0, "rate": 0}

	qty, rate = get_stock_balance(
		variant_name,
		warehouse,
		received_type,
		posting_date,
		posting_time,
		with_valuation_rate=True,
		lot=lot,
		uom=uom,
	)

	return {"item_variant": variant_name, "qty": flt(qty), "rate": flt(rate)}


@frappe.whitelist()
def fetch_item_conversion_items(items):
	if len(items) > 0 and type(items[0]) != dict:
		items = [item.as_dict() for item in items]

	item_details = []
	items = sorted(items, key=lambda i: i["row_index"])
	for key, variants in groupby(items, lambda i: i["row_index"]):
		variants = list(variants)
		current_variant = frappe.get_doc("Item Variant", variants[0]["item"])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			"name": current_variant.item,
			"lot": variants[0]["lot"],
			"attributes": get_item_attribute_details(current_variant, current_item_attribute_details),
			"primary_attribute": current_item_attribute_details["primary_attribute"],
			"values": {},
			"default_uom": variants[0].get("uom") or current_item_attribute_details["default_uom"],
			"secondary_uom": variants[0].get("secondary_uom")
			or current_item_attribute_details["secondary_uom"],
			"received_type": variants[0].get("received_type"),
			"remarks": variants[0].get("remarks"),
		}

		if item["primary_attribute"]:
			for attr in current_item_attribute_details["primary_attribute_values"]:
				item["values"][attr] = {"qty": 0, "rate": 0}
			for variant in variants:
				current_variant = frappe.get_doc("Item Variant", variant["item"])
				for attr in current_variant.attributes:
					if attr.attribute == item.get("primary_attribute"):
						item["values"][attr.attribute_value] = {
							"qty": variant.get("qty", 0),
							"rate": variant.get("rate", 0),
							"secondary_qty": variant.get("secondary_qty", 0),
							"secondary_uom": variant.get("secondary_uom"),
							"set_combination": update_if_string_instance(
								variant.get("set_combination") or {}
							),
						}
						break
		else:
			item["values"]["default"] = {
				"qty": variants[0].get("qty", 0),
				"rate": variants[0].get("rate", 0),
				"secondary_qty": variants[0].get("secondary_qty", 0),
				"secondary_uom": variants[0].get("secondary_uom"),
				"set_combination": update_if_string_instance(
					variants[0].get("set_combination") or {}
				),
			}

		index = get_item_group_index(item_details, current_item_attribute_details)
		if index == -1:
			item_details.append(
				{
					"attributes": current_item_attribute_details["attributes"],
					"primary_attribute": current_item_attribute_details["primary_attribute"],
					"primary_attribute_values": current_item_attribute_details[
						"primary_attribute_values"
					],
					"items": [item],
				}
			)
		else:
			item_details[index]["items"].append(item)

	return item_details


def save_item_conversion_items(item_details):
	item_details = update_if_string_instance(item_details)
	items = []
	row_index = 0

	for table_index, group in enumerate(item_details or []):
		for item in group.get("items", []):
			item_name = item.get("name")
			item_attributes = item.get("attributes") or {}
			primary_attribute = item.get("primary_attribute")
			values = item.get("values") or {}

			if primary_attribute:
				for attr, value in values.items():
					if flt(value.get("qty")):
						attributes = dict(item_attributes)
						attributes[primary_attribute] = attr
						items.append(
							get_item_conversion_item_row(
								item,
								value,
								item_name,
								attributes,
								table_index,
								row_index,
							)
						)
			else:
				value = values.get("default") or {}
				if flt(value.get("qty")):
					items.append(
						get_item_conversion_item_row(
							item,
							value,
							item_name,
							dict(item_attributes),
							table_index,
							row_index,
						)
					)

			row_index += 1

	return items


def get_item_conversion_item_row(item, value, item_name, item_attributes, table_index, row_index):
	variant_name = get_variant(item_name, item_attributes)
	if not variant_name:
		variant = create_variant(item_name, item_attributes)
		variant.insert()
		variant_name = variant.name

	return {
		"item": variant_name,
		"lot": item.get("lot"),
		"uom": item.get("default_uom"),
		"qty": flt(value.get("qty")),
		"rate": flt(value.get("rate")),
		"table_index": table_index,
		"row_index": row_index,
		"remarks": item.get("remarks"),
		"received_type": item.get("received_type"),
		"secondary_qty": flt(value.get("secondary_qty")),
		"secondary_uom": value.get("secondary_uom") or item.get("secondary_uom"),
		"set_combination": value.get("set_combination") or {},
	}
