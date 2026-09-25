// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

function open_lot_transfer_duplicate_dialog(frm, flat_rows) {
	const dialog = new frappe.ui.Dialog({
		title: __('Duplicate Lot Transfer'),
		size: 'extra-large',
		static: true,
		primary_action_label: __('Yes, Duplicate'),
		primary_action: function() {
			if (!dialog.editor) return;
			const items_data = dialog.editor.get_items();
			if (!items_data || items_data.length === 0) {
				frappe.show_alert({
					message: __('At least one item is required to duplicate.'),
					indicator: 'red',
				});
				return;
			}
			frappe.call({
				method: 'production_api.mrp_stock.doctype.lot_transfer.lot_transfer.duplicate_lot_transfer',
				args: { lot_transfer: frm.doc.name, items_data: items_data },
				freeze: true,
				freeze_message: __('Creating duplicate Lot Transfer'),
				callback: function(r) {
					if (r.message) {
						dialog.hide();
						frappe.set_route('Form', 'Lot Transfer', r.message);
					}
				},
			});
		},
		secondary_action_label: __('Close'),
		secondary_action: function() { dialog.hide(); },
	});
	dialog.$wrapper.find('.modal-dialog').css('max-width', '1400px');
	const wrapper = $('<div class="duplicate-lot-transfer-editor"></div>').appendTo(dialog.body);
	dialog.editor = new frappe.production.ui.DuplicateLotTransferItemTable(wrapper);
	dialog.editor.load_data(flat_rows);
	dialog.show();
	dialog.$wrapper.on('hidden.bs.modal', function() {
		if (dialog.editor && dialog.editor.destroy) dialog.editor.destroy();
	});
}

frappe.ui.form.on('Lot Transfer', {
	refresh: function(frm) {
		$(frm.fields_dict['item_html'].wrapper).html("");
		frm.itemEditor = new frappe.production.ui.LotTransferItem(frm.fields_dict["item_html"].wrapper);

		if(frm.doc.__onload && frm.doc.__onload.item_details) {
			frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.item_details);
			frm.itemEditor.load_data(frm.doc.__onload.item_details);
		} else {
			frm.itemEditor.load_data([]);
		}
		frm.itemEditor.update_status();
		frappe.production.ui.eventBus.$on("stock_updated", e => {
			frm.dirty();
		})
		add_make_dc_button(frm);
		add_duplicate_button(frm);
	},

	validate: function(frm) {
		if(frm.itemEditor){
			let items = frm.itemEditor.get_items();
			if(items && items.length > 0) {
				frm.doc['item_details'] = JSON.stringify(items);
			} else {
				frappe.throw(__('Add Items to continue'));
			}
		}
		else {
			frappe.throw(__('Please refresh and try again.'));
		}
	},

	purpose: function(frm) {
		if (frm.doc.purpose) {
			frappe.production.ui.eventBus.$emit("purpose_updated", frm.doc.purpose)
		}
		frm.cscript.toggle_related_fields(frm.doc);
		frm.cscript.set_mandatory_fields(frm.doc);
	}
});

function add_duplicate_button(frm) {
	if (frm.doc.docstatus !== 1) {
		return;
	}

	frm.add_custom_button(__('Duplicate'), function() {
		frappe.call({
			method: 'production_api.mrp_stock.doctype.lot_transfer.lot_transfer.get_lot_transfer_duplicate_items',
			args: { lot_transfer: frm.doc.name },
			freeze: true,
			callback: function(r) {
				open_lot_transfer_duplicate_dialog(frm, r.message || []);
			},
		});
	});
}

function add_make_dc_button(frm) {
	if (frm.doc.docstatus !== 1) {
		return;
	}

	let target_lots = [...new Set(
		(frm.doc.items || []).filter(row => row.qty > 0).map(row => row.to_lot)
	)];
	let warehouses = [...new Set(
		(frm.doc.items || []).filter(row => row.qty > 0).map(row => row.warehouse)
	)];
	let target_lot = target_lots.length === 1 ? target_lots[0] : null;
	let default_warehouse = warehouses.length === 1 ? warehouses[0] : null;

	frm.add_custom_button(__("Make DC"), () => {
		if (!target_lot) {
			frappe.msgprint(__("Make DC requires all Lot Transfer items to have one target Lot."));
			return;
		}

		let dialog = new frappe.ui.Dialog({
			title: __("Make Delivery Challan"),
			fields: [
				{
					fieldname: "work_order",
					fieldtype: "Link",
					options: "Work Order",
					label: __("Work Order"),
					reqd: 1,
					get_query: () => ({
						filters: {
							lot: target_lot,
							docstatus: 1,
							is_delivered: 0,
							open_status: "Open",
						},
					}),
				},
				{
					fieldname: "from_location",
					fieldtype: "Link",
					options: "Supplier",
					label: __("From Location"),
					reqd: 1,
					default: default_warehouse,
					get_query: () => ({ filters: { disabled: 0 } }),
				},
			],
			primary_action_label: __("Make DC"),
			primary_action(values) {
				frappe.call({
					method: "production_api.mrp_stock.doctype.lot_transfer.lot_transfer.get_delivery_challan_details",
					args: {
						doc_name: frm.doc.name,
						work_order: values.work_order,
						from_location: values.from_location,
					},
					freeze: true,
					freeze_message: __("Preparing Delivery Challan..."),
					callback(r) {
						if (!r.message) {
							return;
						}

						let data = r.message;
						sessionStorage.setItem("prefilled_delivery_challan", "1");
						sessionStorage.setItem(
							"delivery_challan_onload_data",
							JSON.stringify(data.item_details)
						);

						let dc = frappe.model.get_new_doc("Delivery Challan");
						dc.naming_series = "DC-";
						dc.posting_date = frappe.datetime.nowdate();
						dc.posting_time = new Date().toTimeString().split(" ")[0];
						dc.actual_date = frappe.datetime.nowdate();
						[
							"work_order", "lot", "item", "production_detail", "process_name",
							"includes_packing", "is_internal_unit", "from_location", "from_address",
							"from_address_details", "supplier", "supplier_name", "supplier_address",
							"supplier_address_details",
						].forEach(field => dc[field] = data[field]);

						dialog.hide();
						frappe.set_route("Form", dc.doctype, dc.name);
					},
				});
			},
		});
		dialog.show();
	});
}
