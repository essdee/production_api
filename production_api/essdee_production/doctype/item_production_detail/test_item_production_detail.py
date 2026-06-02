# Copyright (c) 2024, Essdee and Contributors
# See license.txt

from types import SimpleNamespace

from frappe.tests.utils import FrappeTestCase

from production_api.essdee_production.doctype.item_production_detail.item_production_detail import (
	build_assortment_box_grid,
	check_assortment_data,
	derive_assortment_attributes,
)


class TestDeriveAssortmentAttributes(FrappeTestCase):
	"""The assorted dimension is auto-derived: the box dimensions minus the separator."""

	def test_separator_colour_assorts_size(self):
		ipd = SimpleNamespace(primary_item_attribute="Size", packing_attribute="Colour")
		self.assertEqual(derive_assortment_attributes(ipd, "Colour"), ["Size"])

	def test_separator_size_assorts_colour(self):
		ipd = SimpleNamespace(primary_item_attribute="Size", packing_attribute="Colour")
		self.assertEqual(derive_assortment_attributes(ipd, "Size"), ["Colour"])


class TestPackingAssortmentBuilder(FrappeTestCase):
	"""Pure tests for the export box-assortment grid builder (no DB fixtures)."""

	def test_one_box_per_separator_with_size_rows(self):
		boxes = build_assortment_box_grid(
			separator_attribute="Colour",
			separator_values=["Red", "Blue"],
			assortment_attributes=["Size"],
			assorted_value_lists={"Size": ["S", "M", "L"]},
		)
		self.assertEqual([b["separator_value"] for b in boxes], ["Red", "Blue"])
		red = boxes[0]
		self.assertEqual([r["Size"] for r in red["rows"]], ["S", "M", "L"])
		self.assertTrue(all(r["qty"] == 0 for r in red["rows"]))

	def test_preserves_existing_qty_on_rebuild(self):
		existing = {("Red", frozenset({"Size": "S"}.items())): 7}
		boxes = build_assortment_box_grid(
			"Colour", ["Red"], ["Size"], {"Size": ["S", "M"]}, existing)
		self.assertEqual(boxes[0]["rows"][0]["qty"], 7)
		self.assertEqual(boxes[0]["rows"][1]["qty"], 0)

	def test_cartesian_of_two_assorted_attrs(self):
		boxes = build_assortment_box_grid(
			"Part", ["Top"], ["Size", "Colour"],
			{"Size": ["S", "M"], "Colour": ["Red", "Blue"]})
		self.assertEqual(len(boxes[0]["rows"]), 4)


class TestPackingAssortmentValidation(FrappeTestCase):
	"""Pure tests for the assortment grid validator (no DB fixtures)."""

	def test_zero_total_box_is_rejected(self):
		data = {
			"assortment_attributes": ["Size"],
			"boxes": [{"box": "Red", "separator_value": "Red",
			           "rows": [{"Size": "S", "qty": 0}, {"Size": "M", "qty": 0}]}],
		}
		errors = check_assortment_data(data, "Colour", {"Size", "Colour"})
		self.assertTrue(any("zero total quantity" in e for e in errors))

	def test_box_mixing_two_separator_values_is_rejected(self):
		data = {
			"assortment_attributes": ["Size", "Colour"],
			"boxes": [{"box": "B1", "separator_value": None,
			           "rows": [{"Colour": "Red", "Size": "S", "qty": 2},
			                    {"Colour": "Blue", "Size": "M", "qty": 3}]}],
		}
		errors = check_assortment_data(data, "Colour", {"Size", "Colour"})
		self.assertTrue(any("mixes more than one Colour" in e for e in errors))

	def test_valid_single_colour_box_passes(self):
		data = {
			"assortment_attributes": ["Size"],
			"boxes": [{"box": "Red", "separator_value": "Red",
			           "rows": [{"Size": "S", "qty": 2}, {"Size": "M", "qty": 3}, {"Size": "L", "qty": 5}]}],
		}
		errors = check_assortment_data(data, "Colour", {"Size", "Colour"})
		self.assertEqual(errors, [])

	def test_unknown_assortment_attr_is_rejected(self):
		data = {
			"assortment_attributes": ["Bogus"],
			"boxes": [{"box": "Red", "separator_value": "Red", "rows": [{"Bogus": "x", "qty": 1}]}],
		}
		errors = check_assortment_data(data, "Colour", {"Size", "Colour"})
		self.assertTrue(any("not an attribute of this item" in e for e in errors))
