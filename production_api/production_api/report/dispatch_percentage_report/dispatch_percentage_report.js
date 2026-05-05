// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Dispatch Percentage Report"] = {
	"filters": [
		{
			"fieldname": "percentage",
			"fieldtype": "Percent",
			"label": __("Percentage"),
			"default": 75,
			"reqd": 1,
		},
		{
			"fieldname": "lot",
			"fieldtype": "MultiSelectList",
			"label": __("Lot"),
			"options": "Lot",
			get_data(txt) {
				return frappe.db.get_link_options("Lot", txt);
			},
		},
		{
			"fieldname": "item",
			"fieldtype": "MultiSelectList",
			"label": __("Item"),
			"options": "Item",
			get_data(txt) {
				return frappe.db.get_link_options("Item", txt);
			},
		},
	],

	onload(report) {
		report.page.add_inner_button(__("Paste Filters"), () => {
			show_dispatch_percentage_paste_dialog(report);
		});
	},
};

function show_dispatch_percentage_paste_dialog(report) {
	const dialog = new frappe.ui.Dialog({
		title: __("Paste Filters"),
		fields: [
			{
				"fieldname": "filter_type",
				"fieldtype": "Select",
				"label": __("Apply To"),
				"options": "Lot\nItem",
				"default": "Lot",
				"reqd": 1,
			},
			{
				"fieldname": "values",
				"fieldtype": "Small Text",
				"label": __("Values"),
				"reqd": 1,
			},
		],
		primary_action_label: __("Apply"),
		primary_action(values) {
			const filtername = values.filter_type === "Item" ? "item" : "lot";
			const pasted_values = parse_pasted_values(values.values);

			if (!pasted_values.length) {
				frappe.msgprint(__("Please enter at least one value."));
				return;
			}

			const current_values = normalize_filter_values(report.get_filter_value(filtername));
			report.set_filter_value(filtername, Array.from(new Set(current_values.concat(pasted_values))));
			dialog.hide();
			report.refresh();
		},
	});

	dialog.show();
}

function parse_pasted_values(value) {
	return (value || "")
		.split(/[\n,]/)
		.map((row) => row.trim())
		.filter(Boolean);
}

function normalize_filter_values(value) {
	if (!value) {
		return [];
	}

	if (Array.isArray(value)) {
		return value;
	}

	return [value];
}
