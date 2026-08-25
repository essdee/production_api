# Copyright (c) 2023, Essdee and Contributors
# See license.txt

import json
import unittest
from pathlib import Path


class TestMRPSettings(unittest.TestCase):
	def test_hr_details_fields_and_shift_child_table(self):
		settings_meta = json.loads(
			Path(__file__).with_name("mrp_settings.json").read_text()
		)
		settings_fields = {
			field["fieldname"]: field for field in settings_meta["fields"]
		}
		self.assertEqual(settings_fields["hr_details_section"]["label"], "HR Details")
		self.assertEqual(settings_fields["hr_site_url"]["fieldtype"], "Data")
		self.assertEqual(
			settings_fields["hr_site_url"]["default"], "https://hr.essdee.fit"
		)
		self.assertEqual(settings_fields["hr_api_key"]["fieldtype"], "Data")
		self.assertEqual(settings_fields["hr_api_secret"]["fieldtype"], "Password")
		self.assertEqual(settings_fields["hr_shifts"]["fieldtype"], "Table")
		self.assertEqual(settings_fields["hr_shifts"]["options"], "MRP HR Shift")

		shift_meta_path = (
			Path(__file__).parents[1]
			/ "mrp_hr_shift"
			/ "mrp_hr_shift.json"
		)
		shift_meta = json.loads(shift_meta_path.read_text())
		self.assertEqual(shift_meta["istable"], 1)
		self.assertEqual(len(shift_meta["fields"]), 1)
		self.assertEqual(shift_meta["fields"][0]["fieldname"], "shift_type")
		self.assertEqual(shift_meta["fields"][0]["fieldtype"], "Data")
		self.assertEqual(shift_meta["fields"][0]["reqd"], 1)
