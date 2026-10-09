const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function loadBulkCloseController(responseMessage) {
  const messages = [];
  const alerts = [];
  let request;
  let loadCount = 0;
  let dialogHidden = false;

  const context = {
    console,
    __: (message, values = []) =>
      values.reduce(
        (formatted, value, index) =>
          formatted.replace(`{${index}}`, String(value)),
        message,
      ),
    frappe: {
      pages: { "work-order-bulk-close": {} },
      ui: {
        make_app_page: () => ({}),
      },
      call: (options) => {
        request = options;
        options.callback({ message: responseMessage });
      },
      msgprint: (message) => messages.push(message),
      show_alert: (message) => alerts.push(message),
    },
  };

  vm.createContext(context);
  const source = fs.readFileSync(
    path.join(__dirname, "work_order_bulk_close.js"),
    "utf8",
  );
  vm.runInContext(
    `${source}\nglobalThis.__WorkOrderBulkClose = WorkOrderBulkClose;`,
    context,
    { filename: "work_order_bulk_close.js" },
  );

  const controller = Object.create(context.__WorkOrderBulkClose.prototype);
  controller.selected_work_orders = new Set([
    "WO-SUCCESS",
    "WO-GRN-FAIL",
    "WO-STOCK-FAIL",
  ]);
  controller.load_work_orders = () => {
    loadCount += 1;
  };
  controller.escape_html = (value) =>
    String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");

  const primaryButton = {
    prop: () => {},
  };
  const dialog = {
    get_primary_btn: () => primaryButton,
    hide: () => {
      dialogHidden = true;
    },
  };

  return {
    controller,
    dialog,
    getAlerts: () => alerts,
    getDialogHidden: () => dialogHidden,
    getLoadCount: () => loadCount,
    getMessages: () => messages,
    getRequest: () => request,
  };
}

test("Bulk Close result lists every failed Work Order and its reason", () => {
  const harness = loadBulkCloseController({
    results: [
      { work_order: "WO-SUCCESS", open_status: "Close" },
      { work_order: "WO-REQUEST", open_status: "Close Request" },
    ],
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
  });

  harness.controller.close_work_orders(
    [
      { name: "WO-SUCCESS" },
      { name: "WO-REQUEST" },
      { name: "WO-GRN-FAIL" },
      { name: "WO-STOCK-FAIL" },
    ],
    { close_reason: "Sewing Shortage", close_remarks: "Bulk close" },
    harness.dialog,
  );

  const request = harness.getRequest();
  assert.equal(
    request.method,
    "production_api.production_api.page.work_order_bulk_close.work_order_bulk_close.close_work_orders",
  );
  assert.deepEqual(request.args.work_orders, [
    "WO-SUCCESS",
    "WO-REQUEST",
    "WO-GRN-FAIL",
    "WO-STOCK-FAIL",
  ]);

  const resultMessage = harness.getMessages()[0];
  assert.equal(typeof resultMessage, "object");
  assert.equal(resultMessage.title, "Bulk Close Result");
  assert.match(resultMessage.message, /1 Work Order closed/);
  assert.match(resultMessage.message, /1 close request submitted/);
  assert.match(resultMessage.message, /WO-GRN-FAIL/);
  assert.match(resultMessage.message, /GRN GRN-0001 is not completed/);
  assert.match(resultMessage.message, /WO-STOCK-FAIL/);
  assert.match(resultMessage.message, /Insufficient stock balance/);
  assert.equal(harness.getAlerts().length, 0);
  assert.equal(harness.getDialogHidden(), true);
  assert.equal(harness.getLoadCount(), 1);
  assert.equal(harness.controller.selected_work_orders.size, 0);
});
