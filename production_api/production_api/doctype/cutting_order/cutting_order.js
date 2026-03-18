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

			// Summary tab — completed/incomplete items
			$(frm.fields_dict['completed_items_html'].wrapper).html("");
			frm.completed_items = new frappe.production.ui.CuttingCompletionDetail(
				frm.fields_dict['completed_items_html'].wrapper
			);
			frm.completed_items.load_data(frm.doc.completed_items_json, 1);

			$(frm.fields_dict['incompleted_items_html'].wrapper).html("");
			frm.incompleted_items = new frappe.production.ui.CuttingIncompletionDetail(
				frm.fields_dict['incompleted_items_html'].wrapper
			);
			frm.incompleted_items.load_data(frm.doc.incomplete_items_json);

			// Planned vs Actual tab
			frappe.call({
				method: "production_api.production_api.doctype.cutting_order.cutting_order.get_cutting_order_planned_vs_actual",
				args: { cutting_order: frm.doc.name },
				callback: function(r) {
					if (!r.message) return;
					$(frm.fields_dict['planned_details_html'].wrapper).html("");
					frm.planned_summary = new frappe.production.ui.WOSummary(
						frm.fields_dict['planned_details_html'].wrapper
					);
					frm.planned_summary.load_data(r.message, []);
				}
			});

			// Calculate LaySheets button
			frm.add_custom_button("Calculate LaySheets", function () {
				if (frm.is_dirty()) {
					return;
				}
				frappe.call({
					method: "production_api.production_api.doctype.cutting_order.cutting_order.calculate_laysheets",
					args: {
						cutting_order: frm.doc.name,
					},
				});
			});

			// Get Completed button
			frm.add_custom_button("Get Completed", () => {
				let d = new frappe.ui.Dialog({
					size: "large",
					fields: [
						{ fieldname: "pop_up_html", fieldtype: "HTML" },
						{ fieldname: "output_html", fieldtype: "HTML" },
					],
					primary_action_label: "Copy to Clipboard",
					secondary_action_label: "Take Screenshot",
					async primary_action() {
						let sourceDiv = d.fields_dict.pop_up_html.wrapper;
						let canvas = await html2canvas(sourceDiv, { scale: 1, useCORS: true });
						canvas.toBlob(async (blob) => {
							await navigator.clipboard.write([
								new ClipboardItem({ "image/png": blob }),
							]);
							frappe.show_alert("Image Copied to Clipboard");
						});
					},
					secondary_action() {
						let sourceDiv = d.fields_dict.pop_up_html.wrapper;
						html2canvas(sourceDiv, { scale: 1, useCORS: true }).then((canvas) => {
							let link = document.createElement("a");
							link.href = canvas.toDataURL("image/png");
							link.download = "screenshot.png";
							link.click();
						});
					},
				});
				d.$wrapper.find(".btn-modal-secondary").css({
					"background-color": "cadetblue",
					color: "white",
				});
				frm.completed_popup = new frappe.production.ui.CuttingCompletionDetail(d.fields_dict.pop_up_html.wrapper);
				frm.completed_popup.load_data(frm.doc.completed_items_json, 3);
				d.show();
			}, "Get or Update Completed");

			// Update Completed button
			frm.add_custom_button("Update Completed", () => {
				let d = new frappe.ui.Dialog({
					size: "extra-large",
					fields: [
						{
							"fieldname": "update_pop_up_html",
							"fieldtype": "HTML",
						}
					],
					primary_action_label: "Submit",
					primary_action() {
						frm.dirty();
						let items = frm.update_completed.get_items();
						frm.set_value("completed_items_json", JSON.stringify(items.json_data[0]));
						d.hide();
					}
				});
				frm.update_completed = new frappe.production.ui.CuttingCompletionDetail(d.fields_dict.update_pop_up_html.wrapper);
				frm.update_completed.load_data(frm.doc.completed_items_json, 2);
				d.show();
			}, "Get or Update Completed");
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
