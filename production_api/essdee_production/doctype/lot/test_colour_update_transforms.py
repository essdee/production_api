# Copyright (c) 2026, Essdee and Contributors
# See license.txt

"""Pure unit tests for the Lot "Update Colour" transform foundation.

Every test here is DB-free on purpose: the module under test
(colour_update_transforms) must stay pure so it can be reused by both the
preview and the apply endpoints.  Plain unittest.TestCase (not FrappeTestCase)
keeps that contract visible and avoids any site/DB fixture for this file.
"""

import copy
import unittest

from production_api.essdee_production.doctype.lot.colour_update_transforms import (
	PAYLOAD_SCHEMA_VERSION,
	normalize_payload,
	parse_json_structure,
	serialize_like_original,
	structure_uses_attribute,
	transform_combination_rows,
	transform_major_colour_rows,
	transform_packing_attribute_rows,
	transform_panel_cloth_matrix,
	transform_panel_consumption_matrix,
	transform_process_cost_values,
	transform_bom_mapping_values,
	transform_stitching_accessory_structure,
	validate_size_allocations,
)

# Real stored shapes, copied from tabItem Production Detail on mrp3.site
# (compact separators, key order preserved) so the round-trip test pins the
# exact serialization format the app writes today.
REAL_CUTTING_JSON = (
	'{"combination_type":"Cutting","attributes":["Part","Colour","Dia","Weight"],'
	'"items":[{"Part":"Front","Colour":"Black","Dia":"20 Dia","Weight":0.03}],'
	'"select_list":{}}'
)
REAL_CLOTH_JSON = (
	'{"combination_type":"Cloth","attributes":["Colour","Cloth"],'
	'"items":[{"Colour":"Off white","Cloth":"MAIN FABRIC"}],'
	'"select_list":["MAIN FABRIC"]}'
)


def make_source_structure():
	"""Cutting structure with per-row distinct values (plan section 3.5)."""
	return {
		"combination_type": "Cutting",
		"attributes": ["Part", "Colour", "Dia", "Weight"],
		"items": [
			{"Part": "Front", "Colour": "Black", "Dia": "20 Dia", "Weight": 0.03},
			{"Part": "Back", "Colour": "Black", "Dia": "22 Dia", "Weight": 0.04},
			{"Part": "Sleeve", "Colour": "Black", "Dia": "24 Dia", "Weight": 0.02},
		],
		"select_list": {},
	}


class TestTransformSplitConvert(unittest.TestCase):
	def test_split_clones_each_source_row_per_target(self):
		structure = make_source_structure()
		snapshot = copy.deepcopy(structure)

		result, diff = transform_combination_rows(
			structure, "Colour", "Black", [{"colour": "Black 2", "retained": False}], "split_convert"
		)

		# Every source row cloned per target; only the colour value replaced.
		# The source colour is not retained, so the original Black rows are
		# removed after cloning: the structure ends with only the 3 clones.
		rows = {(row["Part"], row["Colour"]): row for row in result["items"]}
		self.assertEqual(len(result["items"]), 3)
		self.assertEqual({row["Colour"] for row in result["items"]}, {"Black 2"})
		expected_values = {
			"Front": ("20 Dia", 0.03),
			"Back": ("22 Dia", 0.04),
			"Sleeve": ("24 Dia", 0.02),
		}
		for part, (dia, weight) in expected_values.items():
			clone = rows[(part, "Black 2")]
			self.assertEqual(clone["Dia"], dia)
			self.assertEqual(clone["Weight"], weight)

		# Top-level metadata retained untouched.
		self.assertEqual(result["combination_type"], "Cutting")
		self.assertEqual(result["attributes"], ["Part", "Colour", "Dia", "Weight"])
		self.assertEqual(result["select_list"], {})

		# Diff: 3 clones + 3 removals (source not retained), full entry shape.
		self.assertEqual([entry["action"] for entry in diff].count("cloned"), 3)
		self.assertEqual([entry["action"] for entry in diff].count("removed"), 3)
		for entry in diff:
			self.assertEqual(
				sorted(entry.keys()), ["action", "colour", "combination_key", "details"]
			)
		clone_entries = [entry for entry in diff if entry["action"] == "cloned"]
		self.assertEqual(
			clone_entries[0]["combination_key"],
			'{"Colour": "Black 2", "Dia": "20 Dia", "Part": "Front", "Weight": 0.03}',
		)

		# Purity: the input structure was not mutated.
		self.assertEqual(structure, snapshot)

	def test_future_row_keys_retained_and_deep_copied(self):
		structure = {
			"combination_type": "Cutting",
			"attributes": ["Part", "Colour", "Dia", "Weight"],
			"items": [
				{
					"Part": "Front",
					"Colour": "Black",
					"Dia": "20 Dia",
					"Weight": 0.03,
					"future_key": {"nested": ["a"]},
				}
			],
			"select_list": {},
		}
		snapshot = copy.deepcopy(structure)

		result, diff = transform_combination_rows(
			structure, "Colour", "Black", [{"colour": "Black 2", "retained": False}], "split_convert"
		)

		clone = result["items"][0]
		self.assertEqual(clone["Part"], "Front")
		self.assertEqual(clone["future_key"], {"nested": ["a"]})
		# No mutable object shared between the clone and the source row.
		self.assertIsNot(clone, structure["items"][0])
		self.assertIsNot(clone["future_key"], structure["items"][0]["future_key"])
		self.assertIsNot(
			clone["future_key"]["nested"], structure["items"][0]["future_key"]["nested"]
		)
		self.assertEqual(structure, snapshot)
		self.assertEqual(diff[0]["action"], "cloned")

	def test_split_replaces_only_the_packing_attribute(self):
		structure = {
			"attributes": ["Colour", "Accessory Colour", "Cloth"],
			"items": [
				{
					"Colour": "Black",
					"Accessory Colour": "Black",
					"Cloth": "RIB",
				}
			],
		}
		result, _diff = transform_combination_rows(
			structure,
			"Colour",
			"Black",
			[{"colour": "Navy", "retained": False}],
			"split_convert",
		)
		self.assertEqual(
			result["items"],
			[{"Colour": "Navy", "Accessory Colour": "Black", "Cloth": "RIB"}],
		)

	def test_configured_fields_are_compared_not_used_as_identity(self):
		structure = {
			"attributes": ["Part", "Colour", "Dia", "Weight"],
			"items": [
				{"Part": "Front", "Colour": "Black", "Dia": "20 Dia", "Weight": 0.03},
				{"Part": "Front", "Colour": "Navy", "Dia": "22 Dia", "Weight": 0.04},
			],
		}
		result, diff = transform_combination_rows(
			structure,
			"Colour",
			"Black",
			[{"colour": "Navy", "retained": False}],
			"split_convert",
			configured_fields=("Dia", "Weight"),
		)
		self.assertEqual(len(result["items"]), 1)
		conflict = next(entry for entry in diff if entry["action"] == "conflict")
		self.assertEqual(conflict["details"]["fields"]["Dia"]["existing"], "22 Dia")
		self.assertEqual(conflict["details"]["fields"]["Dia"]["new"], "20 Dia")

	def test_compatible_existing_target_merges_without_duplicate(self):
		structure = make_source_structure()
		structure["items"] = [
			structure["items"][0],  # Black Front
			structure["items"][1],  # Black Back
			# Compatible pre-existing target row: identical Dia/Weight values.
			{"Part": "Front", "Colour": "Black 2", "Dia": "20 Dia", "Weight": 0.03},
		]

		result, diff = transform_combination_rows(
			structure, "Colour", "Black", [{"colour": "Black 2", "retained": False}], "split_convert"
		)

		# No duplicate Front/Black 2 row; the two Black rows were removed.
		front_clones = [
			row for row in result["items"] if row["Part"] == "Front" and row["Colour"] == "Black 2"
		]
		self.assertEqual(len(front_clones), 1)
		self.assertEqual(len(result["items"]), 2)

		actions = sorted(entry["action"] for entry in diff)
		self.assertEqual(actions, ["cloned", "merged", "removed", "removed"])
		merged = next(entry for entry in diff if entry["action"] == "merged")
		self.assertEqual(merged["colour"], "Black 2")
		self.assertEqual(
			merged["combination_key"],
			'{"Colour": "Black 2", "Dia": "20 Dia", "Part": "Front", "Weight": 0.03}',
		)

	def test_conflicting_existing_target_records_conflict_and_keeps_rows(self):
		structure = {
			"combination_type": "Cutting",
			"attributes": ["Part", "Colour", "Dia", "Weight"],
			"items": [
				{
					"Part": "Front",
					"Colour": "Black",
					"Dia": "20 Dia",
					"Weight": 0.03,
					"future_key": "source-value",
				},
				{
					"Part": "Front",
					"Colour": "Black 2",
					"Dia": "20 Dia",
					"Weight": 0.03,
					"future_key": "other-value",
				},
			],
			"select_list": {},
		}
		snapshot = copy.deepcopy(structure)

		result, diff = transform_combination_rows(
			structure, "Colour", "Black", [{"colour": "Black 2", "retained": False}], "split_convert"
		)

		conflicts = [entry for entry in diff if entry["action"] == "conflict"]
		self.assertEqual(len(conflicts), 1)
		self.assertEqual(conflicts[0]["colour"], "Black 2")
		self.assertEqual(
			conflicts[0]["combination_key"],
			'{"Colour": "Black 2", "Dia": "20 Dia", "Part": "Front", "Weight": 0.03}',
		)
		self.assertEqual(
			conflicts[0]["details"]["fields"]["future_key"],
			{"existing": "other-value", "new": "source-value"},
		)
		# Structure not corrupted: exactly one Front/Black 2 row and its
		# existing value is untouched.
		front_rows = [
			row for row in result["items"] if row["Part"] == "Front" and row["Colour"] == "Black 2"
		]
		self.assertEqual(len(front_rows), 1)
		self.assertEqual(front_rows[0]["future_key"], "other-value")
		self.assertEqual(structure, snapshot)

	def test_source_in_targets_keeps_single_source_row_set(self):
		structure = make_source_structure()

		result, diff = transform_combination_rows(
			structure,
			"Colour",
			"Black",
			[
				{"colour": "Black", "retained": True},
				{"colour": "Navy", "retained": False},
			],
			"split_convert",
		)

		# Source rows kept exactly once, clones added for the other target.
		black_rows = [row for row in result["items"] if row["Colour"] == "Black"]
		navy_rows = [row for row in result["items"] if row["Colour"] == "Navy"]
		self.assertEqual(len(black_rows), 3)
		self.assertEqual(len(navy_rows), 3)
		self.assertEqual(len(result["items"]), 6)

		actions = sorted(entry["action"] for entry in diff)
		self.assertEqual(actions, ["cloned", "cloned", "cloned", "unchanged", "unchanged", "unchanged"])
		unchanged = [entry for entry in diff if entry["action"] == "unchanged"]
		self.assertTrue(all(entry["colour"] == "Black" for entry in unchanged))

	def test_source_absent_from_targets_removes_source_rows(self):
		structure = make_source_structure()

		result, diff = transform_combination_rows(
			structure, "Colour", "Black", [{"colour": "Navy", "retained": False}], "split_convert"
		)

		self.assertEqual([row["Colour"] for row in result["items"]], ["Navy"] * 3)
		self.assertEqual([entry["action"] for entry in diff].count("removed"), 3)
		self.assertTrue(all(entry["colour"] == "Black" for entry in diff if entry["action"] == "removed"))


class TestTransformRemove(unittest.TestCase):
	def test_remove_deletes_only_source_rows(self):
		structure = make_source_structure()
		structure["items"] = [
			structure["items"][0],  # Black Front
			{"Part": "Front", "Colour": "Navy", "Dia": "20 Dia", "Weight": 0.05},
			{"Part": "Back", "Colour": "White", "Dia": "22 Dia", "Weight": 0.06},
		]
		snapshot = copy.deepcopy(structure)

		result, diff = transform_combination_rows(structure, "Colour", "Black", [], "remove")

		self.assertEqual(len(result["items"]), 2)
		self.assertEqual(
			result["items"],
			[
				{"Part": "Front", "Colour": "Navy", "Dia": "20 Dia", "Weight": 0.05},
				{"Part": "Back", "Colour": "White", "Dia": "22 Dia", "Weight": 0.06},
			],
		)
		self.assertEqual([entry["action"] for entry in diff], ["removed"])
		self.assertEqual(diff[0]["colour"], "Black")
		self.assertEqual(
			diff[0]["combination_key"],
			'{"Colour": "Black", "Dia": "20 Dia", "Part": "Front", "Weight": 0.03}',
		)
		self.assertEqual(structure, snapshot)


class TestTransformAdd(unittest.TestCase):
	def test_add_canonicalizes_row_keys_to_declared_column_order(self):
		structure = {
			"attributes": ["Colour", "Dia", "Weight"],
			"items": [],
		}
		result, _ = transform_combination_rows(
			structure,
			"Colour",
			None,
			[],
			"add",
			new_rows=[{"Dia": "10 Dia", "Weight": 0.1, "Colour": "A Mel"}],
		)
		self.assertEqual(list(result["items"][0]), ["Colour", "Dia", "Weight"])
		self.assertEqual(
			result["items"][0],
			{"Colour": "A Mel", "Dia": "10 Dia", "Weight": 0.1},
		)

	def test_add_appends_new_rows_and_conflict_checks_them(self):
		structure = {
			"combination_type": "Cloth",
			"attributes": ["Colour", "Cloth"],
			"items": [{"Colour": "Navy", "Cloth": "MAIN FABRIC"}],
			"select_list": ["MAIN FABRIC"],
		}
		new_rows = [
			{"Colour": "Red", "Cloth": "MAIN FABRIC"},
			{"Colour": "Navy", "Cloth": "MAIN FABRIC"},  # identical combination -> merge
			{"Colour": "Navy", "Cloth": "RIB", "future_key": "x"},  # same combination key? no: Cloth differs
		]

		result, diff = transform_combination_rows(
			structure, "Colour", None, [], "add", new_rows=new_rows
		)

		# Red appended; Navy/Main FABRIC merged (no duplicate); Navy/RIB has a
		# different combination key (Cloth is a declared attribute) so it is a
		# new row, appended with its future key preserved.
		self.assertEqual(len(result["items"]), 3)
		self.assertEqual(result["select_list"], ["MAIN FABRIC"])
		actions = sorted(entry["action"] for entry in diff)
		self.assertEqual(actions, ["cloned", "cloned", "merged"])
		merged = next(entry for entry in diff if entry["action"] == "merged")
		self.assertEqual(merged["colour"], "Navy")
		self.assertEqual(merged["combination_key"], '{"Cloth": "MAIN FABRIC", "Colour": "Navy"}')

	def test_add_conflicting_existing_combination_reports_conflict(self):
		structure = {
			"combination_type": "Cutting",
			"attributes": ["Part", "Colour", "Dia", "Weight"],
			"items": [
				{"Part": "Front", "Colour": "Red", "Dia": "20 Dia", "Weight": 0.03, "note": "kept"}
			],
			"select_list": {},
		}
		new_rows = [
			{"Part": "Front", "Colour": "Red", "Dia": "20 Dia", "Weight": 0.03, "note": "different"}
		]

		result, diff = transform_combination_rows(
			structure, "Colour", None, [], "add", new_rows=new_rows
		)

		self.assertEqual(len(result["items"]), 1)
		self.assertEqual(result["items"][0]["note"], "kept")
		self.assertEqual([entry["action"] for entry in diff], ["conflict"])
		self.assertEqual(
			diff[0]["details"]["fields"]["note"], {"existing": "kept", "new": "different"}
		)


class TestColourAbsenceSafety(unittest.TestCase):
	def test_structure_without_packing_attribute_is_deeply_unchanged(self):
		# Colour appears nowhere in the declared attributes (plan section 3.4:
		# e.g. an IPD with only Part + Dia + Weight must stay unchanged).
		structure = {
			"combination_type": "Cutting",
			"attributes": ["Part", "Dia", "Weight"],
			"items": [
				{"Part": "Top", "Dia": "60 Dia", "Weight": 0.143},
				{"Part": "Bottom", "Dia": "60 Dia", "Weight": 0.101},
			],
			"select_list": {},
		}
		snapshot = copy.deepcopy(structure)

		for mode, targets in (
			("split_convert", [{"colour": "Black 2", "retained": False}]),
			("remove", []),
			("add", None),
		):
			kwargs = {"new_rows": [{"Part": "Top", "Colour": "Red"}]} if mode == "add" else {}
			result, diff = transform_combination_rows(
				structure, "Colour", "Black", targets, mode, **kwargs
			)
			self.assertEqual(diff, [])
			self.assertEqual(result, snapshot)  # deep equality, not just same repr
			self.assertIsNot(result, structure)  # a copy, never the same object

	def test_non_combination_dicts_are_returned_unchanged(self):
		# accessory_clothtype_json / emblishment_details_json store plain
		# mappings with no declared attributes list; they must never be touched.
		structure = {"ACCESSORY A": "MAIN FABRIC", "ACCESSORY B": "RIB"}

		result, diff = transform_combination_rows(
			structure, "Colour", "Black", [{"colour": "Navy", "retained": False}], "split_convert"
		)

		self.assertEqual(result, {"ACCESSORY A": "MAIN FABRIC", "ACCESSORY B": "RIB"})
		self.assertEqual(diff, [])

	def test_invalid_mode_raises_for_the_caller(self):
		structure = make_source_structure()
		with self.assertRaises(ValueError):
			transform_combination_rows(
				structure, "Colour", "Black", [{"colour": "Navy", "retained": False}], "rename"
			)

	def test_malformed_target_entry_raises_for_the_caller(self):
		structure = make_source_structure()
		for bad_target in ({"retained": False}, "Navy", None):
			with self.assertRaises(ValueError):
				transform_combination_rows(
					structure, "Colour", "Black", [bad_target], "split_convert"
				)

	def test_malformed_new_row_raises_for_the_caller(self):
		structure = make_source_structure()
		with self.assertRaises(ValueError):
			transform_combination_rows(
				structure, "Colour", None, [], "add", new_rows=["not a dict"]
			)

	def test_structure_with_declared_attributes_but_no_items_is_unchanged(self):
		structure = {"combination_type": "Cutting", "attributes": ["Colour"], "items": None}
		result, diff = transform_combination_rows(
			structure, "Colour", "Black", [{"colour": "Navy", "retained": False}], "split_convert"
		)
		self.assertEqual(result, structure)
		self.assertEqual(diff, [])


class TestStructureUsesAttribute(unittest.TestCase):
	def test_dict_shape_checks_declared_attributes_only(self):
		structure = {
			"combination_type": "Cutting",
			"attributes": ["Part", "Colour", "Dia", "Weight"],
			"items": [],
			"select_list": {},
		}
		self.assertTrue(structure_uses_attribute(structure, "Colour"))
		self.assertFalse(structure_uses_attribute(structure, "Colour 2"))

	def test_values_are_never_text_searched(self):
		# "Colour" appears only as a VALUE here, not in the declared attributes.
		structure = {
			"combination_type": "Cutting",
			"attributes": ["Part", "Dia", "Weight"],
			"items": [{"Part": "Colour", "Dia": "60 Dia", "Weight": 0.1}],
			"select_list": {},
		}
		self.assertFalse(structure_uses_attribute(structure, "Colour"))

	def test_list_of_rows_shape_is_recognised_defensively(self):
		rows = [{"Part": "Front", "Colour": "Black"}, {"Part": "Back", "Colour": "Black"}]
		self.assertTrue(structure_uses_attribute(rows, "Colour"))
		self.assertFalse(structure_uses_attribute(rows, "Size"))

	def test_non_structures_are_false(self):
		for value in (None, "", "abc", 5, {}, [], True):
			self.assertFalse(structure_uses_attribute(value, "Colour"))


class TestParseAndSerialize(unittest.TestCase):
	def test_round_trip_preserves_stored_string_exactly(self):
		for stored in (REAL_CUTTING_JSON, REAL_CLOTH_JSON):
			parsed, error = parse_json_structure(stored)
			self.assertIsNone(error)
			self.assertEqual(serialize_like_original(parsed, True), stored)

	def test_already_parsed_values_pass_through(self):
		structure = {"combination_type": "Cloth", "items": [{"Colour": "Navy"}]}
		parsed, error = parse_json_structure(structure)
		self.assertIsNone(error)
		self.assertIs(parsed, structure)

		parsed, error = parse_json_structure([{"Colour": "Navy"}])
		self.assertIsNone(error)
		self.assertEqual(parsed, [{"Colour": "Navy"}])

	def test_none_and_empty_are_absent_not_malformed(self):
		for value in (None, "", "   ", b""):
			parsed, error = parse_json_structure(value)
			self.assertIsNone(parsed)
			self.assertIsNone(error)

	def test_malformed_json_returns_error_note_without_raising(self):
		for value in ("{not json", b'{"broken":'):
			parsed, error = parse_json_structure(value)
			self.assertIsNone(parsed)
			self.assertIn("Malformed JSON", error)

	def test_scalar_json_is_rejected_with_a_note(self):
		parsed, error = parse_json_structure('42')
		self.assertIsNone(parsed)
		self.assertIn("not an object or array", error)

	def test_unsupported_types_return_error_note(self):
		parsed, error = parse_json_structure(5)
		self.assertIsNone(parsed)
		self.assertIn("Unsupported", error)

	def test_serialize_passthrough_when_original_was_parsed(self):
		structure = {"a": [1, 2]}
		self.assertEqual(serialize_like_original(structure, False), structure)

	def test_serialize_none_returns_none(self):
		self.assertIsNone(serialize_like_original(None, True))
		self.assertIsNone(serialize_like_original(None, False))

	def test_serialize_matches_frappe_json_field_format(self):
		structure = {"combination_type": "Cloth", "attributes": ["Colour", "Cloth"], "items": []}
		self.assertEqual(
			serialize_like_original(structure, True),
			'{"combination_type":"Cloth","attributes":["Colour","Cloth"],"items":[]}',
		)


class TestNormalizePayload(unittest.TestCase):
	def test_valid_split_convert_payload_normalizes(self):
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [
				{
					"colour": "Black 2",
					"size_quantities": {"S": 10, "M": 20},
					"packing_quantity": 5,
					"set_or_stitching_mapping": {"Black 2": "Black"},
					"cutting_rows": [{"Dia": "20 Dia", "Weight": 0.03}],
					"cloth_rows": [{"Cloth": "MAIN FABRIC"}],
				}
			],
			"reference_colour": None,
			"process_cost_values": {"Cutting": 12.5},
			"manual_packing_rows": [{"colour": "Black 2", "quantity": 2}],
			"reason": "Shade variation",
		}

		normalized, errors = normalize_payload(payload)

		self.assertEqual(errors, [])
		self.assertEqual(normalized["schema_version"], PAYLOAD_SCHEMA_VERSION)
		self.assertEqual(normalized["operation"], "split_convert")
		self.assertEqual(normalized["source_colour"], "Black")
		self.assertEqual(len(normalized["targets"]), 1)
		target = normalized["targets"][0]
		self.assertEqual(target["colour"], "Black 2")
		self.assertEqual(target["size_quantities"], {"S": 10, "M": 20})
		self.assertEqual(target["packing_quantity"], 5)
		self.assertEqual(target["set_or_stitching_mapping"], {"Black 2": "Black"})
		self.assertEqual(target["cutting_rows"], [{"Dia": "20 Dia", "Weight": 0.03}])
		self.assertEqual(target["cloth_rows"], [{"Cloth": "MAIN FABRIC"}])
		self.assertIsNone(normalized["reference_colour"])
		self.assertEqual(normalized["process_cost_values"], {"Cutting": 12.5})
		self.assertEqual(normalized["manual_packing_rows"], [{"colour": "Black 2", "quantity": 2}])
		self.assertEqual(normalized["reason"], "Shade variation")

	def test_valid_payload_with_missing_optional_fields_fills_defaults(self):
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [
				{"colour": "Black 2", "size_quantities": {"S": 10}},
				{"colour": "Navy", "packing_quantity": 4},
			],
			"reason": "Shade variation",
		}

		normalized, errors = normalize_payload(payload)

		self.assertEqual(errors, [])
		self.assertEqual(normalized["reference_colour"], None)
		self.assertEqual(normalized["process_cost_values"], {})
		self.assertEqual(normalized["manual_packing_rows"], [])
		self.assertEqual(normalized["targets"][0]["packing_quantity"], 0)
		self.assertEqual(normalized["targets"][0]["size_quantities"], {"S": 10})
		self.assertEqual(normalized["targets"][1]["size_quantities"], {})
		self.assertEqual(normalized["targets"][1]["packing_quantity"], 4)
		for target in normalized["targets"]:
			self.assertEqual(target["set_or_stitching_mapping"], {})
			self.assertEqual(target["cutting_rows"], [])
			self.assertEqual(target["cloth_rows"], [])

	def test_valid_remove_payload_normalizes(self):
		payload = {
			"operation": "remove",
			"source_colour": "Black",
			"targets": [],
			"reason": "Cancelled colour",
		}

		normalized, errors = normalize_payload(payload)

		self.assertEqual(errors, [])
		self.assertEqual(normalized["operation"], "remove")
		self.assertEqual(normalized["source_colour"], "Black")
		self.assertEqual(normalized["targets"], [])

	def test_valid_add_payload_normalizes(self):
		payload = {
			"operation": "add",
			"source_colour": None,
			"targets": [{"colour": "Red", "size_quantities": {"M": 4}}],
			"reference_colour": "Black",
			"reason": "New colour approved",
		}

		normalized, errors = normalize_payload(payload)

		self.assertEqual(errors, [])
		self.assertEqual(normalized["source_colour"], None)
		self.assertEqual(normalized["reference_colour"], "Black")
		self.assertEqual(len(normalized["targets"]), 1)

	def test_unknown_operation_is_rejected(self):
		normalized, errors = normalize_payload(
			{"operation": "rename", "source_colour": "Black", "reason": "x"}
		)
		self.assertTrue(any("Unknown operation" in error for error in errors))
		self.assertIn("split_convert", " ".join(errors))
		self.assertIn("remove", " ".join(errors))
		self.assertIn("add", " ".join(errors))

	def test_missing_operation_is_rejected(self):
		normalized, errors = normalize_payload({"source_colour": "Black", "reason": "x"})
		self.assertTrue(any("operation" in error for error in errors))

	def test_duplicate_target_colours_are_rejected(self):
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [
				{"colour": "Navy", "size_quantities": {"S": 5}},
				{"colour": "Navy", "size_quantities": {"S": 5}},
			],
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("Duplicate target colour" in error and "Navy" in error for error in errors))

	def test_all_zero_target_quantities_are_rejected(self):
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [
				{"colour": "Navy", "size_quantities": {"S": 0, "M": 0}, "packing_quantity": 0}
			],
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("Navy" in error and "positive quantity" in error for error in errors))

	def test_negative_quantities_are_rejected(self):
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [{"colour": "Navy", "size_quantities": {"S": -5}, "packing_quantity": 10}],
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("negative" in error and "S" in error for error in errors))

	def test_retained_source_target_is_exempt_from_positive_quantity_rule(self):
		# An all-zero source entry is allowed by shape validation; the
		# orchestration layer treats it as fully removed after allocation.
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [
				{"colour": "Black", "size_quantities": {"S": 0}, "packing_quantity": 0},
				{"colour": "Navy", "size_quantities": {"S": 10}},
			],
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertEqual(errors, [])

	def test_missing_or_blank_reason_is_allowed(self):
		for reason in (None, "", "   "):
			payload = {
				"operation": "remove",
				"source_colour": "Black",
				"targets": [],
			}
			if reason is not None:
				payload["reason"] = reason
			normalized, errors = normalize_payload(payload)
			self.assertEqual(errors, [], reason)
			self.assertEqual(normalized["reason"], "")

	def test_non_string_reason_is_rejected(self):
		payload = {"operation": "remove", "source_colour": "Black", "targets": [], "reason": 5}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("reason" in error for error in errors))

	def test_reason_is_stripped(self):
		payload = {
			"operation": "remove",
			"source_colour": "Black",
			"targets": [],
			"reason": "  Shade variation  ",
		}
		normalized, errors = normalize_payload(payload)
		self.assertEqual(errors, [])
		self.assertEqual(normalized["reason"], "Shade variation")

	def test_add_requires_exactly_one_target(self):
		for targets in (
			[],
			[
				{"colour": "Red", "size_quantities": {"S": 1}},
				{"colour": "Blue", "size_quantities": {"S": 1}},
			],
		):
			payload = {
				"operation": "add",
				"targets": targets,
				"reason": "x",
			}
			normalized, errors = normalize_payload(payload)
			self.assertTrue(any("exactly one target" in error for error in errors), targets)

	def test_add_rejects_source_colour(self):
		payload = {
			"operation": "add",
			"source_colour": "Black",
			"targets": [{"colour": "Red", "size_quantities": {"S": 1}}],
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("source_colour" in error for error in errors))

	def test_remove_rejects_targets(self):
		payload = {
			"operation": "remove",
			"source_colour": "Black",
			"targets": [{"colour": "Navy", "size_quantities": {"S": 1}}],
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("no targets" in error for error in errors))

	def test_split_requires_source_colour(self):
		payload = {
			"operation": "split_convert",
			"targets": [{"colour": "Navy", "size_quantities": {"S": 1}}],
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("source_colour" in error for error in errors))

	def test_remove_requires_source_colour(self):
		payload = {"operation": "remove", "targets": [], "reason": "x"}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("source_colour" in error for error in errors))

	def test_split_needs_a_target_differing_from_source(self):
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [{"colour": "Black", "size_quantities": {"S": 10}}],
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("different from the source" in error for error in errors))

	def test_split_with_empty_targets_is_rejected(self):
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [],
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("at least one target" in error for error in errors))

	def test_non_dict_payload_is_rejected(self):
		for payload in (None, "split", 5, []):
			normalized, errors = normalize_payload(payload)
			self.assertIsNone(normalized)
			self.assertTrue(errors)

	def test_structural_type_errors_are_reported_not_raised(self):
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [{"colour": "Navy", "size_quantities": ["S"], "packing_quantity": "many"}],
			"process_cost_values": "nope",
			"manual_packing_rows": {},
			"reference_colour": 7,
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("size_quantities" in error for error in errors))
		self.assertTrue(any("packing_quantity" in error for error in errors))
		self.assertTrue(any("process_cost_values" in error for error in errors))
		self.assertTrue(any("manual_packing_rows" in error for error in errors))
		self.assertTrue(any("reference_colour" in error for error in errors))
		# Quantities are still normalized where possible, errors are not thrown.
		self.assertEqual(normalized["targets"][0]["size_quantities"], {})
		self.assertEqual(normalized["targets"][0]["packing_quantity"], 0)

	def test_target_missing_colour_is_rejected(self):
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [{"size_quantities": {"S": 1}}],
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertTrue(any("colour" in error for error in errors))

	def test_unknown_target_keys_are_preserved(self):
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [{"colour": "Navy", "size_quantities": {"S": 1}, "future_field": {"a": 1}}],
			"reason": "x",
		}
		normalized, errors = normalize_payload(payload)
		self.assertEqual(errors, [])
		self.assertEqual(normalized["targets"][0]["future_field"], {"a": 1})

	def test_normalized_result_shares_no_mutable_state_with_payload(self):
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [{"colour": "Navy", "size_quantities": {"S": 1}, "cutting_rows": [{"Dia": 20}]}],
			"reason": "x",
		}
		snapshot = copy.deepcopy(payload)

		normalized, errors = normalize_payload(payload)

		normalized["targets"][0]["size_quantities"]["S"] = 999
		normalized["targets"][0]["cutting_rows"][0]["Dia"] = 999
		self.assertEqual(payload, snapshot)


class TestValidateSizeAllocations(unittest.TestCase):
	def test_exact_allocation_passes(self):
		targets = [
			{"colour": "Black", "size_quantities": {"S": 3, "M": 7}},
			{"colour": "Black 2", "size_quantities": {"S": 7, "M": 13}},
		]
		errors = validate_size_allocations({"S": 10, "M": 20}, targets)
		self.assertEqual(errors, [])

	def test_lower_allocation_passes(self):
		targets = [{"colour": "Black 2", "size_quantities": {"S": 9}}]
		errors = validate_size_allocations({"S": 10, "M": 20}, targets)
		self.assertEqual(errors, [])

	def test_higher_allocation_passes(self):
		targets = [
			{"colour": "Black", "size_quantities": {"S": 5, "M": 5}},
			{"colour": "Black 2", "size_quantities": {"S": 30, "M": 40}},
		]
		errors = validate_size_allocations({"S": 10, "M": 20}, targets)
		self.assertEqual(errors, [])

	def test_unknown_size_fails(self):
		targets = [{"colour": "Black 2", "size_quantities": {"S": 10, "XL": 5}}]
		errors = validate_size_allocations({"S": 10}, targets)
		self.assertTrue(any("XL" in error for error in errors))

	def test_fractional_quantities_pass(self):
		targets = [{"colour": "Black 2", "size_quantities": {"S": 0.333}}]
		errors = validate_size_allocations({"S": 0.333}, targets, precision=3)
		self.assertEqual(errors, [])


class TestTransformPackingAttributeRows(unittest.TestCase):
	def test_split_with_retained_source(self):
		rows = [{"attribute_value": "Black", "quantity": 0}, {"attribute_value": "Red", "quantity": 0}]
		result, diff = transform_packing_attribute_rows(
			rows, "Black", [{"colour": "Black"}, {"colour": "Black 2"}], "split_convert"
		)
		self.assertEqual(
			result,
			[
				{"attribute_value": "Black", "quantity": 0},
				{"attribute_value": "Red", "quantity": 0},
				{"attribute_value": "Black 2", "quantity": 0},
			],
		)
		self.assertTrue(any(entry["action"] == "cloned" for entry in diff))

	def test_conversion_removes_source(self):
		rows = [{"attribute_value": "Black", "quantity": 0}]
		result, _ = transform_packing_attribute_rows(
			rows, "Black", [{"colour": "Navy"}], "split_convert"
		)
		self.assertEqual(result, [{"attribute_value": "Navy", "quantity": 0}])

	def test_remove(self):
		rows = [{"attribute_value": "Black", "quantity": 0}, {"attribute_value": "Red", "quantity": 0}]
		result, _ = transform_packing_attribute_rows(rows, "Black", [], "remove")
		self.assertEqual(result, [{"attribute_value": "Red", "quantity": 0}])

	def test_add(self):
		rows = [{"attribute_value": "Red", "quantity": 5}]
		result, _ = transform_packing_attribute_rows(
			rows, None, [{"colour": "Navy", "packing_quantity": 5}], "add"
		)
		self.assertEqual(result[1], {"attribute_value": "Navy", "quantity": 5})

	def test_manual_rows_replace_generated_split(self):
		rows = [{"attribute_value": "Black", "quantity": 5}, {"attribute_value": "Red", "quantity": 5}]
		manual = [
			{"attribute_value": "Red", "quantity": 5},
			{"attribute_value": "Black 2", "quantity": 2},
			{"attribute_value": "Black 3", "quantity": 3},
		]
		result, _ = transform_packing_attribute_rows(
			rows, "Black", [{"colour": "Black 2"}, {"colour": "Black 3"}], "split_convert", manual_rows=manual
		)
		self.assertEqual(result, manual)


class TestTransformMajorColourRows(unittest.TestCase):
	def setUp(self):
		self.rows = [
			{"major_attribute_value": "Black", "attribute_value": "Black", "set_item_attribute_value": "Top", "index": 1},
			{"major_attribute_value": "Black", "attribute_value": "Grey", "set_item_attribute_value": "Bottom", "index": 1},
			{"major_attribute_value": "Red", "attribute_value": "Red", "set_item_attribute_value": "Top", "index": 2},
		]

	def test_split_clones_only_major_side_by_default(self):
		result, _ = transform_major_colour_rows(
			self.rows, "Black", [{"colour": "Black 2"}], "split_convert"
		)
		black_2 = [row for row in result if row["major_attribute_value"] == "Black 2"]
		self.assertEqual(len(black_2), 2)
		self.assertEqual(
			{row["set_item_attribute_value"]: row["attribute_value"] for row in black_2},
			{"Top": "Black", "Bottom": "Grey"},
		)
		self.assertNotIn(1, {row["index"] for row in black_2})
		self.assertFalse([row for row in result if row["major_attribute_value"] == "Black"])

	def test_split_with_stitch_side_following(self):
		result, _ = transform_major_colour_rows(
			self.rows, "Black", [{"colour": "Black 2"}], "split_convert", stitch_side_follows=True
		)
		black_2 = [row for row in result if row["major_attribute_value"] == "Black 2"]
		self.assertEqual({row["attribute_value"] for row in black_2}, {"Black 2"})

	def test_retained_source_keeps_original_rows(self):
		result, _ = transform_major_colour_rows(
			self.rows, "Black", [{"colour": "Black"}, {"colour": "Black 2"}], "split_convert"
		)
		self.assertEqual(len([row for row in result if row["major_attribute_value"] == "Black"]), 2)

	def test_remove(self):
		result, _ = transform_major_colour_rows(self.rows, "Black", [], "remove")
		self.assertEqual({row["major_attribute_value"] for row in result}, {"Red"})

	def test_add_uses_supplied_mapping(self):
		mapping = {"Top": "Navy", "Bottom": "Navy"}
		result, _ = transform_major_colour_rows(
			self.rows, None, [{"colour": "Navy"}], "add", mapping=mapping
		)
		navy = [row for row in result if row["major_attribute_value"] == "Navy"]
		self.assertEqual({row["set_item_attribute_value"] for row in navy}, {"Bottom", "Top"})
		self.assertEqual(len({row["index"] for row in navy}), 1)
		self.assertEqual([row["idx"] for row in result], list(range(1, len(result) + 1)))

	def test_split_reindexes_physical_rows_after_source_removal(self):
		rows = [
			{
				"idx": idx,
				"index": group,
				"major_attribute_value": colour,
				"attribute_value": colour,
				"set_item_attribute_value": part,
			}
			for idx, (group, colour, part) in enumerate(
				[
					(0, "Black", "Top"),
					(0, "Black", "Bottom"),
					(1, "Red", "Top"),
					(1, "Red", "Bottom"),
				],
				start=1,
			)
		]
		result, _ = transform_major_colour_rows(
			rows,
			"Black",
			[{"colour": "Navy"}, {"colour": "Grey"}],
			"split_convert",
			stitch_side_follows=True,
		)
		self.assertEqual([row["idx"] for row in result], list(range(1, len(result) + 1)))
		# Rows are contiguous by semantic group, matching fetch_combination_items'
		# groupby contract.
		self.assertEqual(
			[row["index"] for row in result],
			[1, 1, 2, 2, 3, 3],
		)


class TestTransformStitchingAccessoryStructure(unittest.TestCase):
	def make(self):
		return {
			"select_list": ["OE Fabric"],
			"attributes": ["Accessory", "Major Colour", "Accessory Colour", "Cloth"],
			"items": [
				{"accessory": "Folding", "major_colour": "Black", "accessory_colour": "Red", "cloth_type": "OE Fabric"},
				{"accessory": "Folding", "major_colour": "Navy", "accessory_colour": "Grey", "cloth_type": "Dyed"},
			],
			"is_set_item": 0,
		}

	def test_split_preserves_snake_case_keys_and_values(self):
		structure = self.make()
		result, diff = transform_stitching_accessory_structure(
			structure, "Colour", "Black", [{"colour": "Black 2"}], "split_convert"
		)
		black_2 = [row for row in result["items"] if row["major_colour"] == "Black 2"]
		self.assertEqual(len(black_2), 1)
		self.assertEqual(black_2[0]["accessory"], "Folding")
		self.assertEqual(black_2[0]["accessory_colour"], "Red")
		self.assertEqual(black_2[0]["cloth_type"], "OE Fabric")
		self.assertTrue(any(entry["action"] == "cloned" for entry in diff))
		self.assertFalse([row for row in result["items"] if row["major_colour"] == "Black"])

	def test_same_packing_attribute_makes_matching_accessory_colour_follow(self):
		structure = self.make()
		structure["items"][0]["accessory_colour"] = "Black"
		result, _ = transform_stitching_accessory_structure(
			structure,
			"Colour",
			"Black",
			[{"colour": "Black 2"}],
			"split_convert",
			accessory_colour_follows=True,
		)
		black_2 = next(row for row in result["items"] if row["major_colour"] == "Black 2")
		self.assertEqual(black_2["accessory_colour"], "Black 2")
		self.assertEqual(black_2["cloth_type"], "OE Fabric")

	def test_add_clones_reference_accessory_and_preserves_column_order(self):
		structure = self.make()
		structure["items"][0]["accessory_colour"] = "Black"
		result, _ = transform_stitching_accessory_structure(
			structure,
			"Colour",
			None,
			[{"colour": "Black 2"}],
			"add",
			accessory_colour_follows=True,
			reference_colour="Black",
		)
		added = next(row for row in result["items"] if row["major_colour"] == "Black 2")
		self.assertEqual(
			list(added),
			["accessory", "major_colour", "accessory_colour", "cloth_type"],
		)
		self.assertEqual(added["accessory_colour"], "Black 2")
		self.assertEqual(added["cloth_type"], "OE Fabric")

	def test_structure_without_major_colour_is_unchanged(self):
		structure = {"attributes": ["Accessory", "Cloth"], "items": [{"accessory": "X", "cloth_type": "Y"}]}
		result, diff = transform_stitching_accessory_structure(
			structure, "Colour", "Black", [{"colour": "B2"}], "split_convert"
		)
		self.assertEqual(result, structure)
		self.assertEqual(diff, [])


class TestTransformPanelConsumptionMatrix(unittest.TestCase):
	def make(self):
		return {
			"schema_version": 4,
			"attributes": {"primary": "Size", "panel": "Panel", "packing": "Colour"},
			"primary_values": ["S"],
			"packing_values": ["Black", "Red"],
			"panel_values": ["Front"],
			"panels": [
				{
					"group_id": "Front",
					"panel_value": "Front",
					"panel_values": ["Front"],
					"packing_values": ["Black", "Red"],
					"rows": [
						{
							"primary_value": "S",
							"values": {
								"Black": {"dia": "20 Dia", "weight": 0.03},
								"Red": {"dia": "18 Dia", "weight": 0.02},
							},
						}
					],
				}
			],
		}

	def test_split_copies_cell_exactly(self):
		matrix = self.make()
		result, diff = transform_panel_consumption_matrix(
			matrix, "Colour", "Black", [{"colour": "Black 2"}], "split_convert"
		)
		panel = result["panels"][0]
		cell = panel["rows"][0]["values"]["Black 2"]
		self.assertEqual(cell, {"dia": "20 Dia", "weight": 0.03})
		self.assertIn("Black 2", result["packing_values"])
		self.assertIn("Black 2", panel["packing_values"])
		self.assertNotIn("Black", panel["rows"][0]["values"])
		self.assertTrue(any(entry["action"] == "cloned" for entry in diff))

	def test_remove_deletes_column(self):
		result, _ = transform_panel_consumption_matrix(
			self.make(), "Colour", "Black", [], "remove"
		)
		self.assertNotIn("Black", result["packing_values"])
		self.assertNotIn("Black", result["panels"][0]["packing_values"])
		self.assertNotIn("Black", result["panels"][0]["rows"][0]["values"])

	def test_add_inserts_popup_cell(self):
		result, _ = transform_panel_consumption_matrix(
			self.make(), "Colour", None, [{"colour": "Navy"}], "add",
			new_cells=[{"panel": "Front", "row": {"primary_value": "S"}, "cell": {"dia": "30 Dia", "weight": 0.05}}],
		)
		self.assertEqual(result["panels"][0]["rows"][0]["values"]["Navy"], {"dia": "30 Dia", "weight": 0.05})

	def test_matrix_without_packing_attribute_unchanged(self):
		matrix = {"schema_version": 4, "attributes": {"primary": "Size", "panel": "Panel", "packing": "Shade"}, "panels": []}
		result, diff = transform_panel_consumption_matrix(
			matrix, "Colour", "Black", [{"colour": "B2"}], "split_convert"
		)
		self.assertEqual(result, matrix)
		self.assertEqual(diff, [])


class TestTransformPanelClothMatrix(unittest.TestCase):
	def make(self):
		return {
			"schema_version": 1,
			"attributes": ["Panel", "Colour"],
			"panel_attribute": "Panel",
			"packing_attribute": "Colour",
			"other_attributes": [],
			"cloth_options": ["OE Fabric"],
			"panels": [
				{
					"group_id": "Front",
					"panel_value": "Front",
					"panel_values": ["Front"],
					"packing_values": ["Black"],
					"rows": [{"attribute_values": {}, "values": {"Black": {"cloth": "OE Fabric"}}}],
				}
			],
		}

	def test_split_preserves_cloth(self):
		result, _ = transform_panel_cloth_matrix(
			self.make(), "Colour", "Black", [{"colour": "Black 2"}], "split_convert"
		)
		self.assertEqual(result["panels"][0]["rows"][0]["values"]["Black 2"], {"cloth": "OE Fabric"})

	def test_add_inserts_cloth(self):
		result, _ = transform_panel_cloth_matrix(
			self.make(), "Colour", None, [{"colour": "Navy"}], "add",
			new_cells=[{"panel": "Front", "row": {"attribute_values": {}}, "cell": {"cloth": "Dyed"}}],
		)
		self.assertEqual(result["panels"][0]["rows"][0]["values"]["Navy"], {"cloth": "Dyed"})


class TestTransformBomMappingValues(unittest.TestCase):
	def make_rows(self):
		return [
			{"index": 1, "attribute": "Colour", "attribute_value": "Black", "type": "item", "quantity": 1},
			{"index": 1, "attribute": "Cloth", "attribute_value": "OE Fabric", "type": "bom", "quantity": 0.2},
			{"index": 2, "attribute": "Colour", "attribute_value": "Red", "type": "item", "quantity": 1},
			{"index": 2, "attribute": "Cloth", "attribute_value": "Dyed", "type": "bom", "quantity": 0.3},
		]

	def test_split_clones_group_atomically_with_new_index(self):
		rows = self.make_rows()
		result, diff = transform_bom_mapping_values(
			rows, "Colour", "Black", [{"colour": "Black 2"}], "split_convert"
		)
		new_group = [row for row in result if row["attribute_value"] == "Black 2" and row["type"] == "item"]
		self.assertEqual(len(new_group), 1)
		index = new_group[0]["index"]
		self.assertGreater(index, 2)
		bom_side = [row for row in result if row["index"] == index and row["type"] == "bom"]
		self.assertEqual(
			[{key: row[key] for key in ("index", "attribute", "attribute_value", "type", "quantity")} for row in bom_side],
			[{"index": index, "attribute": "Cloth", "attribute_value": "OE Fabric", "type": "bom", "quantity": 0.2}],
		)
		self.assertEqual([row["idx"] for row in result], list(range(1, len(result) + 1)))
		self.assertFalse([row for row in result if row["attribute_value"] == "Black"])
		self.assertTrue(any(entry["action"] == "cloned" for entry in diff))

	def test_existing_compatible_target_group_merges(self):
		rows = self.make_rows() + [
			{"index": 3, "attribute": "Colour", "attribute_value": "Navy", "type": "item", "quantity": 1},
			{"index": 3, "attribute": "Cloth", "attribute_value": "OE Fabric", "type": "bom", "quantity": 0.2},
		]
		result, diff = transform_bom_mapping_values(
			rows, "Colour", "Black", [{"colour": "Navy"}], "split_convert"
		)
		# Source group is removed; the compatible Navy group already exists and
		# is kept as-is (merged), so no new rows are appended.
		self.assertEqual(len(result), 4)
		self.assertTrue(any(entry["action"] == "merged" for entry in diff))

	def test_existing_conflicting_target_group_reports_conflict(self):
		rows = self.make_rows() + [
			{"index": 3, "attribute": "Colour", "attribute_value": "Navy", "type": "item", "quantity": 1},
			{"index": 3, "attribute": "Cloth", "attribute_value": "Dyed", "type": "bom", "quantity": 0.9},
		]
		result, diff = transform_bom_mapping_values(
			rows, "Colour", "Black", [{"colour": "Navy"}], "split_convert"
		)
		self.assertEqual(len(result), 4)
		self.assertTrue(any(entry["action"] == "conflict" for entry in diff))

	def test_remove_deletes_whole_group(self):
		result, _ = transform_bom_mapping_values(self.make_rows(), "Colour", "Black", [], "remove")
		self.assertTrue(all(row["index"] != 1 for row in result))

	def test_add_clones_reference_groups(self):
		result, _ = transform_bom_mapping_values(
			self.make_rows(), "Colour", None, [{"colour": "Navy"}], "add", reference_colour="Red"
		)
		navy_item = [row for row in result if row["attribute_value"] == "Navy" and row["type"] == "item"]
		self.assertEqual(len(navy_item), 1)
		bom_side = [row for row in result if row["index"] == navy_item[0]["index"] and row["type"] == "bom"]
		self.assertEqual(bom_side[0]["attribute_value"], "Dyed")


class TestTransformProcessCostValues(unittest.TestCase):
	def test_split_clones_price_and_min_qty(self):
		rows = [
			{"attribute_value": "Black", "price": 12, "min_order_qty": 100},
			{"attribute_value": "Red", "price": 15, "min_order_qty": 50},
		]
		result, _ = transform_process_cost_values(rows, "Black", [{"colour": "Black 2"}], "split_convert")
		self.assertIn({"attribute_value": "Black 2", "price": 12, "min_order_qty": 100}, result)
		self.assertFalse([row for row in result if row["attribute_value"] == "Black"])

	def test_retained_source_stays(self):
		rows = [{"attribute_value": "Black", "price": 12, "min_order_qty": 100}]
		result, _ = transform_process_cost_values(rows, "Black", [{"colour": "Black"}, {"colour": "B2"}], "split_convert")
		self.assertTrue(any(row["attribute_value"] == "Black" for row in result))

	def test_split_reports_conflicting_existing_target_price(self):
		rows = [
			{"attribute_value": "Black", "price": 10, "min_order_qty": 5},
			{"attribute_value": "Navy", "price": 12, "min_order_qty": 5},
		]
		result, diff = transform_process_cost_values(
			rows, "Black", [{"colour": "Navy"}], "split_convert"
		)
		self.assertEqual(len(result), 1)
		conflict = next(entry for entry in diff if entry["action"] == "conflict")
		self.assertEqual(conflict["details"]["existing"]["price"], 12)
		self.assertEqual(conflict["details"]["new"]["price"], 10)

	def test_remove(self):
		rows = [{"attribute_value": "Black", "price": 12, "min_order_qty": 100}]
		result, _ = transform_process_cost_values(rows, "Black", [], "remove")
		self.assertEqual(result, [])

	def test_add_uses_popup_values(self):
		rows = [{"attribute_value": "Red", "price": 15, "min_order_qty": 50}]
		result, _ = transform_process_cost_values(
			rows, None, [{"colour": "Navy"}], "add",
			new_values=[{"attribute_value": "Navy", "price": 20, "min_order_qty": 10}],
		)
		self.assertIn({"attribute_value": "Navy", "price": 20, "min_order_qty": 10}, result)


if __name__ == "__main__":
	unittest.main()
