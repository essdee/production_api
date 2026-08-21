# Copyright (c) 2023, Essdee and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.mrp_stock.doctype.lot_transfer.lot_transfer import (
	get_lot_transfer_delivery_items,
	get_lot_transfer_items_for_target_lot,
)


class TestLotTransfer(FrappeTestCase):
	def test_bulk_transfer_items_can_be_filtered_for_one_target_lot(self):
		items = [
			frappe._dict(item="FABRIC-RED", qty=5, to_lot="LOT-ONE"),
			frappe._dict(item="FABRIC-BLUE", qty=7, to_lot="LOT-TWO"),
		]

		filtered = get_lot_transfer_items_for_target_lot(items, "LOT-TWO")

		self.assertEqual(len(filtered), 1)
		self.assertEqual(filtered[0].item, "FABRIC-BLUE")

	def test_cutting_plan_flag_allows_direct_items_on_new_transfer(self):
		doc = frappe.new_doc("Lot Transfer")
		doc.append("items", {"item": "FABRIC-RED", "qty": 5})
		doc.flags.allow_from_cutting_plan = True

		doc.before_validate()

		self.assertEqual(len(doc.items), 1)

	def test_new_transfer_rejects_direct_items_without_creation_flag(self):
		doc = frappe.new_doc("Lot Transfer")
		doc.append("items", {"item": "FABRIC-RED", "qty": 5})

		with self.assertRaisesRegex(frappe.ValidationError, "Add items"):
			doc.before_validate()

	def test_make_dc_allocates_transferred_quantity_to_work_order_deliverables(self):
		transfer_items = [
			frappe._dict(item="FABRIC-RED", qty=7.5, uom="Kg"),
		]
		work_order_items = [
			frappe._dict(
				item_variant="FABRIC-RED",
				uom="Kg",
				pending_quantity=5,
				lot="LOT-NEW",
				comments="Do not copy this comment",
			),
			frappe._dict(
				item_variant="FABRIC-RED",
				uom="Kg",
				pending_quantity=4,
				lot="LOT-NEW",
			),
			frappe._dict(
				item_variant="RIB-RED",
				uom="Kg",
				pending_quantity=2,
				lot="LOT-NEW",
			),
		]

		items = get_lot_transfer_delivery_items(
			transfer_items, work_order_items, "LOT-NEW"
		)

		self.assertEqual([item.delivered_quantity for item in items], [5, 2.5, 0])
		self.assertEqual([item.qty for item in items], [5, 4, 2])
		self.assertTrue(all(item.lot == "LOT-NEW" for item in items))
		self.assertTrue(all(item.comments is None for item in items))

	def test_make_dc_allows_quantity_above_work_order_pending_quantity(self):
		transfer_items = [
			frappe._dict(
				item="FABRIC-RED",
				qty=8,
				uom="Kg",
				rate=120,
				set_combination={},
			),
		]
		work_order_items = [
			frappe._dict(
				item_variant="FABRIC-RED",
				uom="Kg",
				pending_quantity=5,
				lot="LOT-NEW",
				table_index=1,
				row_index="1",
			),
		]

		items = get_lot_transfer_delivery_items(
			transfer_items, work_order_items, "LOT-NEW"
		)

		self.assertEqual(len(items), 1)
		self.assertEqual(items[0].qty, 8)
		self.assertEqual(items[0].delivered_quantity, 8)

	def test_make_dc_allows_excess_when_pending_quantity_is_negative(self):
		transfer_items = [
			frappe._dict(
				item="FABRIC-RED",
				qty=4.5,
				uom="Kg",
			),
		]
		work_order_items = [
			frappe._dict(
				item_variant="FABRIC-RED",
				uom="Kg",
				pending_quantity=-2,
				lot="LOT-NEW",
			),
		]

		items = get_lot_transfer_delivery_items(
			transfer_items, work_order_items, "LOT-NEW"
		)

		self.assertEqual(len(items), 1)
		self.assertEqual(items[0].qty, 4.5)
		self.assertEqual(items[0].delivered_quantity, 4.5)

	def test_make_dc_rejects_items_not_in_work_order_deliverables(self):
		transfer_items = [
			frappe._dict(item="RIB-BLACK", qty=72.2, uom="Kg"),
		]
		work_order_items = [
			frappe._dict(
				item_variant="PLANNED-FABRIC",
				uom="Kg",
				pending_quantity=10,
				lot="LOT-NEW",
			),
		]

		with self.assertRaisesRegex(
			frappe.ValidationError,
			"not in the selected Work Order deliverables: RIB-BLACK",
		):
			get_lot_transfer_delivery_items(
				transfer_items, work_order_items, "LOT-NEW"
			)
