import frappe

def execute():
	ipd_doc=frappe.get_all("Item Production Detail",pluck="name")
	for i in ipd_doc:
		ipd_n=frappe.get_doc("Item Production Detail", i)
		for x in ipd_n.item_bom:
			if not x.based_on_attribute_mapping:
				continue
			bom_map=frappe.get_doc("Item BOM Attribute Mapping", x.attribute_mapping)
			if bom_map.bom_item_attributes:
				continue
			for r in bom_map.values:
				if r.quantity == 0:
					r.quantity = x.qty_of_bom_item
			bom_map.save(ignore_permissions=True)


