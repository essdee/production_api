# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint, date_diff, flt, getdate, now_datetime
from frappe.model.document import Document
from production_api.utils import update_if_string_instance, get_variant_attr_details
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant, get_variant, build_variant_attributes

TRACKED_DATE_FIELDS = {
	"delivery_date": "Delivery Date",
	"dont_deliver_after": "Don't Deliver After",
}

TRACKED_DATE_LABELS = {label: fieldname for fieldname, label in TRACKED_DATE_FIELDS.items()}

PPO_DRAFT_STATUS = "Draft"
PPO_REQUEST_STATUS = "PPO Request"
PPO_APPROVER_ROLE_FIELDS = ("merch_user_role", "merchandising_manager_role")
SYSTEM_GENERATED_ALTERNATIVE_PPO_FLAG = "allow_system_generated_alternative_ppo"


class ProductionOrder(Document):
	def before_cancel(self):
		lots = frappe.get_all(
			"Lot", filters={"production_order": self.name}, pluck="name")
		if lots:
			frappe.throw(f"PPO linked in {','.join(lots)}")

	def validate(self):
		self.validate_ppo_approval_state()
		self.validate_production_dates()
		self.validate_tracked_date_update()
		self.validate_quantity_workflow_lock()
		from production_api.lot_pricing import validate_lot_price_overrides
		validate_lot_price_overrides(self)

	def on_update_after_submit(self):
		self.lead_time_given = date_diff(self.delivery_date, self.posting_date)

	def before_submit(self):
		self.validate_ppo_submission()
		validate_ppo_request_readiness(self, self.posting_date)
		self.lead_time_given = date_diff(self.delivery_date, self.posting_date)
		self.submitted_by = frappe.session.user
		self.submitted_time = frappe.utils.now()

	def on_submit(self):
		self.db_set("status", "Open", update_modified=False)

	def onload(self):
		can_manage_production_order = user_can_manage_production_order()
		self.set_onload("can_manage_production_order", can_manage_production_order)
		if self.docstatus == 0:
			self.set_onload(
				"can_request_ppo_approval",
				can_manage_production_order,
			)
			self.set_onload(
				"can_approve_ppo",
				user_has_any_role(get_ppo_approver_roles()),
			)
			self.set_onload(
				"ppo_approval_request",
				{
					"requested_by": self.get("ppo_requested_by"),
					"requested_on": self.get("ppo_requested_on"),
				},
			)
		order_qty = get_order_qty(self.production_order_details)
		self.set_onload("items", order_qty)
		ordered_detail = get_ordered_details(self.production_ordered_details)
		self.set_onload("ordered_details", {
						"items": order_qty, "ordered": ordered_detail})
		if self.docstatus == 1:
			self.set_onload("linked_lots", get_linked_lots(self.name))
			# Only the two transferable statuses pay for this lookup, and the list doubles as
			# the target filter for the Transfer Quantity dialog, so the button costs no call.
			if self.status in TRANSFERABLE_PO_STATUSES and not self.get(TRANSFER_MARKER_FIELD):
				self.set_onload("alternative_items", get_alternative_items(self.item))
			if self.status == QUANTITY_REQUEST_STATUS:
				request = {}
				if self.get(QUANTITY_REQUEST_FIELD):
					request = frappe.parse_json(self.get(QUANTITY_REQUEST_FIELD)) or {}
					request["request_type"] = "quantity_ratio"
				elif self.get(STATUS_REQUEST_FIELD):
					request = frappe.parse_json(self.get(STATUS_REQUEST_FIELD)) or {}
					request["request_type"] = "status"
				if request:
					self.set_onload("pending_production_order_request", request)
					approver_role = get_quantity_approver_role()
					self.set_onload(
						"can_approve_production_order_request",
						bool(approver_role and approver_role in frappe.get_roles()),
					)
			if self.get(INCOMING_TRANSFER_REQUEST_FIELD):
				request = frappe.parse_json(self.get(INCOMING_TRANSFER_REQUEST_FIELD)) or {}
				self.set_onload("incoming_quantity_transfer_request", request)
				approver_role = get_quantity_approver_role()
				self.set_onload(
					"can_approve_quantity_transfer_request",
					bool(approver_role and approver_role in frappe.get_roles()),
				)
			price_requests = frappe.get_all("PPO Price Request", filters={"production_order": self.name},
												fields=[
													"name", "status", "requested_by", "requested_at", "approved_by", "approved_at"],
											order_by="creation desc", limit=20)
			self.set_onload("price_requests", price_requests)
			pending_name = frappe.db.get_value(
				"PPO Price Request", {"production_order": self.name, "status": "Pending"})
			if pending_name:
				if self.price_approval_status != "Pending Approval":
					self.db_set("price_approval_status",
								"Pending Approval", update_modified=False)
					self.price_approval_status = "Pending Approval"
				pending_doc = frappe.get_doc("PPO Price Request", pending_name)
				self.set_onload("pending_price_request", {"name": pending_doc.name, "requested_by": pending_doc.requested_by,
														  "requested_at": str(pending_doc.requested_at), "details": [row.as_dict() for row in pending_doc.price_details]})

	def before_validate(self):
		if self.is_new():
			self.status = PPO_DRAFT_STATUS
			self.set("production_ordered_details", [])
			self.submitted_by = None
			self.submitted_time = None
		if self.docstatus == 0 and self.get("item") and self.get("item_details"):
			self.update_order()
		self.lead_time_given = date_diff(self.delivery_date, self.posting_date)

	def validate_ppo_approval_state(self):
		if self.docstatus != 0:
			return

		self.status = self.status or PPO_DRAFT_STATUS
		if self.status not in (PPO_DRAFT_STATUS, PPO_REQUEST_STATUS):
			frappe.throw("A draft Production Order must be in Draft or PPO Request status")

		previous = self.get_doc_before_save()
		if not previous:
			return

		previous_status = previous.status or PPO_DRAFT_STATUS
		if self.status != previous_status and not self.flags.get("allow_ppo_request"):
			frappe.throw("Use the Request PPO Approval button to request approval")

	def validate_ppo_submission(self):
		if getattr(self, "flags", None) and self.flags.get(SYSTEM_GENERATED_ALTERNATIVE_PPO_FLAG):
			if self.status != PPO_REQUEST_STATUS:
				frappe.throw("System-generated alternative Production Order must be ready for approval")
			return

		approver_roles = get_ppo_approver_roles()
		if not approver_roles:
			frappe.throw(
				"Set Merch User Role and Merchandising Manager Role in MRP Settings before approving a PPO"
			)
		if not user_has_any_role(approver_roles):
			frappe.throw(
				"Only users with the configured Merch User or Merchandising Manager role can approve a PPO"
			)
		if self.status != PPO_REQUEST_STATUS:
			frappe.throw("Send the Production Order for PPO approval before submitting it")

	def validate_production_dates(self):
		if self.delivery_date and self.posting_date and getdate(self.delivery_date) < getdate(self.posting_date):
			frappe.throw("Delivery date is less than Posting Date")
		if self.delivery_date and self.dont_deliver_after and getdate(self.delivery_date) > getdate(self.dont_deliver_after):
			frappe.throw("Don't deliver after date is less than delivery date")

	def validate_tracked_date_update(self):
		if self.docstatus != 1 or self.flags.get("allow_tracked_date_change"):
			return

		previous = self.get_doc_before_save()
		if not previous:
			return

		changed_fields = []
		for fieldname, label in TRACKED_DATE_FIELDS.items():
			if get_date_value(self.get(fieldname)) != get_date_value(previous.get(fieldname)):
				changed_fields.append(label)

		if changed_fields:
			frappe.throw(
				frappe._("Use the Change Dates button to update {0} after submission.").format(
					", ".join(changed_fields)
				)
				)

	def validate_quantity_workflow_lock(self):
		if self.docstatus != 1:
			return

		previous = self.get_doc_before_save()
		if not previous:
			return

		quantity_ratio_changed = get_quantity_ratio_snapshot(self) != get_quantity_ratio_snapshot(previous)
		if previous.get(TRANSFER_MARKER_FIELD):
			if self.status != previous.status:
				frappe.throw("Status cannot be changed after quantity has been transferred")
			if quantity_ratio_changed:
				frappe.throw("Quantity or Ratio cannot be changed after quantity has been transferred")

		if (
			previous.status == QUANTITY_REQUEST_STATUS
			or previous.get(QUANTITY_REQUEST_FIELD)
			or previous.get(STATUS_REQUEST_FIELD)
		):
			request_changed = (
				self.get(QUANTITY_REQUEST_FIELD) != previous.get(QUANTITY_REQUEST_FIELD)
				or self.get(STATUS_REQUEST_FIELD) != previous.get(STATUS_REQUEST_FIELD)
			)
			status_changed = self.status != previous.status
			approval_allowed = (
				self.flags.get("allow_quantity_ratio_approval")
				or self.flags.get("allow_status_change_approval")
				or self.flags.get("allow_quantity_transfer_approval")
			)
			if (
				not approval_allowed
				and (quantity_ratio_changed or request_changed or status_changed)
			):
				frappe.throw("Use the appropriate Approve button to complete the pending request")

		if (
			previous.status in TRANSFERABLE_PO_STATUSES
			and quantity_ratio_changed
			and not self.flags.get("allow_quantity_transfer")
		):
			frappe.throw("Quantity or Ratio cannot be changed when Production Order is Item Changed or Not Processed")

		if previous.get(INCOMING_TRANSFER_REQUEST_FIELD):
			transfer_request_changed = (
				self.get(INCOMING_TRANSFER_REQUEST_FIELD)
				!= previous.get(INCOMING_TRANSFER_REQUEST_FIELD)
			)
			if (
				not self.flags.get("allow_quantity_transfer_approval")
				and (quantity_ratio_changed or transfer_request_changed)
			):
				frappe.throw("Use Approve Transfer Quantity to complete the pending transfer request")

	def update_order(self):
		item_doc = frappe.get_cached_doc("Item", self.item)
		uom = item_doc.default_unit_of_measure
		pack_out_stage = frappe.db.get_single_value("IPD Settings", "default_pack_out_stage")
		item_details = update_if_string_instance(self.item_details) or {}
		sales_item_price = get_sales_item_price_map(self.item)

		items = []
		for size, current_row in item_details.items():

			price_row = sales_item_price.get(size, {})
			items.append({
				"item_variant": get_or_create_variant(
					self.item, build_variant_attributes({item_doc.primary_attribute: size}, pack_out_stage, item_doc)
				),
				"quantity": current_row.get("qty", 0),
				"ratio": current_row.get("ratio", 0),
				"mrp": current_row.get("mrp", 0),

				"wholesale_price": price_row.get("wholesale", 0),

				"retail_price": price_row.get("retail", 0),

				"uom": uom,
			})
		self.set("production_order_details", items)


def get_sales_item_price_map(item):

	item_doc = frappe.get_cached_doc("Item", item)
	sizes = get_attribute_details(item).get("primary_attribute_values", [])
	pack_out_stage = frappe.db.get_single_value("IPD Settings", "default_pack_out_stage")

	price_map = {}

	for size in sizes:
		variant = get_variant(
			item, build_variant_attributes({item_doc.primary_attribute: size}, pack_out_stage, item_doc)
		) if item_doc.primary_attribute and item_doc.dependent_attribute else None
		candidates = list(set(filter(None, [
			variant,
			f"{item}-{size}",
			f"{item.replace(' ', '-')}-{size}",
			f"{item.replace('-', ' ')}-{size}"
		])))

		rows = frappe.get_all(
			"Sales Item Price",
			filters={"item_variant": ["in", candidates]},
			fields=["item_variant", "rate", "retail_rate", "mrp_rate"]
		)
		price_row = next(
			(r for r in rows if r.item_variant in candidates), None)

		price_map[size] = {
			"wholesale": flt(price_row.rate) if price_row else 0,
			"retail": flt(price_row.retail_rate) if price_row else 0,
			"sales_mrp": flt(price_row.mrp_rate) if price_row and price_row.mrp_rate is not None else None
		}

	return price_map


def get_box_sticker_mrp_map(production_order, item=None):
	box_sticker_mrp = {}
	if not production_order:
		return box_sticker_mrp

	lots = frappe.get_all("Lot", filters={"production_order": production_order}, pluck="name")
	if not lots:
		return box_sticker_mrp

	box_sticker_prints = frappe.get_all(
		"Box Sticker Print",
		filters={"lot": ["in", lots], "docstatus": 1},
		fields=["name"],
		order_by="modified desc, creation desc"
	)
	for bsp in box_sticker_prints:
		rows = frappe.get_all(
			"Box Sticker Print Detail",
			filters={"parent": bsp.name},
			fields=["size", "mrp"]
		)

		for row in rows:
			size = row.size
			if size not in box_sticker_mrp:
				if row.mrp is not None:
					box_sticker_mrp[size] = flt(row.mrp)

	return box_sticker_mrp


@frappe.whitelist()
def get_order_editor_context(item, production_order=None):
	primary_values = get_attribute_details(item).get(
		"primary_attribute_values", [])
	sales_item_price = get_sales_item_price_map(item)

	context = {"primary_values": primary_values, "items": {}}

	for size in primary_values:
		price_row = sales_item_price.get(size, {})
		context["items"][size] = {"qty": 0, "ratio": 0, "mrp": 0,
								  "wholesale": price_row.get("wholesale", 0), "retail": price_row.get("retail", 0)}

	if not production_order or not frappe.db.exists("Production Order", production_order):
		return context

	doc = frappe.get_doc("Production Order", production_order)

	order_qty = get_order_qty(doc.production_order_details)

	for size in primary_values:
		if size not in order_qty:
			continue
		context["items"][size]["qty"] = order_qty[size].get("qty", 0)
		context["items"][size]["ratio"] = order_qty[size].get("ratio", 0)
		context["items"][size]["mrp"] = order_qty[size].get(
			"mrp", context["items"][size]["mrp"])

	context["ordered"] = get_ordered_details(doc.production_ordered_details)

	return context


@frappe.whitelist()
def get_price_update_context(production_order):
	require_ppo_action_role()
	doc = frappe.get_doc("Production Order", production_order)
	doc.check_permission("read")

	primary_values = get_attribute_details(doc.item).get(
		"primary_attribute_values", [])

	order_qty = get_order_qty(doc.production_order_details)
	from production_api.lot_pricing import get_production_order_price_map
	production_order_prices = get_production_order_price_map(doc)

	sales_item_price = get_sales_item_price_map(doc.item)
	box_sticker_mrp = get_box_sticker_mrp_map(production_order, doc.item)
	items = {}
	for size in primary_values:

		sales_mrp = sales_item_price.get(size, {}).get("sales_mrp")
		box_mrp = box_sticker_mrp.get(size)

		production_order_mrp = flt(production_order_prices.get(size, 0))
		selected_source = "production_order_mrp"
		items[size] = {"qty": flt(order_qty.get(size, {}).get("qty", 0)), "ratio": flt(order_qty.get(size, {}).get("ratio", 0)), "production_order_mrp": production_order_mrp, "sales_mrp": sales_mrp, "box_sticker_mrp": box_mrp,
					   "has_sales_mrp": sales_mrp is not None, "has_box_sticker_mrp": box_mrp is not None,
					   "selected_source": selected_source}
	from production_api.lot_pricing import get_lot_pricing
	lots = []
	for lot in frappe.get_all("Lot", filters={"production_order": production_order}, pluck="name", order_by="creation asc"):
		pricing = get_lot_pricing(lot, production_order)
		lots.append(pricing)
	return {"primary_values": primary_values, "items": items, "lots": lots}


@frappe.whitelist()
def get_primary_values(item):
	item_doc = frappe.get_cached_doc("Item", item)
	if not item_doc.primary_attribute or not item_doc.dependent_attribute:
		frappe.throw(f"Can't Create Production Order for Item {item}")
	attr_details = get_attribute_details(item)
	return attr_details['primary_attribute_values']


@frappe.whitelist()
def get_order_qty(items):
	items = [item.as_dict() for item in items]
	order_qty = {}
	for row in items:
		current_variant = frappe.get_cached_doc(
			"Item Variant", row['item_variant'])
		current_item_attribute_details = get_attribute_details(
			current_variant.item)
		primary_attribute = current_item_attribute_details['primary_attribute']
		for attr in current_variant.attributes:
			if attr.attribute == primary_attribute:
				size = attr.attribute_value
				if not size:
					break
				order_qty.setdefault(size, {
									 "qty": 0, "ratio": 0, "mrp": 0, "wholesale": 0, "retail": 0})
				order_qty[size]['qty'] += row['quantity']
				order_qty[size]['ratio'] += row['ratio']
				order_qty[size]['mrp'] += row['mrp']
				order_qty[size]['wholesale'] += row['wholesale_price']
				order_qty[size]['retail'] += row['retail_price']
				break
	return order_qty


def get_ordered_details(items):
	items = [item.as_dict() for item in items]
	lot_wise_detail = {}
	for row in items:
		lot_wise_detail.setdefault(row['lot'], {})
		current_variant = frappe.get_cached_doc(
			"Item Variant", row['item_variant'])
		current_item_attribute_details = get_attribute_details(
			current_variant.item)
		primary_attribute = current_item_attribute_details['primary_attribute']
		for attr in current_variant.attributes:
			if attr.attribute == primary_attribute:
				size = attr.attribute_value
				if not size:
					break
				lot_wise_detail[row['lot']].setdefault(
					size, {"qty": 0})
				lot_wise_detail[row['lot']
								][size]['qty'] += row['quantity']
				break
	return lot_wise_detail


@frappe.whitelist()
def get_production_order_details(production_order):
	doc = frappe.get_doc("Production Order", production_order)
	order_qty = get_order_qty(doc.production_order_details)
	return order_qty


def has_submitted_box_sticker_for_item(item):
	item_names = item
	if not item_names:
		return False
	return bool(frappe.db.exists("Box Sticker Print", {"fg_item": ["in", item_names], "docstatus": 1}))


@frappe.whitelist()
def update_price(production_order, item_details):
	require_ppo_action_role()
	lock_production_orders(production_order)
	doc = frappe.get_doc("Production Order", production_order)
	doc.check_permission("write")
	if doc.docstatus != 1:
		frappe.throw("Price can be changed only after Production Order is submitted")
	payload = update_if_string_instance(item_details) or {}
	if "items" in payload or "lot_price_overrides" in payload:
		item_details = payload.get("items") or {}
		lot_price_payload = payload.get("lot_price_overrides")
	else:
		item_details = payload
		lot_price_payload = None
	primary = frappe.get_value("Item", doc.item, "primary_attribute")
	sales_item_price = get_sales_item_price_map(doc.item)
	box_sticker_mrp = get_box_sticker_mrp_map(production_order, doc.item)
	lots = frappe.get_all("Lot", filters={"production_order": production_order}, pluck="name")
	old_prices = {}
	new_prices = {}
	default_changes = False

	for size in item_details:
		for row in doc.production_order_details:
			attrs = get_variant_attr_details(row.item_variant)
			if attrs.get(primary) == size:
				old_prices[size] = {"mrp": flt(row.mrp),
									"wholesale": flt(row.wholesale_price),
									"retail": flt(row.retail_price)}
				selected_source = item_details[size].get(
					"selected_source")
				if selected_source == "sales_mrp":
					if sales_item_price.get(size, {}).get("sales_mrp") is None:
						frappe.throw(
							f"Sales MRP not available for size {size}")
					new_mrp = flt(sales_item_price[size]["sales_mrp"])
				elif selected_source == "box_sticker_mrp":
					if box_sticker_mrp.get(size) is None:
						frappe.throw(
							f"Box Sticker MRP not available for size {size}")
					new_mrp = flt(box_sticker_mrp[size])
				elif selected_source == "production_order_mrp":
					new_mrp = flt(row.mrp)
				else:
					frappe.throw(f"Invalid MRP source for size {size}")
				if new_mrp <= 0 and selected_source != "production_order_mrp":
					frappe.throw(f"MRP must be greater than zero for size {size}")
				new_prices[size] = {"mrp": new_mrp, "wholesale": flt(
					row.wholesale_price), "retail": flt(row.retail_price)}
				if flt(row.mrp) != new_mrp:
					default_changes = True
					row.mrp = new_mrp
				break

	from production_api.lot_pricing import get_lot_override_map, get_lot_print_state, sync_unprinted_box_sticker_prices
	old_overrides = get_lot_override_map(doc)
	override_changes = []
	if lot_price_payload is not None:
		valid_lots = set(lots)
		valid_sizes = set(get_order_qty(doc.production_order_details))
		new_overrides = {}
		for lot, size_prices in (lot_price_payload or {}).items():
			if lot not in valid_lots:
				frappe.throw(f"Lot {lot} is not linked to Production Order {production_order}")
			for size, mrp in (size_prices or {}).items():
				if mrp in (None, ""):
					continue
				if size not in valid_sizes:
					frappe.throw(f"Size {size} is not present in Production Order {production_order}")
				mrp = flt(mrp)
				if mrp <= 0:
					frappe.throw(f"MRP must be greater than zero for Lot {lot}, size {size}")
				new_overrides.setdefault(lot, {})[size] = mrp

		for lot in valid_lots:
			old_lot_prices = old_overrides.get(lot, {})
			new_lot_prices = new_overrides.get(lot, {})
			if old_lot_prices == new_lot_prices:
				continue
			if get_lot_print_state(lot, for_update=True)["locked"]:
				frappe.throw(f"Lot {lot} price is locked because Box Stickers have already been printed")
			for size in set(old_lot_prices) | set(new_lot_prices):
				if old_lot_prices.get(size) != new_lot_prices.get(size):
					override_changes.append((lot, size, old_lot_prices.get(size), new_lot_prices.get(size)))

		doc.set("lot_price_overrides", [])
		for lot in lots:
			for size, mrp in new_overrides.get(lot, {}).items():
				doc.append("lot_price_overrides", {
					"lot": lot,
					"size": size,
					"mrp": mrp,
					"changed_by": frappe.session.user,
					"changed_on": now_datetime(),
				})

	if not default_changes and not override_changes:
		return {"default_prices_updated": 0, "lot_prices_updated": 0, "box_sticker_rows_updated": 0}

	doc.save(ignore_permissions=True)
	if default_changes:
		_create_ppo_price_request(production_order, old_prices, new_prices, auto_approved=True)

	if override_changes:
		lines = ["Lot price overrides updated:"]
		for lot, size, old_mrp, new_mrp in override_changes:
			old_label = flt(old_mrp) if old_mrp is not None else "Inherited"
			new_label = flt(new_mrp) if new_mrp is not None else "Inherited"
			lines.append(f"- {lot} / {size}: {old_label} -> {new_label}")
		append_comment_log_block(doc, "\n".join(lines))

	updated_bsp_rows = 0
	lots_to_sync = lots if default_changes else sorted({change[0] for change in override_changes})
	for lot in lots_to_sync:
		updated_bsp_rows += sync_unprinted_box_sticker_prices(lot, production_order)

	return {
		"default_prices_updated": int(default_changes),
		"lot_prices_updated": len(override_changes),
		"box_sticker_rows_updated": updated_bsp_rows,
	}


def _apply_prices_to_ppo(doc, item_details, primary):
	for size in item_details:
		for row in doc.production_order_details:
			attrs = get_variant_attr_details(row.item_variant)
			if attrs.get(primary) == size:
				row.mrp = item_details[size]['mrp']
				row.wholesale_price = item_details[size]['wholesale']
				row.retail_price = item_details[size]['retail']
				break
	doc.save(ignore_permissions=True)


def _create_ppo_price_request(production_order, old_prices, new_prices, auto_approved=False):
	price_details = []
	for size in new_prices:
		old = old_prices.get(size, {})
		price_details.append({"size": size, ""
							  "old_mrp": flt(old.get("mrp")),
							  "new_mrp": flt(new_prices[size]['mrp']),
							  "old_wholesale_price": flt(old.get("wholesale")),
							  "new_wholesale_price": flt(new_prices[size]['wholesale']),
							  "old_retail_price": flt(old.get("retail")),
							  "new_retail_price": flt(new_prices[size]['retail'])})
	request = frappe.new_doc("PPO Price Request")
	request.production_order = production_order
	request.requested_by = frappe.session.user
	request.requested_at = frappe.utils.now_datetime()
	if auto_approved:
		request.status = "Approved"
		request.approved_by = frappe.session.user
		request.approved_at = frappe.utils.now_datetime()
	else:
		request.status = "Pending"
	request.set("price_details", price_details)
	request.insert(ignore_permissions=True)


@frappe.whitelist()
def update_production_order_date(production_order, date_field, new_date, reason):
	require_ppo_action_role()
	fieldname = get_tracked_date_fieldname(date_field)
	doc = frappe.get_doc("Production Order", production_order)
	doc.check_permission("write")

	if doc.docstatus != 1:
		frappe.throw("Dates can be changed only after Production Order is submitted")

	if not new_date:
		frappe.throw("New Date is required")

	reason = (reason or "").strip()
	if not reason:
		frappe.throw("Reason is required")

	previous_date = get_date_value(doc.get(fieldname))
	new_date = getdate(new_date)
	if previous_date == new_date:
		frappe.throw("New date is same as the current date")

	previous_lead_time = date_diff(doc.delivery_date, doc.posting_date)
	doc.set(fieldname, new_date)
	new_lead_time = date_diff(doc.delivery_date, doc.posting_date)
	doc.lead_time_given = new_lead_time
	doc.validate_production_dates()

	doc.append("date_change_history", {
		"date_field": TRACKED_DATE_FIELDS[fieldname],
		"previous_date": previous_date,
		"new_date": new_date,
		"reason": reason,
		"previous_lead_time": previous_lead_time,
		"new_lead_time": new_lead_time,
		"changed_by": frappe.session.user,
		"changed_on": now_datetime(),
	})
	doc.flags.allow_tracked_date_change = True
	doc.save(ignore_permissions=True)

	return {
		"date_field": TRACKED_DATE_FIELDS[fieldname],
		"previous_date": previous_date,
		"new_date": new_date,
		"previous_lead_time": previous_lead_time,
		"new_lead_time": new_lead_time,
	}


def get_tracked_date_fieldname(date_field):
	date_field = (date_field or "").strip()
	if date_field in TRACKED_DATE_FIELDS:
		return date_field
	if date_field in TRACKED_DATE_LABELS:
		return TRACKED_DATE_LABELS[date_field]
	frappe.throw("Invalid date field")


def get_date_value(value):
	return getdate(value) if value else None


QUANTITY_CHANGE_REQUESTED_BY_OPTIONS = ["Sales Team", "Planning Team", "Merch Team"]
QUANTITY_REQUEST_STATUS = "Pending Request"
QUANTITY_REQUEST_FIELD = "quantity_ratio_request"
STATUS_REQUEST_FIELD = "status_change_request"
STATUS_APPROVAL_REQUIRED_STATUSES = ["Item Changed", "Not Processed"]
STATUS_CHANGE_LOCKED_STATUSES = ["Item Changed", "Not Processed"]
SYSTEM_MANAGER_ROLE = "System Manager"


def get_quantity_approver_role():
	return (frappe.db.get_single_value("MRP Settings", "production_order_quantity_approver_role") or "").strip()


def get_ppo_approver_roles():
	return {
		role.strip()
		for fieldname in PPO_APPROVER_ROLE_FIELDS
		if (role := frappe.db.get_single_value("MRP Settings", fieldname)) and role.strip()
	}


def get_ppo_action_roles():
	settings = frappe.get_cached_doc("MRP Settings")
	return {
		row.role.strip()
		for row in settings.get("production_order_action_roles") or []
		if row.role and row.role.strip()
	}


def user_can_manage_production_order():
	user_roles = set(frappe.get_roles())
	return SYSTEM_MANAGER_ROLE in user_roles or bool(user_roles & get_ppo_action_roles())


def require_ppo_action_role():
	allowed_roles = get_ppo_action_roles()
	user_roles = set(frappe.get_roles())
	if not allowed_roles and SYSTEM_MANAGER_ROLE not in user_roles:
		frappe.throw("Configure Production Order Action Roles in MRP Settings")
	if SYSTEM_MANAGER_ROLE not in user_roles and not bool(user_roles & allowed_roles):
		frappe.throw("You do not have a configured Production Order Action Role")


def user_has_any_role(allowed_roles):
	return bool(set(frappe.get_roles()) & set(allowed_roles))


def validate_ppo_request_readiness(doc, posting_date=None):
	"""Run submission business checks before Sales sends the PPO to Merch."""
	doc._validate_mandatory()
	validate_ppo_request_links(doc)

	if not doc.production_term:
		frappe.throw("Production Term is required before requesting PPO approval")
	if frappe.get_value("Production Term", doc.production_term, "docstatus") != 1:
		frappe.throw("Selected Production Term must be submitted before requesting PPO approval")

	posting_date = posting_date or doc.posting_date
	if doc.delivery_date and posting_date and getdate(doc.delivery_date) < getdate(posting_date):
		frappe.throw("Delivery date is less than Posting Date")
	if doc.delivery_date and doc.dont_deliver_after and getdate(doc.delivery_date) > getdate(doc.dont_deliver_after):
		frappe.throw("Don't deliver after date is less than delivery date")


def validate_ppo_request_links(doc):
	"""Validate links outside save(), where Frappe has not initialized _action."""
	if doc.flags.ignore_links:
		return

	invalid_links, cancelled_links = doc.get_invalid_links()
	for child in doc.get_all_children():
		child_invalid, child_cancelled = child.get_invalid_links(
			is_submittable=doc.meta.is_submittable
		)
		invalid_links.extend(child_invalid)
		cancelled_links.extend(child_cancelled)

	if invalid_links:
		message = ", ".join(link[2] for link in invalid_links)
		frappe.throw(frappe._("Could not find {0}").format(message), frappe.LinkValidationError)
	if cancelled_links:
		message = ", ".join(link[2] for link in cancelled_links)
		frappe.throw(
			frappe._("Cannot link cancelled document: {0}").format(message),
			frappe.CancelledLinkError,
		)


def get_quantity_ratio_snapshot(doc):
	return {
		row.item_variant: (flt(row.quantity), flt(row.ratio))
		for row in doc.production_order_details
	}


def lock_production_orders(*names):
	"""Serialize status and quantity operations for the same PPOs."""
	names = sorted({name for name in names if name})
	if not names:
		return
	production_order = frappe.qb.DocType("Production Order")
	(
		frappe.qb.from_(production_order)
		.select(production_order.name)
		.where(production_order.name.isin(names))
		.orderby(production_order.name)
		.for_update()
	).run()


@frappe.whitelist()
def request_ppo_approval(production_order):
	require_ppo_action_role()

	lock_production_orders(production_order)
	doc = frappe.get_doc("Production Order", production_order)
	doc.check_permission("write")

	if doc.docstatus != 0:
		frappe.throw("Only a draft Production Order can be sent for PPO approval")
	if (doc.status or PPO_DRAFT_STATUS) != PPO_DRAFT_STATUS:
		frappe.throw("Production Order is already sent for PPO approval")

	# These are the same mandatory, link, term, and date checks that run on
	# submission. Sales must resolve them before Merch receives the request.
	request_posting_date = frappe.utils.nowdate()
	validate_ppo_request_readiness(doc, request_posting_date)

	requested_by = frappe.session.user
	requested_on = now_datetime()
	doc.db_set(
		{
			"status": PPO_REQUEST_STATUS,
			"ppo_requested_by": requested_by,
			"ppo_requested_on": requested_on,
			"posting_date": request_posting_date,
			"lead_time_given": date_diff(doc.delivery_date, request_posting_date),
		}
	)
	append_ppo_request_to_comment_log(doc, requested_by)

	return {
		"status": PPO_REQUEST_STATUS,
		"requested_by": requested_by,
		"requested_on": requested_on,
	}


@frappe.whitelist()
def request_ppo_changes(production_order, reason):
	approver_roles = get_ppo_approver_roles()
	if not approver_roles:
		frappe.throw(
			"Merch User Role and Merchandising Manager Role are not configured in MRP Settings"
		)
	if not user_has_any_role(approver_roles):
		frappe.throw(
			"Only users with the configured Merch User or Merchandising Manager role can request PPO changes"
		)

	reason = (reason or "").strip()
	if not reason:
		frappe.throw("Reason is required to request PPO changes")

	lock_production_orders(production_order)
	doc = frappe.get_doc("Production Order", production_order)
	if doc.docstatus != 0 or doc.status != PPO_REQUEST_STATUS:
		frappe.throw("Production Order does not have a pending PPO approval request")

	original_requester = doc.get("ppo_requested_by")
	doc.db_set({
		"status": PPO_DRAFT_STATUS,
		"ppo_requested_by": None,
		"ppo_requested_on": None,
	})
	append_ppo_changes_requested_to_comment_log(doc, reason, original_requester)

	return {
		"status": PPO_DRAFT_STATUS,
		"requested_changes_by": frappe.session.user,
		"reason": reason,
	}


@frappe.whitelist()
def approve_ppo(production_order):
	approver_roles = get_ppo_approver_roles()
	if not approver_roles:
		frappe.throw(
			"Merch User Role and Merchandising Manager Role are not configured in MRP Settings"
		)
	if not user_has_any_role(approver_roles):
		frappe.throw(
			"Only users with the configured Merch User or Merchandising Manager role can approve a PPO"
		)

	lock_production_orders(production_order)
	doc = frappe.get_doc("Production Order", production_order)

	if doc.docstatus != 0 or doc.status != PPO_REQUEST_STATUS:
		frappe.throw("Production Order does not have a pending PPO approval request")

	doc.flags.ignore_permissions = True
	doc.flags.allow_ppo_approval = True
	doc.submit()
	append_ppo_approval_to_comment_log(doc)

	return {
		"docstatus": doc.docstatus,
		"status": doc.status,
		"approved_by": frappe.session.user,
	}


@frappe.whitelist()
def update_quantity_and_ratio(production_order, size_quantities, size_ratios, requested_by, reason):
	require_ppo_action_role()
	lock_production_orders(production_order)
	doc = frappe.get_doc("Production Order", production_order)
	doc.check_permission("write")

	if doc.docstatus != 1:
		frappe.throw("Quantity and Ratio can be changed only after Production Order is submitted")

	if doc.status != "Open":
		frappe.throw("Quantity and Ratio update can be requested only when Production Order status is Open")

	if doc.get(TRANSFER_MARKER_FIELD):
		frappe.throw(f"Quantity is locked because it was already transferred to {doc.get(TRANSFER_MARKER_FIELD)}")

	if doc.get(QUANTITY_REQUEST_FIELD):
		frappe.throw("A Quantity and Ratio update request is already pending")
	if doc.get(STATUS_REQUEST_FIELD):
		frappe.throw("A status change request is already pending")
	if doc.get(INCOMING_TRANSFER_REQUEST_FIELD):
		frappe.throw("Approve the incoming quantity transfer before requesting a Quantity and Ratio update")

	if doc.production_ordered_details:
		frappe.throw("Cannot update quantity or ratio. Quantities are already ordered against Lots")

	if not doc.production_order_details:
		frappe.throw("Production Order has no size details to update")

	approver_role = get_quantity_approver_role()
	if not approver_role:
		frappe.throw("Set Production Order Quantity Approver Role in MRP Settings before requesting an update")

	if requested_by not in QUANTITY_CHANGE_REQUESTED_BY_OPTIONS:
		frappe.throw("Who Told to Change must be one of: " + ", ".join(QUANTITY_CHANGE_REQUESTED_BY_OPTIONS))

	reason = (reason or "").strip()
	if not reason:
		frappe.throw("Reason is required")

	size_quantities = frappe.parse_json(size_quantities) or {}
	size_ratios = frappe.parse_json(size_ratios) or {}

	rows_by_size = get_rows_by_size(doc)
	new_quantities = validate_size_quantities(size_quantities, rows_by_size)
	new_ratios = validate_size_ratios(size_ratios, rows_by_size)
	change_details = get_quantity_ratio_changes(rows_by_size, new_quantities, new_ratios)

	if not change_details["qty_changes"] and not change_details["ratio_changes"]:
		frappe.throw("No quantity or ratio was changed")
	if change_details["qty_changes"] and change_details["qty_new_total"] <= 0:
		frappe.throw("At least one size must have a quantity greater than zero")

	request = {
		"original_quantities": change_details["original_quantities"],
		"original_ratios": change_details["original_ratios"],
		"requested_quantities": change_details["requested_quantities"],
		"requested_ratios": change_details["requested_ratios"],
		"requested_by": requested_by,
		"reason": reason,
		"requested_user": frappe.session.user,
		"requested_on": str(now_datetime()),
		"previous_status": doc.status,
	}
	doc.db_set({
		QUANTITY_REQUEST_FIELD: frappe.as_json(request),
		"status": QUANTITY_REQUEST_STATUS,
	})
	append_quantity_ratio_request_to_comment_log(doc, change_details, request)

	return {
		"status": QUANTITY_REQUEST_STATUS,
		"qty_old_total": change_details["qty_old_total"],
		"qty_new_total": change_details["qty_new_total"],
	}


@frappe.whitelist()
def approve_quantity_and_ratio(production_order):
	approver_role = get_quantity_approver_role()
	if not approver_role:
		frappe.throw("Production Order Quantity Approver Role is not configured in MRP Settings")
	if approver_role not in frappe.get_roles():
		frappe.throw(f"Only users with the {approver_role} role can approve this request")

	lock_production_orders(production_order)
	doc = frappe.get_doc("Production Order", production_order)
	doc.check_permission("read")

	if doc.docstatus != 1 or doc.status != QUANTITY_REQUEST_STATUS:
		frappe.throw("Production Order does not have a pending Quantity and Ratio update request")
	if doc.get(STATUS_REQUEST_FIELD):
		frappe.throw("Production Order has a pending status change request, not a Quantity and Ratio request")
	if doc.get(INCOMING_TRANSFER_REQUEST_FIELD):
		frappe.throw("Approve the incoming quantity transfer before approving a Quantity and Ratio request")
	if doc.get(TRANSFER_MARKER_FIELD):
		frappe.throw(f"Quantity is locked because it was already transferred to {doc.get(TRANSFER_MARKER_FIELD)}")
	if doc.production_ordered_details:
		frappe.throw("Cannot approve the request. Quantities are already ordered against Lots")

	request = frappe.parse_json(doc.get(QUANTITY_REQUEST_FIELD)) or {}
	if not request:
		frappe.throw("Pending Quantity and Ratio request details are missing")
	if request.get("previous_status") != "Open":
		frappe.throw("Pending Quantity and Ratio request has an invalid previous status")

	rows_by_size = get_rows_by_size(doc)
	original_quantities = validate_size_quantities(request.get("original_quantities") or {}, rows_by_size)
	original_ratios = validate_size_ratios(request.get("original_ratios") or {}, rows_by_size)
	new_quantities = validate_size_quantities(request.get("requested_quantities") or {}, rows_by_size)
	new_ratios = validate_size_ratios(request.get("requested_ratios") or {}, rows_by_size)

	for size, row in rows_by_size.items():
		if size not in original_quantities or size not in original_ratios:
			frappe.throw(f"Pending request is missing the original values for size {size}")
		if flt(row.quantity) != flt(original_quantities[size]) or flt(row.ratio) != flt(original_ratios[size]):
			frappe.throw("Production Order quantity or ratio changed while the request was pending. Create a new request")

	change_details = get_quantity_ratio_changes(rows_by_size, new_quantities, new_ratios)
	if not change_details["qty_changes"] and not change_details["ratio_changes"]:
		frappe.throw("Pending request does not contain any quantity or ratio change")
	if change_details["qty_changes"] and change_details["qty_new_total"] <= 0:
		frappe.throw("At least one size must have a quantity greater than zero")

	for size, row in rows_by_size.items():
		row.quantity = change_details["requested_quantities"][size]
		row.ratio = change_details["requested_ratios"][size]

	doc.status = "Open"
	doc.set(QUANTITY_REQUEST_FIELD, None)
	doc.flags.allow_quantity_ratio_approval = True
	doc.save(ignore_permissions=True)

	approved_by = frappe.session.user
	append_quantity_ratio_to_comment_log(doc, change_details, request, approved_by)

	return {
		"status": doc.status,
		"qty_old_total": change_details["qty_old_total"],
		"qty_new_total": change_details["qty_new_total"],
	}


def get_rows_by_size(doc):
	"""Map each size (variant's primary attribute value) to its per-size row."""
	primary_attribute = frappe.get_value("Item", doc.item, "primary_attribute")
	rows_by_size = {}
	for row in doc.production_order_details:
		size = get_variant_attr_details(row.item_variant).get(primary_attribute) or row.item_variant
		if size in rows_by_size:
			frappe.throw(f"Production Order has more than one row for size {size}")
		rows_by_size[size] = row
	return rows_by_size


def validate_size_quantities(size_quantities, rows_by_size):
	"""Check every payload size exists and every quantity is a whole number >= 0."""
	new_quantities = {}
	for size, qty in size_quantities.items():
		if size not in rows_by_size:
			frappe.throw(f"Size {size} is not part of this Production Order")
		qty = flt(qty)
		if qty < 0:
			frappe.throw(f"Quantity for size {size} cannot be negative")
		if qty != cint(qty):
			frappe.throw(f"Quantity for size {size} must be a whole number")
		new_quantities[size] = cint(qty)
	return new_quantities


def validate_size_ratios(size_ratios, rows_by_size):
	"""Check every payload size exists and every ratio is a number >= 0."""
	new_ratios = {}
	for size, ratio in size_ratios.items():
		if size not in rows_by_size:
			frappe.throw(f"Size {size} is not part of this Production Order")
		ratio = flt(ratio)
		if ratio < 0:
			frappe.throw(f"Ratio for size {size} cannot be negative")
		new_ratios[size] = ratio
	return new_ratios


def get_quantity_ratio_changes(rows_by_size, new_quantities, new_ratios):
	details = {
		"original_quantities": {},
		"original_ratios": {},
		"requested_quantities": {},
		"requested_ratios": {},
		"qty_changes": [],
		"ratio_changes": [],
		"qty_old_total": 0,
		"qty_new_total": 0,
	}
	for size, row in rows_by_size.items():
		old_qty = flt(row.quantity)
		new_qty = new_quantities.get(size, old_qty)
		old_ratio = flt(row.ratio)
		new_ratio = new_ratios.get(size, old_ratio)

		details["original_quantities"][size] = old_qty
		details["original_ratios"][size] = old_ratio
		details["requested_quantities"][size] = new_qty
		details["requested_ratios"][size] = new_ratio
		details["qty_old_total"] += old_qty
		details["qty_new_total"] += new_qty

		if new_qty != old_qty:
			details["qty_changes"].append({"size": size, "old_qty": old_qty, "new_qty": new_qty})
		if new_ratio != old_ratio:
			details["ratio_changes"].append({"size": size, "old_ratio": old_ratio, "new_ratio": new_ratio})

	return details


def get_quantity_ratio_change_lines(change_details):
	lines = []
	for change in change_details["qty_changes"]:
		lines.append(
			f"Quantity {change['size']}: {format_comment_qty(change['old_qty'])} -> {format_comment_qty(change['new_qty'])}")
	if change_details["qty_changes"]:
		lines.append(
			f"Quantity Total: {format_comment_qty(change_details['qty_old_total'])} -> "
			f"{format_comment_qty(change_details['qty_new_total'])}"
		)
	for change in change_details["ratio_changes"]:
		lines.append(
			f"Ratio {change['size']}: {format_comment_qty(change['old_ratio'])} -> {format_comment_qty(change['new_ratio'])}")
	return lines


def append_quantity_ratio_request_to_comment_log(doc, change_details, request):
	log_date = frappe.utils.formatdate(frappe.utils.nowdate(), "dd-mm-yyyy")
	lines = [f"[{log_date}] Quantity/Ratio Update Requested - {request['requested_user']}"]
	lines.extend(get_quantity_ratio_change_lines(change_details))
	lines.extend([
		f"Who Told to Change: {request['requested_by']}",
		f"Reason: {request['reason']}",
	])
	append_comment_log_block(doc, "\n".join(lines))


def append_quantity_ratio_to_comment_log(doc, change_details, request, approved_by):
	log_date = frappe.utils.formatdate(frappe.utils.nowdate(), "dd-mm-yyyy")
	lines = [f"[{log_date}] Quantity/Ratio Update Approved - {approved_by}"]
	lines.extend(get_quantity_ratio_change_lines(change_details))
	lines.extend([
		f"Who Told to Change: {request['requested_by']}",
		f"Requested By: {request['requested_user']}",
		f"Reason: {request['reason']}",
	])
	append_comment_log_block(doc, "\n".join(lines))


def append_comment_log_block(doc, block):
	"""Append a plain-text block to the read-only 'comment_log' field.

	The doc is submitted and 'comment_log' is read_only, so write via db_set."""
	existing = doc.comment_log or ""
	doc.db_set("comment_log", f"{existing}\n{block}" if existing else block)


def append_ppo_request_to_comment_log(doc, requested_by):
	log_date = frappe.utils.formatdate(frappe.utils.nowdate(), "dd-mm-yyyy")
	append_comment_log_block(
		doc,
		f"[{log_date}] PPO Approval Requested - {requested_by}",
	)


def append_ppo_approval_to_comment_log(doc):
	log_date = frappe.utils.formatdate(frappe.utils.nowdate(), "dd-mm-yyyy")
	lines = [
		f"[{log_date}] PPO Approved and Submitted - {frappe.session.user}",
	]
	if doc.get("ppo_requested_by"):
		lines.append(f"Requested By: {doc.get('ppo_requested_by')}")
	append_comment_log_block(doc, "\n".join(lines))


def append_ppo_changes_requested_to_comment_log(doc, reason, original_requester=None):
	log_date = frappe.utils.formatdate(frappe.utils.nowdate(), "dd-mm-yyyy")
	lines = [
		f"[{log_date}] PPO Changes Requested - {frappe.session.user}",
		f"Reason: {reason}",
	]
	if original_requester:
		lines.append(f"Original Request By: {original_requester}")
	append_comment_log_block(doc, "\n".join(lines))


def format_comment_qty(value):
	value = flt(value)
	if value == cint(value):
		return str(cint(value))
	return str(value)


@frappe.whitelist()
def create_lot(production_order, lot_name):
	require_ppo_action_role()
	if frappe.db.exists("Lot", lot_name):
		frappe.throw(frappe._("Lot Name {0} already exists").format(lot_name))
	po_doc = frappe.get_doc("Production Order", production_order)
	lot = frappe.new_doc("Lot")
	lot.lot_name = lot_name
	lot.production_order = production_order
	lot.item = po_doc.item
	lot.status = "Open"
	lot.insert(ignore_permissions=True)
	return lot.name


@frappe.whitelist()
def link_lot(production_order, lot_name):
	require_ppo_action_role()
	lot = frappe.get_doc("Lot", lot_name)
	po_doc = frappe.get_doc("Production Order", production_order)
	if lot.item and lot.item != po_doc.item:
		frappe.throw("This Lot is linked with a different Item")
	if lot.production_order and lot.production_order != production_order:
		frappe.throw(
			f"This Lot is already linked with Production Order {lot.production_order}")
	lot.production_order = production_order
	if not lot.item:
		lot.item = po_doc.item
	lot.status = "Open"
	lot.save(ignore_permissions=True)
	return lot.name


# "Closed" exists in the field options but is reserved for Finishing Plan
# automation - it cannot be set manually through change_status.
CHANGEABLE_PO_STATUSES = ["Open", "Item Changed", "Not Processed"]


def get_linked_lots(production_order):
	return frappe.get_all(
		"Lot",
		filters={"production_order": production_order},
		pluck="name",
		order_by="name asc",
	)


def validate_status_change_has_no_linked_lot(production_order, action="changed"):
	linked_lots = get_linked_lots(production_order)
	if linked_lots:
		frappe.throw(
			f"Status cannot be {action} because Production Order is linked to Lot(s): "
			+ ", ".join(linked_lots)
		)


@frappe.whitelist()
def change_status(production_order, new_status, reason):
	require_ppo_action_role()
	lock_production_orders(production_order)
	doc = frappe.get_doc("Production Order", production_order)
	doc.check_permission("write")

	if doc.docstatus != 1:
		frappe.throw("Status can be changed only after Production Order is submitted")
	validate_status_change_has_no_linked_lot(production_order)

	if doc.status in STATUS_CHANGE_LOCKED_STATUSES:
		frappe.throw(f"Status cannot be changed after {doc.status} is approved")

	if doc.get(TRANSFER_MARKER_FIELD):
		frappe.throw(f"Status is locked because quantity was already transferred to {doc.get(TRANSFER_MARKER_FIELD)}")

	if (
		doc.status == QUANTITY_REQUEST_STATUS
		or doc.get(QUANTITY_REQUEST_FIELD)
		or doc.get(STATUS_REQUEST_FIELD)
	):
		frappe.throw("Status cannot be changed while another request is pending")
	if doc.get(INCOMING_TRANSFER_REQUEST_FIELD):
		frappe.throw("Status cannot be changed while an incoming quantity transfer is pending")

	if new_status not in CHANGEABLE_PO_STATUSES:
		frappe.throw("Status must be one of: " + ", ".join(CHANGEABLE_PO_STATUSES))

	reason = (reason or "").strip()
	if not reason:
		frappe.throw("Reason is required")

	old_status = doc.status or ""
	if new_status == old_status:
		frappe.throw("New status is same as the current status")

	if new_status in STATUS_APPROVAL_REQUIRED_STATUSES:
		approver_role = get_quantity_approver_role()
		if not approver_role:
			frappe.throw("Set Production Order Quantity Approver Role in MRP Settings before requesting a status change")

		request = {
			"previous_status": old_status,
			"requested_status": new_status,
			"reason": reason,
			"requested_user": frappe.session.user,
			"requested_on": str(now_datetime()),
		}
		doc.db_set({
			STATUS_REQUEST_FIELD: frappe.as_json(request),
			"status": QUANTITY_REQUEST_STATUS,
		})
		append_status_change_request_to_comment_log(doc, request)
		return {
			"old_status": old_status,
			"new_status": QUANTITY_REQUEST_STATUS,
			"requested_status": new_status,
			"approval_required": True,
		}

	doc.db_set("status", new_status)
	log_date = frappe.utils.formatdate(frappe.utils.nowdate(), "dd-mm-yyyy")
	append_comment_log_block(doc, "\n".join([
		f"[{log_date}] Status Changed - {frappe.session.user}",
		f"Status: {old_status or 'None'} -> {new_status}",
		f"Reason: {reason}",
	]))

	return {
		"old_status": old_status,
		"new_status": new_status,
		"approval_required": False,
	}


@frappe.whitelist()
def approve_status_change(production_order):
	approver_role = get_quantity_approver_role()
	if not approver_role:
		frappe.throw("Production Order Quantity Approver Role is not configured in MRP Settings")
	if approver_role not in frappe.get_roles():
		frappe.throw(f"Only users with the {approver_role} role can approve this request")

	lock_production_orders(production_order)
	doc = frappe.get_doc("Production Order", production_order)
	doc.check_permission("read")

	if doc.docstatus != 1 or doc.status != QUANTITY_REQUEST_STATUS:
		frappe.throw("Production Order does not have a pending status change request")
	validate_status_change_has_no_linked_lot(production_order, action="approved")
	if doc.get(TRANSFER_MARKER_FIELD):
		frappe.throw(f"Status is locked because quantity was already transferred to {doc.get(TRANSFER_MARKER_FIELD)}")
	if doc.get(QUANTITY_REQUEST_FIELD):
		frappe.throw("Production Order has a pending Quantity and Ratio request, not a status change request")

	request = frappe.parse_json(doc.get(STATUS_REQUEST_FIELD)) or {}
	if not request:
		frappe.throw("Pending status change request details are missing")

	previous_status = request.get("previous_status")
	requested_status = request.get("requested_status")
	if not previous_status or requested_status not in STATUS_APPROVAL_REQUIRED_STATUSES:
		frappe.throw("Pending status change request is invalid")

	doc.status = requested_status
	doc.set(STATUS_REQUEST_FIELD, None)
	doc.flags.allow_status_change_approval = True
	doc.save(ignore_permissions=True)

	approved_by = frappe.session.user
	append_status_change_approved_to_comment_log(doc, request, approved_by)

	return {
		"old_status": previous_status,
		"new_status": requested_status,
	}


def append_status_change_request_to_comment_log(doc, request):
	log_date = frappe.utils.formatdate(frappe.utils.nowdate(), "dd-mm-yyyy")
	append_comment_log_block(doc, "\n".join([
		f"[{log_date}] Status Change Requested - {request['requested_user']}",
		f"Status: {request['previous_status']} -> {request['requested_status']}",
		f"Reason: {request['reason']}",
	]))


def append_status_change_approved_to_comment_log(doc, request, approved_by):
	log_date = frappe.utils.formatdate(frappe.utils.nowdate(), "dd-mm-yyyy")
	append_comment_log_block(doc, "\n".join([
		f"[{log_date}] Status Change Approved - {approved_by}",
		f"Status: {request['previous_status']} -> {request['requested_status']}",
		f"Requested By: {request['requested_user']}",
		f"Reason: {request['reason']}",
	]))


# A PPO can push its quantity out only from these statuses. "Open" is still live and
# "Closed" is Finishing Plan automation, so neither may be re-routed.
TRANSFERABLE_PO_STATUSES = ["Item Changed", "Not Processed"]
TRANSFER_TARGET_STATUSES = ["Open", "Item Changed", "Not Processed"]

TRANSFER_MARKER_FIELD = "transferred_to_ppo"
INCOMING_TRANSFER_REQUEST_FIELD = "incoming_quantity_transfer_request"


def has_transfer_marker_field():
	"""The one-shot marker is a DocType change, so it is absent until migrate has run."""
	return frappe.get_meta("Production Order").has_field(TRANSFER_MARKER_FIELD)


def has_incoming_transfer_request_field():
	return frappe.get_meta("Production Order").has_field(INCOMING_TRANSFER_REQUEST_FIELD)


def get_alternative_items(item):
	"""Items configured as alternatives of `item`.

	"Item Alternative" here is this app's own doctype (item / alternative_item), not
	ERPNext's - it has no two_way flag, so only the forward leg is resolved and the
	reciprocal row is maintained by hand. Same resolution as
	finishing_plan.check_is_alternative_item. The doctype has no validate(), so
	duplicate, empty and self-referencing rows are possible and are dropped here."""
	items = frappe.db.get_all("Item Alternative", filters={"item": item}, pluck="alternative_item")
	return sorted({alternative for alternative in items if alternative and alternative != item})


def get_transfer_quantities(doc):
	"""Per-size quantity this Production Order would push out.

	Rows are seeded for every size on save, so the zero rows carry no intent and are skipped."""
	transfers = {}
	for size, row in get_rows_by_size(doc).items():
		qty = flt(row.quantity)
		if qty > 0:
			transfers[size] = qty
	return transfers


@frappe.whitelist()
def transfer_quantity_to_ppo(source_production_order, target_production_order, reason):
	require_ppo_action_role()
	if not target_production_order:
		frappe.throw("Target Production Order is required")
	if target_production_order == source_production_order:
		frappe.throw("Target Production Order must be different from this Production Order")

	lock_production_orders(source_production_order, target_production_order)
	doc = frappe.get_doc("Production Order", source_production_order)
	doc.check_permission("write")

	if not has_transfer_marker_field():
		frappe.throw("Cannot transfer quantity. Run bench migrate first - the transfer marker field is missing")
	if not has_incoming_transfer_request_field():
		frappe.throw("Cannot transfer quantity. Run bench migrate first - the incoming transfer request field is missing")

	if doc.docstatus != 1:
		frappe.throw("Quantity can be transferred only after Production Order is submitted")

	if doc.status not in TRANSFERABLE_PO_STATUSES:
		frappe.throw("Quantity can be transferred only when status is one of: " + ", ".join(TRANSFERABLE_PO_STATUSES))

	if doc.get(TRANSFER_MARKER_FIELD):
		frappe.throw(f"Quantity is already requested or transferred to {doc.get(TRANSFER_MARKER_FIELD)}")
	if doc.get(INCOMING_TRANSFER_REQUEST_FIELD):
		frappe.throw("Approve the incoming quantity transfer before transferring this Production Order")

	if doc.production_ordered_details:
		frappe.throw("Cannot transfer quantity. Quantities are already ordered against Lots")

	if not doc.production_order_details:
		frappe.throw("Production Order has no size details to transfer")

	reason = (reason or "").strip()
	if not reason:
		frappe.throw("Reason is required")

	if not frappe.db.exists("Production Order", target_production_order):
		frappe.throw(f"Production Order {target_production_order} does not exist")

	target = frappe.get_doc("Production Order", target_production_order)
	target.check_permission("write")

	if target.docstatus != 1:
		frappe.throw(f"Target Production Order {target.name} is not submitted")

	if target.status not in TRANSFER_TARGET_STATUSES:
		frappe.throw(f"Target Production Order {target.name} is Closed or has a pending update request")

	if target.get(TRANSFER_MARKER_FIELD):
		frappe.throw(f"Target Production Order {target.name} already transferred its quantity and is locked")
	if target.get(INCOMING_TRANSFER_REQUEST_FIELD):
		frappe.throw(f"Target Production Order {target.name} already has a pending quantity transfer request")

	# The dialog's get_query is advisory only, so the alternative set is re-asserted here.
	if target.item not in get_alternative_items(doc.item):
		frappe.throw(f"Item {target.item} is not an alternative item of {doc.item}")

	approver_role = get_quantity_approver_role()
	if not approver_role:
		frappe.throw("Set Production Order Quantity Approver Role in MRP Settings before requesting a quantity transfer")

	transfers = get_transfer_quantities(doc)
	if not transfers:
		frappe.throw("Production Order has no quantity to transfer")

	target_rows_by_size = get_rows_by_size(target)
	validate_transfer_target_sizes(target, transfers, target_rows_by_size)

	changes = []
	for size, qty in transfers.items():
		old_qty = flt(target_rows_by_size[size].quantity) if size in target_rows_by_size else 0
		changes.append({
			"size": size,
			"qty": qty,
			"old_qty": old_qty,
			"new_qty": old_qty + qty,
		})

	request = {
		"transfer_reference": frappe.generate_hash(length=10),
		"source_production_order": doc.name,
		"source_status": doc.status,
		"target_previous_status": target.status,
		"transfers": transfers,
		"target_original_quantities": {
			change["size"]: change["old_qty"] for change in changes
		},
		"requested_user": frappe.session.user,
		"requested_on": str(now_datetime()),
		"reason": reason,
	}
	target.db_set({
		INCOMING_TRANSFER_REQUEST_FIELD: frappe.as_json(request),
		"status": QUANTITY_REQUEST_STATUS,
	})
	doc.db_set(TRANSFER_MARKER_FIELD, target.name)

	return {
		"target_production_order": target.name,
		"requested": {change["size"]: change["qty"] for change in changes},
		"status": "Pending Approval",
	}


@frappe.whitelist()
def approve_quantity_transfer(production_order):
	approver_role = get_quantity_approver_role()
	if not approver_role:
		frappe.throw("Production Order Quantity Approver Role is not configured in MRP Settings")
	if approver_role not in frappe.get_roles():
		frappe.throw(f"Only users with the {approver_role} role can approve this request")

	target = frappe.get_doc("Production Order", production_order)
	request = frappe.parse_json(target.get(INCOMING_TRANSFER_REQUEST_FIELD)) or {}
	source_name = request.get("source_production_order")
	if not source_name:
		frappe.throw("Pending quantity transfer request details are missing")

	lock_production_orders(source_name, production_order)
	target = frappe.get_doc("Production Order", production_order)
	target.check_permission("read")
	source = frappe.get_doc("Production Order", source_name)
	request = frappe.parse_json(target.get(INCOMING_TRANSFER_REQUEST_FIELD)) or {}
	if request.get("source_production_order") != source_name:
		frappe.throw("Quantity transfer request changed while approval was pending. Reload and try again")

	target_previous_status = request.get("target_previous_status")
	if target_previous_status not in TRANSFER_TARGET_STATUSES:
		frappe.throw("Pending quantity transfer request has an invalid destination status")
	if target.docstatus != 1 or target.status != QUANTITY_REQUEST_STATUS:
		frappe.throw("Destination Production Order does not have a pending quantity transfer request")
	if target.get(TRANSFER_MARKER_FIELD):
		frappe.throw(f"Destination Production Order already transferred its quantity to {target.get(TRANSFER_MARKER_FIELD)}")
	if source.docstatus != 1 or source.status not in TRANSFERABLE_PO_STATUSES:
		frappe.throw("Source Production Order is no longer eligible to transfer quantity")
	if source.get(TRANSFER_MARKER_FIELD) != target.name:
		frappe.throw("Source Production Order transfer marker does not match this request")
	if source.transferred_on:
		frappe.throw("This quantity transfer was already approved")
	if target.item not in get_alternative_items(source.item):
		frappe.throw(f"Item {target.item} is not an alternative item of {source.item}")

	transfers = {
		size: flt(qty)
		for size, qty in (request.get("transfers") or {}).items()
		if flt(qty) > 0
	}
	if not transfers:
		frappe.throw("Pending quantity transfer request has no quantity")

	target_rows_by_size = get_rows_by_size(target)
	missing_sizes = validate_transfer_target_sizes(target, transfers, target_rows_by_size)
	original_quantities = request.get("target_original_quantities") or {}
	for size in transfers:
		if size not in original_quantities:
			frappe.throw(f"Pending quantity transfer request is missing the original quantity for size {size}")
		current_qty = flt(target_rows_by_size[size].quantity) if size in target_rows_by_size else 0
		if current_qty != flt(original_quantities[size]):
			frappe.throw(
				f"Destination quantity for size {size} changed while approval was pending. Create a new transfer request")

	if missing_sizes:
		target_rows_by_size.update(add_target_size_rows(target, missing_sizes))

	changes = []
	for size, qty in transfers.items():
		row = target_rows_by_size[size]
		old_qty = flt(row.quantity)
		row.quantity = old_qty + qty
		changes.append({
			"size": size,
			"qty": qty,
			"old_qty": old_qty,
			"new_qty": flt(row.quantity),
		})

	target.set(INCOMING_TRANSFER_REQUEST_FIELD, None)
	target.status = target_previous_status
	target.flags.allow_quantity_transfer = True
	target.flags.allow_quantity_transfer_approval = True
	target.save(ignore_permissions=True)
	approved_by = frappe.session.user
	approved_on = now_datetime()
	source.db_set("transferred_on", approved_on)
	append_quantity_transfer_history(
		source,
		target,
		changes,
		request,
		approved_by,
		approved_on,
	)

	return {
		"source_production_order": source.name,
		"target_production_order": target.name,
		"status": target.status,
		"transferred": {change["size"]: change["qty"] for change in changes},
	}


def validate_transfer_target_sizes(target, transfers, target_rows_by_size):
	missing_sizes = [size for size in transfers if size not in target_rows_by_size]
	if missing_sizes:
		target_sizes = get_attribute_details(target.item).get("primary_attribute_values", [])
		unknown_sizes = [size for size in missing_sizes if size not in target_sizes]
		if unknown_sizes:
			frappe.throw(
				f"Item {target.item} of Production Order {target.name} is not made in size {', '.join(unknown_sizes)}")
	return missing_sizes


def add_target_size_rows(target, sizes):
	"""Append rows for sizes the target has no row for, and return them keyed by size.

	update_order seeds a row per size on save, so this only fires when the target was
	saved before its item gained the size. The variant, stage and price seeding mirror
	update_order so the new rows are indistinguishable from the seeded ones; quantity and
	ratio start at 0 because the transfer adds the quantity and must not invent a ratio."""
	item_doc = frappe.get_cached_doc("Item", target.item)
	pack_out_stage = frappe.db.get_single_value("IPD Settings", "default_pack_out_stage")
	sales_item_price = get_sales_item_price_map(target.item)

	new_rows = {}
	for size in sizes:
		price_row = sales_item_price.get(size, {})
		new_rows[size] = target.append("production_order_details", {
			"item_variant": get_or_create_variant(
				target.item, build_variant_attributes({item_doc.primary_attribute: size}, pack_out_stage, item_doc)
			),
			"quantity": 0,
			"ratio": 0,
			"mrp": 0,
			"wholesale_price": price_row.get("wholesale", 0),
			"retail_price": price_row.get("retail", 0),
		})
	return new_rows


ALTERNATIVE_PPO_COPY_FIELDS = (
	"naming_series",
	"fabric",
	"dia",
	"gsm",
	"delivery_date",
	"posting_date",
	"lead_time_given",
	"dont_deliver_after",
	"production_term",
	"comments",
	"skip_box_sticker_print",
)


def _normalise_alternative_transfers(transfers):
	transfers = update_if_string_instance(transfers) or {}
	transfers = {
		str(size): flt(quantity)
		for size, quantity in transfers.items()
		if flt(quantity) > 0
	}
	if not transfers:
		frappe.throw("Enter a quantity to move to the alternative item")
	return transfers


def _get_lot_packing_combo(lot):
	production_detail = frappe.db.get_value("Lot", lot, "production_detail")
	if not production_detail:
		frappe.throw(f"Lot {lot} has no Item Production Detail")
	packing_combo = flt(
		frappe.db.get_value(
			"Item Production Detail", production_detail, "packing_combo"
		)
	)
	if packing_combo <= 0:
		frappe.throw(
			f"Set a valid Packing Combo in Item Production Detail {production_detail}"
		)
	return packing_combo


def _piece_transfers_to_boxes(piece_transfers, packing_combo):
	return {
		size: round(piece_quantity / packing_combo, 6)
		for size, piece_quantity in piece_transfers.items()
	}


def _validate_alternative_ppo_pair(source, target, source_lot, target_lot):
	if source.docstatus != 1 or target.docstatus != 1:
		frappe.throw("Alternative quantity can be moved only between submitted Production Orders")
	if frappe.db.get_value("Lot", source_lot, "production_order") != source.name:
		frappe.throw(f"Source Lot {source_lot} is not linked to Production Order {source.name}")
	if frappe.db.get_value("Lot", target_lot, "production_order") != target.name:
		frappe.throw(f"Alternative Lot {target_lot} is not linked to Production Order {target.name}")
	if target.item not in get_alternative_items(source.item):
		frappe.throw(f"Item {target.item} is not an alternative item of {source.item}")
	for doc in (source, target):
		if (
			doc.status == QUANTITY_REQUEST_STATUS
			or doc.get(QUANTITY_REQUEST_FIELD)
			or doc.get(STATUS_REQUEST_FIELD)
			or doc.get(INCOMING_TRANSFER_REQUEST_FIELD)
		):
			frappe.throw(f"Production Order {doc.name} has a pending request")
		if doc.get(TRANSFER_MARKER_FIELD):
			frappe.throw(f"Production Order {doc.name} is locked by another quantity transfer")


def _append_alternative_target_size_row(target, source_row, size):
	item_doc = frappe.get_cached_doc("Item", target.item)
	pack_out_stage = frappe.db.get_single_value("IPD Settings", "default_pack_out_stage")
	return target.append("production_order_details", {
		"item_variant": get_or_create_variant(
			target.item,
			build_variant_attributes(
				{item_doc.primary_attribute: size},
				pack_out_stage,
				item_doc,
			),
		),
		"quantity": 0,
		"ratio": flt(source_row.ratio),
		"mrp": flt(source_row.mrp),
		"production_order_mrp": flt(source_row.production_order_mrp),
		"wholesale_price": flt(source_row.wholesale_price),
		"retail_price": flt(source_row.retail_price),
	})


def apply_alternative_plan_ppo_transfer(
	source_production_order,
	target_production_order,
	source_lot,
	target_lot,
	transfers,
	reason,
):
	"""Convert finishing pieces to each Lot's box UOM and persist paired PPO movements."""
	piece_transfers = _normalise_alternative_transfers(transfers)
	requested_source_box_transfers = _piece_transfers_to_boxes(
		piece_transfers, _get_lot_packing_combo(source_lot)
	)
	target_box_transfers = _piece_transfers_to_boxes(
		piece_transfers, _get_lot_packing_combo(target_lot)
	)
	lock_production_orders(source_production_order, target_production_order)
	source = frappe.get_doc("Production Order", source_production_order)
	target = frappe.get_doc("Production Order", target_production_order)
	_validate_alternative_ppo_pair(source, target, source_lot, target_lot)

	source_rows = get_rows_by_size(source)
	target_rows = get_rows_by_size(target)
	source_box_transfers = {}
	changes = []
	for size, piece_quantity in piece_transfers.items():
		requested_source_quantity = requested_source_box_transfers[size]
		target_quantity = target_box_transfers[size]
		source_row = source_rows.get(size)
		if not source_row:
			frappe.throw(f"Size {size} is not present in source Production Order {source.name}")
		source_before = flt(source_row.quantity)
		# The PPO contains the original planned boxes. Actual finishing output can exceed
		# that plan, so reduce only the boxes still present and clamp the source at zero.
		# The target PPO continues to receive the full piece conversion using its own combo.
		source_quantity = min(requested_source_quantity, max(source_before, 0))
		source_box_transfers[size] = source_quantity
		target_row = target_rows.get(size)
		if not target_row:
			target_row = _append_alternative_target_size_row(target, source_row, size)
			target_rows[size] = target_row
		target_before = flt(target_row.quantity)
		changes.append({
			"size": size,
			"qty": target_quantity,
			"piece_qty": piece_quantity,
			"source_qty": source_quantity,
			"source_requested_qty": requested_source_quantity,
			"target_qty": target_quantity,
			"old_qty": target_before,
			"new_qty": target_before + target_quantity,
			"source_old_qty": source_before,
			"source_new_qty": source_before - source_quantity,
		})
		source_row.quantity = source_before - source_quantity
		target_row.quantity = target_before + target_quantity

	source.flags.allow_quantity_transfer = True
	target.flags.allow_quantity_transfer = True
	source.save(ignore_permissions=True)
	target.save(ignore_permissions=True)

	approved_on = now_datetime()
	request = {
		"transfer_reference": frappe.generate_hash(length=10),
		"source_production_order": source.name,
		"source_status": source.status,
		"target_previous_status": target.status,
		"transfers": target_box_transfers,
		"piece_transfers": piece_transfers,
		"source_box_transfers": source_box_transfers,
		"requested_source_box_transfers": requested_source_box_transfers,
		"target_box_transfers": target_box_transfers,
		"requested_user": frappe.session.user,
		"requested_on": str(approved_on),
		"reason": reason,
	}
	append_quantity_transfer_history(
		source,
		target,
		changes,
		request,
		frappe.session.user,
		approved_on,
	)
	return {
		"source_production_order": source.name,
		"target_production_order": target.name,
		"transferred": piece_transfers,
		"source_boxes": source_box_transfers,
		"requested_source_boxes": requested_source_box_transfers,
		"target_boxes": target_box_transfers,
	}


def create_alternative_plan_production_order(
	source_production_order,
	source_lot,
	target_lot,
	alternative_item,
	transfers,
	finishing_plan,
):
	"""Clone PPO business terms for an alternative item, submit it, link its Lot, and move qty."""
	transfers = _normalise_alternative_transfers(transfers)
	lock_production_orders(source_production_order)
	source = frappe.get_doc("Production Order", source_production_order)
	if source.docstatus != 1:
		frappe.throw(f"Source Production Order {source.name} must be submitted")
	if frappe.db.get_value("Lot", source_lot, "production_order") != source.name:
		frappe.throw(f"Source Lot {source_lot} is not linked to Production Order {source.name}")
	if alternative_item not in get_alternative_items(source.item):
		frappe.throw(f"Item {alternative_item} is not an alternative item of {source.item}")

	source_rows = get_rows_by_size(source)
	target_item_doc = frappe.get_cached_doc("Item", alternative_item)
	target_sizes = set(get_attribute_details(alternative_item).get("primary_attribute_values", []))
	invalid_sizes = [size for size in transfers if size not in target_sizes]
	if invalid_sizes:
		frappe.throw(
			f"Item {alternative_item} is not made in size {', '.join(invalid_sizes)}"
		)
	for size in transfers:
		if size not in source_rows:
			frappe.throw(f"Size {size} is not present in source Production Order {source.name}")

	target = frappe.new_doc("Production Order")
	for fieldname in ALTERNATIVE_PPO_COPY_FIELDS:
		target.set(fieldname, source.get(fieldname))
	target.naming_series = target.naming_series or "PPO-"
	target.item = alternative_item

	pack_out_stage = frappe.db.get_single_value("IPD Settings", "default_pack_out_stage")
	source_primary = frappe.get_value("Item", source.item, "primary_attribute")
	seen_sizes = set()
	for source_row in source.production_order_details:
		attrs = get_variant_attr_details(source_row.item_variant)
		size = attrs.get(source_primary)
		if not size or size in seen_sizes or size not in target_sizes:
			continue
		seen_sizes.add(size)
		target.append("production_order_details", {
			"item_variant": get_or_create_variant(
				alternative_item,
				build_variant_attributes(
					{target_item_doc.primary_attribute: size},
					pack_out_stage,
					target_item_doc,
				),
			),
			"quantity": 0,
			"ratio": flt(source_row.ratio),
			"mrp": flt(source_row.mrp),
			"production_order_mrp": flt(source_row.production_order_mrp),
			"wholesale_price": flt(source_row.wholesale_price),
			"retail_price": flt(source_row.retail_price),
		})

	missing_target_rows = [size for size in transfers if size not in seen_sizes]
	if missing_target_rows:
		frappe.throw(
			f"Could not copy Production Order rows for size {', '.join(missing_target_rows)}"
		)

	from production_api.lot_pricing import get_effective_lot_price_map
	source_lot_prices = get_effective_lot_price_map(source_lot, source.name)
	target.insert(ignore_permissions=True)
	target.status = PPO_REQUEST_STATUS
	target.flags.ignore_permissions = True
	target.flags[SYSTEM_GENERATED_ALTERNATIVE_PPO_FLAG] = True
	target.submit()

	lot_doc = frappe.get_doc("Lot", target_lot)
	if lot_doc.production_order and lot_doc.production_order != target.name:
		frappe.throw(
			f"Alternative Lot {target_lot} is already linked to Production Order {lot_doc.production_order}"
		)
	if lot_doc.item != alternative_item:
		frappe.throw(f"Alternative Lot {target_lot} is linked with a different Item")
	lot_doc.production_order = target.name
	lot_doc.status = "Open"
	lot_doc.save(ignore_permissions=True)

	# The Lot save inserts ordered-quantity rows directly into the submitted PPO, so reload
	# before saving price overrides to preserve those rows in the parent document.
	target = frappe.get_doc("Production Order", target.name)
	target_rows = get_rows_by_size(target)
	for size, mrp in source_lot_prices.items():
		if size not in target_rows or flt(mrp) <= 0 or flt(mrp) == flt(target_rows[size].mrp):
			continue
		target.append("lot_price_overrides", {
			"lot": target_lot,
			"size": size,
			"mrp": flt(mrp),
			"changed_by": frappe.session.user,
			"changed_on": now_datetime(),
		})
	if target.get("lot_price_overrides"):
		target.save(ignore_permissions=True)

	append_comment_log_block(target, "\n".join([
		f"[{frappe.utils.formatdate(frappe.utils.nowdate(), 'dd-mm-yyyy')}] Alternative PPO Created - {frappe.session.user}",
		f"From Production Order: {source.name}",
		f"From Finishing Plan: {finishing_plan}",
		f"Alternative Lot: {target_lot}",
	]))

	reason = f"Alternative item conversion from Finishing Plan {finishing_plan}"
	apply_alternative_plan_ppo_transfer(
		source.name,
		target.name,
		source_lot,
		target_lot,
		transfers,
		reason,
	)
	return target.name


def build_quantity_transfer_history_rows(
	source,
	target,
	changes,
	request,
	approved_by,
	approved_on,
):
	"""Build matching size-wise audit rows for the source and destination PPOs.

	The source Production Order details remain the original sales-order snapshot. Its
	`Reduced` history rows therefore carry the operational before/after quantity, while
	the destination rows carry the persisted before/after addition.
	"""
	transfer_reference = request.get("transfer_reference") or frappe.generate_hash(length=10)
	source_rows_by_size = get_rows_by_size(source)
	source_history = []
	target_history = []

	common = {
		"transfer_reference": transfer_reference,
		"requested_by": request.get("requested_user"),
		"requested_on": request.get("requested_on"),
		"approved_by": approved_by,
		"approved_on": approved_on,
		"reason": request.get("reason"),
	}

	for change in changes:
		size = change["size"]
		quantity = flt(change["qty"])
		source_quantity = flt(change.get("source_qty", quantity))
		target_quantity = flt(change.get("target_qty", quantity))
		source_row = source_rows_by_size.get(size)
		source_before = flt(
			change["source_old_qty"]
			if "source_old_qty" in change
			else source_row.quantity if source_row else 0
		)
		source_after = flt(
			change["source_new_qty"]
			if "source_new_qty" in change
			else source_before - source_quantity
		)
		if not source_row or source_before < source_quantity:
			frappe.throw(
				f"Source quantity for size {size} changed while approval was pending. Create a new transfer request"
			)
		source_history.append({
			**common,
			"movement": "Reduced",
			"counterpart_production_order": target.name,
			"size": size,
			"quantity": source_quantity,
			"quantity_before": source_before,
			"quantity_after": source_after,
		})
		target_history.append({
			**common,
			"movement": "Added",
			"counterpart_production_order": source.name,
			"size": size,
			"quantity": target_quantity,
			"quantity_before": flt(change["old_qty"]),
			"quantity_after": flt(change["new_qty"]),
		})

	return source_history, target_history


def append_quantity_transfer_history(
	source,
	target,
	changes,
	request,
	approved_by,
	approved_on,
):
	"""Persist the paired audit rows without resaving either submitted parent."""
	source_history, target_history = build_quantity_transfer_history_rows(
		source,
		target,
		changes,
		request,
		approved_by,
		approved_on,
	)
	for parent, rows in ((source, source_history), (target, target_history)):
		for values in rows:
			parent.append("quantity_transfer_history", values).db_insert()
		frappe.clear_document_cache("Production Order", parent.name)
