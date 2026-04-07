# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff, flt
from frappe.model.document import Document
from production_api.utils import update_if_string_instance, get_variant_attr_details
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant, get_variant


class ProductionOrder(Document):
    def before_cancel(self):
        lots = frappe.get_all(
            "Lot", filters={"production_order": self.name}, pluck="name")
        if lots:
            frappe.throw(f"PPO linked in {','.join(lots)}")

    def on_update_after_submit(self):
        self.lead_time_given = date_diff(self.delivery_date, self.posting_date)

    def before_submit(self):
        docstatus = frappe.get_value(
            "Production Term", self.production_term, "docstatus")
        if docstatus != 1:
            frappe.throw("Selected Term is not valid")
        self.posting_date = frappe.utils.nowdate()
        if self.delivery_date < self.posting_date:
            frappe.throw("Delivery date is less than Posting Date")
        if self.delivery_date > self.dont_deliver_after:
            frappe.throw("Don't deliver after date is less than delivery date")
        self.lead_time_given = date_diff(self.delivery_date, self.posting_date)
        self.submitted_by = frappe.session.user
        self.submitted_time = frappe.utils.now()

    def onload(self):
        order_qty = get_order_qty(self.production_order_details)
        self.set_onload("items", order_qty)
        ordered_detail = get_ordered_details(self.production_ordered_details)
        self.set_onload("ordered_details", {
                        "items": order_qty, "ordered": ordered_detail})
        if self.docstatus == 1:
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
            self.set("production_ordered_details", [])
            self.submitted_by = None
            self.submitted_time = None
        if self.docstatus == 0 and self.get("item") and self.get("item_details"):
            self.update_order()
        self.lead_time_given = date_diff(self.delivery_date, self.posting_date)

    def update_order(self):
        item_fields = ["primary_attribute",
                       "dependent_attribute", "default_unit_of_measure"]
        primary, dependent, uom = frappe.get_value(
            "Item", self.item, item_fields)
        item_details = update_if_string_instance(self.item_details) or {}
        sales_item_price = get_sales_item_price_map(self.item)

        items = []
        for size, current_row in item_details.items():

            price_row = sales_item_price.get(size, {})
            items.append({
                "item_variant": get_or_create_variant(
                    self.item, {dependent: "Pack", primary: size}
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

    price_map = {}

    for size in sizes:
        variant = get_variant(item, {
            item_doc.dependent_attribute: "Pack",
            item_doc.primary_attribute: size
        }) if item_doc.primary_attribute and item_doc.dependent_attribute else None
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
    if not item and production_order:
        item = frappe.get_value("Production Order", production_order, "item")
    if not item:
        return box_sticker_mrp

    # item_names = [item, item.replace(" ", "-"), item.replace("-", " ")]
    # unique_items = []
    # for name in item_names:
    #     if name and name not in unique_items:
    #         unique_items.append(name)

    filters = {"fg_item": ["in", item], "docstatus": 1}
    box_sticker_prints = frappe.get_all(
        "Box Sticker Print",
        filters=filters,
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

    context = {"primary_values": primary_values, "items": {}, "ordered": {}}

    for size in primary_values:
        price_row = sales_item_price.get(size, {})
        context["items"][size] = {"qty": 0, "ratio": 0, "mrp": 0,
                                  "wholesale": price_row.get("wholesale", 0), "retail": price_row.get("retail", 0)}

    if not production_order or not frappe.db.exists("Production Order", production_order):
        return context

    doc = frappe.get_doc("Production Order", production_order)

    order_qty = get_order_qty(doc.production_order_details)

    context["ordered"] = get_ordered_details(doc.production_ordered_details)
    for size in primary_values:
        if size not in order_qty:
            continue
        context["items"][size]["qty"] = order_qty[size].get("qty", 0)
        context["items"][size]["ratio"] = order_qty[size].get("ratio", 0)
        context["items"][size]["mrp"] = order_qty[size].get(
            "mrp", context["items"][size]["mrp"])
        # if not sales_item_price.get(size, {}).get("wholesale") and order_qty[size].get("wholesale"):
        #     context["items"][size]["wholesale"] = order_qty[size].get(
        #         "wholesale", 0)
        # if not sales_item_price.get(size, {}).get("retail") and order_qty[size].get("retail"):
        #     context["items"][size]["retail"] = order_qty[size].get("retail", 0)
    return context


@frappe.whitelist()
def get_price_update_context(production_order):
    doc = frappe.get_doc("Production Order", production_order)

    primary_values = get_attribute_details(doc.item).get(
        "primary_attribute_values", [])

    order_qty = get_order_qty(doc.production_order_details)

    sales_item_price = get_sales_item_price_map(doc.item)
    box_sticker_mrp = get_box_sticker_mrp_map(production_order, doc.item)
    items = {}
    for size in primary_values:
        current_mrp = flt(order_qty.get(size, {}).get("mrp", 0))
        sales_mrp = sales_item_price.get(size, {}).get("sales_mrp")
        box_mrp = box_sticker_mrp.get(size)

        production_order_mrp = current_mrp
        selected_source = "production_order_mrp"
        items[size] = {"qty": flt(order_qty.get(size, {}).get("qty", 0)), "ratio": flt(order_qty.get(size, {}).get("ratio", 0)), "sales_mrp": sales_mrp, "box_sticker_mrp": box_mrp,
                       "production_order_mrp": production_order_mrp, "has_sales_mrp": sales_mrp is not None, "has_box_sticker_mrp": box_mrp is not None,
                       "selected_source": selected_source}
    return {"primary_values": primary_values, "items": items}


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

    doc = frappe.get_doc("Production Order", production_order)
    item_details = update_if_string_instance(item_details) or {}
    primary = frappe.get_value("Item", doc.item, "primary_attribute")
    sales_item_price = get_sales_item_price_map(doc.item)
    box_sticker_mrp = get_box_sticker_mrp_map(production_order, doc.item)
    has_submitted_item_bsp = has_submitted_box_sticker_for_item(doc.item)
    old_prices = {}
    new_prices = {}
    has_changes = False

    if has_submitted_item_bsp:
        for size in item_details:
            sales_mrp = sales_item_price.get(size, {}).get("sales_mrp")
            box_mrp = box_sticker_mrp.get(size)
            if sales_mrp is None or box_mrp is None:
                frappe.throw(
                    f"Cannot update MRP for size {size}. Submitted Box Sticker exists and Sales/Box Sticker MRP is missing."
                )
            if flt(sales_mrp) != flt(box_mrp):
                frappe.throw(
                    f"Cannot update MRP for size {size}. Submitted Box Sticker exists and Sales MRP ({flt(sales_mrp)}) does not match Box Sticker MRP ({flt(box_mrp)})."
                )

    for size in item_details:
        for row in doc.production_order_details:
            attrs = get_variant_attr_details(row.item_variant)
            if attrs.get(primary) == size:
                old_prices[size] = {"mrp": flt(row.mrp),
                                    "wholesale": flt(row.wholesale_price),
                                    "retail": flt(row.retail_price)}
                selected_source = item_details[size].get(
                    "selected_source", "production_order_mrp")
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
                else:
                    baseline = row.get("production_order_mrp")
                    if baseline in (None, "", 0, "0"):
                        baseline = row.mrp
                    new_mrp = flt(item_details[size].get(
                        "production_order_mrp", baseline))
                new_prices[size] = {"mrp": new_mrp, "wholesale": flt(
                    row.wholesale_price), "retail": flt(row.retail_price)}
                if flt(row.mrp) != new_mrp:
                    has_changes = True
                break
    if not has_changes:
        return {"status": "no_change"}

    lots = frappe.get_all(
        "Lot", filters={"production_order": production_order}, pluck="name")

    has_bsp = False
    if has_submitted_item_bsp:
        has_bsp = True
    elif lots:
        has_bsp = frappe.db.exists("Box Sticker Print", {
                                   "lot": ["in", lots], "docstatus": 1})
    if not has_bsp:
        _apply_prices_to_ppo(doc, new_prices, primary)
        _create_ppo_price_request(
            production_order, old_prices, new_prices, auto_approved=True)
        return {"status": "approved"}
    pending = frappe.db.exists("PPO Price Request", {
                               "production_order": production_order, "status": "Pending"})
    if pending:
        frappe.throw(
            "A price change request is already pending approval for this Production Order")
    _create_ppo_price_request(
        production_order, old_prices, new_prices, auto_approved=False)
    doc.db_set("price_approval_status",
               "Pending Approval", update_modified=False)
    print("Price update request created", item_details)
    return {"status": "pending_approval"}


def _apply_prices_to_ppo(doc, item_details, primary):
    for size in item_details:
        for row in doc.production_order_details:
            attrs = get_variant_attr_details(row.item_variant)
            if attrs.get(primary) == size:
                if row.get('production_order_mrp') in (None, "", 0, "0"):
                    row.production_order_mrp = flt(row.mrp)
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
def create_lot(production_order, lot_name):
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
