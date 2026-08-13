# Copyright (c) 2025, Essdee and Contributors
# See license.txt

from io import BytesIO
from unittest.mock import patch

import frappe
import openpyxl
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.grn_rework_item.grn_rework_item import (
	download_xl,
	get_rework_items,
)


class TestGRNReworkItem(FrappeTestCase):
	@patch(
		"production_api.production_api.doctype.grn_rework_item.grn_rework_item.get_variant_attr_details",
		return_value={"Size": "M", "Colour": "Blue"},
	)
	@patch("frappe.get_cached_value")
	@patch("frappe.get_doc")
	@patch("frappe.db.sql")
	def test_get_rework_items_filters_rows_by_received_type(
		self, mock_sql, mock_get_doc, mock_get_cached_value, _mock_attr_details
	):
		mock_sql.return_value = [{"name": "REWORK-0001"}]
		mock_get_cached_value.side_effect = [
			"IPD-0001",
			("Colour", "Size", 0, None),
		]
		mock_get_doc.return_value = frappe._dict({
			"grn_number": "GRN-0001",
			"creation": "2026-08-07 10:00:00.000000",
			"lot": "LOT-0001",
			"item": "Test Item",
			"grn_rework_item_details": [
				frappe._dict({
					"completed": 0,
					"received_type": "Accepted",
					"quantity": 10,
					"reworked": 0,
					"rejection": 0,
					"item_variant": "Test Item-Blue-M",
					"set_combination": "{}",
					"name": "ROW-0001",
					"uom": "Nos",
				}),
				frappe._dict({
					"completed": 0,
					"received_type": "Rejected",
					"quantity": 4,
					"reworked": 1,
					"rejection": 1,
					"item_variant": "Test Item-Blue-M",
					"set_combination": "{}",
					"name": "ROW-0002",
					"uom": "Nos",
				}),
			],
		})

		data = get_rework_items(
			lot=None,
			item=None,
			colour=None,
			received_type="Rejected",
		)

		self.assertEqual(data["types"], ["Rejected"])
		self.assertEqual(data["total_detail"], {"Rejected": 3})
		self.assertEqual(data["total_sum"], 3)
		self.assertEqual(data["report_detail"]["REWORK-0001"]["types"], {"Rejected": 3})
		self.assertNotIn("Accepted", data["report_detail"]["REWORK-0001"]["types"])
		query, params = mock_sql.call_args.args[:2]
		self.assertIn("t2.received_type = %(received_type)s", query)
		self.assertEqual(params["received_type"], "Rejected")

	def test_download_xl_contains_only_filtered_received_type_column(self):
		data = {
			"types": ["Rejected"],
			"report_detail": {
				"REWORK-0001": {
					"date": "2026-08-07 10:00:00.000000",
					"grn_number": "GRN-0001",
					"lot": "LOT-0001",
					"item": "Test Item",
					"rework_detail": {"Rejected-Blue": {"items": []}},
					"types": {"Rejected": 4},
					"rejection_detail": {"Rejected": 1},
				},
			},
		}

		download_xl(data)
		workbook = openpyxl.load_workbook(BytesIO(frappe.local.response.filecontent))
		rows = list(workbook.active.iter_rows(values_only=True))

		self.assertEqual(
			rows[0],
			("Series No", "Date", "GRN Number", "Lot", "Item", "Colour", "Rejected"),
		)
		self.assertEqual(rows[1][-1], 3)

	@patch("frappe.get_cached_value")
	@patch("frappe.get_doc")
	@patch("frappe.db.sql")
	def test_get_rework_items_omits_parent_when_every_child_is_filtered_out(
		self, mock_sql, mock_get_doc, mock_get_cached_value
	):
		mock_sql.return_value = [{"name": "REWORK-EMPTY"}]
		mock_get_cached_value.side_effect = [
			"IPD-0001",
			("Colour", "Size", 0, None),
		]
		mock_get_doc.return_value = frappe._dict({
			"grn_number": "GRN-EMPTY",
			"creation": "2026-08-13 10:00:00.000000",
			"lot": "LOT-0001",
			"item": "Test Item",
			"grn_rework_item_details": [
				frappe._dict({
					"completed": 1,
					"received_type": "Accepted",
					"quantity": 5,
					"reworked": 5,
					"rejection": 0,
					"item_variant": "Test Item-Blue-M",
					"set_combination": "{}",
					"name": "ROW-COMPLETED",
					"uom": "Nos",
				}),
			],
		})

		data = get_rework_items(lot=None, item=None, colour=None, show_reworked=0)

		self.assertEqual(data["report_detail"], {})
