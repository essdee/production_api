// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('FG Item Master', {
	setup: function(frm) {
		frm.set_query('attribute_value', 'sizes', (doc, cdt, cdn) => {
			// let child = locals[cdt][cdn]
			return {
				filters: {
					'attribute_name': 'Size',
				}
			}
		});
	},

	refresh: function(frm) {
		if (!frm.is_new()) {
			frm.page.add_menu_item(__('Sync FG Item'), function() {
				frappe.call({
					method: "production_api.product_development.doctype.fg_item_master.fg_item_master.sync_fg_items",
					args: {
						"names": [frm.doc.name],
					},
					callback: function(r) {
						if (r.message) {
							console.log(r.message)
						}
					}
				})
			});
			frm.page.add_menu_item(__('Rename FG Item'), function() {
				frappe.call({
					method: "production_api.product_development.doctype.fg_item_master.fg_item_master.sync_fg_items",
					args: {
						"names": [frm.doc.name],
						"rename": true,
					},
					callback: function(r) {
						if (r.message) {
							console.log(r.message)
						}
					}
				})
			});
		}
	},

	size_range: function(frm) {
		if (frm.doc.size_range) {
			frm.trigger("get_sizes");
		} else {
			frm.set_value("sizes", []);
		}
	},

	get_sizes: function(frm) {
		frappe.db.get_doc("FG Item Size Range", frm.doc.size_range).then(size_range => {
			console.log(size_range);
			frm.set_value("sizes", []);
			size_range.sizes.forEach(size => {
				let row = frm.add_child("sizes");
				row.attribute_value = size.attribute_value;
			});
			frm.refresh_field("sizes");
		});
	}
});
