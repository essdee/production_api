// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting Laysheet Plan", {
	refresh(frm) {
		// Optimize button
		if (frm.doc.order_details && frm.doc.order_details.length > 0
			&& frm.doc.max_plies && frm.doc.max_pieces && !frm.is_new()) {
			frm.add_custom_button(__("Optimize"), () => {
				frappe.call({
					method: "production_api.production_api.doctype.cutting_laysheet_plan.cutting_laysheet_plan.optimize",
					args: { doc_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Running all strategies..."),
					callback: function(r) {
						if (r.message) {
							frm.reload_doc();
						}
					}
				});
			}).addClass("btn-primary");
		}

		// Initialize and render the Vue component
		if (!frm.lay_plan_result) {
			// Clear wrapper and mount in the all_strategies_html field wrapper
			$(frm.fields_dict['all_strategies_html'].wrapper).empty();
			frm.lay_plan_result = new frappe.production.ui.LayPlanResult(frm.fields_dict['all_strategies_html'].wrapper);
		}

		if (frm.doc.result_json) {
			const data = JSON.parse(frm.doc.result_json);
			frm.lay_plan_result.load_data(data);
			if (frm.doc.selected_strategy) {
				frm.lay_plan_result.set_selected(frm.doc.selected_strategy);
			}
			
			// Hide the redundant fields if we have the pretty view
			frm.set_df_property('per_size_section', 'hidden', 1);
			frm.set_df_property('lay_details_section', 'hidden', 1);
			frm.set_df_property('result_section', 'hidden', 1);
		} else {
			// Clear component if no results
			frm.lay_plan_result.load_data({ results: [], failed: [] });
			
			// Show input sections
			frm.set_df_property('per_size_section', 'hidden', 0);
			frm.set_df_property('lay_details_section', 'hidden', 0);
			frm.set_df_property('result_section', 'hidden', 0);
		}
	}
});
