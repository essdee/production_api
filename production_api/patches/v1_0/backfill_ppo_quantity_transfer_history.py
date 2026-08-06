import frappe
from frappe.utils import flt


def execute():
	if not frappe.db.table_exists("PPO Quantity Transfer History"):
		return

	from production_api.production_api.doctype.production_order.production_order import (
		append_quantity_transfer_history,
		get_rows_by_size,
		get_transfer_quantities,
	)

	sources = frappe.get_all(
		"Production Order",
		filters={
			"transferred_to_ppo": ["is", "set"],
			"transferred_on": ["is", "set"],
		},
		fields=[
			"name",
			"transferred_to_ppo",
			"transferred_on",
			"owner",
			"modified_by",
			"comment_log",
		],
	)

	for source_row in sources:
		if frappe.db.exists(
			"PPO Quantity Transfer History",
			{"parent": source_row.name, "movement": "Reduced"},
		):
			continue
		if not frappe.db.exists("Production Order", source_row.transferred_to_ppo):
			continue

		source = frappe.get_doc("Production Order", source_row.name)
		target = frappe.get_doc("Production Order", source_row.transferred_to_ppo)
		transfers = get_transfer_quantities(source)
		target_rows_by_size = get_rows_by_size(target)
		changes = []
		for size, quantity in transfers.items():
			target_row = target_rows_by_size.get(size)
			if not target_row:
				continue
			target_after = flt(target_row.quantity)
			changes.append({
				"size": size,
				"qty": flt(quantity),
				"old_qty": max(target_after - flt(quantity), 0),
				"new_qty": target_after,
			})

		if not changes:
			continue

		metadata = get_transfer_metadata(
			source_row.comment_log,
			source_row.owner,
			source_row.modified_by,
		)
		request = {
			"transfer_reference": f"BACKFILL-{source.name}-{target.name}",
			"requested_user": metadata["requested_by"],
			"requested_on": source_row.transferred_on,
			"reason": metadata["reason"],
		}
		append_quantity_transfer_history(
			source,
			target,
			changes,
			request,
			metadata["approved_by"],
			source_row.transferred_on,
		)


def get_transfer_metadata(comment_log, fallback_requested_by, fallback_approved_by):
	metadata = {
		"requested_by": fallback_requested_by,
		"approved_by": fallback_approved_by,
		"reason": "Historical approved quantity transfer",
	}
	blocks = (comment_log or "").replace("\r\n", "\n").split("\n[")
	for raw_block in reversed(blocks):
		block = raw_block if raw_block.startswith("[") else f"[{raw_block}"
		if "Quantity Transfer Approved - " not in block and "Quantity Transferred - " not in block:
			continue
		for line in block.splitlines():
			line = line.strip()
			for marker in ("Quantity Transfer Approved - ", "Quantity Transferred - "):
				if marker in line:
					metadata["approved_by"] = line.split(marker, 1)[1].strip()
			if line.startswith("Requested By: "):
				metadata["requested_by"] = line.split(":", 1)[1].strip()
			elif line.startswith("Reason: "):
				metadata["reason"] = line.split(":", 1)[1].strip()
		break
	return metadata
