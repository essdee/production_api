"""Sync linked Lot quantities from Lot Order Detail rows."""

import frappe


def execute():
	lot_names = frappe.get_all(
		"Lot",
		filters={
			"production_order": ["is", "set"],
			"production_detail": ["is", "set"],
		},
		pluck="name",
		order_by="name",
	)

	for lot_name in lot_names:
		lot = frappe.get_doc("Lot", lot_name)

		# Convert the piece quantities in Lot Order Detail into the packed
		# quantities stored in Lot.items, using the Lot controller's existing
		# packing-combo and size-wise calculation.
		lot.derive_items_from_order_details()

		# Saving the Lot persists the derived item quantities. The existing
		# before_save hook also replaces this Lot's Production Ordered Detail
		# rows on the linked Production Order with the derived quantities.
		lot.save(ignore_permissions=True)

	print(f"Synced quantities for {len(lot_names)} linked Lots")
