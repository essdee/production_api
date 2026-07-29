from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.sd_yrp_sync import publish_sd_yrp_event


class TestSDYRPSyncPrerequisites(FrappeTestCase):
	def test_lot_publishes_its_production_order_first_once_per_request(self):
		lot = frappe._dict(
			doctype="Lot",
			name="TEST-LOT",
			production_order="TEST-PPO",
		)
		production_order = frappe._dict(
			doctype="Production Order",
			name="TEST-PPO",
		)
		if hasattr(frappe.local, "_sd_yrp_published_lot_prerequisites"):
			delattr(frappe.local, "_sd_yrp_published_lot_prerequisites")

		try:
			with patch.dict(frappe.local.conf, {"kafka": {"enabled": True}}), patch(
				"production_api.sd_yrp_sync.frappe.get_doc",
				return_value=production_order,
			), patch(
				"production_api.sd_yrp_sync.publish_doc_event",
			) as publish:
				publish_sd_yrp_event(lot, "on_update")
				publish_sd_yrp_event(lot, "on_update")

			self.assertEqual(
				[call.kwargs["doctype"] for call in publish.call_args_list],
				["Production Order", "Lot", "Lot"],
			)
			self.assertEqual(publish.call_args_list[0].kwargs["event"], "on_update")
			self.assertEqual(publish.call_args_list[0].kwargs["doc"]["name"], "TEST-PPO")
		finally:
			if hasattr(frappe.local, "_sd_yrp_published_lot_prerequisites"):
				delattr(frappe.local, "_sd_yrp_published_lot_prerequisites")
