const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function loadWorkOrderList(selectedItems = [], responseMessage = null) {
  const actions = new Map();
  const messages = [];
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
    __: (message, values = []) =>
      values.reduce(
        (formatted, value, index) =>
          formatted.replace(`{${index}}`, String(value)),
        message,
      ),
    frappe: {
      listview_settings: {},
      confirm: (_message, onConfirm) => onConfirm(),
      msgprint: (message) => messages.push(message),
      show_alert: () => {},
      utils: {
        escape_html: (value) => String(value),
      },
      call: (options) => {
        request = options;
        options.callback({
          message:
            responseMessage ||
            {
              results: selectedItems.map((item) => ({
                work_order: item.name,
                open_status: "Close",
              })),
              failed: [],
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
    getMessages: () => messages,
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

test("Approve Close result lists every failed Work Order and its reason", () => {
  const harness = loadWorkOrderList(
    [
      { name: "WO-SUCCESS" },
      { name: "WO-GRN-FAIL" },
      { name: "WO-STOCK-FAIL" },
    ],
    {
      results: [{ work_order: "WO-SUCCESS", open_status: "Close" }],
      failed: [
        {
          work_order: "WO-GRN-FAIL",
          error: "GRN GRN-0001 is not completed",
        },
        {
          work_order: "WO-STOCK-FAIL",
          error: "Insufficient stock balance",
        },
      ],
    },
  );

  harness.actions.get("Approve Close")();

  const resultMessage = harness.getMessages()[0];
  assert.equal(typeof resultMessage, "object");
  assert.equal(resultMessage.title, "Bulk Approve Close Result");
  assert.match(resultMessage.message, /1 Work Order closed successfully/);
  assert.match(resultMessage.message, /WO-GRN-FAIL/);
  assert.match(resultMessage.message, /GRN GRN-0001 is not completed/);
  assert.match(resultMessage.message, /WO-STOCK-FAIL/);
  assert.match(resultMessage.message, /Insufficient stock balance/);
  assert.equal(harness.getRefreshCount(), 1);
});
