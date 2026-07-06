// SD YRP Sync controls on the Spine Producer Config form.
// Thin UI over the whitelisted triggers in production_api.sd_yrp_sync — no sync
// logic lives here. Re-running any doctype (especially with "Update Sync") is the
// resync path.

const SD_YRP_METHOD = "production_api.sd_yrp_sync";

const SYNC_TYPE_OPTIONS = [
	{ label: __("Initial Sync (first_sync)"), value: "first_sync" },
	{ label: __("Update Sync (on_update)"), value: "on_update" },
];

frappe.ui.form.on("Spine Producer Config", {
	refresh(frm) {
		const group = __("SD YRP Sync");
		frm.add_custom_button(__("Sync One DocType"), () => sync_one_dialog(), group);
		frm.add_custom_button(__("Sync Ordered (choose)"), () => sync_ordered_dialog(), group);
		frm.add_custom_button(__("Sync All"), () => sync_all_dialog(), group);
	},
});

function sync_type_field(fieldname = "sync_type") {
	return {
		fieldtype: "Select",
		fieldname,
		label: __("Sync Type"),
		reqd: 1,
		default: "first_sync",
		options: SYNC_TYPE_OPTIONS.map((o) => `${o.value}`).join("\n"),
	};
}

function sync_type_label(value) {
	const match = SYNC_TYPE_OPTIONS.find((o) => o.value === value);
	return match ? match.label : value;
}

// Fetch the ordered enabled-doctype list, then hand it to the caller.
function with_sync_doctypes(callback) {
	frappe.call({
		method: `${SD_YRP_METHOD}.get_sd_yrp_sync_doctypes`,
		callback: (r) => {
			const doctypes = r.message || [];
			if (!doctypes.length) {
				frappe.msgprint(__("No DocTypes are enabled for SD YRP sync."));
				return;
			}
			callback(doctypes);
		},
	});
}

function sync_one_dialog() {
	with_sync_doctypes((doctypes) => {
		// The native filter builder, rebuilt whenever the DocType changes so its
		// fields always match the chosen doctype. get_filters() -> the same
		// [doctype, field, operator, value] rows frappe.get_all accepts.
		let filter_group = null;

		const dialog = new frappe.ui.Dialog({
			title: __("Sync One DocType"),
			fields: [
				{
					fieldtype: "Select",
					fieldname: "doctype",
					label: __("DocType"),
					reqd: 1,
					options: [""].concat(doctypes).join("\n"),
					onchange() {
						build_filters(dialog.get_value("doctype"));
					},
				},
				sync_type_field(),
				{
					fieldtype: "HTML",
					fieldname: "filter_area",
					label: __("Filters (optional)"),
				},
			],
			primary_action_label: __("Sync"),
			primary_action: (values) => {
				const filters = filter_group ? filter_group.get_filters() : [];
				dialog.hide();
				run_trigger(
					`${SD_YRP_METHOD}.trigger_initial_sync`,
					{ doctype: values.doctype, filters, event: values.sync_type },
					__("Queued {0} — {1}", [sync_type_label(values.sync_type), values.doctype])
				);
			},
		});

		// Match Frappe's own dialog pattern (widget_dialog.js / data_exporter.js):
		// parent + doctype only, no custom filter_button — FilterGroup then renders
		// its filter editor INLINE inside the wrapper (a custom button turns it into
		// a detached, mispositioned popover).
		const build_filters = (doctype) => {
			const wrapper = dialog.fields_dict.filter_area.$wrapper;
			if (filter_group) {
				filter_group.wrapper && filter_group.wrapper.empty();
				filter_group = null;
			}
			wrapper.empty();
			if (!doctype) return;
			frappe.model.with_doctype(doctype, () => {
				filter_group = new frappe.ui.FilterGroup({
					parent: wrapper,
					doctype: doctype,
					on_change: () => {},
				});
				filter_group.add_filters_to_filter_group([]);
			});
		};

		dialog.show();
	});
}

function sync_ordered_dialog() {
	with_sync_doctypes((doctypes) => {
		const dialog = new frappe.ui.Dialog({
			title: __("Sync Ordered (choose DocTypes)"),
			fields: [
				{
					fieldtype: "MultiSelectPills",
					fieldname: "doctypes",
					label: __("DocTypes"),
					reqd: 1,
					get_data: () => doctypes.map((d) => ({ value: d, label: d })),
				},
				sync_type_field(),
			],
			primary_action_label: __("Sync"),
			primary_action: (values) => {
				const chosen = values.doctypes || [];
				if (!chosen.length) {
					frappe.msgprint(__("Pick at least one DocType."));
					return;
				}
				dialog.hide();
				run_trigger(
					`${SD_YRP_METHOD}.trigger_ordered_initial_sync`,
					{ doctypes: chosen, event: values.sync_type },
					__("Queued {0} — ordered ({1} DocTypes)", [
						sync_type_label(values.sync_type),
						chosen.length,
					])
				);
			},
		});
		dialog.show();
	});
}

function sync_all_dialog() {
	const dialog = new frappe.ui.Dialog({
		title: __("Sync All DocTypes (ordered)"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p>${__(
					"This publishes <b>every</b> enabled DocType in dependency order. On a full dataset this can take a while."
				)}</p>`,
			},
			sync_type_field(),
		],
		primary_action_label: __("Sync All"),
		primary_action: (values) => {
			dialog.hide();
			run_trigger(
				`${SD_YRP_METHOD}.trigger_all_initial_sync`,
				{ event: values.sync_type },
				__("Queued {0} — all DocTypes", [sync_type_label(values.sync_type)])
			);
		},
	});
	dialog.show();
}

// Fire a trigger method and report what was queued. The triggers return the
// docnames (single) or the ordered doctype list (bulk).
function run_trigger(method, args, queued_label) {
	frappe.call({
		method,
		args,
		freeze: true,
		freeze_message: __("Queuing sync…"),
		callback: (r) => {
			const result = Array.isArray(r.message) ? r.message : [];
			// Single-doctype run that matched nothing (e.g. a filter with no hits).
			if (args.doctype && !result.length) {
				frappe.msgprint({
					title: __("SD YRP Sync"),
					indicator: "orange",
					message: __("No records matched — nothing was published for {0}.", [
						args.doctype,
					]),
				});
				return;
			}
			let detail = "";
			if (result.length) {
				detail = args.doctype
					? __(" ({0} records)", [result.length])
					: __("<br>{0}", [frappe.utils.escape_html(result.join(", "))]);
			}
			frappe.msgprint({
				title: __("SD YRP Sync"),
				indicator: "green",
				message: `${queued_label}${detail}`,
			});
		},
	});
}
