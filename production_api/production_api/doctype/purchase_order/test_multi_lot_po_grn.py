# Copyright (c) 2026, Essdee and contributors
from itertools import groupby

import frappe
from frappe.tests.utils import FrappeTestCase
from production_api.production_api.doctype.purchase_order.purchase_order import get_purchase_order_lots
from production_api.production_api.doctype.goods_received_note.goods_received_note import (
	validate_grn_lots_subset, split_lot_rows,
)


class TestMultiLotPOGRN(FrappeTestCase):
	def test_get_purchase_order_lots_empty_when_unlinked(self):
		po_name = frappe.get_all("Purchase Order", limit=1, pluck="name")
		if not po_name:
			self.skipTest("No Purchase Order in site to test against")
		lots = get_purchase_order_lots(po_name[0])
		self.assertIsInstance(lots, list)

	def test_update_po_lot_links_idempotent_link_and_unlink(self):
		from production_api.production_api.doctype.purchase_order.purchase_order import update_po_lot_links
		po = frappe.get_all("Purchase Order", filters={"docstatus": 1}, limit=1, pluck="name")
		lot = frappe.get_all("Lot", limit=1, pluck="name")
		if not po or not lot:
			self.skipTest("Need a submitted PO and a Lot")
		po, lot = po[0], lot[0]
		update_po_lot_links(po, add_lots=[lot], comment="t")
		update_po_lot_links(po, add_lots=[lot], comment="t")      # duplicate link -> no-op
		self.assertEqual(get_purchase_order_lots(po).count(lot), 1)
		update_po_lot_links(po, remove_lots=[lot], comment="t")   # unlink
		self.assertNotIn(lot, get_purchase_order_lots(po))
		update_po_lot_links(po, remove_lots=[lot], comment="t")   # unlink absent -> no-op
		frappe.db.rollback()

	def test_unlink_blocked_when_lot_referenced_by_grn(self):
		import production_api.production_api.doctype.purchase_order.purchase_order as po_mod
		po = frappe.get_all("Purchase Order", filters={"docstatus": 1}, limit=1, pluck="name")
		lot = frappe.get_all("Lot", limit=1, pluck="name")
		if not po or not lot:
			self.skipTest("Need a submitted PO and a Lot")
		po, lot = po[0], lot[0]
		po_mod.update_po_lot_links(po, add_lots=[lot], comment="t")
		original = po_mod._lot_has_grn_on_po
		po_mod._lot_has_grn_on_po = lambda p, l: True             # simulate a GRN referencing the lot (any docstatus)
		try:
			with self.assertRaises(frappe.ValidationError):
				po_mod.update_po_lot_links(po, remove_lots=[lot], comment="t")
		finally:
			po_mod._lot_has_grn_on_po = original
		frappe.db.rollback()


class TestGRNLotSplit(FrappeTestCase):
	def test_split_lot_rows_emits_one_per_lot(self):
		cell = {
			"ref_doctype": "Purchase Order Item",
			"ref_docname": "PO-ITEM-1",
			"qty": 100, "pending_qty": 100,
			"lot_rows": [
				{"lot": "LOT-A", "received": 60},
				{"lot": "LOT-B", "received": 40},
				{"lot": "LOT-C", "received": 0},   # zero -> dropped
			],
		}
		rows = split_lot_rows(cell)
		self.assertEqual(len(rows), 2)
		self.assertEqual({r["lot"] for r in rows}, {"LOT-A", "LOT-B"})
		self.assertEqual(sum(r["received"] for r in rows), 100)

	def test_split_lot_rows_legacy_single_value(self):
		cell = {"ref_docname": "PO-ITEM-1", "received": 25, "lot": "LOT-A"}
		rows = split_lot_rows(cell)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["lot"], "LOT-A")
		self.assertEqual(rows[0]["received"], 25)

	def test_subset_gate_rejects_unlisted_lot(self):
		po_name = frappe.get_all("Purchase Order", filters={"docstatus": 1}, limit=1, pluck="name")
		if not po_name:
			self.skipTest("No submitted PO to test against")
		variant = frappe.get_all("Item Variant", limit=1, pluck="name")
		real_lot = frappe.get_all("Lot", limit=1, pluck="name")
		if not variant or not real_lot:
			self.skipTest("No Item Variant / Lot in site")
		rows = [{"item_variant": variant[0], "lot": "definitely-not-a-real-lot-xyz"}]
		# ensure this PO has at least one linked lot so `allowed` is non-empty
		po = frappe.get_doc("Purchase Order", po_name[0])
		po.set("sd_lot", [{"lot": real_lot[0]}])
		po.flags.ignore_item_details_check = True
		po.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			validate_grn_lots_subset(po_name[0], rows)
		frappe.db.rollback()


class TestMultiLotGRNFixes(FrappeTestCase):
	"""Regression tests for the four code-review-confirmed defects."""

	def _multilot_cell(self, ref_docname, lot_rows, qty=100, pending=100):
		return {
			"qty": qty, "pending_qty": pending, "rate": 5, "tax": 0,
			"ref_doctype": "Purchase Order Item", "ref_docname": ref_docname,
			"received": None, "secondary_received": None,
			"lot_rows": lot_rows,
		}

	# ---- ISSUE A: staggered / partial multi-lot receipt must be possible ----
	def test_multilot_save_skips_unreceived_cell(self):
		"""A multi-lot PO where only ONE ordered cell is received: the untouched
		cell (empty lot_rows) is skipped entirely — no spurious inherited-lot
		row, no throw — and only the received split rows are emitted."""
		import production_api.production_api.doctype.goods_received_note.goods_received_note as grn
		item_details = [{
			"items": [{
				"name": "ITEM-X",
				"attributes": {},
				"primary_attribute": "Colour",
				"lot": "INHERITED-LOT",
				"default_uom": "Nos",
				"secondary_uom": None,
				"comments": None,
				"values": {
					# received: one valid sd_lot split
					"Red": self._multilot_cell(
						"POI-RED",
						[{"lot": "LOT-A", "received": 60, "secondary_received": 0}],
						qty=100, pending=100),
					# ordered but NOT received: empty lot_rows, still carries qty/pending
					"Blue": self._multilot_cell("POI-BLUE", [], qty=50, pending=50),
				},
			}],
		}]
		orig_variant = grn.get_or_create_variant
		orig_tol = grn.validate_quantity_tolerance
		grn.get_or_create_variant = lambda name, attrs: name + ":" + (attrs.get("Colour") or "")
		grn.validate_quantity_tolerance = lambda *a, **k: True
		try:
			rows = grn.save_grn_purchase_item_details(item_details, has_lots=True)
		finally:
			grn.get_or_create_variant = orig_variant
			grn.validate_quantity_tolerance = orig_tol
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["lot"], "LOT-A")
		self.assertEqual(rows[0]["quantity"], 60)
		self.assertEqual(rows[0]["ref_docname"], "POI-RED")
		self.assertTrue(all(r["lot"] != "INHERITED-LOT" for r in rows))

	# ---- ISSUE B: legacy GRN amend/reopen must not discard edited received ----
	def test_legacy_save_respects_edited_received(self):
		"""A legacy (empty sd_lot) cell that still carries a stale lot_rows from
		an earlier fetch must round-trip the edited plain `received`, not the
		stale lot_rows value."""
		import production_api.production_api.doctype.goods_received_note.goods_received_note as grn
		item_details = [{
			"items": [{
				"name": "ITEM-Y",
				"attributes": {},
				"primary_attribute": None,
				"lot": "INHERITED-LOT",
				"default_uom": "Nos",
				"secondary_uom": None,
				"comments": None,
				"values": {
					"default": {
						"qty": 100, "pending_qty": 100, "rate": 5, "tax": 0,
						"ref_doctype": "Purchase Order Item", "ref_docname": "POI-Y",
						"received": 8,            # user edited it to 8
						"secondary_received": 0,
						# stale accumulator that a pre-fix fetch would have attached:
						"lot_rows": [{"lot": "STALE", "received": 5, "secondary_received": 0}],
					},
				},
			}],
		}]
		orig_variant = grn.get_or_create_variant
		orig_tol = grn.validate_quantity_tolerance
		grn.get_or_create_variant = lambda name, attrs: name
		grn.validate_quantity_tolerance = lambda *a, **k: True
		try:
			rows = grn.save_grn_purchase_item_details(item_details, has_lots=False)
		finally:
			grn.get_or_create_variant = orig_variant
			grn.validate_quantity_tolerance = orig_tol
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["quantity"], 8)          # edited value, NOT stale 5
		self.assertEqual(rows[0]["lot"], "INHERITED-LOT")

	def test_fetch_legacy_grn_omits_lot_rows(self):
		"""Fetch must not attach a lot_rows accumulator for a legacy PO GRN —
		legacy cells stay byte-identical to pre-feature shape."""
		from production_api.production_api.doctype.goods_received_note.goods_received_note import (
			fetch_grn_purchase_item_details,
		)
		grn_name = frappe.get_all(
			"Goods Received Note",
			filters={"against": "Purchase Order", "docstatus": 1},
			limit=1, pluck="name",
		)
		if not grn_name:
			self.skipTest("No submitted PO GRN on site to test against")
		doc = frappe.get_doc("Goods Received Note", grn_name[0])
		item_details = fetch_grn_purchase_item_details(
			doc.get("items"), docstatus=doc.docstatus, has_lots=False)
		for grp in item_details:
			for it in grp["items"]:
				for cell in it["values"].values():
					self.assertNotIn("lot_rows", cell)

	# ---- ISSUE C: link/unlink endpoints must enforce write permission ----
	def test_link_blocked_without_write_permission(self):
		import production_api.production_api.doctype.purchase_order.purchase_order as po_mod
		po = frappe.get_all("Purchase Order", filters={"docstatus": 1}, limit=1, pluck="name")
		lot = frappe.get_all("Lot", limit=1, pluck="name")
		if not po or not lot:
			self.skipTest("Need a submitted PO and a Lot")
		po, lot = po[0], lot[0]
		original = frappe.has_permission

		def deny(doctype, ptype=None, *args, **kwargs):
			if doctype == "Purchase Order" and ptype == "write":
				if kwargs.get("throw"):
					raise frappe.PermissionError("No permission to write Purchase Order")
				return False
			return original(doctype, ptype, *args, **kwargs)

		frappe.has_permission = deny
		try:
			with self.assertRaises(frappe.PermissionError):
				po_mod.update_po_lot_links(po, add_lots=[lot], comment="t")
		finally:
			frappe.has_permission = original
		frappe.db.rollback()

	# ---- ISSUE D: intra-batch duplicate lots must be deduped ----
	def test_intra_batch_duplicate_lots_deduped(self):
		from production_api.production_api.doctype.purchase_order.purchase_order import update_po_lot_links
		po = frappe.get_all("Purchase Order", filters={"docstatus": 1}, limit=1, pluck="name")
		lot = frappe.get_all("Lot", limit=1, pluck="name")
		if not po or not lot:
			self.skipTest("Need a submitted PO and a Lot")
		po, lot = po[0], lot[0]
		update_po_lot_links(po, add_lots=[lot, lot], comment="dup")
		self.assertEqual(get_purchase_order_lots(po).count(lot), 1)
		frappe.db.rollback()


class TestFetchGRNRaisedLot(FrappeTestCase):
	"""The GRN 'Lot' column must always show the PO item row's ORIGINAL raised
	lot (e.g. the 'Open Lot' placeholder), never the first received/split lot,
	after the multi-lot feature splits one ordered cell into several GRN rows."""

	def _find_split_multilot_grn(self):
		"""Find a draft PO GRN where one PO-item ref was received across 2+
		distinct lots AND the PO item's raised lot is not one of those received
		lots (so the assertion is meaningful). Returns (grn, ref_docname,
		raised_lot, split_lots) or (None, ...)."""
		rows = frappe.db.sql(
			"""
			SELECT gi.parent AS parent, gi.ref_docname AS ref_docname,
			       COUNT(DISTINCT gi.lot) AS nlots
			FROM `tabGoods Received Note Item` gi
			INNER JOIN `tabGoods Received Note` g ON g.name = gi.parent
			WHERE g.against = %s AND g.docstatus = 0
			  AND gi.ref_doctype = %s
			  AND gi.ref_docname IS NOT NULL AND gi.ref_docname != ''
			GROUP BY gi.parent, gi.ref_docname
			HAVING nlots >= 2
			LIMIT 50
			""",
			("Purchase Order", "Purchase Order Item"),
			as_dict=True,
		)
		for r in rows:
			raised = frappe.db.get_value("Purchase Order Item", r.ref_docname, "lot")
			split_lots = frappe.get_all(
				"Goods Received Note Item",
				filters={"parent": r.parent, "ref_docname": r.ref_docname},
				pluck="lot",
			)
			if raised and raised not in split_lots:
				return r.parent, r.ref_docname, raised, split_lots
		return None, None, None, None

	def test_fetch_multilot_grn_shows_raised_lot_not_split_lot(self):
		from production_api.production_api.doctype.goods_received_note.goods_received_note import (
			fetch_grn_purchase_item_details,
		)
		grn_name, ref_docname, raised, split_lots = self._find_split_multilot_grn()
		if not grn_name:
			self.skipTest("No draft multi-lot PO GRN with a split ref on site")
		doc = frappe.get_doc("Goods Received Note", grn_name)
		item_details = fetch_grn_purchase_item_details(
			doc.get("items"), docstatus=doc.docstatus, has_lots=True)

		# locate the fetched item that owns this split PO-item row
		target = None
		for grp in item_details:
			for it in grp["items"]:
				for cell in it["values"].values():
					if cell.get("ref_docname") == ref_docname:
						target = it
						break
				if target:
					break
			if target:
				break
		self.assertIsNotNone(target, "split PO-item cell not found in fetched details")

		# the displayed Lot column must show the PO row's RAISED lot ...
		self.assertEqual(target["lot"], raised)
		# ... never one of the received/split lots.
		self.assertNotIn(target["lot"], split_lots)
		# and the per-lot split still carries the real received lots.
		received_lots = {
			lr["lot"]
			for cell in target["values"].values()
			for lr in (cell.get("lot_rows") or [])
		}
		self.assertTrue(set(split_lots).issubset(received_lots))

	def test_fetch_legacy_branch_keeps_row_lot_unchanged(self):
		"""Legacy path (has_lots=False): the displayed lot stays each item's own
		first GRN-row lot — byte-identical to pre-feature; the raised-lot lookup
		must never apply."""
		from production_api.production_api.doctype.goods_received_note.goods_received_note import (
			fetch_grn_purchase_item_details,
		)
		grn_name = frappe.get_all(
			"Goods Received Note",
			filters={"against": "Purchase Order", "docstatus": 1},
			limit=1, pluck="name",
		)
		if not grn_name:
			self.skipTest("No submitted PO GRN on site to test against")
		doc = frappe.get_doc("Goods Received Note", grn_name[0])
		items = doc.get("items")
		rows = sorted(
			[r.as_dict() for r in items if (r.quantity or 0) > 0],
			key=lambda i: i["row_index"],
		)
		expected_first_lot = {
			k: list(v)[0]["lot"] for k, v in groupby(rows, lambda i: i["row_index"])
		}
		item_details = fetch_grn_purchase_item_details(
			items, docstatus=doc.docstatus, has_lots=False)
		displayed = [it["lot"] for grp in item_details for it in grp["items"]]
		self.assertTrue(displayed, "legacy fetch produced no items")
		for lot in displayed:
			self.assertIn(lot, set(expected_first_lot.values()))
