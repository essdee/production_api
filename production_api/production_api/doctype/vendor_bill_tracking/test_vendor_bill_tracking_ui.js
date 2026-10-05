const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const scriptPath = __dirname + "/vendor_bill_tracking.js";

function loadFormScript(roles = []) {
	let handlers;
	const calls = [];
	const confirmations = [];
	const dialogs = [];
	const context = {
		URLSearchParams,
		console,
		window: { open() {} },
		__: (value) => value,
		$: () => ({ html() {} }),
		frappe: {
			production: { ui: { SuggestedVendorBillDeliveryPerson: class {} } },
			ui: {
				form: { on(_doctype, registeredHandlers) { handlers = registeredHandlers; } },
				Dialog: class {
					constructor(options) {
						this.options = options;
						dialogs.push(this);
					}
					show() {}
					hide() {}
				},
			},
			user: { has_role: (role) => roles.includes(role) },
			confirm(message, action) {
				confirmations.push(message);
				action();
			},
			call(options) {
				calls.push(options);
				if (options.callback) options.callback({ message: true });
			},
			model: { get_new_doc: () => ({}) },
			set_route() {},
		},
	};
	vm.runInNewContext(fs.readFileSync(scriptPath, "utf8"), context, { filename: scriptPath });
	return { handlers, calls, confirmations, dialogs };
}

function makeForm(formStatus) {
	const buttons = new Map();
	let reloads = 0;
	return {
		doc: {
			name: "VBT-TEST",
			docstatus: 1,
			form_status: formStatus,
			purchase_invoice: null,
			mrp_purchase_invoice: null,
			assigned_to: null,
			vendor_bill_tracking_history: [],
		},
		fields_dict: { delivery_person_suggestion_html: { wrapper: {} } },
		page: { btn_secondary: { hide() {} } },
		is_new: () => false,
		set_query() {},
		add_custom_button(label, action) { buttons.set(label, action); },
		reload_doc() { reloads += 1; },
		buttons,
		get reloads() { return reloads; },
	};
}

async function render(status, roles) {
	const runtime = loadFormScript(roles);
	const frm = makeForm(status);
	await runtime.handlers.refresh(frm);
	return { ...runtime, frm };
}

(async () => {
	{
		const { frm, calls, confirmations } = await render("Open", ["HR User"]);
		assert.deepEqual([...frm.buttons.keys()], ["Assign", "Request for Cancel"]);
		frm.buttons.get("Request for Cancel")();
		assert.equal(confirmations.length, 1);
		assert.equal(
			calls.at(-1).method,
			"production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.request_vendor_bill_cancellation",
		);
		assert.equal(calls.at(-1).args.name, "VBT-TEST");
		assert.equal(frm.reloads, 1);
	}

	{
		const { frm, calls } = await render("Pending Approval", ["HR Manager"]);
		assert.deepEqual([...frm.buttons.keys()], ["Approve Cancel Request"]);
		frm.buttons.get("Approve Cancel Request")();
		assert.equal(
			calls.at(-1).method,
			"production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.approve_vendor_bill_cancellation",
		);
		assert.equal(frm.reloads, 1);
	}

	{
		const { frm, dialogs, calls } = await render("Cancel Request Approved", ["HR User"]);
		assert.deepEqual([...frm.buttons.keys()], ["Cancel"]);
		frm.buttons.get("Cancel")();
		assert.equal(dialogs.length, 1);
		assert.equal(dialogs[0].options.fields[0].fieldname, "cancel_reason");
		dialogs[0].options.primary_action({ cancel_reason: "duplicate bill" });
		assert.equal(
			calls.at(-1).method,
			"production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.cancel_vendor_bill",
		);
		assert.equal(calls.at(-1).args.name, "VBT-TEST");
		assert.equal(calls.at(-1).args.cancel_reason, "duplicate bill");
		assert.equal(frm.reloads, 1);
	}

	{
		const { frm } = await render("Cancel Request Approved", ["HR Manager"]);
		assert.deepEqual([...frm.buttons.keys()], []);
	}

	console.log("Vendor Bill Tracking UI behavior tests passed");
})().catch((error) => {
	console.error(error);
	process.exitCode = 1;
});
