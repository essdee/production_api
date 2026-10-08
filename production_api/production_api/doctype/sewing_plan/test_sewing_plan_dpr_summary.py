from datetime import date
from unittest import TestCase
from unittest.mock import patch

import frappe

from production_api.production_api.doctype.sewing_plan import sewing_plan


class TestSewingPlanDPRSummary(TestCase):
	def _raise_validation(self, message, *args, **kwargs):
		raise frappe.ValidationError(message)

	def _call_dates(self, *args, **kwargs):
		method = getattr(sewing_plan, "get_sewing_plan_dpr_dates", None)
		if not callable(method):
			return None
		return method(*args, **kwargs)

	def _call_summary(self, *args, **kwargs):
		method = getattr(sewing_plan, "get_sewing_plan_dpr_summary", None)
		if not callable(method):
			return None
		return getattr(method, "__wrapped__", method)(*args, **kwargs)

	@patch.object(sewing_plan, "get_sewing_plan_dpr_data")
	@patch.object(
		sewing_plan,
		"get_sewing_plan_dpr_dates",
		create=True,
		return_value=[date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)],
	)
	def test_summary_returns_only_dates_with_dpr_data(self, get_dates, get_daily):
		daily_results = {
			date(2026, 10, 1): {
				"headers": ["Line Output"],
				"dpr_data": {"Line Output": {"LOT-001": {"details": {}}}},
				"pending_fi": [],
			},
			date(2026, 10, 2): {
				"headers": ["Line Output"],
				"dpr_data": {},
				"pending_fi": [
					{"lot": "LOT-002", "colour": "Navy", "part": "Top"}
				],
			},
			date(2026, 10, 3): {
				"headers": ["Line Output"],
				"dpr_data": {"Line Output": {"LOT-003": {"details": {}}}},
				"pending_fi": [],
			},
		}

		def get_daily_result(
			supplier,
			entry_date,
			work_station=None,
			input_type=None,
		):
			self.assertEqual(supplier, "WAREHOUSE-1")
			self.assertEqual(work_station, "LINE-1")
			self.assertEqual(input_type, "Line Output")
			return daily_results[entry_date]

		get_daily.side_effect = get_daily_result

		result = self._call_summary(
			"WAREHOUSE-1",
			"2026-10-01",
			"2026-10-03",
			work_station="LINE-1",
			input_type="Line Output",
		)

		self.assertEqual(
			result,
			{
				"reports": [
					{
						"date": "2026-10-01",
						"headers": ["Line Output"],
						"dpr_data": {"Line Output": {"LOT-001": {"details": {}}}},
					},
					{
						"date": "2026-10-03",
						"headers": ["Line Output"],
						"dpr_data": {"Line Output": {"LOT-003": {"details": {}}}},
					},
				],
				"pending_fi": [
					{"lot": "LOT-002", "colour": "Navy", "part": "Top"}
				],
			},
		)
		get_dates.assert_called_once_with(
			"WAREHOUSE-1",
			"2026-10-01",
			"2026-10-03",
			work_station="LINE-1",
			input_type="Line Output",
		)
		self.assertEqual(get_daily.call_count, 3)

	@patch.object(sewing_plan.frappe, "get_all")
	def test_summary_dates_are_filtered_deduplicated_and_sorted(self, get_all):
		def lookup(doctype, filters=None, pluck=None):
			if doctype == "Sewing Plan":
				self.assertEqual(filters, {"supplier": "WAREHOUSE-1"})
				self.assertEqual(pluck, "name")
				return ["SP-001", "SP-002"]
			if doctype == "Sewing Plan Entry Detail":
				self.assertEqual(
					filters,
					{
						"sewing_plan": ["in", ["SP-001", "SP-002"]],
						"entry_date": ["between", ["2026-10-01", "2026-10-05"]],
						"work_station": "LINE-1",
						"input_type": "Line Output",
					},
				)
				self.assertEqual(pluck, "entry_date")
				return [date(2026, 10, 3), date(2026, 10, 1), date(2026, 10, 3)]
			raise AssertionError(f"Unexpected doctype: {doctype}")

		get_all.side_effect = lookup

		result = self._call_dates(
			"WAREHOUSE-1",
			"2026-10-01",
			"2026-10-05",
			work_station="LINE-1",
			input_type="Line Output",
		)

		self.assertEqual(result, [date(2026, 10, 1), date(2026, 10, 3)])

	@patch.object(sewing_plan.frappe, "throw")
	@patch.object(sewing_plan, "get_sewing_plan_dpr_dates", return_value=[])
	def test_summary_requires_both_range_dates(self, get_dates, throw):
		throw.side_effect = self._raise_validation
		with self.assertRaisesRegex(frappe.ValidationError, "From Date and To Date"):
			self._call_summary("WAREHOUSE-1", None, "2026-10-03")

	@patch.object(sewing_plan.frappe, "throw")
	@patch.object(sewing_plan, "get_sewing_plan_dpr_dates", return_value=[])
	def test_summary_rejects_reversed_date_range(self, get_dates, throw):
		throw.side_effect = self._raise_validation
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be after"):
			self._call_summary("WAREHOUSE-1", "2026-10-04", "2026-10-03")
