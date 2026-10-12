const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");

const scriptPath = __dirname + "/production_order.js";

function loadFormScript({ currentUserName = "Current Viewer" } = {}) {
  let handlers;
  const context = {
    console,
    __: (value) => value,
    frappe: {
      ui: {
        form: {
          on(_doctype, registeredHandlers) {
            handlers = registeredHandlers;
          },
        },
      },
      user: {
        has_role: () => false,
        full_name: (user) => user || currentUserName,
      },
      datetime: {
        str_to_user: (value) => `formatted:${value}`,
      },
      utils: {
        escape_html(value) {
          return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
        },
      },
    },
  };

  vm.runInNewContext(fs.readFileSync(scriptPath, "utf8"), context, {
    filename: scriptPath,
  });
  return { handlers };
}

function makeWrapper() {
  let content = "";
  return {
    html(value) {
      if (value === undefined) return content;
      content = String(value);
      return this;
    },
  };
}

function makeForm(priceRequests) {
  const priceHistoryWrapper = makeWrapper();
  return {
    doc: {
      docstatus: 1,
      status: "Closed",
      __onload: { price_requests: priceRequests },
    },
    fields_dict: {
      ppo_price_request_html: { $wrapper: priceHistoryWrapper },
    },
    set_df_property() {},
    clear_custom_buttons() {},
    priceHistoryWrapper,
  };
}

test("refresh renders the Production Order price request history", () => {
  const { handlers } = loadFormScript();
  const frm = makeForm([
    {
      name: "PPR-2026-00064",
      status: "Approved",
      requested_by: "sharmitha.p@essdee.fit",
      requested_at: "2026-07-13 15:29:35",
      approved_by: "approver@essdee.fit",
      approved_at: "2026-07-13 16:00:00",
    },
  ]);

  handlers.refresh(frm);

  const html = frm.priceHistoryWrapper.html();
  assert.match(html, /PPR-2026-00064/);
  assert.match(html, /href="\/app\/ppo-price-request\/PPR-2026-00064"/);
  assert.match(html, /Approved/);
  assert.match(html, /sharmitha\.p@essdee\.fit/);
  assert.match(html, /formatted:2026-07-13 15:29:35/);
  assert.match(html, /approver@essdee\.fit/);
  assert.match(html, /formatted:2026-07-13 16:00:00/);
});

test("refresh shows an explicit empty state when no price requests exist", () => {
  const { handlers } = loadFormScript();
  const frm = makeForm([]);

  handlers.refresh(frm);

  assert.match(frm.priceHistoryWrapper.html(), /No price change requests/);
});

test("price request history escapes displayed values and encodes request links", () => {
  const { handlers } = loadFormScript();
  const frm = makeForm([
    {
      name: "PPR 64/evil",
      status: "<Approved>",
      requested_by: "<requester@example.com>",
      requested_at: "2026<date>",
      approved_by: "Approver & Co",
      approved_at: "2026<approved>",
    },
  ]);

  handlers.refresh(frm);

  const html = frm.priceHistoryWrapper.html();
  assert.match(html, /href="\/app\/ppo-price-request\/PPR%2064%2Fevil"/);
  assert.match(html, /&lt;Approved&gt;/);
  assert.match(html, /&lt;requester@example\.com&gt;/);
  assert.match(html, /Approver &amp; Co/);
  assert.match(html, /formatted:2026&lt;approved&gt;/);
  assert.doesNotMatch(
    html,
    /<Approved>|<requester@example\.com>|Approver & Co/
  );
});

test("missing requester data is not attributed to the current viewer", () => {
  const { handlers } = loadFormScript();
  const frm = makeForm([
    {
      name: "PPR-LEGACY",
      status: "Approved",
      requested_by: null,
      requested_at: null,
      approved_by: null,
      approved_at: null,
    },
  ]);

  handlers.refresh(frm);

  assert.doesNotMatch(frm.priceHistoryWrapper.html(), /Current Viewer/);
});
