from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.sd_yrp_sync import (
	prepare_sd_yrp_doc_for_publish,
	publish_sd_yrp_event,
)


class TestSDYRPSyncPrerequisites(FrappeTestCase):
	def test_lot_payload_preserves_all_business_fields(self):
		payload = prepare_sd_yrp_doc_for_publish(frappe._dict(
			doctype="Lot",
			name="TEST-LOT-CLOTH-EXCESS",
			cloth_excess_percentage=7.5,
			cloth_program_additions={
				"version": 1,
				"totals": [{"cloth_item": "CLOTH-1", "additional_weight": 20}],
			},
			lot_time_and_action_details=[{
				"colour": "Black",
				"master": "Master-00001",
				"time_and_action": "TNA-00001",
			}],
		))

		self.assertEqual(payload["cloth_excess_percentage"], 7.5)
		self.assertEqual(
			payload["cloth_program_additions"]["totals"][0]["additional_weight"],
			20,
		)
		self.assertEqual(
			payload["lot_time_and_action_details"][0]["time_and_action"],
			"TNA-00001",
		)

	def test_ipd_compacting_publishes_linked_ipd_before_itself(self):
		compacting = frappe._dict(
			doctype="IPD Compacting",
			name="TEST-IPD",
			item_production_detail="TEST-IPD",
			packing_attribute="Colour",
			compacting_details=[
				frappe._dict(
					cloth_item="TEST-CLOTH",
					packing_attribute_value="Black",
					input_dia="32 Dia",
					compacting_dia="30 Dia",
				)
			],
		)
		ipd = frappe._dict(
			doctype="Item Production Detail",
			name="TEST-IPD",
		)

		with patch.dict(frappe.local.conf, {"kafka": {"enabled": True}}), patch(
			"production_api.sd_yrp_sync.frappe.get_doc",
			return_value=ipd,
		), patch(
			"production_api.sd_yrp_sync.publish_ipd_prerequisites",
		) as publish_prerequisites, patch(
			"production_api.sd_yrp_sync._publish_ipd_prerequisite_names",
		) as publish_consumption_prerequisites, patch(
			"production_api.sd_yrp_sync.publish_doc_event",
		) as publish:
			publish_sd_yrp_event(compacting, "on_update")

		publish_prerequisites.assert_called_once_with(ipd)
		self.assertEqual(
			publish_consumption_prerequisites.call_args.args[0],
			{
				"Item Attribute": {"Colour"},
				"Item": {"TEST-CLOTH"},
				"Item Attribute Value": {"Black", "32 Dia", "30 Dia"},
			},
		)
		self.assertEqual(
			[call.kwargs["doctype"] for call in publish.call_args_list],
			["Item Production Detail", "IPD Compacting"],
		)

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
