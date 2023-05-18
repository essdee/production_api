// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Purchase Order Itemwise"] = {
	"filters": [
		{
			"fieldname": "item",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname": "supplier",
			"label": __("Supplier"),
			"fieldtype": "Link",
			"options": "Supplier"
		},
		{
			"fieldname": "purchase_order",
			"label": __("Purchase Order"),
			"fieldtype": "Link",
			"options": "Purchase Order"
		},
		{
			"fieldname": "delivery_location",
			"label": __("Delivery Location"),
			"fieldtype": "Link",
			"options": "Supplier"
		},
		{
			"fieldname": "lot",
			"label": __("Lot"),
			"fieldtype": "Link",
			"options": "Lot"
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "\nDraft\nOrdered\nCancelled\nDelivered\nPartially Delivered\nPartially Cancelled"
		},
		{
			"fieldname": "open_status",
			"label": __("Open Status"),
			"fieldtype": "Select",
			"options": "\nOpen\nClosed",
			"default": "Open"
		},
		{
			"fieldname": "docstatus",
			"label": __("Docstatus"),
			"fieldtype": "Select",
			"options": "\n0\n1\n2",
		},
		{
			"fieldname": "date_based_on",
			"label": __("Date Filter Based On"),
			"fieldtype": "Select",
			"options": "\nPosting Date\nDelivery Date",
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"depends_on": "eval:doc.date_based_on"
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"depends_on": "eval:doc.date_based_on"
		},
	],
	formatter: function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "pending_qty") {
			if (data.pending_qty > 0 && data.delivery_date > frappe.datetime.nowdate()) {
				value = "<span style='color:green'>" + value + "</span>";
			} else if (data.pending_qty > 0 && data.delivery_date == frappe.datetime.nowdate()) {
				value = "<span style='color:blue'>" + value + "</span>";
			} else if (data.pending_qty > 0 && data.delivery_date < frappe.datetime.nowdate()) {
				value = "<span style='color:red'>" + value + "</span>";
			} else if (data.pending_qty < 0) {
				value = "<span style='color:orange'>" + value + "</span>";
			}
		} else if (column.fieldname == "status") {
			const status_colors = {
				"Draft": "orange",
				"Ordered": "blue",
				"Partially Delivered": "yellow",
				"Delivered": "green",
				"Overdue": "red",
				"Cancelled": "darkgrey",
				"Partially Cancelled": "grey",
			};
			if (status_colors[data.status]) {
				value = `<span class='indicator-pill ${status_colors[data.status]}'>${__(data.status)}</span>`;
			}
		} else if (column.fieldname == "supplier_name") {
			value = `<a href="/app/supplier/${data.supplier}" data-doctype="Supplier" data-name="${data.supplier}" data-value="${data.supplier}">${data.supplier_name}</a>`;
		} else if (column.fieldname == "delivery_location_name") {
			value = `<a href="/app/supplier/${data.delivery_location}" data-doctype="Supplier" data-name="${data.delivery_location}" data-value="${data.delivery_location}">${data.delivery_location_name}</a>`;
		}

		return value;
	}
};
