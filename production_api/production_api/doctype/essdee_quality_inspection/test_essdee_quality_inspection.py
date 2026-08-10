# Copyright (c) 2025, Essdee and Contributors
# See license.txt

from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.essdee_quality_inspection import (
	essdee_quality_inspection,
)


class TestEssdeeQualityInspection(FrappeTestCase):
	def test_debit_details_tab_and_inspection_link_metadata(self):
		inspection_meta = frappe.get_file_json(
			frappe.get_app_path(
				"production_api",
				"production_api",
				"doctype",
				"essdee_quality_inspection",
				"essdee_quality_inspection.json",
			)
		)
		inspection_fields = {
			field["fieldname"]: field for field in inspection_meta["fields"]
		}
		self.assertEqual(
			inspection_fields["debit_details_tab"]["fieldtype"],
			"Tab Break",
		)
		self.assertEqual(
			inspection_fields["debit_details_html"]["fieldtype"],
			"HTML",
		)
		self.assertFalse(inspection_fields["debit_details_tab"].get("hidden"))
		self.assertFalse(inspection_fields["debit_details_html"].get("hidden"))

		debit_meta = frappe.get_file_json(
			frappe.get_app_path(
				"production_api",
				"production_api",
				"doctype",
				"essdee_debit",
				"essdee_debit.json",
			)
		)
		quality_inspection = next(
			field
			for field in debit_meta["fields"]
			if field.get("fieldname") == "quality_inspection"
		)
		self.assertEqual(quality_inspection["fieldtype"], "Link")
		self.assertEqual(quality_inspection["options"], "Essdee Quality Inspection")

	@patch.object(essdee_quality_inspection.frappe, "get_all")
	def test_debit_details_are_scoped_to_exact_inspection(self, get_all):
		get_all.return_value = [{"name": "ED-00001"}]

		result = essdee_quality_inspection.get_debit_details("EQI-00001")

		self.assertEqual(result, [{"name": "ED-00001"}])
		filters = get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["quality_inspection"], "EQI-00001")
		self.assertEqual(filters["docstatus"], ["!=", 2])

	def test_client_links_created_debit_and_hides_empty_tab(self):
		source = Path(
			frappe.get_app_path(
				"production_api",
				"production_api",
				"doctype",
				"essdee_quality_inspection",
				"essdee_quality_inspection.js",
			)
		).read_text()

		self.assertIn("quality_inspection: frm.doc.name", source)
		self.assertIn('render_debit_details(frm);', source)
		self.assertIn(
			'frm.toggle_display(["debit_details_tab", "debit_details_html"], has_debits);',
			source,
		)
		self.assertIn("debit_tab.toggle(has_debits);", source)
		self.assertIn("frm.reload_doc();", source)
