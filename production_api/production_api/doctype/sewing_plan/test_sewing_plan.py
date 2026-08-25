# Copyright (c) 2026, Essdee and Contributors
# See license.txt

from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.sewing_plan import sewing_plan


class FakeSewingPlan:
	def __init__(self):
		self.sewing_plan_order_details = [
			frappe._dict(item_variant="VARIANT-1"),
			frappe._dict(item_variant="VARIANT-2"),
		]
		self.consumption_details = []

	def set(self, fieldname, value):
		setattr(self, fieldname, value)

	def append(self, fieldname, value):
		getattr(self, fieldname).append(frappe._dict(value))


class FakeHRSettings:
	def __init__(
		self,
		site_url="https://hr.essdee.fit/",
		api_key="hr-key",
		api_secret="hr-secret",
		shifts=None,
	):
		self.values = {
			"hr_site_url": site_url,
			"hr_api_key": api_key,
			"hr_api_secret": api_secret,
			"hr_shifts": [
				frappe._dict(shift_type=shift_type)
				for shift_type in (shifts if shifts is not None else ["Shift A"])
			],
		}
		self.api_secret = api_secret

	def get(self, fieldname):
		return self.values.get(fieldname)

	def get_password(self, fieldname):
		if fieldname == "hr_api_secret":
			return self.api_secret
		return None


class TestSewingPlan(FrappeTestCase):
	def test_worker_strength_report_uses_hr_credentials_and_configured_shifts(self):
		settings = FakeHRSettings(shifts=["Shift A", " Shift B ", "Shift A"])
		report_response = MagicMock()
		report_response.json.return_value = {
			"message": {
				"columns": [
					{"fieldname": "department", "label": "Department", "fieldtype": "Data"},
					{"fieldname": "strength", "label": "Strength", "fieldtype": "Int"},
				],
				"result": [{"department": "Sewing", "strength": 12}],
				"add_total_row": 1,
			}
		}
		punch_response = MagicMock()
		punch_response.json.return_value = {
			"message": {
				"rows": [
					{
						"employee": "EMP-001",
						"employee_name": "Test Employee",
						"shift_type": "Shift A",
						"first_punch": "08:05:00",
					}
				]
			}
		}

		with (
			patch.object(sewing_plan.frappe, "get_single", return_value=settings),
			patch.object(
				sewing_plan.requests,
				"get",
				side_effect=[report_response, punch_response],
			) as mock_get,
		):
			result = sewing_plan.get_worker_strength_report(
				"2026-08-25", "08:00:00", "17:00:00"
			)

		report_response.raise_for_status.assert_called_once_with()
		punch_response.raise_for_status.assert_called_once_with()
		self.assertEqual(mock_get.call_count, 2)
		request = mock_get.call_args_list[0]
		self.assertEqual(
			request.args[0],
			"https://hr.essdee.fit/api/method/frappe.desk.query_report.run",
		)
		self.assertEqual(
			request.kwargs["headers"]["Authorization"], "token hr-key:hr-secret"
		)
		self.assertEqual(request.kwargs["timeout"], 30)
		self.assertEqual(
			request.kwargs["params"]["report_name"], "Workers Strength Report"
		)
		filters = frappe.parse_json(request.kwargs["params"]["filters"])
		self.assertEqual(filters["shift_type"], ["Shift A", "Shift B"])
		self.assertEqual(filters["report_date"], "2026-08-25")
		self.assertEqual(result["rows"], [{"department": "Sewing", "strength": 12}])
		self.assertEqual(result["employee_punches"][0]["first_punch"], "08:05:00")
		self.assertEqual(result["shifts"], ["Shift A", "Shift B"])
		self.assertEqual(result["add_total_row"], 1)
		punch_request = mock_get.call_args_list[1]
		self.assertTrue(
			punch_request.args[0].endswith("get_active_employee_first_punches")
		)
		self.assertEqual(
			frappe.parse_json(punch_request.kwargs["params"]["shift_type"]),
			["Shift A", "Shift B"],
		)

	def test_worker_strength_report_requires_hr_credentials(self):
		settings = FakeHRSettings(api_key="", api_secret="")
		with patch.object(sewing_plan.frappe, "get_single", return_value=settings):
			with self.assertRaisesRegex(frappe.ValidationError, "Configure the HR API"):
				sewing_plan.get_worker_strength_report(
					"2026-08-25", "08:00:00", "17:00:00"
				)

	def test_worker_strength_report_requires_hr_site_url(self):
		settings = FakeHRSettings(site_url="")
		with patch.object(sewing_plan.frappe, "get_single", return_value=settings):
			with self.assertRaisesRegex(frappe.ValidationError, "HR Site URL"):
				sewing_plan.get_worker_strength_report(
					"2026-08-25", "08:00:00", "17:00:00"
				)

	def test_worker_strength_report_requires_configured_shifts(self):
		settings = FakeHRSettings(shifts=[])
		with patch.object(sewing_plan.frappe, "get_single", return_value=settings):
			with self.assertRaisesRegex(frappe.ValidationError, "at least one Shift"):
				sewing_plan.get_worker_strength_report(
					"2026-08-25", "08:00:00", "17:00:00"
				)

	def test_worker_strength_report_rejects_invalid_hr_response(self):
		settings = FakeHRSettings()
		response = MagicMock()
		response.json.return_value = {"message": {"columns": []}}
		with (
			patch.object(sewing_plan.frappe, "get_single", return_value=settings),
			patch.object(sewing_plan.requests, "get", return_value=response),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "invalid Workers Strength"):
				sewing_plan.get_worker_strength_report(
					"2026-08-25", "08:00:00", "17:00:00"
				)

	def test_worker_strength_report_rejects_invalid_first_punch_response(self):
		settings = FakeHRSettings()
		report_response = MagicMock()
		report_response.json.return_value = {
			"message": {"columns": [], "result": [], "add_total_row": 0}
		}
		punch_response = MagicMock()
		punch_response.json.return_value = {"message": {"rows": None}}
		with (
			patch.object(sewing_plan.frappe, "get_single", return_value=settings),
			patch.object(
				sewing_plan.requests,
				"get",
				side_effect=[report_response, punch_response],
			),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "first punch"):
				sewing_plan.get_worker_strength_report(
					"2026-08-25", "08:00:00", "17:00:00"
				)

	def test_scr_aggregates_delivered_and_calculates_delivered_minus_input(self):
		scr_data = {}
		colours = []
		rows = [
			frappe._dict(
				item_variant="NAVY-S",
				set_combination={"major_colour": "Navy"},
				delivered_quantity=7,
			),
			frappe._dict(
				item_variant="NAVY-S",
				set_combination={"major_colour": "Navy"},
				delivered_quantity=3,
			),
		]

		with patch.object(
			sewing_plan,
			"get_colour_size_data",
			return_value=("S", None, "Navy", "Navy"),
		):
			sewing_plan._add_scr_delivered_quantities(
				scr_data,
				rows,
				False,
				"Colour",
				None,
				"Size",
				colours,
			)

		values = scr_data["Navy"]["values"]["S"]
		values["Input Qty"] = 6
		values["Delivered - Input"] = (
			values["Delivered Qty"] - values["Input Qty"]
		)
		self.assertEqual(values["Delivered Qty"], 10)
		self.assertEqual(values["Delivered - Input"], 4)
		self.assertEqual(colours, ["Navy"])

	def test_sewing_detail_ui_has_scr_and_input_date_range_controls(self):
		scr_source = Path(
			frappe.get_app_path(
				"production_api", "public", "js", "SewingPlan", "components", "SCRTab.vue"
			)
		).read_text()
		status_source = Path(
			frappe.get_app_path(
				"production_api", "public", "js", "SewingPlan", "components", "StatusSummaryTab.vue"
			)
		).read_text()

		self.assertIn("Delivered - Input", scr_source)
		self.assertIn("selected_from_date", status_source)
		self.assertIn("selected_to_date", status_source)
		self.assertIn("fieldname: 'status_summary_from_date'", status_source)
		self.assertIn("fieldname: 'status_summary_to_date'", status_source)
		self.assertIn("fieldtype: 'Date'", status_source)
		self.assertIn("normalizeInputDate(row['Input Date'])", status_source)

	def test_unmapped_bom_item_loads_saved_consumption_by_item(self):
		saved_row = frappe._dict(
			item_name="Jobwork-Mobilon Tape",
			index=0,
			consumption_qty=1,
		)
		sp_doc = frappe._dict(
			consumption_details=[saved_row],
			cloth_accessory_consumption=[],
		)
		ipd_doc = frappe._dict(
			accessory_clothtype_json=None,
			cloth_accessory_json=None,
		)
		ipd_row = frappe._dict(production_detail="IPD-1")
		bom_row = frappe._dict(
			item="Jobwork-Mobilon Tape",
			attribute_mapping=None,
			uom="Meter",
			qty_of_bom_item=1.2,
		)

		with (
			patch.object(
				sewing_plan,
				"Ipd_setting_att",
				return_value={"sti_process": "Stitching"},
			),
			patch.object(
				sewing_plan.frappe.db,
				"sql",
				side_effect=[[ipd_row], [bom_row]],
			),
			patch.object(sewing_plan.frappe, "get_all", return_value=["SP-1"]),
			patch.object(
				sewing_plan.frappe,
				"get_doc",
				side_effect=[sp_doc, ipd_doc],
			),
		):
			result = sewing_plan.get_consumption_mapping_data("LOT-1", "SUPPLIER-1")

		row = result["sections"][0]["rows"][0]
		self.assertEqual(row["quantity"], 1)
		self.assertEqual(row["item_bom_qty"], 1.2)

	def test_consumption_storage_matches_attributes_or_item_once(self):
		sp_doc = FakeSewingPlan()
		sections = [
			{
				"item": "Jobwork-Inner Elastic",
				"item_attributes": ["item_Part", "bom_Size"],
				"attribute_in_item": ["Part"],
				"rows": [
					{
						"index": 1,
						"values": {"item_Part": "Bottom", "bom_Size": "20 mm"},
						"item_bom_qty": 0.64,
						"quantity": 1,
					},
					{
						"index": 2,
						"values": {"item_Part": "Top", "bom_Size": "20 mm"},
						"item_bom_qty": 0.64,
						"quantity": 2,
					},
				],
			},
			{
				"item": "Jobwork-Mobilon Tape",
				"item_attributes": ["Item"],
				"attribute_in_item": [],
				"rows": [
					{
						"index": 0,
						"values": {"Item": "Jobwork-Mobilon Tape"},
						"item_bom_qty": 1.2,
						"quantity": 1,
					},
				],
			},
		]

		with patch.object(
			sewing_plan,
			"get_variant_attr_details",
			return_value={"Part": "Bottom"},
		):
			sewing_plan._set_consumption_details(sp_doc, sections)

		elastic_rows = [
			row
			for row in sp_doc.consumption_details
			if row.item_name == "Jobwork-Inner Elastic"
		]
		mobilon_rows = [
			row
			for row in sp_doc.consumption_details
			if row.item_name == "Jobwork-Mobilon Tape"
		]

		self.assertEqual(len(elastic_rows), 2)
		self.assertEqual(
			{(row.attribute, row.attribute_value) for row in elastic_rows},
			{("Part", "Bottom"), ("Size", "20 mm")},
		)
		self.assertEqual(len(mobilon_rows), 1)
		self.assertEqual(mobilon_rows[0].attribute, "Item")
		self.assertEqual(mobilon_rows[0].attribute_value, "Jobwork-Mobilon Tape")
		self.assertEqual(mobilon_rows[0].consumption_qty, 1)
