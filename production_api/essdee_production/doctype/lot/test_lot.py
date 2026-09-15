# Copyright (c) 2024, Essdee and Contributors
# See license.txt

import json
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase


class TestLot(FrappeTestCase):
	def test_lot_order_vue_container_is_visible(self):
		doctype_path = Path(
			frappe.get_app_path(
				"production_api",
				"essdee_production",
				"doctype",
				"lot",
				"lot.json",
			)
		)
		fields = {
			field["fieldname"]: field
			for field in json.loads(doctype_path.read_text())["fields"]
		}
		self.assertFalse(fields["column_break_njmh"].get("hidden", 0))
		self.assertFalse(fields["items_html"].get("hidden", 0))

		form_source = doctype_path.with_name("lot.js").read_text()
		self.assertIn(
			"new frappe.production.ui.LotOrder(frm.fields_dict['items_html'].wrapper)",
			form_source,
		)
