import json
from pathlib import Path
from unittest import TestCase

from frappe import _dict

from production_api.utils import (
	_get_ppo_report_filters,
	_get_ppo_report_status,
	_group_ppo_transfer_movements,
)


class TestPPOTransferHistory(TestCase):
	def test_ppo_report_filters_by_production_order_status(self):
		self.assertEqual(
			_get_ppo_report_filters("Close Request"),
			{"docstatus": ["!=", 2], "status": "Close Request"},
		)
		self.assertEqual(_get_ppo_report_filters(), {"docstatus": ["!=", 2]})

	def test_ppo_report_returns_stored_production_order_status(self):
		order = _dict(docstatus=1, status="Item Changed")

		self.assertEqual(_get_ppo_report_status(order), "Item Changed")

	def test_ppo_report_filter_offers_all_production_order_statuses(self):
		package_path = Path(__file__).resolve().parent
		meta = json.loads(
			(package_path / "production_api/doctype/production_order/production_order.json").read_text()
		)
		status_options = next(
			field["options"].splitlines()
			for field in meta["fields"]
			if field.get("fieldname") == "status"
		)
		component = (
			package_path / "public/js/PPOReport/components/PPOReport.vue"
		).read_text()

		for status in filter(None, status_options):
			with self.subTest(status=status):
				self.assertIn(f'"{status}"', component)
		self.assertNotIn('options: "\\nDraft\\nSubmitted"', component)

	def test_groups_source_rows_as_negative_reduction(self):
		rows = [
			_dict(
				name="ROW-1",
				transfer_reference="TRANSFER-1",
				movement="Reduced",
				counterpart_production_order="PPO-TARGET",
				size="S",
				quantity=5,
				approved_on="2026-07-24 12:30:00",
				approved_by="approver@example.com",
				requested_by="requester@example.com",
				reason="Move to alternative",
			),
			_dict(
				name="ROW-2",
				transfer_reference="TRANSFER-1",
				movement="Reduced",
				counterpart_production_order="PPO-TARGET",
				size="M",
				quantity=7,
				approved_on="2026-07-24 12:30:00",
				approved_by="approver@example.com",
				requested_by="requester@example.com",
				reason="Move to alternative",
			),
		]

		movement = _group_ppo_transfer_movements(rows)[0]

		self.assertEqual(movement["movement"], "Reduced")
		self.assertEqual(movement["quantity"], 12)
		self.assertEqual(movement["signed_quantity"], -12)
		self.assertEqual(movement["signed_sizes"], {"S": -5, "M": -7})
		self.assertEqual(movement["summary"], "Reduced 12 to PPO-TARGET")

	def test_groups_destination_rows_as_positive_addition(self):
		rows = [
			_dict(
				name="ROW-1",
				transfer_reference="TRANSFER-1",
				movement="Added",
				counterpart_production_order="PPO-SOURCE",
				size="S",
				quantity=5,
				approved_on="2026-07-24 12:30:00",
				approved_by="approver@example.com",
				requested_by="requester@example.com",
				reason="Move to alternative",
			),
		]

		movement = _group_ppo_transfer_movements(rows)[0]

		self.assertEqual(movement["signed_quantity"], 5)
		self.assertEqual(movement["signed_sizes"], {"S": 5})
		self.assertEqual(movement["detail_summary"], "Added 5 from PPO-SOURCE (S: 5)")
