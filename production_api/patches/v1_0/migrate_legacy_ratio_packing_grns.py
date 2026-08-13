import frappe
from frappe.utils import cint, flt

from production_api.dynamic_packing import LEGACY_BATCH_TRACKING_VERSION
from production_api.production_api.doctype.finishing_plan.finishing_plan import (
	rebuild_finishing_packing_quantities,
)
from production_api.utils import get_variant_attr_details


LEGACY_BATCH_COLOUR = "Legacy Fixed Ratio"
TOLERANCE = 0.001


def execute():
	if not frappe.db.exists("DocType", "GRN Packing Batch"):
		return

	migrations = [prepare_migration(name) for name in get_candidate_plans()]
	grn_owners = {}
	for migration in migrations:
		for grn in migration["grns"]:
			owner = grn_owners.setdefault(grn["name"], migration["finishing_plan"])
			if owner != migration["finishing_plan"]:
				frappe.throw(
					f"Legacy GRN {grn['name']} is linked to multiple Finishing Plans: "
					f"{owner} and {migration['finishing_plan']}"
				)
	for migration in migrations:
		apply_migration(migration)

	migrated_plans = {row["finishing_plan"] for row in migrations}
	repaired_plans = [
		name for name in get_negative_packing_plans() if name not in migrated_plans
	]
	for name in repaired_plans:
		fp = rebuild_finishing_packing_quantities(name)
		fp.save(ignore_permissions=True)

	if migrations or repaired_plans:
		print(
			"Migrated legacy ratio packing: "
			f"plans={len(migrations)}, "
			f"grns={sum(len(row['grns']) for row in migrations)}, "
			f"negative_plans_repaired={len(repaired_plans)}"
		)


def get_candidate_plans():
	return frappe.db.sql(
		"""
			SELECT DISTINCT fp.name
			FROM `tabFinishing Plan` fp
			INNER JOIN `tabLot` lot ON lot.name = fp.lot
			INNER JOIN `tabItem Production Detail` ipd
				ON ipd.name = lot.production_detail
			INNER JOIN `tabGoods Received Note` grn
				ON grn.against = 'Work Order'
				AND grn.against_id = fp.work_order
				AND grn.lot = fp.lot
				AND grn.docstatus = 1
				AND COALESCE(grn.is_return, 0) = 0
				AND COALESCE(grn.includes_packing, 0) = 1
				AND COALESCE(grn.from_finishing, 0) = 1
				AND COALESCE(grn.packing_calculation_version, 0) < %s
			WHERE
				ipd.packing_mode = 'Size Ratio Packing'
				AND COALESCE(ipd.based_on_other_attribute_mapping, 0) = 1
			ORDER BY fp.name
		""",
		(LEGACY_BATCH_TRACKING_VERSION,),
		pluck=True,
	)


def get_negative_packing_plans():
	return frappe.db.sql(
		"""
			SELECT DISTINCT parent
			FROM `tabFinishing Plan GRN Detail`
			WHERE quantity < 0
			ORDER BY parent
		""",
		pluck=True,
	)


def prepare_migration(finishing_plan):
	fp = frappe.get_doc("Finishing Plan", finishing_plan)
	combo = cint(fp.pieces_per_box)
	if combo <= 0:
		frappe.throw(f"Finishing Plan {fp.name} has no valid pieces per box")

	dispatched = sum(flt(row.dispatched) for row in fp.finishing_plan_grn_details)
	if abs(dispatched) > TOLERANCE:
		frappe.throw(
			f"Finishing Plan {fp.name} has {dispatched:g} legacy dispatched box equivalents. "
			"Its historical colour/ratio split cannot be migrated automatically."
		)

	grn_names = frappe.db.sql(
		"""
			SELECT name
			FROM `tabGoods Received Note`
			WHERE
				against = 'Work Order'
				AND against_id = %s
				AND lot = %s
				AND docstatus = 1
				AND COALESCE(is_return, 0) = 0
				AND COALESCE(includes_packing, 0) = 1
				AND COALESCE(from_finishing, 0) = 1
				AND COALESCE(packing_calculation_version, 0) < %s
			ORDER BY posting_date, posting_time, creation, name
		""",
		(fp.work_order, fp.lot, LEGACY_BATCH_TRACKING_VERSION),
		pluck=True,
	)
	grns = [prepare_grn(grn_name, fp, combo) for grn_name in grn_names]
	return {"finishing_plan": fp.name, "grns": grns}


def prepare_grn(grn_name, finishing_plan, combo):
	if frappe.db.exists("GRN Packing Batch", {"parent": grn_name}):
		frappe.throw(f"Legacy GRN {grn_name} already has packing batch rows")

	items = frappe.get_all(
		"Goods Received Note Item",
		filters={"parent": grn_name, "docstatus": 1},
		fields=["item_variant", "quantity"],
	)
	boxes = sum(flt(item.quantity) for item in items)
	rounded_boxes = round(boxes)
	if boxes <= 0 or abs(boxes - rounded_boxes) > TOLERANCE:
		frappe.throw(
			f"Legacy GRN {grn_name} has non-whole physical box total {boxes:g}"
		)

	pieces_by_size = {}
	for item in items:
		size = get_variant_attr_details(item.item_variant).get(
			frappe.get_cached_value(
				"Item Production Detail",
				finishing_plan.production_detail,
				"primary_item_attribute",
			)
		)
		if not size:
			frappe.throw(f"Cannot determine size for {item.item_variant} in GRN {grn_name}")
		pieces_by_size[size] = pieces_by_size.get(size, 0) + flt(item.quantity) * combo

	ratio = reconstruct_ratio(grn_name, pieces_by_size, rounded_boxes, combo)

	return {
		"name": grn_name,
		"box_quantity": rounded_boxes,
		"pieces_per_box": combo,
		"total_pieces": rounded_boxes * combo,
		"ratio": ratio,
	}


def reconstruct_ratio(grn_name, pieces_by_size, boxes, combo):
	ratio = {}
	for size, pieces in pieces_by_size.items():
		per_box = flt(pieces) / boxes
		rounded_ratio = round(per_box)
		if abs(per_box - rounded_ratio) > TOLERANCE:
			frappe.throw(
				f"Legacy GRN {grn_name} ratio for {size} cannot be reconstructed exactly"
			)
		if rounded_ratio:
			ratio[size] = rounded_ratio
	if sum(ratio.values()) != combo:
		frappe.throw(
			f"Legacy GRN {grn_name} reconstructed ratio totals {sum(ratio.values())}, "
			f"expected {combo}"
		)
	return ratio


def apply_migration(migration):
	for grn in migration["grns"]:
		frappe.get_doc({
			"doctype": "GRN Packing Batch",
			"parent": grn["name"],
			"parenttype": "Goods Received Note",
			"parentfield": "packing_batches",
			"idx": 1,
			"batch_id": "LEGACY-001",
			"colour": LEGACY_BATCH_COLOUR,
			"box_quantity": grn["box_quantity"],
			"dispatched_boxes": 0,
			"pieces_per_box": grn["pieces_per_box"],
			"total_pieces": grn["total_pieces"],
			"ratio_json": frappe.as_json(grn["ratio"]),
		}).db_insert()
		frappe.db.set_value(
			"Goods Received Note",
			grn["name"],
			{
				"packing_calculation_version": LEGACY_BATCH_TRACKING_VERSION,
				"total_packing_boxes": grn["box_quantity"],
				"total_packing_pieces": grn["total_pieces"],
			},
			update_modified=False,
		)
		frappe.clear_document_cache("Goods Received Note", grn["name"])

	fp = frappe.get_doc("Finishing Plan", migration["finishing_plan"])
	rebuild_finishing_packing_quantities(fp)
	fp.save(ignore_permissions=True)
