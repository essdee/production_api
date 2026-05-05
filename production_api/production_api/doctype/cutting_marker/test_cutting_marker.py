# Copyright (c) 2024, Essdee and Contributors
# See license.txt

import frappe
import json
from frappe.tests.utils import FrappeTestCase
from production_api.production_api.doctype.cutting_marker.cutting_marker import (
	calculate_parts, get_panels_and_size, get_primary_and_bundle_detail,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_attribute(attr_name):
	if not frappe.db.exists("Item Attribute", attr_name):
		frappe.get_doc({"doctype": "Item Attribute", "attribute_name": attr_name}).insert(ignore_permissions=True)
	return attr_name


def ensure_attribute_value(attr_name, value):
	if not frappe.db.exists("Item Attribute Value", value):
		frappe.get_doc({
			"doctype": "Item Attribute Value",
			"attribute_name": attr_name,
			"attribute_value": value,
		}).insert(ignore_permissions=True)
	return value


def ensure_process(name):
	if not frappe.db.exists("Process", name):
		frappe.get_doc({"doctype": "Process", "process_name": name}).insert(ignore_permissions=True)
	return name


def ensure_item_group(name):
	if not frappe.db.exists("Item Group", name):
		frappe.get_doc({"doctype": "Item Group", "item_group_name": name}).insert(ignore_permissions=True)
	return name


def configure_ipd_settings(cfg):
	"""Set IPD Settings fields from *cfg* dict and return the original values."""
	settings = frappe.get_single("IPD Settings")
	orig = {}
	for key, val in cfg.items():
		orig[key] = settings.get(key)
		settings.set(key, val)
	settings.save(ignore_permissions=True)
	frappe.clear_cache()
	return orig


def restore_ipd_settings(orig):
	settings = frappe.get_single("IPD Settings")
	for key, val in orig.items():
		settings.set(key, val)
	settings.save(ignore_permissions=True)
	frappe.clear_cache()


def create_cod(item_name, sizes, colours, panels):
	"""Create a Cutting Order Detail with child tables."""
	cod = frappe.get_doc({
		"doctype": "Cutting Order Detail",
		"item": item_name,
		"attribute_no": len(colours),
		"attribute_values": [{"attribute_value": c} for c in colours],
		"stiching_item_details": [
			{"stiching_attribute_value": p, "quantity": 1} for p in panels
		],
	})
	cod.insert(ignore_permissions=True)

	# Populate the primary-attribute mapping with sizes
	for row in cod.item_attributes:
		if row.attribute == cod.primary_attribute and row.mapping:
			mapping_doc = frappe.get_doc("Item Item Attribute Mapping", row.mapping)
			mapping_doc.set("values", [{"attribute_value": s} for s in sizes])
			mapping_doc.save(ignore_permissions=True)
			break

	# Populate the packing-attribute mapping with colours
	for row in cod.item_attributes:
		if row.attribute == cod.packing_attribute and row.mapping:
			mapping_doc = frappe.get_doc("Item Item Attribute Mapping", row.mapping)
			mapping_doc.set("values", [{"attribute_value": c} for c in colours])
			mapping_doc.save(ignore_permissions=True)
			break

	return cod


def create_and_submit_co(cod, colours, sizes):
	"""Create a Cutting Order linked to *cod*, populate items_json, and submit."""
	items = []
	for colour in colours:
		quantities = {s: 10 for s in sizes}
		items.append({"colour": colour, "quantities": quantities})

	co = frappe.get_doc({
		"doctype": "Cutting Order",
		"cutting_order_detail": cod.name,
		"items_json": json.dumps({"items": items}),
	})
	co.insert(ignore_permissions=True)
	co.submit()
	return co


def create_cutting_marker(cutting_order=None, cutting_plan=None, marker_name="Test Marker"):
	"""Create (but don't submit) a Cutting Marker, then save once more to
	exercise the full save() path (where _validate_links runs after item is set)."""
	doc = frappe.get_doc({
		"doctype": "Cutting Marker",
		"cutting_order": cutting_order,
		"cutting_plan": cutting_plan,
		"marker_name": marker_name,
		"selected_type": "Auto",
	})
	doc.insert(ignore_permissions=True)
	# Re-save to trigger the real _validate_links path:
	# On insert(), _validate_links runs before before_validate (item is None → skipped).
	# On save(), _validate_links runs when item is already populated → would crash
	# if the code incorrectly sets a non-existent Item link.
	doc.save(ignore_permissions=True)
	return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCuttingMarker(FrappeTestCase):

	SIZES = ["_TCM S", "_TCM M", "_TCM L"]
	COLOURS = ["_TCM Red"]
	PANELS = ["_TCM Front", "_TCM Back"]

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		# 1. Attributes
		ensure_attribute("_TCM Dia")
		ensure_attribute("_TCM Colour")
		ensure_attribute("_TCM Panel")
		ensure_attribute("_TCM Set")
		ensure_attribute("_TCM Stage")

		# 2. Attribute values
		for s in cls.SIZES:
			ensure_attribute_value("_TCM Dia", s)
		for c in cls.COLOURS:
			ensure_attribute_value("_TCM Colour", c)
		for p in cls.PANELS:
			ensure_attribute_value("_TCM Panel", p)
		ensure_attribute_value("_TCM Stage", "_TCM Pack In")
		ensure_attribute_value("_TCM Stage", "_TCM Pack Out")
		ensure_attribute_value("_TCM Stage", "_TCM Stitch In")
		ensure_attribute_value("_TCM Stage", "_TCM Stitch Out")

		# 3. Processes
		ensure_process("_TCM Cutting")
		ensure_process("_TCM Stitching")
		ensure_process("_TCM Packing")

		# 4. Item Group
		ensure_item_group("_TCM Group")

		# 5. IPD Settings
		cls._orig_ipd = configure_ipd_settings({
			"item_group": "_TCM Group",
			"default_primary_attribute": "_TCM Dia",
			"default_packing_attribute": "_TCM Colour",
			"default_stitching_attribute": "_TCM Panel",
			"default_set_item_attribute": "_TCM Set",
			"default_cutting_process": "_TCM Cutting",
			"default_stitching_process": "_TCM Stitching",
			"default_packing_process": "_TCM Packing",
			"default_pack_in_stage": "_TCM Pack In",
			"default_pack_out_stage": "_TCM Pack Out",
			"default_stitching_in_stage": "_TCM Stitch In",
			"default_stitching_out_stage": "_TCM Stitch Out",
		})

		# 6. COD + CO  (CO.item = "_TCM Test Item" — no Item doc exists on purpose)
		cls.cod = create_cod("_TCM Test Item", cls.SIZES, cls.COLOURS, cls.PANELS)
		cls.co = create_and_submit_co(cls.cod, cls.COLOURS, cls.SIZES)

	@classmethod
	def tearDownClass(cls):
		restore_ipd_settings(cls._orig_ipd)
		super().tearDownClass()

	# --- Validation tests ---

	def test_requires_parent(self):
		"""CM without either Cutting Plan or Cutting Order should throw."""
		doc = frappe.get_doc({
			"doctype": "Cutting Marker",
			"marker_name": "No Parent",
			"selected_type": "Auto",
		})
		self.assertRaises(frappe.ValidationError, doc.insert, ignore_permissions=True)

	def test_co_parent_must_be_submitted(self):
		"""CM with a draft (unsubmitted) CO should throw."""
		draft_co = frappe.get_doc({
			"doctype": "Cutting Order",
			"cutting_order_detail": self.cod.name,
		})
		draft_co.insert(ignore_permissions=True)

		doc = frappe.get_doc({
			"doctype": "Cutting Marker",
			"cutting_order": draft_co.name,
			"marker_name": "Draft CO Marker",
			"selected_type": "Auto",
		})
		self.assertRaises(frappe.ValidationError, doc.insert, ignore_permissions=True)

	# --- Field population tests (CO path) ---

	def test_co_item_populated(self):
		"""CM saved against CO should have item set from CO."""
		cm = create_cutting_marker(cutting_order=self.co.name)
		self.assertEqual(cm.item, self.co.item)

	def test_co_version_is_v3(self):
		"""CM saved against CO should have version='V3'."""
		cm = create_cutting_marker(cutting_order=self.co.name)
		self.assertEqual(cm.version, "V3")

	def test_co_is_manual_entry_zero(self):
		"""CM saved against CO should have is_manual_entry=0."""
		cm = create_cutting_marker(cutting_order=self.co.name)
		self.assertEqual(cm.is_manual_entry, 0)

	def test_co_lot_is_none(self):
		"""CM saved against CO should have lot=None."""
		cm = create_cutting_marker(cutting_order=self.co.name)
		self.assertFalse(cm.lot)

	# --- Whitelisted API tests (CO path) ---

	def test_calculate_parts_co(self):
		"""calculate_parts(cutting_order=co) should return panel list."""
		result = calculate_parts(cutting_order=self.co.name)
		parts = [r["part"] for r in result]
		for panel in self.PANELS:
			self.assertIn(panel, parts)

	def test_get_panels_and_size_co(self):
		"""get_panels_and_size should return sizes + panels for CO."""
		result = get_panels_and_size(cutting_order=self.co.name)
		self.assertIn("sizes", result)
		self.assertIn("panels", result)
		for s in self.SIZES:
			self.assertIn(s, result["sizes"])
		panel_names = [p["part"] for p in result["panels"]]
		for p in self.PANELS:
			self.assertIn(p, panel_names)

	def test_get_primary_and_bundle_detail_co_no_crash(self):
		"""get_primary_and_bundle_detail should not crash (NameError) for CO path."""
		panels = json.dumps(self.PANELS)
		grp_panels = json.dumps(self.PANELS)
		result = get_primary_and_bundle_detail(
			cutting_order=self.co.name,
			selected_value="Auto",
			panels=panels,
			grp_panels=grp_panels,
		)
		self.assertIn("primary", result)
		self.assertIn("grp_items", result)
		# CO path should return empty grp_items (no IPD marker groups)
		self.assertEqual(result["grp_items"], [])
