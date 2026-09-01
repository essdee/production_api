// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Stock Balance"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
		// {
		// 	"fieldname": "item_group",
		// 	"label": __("Item Group"),
		// 	"fieldtype": "Link",
		// 	"width": "80",
		// 	"options": "Item Group"
		// },
		{
			"fieldname": "item",
			"label": __("Item Variant"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item Variant",
		},
		{
			"fieldname": "parent_item",
			"label": __("Item"),
			"fieldtype": "MultiSelectList",
			"width": "80",
			"options": "Item",
			get_data(txt) {
				return frappe.db.get_link_options("Item", txt);
			},
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
			"fieldtype": "MultiSelectList",
			"width": "80",
			"options": "Lot",
			get_data(txt) {
				return frappe.db.get_link_options("Lot", txt);
			},
		},
		{
			"fieldname":"received_type",
			"label":"Received Type",
			"fieldtype":"Link",
			"options":"GRN Item Type",
			"width":"80",
		},
		{
			"fieldname": "show_variant_attributes",
			"label": __("Show Variant Attributes"),
			"fieldtype": "Check"
		},
		{
			"fieldname": 'show_stock_ageing_data',
			"label": __('Show Stock Ageing Data'),
			"fieldtype": 'Check'
		},
		{
			"fieldname": 'remove_zero_balance_item',
			"label": __('Remove Zero Balance Item'),
			"fieldtype": 'Check',
			"default": 1,
		},
		{
			"fieldname": 'show_inward_date_split',
			"label": __('Show Inward Date Split'),
			"fieldtype": 'Check',
		},
	],

	"onload": function (report) {
		const export_event = "stock_balance_horizontal_export_ready";
		const queue_method =
			"production_api.mrp_stock.report.stock_balance.stock_balance.queue_horizontal_download";
		const status_method =
			"production_api.mrp_stock.report.stock_balance.stock_balance.get_horizontal_download_status";
		let download_button;

		const clear_export_state = () => {
			if (report._horizontal_export_poll) {
				clearInterval(report._horizontal_export_poll);
				report._horizontal_export_poll = null;
			}
			report._horizontal_export_request_id = null;
			download_button && download_button.prop("disabled", false);
		};

		const trigger_download = (file_url, file_name) => {
			const link = document.createElement("a");
			link.href = file_url;
			link.download = file_name || "Stock_Balance_Horizontal.xlsx";
			document.body.appendChild(link);
			link.click();
			link.remove();
		};

		const handle_export_status = (data) => {
			if (
				!data ||
				!report._horizontal_export_request_id ||
				data.request_id !== report._horizontal_export_request_id
			) {
				return;
			}

			if (data.status === "ready") {
				clear_export_state();
				frappe.show_alert({
					message: __("Horizontal Stock Balance is ready"),
					indicator: "green",
				});
				trigger_download(data.file_url, data.file_name);
			} else if (["failed", "expired"].includes(data.status)) {
				clear_export_state();
				frappe.msgprint({
					title: __("Horizontal Export Failed"),
					message: data.error || __("The export expired. Please try again."),
					indicator: "red",
				});
			}
		};

		const poll_export_status = () => {
			if (!report._horizontal_export_request_id) return;
			frappe.call({
				method: status_method,
				args: { request_id: report._horizontal_export_request_id },
				callback: (response) => handle_export_status(response.message),
			});
		};

		if (report._horizontal_export_poll) {
			clearInterval(report._horizontal_export_poll);
		}
		frappe.realtime.off(export_event);
		frappe.realtime.on(export_event, handle_export_status);

		download_button = report.page.add_inner_button(__("Download as Horizontal"), () => {
			if (report._horizontal_export_request_id) {
				frappe.show_alert(__("The horizontal export is already being prepared."));
				return;
			}

			download_button.prop("disabled", true);
			frappe.call({
				method: queue_method,
				args: { filters: JSON.stringify(report.get_filter_values()) },
				callback: (response) => {
					if (!response.message || !response.message.request_id) {
						clear_export_state();
						return;
					}
					report._horizontal_export_request_id = response.message.request_id;
					report._horizontal_export_poll = setInterval(poll_export_status, 5000);
					frappe.show_alert({
						message: __("Preparing Horizontal Stock Balance in the background..."),
						indicator: "blue",
					}, 8);
				},
				error: clear_export_state,
			});
		});
	},

	// datatable rows have a uniform height (HyperList virtual scroll), so the
	// inward-split lines are shown by raising cellHeight to fit the tallest
	// cell (capped; overflow readable via the title tooltip). Runs on every
	// render, so toggling the checkbox resizes back to the default 33.
	"after_datatable_render": function (datatable) {
		let max_lines = 1;
		const rows = (frappe.query_report && frappe.query_report.data) || [];
		if (rows.length && cint(frappe.query_report.get_filter_value("show_inward_date_split"))) {
			rows.forEach((row) => {
				if (row.inward_split) {
					const lines = String(row.inward_split).split("\n").length;
					if (lines > max_lines) max_lines = lines;
				}
			});
		}
		const cell_height = 33 + (Math.min(max_lines, 6) - 1) * 21;
		if (datatable.options.cellHeight != cell_height) {
			datatable.options.cellHeight = cell_height;
			datatable.bodyRenderer.render();
		}
	},

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "out_qty" && data && data.out_qty > 0) {
			value = "<span style='color:red'>" + value + "</span>";
		} else if (column.fieldname == "in_qty" && data && data.in_qty > 0) {
			value = "<span style='color:green'>" + value + "</span>";
		}  else if (column.fieldname == "warehouse_name" && data && data.warehouse) {
			value = `<a href="/app/supplier/${data.warehouse}" data-doctype="Supplier" data-name="${data.warehouse}" data-value="${data.warehouse}">${data.warehouse_name}</a>`;
		} else if (column.fieldname == "inward_split" && data && data.inward_split) {
			const escaped = frappe.utils.escape_html(String(data.inward_split));
			value = `<span title="${escaped}">${escaped.replace(/\n/g, "<br>")}</span>`;
		}

		return value;
	}
};
