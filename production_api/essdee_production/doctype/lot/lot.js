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
		}
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
				label: __("Extra Percentage"),
				fieldname: "extra_percentage",
				fieldtype: "Float",
				default: 0,
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
				frappe.msgprint(__("Extra Percentage cannot be negative."));
				return;
			}
			frappe.call({
				method: "production_api.essdee_production.doctype.lot.cloth_program.get_cloth_program_preview",
				args: {
					lot: frm.doc.name,
					extra_percentage: extra_percentage,
				},
				freeze: true,
				freeze_message: __("Calculating cloth program..."),
				callback(r) {
					render_cloth_program_preview(dialog, r.message || {});
				},
			});
		},
	});
	dialog.show();
	render_cloth_program_preview(dialog, {});
}

function render_cloth_program_preview(dialog, preview) {
	const rows = preview.rows || [];
	const result_field = dialog.fields_dict.cloth_program_result;
	if (!rows.length) {
		$(result_field.wrapper).html(`
			<div class="text-muted" style="padding: 18px 0;">
				${__("Enter the extra percentage and click Calculate. No data will be saved.")}
			</div>
		`);
		return;
	}

	const escape = (value) => frappe.utils.escape_html(String(value ?? ""));
	const ceil_weight = (value) => Math.ceil(Number(value || 0));
	const format_weight = (value) => ceil_weight(value).toLocaleString();
	const accessory_block_label = (value) => {
		const label = String(value || __("Accessory"))
			.trim()
			.replace(/\s+/g, " ")
			.replace(/\b\w/g, (letter) => letter.toUpperCase());
		return /\bFabric$/i.test(label) ? label : `${label} Fabric`;
	};
	const uses_compacting_details = Boolean(preview.uses_compacting_details);
	const table_groups = {};
	rows.forEach((row) => {
		const cloth_item = row.cloth_item || __("Unspecified Cloth");
		const requirement_type = row.requirement_type === "accessory" ? "accessory" : "cloth";
		const accessory_name = row.accessory_name || __("Accessory");
		const table_key = [cloth_item, requirement_type, accessory_name].join("\u0000");
		const colour = row.colour || __("No Colour");
		const dia = row.compacting_dia
			? `${row.input_dia || __("No Dia")} → ${row.compacting_dia || __("No Dia")}`
			: (row.dia || __("No Dia"));
		if (!table_groups[table_key]) {
			table_groups[table_key] = {
				cloth_item,
				requirement_type,
				accessory_name,
				colours: new Set(),
				dias: new Set(),
				weights: {},
			};
		}
		table_groups[table_key].colours.add(colour);
		table_groups[table_key].dias.add(dia);
		table_groups[table_key].weights[`${dia}\u0000${colour}`] = ceil_weight(row.program_weight);
	});

	const tables = Object.values(table_groups).sort((left, right) => {
		const clothCompare = left.cloth_item.localeCompare(right.cloth_item);
		if (clothCompare) return clothCompare;
		if (left.requirement_type !== right.requirement_type) {
			return left.requirement_type === "cloth" ? -1 : 1;
		}
		return left.accessory_name.localeCompare(right.accessory_name);
	}).map((item) => {
		const accessory_label = accessory_block_label(item.accessory_name);
		const colours = Array.from(item.colours).sort();
		const dias = Array.from(item.dias).sort();
		const colour_totals = Object.fromEntries(colours.map((colour) => [colour, 0]));
		let cloth_total = 0;
		const body = dias.map((dia) => {
			let dia_total = 0;
			const cells = colours.map((colour) => {
				const weight = item.weights[`${dia}\u0000${colour}`] || 0;
				dia_total += weight;
				colour_totals[colour] += weight;
				return `<td class="text-right">${weight ? format_weight(weight) : "—"}</td>`;
			}).join("");
			cloth_total += dia_total;
			return `
				<tr>
					<td>${escape(dia)}</td>
					${cells}
					<td class="text-right"><strong>${format_weight(dia_total)}</strong></td>
				</tr>
			`;
		}).join("");
		const colour_total_cells = colours.map(
			(colour) => `<th class="text-right">${format_weight(colour_totals[colour])}</th>`
		).join("");

		return `
			<div style="margin-bottom: 24px;">
				<h5 style="margin-bottom: 4px;">${escape(item.cloth_item)}</h5>
				${item.requirement_type === "accessory" ? `
					<div style="display: block; margin: 8px 0; padding: 8px 10px;
						border-left: 3px solid var(--primary); background: var(--subtle-fg);
						font-weight: 700;">
						${escape(accessory_label)}
					</div>
				` : `
					<div class="text-muted small" style="margin-bottom: 8px;">
						${__("Main Fabric")} · ${__("Knitting Program Kg")}
					</div>
				`}
				<div class="table-responsive">
					<table class="table table-bordered table-hover">
						<thead>
							<tr>
								<th>${uses_compacting_details ? __("Input Dia → Compacting Dia") : __("Dia")}</th>
								${colours.map((colour) => `<th class="text-right">${escape(colour)}</th>`).join("")}
								<th class="text-right">${__("Total")}</th>
							</tr>
						</thead>
						<tbody>${body}</tbody>
						<tfoot>
							<tr>
								<th>${__("Total")}</th>
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
		const required = ceil_weight(row.required_weight);
		const program = ceil_weight(row.program_weight);
		result.required_weight += required;
		result.extra_weight += Math.max(program - required, 0);
		result.program_weight += program;
		return result;
	}, { required_weight: 0, extra_weight: 0, program_weight: 0 });

	$(result_field.wrapper).html(`
		<div style="margin-top: 18px;">
			<div class="text-muted small" style="margin-bottom: 10px;">
				${__("Preview only — no IPD or Lot data is saved.")}
				${__("Cloth Kg per 1 Kg Yarn")}: <strong>${format_weight(preview.cloth_per_kg_yarn)}</strong>
				· ${__("Extra")}: <strong>${format_weight(preview.extra_percentage)}%</strong>
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
