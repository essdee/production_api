import base64
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.utils import download_work_in_progress_excel


class TestWorkInProgressReport(FrappeTestCase):
	def test_excel_export_returns_real_xlsx(self):
		result = download_work_in_progress_excel([
			["Style", "PPO", "Lot No", "Order Qty"],
			["TEST-STYLE", "PPO-TEST", "LOT-TEST", 10],
			["", "", "", 10],
		])

		self.assertTrue(result["filename"].endswith(".xlsx"))
		self.assertTrue(base64.b64decode(result["filecontent"]).startswith(b"PK"))

	def test_page_has_ppo_column_filter_and_excel_action(self):
		source = Path(
			frappe.get_app_path(
				"production_api",
				"public",
				"js",
				"components",
				"WorkInProgress.vue",
			)
		).read_text()

		self.assertIn("<th>PPO</th>", source)
		self.assertIn("columnFilters.production_order", source)
		self.assertIn("download_work_in_progress_excel", source)
