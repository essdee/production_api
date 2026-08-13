"""Transaction-level packing ratios used by Finishing Plan GRNs and dispatches."""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import cint, flt

from production_api.utils import update_if_string_instance


LEGACY_BATCH_TRACKING_VERSION = 1
DYNAMIC_PACKING_VERSION = 2


def _positive_integer(value, label):
	value = flt(value)
	if value <= 0 or value != cint(value):
		frappe.throw(f"{label} should be a positive whole number")
	return cint(value)


def normalize_packing_batches(
	batches, valid_sizes, valid_colours=None, expected_pieces_per_box=None
):
	"""Validate GRN-time ratio rows and calculate their exact piece quantities."""
	batches = update_if_string_instance(batches) or []
	if not isinstance(batches, list) or not batches:
		frappe.throw("Enter at least one packing ratio")

	valid_sizes = list(valid_sizes or [])
	valid_size_set = set(valid_sizes)
	valid_colour_set = set(valid_colours or [])
	expected_pieces = None
	if expected_pieces_per_box is not None:
		expected_pieces = _positive_integer(
			expected_pieces_per_box, "Configured pieces per box"
		)
	normalized = []

	for index, raw in enumerate(batches, 1):
		raw = update_if_string_instance(raw) or {}
		colour = (raw.get("colour") or "").strip()
		if valid_colour_set and colour not in valid_colour_set:
			frappe.throw(f"Packing ratio {index}: select a valid colour")

		boxes = _positive_integer(raw.get("box_quantity"), f"Packing ratio {index} boxes")
		raw_ratio = update_if_string_instance(raw.get("ratio")) or {}
		if not isinstance(raw_ratio, dict):
			frappe.throw(f"Packing ratio {index}: invalid size ratio")

		ratio = {}
		for size in valid_sizes:
			qty = flt(raw_ratio.get(size))
			if qty < 0 or qty != cint(qty):
				frappe.throw(f"Packing ratio {index}, {size}: quantity should be a whole number")
			if qty:
				ratio[size] = cint(qty)

		unknown_sizes = [size for size, qty in raw_ratio.items() if flt(qty) and size not in valid_size_set]
		if unknown_sizes:
			frappe.throw(
				f"Packing ratio {index}: invalid sizes {', '.join(sorted(unknown_sizes))}"
			)
		if not ratio:
			frappe.throw(f"Packing ratio {index}: enter quantity for at least one size")

		pieces_per_box = sum(ratio.values())
		if expected_pieces is not None and pieces_per_box != expected_pieces:
			frappe.throw(
				f"Packing ratio {index}: total pieces per box should be "
				f"{expected_pieces}, but the entered ratio totals {pieces_per_box}"
			)
		size_pieces = {size: qty * boxes for size, qty in ratio.items()}
		normalized.append({
			"batch_id": f"BATCH-{index:03d}",
			"colour": colour,
			"box_quantity": boxes,
			"dispatched_boxes": 0,
			"pieces_per_box": pieces_per_box,
			"total_pieces": boxes * pieces_per_box,
			"ratio": ratio,
			"size_pieces": size_pieces,
		})

	return normalized


def aggregate_batch_pieces(batches, box_field="box_quantity"):
	"""Return size pieces, boxes and pieces for normalized/persisted batch rows."""
	size_pieces = defaultdict(float)
	total_boxes = 0.0
	total_pieces = 0.0
	for batch in batches or []:
		as_dict = getattr(batch, "as_dict", None)
		batch = as_dict() if callable(as_dict) else dict(batch)
		ratio = update_if_string_instance(batch.get("ratio") or batch.get("ratio_json")) or {}
		boxes = flt(batch.get(box_field))
		total_boxes += boxes
		for size, per_box in ratio.items():
			pieces = boxes * flt(per_box)
			size_pieces[size] += pieces
			total_pieces += pieces
	return dict(size_pieces), total_boxes, total_pieces


def packing_batch_label(batch):
	as_dict = getattr(batch, "as_dict", None)
	batch = as_dict() if callable(as_dict) else batch
	ratio = update_if_string_instance(batch.get("ratio") or batch.get("ratio_json")) or {}
	ratio_text = ", ".join(f"{size}:{cint(qty)}" for size, qty in ratio.items() if flt(qty))
	colour = batch.get("colour") or "No Colour"
	return f"{colour} [{ratio_text}]"


def is_dynamic_packing_grn(grn):
	version = grn.get("packing_calculation_version") if hasattr(grn, "get") else 0
	return cint(version) >= DYNAMIC_PACKING_VERSION


def is_batch_tracked_packing_grn(grn):
	"""Return whether a GRN has auditable packing batches.

	Version 1 is a migrated fixed-ratio GRN: its stock rows remain in the historical
	box unit, but a reconstructed packing batch makes its boxes dispatchable alongside
	new transaction-ratio GRNs. Version 2 stores exact piece rows natively.
	"""
	version = grn.get("packing_calculation_version") if hasattr(grn, "get") else 0
	return cint(version) >= LEGACY_BATCH_TRACKING_VERSION
