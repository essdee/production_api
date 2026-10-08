const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function loadWorkOrderList(selectedItems = []) {
  const actions = new Map();
  let request;
  let refreshCount = 0;

  const listview = {
    page: {
      fields_dict: Object.fromEntries(
        ["name", "status", "supplier", "lot", "item", "process_name"].map(
          (fieldname) => [fieldname, { df: { fieldname } }],
        ),
      ),
      page_form: {
        find: () => ({ length: 0 }),
      },
      add_action_item: (label, handler) => actions.set(label, handler),
    },
    get_checked_items: () => selectedItems,
    refresh: () => {
      refreshCount += 1;
    },
  };

  const context = {
    console,
    localStorage: {
      getItem: () => null,
      removeItem: () => {},
    },
    cur_list: {
      filter_area: {
        list_view: {
          page: {
            add_field: () => {},
          },
        },
      },
    },
    __: (message) => message,
    frappe: {
      listview_settings: {},
      confirm: (_message, onConfirm) => onConfirm(),
      msgprint: () => {},
      show_alert: () => {},
      call: (options) => {
        request = options;
        options.callback({
          message: {
            results: selectedItems.map((item) => ({
              work_order: item.name,
              open_status: "Close",
            })),
          },
        });
      },
    },
  };

  const source = fs.readFileSync(
    path.join(__dirname, "work_order_list.js"),
    "utf8",
  );
  vm.runInNewContext(source, context, { filename: "work_order_list.js" });
  context.frappe.listview_settings["Work Order"].onload(listview);

  return {
    actions,
    getRequest: () => request,
    getRefreshCount: () => refreshCount,
  };
}

test("Approve Close list action submits all selected Work Orders and refreshes", () => {
  const harness = loadWorkOrderList([
    { name: "WO-TEST-0001" },
    { name: "WO-TEST-0002" },
  ]);

  const approveClose = harness.actions.get("Approve Close");
  assert.equal(typeof approveClose, "function");

  approveClose();

  const request = harness.getRequest();
  assert.equal(
    request.method,
    "production_api.production_api.page.work_order_bulk_close.work_order_bulk_close.approve_close_requests",
  );
  assert.equal(
    JSON.stringify(request.args.work_orders),
    JSON.stringify(["WO-TEST-0001", "WO-TEST-0002"]),
  );
  assert.equal(harness.getRefreshCount(), 1);
});
