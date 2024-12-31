// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Lot Purchase Summary"] = {
	"filters": [
		{
			"fieldname": "lot",
			"label": __("Lot"),
			"fieldtype": "Link",
			"options": "Lot",
			on_change: (report) => {
				clear_selected_rows(report);
				report.refresh(true);
			}
		},
		{
			"fieldname": "item",
			"label": __("Item Variant"),
			"fieldtype": "Link",
			"options": "Item Variant",
			on_change: (report) => {
				clear_selected_rows(report);
				report.refresh(true);
			}
		},
		{
			"fieldname": "parent_item",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
			on_change: (report) => {
				clear_selected_rows(report);
				report.refresh(true);
			}
		},
	],

	onload(report) {
		console.log(report);
		report.page.add_inner_button('Purchase Order', () => {
			frappe.prompt([
				{
					label: 'Delivery Location',
					fieldname: 'delivery_location',
					fieldtype: 'Link',
					options: 'Supplier',
					reqd: true,
				},
				{
					label: 'Delivery Date',
					fieldname: 'delivery_date',
					fieldtype: 'Date',
					reqd: true,
				},
			], (values) => {
				create_purchase_order(report, values)
			})
		}, 'Create')
	},

	get_datatable_options(options) {
		return Object.assign(options, {
			checkboxColumn: true,
		})
	},
};

function create_purchase_order(report, values) {
	let data = get_selected_rows(report);
	if (!data || data.length == 0) {
		frappe.msgprint("Please Select any row.");
		return;
	}
	let po_data = []
	for (let i = 0; i < data.length; i++) {
		let qty = 0;
		if (data[i].required_qty) {
			qty = data[i].required_qty - data[i].stock_qty - data[i].po_pending_qty;
		}
		if (qty > 0) {
			po_data.push({
				'item': data[i].item,
				'lot': data[i].lot,
				'qty': qty,
				'delivery_location': values['delivery_location'],
				'delivery_date': values['delivery_date'],
			})
		}
	}
	frappe.call({
		method: 'production_api.production_api.doctype.purchase_order.purchase_order.make_purchase_order_mapped_doc',
		args: {
			items: po_data
		},
		callback: function(r) {
			if(r.message) {
				frappe.model.sync(r.message);
				frappe.set_route("Form", r.message.doctype, r.message.name);
			}
		}
	});
}

function get_selected_rows(report) {
	let check_index = report.datatable.rowmanager.checkMap || []
	let data = []
	if (check_index && check_index.length > 0) {
		for (let i = 0; i < check_index.length; i++) {
			if (check_index[i]) {
				let d = report.datatable.datamanager.data[i];
				d['_idx_'] = i;
				data.push(d)
			}
		}
	}
	return data;
}

function clear_selected_rows(report) {
	report.datatable.rowmanager.checkMap = [];
	report.datatable.rowmanager.refreshRows();
}
