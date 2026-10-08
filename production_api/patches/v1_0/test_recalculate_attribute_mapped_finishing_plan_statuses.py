from importlib import import_module
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

import frappe


PATCH_MODULE = (
	"production_api.patches.v1_0."
	"recalculate_attribute_mapped_finishing_plan_statuses"
)


class TestRecalculateAttributeMappedFinishingPlanStatuses(TestCase):
	def get_patch(self):
		try:
			return import_module(PATCH_MODULE)
		except ModuleNotFoundError:
			self.fail("Finishing Plan status recalculation patch is missing")

	def test_candidates_include_attribute_mapped_and_size_wise_plans_in_one_query(self):
		status_patch = self.get_patch()
		expected = [frappe._dict(name="FP-1", fp_status="Partially Dispatched")]

		with patch.object(status_patch.frappe.db, "sql", return_value=expected) as sql:
			actual = status_patch.get_candidate_plans()

		self.assertEqual(actual, expected)
		sql.assert_called_once()
		query = " ".join(sql.call_args.args[0].split())
		self.assertIn(
			"INNER JOIN `tabItem Production Detail` ipd "
			"ON ipd.name = fp.production_detail",
			query,
		)
		self.assertIn(
			"( COALESCE(ipd.based_on_other_attribute_mapping, 0) = 1 "
			"OR ipd.packing_mode = 'Size Wise Packing' )",
			query,
		)
		self.assertIn("fp.docstatus < 2", query)

	def test_execute_updates_only_changed_auto_managed_statuses(self):
		status_patch = self.get_patch()
		candidates = [
			frappe._dict(name="FP-CHANGE", fp_status="Partially Dispatched"),
			frappe._dict(name="FP-SAME", fp_status="Dispatched"),
			frappe._dict(name="FP-MANUAL", fp_status="Ready for Audit"),
		]
		documents = {
			"FP-CHANGE": MagicMock(name="FP-CHANGE"),
			"FP-SAME": MagicMock(name="FP-SAME"),
		}
		calculated = {
			"FP-CHANGE": "Dispatched",
			"FP-SAME": "Dispatched",
		}

		with (
			patch.object(status_patch, "get_candidate_plans", return_value=candidates),
			patch.object(
				status_patch.frappe,
				"get_doc",
				side_effect=lambda _doctype, name: documents[name],
			) as get_doc,
			patch.object(
				status_patch,
				"compute_received_status",
				side_effect=lambda doc: calculated[doc._mock_name],
			),
			patch.object(status_patch.frappe.db, "set_value") as set_value,
			patch("builtins.print"),
		):
			result = status_patch.execute()

		self.assertEqual(
			result,
			{"total": 3, "updated": 1, "unchanged": 1, "skipped": 1},
		)
		self.assertEqual(
			get_doc.call_args_list,
			[
				call("Finishing Plan", "FP-CHANGE"),
				call("Finishing Plan", "FP-SAME"),
			],
		)
		set_value.assert_called_once_with(
			"Finishing Plan",
			"FP-CHANGE",
			"fp_status",
			"Dispatched",
			update_modified=False,
		)

	def test_empty_calculation_resets_auto_managed_plan_to_planned(self):
		status_patch = self.get_patch()
		doc = MagicMock(name="FP-EMPTY")

		with (
			patch.object(
				status_patch,
				"get_candidate_plans",
				return_value=[
					frappe._dict(name="FP-EMPTY", fp_status="Partially Received")
				],
			),
			patch.object(status_patch.frappe, "get_doc", return_value=doc),
			patch.object(status_patch, "compute_received_status", return_value=None),
			patch.object(status_patch.frappe.db, "set_value") as set_value,
			patch("builtins.print"),
		):
			status_patch.execute()

		set_value.assert_called_once_with(
			"Finishing Plan",
			"FP-EMPTY",
			"fp_status",
			"Planned",
			update_modified=False,
		)
