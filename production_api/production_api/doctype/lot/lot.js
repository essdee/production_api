// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt


frappe.ui.form.on('Lot', {
	setup: function(frm) {
		frm.set_query('lot_template', (doc) => {
			return {
				filters: {
					item: doc.item,
				}
			}
		});
		frm.set_query('size', 'planned_qty', (doc) => {
			return {
				filters: {
					attribute_name: 'Size',
				}
			}
		});
	},

	refresh: function(frm) {
		frm.page.add_menu_item(__("Calculate"), function() {
			calculate_all(frm);
		}, false, 'Ctrl+E', false);
		if (!frm.is_new()) {
			frm.add_custom_button(__('Purchase Summary'), function() {
				frappe.set_route("query-report", "Lot Purchase Summary", {
					lot: frm.doc.name
				});
			}, __("View"));
		}
	},

	item: function(frm) {
		if (frm.doc.item) {
			frm.set_value({"lot_template": ""});
			frappe.call({
				method: "production_api.production_api.doctype.item.item.get_attribute_values",
				args: {
					item: frm.doc.item,
				},
				callback: function(r) {
					if (r.message) {
						if (r.message['Size']) {
							let planned_qty = []
							for(let i = 0;i < r.message.Size.length; i++) {
								planned_qty.push({size: r.message.Size[i], qty: 0});
							}
							frm.set_value({'planned_qty': planned_qty});
						}
					}
				}
			});
		}
	},

	lot_template: function(frm) {
		if (frm.doc.lot_template) {
			frappe.call({
				method: "production_api.production_api.doctype.lot_template.lot_template.get_attribute_values",
				args: {
					lot_template: frm.doc.lot_template,
				},
				callback: function(r) {
					if (r.message) {
						if (r.message['Size']) {
							let planned_qty = []
							for(let i = 0;i < r.message.Size.length; i++) {
								planned_qty.push({size: r.message.Size[i], qty: 0});
							}
							frm.set_value({'planned_qty': planned_qty});
						}
					}
				}
			});
		}
	},

	calculate_bom: function(frm) {
		if (frm.doc.item && frm.doc.lot_template && frm.doc.planned_qty.length > 0) {
			frappe.call({
				method: "production_api.production_api.doctype.lot_template.lot_template.get_calculated_bom",
				args: {
					lot_template: frm.doc.lot_template,
					planned_qty: frm.doc.planned_qty,
				},
				callback: function(r) {
					console.log(r.message);
					if (r.message) {
						if (r.message['items']) {
							let items = r.message.items || [];
							for (let i = 0; i < items.length; i++) {
								let bom = frm.doc.bom_summary;
								let found = false;
								for (let j = 0; j < bom.length; j++) {
									if (bom[j].item_name == items[i].item) {
										bom[j].required_qty = items[i].required_qty;
										found = true;
										break;
									}
								}
								if (!found) {
									var childTable = frm.add_child("bom_summary");
									childTable.item_name = items[i].item;
									childTable.required_qty = items[i].required_qty;
								}
							}
							frm.refresh_field('bom_summary');
						}
					}
				}
			});
		}
	}
});

frappe.ui.form.on('Lot Planned Qty', {
	qty: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.qty = parseInt(row.qty);
		calculate_all(frm);
	},
	cut_qty: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.cut_qty = parseInt(row.cut_qty);
		calculate_all(frm);
	},
	final_qty: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.final_qty = parseInt(row.final_qty);
		calculate_all(frm);
	},
});

function calculate_all(frm) {
	calculate_planned_qty(frm);
	frm.refresh_field("total_planned_qty")
	frm.refresh_field("total_final_qty")
	frm.refresh_field("total_cutting_qty")
	frm.dirty();
}

function calculate_planned_qty(frm) {
	let total_qty = 0, total_cut_qty = 0, total_final_qty = 0;
	$.each(frm.doc.planned_qty || [], function(i, v) {
		total_cut_qty += (v.cut_qty || 0)
		total_qty += (v.qty || 0);
		total_final_qty += (v.final_qty || 0);
    })
	frm.doc.total_planned_qty = total_qty;
	frm.doc.total_final_qty = total_final_qty;
	frm.doc.total_cutting_qty = total_cut_qty;
}
