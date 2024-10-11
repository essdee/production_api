// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('FG Item Master Template', {
	setup: function(frm) {
		frm.set_query('additional_parameter_value', 'additional_parameters', (doc, cdt, cdn) => {
			let child = locals[cdt][cdn]
			if (!child.additional_parameter_key){
				frappe.throw("Set Additional Parameter Key")
			}
			return {
				filters: {
					key: child.additional_parameter_key,
				}
			}
		});
		
		frm.get_docfield('additional_parameters', 'additional_parameter_value').get_route_options_for_new_doc = (field) => {
			return {
				key: field.doc.additional_parameter_key,
			}
		};
		frm.set_query('default_unit_of_measure', (doc) => {
			return {
				filters: {
					secondary_only: 0,
				}
			}
		});
	},

	refresh: function(frm) {
		if (frm.doc.__islocal) {
			hide_field(["attribute_list_html", "dependent_attribute_details_html"]);
		} else {
			unhide_field(["attribute_list_html", "dependent_attribute_details_html"]);

			// Setting the HTML for the attribute list
			$(frm.fields_dict['attribute_list_html'].wrapper).html("");
			new frappe.production.ui.ItemAttributeList({
				wrapper: frm.fields_dict["attribute_list_html"].wrapper,
				attr_values: frm.doc.__onload["attr_list"]
			});

			// Setting the HTML for the attribute list
			$(frm.fields_dict['dependent_attribute_details_html'].wrapper).html("");
			new frappe.production.ui.ItemDependentAttributeDetail(frm.fields_dict["dependent_attribute_details_html"].wrapper);
		}
	}
});
