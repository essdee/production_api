import frappe

def execute():
    frappe.reload_doc("production_api", "doctype", "Purchase Order Item")

    # get all Purchase Order Item records
    po_items = get_all_po_items()
    print(f"Migrating {len(po_items)} Purchase Order Items")
    failed_items = []
    for po_item in po_items:
        try:
            po_item_doc = frappe.get_doc("Purchase Order Item", po_item.name)
            # Fetch the Item Variant's item
            item_name = frappe.get_value("Item Variant", po_item_doc.item_variant, "item")
            # Get the UOM and secondary UOM of the Item
            item_uom = frappe.get_value("Item", item_name, "default_unit_of_measure")
            item_secondary_uom = frappe.get_value("Item", item_name, "secondary_unit_of_measure")
            # Set the UOM and secondary UOM of the Purchase Order Item
            po_item_doc.uom = item_uom
            po_item_doc.secondary_uom = item_secondary_uom
            po_item_doc.save()
        except Exception as e:
            failed_items.append(po_item.name)
            print(f"Failed to migrate Purchase Order Item {po_item.name}: {e}")

def get_all_po_items():
    purchase_order_item = frappe.qb.DocType("Purchase Order Item")
    po_items = frappe.qb.from_(purchase_order_item).select(purchase_order_item.name).run(as_dict=True)
    return po_items
    