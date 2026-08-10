// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

const ACTIVE_OPTIMIZATION_STATUSES = ["Queued", "Running"];
const TERMINAL_OPTIMIZATION_STATUSES = ["Completed", "Failed"];

frappe.ui.form.on("Cutting Laysheet Planner", {
	refresh(frm) {
		initialize_lay_plan_result(frm);
		render_lay_plan_result(frm);
		render_optimization_status(frm);

		const is_active = ACTIVE_OPTIMIZATION_STATUSES.includes(frm.doc.optimization_status);
		const has_inputs = frm.doc.order_details?.length
			&& frm.doc.max_plies
			&& frm.doc.max_pieces
			&& frm.doc.max_lays !== null
			&& frm.doc.max_lays !== undefined;

		if (!frm.is_new() && has_inputs && !is_active) {
			const label = frm.doc.optimization_status === "Failed"
				? __("Retry Optimization")
				: (frm.doc.result_json ? __("Re-optimize") : __("Optimize"));

			frm.add_custom_button(label, async () => {
				if (frm.is_dirty()) {
					await frm.save();
				}

				const response = await frappe.call({
					method: "production_api.production_api.doctype.cutting_laysheet_planner.cutting_laysheet_planner.optimize",
					args: { doc_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Queueing lay optimization..."),
				});

				if (response.message?.status === "Queued") {
					frappe.show_alert({
						message: __("Lay optimization queued on the long worker."),
						indicator: "blue",
					});
					await frm.reload_doc();
				}
			}).addClass("btn-primary");
		}

		if (is_active) {
			start_optimization_polling(frm);
		} else {
			stop_optimization_polling(frm);
		}

		frm.set_df_property("per_size_section", "hidden", 1);
		frm.set_df_property("lay_details_section", "hidden", 1);
		frm.set_df_property("result_section", "hidden", 1);
		frm.set_df_property("selected_strategy", "hidden", 1);
	},
});


function initialize_lay_plan_result(frm) {
	if (frm.lay_plan_result) {
		return;
	}

	const wrapper = frm.fields_dict.all_strategies_html?.wrapper;
	if (!wrapper) {
		return;
	}

	$(wrapper).empty();
	frm.lay_plan_result = new frappe.production.ui.LayPlanResult(
		wrapper,
		(strategy) => persist_selected_strategy(frm, strategy),
	);
}


function render_lay_plan_result(frm) {
	if (!frm.lay_plan_result) {
		return;
	}

	let data = { results: [], failed: [] };
	if (frm.doc.result_json) {
		try {
			data = JSON.parse(frm.doc.result_json);
		} catch (error) {
			console.error("Unable to parse Cutting Laysheet Planner results", error);
			data = {
				results: [],
				failed: [],
				error_message: __("Stored optimization results could not be read."),
			};
		}
	}

	data.optimization_status = frm.doc.optimization_status || "Not Started";
	data.error_message = frm.doc.optimization_error || data.error_message || "";
	frm.lay_plan_result.load_data(data);

	if (frm.doc.selected_strategy) {
		frm.lay_plan_result.set_selected(frm.doc.selected_strategy);
	}
}


function render_optimization_status(frm) {
	const status = frm.doc.optimization_status || "Not Started";
	const messages = {
		"Queued": [__("Lay optimization is queued on the long worker."), "blue"],
		"Running": [__("Lay optimization is running. This form will refresh automatically."), "orange"],
		"Completed": [__("Lay optimization completed successfully."), "green"],
		"Failed": [frm.doc.optimization_error || __("Lay optimization failed."), "red"],
	};

	if (messages[status]) {
		frm.set_intro(messages[status][0], messages[status][1]);
	} else {
		frm.set_intro("");
	}
}


async function persist_selected_strategy(frm, strategy) {
	await frappe.call({
		method: "production_api.production_api.doctype.cutting_laysheet_planner.cutting_laysheet_planner.select_strategy",
		args: {
			doc_name: frm.doc.name,
			strategy,
		},
		freeze: true,
		freeze_message: __("Saving selected strategy..."),
	});

	frm.doc.selected_strategy = strategy;
	frm.lay_plan_result?.set_selected(strategy);
	await frm.reload_doc();
}


function start_optimization_polling(frm) {
	if (frm.__lay_optimization_polling) {
		return;
	}

	const doc_name = frm.doc.name;
	frm.__lay_optimization_polling = true;

	const schedule = (delay = 2000) => {
		if (!frm.__lay_optimization_polling) {
			return;
		}
		frm.__lay_optimization_timer = setTimeout(poll, delay);
	};

	const poll = async () => {
		if (
			!frm.__lay_optimization_polling
			|| frm.doc.name !== doc_name
			|| (window.cur_frm && window.cur_frm !== frm)
		) {
			stop_optimization_polling(frm);
			return;
		}

		try {
			const response = await frappe.call({
				method: "production_api.production_api.doctype.cutting_laysheet_planner.cutting_laysheet_planner.get_optimization_status",
				args: { doc_name },
			});
			const status = response.message?.status || "Not Started";

			if (TERMINAL_OPTIMIZATION_STATUSES.includes(status)) {
				stop_optimization_polling(frm);
				await frm.reload_doc();
				return;
			}

			frm.doc.optimization_status = status;
			frm.doc.optimization_error = response.message?.error_message || "";
			frm.refresh_field("optimization_status");
			render_lay_plan_result(frm);
			render_optimization_status(frm);
			schedule();
		} catch (error) {
			console.warn("Lay optimization status check failed", error);
			schedule(5000);
		}
	};

	schedule(1000);
}


function stop_optimization_polling(frm) {
	frm.__lay_optimization_polling = false;
	if (frm.__lay_optimization_timer) {
		clearTimeout(frm.__lay_optimization_timer);
		frm.__lay_optimization_timer = null;
	}
}
