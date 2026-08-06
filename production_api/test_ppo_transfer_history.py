from unittest import TestCase

from frappe import _dict

from production_api.utils import _group_ppo_transfer_movements


class TestPPOTransferHistory(TestCase):
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
