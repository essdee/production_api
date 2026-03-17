# Copyright (c) 2024, Essdee and Contributors
# See license.txt

import frappe
import json
from frappe.tests.utils import FrappeTestCase

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


def ensure_spreader(name):
	if not frappe.db.exists("Cutting Spreader", name):
		frappe.get_doc({"doctype": "Cutting Spreader", "spreader": name}).insert(ignore_permissions=True)
	return name


def ensure_cutter(name):
	if not frappe.db.exists("Cutter", name):
		frappe.get_doc({"doctype": "Cutter", "cutter": name}).insert(ignore_permissions=True)
	return name


def configure_ipd_settings(cfg):
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

	for row in cod.item_attributes:
		if row.attribute == cod.primary_attribute and row.mapping:
			mapping_doc = frappe.get_doc("Item Item Attribute Mapping", row.mapping)
			mapping_doc.set("values", [{"attribute_value": s} for s in sizes])
			mapping_doc.save(ignore_permissions=True)
			break

	for row in cod.item_attributes:
		if row.attribute == cod.packing_attribute and row.mapping:
			mapping_doc = frappe.get_doc("Item Item Attribute Mapping", row.mapping)
			mapping_doc.set("values", [{"attribute_value": c} for c in colours])
			mapping_doc.save(ignore_permissions=True)
			break

	return cod


def create_and_submit_co(cod, colours, sizes):
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


def create_and_submit_marker(cutting_order=None, cutting_plan=None,
							 marker_name="Test Marker", panels=None):
	"""Create and submit a Cutting Marker with length/width set."""
	fields = {
		"doctype": "Cutting Marker",
		"cutting_order": cutting_order,
		"cutting_plan": cutting_plan,
		"marker_name": marker_name,
		"selected_type": "Auto",
		"length": 1.5,
		"width": 60.0,
	}
	if panels:
		fields["calculated_parts"] = ",".join(panels)

	doc = frappe.get_doc(fields)
	doc.insert(ignore_permissions=True)
	# Re-save before submit to exercise the real _validate_links path.
	# If `item` were set to a non-existent Item, this would crash.
	doc.save(ignore_permissions=True)
	doc.submit()
	return doc


def create_laysheet(cutting_order=None, cutting_plan=None, cutting_marker=None,
					spreader="_TCLS Spreader", cutter="_TCLS Cutter"):
	doc = frappe.get_doc({
		"doctype": "Cutting LaySheet",
		"cutting_order": cutting_order,
		"cutting_plan": cutting_plan,
		"cutting_marker": cutting_marker,
		"cutting_spreader": spreader,
		"cutter": cutter,
	})
	doc.insert(ignore_permissions=True)
	# Re-save to exercise _validate_links with populated fields
	doc.save(ignore_permissions=True)
	doc.reload()
	return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCuttingLaySheet(FrappeTestCase):

	SIZES = ["_TCLS S", "_TCLS M", "_TCLS L"]
	COLOURS = ["_TCLS Red"]
	PANELS = ["_TCLS Front", "_TCLS Back"]

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		# 1. Attributes
		ensure_attribute("_TCLS Dia")
		ensure_attribute("_TCLS Colour")
		ensure_attribute("_TCLS Panel")
		ensure_attribute("_TCLS Set")
		ensure_attribute("_TCLS Stage")

		# 2. Attribute values
		for s in cls.SIZES:
			ensure_attribute_value("_TCLS Dia", s)
		for c in cls.COLOURS:
			ensure_attribute_value("_TCLS Colour", c)
		for p in cls.PANELS:
			ensure_attribute_value("_TCLS Panel", p)
		ensure_attribute_value("_TCLS Stage", "_TCLS Pack In")
		ensure_attribute_value("_TCLS Stage", "_TCLS Pack Out")
		ensure_attribute_value("_TCLS Stage", "_TCLS Stitch In")
		ensure_attribute_value("_TCLS Stage", "_TCLS Stitch Out")

		# 3. Processes
		ensure_process("_TCLS Cutting")
		ensure_process("_TCLS Stitching")
		ensure_process("_TCLS Packing")

		# 4. Item Group
		ensure_item_group("_TCLS Group")

		# 5. IPD Settings
		cls._orig_ipd = configure_ipd_settings({
			"item_group": "_TCLS Group",
			"default_primary_attribute": "_TCLS Dia",
			"default_packing_attribute": "_TCLS Colour",
			"default_stitching_attribute": "_TCLS Panel",
			"default_set_item_attribute": "_TCLS Set",
			"default_cutting_process": "_TCLS Cutting",
			"default_stitching_process": "_TCLS Stitching",
			"default_packing_process": "_TCLS Packing",
			"default_pack_in_stage": "_TCLS Pack In",
			"default_pack_out_stage": "_TCLS Pack Out",
			"default_stitching_in_stage": "_TCLS Stitch In",
			"default_stitching_out_stage": "_TCLS Stitch Out",
		})

		# 6. COD + CO  (CO.item = "_TCLS Test Item" — no Item doc exists)
		cls.cod = create_cod("_TCLS Test Item", cls.SIZES, cls.COLOURS, cls.PANELS)
		cls.co = create_and_submit_co(cls.cod, cls.COLOURS, cls.SIZES)

		# 7. Submitted Cutting Marker
		cls.cm = create_and_submit_marker(
			cutting_order=cls.co.name,
			marker_name="_TCLS Marker",
			panels=cls.PANELS,
		)

		# 8. Spreader + Cutter
		ensure_spreader("_TCLS Spreader")
		ensure_cutter("_TCLS Cutter")

	@classmethod
	def tearDownClass(cls):
		restore_ipd_settings(cls._orig_ipd)
		super().tearDownClass()

	# --- Validation tests ---

	def test_requires_parent(self):
		"""CLS without either Cutting Plan or Cutting Order should throw."""
		doc = frappe.get_doc({
			"doctype": "Cutting LaySheet",
			"cutting_marker": self.cm.name,
			"cutting_spreader": "_TCLS Spreader",
			"cutter": "_TCLS Cutter",
		})
		self.assertRaises(frappe.ValidationError, doc.insert, ignore_permissions=True)

	def test_requires_submitted_marker(self):
		"""CLS with a draft (unsubmitted) marker should throw."""
		draft_cm = frappe.get_doc({
			"doctype": "Cutting Marker",
			"cutting_order": self.co.name,
			"marker_name": "_TCLS Draft Marker",
			"selected_type": "Auto",
		})
		draft_cm.insert(ignore_permissions=True)

		doc = frappe.get_doc({
			"doctype": "Cutting LaySheet",
			"cutting_order": self.co.name,
			"cutting_marker": draft_cm.name,
			"cutting_spreader": "_TCLS Spreader",
			"cutter": "_TCLS Cutter",
		})
		self.assertRaises(frappe.ValidationError, doc.insert, ignore_permissions=True)

	def test_marker_parent_must_match(self):
		"""CLS CO parent must match marker's CO parent."""
		cod2 = create_cod("_TCLS Item 2", self.SIZES, self.COLOURS, self.PANELS)
		co2 = create_and_submit_co(cod2, self.COLOURS, self.SIZES)

		# self.cm belongs to self.co, but we point CLS at co2
		doc = frappe.get_doc({
			"doctype": "Cutting LaySheet",
			"cutting_order": co2.name,
			"cutting_marker": self.cm.name,
			"cutting_spreader": "_TCLS Spreader",
			"cutter": "_TCLS Cutter",
		})
		self.assertRaises(frappe.ValidationError, doc.insert, ignore_permissions=True)

	# --- Field population tests (CO path) ---

	def test_co_item_populated(self):
		"""CLS created against CO should have item set from CO."""
		cls_doc = create_laysheet(cutting_order=self.co.name, cutting_marker=self.cm.name)
		self.assertEqual(cls_doc.item, self.co.item)

	def test_co_lot_is_none(self):
		"""CLS created against CO should have lot=None."""
		cls_doc = create_laysheet(cutting_order=self.co.name, cutting_marker=self.cm.name)
		self.assertFalse(cls_doc.lot)

	# --- Lay number and status tests ---

	def test_co_lay_no_incremented(self):
		"""First CLS should get lay_no=1, and CO's lay_no should be updated."""
		frappe.db.set_value("Cutting Order", self.co.name, "lay_no", 0)

		cls_doc = create_laysheet(cutting_order=self.co.name, cutting_marker=self.cm.name)
		self.assertEqual(cls_doc.lay_no, 1)

		co_lay = frappe.db.get_value("Cutting Order", self.co.name, "lay_no")
		self.assertEqual(co_lay, 1)

	def test_co_status_updates_on_first_lay(self):
		"""CO status should become 'Cutting In Progress' after first laysheet."""
		frappe.db.set_value("Cutting Order", self.co.name, {
			"co_status": "Submitted",
			"lay_no": 0,
		})

		cls_doc = create_laysheet(cutting_order=self.co.name, cutting_marker=self.cm.name)
		self.assertEqual(cls_doc.lay_no, 1)

		co_status = frappe.db.get_value("Cutting Order", self.co.name, "co_status")
		self.assertEqual(co_status, "Cutting In Progress")
