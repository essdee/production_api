import copy

import frappe
from frappe.model.document import Document

from spine.spine_adapter.kafka_client.kafka_producer import publish_doc_event


SD_YRP_TOPIC = "sd_yrp_master"

SD_YRP_EXACT_MATCH_DOCTYPES = (
	"MRP Settings",
	"Country",
	"UOM",
	"Item Group",
	"Brand",
	"Department",
	"Terms and Condition",
	"Product Season",
	"Product Category",
	"Additional Parameter Key",
	"Additional Parameter Value",
	"Item Attribute",
	"Item Attribute Value",
	"Process",
	"Production Term",
	"Item Item Attribute Mapping",
	"Item Dependent Attribute Mapping",
	"Item Variant",
	"Item Category",
	"Item BOM Attribute Mapping",
	"Address",
	"Contact",
)

SD_YRP_CUSTOM_MAPPER_DOCTYPES = (
	"Item",
	"Supplier",
	"User",
	"Lot Template",
	"Item Production Detail",
	"Production Order",
	"Lot",
)

SD_YRP_SYNC_DOCTYPES = SD_YRP_EXACT_MATCH_DOCTYPES + SD_YRP_CUSTOM_MAPPER_DOCTYPES

# Dependency-first (topological) publish order, derived from the actual Link
# fields among these DocTypes — NOT hand-ordered. Every DocType is published
# after everything it links to. The three inherent circular references are
# broken master-first, matching what the consumer already tolerates:
#   Item -> Item Dependent Attribute Mapping (Item first)
#   Item BOM Attribute Mapping -> Item Production Detail (IBAM first)
#   Production Order -> Lot (Production Order first; Lot not existence-validated)
# Notable placements the old order got wrong: MRP Settings links Process
# (-> Item -> Item Attribute/Value) so it CANNOT be first; Process links Item;
# Department links User.
SD_YRP_INITIAL_SYNC_ORDER = (
	"Country",
	"UOM",
	"Brand",
	"Terms and Condition",
	"Product Season",
	"Product Category",
	"Additional Parameter Key",
	"Additional Parameter Value",
	"Item Attribute",
	"Production Term",
	"User",
	"Item Category",
	"Address",
	"Item Group",
	"Item Attribute Value",
	"Department",
	"Contact",
	"Item Item Attribute Mapping",
	"Supplier",
	"Item",
	"Process",
	"Item Variant",
	"Item Dependent Attribute Mapping",
	"Item BOM Attribute Mapping",
	"MRP Settings",
	"Production Order",
	"Lot Template",
	"Item Production Detail",
	"Lot",
)

LOT_TIME_AND_ACTION_KEY_PARTS = ("time_and_action",)


def handle_existing_spine_and_sd_yrp(doc, event, *args):
	"""Preserve existing ERP Spine publishing and also publish isolated SD YRP events."""
	from spine.spine_adapter.docevents.eventhandler import handle_event

	if event != "on_trash":
		handle_event(doc, event, *args)
	enqueue_sd_yrp_publish(doc, event, args)


def handle_sd_yrp_event(doc, event, *args):
	enqueue_sd_yrp_publish(doc, event, args)


def handle_item_event(doc, event, *args):
	if event == "on_update":
		from production_api.production_api.doctype.item.item import sync_updated_item_variant

		sync_updated_item_variant(doc, event)
	enqueue_sd_yrp_publish(doc, event, args)


def produce_exact_doc(producer_dict):
	"""Producer handler for manual/bulk SD YRP producer config runs."""
	doc = producer_dict.get("doc_to_publish")
	if not doc:
		return None

	event = producer_dict.get("event") or producer_dict.get("docevent")
	producer_dict["doc_to_publish"] = prepare_sd_yrp_doc_for_publish(doc, event)
	return producer_dict


def enqueue_sd_yrp_publish(doc, event, args=None):
	if not frappe.conf.developer_mode:
		frappe.utils.background_jobs.enqueue(
			publish_sd_yrp_event,
			doc=doc,
			docevent=event,
			extra_args=args or (),
			enqueue_after_commit=True,
		)
	else:
		publish_sd_yrp_event(doc, event, args or ())


def publish_sd_yrp_event(doc, docevent, extra_args=()):
	if doc.doctype not in SD_YRP_SYNC_DOCTYPES:
		return
	if not frappe.local.conf.get("kafka"):
		return

	publish_doc_event(
		doc=prepare_sd_yrp_doc_for_publish(doc, docevent),
		doctype=doc.doctype,
		target_topic=SD_YRP_TOPIC,
		event=docevent,
		args=extra_args,
	)


def prepare_sd_yrp_doc_for_publish(doc, event=None):
	data = clean_doc_for_publish(doc)
	if data.get("doctype") == "Lot":
		return strip_lot_time_and_action_fields(data)
	return data


def clean_doc_for_publish(doc):
	if isinstance(doc, Document):
		data = doc.as_dict()
	else:
		data = copy.deepcopy(doc)

	for key in ("__onload", "_doc_before_save"):
		data.pop(key, None)
	return data


def strip_lot_time_and_action_fields(data):
	data = copy.deepcopy(data)
	for key in list(data):
		if is_lot_time_and_action_key(key):
			data.pop(key, None)
	return data


def is_lot_time_and_action_key(key):
	key = (key or "").lower()
	return any(part in key for part in LOT_TIME_AND_ACTION_KEY_PARTS)


def _ordered_initial_docnames(doctype, filters=None):
	"""Publish dependency-first so the consumer's link validation passes:
	- tree doctypes (lft column) -> nested-set order (parent before child)
	- doctypes with a self-referential child table (e.g. Process.process_details
	  -> Process) -> topological order (referenced rows first)
	"""
	if frappe.get_meta(doctype).issingle:
		return [doctype]
	if frappe.db.has_column(doctype, "lft"):
		return frappe.get_all(doctype, filters=filters, pluck="name", order_by="lft asc")
	docnames = frappe.get_all(doctype, filters=filters, pluck="name")
	return _self_ref_child_order(doctype, docnames)


def _self_ref_child_order(doctype, docnames):
	if not docnames:
		return docnames
	meta = frappe.get_meta(doctype)
	self_links = []
	for table_field in meta.get_table_fields():
		child_meta = frappe.get_meta(table_field.options)
		for field in child_meta.fields:
			if field.fieldtype == "Link" and field.options == doctype:
				self_links.append((table_field.options, table_field.fieldname, field.fieldname))
	if not self_links:
		return docnames

	nameset = set(docnames)
	deps = {name: set() for name in docnames}
	# Build the dependency graph with ONE query per self-referential child table
	# (not get_doc-per-record), so this stays cheap even on large doctypes.
	for child_doctype, child_field, link_field in self_links:
		rows = frappe.get_all(
			child_doctype,
			filters={"parenttype": doctype, "parentfield": child_field},
			fields=["parent", link_field],
		)
		for row in rows:
			parent = row.get("parent")
			ref = row.get(link_field)
			if parent in deps and ref and ref != parent and ref in nameset:
				deps[parent].add(ref)

	# Kahn topological sort — referenced rows first; stable on input order.
	from collections import deque

	indeg = {name: len(deps[name]) for name in docnames}
	dependents = {name: [] for name in docnames}
	for name in docnames:
		for ref in deps[name]:
			dependents[ref].append(name)
	queue = deque(name for name in docnames if indeg[name] == 0)
	ordered = []
	while queue:
		name = queue.popleft()
		ordered.append(name)
		for dependent in dependents[name]:
			indeg[dependent] -= 1
			if indeg[dependent] == 0:
				queue.append(dependent)
	if len(ordered) < len(docnames):  # cycle fallback: append the rest as-is
		seen = set(ordered)
		ordered.extend(name for name in docnames if name not in seen)
	return ordered


@frappe.whitelist()
def get_sd_yrp_sync_doctypes():
	"""Ordered list of DocTypes enabled for SD YRP sync — powers the sync UI selects."""
	frappe.only_for("System Manager")
	return list(SD_YRP_INITIAL_SYNC_ORDER)


@frappe.whitelist()
def trigger_initial_sync(doctype, filters=None, event="first_sync"):
	frappe.only_for("System Manager")
	if doctype not in SD_YRP_SYNC_DOCTYPES:
		frappe.throw(f"{doctype} is not enabled for SD YRP sync")

	if event not in {"first_sync", "on_update"}:
		frappe.throw("Only first_sync and on_update are allowed for bulk sync")

	if isinstance(filters, str):
		filters = frappe.parse_json(filters) if filters.strip() else None

	docnames = _ordered_initial_docnames(doctype, filters)
	if not frappe.conf.developer_mode:
		frappe.enqueue(
			process_initial_sync,
			queue="long",
			doctype=doctype,
			docnames=docnames,
			# NOT `event=` — frappe.enqueue has its own `event` param that would
			# swallow it; pass under a distinct name so it reaches the function.
			sync_event=event,
		)
	else:
		process_initial_sync(doctype, docnames, event)
	return docnames


@frappe.whitelist()
def trigger_all_initial_sync(event="first_sync"):
	frappe.only_for("System Manager")
	return trigger_ordered_initial_sync(event=event)


@frappe.whitelist()
def trigger_ordered_initial_sync(doctypes=None, event="first_sync"):
	frappe.only_for("System Manager")
	if event not in {"first_sync", "on_update"}:
		frappe.throw("Only first_sync and on_update are allowed for bulk sync")

	ordered_doctypes = get_ordered_initial_sync_doctypes(doctypes)
	if not frappe.conf.developer_mode:
		frappe.enqueue(
			process_all_initial_sync,
			queue="long",
			# NOT `event=` — see note in trigger_initial_sync.
			sync_event=event,
			doctypes=ordered_doctypes,
		)
	else:
		process_all_initial_sync(event, ordered_doctypes)
	return list(ordered_doctypes)


def get_ordered_initial_sync_doctypes(doctypes=None):
	if not doctypes:
		return SD_YRP_INITIAL_SYNC_ORDER

	if isinstance(doctypes, str):
		doctypes = frappe.parse_json(doctypes)

	requested = set(doctypes)
	unknown = requested.difference(SD_YRP_SYNC_DOCTYPES)
	if unknown:
		frappe.throw(f"DocTypes are not enabled for SD YRP sync: {', '.join(sorted(unknown))}")

	return tuple(doctype for doctype in SD_YRP_INITIAL_SYNC_ORDER if doctype in requested)


def process_all_initial_sync(sync_event, doctypes=None):
	for doctype in doctypes or SD_YRP_INITIAL_SYNC_ORDER:
		docnames = _ordered_initial_docnames(doctype)
		process_initial_sync(doctype, docnames, sync_event)


def process_initial_sync(doctype, docnames, sync_event):
	if doctype not in SD_YRP_SYNC_DOCTYPES:
		frappe.throw(f"{doctype} is not enabled for SD YRP sync")

	for docname in docnames:
		doc = frappe.get_doc(doctype, docname)
		publish_sd_yrp_event(doc, sync_event)
