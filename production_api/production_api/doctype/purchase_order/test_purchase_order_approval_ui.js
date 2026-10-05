const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const scriptPath = __dirname + "/purchase_order.js";

function loadFormScript({ roles = [], canCreate = false, liveRequest = null } = {}) {
	let handlers;
	const calls = [];
	const confirmations = [];
	const context = {
		console,
		__: (value) => value,
		$: () => ({ html() {}, appendTo() { return this; } }),
		frappe: {
			ui: {
				form: { on(_doctype, registeredHandlers) { handlers = registeredHandlers; } },
				Dialog: class {},
			},
			production: {
				ui: {
					PurchaseOrderItem: class {},
					DuplicatePOItemTable: class {},
					DateDialog: class {},
					eventBus: { $on() {}, $emit() {} },
				},
			},
			user: { has_role: (role) => roles.includes(role) },
			perm: { has_perm: (_doctype, _level, permission) => permission === "create" && canCreate },
			confirm(message, action) {
				confirmations.push(message);
				action();
			},
			call(options) {
				calls.push(options);
				if (!options.callback) return;
				if (options.method.endsWith("get_purchase_order_approval_state")) {
					options.callback({ message: { live_request: liveRequest } });
				} else {
					options.callback({ message: { status: "Pending" } });
				}
			},
			model: { get_new_doc: () => ({}) },
			meta: { get_label: () => "Supplier" },
			datetime: { nowdate: () => "2026-10-05" },
			set_route() {},
			throw(message) { throw new Error(message); },
			utils: { copy_to_clipboard() {} },
		},
	};
	vm.runInNewContext(fs.readFileSync(scriptPath, "utf8"), context, { filename: scriptPath });
	return { context, handlers, calls, confirmations };
}

function makeForm(status = "Pending Approval") {
	const buttons = new Map();
	let primaryHidden = 0;
	let reloads = 0;
	return {
		doc: { doctype: "Purchase Order", name: "PO-0012", docstatus: 0, status },
		page: {
			btn_primary: { hide() { primaryHidden += 1; } },
			btn_secondary: { hide() {} },
		},
		is_new: () => false,
		add_custom_button(label, action) { buttons.set(label, action); },
		reload_doc() { reloads += 1; },
		buttons,
		get primaryHidden() { return primaryHidden; },
		get reloads() { return reloads; },
	};
}

function render(options = {}, status = "Pending Approval") {
	const runtime = loadFormScript(options);
	const frm = makeForm(status);
	runtime.context.setup_purchase_order_approval_actions(frm);
	return { ...runtime, frm };
}

{
	const { frm, calls } = render({ roles: ["Purchase User"], canCreate: true });
	assert.equal(frm.primaryHidden, 1);
	assert.deepEqual([...frm.buttons.keys()], ["Send Request"]);
	assert.equal(calls[0].method, "production_api.purchase_order_approval.get_purchase_order_approval_state");
	frm.buttons.get("Send Request")();
	assert.equal(calls.at(-1).method, "production_api.purchase_order_approval.send_purchase_order_request");
	assert.equal(frm.reloads, 1);
}

{
	const { frm, calls, confirmations } = render({ roles: ["System Manager"], canCreate: true });
	assert.equal(frm.primaryHidden, 0);
	assert.deepEqual([...frm.buttons.keys()], ["Send Request", "Approve PO", "Reject PO"]);
	frm.buttons.get("Approve PO")();
	assert.equal(confirmations.length, 1);
	assert.equal(calls.at(-1).method, "production_api.purchase_order_approval.approve_purchase_order");
	frm.buttons.get("Reject PO")();
	assert.equal(confirmations.length, 2);
	assert.equal(calls.at(-1).method, "production_api.purchase_order_approval.reject_purchase_order");
	assert.equal(frm.reloads, 2);
}

{
	const { frm } = render({ roles: ["Purchase User"], canCreate: true, liveRequest: { name: "REQ-1", status: "Pending" } });
	assert.equal(frm.primaryHidden, 1);
	assert.deepEqual([...frm.buttons.keys()], []);
}

{
	const { frm, calls } = render({ roles: ["Purchase User"], canCreate: true }, "Draft");
	assert.equal(frm.primaryHidden, 0);
	assert.deepEqual([...frm.buttons.keys()], []);
	assert.equal(calls.length, 0);
}

console.log("Purchase Order approval UI behavior tests passed");
