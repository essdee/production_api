from unittest import TestCase

from frappe import _dict

from production_api.utils import (
	get_bundles_by_cutter,
	group_laysheet_stats_by_parent,
)


class TestDailyProductionReport(TestCase):
	def test_same_plan_keeps_laysheets_with_null_and_empty_cutting_order(self):
		laysheets = [
			_dict(
				name="CLS-SUKUMAR",
				cutting_plan="CP-A",
				cutting_order=None,
				cutter="Sukumar",
				status="Label Printed",
				posting_date="2026-09-14",
			),
			_dict(
				name="CLS-PANDIAN",
				cutting_plan="CP-A",
				cutting_order="",
				cutter="Pandian",
				status="Bundles Generated",
				posting_date="2026-09-14",
			),
		]

		stats_by_parent = group_laysheet_stats_by_parent(
			laysheets,
			"2026-09-14",
		)

		self.assertEqual(list(stats_by_parent), [("Cutting Plan", "CP-A")])
		stats = stats_by_parent[("Cutting Plan", "CP-A")]
		self.assertEqual(stats["names"], ["CLS-SUKUMAR", "CLS-PANDIAN"])
		self.assertEqual(stats["bundle_count"], 2)
		self.assertEqual(stats["label_count"], 1)
		self.assertEqual(stats["created_count"], 2)

		bundles_by_cutter = get_bundles_by_cutter(
			[{"name": name} for name in stats["names"]],
			{
				"CLS-SUKUMAR": [_dict(cutter="Sukumar", colour="Maroon")],
				"CLS-PANDIAN": [_dict(cutter="Pandian", colour="Navy")],
			},
		)

		self.assertEqual(set(bundles_by_cutter), {"Sukumar", "Pandian"})
		self.assertEqual(
			list(bundles_by_cutter["Sukumar"]),
			["CLS-SUKUMAR"],
		)
		self.assertEqual(
			list(bundles_by_cutter["Pandian"]),
			["CLS-PANDIAN"],
		)
