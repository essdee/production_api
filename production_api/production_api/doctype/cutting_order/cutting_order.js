// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting Order", {
	refresh(frm) {
		// Mount Vue component
		$(frm.fields_dict['items_html'].wrapper).html("");
		frm.cutting_order_items = new frappe.production.ui.CuttingOrderItems(
			frm.fields_dict['items_html'].wrapper
		);

		// Load existing data
		if (frm.doc.__onload && frm.doc.__onload.cutting_order_items) {
			frm.cutting_order_items.load_data(frm.doc.__onload.cutting_order_items);
		} else if (frm.doc.items_json) {
			try {
				let data = JSON.parse(frm.doc.items_json);
				frm.cutting_order_items.load_data(data);
			} catch(e) {
				console.error("Failed to parse items_json", e);
			}
		}

		// Read-only when submitted
		if (frm.doc.docstatus === 1) {
			frm.cutting_order_items.set_read_only(true);
		}
	},

	cutting_order_detail(frm) {
		if (!frm.doc.cutting_order_detail) {
			$(frm.fields_dict['items_html'].wrapper).html("");
			return;
		}
		frappe.call({
			method: 'production_api.production_api.doctype.cutting_order.cutting_order.get_cutting_order_detail_data',
			args: { cutting_order_detail: frm.doc.cutting_order_detail },
			callback: function(r) {
				if (!r.message) return;
				let d = r.message;
				frm.set_value('item', d.item);
				frm.set_value('is_set_item', d.is_set_item ? 1 : 0);

				let data = {
					is_set_item: d.is_set_item ? true : false,
					sizes: d.sizes || [],
					colours: d.colours || [],
					parts: d.parts || [],
					items: [],
				};

				if (!d.is_set_item) {
					// Non-set: pre-populate all colours as rows
					data.items = (d.colours || []).map(colour => {
						let quantities = {};
						(d.sizes || []).forEach(s => { quantities[s] = 0; });
						return { colour: colour, quantities: quantities };
					});
				} else {
					// Set item: use actual colour×part combos from set_item_combination_details
					(d.items || []).forEach(item => {
						let quantities = {};
						(d.sizes || []).forEach(s => { quantities[s] = 0; });
						data.items.push({
							colour: item.colour,
							part: item.part,
							major_colour: item.major_colour,
							quantities: quantities,
						});
					});
				}

				// Remount fresh component
				$(frm.fields_dict['items_html'].wrapper).html("");
				frm.cutting_order_items = new frappe.production.ui.CuttingOrderItems(
					frm.fields_dict['items_html'].wrapper
				);
				frm.cutting_order_items.load_data(data);
				frm.dirty();
			}
		});
	},

	validate(frm) {
		if (frm.cutting_order_items) {
			let data = frm.cutting_order_items.get_data();
			frm.doc.items_json = JSON.stringify(data);
		}
	},
});
