// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lot", {
	setup(frm) {
		frm.set_query('production_detail', (doc) => {
			return {
				filters: {
					'item': doc.item
				}
			}
		})
		frm.set_query("production_order", (doc) => {
			return {
				filters: {
					"item": doc.item,
					"docstatus": 1,
					"status": "Open",
				}
			}
		})
	},
	refresh(frm) {
		$(".layout-side-section").css("display", "none");
		frm.page.add_menu_item(__("Calculate"), function () {
			calculate_all(frm);
		}, false, 'Ctrl+E', false);
		frappe.call({
			method: "production_api.essdee_production.doctype.lot.lot.check_enabled_po",
			callback: function (r) {
				let x = true
				if (!r.message) {
					x = false
				}
				frm.set_df_property("item", "read_only", x)
				frm.refresh_field("item")
				if (frm.doc.item && !frm.doc.production_order) {
					frm.set_df_property("production_order", "read_only", true)
				}
				else{
					frm.set_df_property("production_order", "read_only", !x)
				}
				frm.refresh_field("production_order")
			}
		})
		if(frm.doc.production_detail){
			frm.set_df_property("production_order", "read_only", true)
			frm.refresh_field("production_order")
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__('Purchase Summary'), function () {
				frappe.set_route("query-report", "Lot Purchase Summary", {
					lot: frm.doc.name
				});
			}, __("View"));

			frm.add_custom_button(__('Link to PO'), function() {
				new frappe.ui.form.MultiSelectDialog({
					doctype: 'Purchase Order',
					target: frm,
					date_field: 'po_date',
					get_query() {
						return { filters: { docstatus: 1, open_status: 'Open' } };
					},
					primary_action_label: __('Link'),
					action(selections) {
						if (!selections || !selections.length) {
							frappe.show_alert({ message: __('Select at least one Purchase Order'), indicator: 'red' });
							return;
						}
						frappe.prompt(
							[{ fieldname: 'comment', fieldtype: 'Small Text', label: 'Reason', reqd: 1 }],
							function(values) {
								frappe.call({
									method: 'production_api.production_api.doctype.purchase_order.purchase_order.update_lot_po_links',
									args: { lot: frm.doc.name, add_pos: selections, comment: values.comment },
									freeze: true,
									freeze_message: __('Linking lot to Purchase Orders...'),
									callback: function() {
										frappe.show_alert({ message: __('Lot linked to {0} PO(s)', [selections.length]), indicator: 'green' });
									},
								});
							},
							__('Reason for Linking'),
							__('Link')
						);
					},
				});
			}, __('Actions'));

			frm.add_custom_button(__('Unlink from PO'), function() {
				frappe.call({
					method: 'production_api.production_api.doctype.purchase_order.purchase_order.get_purchase_orders_for_lot',
					args: { lot: frm.doc.name },
					callback: function(r) {
						const linked = r.message || [];
						if (!linked.length) {
							frappe.show_alert({ message: __('This lot is not linked to any submitted PO'), indicator: 'blue' });
							return;
						}
						new frappe.ui.form.MultiSelectDialog({
							doctype: 'Purchase Order',
							target: frm,
							date_field: 'po_date',
							get_query() {
								return { filters: { name: ['in', linked], docstatus: 1 } };
							},
							primary_action_label: __('Unlink'),
							action(selections) {
								if (!selections || !selections.length) {
									frappe.show_alert({ message: __('Select at least one Purchase Order'), indicator: 'red' });
									return;
								}
								frappe.prompt(
									[{ fieldname: 'comment', fieldtype: 'Small Text', label: 'Reason', reqd: 1 }],
									function(values) {
										frappe.call({
											method: 'production_api.production_api.doctype.purchase_order.purchase_order.update_lot_po_links',
											args: { lot: frm.doc.name, remove_pos: selections, comment: values.comment },
											freeze: true,
											freeze_message: __('Unlinking lot from Purchase Orders...'),
											// unlink-guard throw (received qty) surfaces via the standard error dialog
										});
									},
									__('Reason for Unlinking'),
									__('Unlink')
								);
							},
						});
					},
				});
			}, __('Actions'));
		}
		frappe.db.get_single_value("T and A Settings", "assigned_person_editer_role").then((res) => {
			if (!frappe.user.has_role(res)) {
				frm.set_df_property("assigned_person", "read_only", true)
			}
			else {
				frm.set_df_property("assigned_person", "read_only", false)
			}
		})
		frm.set_df_property('bom_summary', 'cannot_add_rows', true)
		frm.set_df_property('bom_summary', 'cannot_delete_rows', true)
		if (frm.doc.lot_time_and_action_details.length == 0) {
			frm.add_custom_button("Calculate Order Items", () => {
				let d = new frappe.ui.Dialog({
					title: "Confirm Calculation",
					primary_action_label: "Yes",
					secondary_action_label: "No",
					primary_action() {
						d.hide()
						frappe.call({
							method: "production_api.essdee_production.doctype.lot.lot.update_order_details",
							args: {
								doc_name: frm.doc.name,
							},
							freeze: true,
							freeze_message: __("Calculating Order Items..."),
							callback: function (r) {
								frm.reload_doc()
							}
						})
					},
					secondary_action() {
						d.hide()
					}
				})
				d.show()
			})
		}
		if (!frm.is_new() && frm.doc.production_detail) {
			frm.add_custom_button(__("Build Cloth Program"), () => {
				if (frm.is_dirty()) {
					frappe.msgprint(__("Save the Lot before calculating the cloth program."));
					return;
				}
				open_cloth_program_preview(frm);
			});
			if (frm.has_perm("write")) {
				frm.add_custom_button(__("Update Colour"), () => {
					if (frm.is_dirty()) {
						frappe.msgprint(__("Save the Lot before updating colours."));
						return;
					}
					open_colour_update_dialog(frm);
				}, __("Actions"));
			}
		}
		load_saved_cloth_program(frm);
		$(frm.fields_dict['items_html'].wrapper).html("")
		frm.item = new frappe.production.ui.LotOrder(frm.fields_dict['items_html'].wrapper)
		if (frm.doc.__onload && frm.doc.__onload.item_details) {
			frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.item_details);
			frm.item.load_data(frm.doc.__onload.item_details);
		}
		else {
			if (frm.doc.item && frm.doc.production_detail) {
				frappe.call({
					method: 'production_api.essdee_production.doctype.lot.lot.get_item_details',
					args: {
						item_name: frm.doc.item,
						uom: frm.doc.uom,
						production_detail: frm.doc.production_detail,
						ppo: frm.doc.production_order,
					},
					callback: function (r) {
						frm.item.load_data(r.message)
						if (frm.doc.production_order) {
							frm.item.show_inputs()
							frm.item.load_data(r.message)
						}
						cur_frm.dirty()
					}
				})
			}
			else {
				frm.item.load_data([])
			}
		}
		if (frm.doc.lot_order_details.length > 0) {
			frappe.call({
				method: "production_api.essdee_production.doctype.lot.lot.get_packing_attributes",
				args: {
					ipd: frm.doc.production_detail,
				},
				callback: function (r) {
					frm.fields_dict['size_set_colour'].df.options = r.message.major_colours
					frm.refresh_field("size_set_colour")
				}
			})
		}
		if (frm.doc.lot_time_and_action_details.length > 0) {
			$(frm.fields_dict['time_and_action_html'].wrapper).html("")
			frm.time_action = new frappe.production.ui.TimeAction(frm.fields_dict['time_and_action_html'].wrapper)
			if (frm.doc.__onload && frm.doc.__onload.action_details) {
				frm.time_action.load_data(frm.doc.__onload.action_details)
			}
			$(frm.fields_dict['time_and_action_report_html'].wrapper).html("")
			frm.time_action_report = new frappe.production.ui.TimeActionReport(frm.fields_dict['time_and_action_report_html'].wrapper)
			if (frappe.user.has_role("T & A Admin")) {
				frm.add_custom_button("Revert T & A", () => {
					let d = new frappe.ui.Dialog({
						title: "Are you sure want to Revert the T & A",
						primary_action_label: "Yes",
						secondary_action_label: "No",
						primary_action() {
							d.hide()
							frappe.call({
								method: "production_api.essdee_production.doctype.time_and_action.time_and_action.revert_t_and_a",
								args: {
									doc_name: frm.doc.name
								},
								freeze: true,
								freeze_message: "Reverting T & A",
								callback: function () {
									frm.reload_doc()
								}
							})
							d.hide()
						},
						secondary_action() {
							d.hide()
						}
					})
					d.show()
				})
			}
		}
		if (frm.doc.lot_time_and_action_details.length == 0 && frm.doc.assigned_person && frm.doc.size_set_colour) {
			frm.add_custom_button("Create T&A", () => {
				frappe.call({
					method: "production_api.essdee_production.doctype.lot.lot.get_packing_attributes",
					args: {
						ipd: frm.doc.production_detail,
					},
					callback: function (r) {
						let data = []
						for (let i = 0; i < r.message.colour_combo.length; i++) {
							data.push(
								{ 'colour': r.message.colour_combo[i]['colour'], 'master': null, 'major_colour': r.message.colour_combo[i]['major_colour'] }
							)
						}
						let label = "Colours"
						if (frm.doc.is_set_item) {
							label += " - " + frm.doc.set_item_attribute
						}
						let dialog = new frappe.ui.Dialog({
							size: "extra-large",
							fields: [
								{
									label: label,
									fieldname: 'table',
									fieldtype: 'Table',
									cannot_add_rows: true,
									in_place_edit: false,
									data: data,
									fields: [
										{
											fieldname: 'major_colour',
											fieldtype: 'Data',
											in_list_view: 1,
											label: 'Major Colour',
											read_only: 1
										},
										{
											fieldname: 'colour',
											fieldtype: 'Data',
											in_list_view: 1,
											label: 'Colour',
											read_only: 1
										},
										{
											fieldname: 'master',
											fieldtype: 'Link',
											in_list_view: 1,
											options: "Action Master",
											label: 'Master',
											reqd: 1,
											filters: {
												"workflow_state": "Approved",
												"disable": 0,
											}
										},
									]
								},
								{
									label: 'Start Date',
									fieldname: "start_date",
									fieldtype: "Date",
									reqd: true,
								},
							],
							primary_action_label: "Submit",
							secondary_action_label: "Preview",
							primary_action(values) {
								for (let i = 0; i < values.table.length; i++) {
									if (values.table[i].master == null) {
										frappe.throw(`Mention master for colour ${values.table[i].colour}`)
									}
								}
								if (!values.start_date) {
									frappe.throw("Select the Start Date")
								}
								frappe.call({
									method: "production_api.essdee_production.doctype.action_master.action_master.get_action_master_details",
									args: {
										master_list: values.table,
									},
									callback: async function (res) {
										let d = new frappe.ui.Dialog({
											size: "large",
											title: "Work Station List",
											fields: [
												{
													"fieldtype": "HTML",
													"fieldname": "work_station_html",
												},
											],
											primary_action() {
												let items = popupDialog.get_items()
												frappe.call({
													method: "production_api.essdee_production.doctype.time_and_action.time_and_action.create_time_and_action",
													args: {
														"lot": frm.doc.name,
														"item_name": frm.doc.item,
														"args": r.message,
														"values": values,
														"total_qty": frm.doc.total_order_quantity,
														"items": items
													}
												})
												d.hide()
											}
										})
										d.show()
										let popupDialog = new frappe.production.ui.WorkStation(d.fields_dict['work_station_html'].wrapper);
										await popupDialog.load_data(res.message, "create")
										popupDialog.set_attributes()
									}
								})
								dialog.hide()
							},
							secondary_action() {
								let table = dialog.get_value("table")
								for (let i = 0; i < table.length; i++) {
									if (table[i].master == null) {
										frappe.throw(`Mention master for colour ${table[i].colour}`)
									}
								}
								if (!dialog.get_value("start_date")) {
									frappe.throw("Select the Start Date")
								}

								frappe.call({
									method: "production_api.essdee_production.doctype.time_and_action.time_and_action.get_t_and_a_preview_data",
									args: {
										"start_date": dialog.get_value("start_date"),
										"table": dialog.get_value("table")
									},
									callback: function (r) {
										let d = new frappe.ui.Dialog({
											size: "extra-large",
											fields: [
												{
													fieldname: "preview_html",
													fieldtype: "HTML"
												}
											],
											primary_action_label: "Close",
											primary_action() {
												d.hide()
											}
										})
										let previewDialog = new frappe.production.ui.TimeActionPreview(d.fields_dict['preview_html'].wrapper);
										previewDialog.load_data(r.message, dialog.get_value("start_date"))
										d.show()
									}
								})
							}
						});
						dialog.show();
					}
				})
			})
		}
		frm.order_detail = new frappe.production.ui.CutPlanItems(frm.fields_dict['lot_item_order_detail_html'].wrapper)
		if (frm.doc.__onload && frm.doc.__onload.order_item_details) {
			frm.order_detail.load_data(frm.doc.__onload.order_item_details, frm.doc.lot_time_and_action_details.length);
		}
		else {
			frm.order_detail.load_data([], 0)
		}
		if (frm.doc.is_transferred) {
			frm.order_detail.update_status()
		}
		// if(!frm.is_new()){
		// 	frm.cad_detail = new frappe.production.ui.CadDetail(frm.fields_dict['cad_detail_html'].wrapper)
		// 	if(frm.doc.__onload && frm.doc.__onload.cad_item_details) {
		// 		frm.cad_detail.load_data(frm.doc.__onload.cad_item_details);
		// 	}
		// 	else{
		// 		frm.cad_detail.load_data([])
		// 	}
		// }
		if (!frm.is_new() && frm.doc.item && frm.doc.production_detail) {
			$(frm.fields_dict['ocr_detail_html'].wrapper).html("")
			new frappe.production.ui.OCRDetail(frm.fields_dict['ocr_detail_html'].wrapper)
		}
		if (frm.doc.has_transferred) {
			new frappe.production.ui.AlternativeDetail(frm.fields_dict['alternative_html'].wrapper)
		}
	},
	production_order(frm) {
		if (frm.doc.production_order) {
			frappe.db.get_value("Production Order", frm.doc.production_order, "item").then((r) => {
				frm.set_value("item", r.message.item)
				frm.refresh_field("item")
			})
		}
		else{
			frm.set_value("production_detail", "")
			frm.set_value("item", "")
			frm.refresh_field("item")
			frm.refresh_field("production_detail")
		}
	},
	// fetch_cad_template(frm){
	// 	frm.cad_detail.load_data([])
	// 	if(!frm.is_dirty()){
	// 		frm.dirty()
	// 	}
	// },
	async validate(frm) {
		if (frm.item) {
			let items = frm.item.get_data()
			frm.doc['item_details'] = JSON.stringify(items)
		}
		let order_items = frm.order_detail.get_items()
		frm.doc['order_item_details'] = JSON.stringify(order_items)
		if (frm.time_action) {
			let action_items = await frm.time_action.get_data()
			if (action_items.changed) {
				frm.doc['action_details'] = JSON.stringify(action_items.items)
			}
		}
		// if(frm.cad_detail){
		// 	let cad_data = frm.cad_detail.get_data()
		// 	frm.doc['cad_details'] = JSON.stringify(cad_data)
		// }
	},
	item(frm) {
		if (!frm.doc.item) {
			if (frm.item) {
				frm.item.load_data([])
			}
		}
	},
	async production_detail(frm) {
		if (frm.doc.production_detail) {
			await frappe.call({
				method: 'production_api.essdee_production.doctype.lot.lot.get_isfinal_uom',
				args: {
					item_production_detail: frm.doc.production_detail,
					get_pack_stage: true,
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value('uom', r.message.uom)
						frm.set_value('pack_in_stage', r.message.pack_in_stage)
						frm.set_value('packing_uom', r.message.packing_uom)
						frm.set_value('pack_out_stage', r.message.pack_out_stage)
						frm.set_value('dependent_attribute_mapping', r.message.dependent_attr_mapping)
						frm.set_value('tech_pack_version', r.message.tech_pack_version)
						frm.set_value('pattern_version', r.message.pattern_version)
						frm.set_value('packing_combo', r.message.packing_combo)
					}
				}
			})
			frappe.call({
				method: 'production_api.essdee_production.doctype.lot.lot.get_item_details',
				args: {
					item_name: frm.doc.item,
					uom: frm.doc.uom,
					production_detail: frm.doc.production_detail,
					dependent_attr_mapping: frm.doc.dependent_attribute_mapping,
					ppo: frm.doc.production_order,
				},
				callback: function (r) {
					frm.item.load_data(r.message)
					if (frm.doc.production_order) {
						frm.item.show_inputs()
						frm.item.load_data(r.message)
					}
				}
			})
		}
		else{
			let fields = ['uom', 'pack_in_stage', 'packing_uom', 'pack_out_stage', 'dependent_attribute_mapping', 'tech_pack_version', 'pattern_version', 'packing_combo']
			fields.forEach(field => {
				frm.set_value(field, "")
				frm.refresh_field(field)
			})
			if (frm.item) {
				frm.item.load_data([])
			}
		}
	},
	calculate_bom: function (frm) {
		if (frm.is_dirty()) {
			frappe.msgprint("Save the document before calculate the BOM")
			return
		}
		if (frm.doc.item && frm.doc.production_detail) {
			frappe.call({
				method: "production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_calculated_bom",
				args: {
					item_production_detail: frm.doc.production_detail,
					items: frm.doc.lot_order_details,
					lot_name: frm.doc.name
				},
				freeze: true,
				freeze_message: __("Calculating BOM..."),
				callback: function (r) {
					frm.refresh()
				}
			});
		}
	}
});

function open_cloth_program_preview(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Build Cloth Program"),
		size: "extra-large",
		fields: [
			{
				label: __("Cloth Excess Percentage"),
				fieldname: "extra_percentage",
				fieldtype: "Float",
				default: frm.doc.cloth_excess_percentage || 0,
				description: __("Adds this percentage to every calculated cloth Colour and Dia."),
			},
			{
				fieldname: "cloth_program_result",
				fieldtype: "HTML",
			},
		],
		primary_action_label: __("Calculate"),
		primary_action(values) {
			const extra_percentage = Number(values.extra_percentage || 0);
			if (extra_percentage < 0) {
				frappe.msgprint(__("Cloth Excess Percentage cannot be negative."));
				return;
			}
			const result_wrapper = dialog.fields_dict.cloth_program_result.wrapper;
			const selected_additions = collect_cloth_program_additions(result_wrapper);
			const args = {
				lot: frm.doc.name,
				extra_percentage: extra_percentage,
			};
			if (selected_additions !== null) {
				args.additions = JSON.stringify(selected_additions);
			}
			frappe.call({
				method: "production_api.essdee_production.doctype.lot.cloth_program.get_cloth_program_preview",
				args,
				freeze: true,
				freeze_message: __("Calculating cloth program..."),
				callback(r) {
					frm.doc.cloth_excess_percentage = extra_percentage;
					if (r.message && r.message.cloth_program_additions !== undefined) {
						frm.doc.cloth_program_additions = r.message.cloth_program_additions;
					}
					if (r.message && r.message.lot_modified) {
						frm.doc.modified = r.message.lot_modified;
					}
					frm.refresh_field("cloth_excess_percentage");
					render_cloth_program_preview(
						result_wrapper,
						r.message || {}
					);
					render_saved_cloth_program(frm, r.message || {});
				},
			});
		},
		secondary_action_label: __("Print"),
		secondary_action() {
			open_cloth_program_print(frm);
		},
	});
	dialog.show();
	render_cloth_program_preview(dialog.fields_dict.cloth_program_result.wrapper, {});
}

function load_saved_cloth_program(frm) {
	const result_field = frm.fields_dict.cloth_program_html;
	if (!result_field) {
		return;
	}

	const extra_percentage = Number(frm.doc.cloth_excess_percentage || 0);
	if (frm.is_new() || !frm.doc.production_detail || !has_saved_cloth_program(frm)) {
		render_saved_cloth_program(frm, {});
		return;
	}

	$(result_field.wrapper).html(`
		<div class="text-muted" style="padding: 18px 0;">
			${__("Loading cloth program...")}
		</div>
	`);
	frappe.call({
		method: "production_api.essdee_production.doctype.lot.cloth_program.get_cloth_program_preview",
		args: {
			lot: frm.doc.name,
			extra_percentage,
		},
		callback(r) {
			render_saved_cloth_program(frm, r.message || {});
		},
		error() {
			$(result_field.wrapper).html(`
				<div class="text-muted" style="padding: 18px 0;">
					${__("The cloth program could not be loaded.")}
				</div>
			`);
		},
	});
}

function render_saved_cloth_program(frm, preview) {
	const result_field = frm.fields_dict.cloth_program_html;
	if (!result_field) {
		return;
	}
	render_cloth_program_preview(
		result_field.wrapper,
		has_saved_cloth_program(frm) ? preview : {},
		__("Build the Cloth Program to view its saved details here."),
		true
	);
	$(result_field.wrapper)
		.find('[data-action="print-cloth-program"]')
		.on("click", () => open_cloth_program_print(frm));
}

function open_cloth_program_print(frm) {
	const print_window = window.open(
		frappe.urllib.get_full_url(
			"/printview?doctype=" + encodeURIComponent(frm.doc.doctype)
			+ "&name=" + encodeURIComponent(frm.doc.name)
			+ "&format=" + encodeURIComponent("Lot Cloth Program")
			+ "&trigger_print=1"
		),
		"_blank"
	);
	if (!print_window) {
		frappe.msgprint(__("Please enable pop-ups"));
	}
}

function parse_cloth_program_additions(value) {
	if (!value) return [];
	let parsed = value;
	if (typeof parsed === "string") {
		try {
			parsed = JSON.parse(parsed);
		} catch (_error) {
			return [];
		}
	}
	if (Array.isArray(parsed)) return parsed;
	return Array.isArray(parsed.totals) ? parsed.totals : [];
}

function has_saved_cloth_program(frm) {
	return Number(frm.doc.cloth_excess_percentage || 0) > 0
		|| parse_cloth_program_additions(frm.doc.cloth_program_additions)
			.some((row) => Number(row.additional_weight || 0) > 0);
}

function collect_cloth_program_additions(wrapper) {
	const inputs = $(wrapper).find("[data-cloth-program-addition]");
	if (!inputs.length) return null;
	const additions = [];
	inputs.each((_index, element) => {
		const additional_weight = Number(element.value || 0);
		if (additional_weight <= 0) return;
		additions.push({
			cloth_item: element.dataset.clothItem || "",
			requirement_type: element.dataset.requirementType || "cloth",
			accessory_name: element.dataset.accessoryName || null,
			colour: element.dataset.colour || null,
			additional_weight,
		});
	});
	return additions;
}

function render_cloth_program_preview(wrapper, preview, empty_message, is_saved_view = false) {
	const rows = preview.rows || [];
	if (!rows.length) {
		$(wrapper).html(`
			<div class="text-muted" style="padding: 18px 0;">
				${empty_message || __("Enter the Cloth Excess Percentage and click Calculate.")}
			</div>
		`);
		return;
	}

	const escape = (value) => frappe.utils.escape_html(String(value ?? ""));
	const round_weight = (value) => {
		const number = Number(value || 0);
		const floor = Math.floor(number);
		return number - floor > 0.5 ? Math.ceil(number) : floor;
	};
	const format_weight = (value) => round_weight(value).toLocaleString();
	const format_number = (value) => Number(value || 0).toLocaleString(
		undefined, { maximumFractionDigits: 3 }
	);
	const accessory_block_label = (value) => {
		const label = String(value || __("Accessory"))
			.trim()
			.replace(/\s+/g, " ")
			.replace(/\b\w/g, (letter) => letter.toUpperCase());
		return /\bFabric$/i.test(label) ? label : `${label} Fabric`;
	};
	const uses_compacting_details = Boolean(preview.uses_compacting_details);
	const addition_key = (cloth_item, requirement_type, accessory_name, colour) => [
		cloth_item || "",
		requirement_type === "accessory" ? "accessory" : "cloth",
		requirement_type === "accessory" ? (accessory_name || "") : "",
		colour || "",
	].join("\u0000");
	const addition_map = {};
	(preview.additions || []).forEach((row) => {
		addition_map[addition_key(
			row.cloth_item,
			row.requirement_type,
			row.accessory_name,
			row.colour
		)] = Number(row.additional_weight || 0);
	});
	const table_groups = {};
	rows.forEach((row) => {
		const cloth_item = row.cloth_item || __("Unspecified Cloth");
		const requirement_type = row.requirement_type === "accessory" ? "accessory" : "cloth";
		const accessory_name = row.accessory_name || "";
		const table_key = cloth_item;
		const colour_value = row.colour || "";
		const colour = colour_value || __("No Colour");
		const dia = row.compacting_dia
			? `${row.input_dia || __("No Dia")} → ${row.compacting_dia || __("No Dia")}`
			: (row.dia || __("No Dia"));
		const route_key = [requirement_type, accessory_name, dia].join("\u0000");
		if (!table_groups[table_key]) {
			table_groups[table_key] = {
				cloth_item,
				colours: new Set(),
				colour_values: {},
				routes: {},
				weights: {},
			};
		}
		table_groups[table_key].colours.add(colour);
		table_groups[table_key].colour_values[colour] = colour_value;
		table_groups[table_key].routes[route_key] = {
			route_key,
			requirement_type,
			accessory_name,
			fabric_type: requirement_type === "accessory"
				? accessory_block_label(accessory_name)
				: __("Main Fabric"),
			dia,
		};
		const weight_key = `${route_key}\u0000${colour}`;
		table_groups[table_key].weights[weight_key] =
			(table_groups[table_key].weights[weight_key] || 0) + round_weight(row.program_weight);
	});

	const tables = Object.values(table_groups).sort(
		(left, right) => left.cloth_item.localeCompare(right.cloth_item)
	).map((item) => {
		const colours = Array.from(item.colours).sort();
		const routes = Object.values(item.routes).sort((left, right) => {
			if (left.requirement_type !== right.requirement_type) {
				return left.requirement_type === "cloth" ? -1 : 1;
			}
			const fabricCompare = left.fabric_type.localeCompare(right.fabric_type);
			return fabricCompare || left.dia.localeCompare(right.dia);
		});
		const colour_totals = Object.fromEntries(colours.map((colour) => [colour, 0]));
		let cloth_total = 0;
		const fabric_groups = [];
		const fabric_groups_by_key = new Map();
		routes.forEach((route) => {
			const fabric_key = [
				route.requirement_type,
				route.requirement_type === "accessory" ? route.accessory_name : "",
			].join("\u0000");
			if (!fabric_groups_by_key.has(fabric_key)) {
				const fabric_group = {
					fabric_type: route.fabric_type,
					requirement_type: route.requirement_type,
					accessory_name: route.accessory_name,
					routes: [],
				};
				fabric_groups_by_key.set(fabric_key, fabric_group);
				fabric_groups.push(fabric_group);
			}
			fabric_groups_by_key.get(fabric_key).routes.push(route);
		});
		const body = fabric_groups.map((fabric_group) => {
			const fabric_colour_totals = Object.fromEntries(
				colours.map((colour) => [colour, 0])
			);
			let fabric_total = 0;
			const route_rows = fabric_group.routes.map((route) => {
				let dia_total = 0;
				const cells = colours.map((colour) => {
					const weight = item.weights[`${route.route_key}\u0000${colour}`] || 0;
					dia_total += weight;
					fabric_colour_totals[colour] += weight;
					colour_totals[colour] += weight;
					return `<td class="text-right">${weight ? format_weight(weight) : "—"}</td>`;
				}).join("");
				fabric_total += dia_total;
				cloth_total += dia_total;
				return `
					<tr>
						<td>${escape(route.fabric_type)}</td>
						<td>${escape(route.dia)}</td>
						${cells}
						<td class="text-right"><strong>${format_weight(dia_total)}</strong></td>
					</tr>
				`;
			}).join("");
			const fabric_colour_total_cells = colours.map(
				(colour) => `<th class="text-right">${format_weight(fabric_colour_totals[colour])}</th>`
			).join("");
			const fabric_additions = Object.fromEntries(colours.map((colour) => [
				colour,
				addition_map[addition_key(
					item.cloth_item,
					fabric_group.requirement_type,
					fabric_group.accessory_name,
					item.colour_values[colour]
				)] || 0,
			]));
			const addition_total = Object.values(fabric_additions).reduce(
				(sum, weight) => sum + weight, 0
			);
			const addition_cells = colours.map((colour) => {
				const added_weight = fabric_additions[colour];
				if (is_saved_view) {
					return `<th class="text-right">${added_weight ? `+${format_weight(added_weight)}` : "—"}</th>`;
				}
				return `
					<th style="padding: 5px;">
						<input
							type="number"
							class="form-control input-sm text-right"
							style="min-width: 82px;"
							min="0"
							step="1"
							value="${added_weight || ""}"
							data-cloth-program-addition
							data-cloth-item="${escape(item.cloth_item)}"
							data-requirement-type="${escape(fabric_group.requirement_type)}"
							data-accessory-name="${escape(fabric_group.accessory_name)}"
							data-colour="${escape(item.colour_values[colour])}"
							aria-label="${escape(__("Add Weight for {0} / {1}", [fabric_group.fabric_type, colour]))}"
						>
					</th>
				`;
			}).join("");
			const addition_row = (is_saved_view && !addition_total) ? "" : `
				<tr class="text-primary">
					<th>${is_saved_view ? __("Added Weight") : __("Add Weight")}</th>
					<th class="small text-muted">
						${is_saved_view ? __("Split across non-zero Dia rows") : __("Enter Kg and click Calculate again")}
					</th>
					${addition_cells}
					<th class="text-right">${addition_total ? `+${format_weight(addition_total)}` : "—"}</th>
				</tr>
			`;
			return `
				${route_rows}
					<tr class="active">
						<th>${escape(__("Total {0}", [fabric_group.fabric_type]))}</th>
						<th></th>
					${fabric_colour_total_cells}
					<th class="text-right">${format_weight(fabric_total)}</th>
				</tr>
				${addition_row}
			`;
		}).join("");
		const colour_total_cells = colours.map(
			(colour) => `<th class="text-right">${format_weight(colour_totals[colour])}</th>`
		).join("");

		return `
			<div style="margin-bottom: 24px;">
				<h5 style="margin-bottom: 4px;">${escape(item.cloth_item)}</h5>
				<div class="text-muted small" style="margin-bottom: 8px;">
					${__("Knitting Program Kg")}
				</div>
				<div class="table-responsive">
					<table class="table table-bordered table-hover">
						<thead>
							<tr>
								<th>${__("Fabric Type")}</th>
								<th>${uses_compacting_details ? __("Input Dia → Compacting Dia") : __("Dia")}</th>
								${colours.map((colour) => `<th class="text-right">${escape(colour)}</th>`).join("")}
								<th class="text-right">${__("Total")}</th>
							</tr>
						</thead>
						<tbody>${body}</tbody>
						<tfoot>
							<tr>
								<th>${__("Total")}</th>
								<th></th>
								${colour_total_cells}
								<th class="text-right">${format_weight(cloth_total)}</th>
							</tr>
						</tfoot>
					</table>
				</div>
			</div>
		`;
	}).join("");
	const totals = rows.reduce((result, row) => {
		const required = round_weight(row.required_weight);
		const program = round_weight(row.program_weight);
		result.required_weight += required;
		result.extra_weight += Math.max(program - required, 0);
		result.manual_additional_weight += Number(row.manual_additional_weight || 0);
		result.program_weight += program;
		return result;
	}, { required_weight: 0, extra_weight: 0, manual_additional_weight: 0, program_weight: 0 });

	const storage_message = is_saved_view
		? __("Calculated using the percentage and added weights saved on this Lot.")
		: __("The percentage and added weights are saved on this Lot; click Calculate again after editing Add Weight.");
	const print_button = is_saved_view
		? `<button type="button" class="btn btn-default btn-sm" data-action="print-cloth-program">
			${frappe.utils.icon("printer", "sm")} ${__("Print")}
		</button>`
		: "";
	$(wrapper).html(`
		<div style="margin-top: 18px;">
			<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 10px;">
				<div class="text-muted small">
					${storage_message}
					${__("Cloth Kg per 1 Kg Yarn")}: <strong>${format_number(preview.cloth_per_kg_yarn)}</strong>
					· ${__("Extra")}: <strong>${format_number(preview.extra_percentage)}%</strong>
				</div>
				${print_button}
			</div>
			${tables}
			<div class="text-right" style="margin-top: -8px;">
				<span style="margin-left: 18px;">
					${__("Required Kg")}: <strong>${format_weight(totals.required_weight)}</strong>
				</span>
					<span style="margin-left: 18px;">
						${__("Extra Kg")}: <strong>${format_weight(totals.extra_weight)}</strong>
					</span>
					<span style="margin-left: 18px;">
						${__("Added Kg")}: <strong>${format_weight(totals.manual_additional_weight)}</strong>
					</span>
				<span style="margin-left: 18px;">
					${__("Total Knitting Program Kg")}: <strong>${format_weight(totals.program_weight)}</strong>
				</span>
			</div>
		</div>
	`);
}


// frappe.ui.form.on('Lot', {
// 	setup: function(frm) {
// 		frm.set_query('lot_template', (doc) => {
// 			return {
// 				filters: {
// 					item: doc.item,
// 				}
// 			}
// 		});
// 		frm.set_query('size', 'planned_qty', (doc) => {
// 			return {
// 				filters: {
// 					attribute_name: 'Size',
// 				}
// 			}
// 		});
// 	},

// 	refresh: function(frm) {
// 		frm.page.add_menu_item(__("Calculate"), function() {
// 			calculate_all(frm);
// 		}, false, 'Ctrl+E', false);
// 		if (!frm.is_new()) {
// 			frm.add_custom_button(__('Purchase Summary'), function() {
// 				frappe.set_route("query-report", "Lot Purchase Summary", {
// 					lot: frm.doc.name
// 				});
// 			}, __("View"));
// 		}
// 	},

// 	item: function(frm) {
// 		if (frm.doc.item) {
// 			frm.set_value({"lot_template": ""});
// 			frappe.call({
// 				method: "production_api.production_api.doctype.item.item.get_attribute_values",
// 				args: {
// 					item: frm.doc.item,
// 				},
// 				callback: function(r) {
// 					if (r.message) {
// 						if (r.message['Size']) {
// 							let planned_qty = []
// 							for(let i = 0;i < r.message.Size.length; i++) {
// 								planned_qty.push({size: r.message.Size[i], qty: 0});
// 							}
// 							frm.set_value({'planned_qty': planned_qty});
// 						}
// 					}
// 				}
// 			});
// 		}
// 	},

// 	lot_template: function(frm) {
// 		if (frm.doc.lot_template) {
// 			frappe.call({
// 				method: "production_api.production_api.doctype.lot_template.lot_template.get_attribute_values",
// 				args: {
// 					lot_template: frm.doc.lot_template,
// 				},
// 				callback: function(r) {
// 					if (r.message) {
// 						if (r.message['Size']) {
// 							let planned_qty = []
// 							for(let i = 0;i < r.message.Size.length; i++) {
// 								planned_qty.push({size: r.message.Size[i], qty: 0});
// 							}
// 							frm.set_value({'planned_qty': planned_qty});
// 						}
// 					}
// 				}
// 			});
// 		}s
// 	},

// 	calculate_bom: function(frm) {
// 		if (frm.doc.item && frm.doc.lot_template && frm.doc.planned_qty.length > 0) {
// 			frappe.call({
// 				method: "production_api.production_api.doctype.lot_template.lot_template.get_calculated_bom",
// 				args: {
// 					lot_template: frm.doc.lot_template,
// 					planned_qty: frm.doc.planned_qty,
// 				},
// 				callback: function(r) {
// 					console.log(r.message);
// 					if (r.message) {
// 						if (r.message['items']) {
// 							let items = r.message.items || [];
// 							for (let i = 0; i < items.length; i++) {
// 								let bom = frm.doc.bom_summary;
// 								let found = false;
// 								for (let j = 0; j < bom.length; j++) {
// 									if (bom[j].item_name == items[i].item) {
// 										bom[j].required_qty = items[i].required_qty;
// 										found = true;
// 										break;
// 									}
// 								}
// 								if (!found) {
// 									var childTable = frm.add_child("bom_summary");
// 									childTable.item_name = items[i].item;
// 									childTable.required_qty = items[i].required_qty;
// 								}
// 							}
// 							frm.refresh_field('bom_summary');
// 						}
// 					}
// 				}
// 			});
// 		}
// 	}
// });

// frappe.ui.form.on('Lot Planned Qty', {
// 	qty: function(frm, cdt, cdn) {
// 		let row = frappe.get_doc(cdt, cdn)
// 		row.qty = parseInt(row.qty);
// 		calculate_all(frm);
// 	},
// 	cut_qty: function(frm, cdt, cdn) {
// 		let row = frappe.get_doc(cdt, cdn)
// 		row.cut_qty = parseInt(row.cut_qty);
// 		calculate_all(frm);
// 	},
// 	final_qty: function(frm, cdt, cdn) {
// 		let row = frappe.get_doc(cdt, cdn)
// 		row.final_qty = parseInt(row.final_qty);
// 		calculate_all(frm);
// 	},
// });

// function calculate_all(frm) {
// 	calculate_planned_qty(frm);
// 	frm.refresh_field("total_planned_qty")
// 	frm.refresh_field("total_final_qty")
// 	frm.refresh_field("total_cutting_qty")
// 	frm.dirty();
// }

// function calculate_planned_qty(frm) {
// 	let total_qty = 0, total_cut_qty = 0, total_final_qty = 0;
// 	$.each(frm.doc.planned_qty || [], function(i, v) {
// 		total_cut_qty += (v.cut_qty || 0)
// 		total_qty += (v.qty || 0);
// 		total_final_qty += (v.final_qty || 0);
//     })
// 	frm.doc.total_planned_qty = total_qty;
// 	frm.doc.total_final_qty = total_final_qty;
// 	frm.doc.total_cutting_qty = total_cut_qty;
// }

// ---------------------------------------------------------------------------
// Update Colour (Split/Convert, Remove, Add) — see
// docs/lot-colour-update-implementation-plan.md
// ---------------------------------------------------------------------------

function open_colour_update_dialog(frm) {
	frappe.call({
		method: "production_api.essdee_production.doctype.lot.colour_update.get_colour_update_context",
		args: { lot: frm.doc.name },
		freeze: true,
		freeze_message: __("Loading colour configuration..."),
		callback(r) {
			if (!r.message) return;
			const ctx = r.message;
			if (ctx.blockers && (ctx.blockers.submitted_work_orders || ctx.blockers.laysheets)) {
				show_colour_update_blockers(ctx.blockers);
			}
			build_colour_update_dialog(frm, ctx);
		},
	});
}

function show_colour_update_blockers(blockers) {
	const parts = [];
	if (blockers.submitted_work_orders && blockers.submitted_work_orders.length) {
		parts.push(
			__("Submitted Work Orders") + ":<br>" +
			blockers.submitted_work_orders
				.map(name => `<a href="/app/work-order/${encodeURIComponent(name)}">${frappe.utils.escape_html(name)}</a>`)
				.join("<br>")
		);
	}
	if (blockers.laysheets && blockers.laysheets.length) {
		parts.push(
			__("Non-cancelled LaySheets containing the source colour") + ":<br>" +
			blockers.laysheets
				.map(name => `<a href="/app/cutting-laysheet/${encodeURIComponent(name)}">${frappe.utils.escape_html(name)}</a>`)
				.join("<br>")
		);
	}
	if (parts.length) {
		frappe.msgprint({
			title: __("Colour Update Blockers"),
			message: parts.join("<br><br>"),
			indicator: "red",
		});
	}
}

function colour_update_esc(value) {
	return frappe.utils.escape_html(value == null ? "" : String(value));
}

function colour_update_options(options, selected) {
	return ["<option value=''></option>"]
		.concat(
			(options || []).map(
				option =>
					`<option value="${colour_update_esc(option)}" ${option === selected ? "selected" : ""}>${colour_update_esc(option)}</option>`
			)
		)
		.join("");
}

function build_colour_update_dialog(frm, ctx) {
	const state = {
		operation: "split_convert",
		source_colour: null,
		targets: [],
		reference_colour: null,
		process_cost_values: {},
		manual_packing_rows: null,
	};

	const colours = ctx.colours.map(c => c.colour);
	const configured = new Set(colours);
	const available = (ctx.available_colours || []).filter(c => !configured.has(c));
	const packing = ctx.requirements.packing;
	const setReq = ctx.requirements.set_item;
	const stitchReq = ctx.requirements.stitching;
	const cuttingReq = ctx.requirements.cutting;
	const clothReq = ctx.requirements.cloth;
	const needsReference =
		ctx.requirements.has_colour_dependent_accessory_mappings
		|| ctx.requirements.has_colour_dependent_bom_mappings
		|| (ctx.process_costs || []).length > 0;

	function source_colour_obj() {
		return ctx.colours.find(c => c.colour === state.source_colour) || null;
	}

	function default_target() {
		return {
			colour: "",
			size_quantities: {},
			packing_quantity: 0,
			set_or_stitching_mapping: { set: {}, stitch: {} },
			cutting_rows: [],
			cloth_rows: [],
		};
	}

	function target_colour_options(target) {
		// Split/Convert may merge into another colour already configured in the
		// IPD, and the source may appear once to retain part of its quantity.
		// Add remains limited to colours not configured in the IPD.
		const options =
			state.operation === "add"
				? available.slice()
				: (ctx.available_colours || []).slice();
		const selectedElsewhere = new Set(
			state.targets.filter(t => t !== target).map(t => t.colour).filter(Boolean)
		);
		return options.filter(option => !selectedElsewhere.has(option));
	}

	function alloc_summary() {
		const source = source_colour_obj();
		if (!source) return [];
		return ctx.sizes.map(size => {
			const allocated = state.targets.reduce(
				(sum, target) => sum + flt((target.size_quantities || {})[size]),
				0
			);
			const current = flt((source.size_quantities || {})[size]);
			return { size, allocated, current };
		});
	}

	function render_quantity_matrix() {
		const wrapper = $(dialog.fields_dict.qty_matrix.wrapper);
		if (state.operation === "remove") {
			const source = source_colour_obj();
			if (!source) { wrapper.html(`<p class="text-muted">${__("Select a source colour.")}</p>`); return; }
			const rows = ctx.sizes.map(size => `
				<tr><td>${colour_update_esc(size)}</td><td class="text-right">${colour_update_esc(source.size_quantities[size] || 0)}</td></tr>
			`).join("");
			wrapper.html(`
				<h5>${__("Quantities removed")} — ${colour_update_esc(source.colour)}</h5>
				<table class="table table-bordered">
					<thead><tr><th>${__("Size")}</th><th class="text-right">${__("Quantity")}</th></tr></thead>
					<tbody>${rows}
					<tr class="info"><td><strong>${__("New total")}</strong></td>
					<td class="text-right"><strong>${colour_update_esc(flt(ctx.total_order_quantity) - flt(source.total))}</strong></td></tr></tbody>
				</table>
			`);
			return;
		}
		if (!state.targets.length) {
			wrapper.html(`<p class="text-muted">${__("Add at least one target colour.")}</p>`);
			return;
		}
		const source = source_colour_obj();
		const header = ctx.sizes.map(size => `<th class="text-right">${colour_update_esc(size)}</th>`).join("");
		const rows = state.targets
			.map((target, index) => {
				const cells = ctx.sizes
					.map(size => {
						const value = (target.size_quantities || {})[size] || "";
						return `<td><input type="number" min="0" step="any" class="form-control input-xs cu-qty"
							data-target="${index}" data-size="${colour_update_esc(size)}" value="${value}"></td>`;
					})
					.join("");
				const removeBtn =
					state.operation === "split_convert" && state.targets.length > 1
						? `<button class="btn btn-xs btn-default cu-remove-target" data-target="${index}">${__("Remove")}</button>`
						: "";
				const colourInput =
					state.operation === "add"
						? `<select class="form-control input-xs cu-target-colour" data-target="0">${colour_update_options(
								target_colour_options(target), target.colour
						  )}</select>`
						: `<select class="form-control input-xs cu-target-colour" data-target="${index}">${colour_update_options(
								target_colour_options(target), target.colour
						  )}</select>`;
				return `<tr>
					<td style="min-width:160px">${colourInput}</td>
					${cells}
					<td>${removeBtn}</td>
				</tr>`;
			})
			.join("");
		let footer = "";
		if (state.operation === "split_convert" && source) {
			const summary = alloc_summary();
			footer = `<tr class="warning">
				<td><strong>${__("Source current")}</strong></td>
				${summary.map(s => `<td class="text-right">${colour_update_esc(s.current)}</td>`).join("")}
				<td></td></tr>
			<tr class="cu-allocated-row">
				<td><strong>${__("Requested target total")}</strong></td>
				${summary.map(s => `<td class="text-right">${colour_update_esc(roundNumber(s.allocated, 3))}</td>`).join("")}
				<td></td></tr>`;
		}
		$(dialog.fields_dict.qty_matrix.wrapper).html(`
			<h5>${state.operation === "add" ? __("Size-wise quantities for the new colour") : __("Size-wise target quantities")}</h5>
			<table class="table table-bordered cu-matrix">
				<thead><tr><th>${__("Colour")}</th>${header}<th></th></tr></thead>
				<tbody>${rows}${footer}</tbody>
			</table>
			${state.operation === "split_convert" ? `<button class="btn btn-xs btn-default cu-add-target">${__("Add Target Colour")}</button>` : ""}
		`);
	}

	function render_packing_section() {
		const wrapper = $(dialog.fields_dict.packing_section.wrapper);
		if (packing.auto_calculate || packing.based_on_other_attribute_mapping) {
			wrapper.html(
				`<p class="text-muted">${__("Packing ratios are calculated automatically for this IPD.")}</p>`
			);
			return;
		}
		if (state.operation === "remove") {
			wrapper.html("");
			return;
		}
		const finalColours = colours
			.filter(c => state.operation !== "split_convert" || c !== state.source_colour)
			.concat(
				state.targets
					.filter(target =>
						target.colour !== state.source_colour ||
						Object.values(target.size_quantities || {}).some(quantity => flt(quantity) > 0)
					)
					.map(target => target.colour)
					.filter(Boolean)
			)
			.filter((colour, index, list) => list.indexOf(colour) === index);
		const currentRows = state.manual_packing_rows || [];
		state.manual_packing_rows = finalColours.map(colour => {
			const current = currentRows.find(row => row.attribute_value === colour);
			const existing = (packing.current_rows || []).find(row => row.attribute_value === colour);
			return {
				attribute_value: colour,
				quantity: current ? current.quantity : existing ? existing.quantity : 0,
			};
		});
		const total = state.manual_packing_rows.reduce((sum, row) => sum + flt(row.quantity), 0);
		const balanced = Math.abs(total - flt(packing.packing_combo)) < 1e-6;
		wrapper.html(`
			<h5>${__("Rebalanced Packing Ratios")} (${__("must sum to")} ${colour_update_esc(packing.packing_combo)})</h5>
			<table class="table table-bordered">
				<thead><tr><th>${__("Colour")}</th><th class="text-right">${__("Quantity")}</th></tr></thead>
				<tbody>
					${state.manual_packing_rows
						.map(
							(row, index) => {
								const editable =
									state.operation === "add" ||
									row.attribute_value === state.source_colour ||
									state.targets.some(target => target.colour === row.attribute_value);
								return `<tr><td>${colour_update_esc(row.attribute_value)}</td>
							<td><input type="number" min="0" step="any" class="form-control input-xs cu-packing-qty"
								data-row="${index}" value="${row.quantity}" ${editable ? "" : "readonly"}></td></tr>`;
							}
						)
						.join("")}
					<tr class="${balanced ? "success" : "danger"}">
						<td><strong>${__("Total")}</strong></td>
						<td class="text-right"><strong>${colour_update_esc(roundNumber(total, 3))}</strong></td>
					</tr>
				</tbody>
			</table>
		`);
	}

	function render_stitching_section() {
		const wrapper = $(dialog.fields_dict.stitching_section.wrapper);
		if (state.operation !== "add") { wrapper.html(""); return; }
		const parts = [];
		const target = state.targets[0] || default_target();
		target.set_or_stitching_mapping = target.set_or_stitching_mapping || { set: {}, stitch: {} };
		target.set_or_stitching_mapping.set = target.set_or_stitching_mapping.set || {};
		target.set_or_stitching_mapping.stitch = target.set_or_stitching_mapping.stitch || {};
		const mapping = target.set_or_stitching_mapping;
		if (setReq) {
			parts.push(`<h6>${__("Set part colours")} (${colour_update_esc(setReq.set_item_attribute)})</h6>`);
			parts.push(
				(setReq.parts || [])
					.map(part => `
						<div class="col-md-4" style="padding:4px">
							<label class="control-label">${colour_update_esc(part)}</label>
							<select class="form-control input-xs cu-set-mapping" data-part="${colour_update_esc(part)}">
								${colour_update_options(available.concat(colours), mapping.set[part])}
							</select>
						</div>`).join("")
			);
		}
		if (stitchReq.is_same_packing_attribute) {
			parts.push(
				`<p class="text-muted" style="clear:both">${__("Stitching colour follows the new packing colour automatically (same attribute).")}</p>`
			);
			wrapper.html(`<div class="row">${parts.join("")}</div><div style="clear:both"></div>`);
			return;
		}
		parts.push(`<h6 style="clear:both">${__("Stitching colour mapping")} (${__("Major Colour")} → ${__("Stitching Colour")})</h6>`);
		parts.push(
			(stitchReq.stitching_parts || [])
				.map(part => `
					<div class="col-md-4" style="padding:4px">
						<label class="control-label">${colour_update_esc(part)}</label>
						<select class="form-control input-xs cu-stitch-mapping" data-part="${colour_update_esc(part)}">
							${colour_update_options(available.concat(colours), mapping.stitch[part])}
						</select>
					</div>`).join("")
		);
		wrapper.html(`<div class="row">${parts.join("")}</div><div style="clear:both"></div>`);
	}

	function combination_label(combination) {
		const label = Object.keys(combination || {})
			.map(key => `${key}: ${combination[key] == null ? "" : combination[key]}`)
			.join(" / ");
		return label || __("Default");
	}

	function render_cutting_section() {
		const wrapper = $(dialog.fields_dict.cutting_section.wrapper);
		if (state.operation !== "add" || !cuttingReq.uses_colour) { wrapper.html(""); return; }
		const target = state.targets[0] || default_target();
		const rows = target.cutting_rows || [];
		const html = (cuttingReq.combinations || [])
			.map((combination, index) => {
				let existing = rows.find(
					row => row.__combination === index
				);
				if (!existing) {
					existing = Object.assign({}, combination, { Dia: "", Weight: "" });
					rows.push(Object.assign(existing, { __combination: index }));
				}
				return `<tr>
					<td>${colour_update_esc(combination_label(combination))}</td>
					<td style="min-width:140px"><select class="form-control input-xs cu-cutting-dia" data-row="${index}">
						${colour_update_options(cuttingReq.dia_options, existing.Dia)}</select></td>
					<td><input type="number" min="0" step="any" class="form-control input-xs cu-cutting-weight" data-row="${index}" value="${existing.Weight}"></td>
				</tr>`;
			})
			.join("");
		wrapper.html(`
			<h5>${__("Cutting configuration for the new colour")}</h5>
			<table class="table table-bordered">
				<thead><tr><th>${__("Combination")}</th><th>${__("Dia")}</th><th>${__("Weight")}</th></tr></thead>
				<tbody>${html || `<tr><td colspan="3" class="text-muted">${__("No cutting inputs required.")}</td></tr>`}</tbody>
			</table>
		`);
	}

	function render_cloth_section() {
		const wrapper = $(dialog.fields_dict.cloth_section.wrapper);
		if (state.operation !== "add" || !clothReq.uses_colour) { wrapper.html(""); return; }
		const target = state.targets[0] || default_target();
		const rows = target.cloth_rows || [];
		const clothOptions = (clothReq.select_lists && clothReq.select_lists.Cloth) || [];
		const html = (clothReq.combinations || [])
			.map((combination, index) => {
				let existing = rows.find(row => row.__combination === index);
				if (!existing) {
					existing = Object.assign({}, combination, { Cloth: "" });
					rows.push(Object.assign(existing, { __combination: index }));
				}
				return `<tr>
					<td>${colour_update_esc(combination_label(combination))}</td>
					<td style="min-width:180px"><select class="form-control input-xs cu-cloth-select" data-row="${index}">
						${colour_update_options(clothOptions, existing.Cloth)}</select></td>
				</tr>`;
			})
			.join("");
		wrapper.html(`
			<h5>${__("Cloth mapping for the new colour")}</h5>
			<table class="table table-bordered">
				<thead><tr><th>${__("Combination")}</th><th>${__("Cloth")}</th></tr></thead>
				<tbody>${html || `<tr><td colspan="2" class="text-muted">${__("No cloth inputs required.")}</td></tr>`}</tbody>
			</table>
		`);
	}

	function render_process_cost_section() {
		const wrapper = $(dialog.fields_dict.process_cost_section.wrapper);
		if (state.operation !== "add" || !(ctx.process_costs || []).length) { wrapper.html(""); return; }
		const reference = state.reference_colour;
		const target = (state.targets[0] || {}).colour;
		const rows = ctx.process_costs
			.map(pc => {
				const refValue = (pc.values || []).find(v => v.attribute_value === reference);
				const adjusted = (state.process_cost_values[pc.name] || {});
				const price = adjusted.price != null ? adjusted.price : refValue ? refValue.price : "";
				const minOrderQty = adjusted.min_order_qty != null ? adjusted.min_order_qty : refValue ? refValue.min_order_qty : "";
				return `<tr>
					<td>${colour_update_esc(pc.process_name)} ${pc.docstatus === 1 ? `<span class="text-muted">(${__("Submitted — a draft replacement will be created")})</span>` : ""}</td>
					<td><input type="number" min="0" step="any" class="form-control input-xs cu-pc-price" data-pc="${colour_update_esc(pc.name)}" value="${price}"></td>
					<td><input type="number" min="0" step="any" class="form-control input-xs cu-pc-min-qty" data-pc="${colour_update_esc(pc.name)}" value="${minOrderQty}"></td>
				</tr>`;
			})
			.join("");
		wrapper.html(`
			<h5>${__("Process Cost values for the new colour")}</h5>
			<table class="table table-bordered">
				<thead><tr><th>${__("Process")}</th><th>${__("Price")}</th><th>${__("Min Order Qty")}</th></tr></thead>
				<tbody>${rows}</tbody>
			</table>
		`);
	}

	function render_shared_section() {
		const wrapper = $(dialog.fields_dict.shared_section.wrapper);
		if (!ctx.shared_ipd.is_shared) { wrapper.html(""); return; }
		wrapper.html(`
			<div class="alert alert-warning">
				<strong>${__("This IPD is shared by other Lots")}:</strong>
				${ctx.shared_ipd.linked_lots.map(l => colour_update_esc(l)).join(", ")}<br>
				${__("Confirming will create a private duplicate for this Lot; the other Lots will keep the original IPD unchanged.")}
			</div>
		`);
	}

	function render_sections() {
		render_quantity_matrix();
		render_packing_section();
		render_stitching_section();
		render_cutting_section();
		render_cloth_section();
		render_process_cost_section();
		render_shared_section();
	}

	function clean_rows(rows) {
		return (rows || []).map(row => {
			const copy = Object.assign({}, row);
			delete copy.__combination;
			return copy;
		});
	}

	function cutting_rows_for_payload(target) {
		const rows = clean_rows(target.cutting_rows).map(row =>
			Object.assign({}, row, { [ctx.packing_attribute]: target.colour })
		);
		if (!ctx.requirements.panel_wise || !cuttingReq.panel_mode) return rows;
		// Panel mode: the server expects matrix cells cloned from the popup
		// matrix ({panel, row, cell}) rather than flat combination rows.
		return rows
			.map(row => ({
				panel: row[cuttingReq.panel_attribute],
				row: { primary_value: row[cuttingReq.primary_attribute] },
				cell: { dia: row.Dia, weight: row.Weight },
			}))
			.filter(cell => cell.panel);
	}

	function cloth_rows_for_payload(target) {
		const rows = clean_rows(target.cloth_rows).map(row =>
			Object.assign({}, row, { [ctx.packing_attribute]: target.colour })
		);
		if (!ctx.requirements.panel_wise || !clothReq.panel_mode) return rows;
		return rows
			.map(row => {
				const attributeValues = {};
				(clothReq.other_attributes || []).forEach(attribute => {
					attributeValues[attribute] = row[attribute];
				});
				return {
					panel: row[clothReq.panel_attribute],
					row: { attribute_values: attributeValues },
					cell: { cloth: row.Cloth },
				};
			})
			.filter(cell => cell.panel);
	}

	function build_payload() {
		const payload_targets =
			state.operation === "remove" ? [] : state.targets.map(target => ({
			colour: target.colour,
			size_quantities: Object.assign({}, target.size_quantities),
			packing_quantity: flt(target.packing_quantity),
			set_or_stitching_mapping: Object.assign({}, target.set_or_stitching_mapping),
			cutting_rows: cutting_rows_for_payload(target),
			cloth_rows: cloth_rows_for_payload(target),
		}));
		return {
			operation: state.operation,
			source_colour: state.operation === "add" ? null : state.source_colour,
			targets: payload_targets,
			reference_colour: state.reference_colour,
			process_cost_values: state.process_cost_values,
			manual_packing_rows: state.manual_packing_rows || [],
		};
	}

	function apply() {
		if (ctx.shared_ipd.is_shared && !dialog.get_value("confirm_shared_ipd")) {
			frappe.msgprint(__("Confirm the shared IPD duplication before applying."));
			return;
		}
		const payload = build_payload();
		frappe.call({
			method: "production_api.essdee_production.doctype.lot.colour_update.apply_colour_update",
			args: {
				lot: frm.doc.name,
				payload: JSON.stringify(payload),
				expected_lot_modified: ctx.lot_modified,
				expected_ipd_modified: ctx.ipd_modified,
				confirmed_shared_ipd: ctx.shared_ipd.is_shared ? dialog.get_value("confirm_shared_ipd") : false,
			},
			freeze: true,
			freeze_message: __("Applying colour update..."),
			callback(r) {
				dialog.hide();
				const message = r.message || {};
				frappe.show_alert({
					message: message.message || __("Colour update applied."),
					indicator: "green",
				});
				frappe.set_route("Form", "Lot", frm.doc.name);
			},
		});
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Update Colour"),
		size: "extra-large",
		fields: [
			{
				fieldname: "operation",
				label: __("Operation"),
				fieldtype: "Select",
				options: [
					{ label: __("Split / Convert Colour"), value: "split_convert" },
					{ label: __("Remove Colour"), value: "remove" },
					{ label: __("Add New Colour"), value: "add" },
				],
				default: "split_convert",
				onchange() {
					state.operation = dialog.get_value("operation");
					state.targets = [default_target()];
					state.manual_packing_rows = null;
					dialog.set_value("source_colour", null);
					if (state.operation === "add" && needsReference && !state.reference_colour) {
						state.reference_colour = colours[0] || null;
						dialog.set_value("reference_row", state.reference_colour);
					}
					$(dialog.fields_dict.source_colour.wrapper).toggle(state.operation !== "add");
					$(dialog.fields_dict.reference_row.wrapper).toggle(
						state.operation === "add" && needsReference
					);
					dialog.set_df_property(
						"reference_row",
						"reqd",
						state.operation === "add" && needsReference ? 1 : 0
					);
					render_sections();
				},
			},
			{
				fieldname: "source_colour",
				label: __("Source Colour"),
				fieldtype: "Select",
				// Frappe Select fields take an ARRAY of values — never the
				// HTML <option> string used by the custom matrix selects.
				options: [""].concat(colours),
				onchange() {
					state.source_colour = dialog.get_value("source_colour");
					state.manual_packing_rows = null;
					render_sections();
				},
			},
			{ fieldname: "matrix_break", fieldtype: "Column Break" },
			{
				fieldname: "reference_row",
				label: __("Reference Colour (for Accessory / BOM / Process Cost defaults)"),
				fieldtype: "Select",
				options: [""].concat(colours),
				onchange() {
					state.reference_colour = dialog.get_value("reference_row") || null;
					render_sections();
				},
			},
			{ fieldname: "sections_break", fieldtype: "Section Break", label: __("Quantities & Configuration") },
			{ fieldname: "qty_matrix", fieldtype: "HTML" },
			{ fieldname: "packing_section", fieldtype: "HTML" },
			{ fieldname: "stitching_section", fieldtype: "HTML" },
			{ fieldname: "cutting_section", fieldtype: "HTML" },
			{ fieldname: "cloth_section", fieldtype: "HTML" },
			{ fieldname: "process_cost_section", fieldtype: "HTML" },
			{ fieldname: "shared_section", fieldtype: "HTML" },
			{
				fieldname: "confirm_shared_ipd",
				label: __("I understand a private duplicate will be created for this Lot"),
				fieldtype: "Check",
				depends_on: `eval: ${ctx.shared_ipd.is_shared ? "true" : "false"}`,
			},
		],
		primary_action_label: __("Apply"),
		primary_action: apply,
	});

	dialog.wrapper.on("click", ".cu-add-target", () => {
		state.targets.push(default_target());
		state.manual_packing_rows = null;
		render_sections();
	});
	dialog.wrapper.on("click", ".cu-remove-target", event => {
		const index = $(event.currentTarget).data("target");
		state.targets.splice(index, 1);
		state.manual_packing_rows = null;
		render_sections();
	});
	dialog.wrapper.on("change", ".cu-target-colour", event => {
		const index = $(event.currentTarget).data("target");
		state.targets[index].colour = $(event.currentTarget).val();
		state.manual_packing_rows = null;
		render_sections();
	});
	dialog.wrapper.on("input", ".cu-qty", event => {
		const element = $(event.currentTarget);
		const target = state.targets[element.data("target")];
		if (target) {
			target.size_quantities[element.data("size")] = flt(element.val());
			if (!packing.auto_calculate && !packing.based_on_other_attribute_mapping) {
				render_packing_section();
			}
			const summary = alloc_summary();
			if (summary.length) {
				// Refresh the allocated row without a full re-render so typing is
				// not interrupted.
				const allocatedCells = dialog.wrapper.find(".cu-allocated-row td");
				allocatedCells.each((cellIndex, cell) => {
					if (cellIndex === 0 || cellIndex === summary.length + 1) return;
					const entry = summary[cellIndex - 1];
					$(cell).text(roundNumber(entry.allocated, 3));
				});
			}
		}
	});
	dialog.wrapper.on("input", ".cu-packing-qty", event => {
		const element = $(event.currentTarget);
		const row = state.manual_packing_rows[element.data("row")];
		if (row) {
			row.quantity = flt(element.val());
			render_packing_section();
		}
	});
	dialog.wrapper.on("change", ".cu-set-mapping, .cu-stitch-mapping", event => {
		const element = $(event.currentTarget);
		const part = element.data("part");
		const target = state.targets[0];
		if (target) {
			const bucket = element.hasClass("cu-set-mapping") ? "set" : "stitch";
			target.set_or_stitching_mapping[bucket][part] = element.val() || null;
		}
	});
	dialog.wrapper.on("change", ".cu-cutting-dia", event => {
		const element = $(event.currentTarget);
		const row = state.targets[0].cutting_rows[element.data("row")];
		if (row) {
			row.Dia = element.val() || null;
		}
	});
	dialog.wrapper.on("input", ".cu-cutting-weight", event => {
		const element = $(event.currentTarget);
		const row = state.targets[0].cutting_rows[element.data("row")];
		if (row) {
			row.Weight = element.val() === "" ? "" : flt(element.val());
		}
	});
	dialog.wrapper.on("change", ".cu-cloth-select", event => {
		const element = $(event.currentTarget);
		const row = state.targets[0].cloth_rows[element.data("row")];
		if (row) {
			row.Cloth = element.val() || null;
		}
	});
	dialog.wrapper.on("input", ".cu-pc-price", event => {
		const name = $(event.currentTarget).data("pc");
		if (!name) return;
		state.process_cost_values[name] = state.process_cost_values[name] || {};
		state.process_cost_values[name].price = flt($(event.currentTarget).val());
	});
	dialog.wrapper.on("input", ".cu-pc-min-qty", event => {
		const name = $(event.currentTarget).data("pc");
		if (!name) return;
		state.process_cost_values[name] = state.process_cost_values[name] || {};
		state.process_cost_values[name].min_order_qty = flt($(event.currentTarget).val());
	});

	state.targets = [default_target()];
	$(dialog.fields_dict.reference_row.wrapper).toggle(false);
	dialog.show();
	render_sections();
}
