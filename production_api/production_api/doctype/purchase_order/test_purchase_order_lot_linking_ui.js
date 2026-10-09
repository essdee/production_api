const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const scriptPath = __dirname + "/purchase_order.js";

let handlers;
let activeDialog;
const calls = [];
const buttons = new Map();

class Dialog {
	constructor(options) {
		this.options = options;
		this.fields_dict = {
			lots: {
				df: {},
				grid: { refresh() {} },
			},
		};
		activeDialog = this;
	}
	show() {}
	hide() {}
}

const context = {
	console,
	__: (value) => value,
	$: () => ({ html() {} }),
	frappe: {
		ui: {
			form: { on(_doctype, registeredHandlers) { handlers = registeredHandlers; } },
			Dialog,
		},
		production: {
			ui: {
				PurchaseOrderItem: class {
					load_data() {}
					update_status() {}
				},
				eventBus: { $on() {} },
			},
		},
		user: { has_role: (role) => role === "Purchase User" },
		perm: { has_perm: () => false },
		db: { get_link_options() { return Promise.resolve([]); } },
		call(options) {
			calls.push(options);
			if (options.method.endsWith("get_purchase_order_lots")) {
				options.callback({ message: ["LOT-EXISTING"] });
			}
		},
		model: { get_new_doc: () => ({}) },
		meta: { get_label: () => "Supplier" },
		datetime: { nowdate: () => "2026-10-09" },
		set_route() {},
		throw(message) { throw new Error(message); },
		utils: { copy_to_clipboard() {} },
	},
};

vm.runInNewContext(fs.readFileSync(scriptPath, "utf8"), context, { filename: scriptPath });

const frm = {
	doc: {
		doctype: "Purchase Order",
		name: "PO-0012",
		docstatus: 1,
		status: "Closed",
		open_status: "Open",
		items: [],
	},
	fields_dict: { item_html: { wrapper: {} } },
	page: { btn_secondary: { hide() {} }, add_menu_item() {} },
	is_new: () => false,
	set_df_property() {},
	add_custom_button(label, action) { buttons.set(label, action); },
	dirty() {},
	reload_doc() {},
};

handlers.refresh(frm);
buttons.get("Manage Linked Lots")();

assert.deepEqual(
	JSON.parse(JSON.stringify(activeDialog.fields_dict.lots.df.data)),
	[{ lot: "LOT-EXISTING" }],
);

activeDialog.options.primary_action({
	lots: [{ lot: "LOT-ADDITIONAL" }],
	comment: "Add another lot",
});

const saveCall = calls.at(-1);
assert.equal(
	saveCall.method,
	"production_api.production_api.doctype.purchase_order.purchase_order.add_po_lot_links",
);
assert.deepEqual(JSON.parse(JSON.stringify(saveCall.args)), {
	doc_name: "PO-0012",
	lots: ["LOT-ADDITIONAL"],
	comment: "Add another lot",
});

console.log("Purchase Order linked-lot UI append behavior test passed");
