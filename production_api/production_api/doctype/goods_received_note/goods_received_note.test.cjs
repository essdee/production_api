const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

class TestBus {
  constructor() {
    this.listeners = new Map();
  }

  $on(eventName, callback) {
    const callbacks = this.listeners.get(eventName) || [];
    callbacks.push(callback);
    this.listeners.set(eventName, callbacks);
  }

  $off(eventName, callback) {
    const callbacks = this.listeners.get(eventName) || [];
    this.listeners.set(
      eventName,
      callbacks.filter((registered) => registered !== callback),
    );
  }

  $emit(eventName, ...args) {
    for (const callback of this.listeners.get(eventName) || []) {
      callback(...args);
    }
  }

  listenerCount(eventName) {
    return (this.listeners.get(eventName) || []).length;
  }
}

function loadGoodsReceivedNoteForm() {
  const bus = new TestBus();
  const editors = [];
  let formEvents;
  let saveCalls = 0;

  class PurchaseOrderEditor {
    constructor() {
      this.destroyCount = 0;
      editors.push(this);
    }

    destroy() {
      this.destroyCount += 1;
    }

    get_items() {
      return [];
    }

    load_data() {}

    update_status() {}
  }

  const jqueryResult = {
    css() {
      return this;
    },
    html() {
      return this;
    },
    length: 0,
  };
  const context = {
    console,
    sessionStorage: {
      getItem: () => null,
      removeItem: () => {},
    },
    $: () => jqueryResult,
    __: (message) => message,
    frappe: {
      production: {
        ui: {
          eventBus: bus,
          GRNPurchaseOrder: PurchaseOrderEditor,
        },
      },
      ui: {
        form: {
          on: (_doctype, events) => {
            formEvents = events;
          },
        },
      },
    },
  };
  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, "goods_received_note.js"), "utf8"),
    context,
    { filename: "goods_received_note.js" },
  );

  const frm = {
    doc: {
      against: "Purchase Order",
      against_id: "PO-TEST-1",
      docstatus: 0,
      includes_packing: 0,
      is_return: 0,
      supplier: "SUPPLIER-TEST",
    },
    events: {
      check_eligible_to_calculate_items: () => false,
      check_eligible_to_complete_transfer: () => false,
      check_eligible_to_create_yrp_stock_entry: () => false,
      save_item_details: () => {
        saveCalls += 1;
      },
    },
    fields_dict: {
      item_html: { wrapper: {} },
    },
    dirty: () => {},
    is_new: () => false,
    set_query: () => {},
  };

  return {
    bus,
    editors,
    formEvents,
    frm,
    getSaveCalls: () => saveCalls,
  };
}

test("refresh replaces the PO GRN editor and event handler without leaks", () => {
  const harness = loadGoodsReceivedNoteForm();

  harness.formEvents.refresh(harness.frm);
  harness.formEvents.refresh(harness.frm);

  assert.equal(harness.editors.length, 2);
  assert.equal(harness.editors[0].destroyCount, 1);
  assert.equal(harness.bus.listenerCount("grn_updated"), 1);

  harness.bus.$emit("grn_updated", true);
  assert.equal(harness.getSaveCalls(), 1);
});
