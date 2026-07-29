# Copyright (c) 2021, Essdee and Contributors
# See license.txt

import unittest
from unittest.mock import patch

import frappe

from production_api.production_api.doctype.item.item import (
	validate_cloth_yarn_ratio,
)

class TestItem(unittest.TestCase):
	def _cloth(self, rows):
		return frappe._dict(
			name="_Test Cloth",
			is_cloth_item=1,
			yarn_ratio_details=[
				frappe._dict(idx=index, **row)
				for index, row in enumerate(rows, 1)
			],
		)

	@patch.object(frappe.db, "exists", return_value=False)
	@patch.object(frappe.db, "get_value", return_value=0)
	def test_cloth_yarn_ratio_accepts_exactly_100(self, _get_value, _exists):
		validate_cloth_yarn_ratio(
			self._cloth([
				{"yarn_item": "YARN-A", "ratio": 60},
				{"yarn_item": "YARN-B", "ratio": 40},
			])
		)

	@patch.object(frappe.db, "exists", return_value=False)
	@patch.object(frappe.db, "get_value", return_value=0)
	def test_cloth_yarn_ratio_rejects_wrong_total(self, _get_value, _exists):
		with self.assertRaisesRegex(frappe.ValidationError, "Current total is 90"):
			validate_cloth_yarn_ratio(
				self._cloth([
					{"yarn_item": "YARN-A", "ratio": 60},
					{"yarn_item": "YARN-B", "ratio": 30},
				])
			)

	@patch.object(frappe.db, "exists", return_value=False)
	@patch.object(frappe.db, "get_value", return_value=0)
	def test_cloth_yarn_ratio_rejects_duplicate_yarn(self, _get_value, _exists):
		with self.assertRaisesRegex(frappe.ValidationError, "duplicated"):
			validate_cloth_yarn_ratio(
				self._cloth([
					{"yarn_item": "YARN-A", "ratio": 50},
					{"yarn_item": "YARN-A", "ratio": 50},
				])
			)
