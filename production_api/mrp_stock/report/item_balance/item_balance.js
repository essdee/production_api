// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Item Balance"] = {
	"filters": [
		{
			"fieldname": "item_variant",
			"label": __("Item Variant"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item Variant",
		},
		{
			"fieldname": "item",
			"label": __("Item"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item",
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Supplier",
		},
		{
			"fieldname": "lot",
			"label": __("Lot"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Lot",
		},
		{
			"fieldname":"received_type",
			"fieldtype":"Link",
			"label":"Received Type",
			"options":"GRN Item Type",
			"width":80,
		},
		{
			"fieldname": 'remove_zero_balance_item',
			"label": __('Remove Zero Balance Item'),
			"fieldtype": 'Check',
			"default": 1
		},
	]
};
