// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting Order", {
	setup(frm) {
		frm.trigger("declarations");

		frm.set_query('attribute_value', 'attribute_values', () => {
			if (!frm.doc.packing_attribute) {
				frappe.throw("Please select the packing attribute first");
			}
			return {
				query: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.set_packing_attr_map_value,
				}
			};
		});

		frm.set_query('stiching_attribute_value', 'stiching_item_details', () => {
			return {
				query: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.stiching_attribute_mapping,
				}
			};
		});

		frm.set_query('major_panel_value', () => {
			return {
				query: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.stiching_attribute_mapping,
				}
			};
		});

		frm.set_query('set_item_attribute_value', 'stiching_item_details', () => {
			return {
				query: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.set_item_attr_map_value,
				}
			};
		});

		frm.set_query('dia', 'cloth_detail', () => {
			return { filters: { 'attribute_name': 'Dia' } };
		});

		frm.set_query('major_attribute_value', () => {
			if (!frm.doc.set_item_attribute) {
				frappe.throw("Please set the Set Attribute Item");
			}
			return {
				query: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.set_item_attr_map_value,
				}
			};
		});
	},

	declarations(frm) {
		frm.set_packing_attr_map_value = null;
		frm.set_item_attr_map_value = null;
		frm.stiching_attribute_mapping = null;

		for (let i = 0; i < frm.doc.item_attributes.length; i++) {
			if (frm.doc.item_attributes[i].attribute == frm.doc.packing_attribute) {
				frm.set_packing_attr_map_value = frm.doc.item_attributes[i].mapping;
			}
			if (frm.doc.item_attributes[i].attribute == frm.doc.set_item_attribute) {
				frm.set_item_attr_map_value = frm.doc.item_attributes[i].mapping;
			}
			if (frm.doc.item_attributes[i].attribute == frm.doc.stiching_attribute) {
				frm.stiching_attribute_mapping = frm.doc.item_attributes[i].mapping;
			}
		}
	},

	refresh(frm) {
		frm.trigger('declarations');
		frm.trigger('onload_post_render');

		// Item Attribute List widget
		$(frm.fields_dict['item_attribute_list_values_html'].wrapper).html("");
		if (!frm.doc.__islocal && frm.doc.__onload && frm.doc.__onload["attr_list"]) {
			new frappe.production.ui.ItemAttributeList({
				wrapper: frm.fields_dict["item_attribute_list_values_html"].wrapper,
				attr_values: frm.doc.__onload["attr_list"]
			});
		}

		// Set Item combination
		$(frm.fields_dict['set_items_html'].wrapper).html("");
		if (!frm.doc.__islocal) {
			if (!frm.doc.is_set_item) {
				hide_field('set_items_html');
			} else {
				unhide_field('set_items_html');
				frm.trigger('make_set_combination');
			}
		}

		// Stitching combination
		$(frm.fields_dict['stiching_items_html'].wrapper).html("");

		frm.trigger('make_hide_and_unhide_tabs');
	},

	async make_set_combination(frm) {
		$(frm.fields_dict['set_items_html'].wrapper).html("");
		frm.set_item = new frappe.production.ui.CombinationItemDetail(frm.fields_dict['set_items_html'].wrapper);
		if (frm.doc.__onload && frm.doc.__onload.set_item_detail) {
			frm.doc['set_item_detail'] = JSON.stringify(frm.doc.__onload.set_item_detail);
			await frm.set_item.load_data(frm.doc.__onload.set_item_detail);
			frm.set_item.set_attributes();
		}
	},

	async make_stiching_combination(frm) {
		$(frm.fields_dict['stiching_items_html'].wrapper).html("");
		frm.stiching_item = new frappe.production.ui.CombinationItemDetail(frm.fields_dict['stiching_items_html'].wrapper);
		if (frm.doc.__onload && frm.doc.__onload.stiching_item_detail) {
			frm.doc['stiching_item_detail'] = JSON.stringify(frm.doc.__onload.stiching_item_detail);
			await frm.stiching_item.load_data(frm.doc.__onload.stiching_item_detail);
			frm.stiching_item.set_attributes();
		}
	},

	make_hide_and_unhide_tabs(frm) {
		frm.trigger('make_stiching_combination');

		if (!frm.doc.packing_attribute) {
			frm.$wrapper.find("[data-fieldname='set_item_tab']").hide();
		} else {
			frm.$wrapper.find("[data-fieldname='set_item_tab']").show();
		}
	},

	onload_post_render(frm) {
		if (frm.fields_dict.stiching_item_details) {
			showOrHideColumns(frm, ['set_item_attribute_value', 'is_default'], 'stiching_item_details', frm.doc.is_set_item ? 0 : 1);
			updateChildTableReqd(frm, ['set_item_attribute_value', 'is_default'], 'stiching_item_details', frm.doc.is_set_item ? 1 : 0);
		}
	},

	// Button handlers
	get_colour_values(frm) {
		frappe.call({
			method: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_mapping_attribute_values',
			args: {
				attribute_mapping_value: frm.set_packing_attr_map_value,
				attribute_no: frm.doc.attribute_no,
			},
			callback: function(r) {
				if (r.message) {
					frm.set_value('attribute_values', r.message);
					frm.refresh_field('attribute_values');
				}
			}
		});
	},

	get_panel_values(frm) {
		frappe.call({
			method: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_mapping_attribute_values',
			args: {
				attribute_mapping_value: frm.stiching_attribute_mapping,
				attribute_no: null,
			},
			callback: function(r) {
				if (r.message) {
					frm.set_value('stiching_item_details', r.message);
					frm.refresh_field('stiching_item_details');
				}
			}
		});
	},

	get_set_item_combination(frm) {
		if (!frm.doc.major_attribute_value) {
			frappe.msgprint("Set the major attribute value");
			return;
		}
		frappe.call({
			method: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_new_combination',
			args: {
				attribute_mapping_value: frm.set_item_attr_map_value,
				packing_attribute_details: frm.doc.attribute_values,
				major_attribute_value: frm.doc.major_attribute_value,
			},
			callback: async function(r) {
				await frm.set_item.load_data(r.message);
				frm.set_item.set_attributes();
			}
		});
	},

	get_panel_combination(frm) {
		if (!frm.doc.stiching_attribute) {
			return;
		}
		if (!frm.doc.major_panel_value) {
			frappe.msgprint("Set the major panel value");
			return;
		}
		if (frm.doc.stiching_item_details.length == 0) {
			frappe.msgprint("Set the Panel Details");
			return;
		}
		frappe.call({
			method: 'production_api.production_api.doctype.cutting_order.cutting_order.get_co_new_combination',
			args: {
				attribute_mapping_value: frm.stiching_attribute_mapping,
				packing_attribute_details: frm.doc.attribute_values,
				major_attribute_value: frm.doc.major_panel_value,
				is_same_colour: frm.doc.is_same_colour,
				doc_name: frm.doc.name,
			},
			callback: async function(r) {
				await frm.stiching_item.load_data(r.message);
				frm.stiching_item.set_attributes();
				frm.dirty();
			}
		});
	},

	// Field change handlers
	is_set_item(frm) {
		showOrHideColumns(frm, ['set_item_attribute_value', 'is_default'], 'stiching_item_details', frm.doc.is_set_item ? 0 : 1);
		updateChildTableReqd(frm, ['set_item_attribute_value', 'is_default'], 'stiching_item_details', frm.doc.is_set_item ? 1 : 0);
	},

	major_attribute_value(frm) {
		frm.trigger('get_set_item_combination');
	},

	// Serialize Vue data before save
	validate: async function(frm) {
		if (!frm.doc.__islocal) {
			if (frm.set_item && frm.doc.is_set_item) {
				let item_details = frm.set_item.get_data();
				frm.doc['set_item_detail'] = JSON.stringify(item_details);
			}

			if (frm.stiching_item) {
				let item_details = frm.stiching_item.get_data();
				if (item_details['values'].length > 0) {
					frm.doc['stiching_item_detail'] = JSON.stringify(item_details);
				}
			}
		}
	},
});


function showOrHideColumns(frm, fields, table, hidden) {
	if (frappe.ui.form.editable_row) {
		frappe.ui.form.editable_row.toggle_editable_row(false);
	}
	let grid = frm.get_field(table).grid;
	for (let field of fields) {
		grid.fields_map[field].hidden = hidden;
	}
	grid.visible_columns = undefined;
	grid.setup_visible_columns();

	grid.header_row.wrapper.remove();
	delete grid.header_row;
	grid.make_head();

	for (let row of grid.grid_rows) {
		if (row.open_form_button) {
			row.open_form_button.parent().remove();
			delete row.open_form_button;
		}
		for (let field in row.columns) {
			if (row.columns[field] !== undefined) {
				row.columns[field].remove();
			}
		}
		for (let fieldname of fields) {
			let df = row.docfields.find(field => field.fieldname === fieldname);
			df && (df.hidden = hidden);
		}
		delete row.columns;
		row.columns = [];
		row.render_row();
	}
	frappe.ui.form.editable_row && frappe.ui.form.editable_row.toggle_editable_row(false);
}

function updateChildTableReqd(frm, fields, table, reqd) {
	let grid = frm.get_field(table).grid;
	for (let row of grid.grid_rows) {
		if (row.open_form_button) {
			row.open_form_button.parent().remove();
			delete row.open_form_button;
		}
		for (let field in row.columns) {
			if (row.columns[field] !== undefined) {
				row.columns[field].remove();
			}
		}
		for (let fieldname of fields) {
			let df = row.docfields.find(field => field.fieldname === fieldname);
			df && (df.reqd = reqd);
		}
		delete row.columns;
		row.columns = [];
		row.render_row();
	}
	frappe.ui.form.editable_row && frappe.ui.form.editable_row.toggle_editable_row(false);
}
