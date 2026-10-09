const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const frappeNodeModules = path.resolve(
  __dirname,
  "../../../../../../frappe/node_modules",
);
const esbuild = require(path.join(frappeNodeModules, "esbuild"));
const vuePlugin = require(path.join(frappeNodeModules, "esbuild-plugin-vue3"));
const { createRenderer, nextTick } = require(
  path.join(frappeNodeModules, "vue"),
);

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

async function loadComponent(bus) {
  globalThis.__grnTestBus = bus;
  const virtualBusPlugin = {
    name: "grn-test-bus",
    setup(build) {
      build.onResolve({ filter: /\.\.\/\.\.\/bus$/ }, () => ({
        path: "grn-test-bus",
        namespace: "grn-test",
      }));
      build.onLoad({ filter: /.*/, namespace: "grn-test" }, () => ({
        contents: "export default globalThis.__grnTestBus;",
        loader: "js",
      }));
    },
  };
  const result = await esbuild.build({
    entryPoints: [path.join(__dirname, "GRNPurchaseOrder.vue")],
    bundle: true,
    external: ["vue"],
    format: "cjs",
    logLevel: "silent",
    nodePaths: [frappeNodeModules],
    platform: "node",
    plugins: [virtualBusPlugin, vuePlugin()],
    write: false,
  });
  const loadedModule = { exports: {} };
  const customRequire = (moduleName) => {
    if (moduleName === "vue") {
      return require(path.join(frappeNodeModules, "vue"));
    }
    return require(moduleName);
  };
  new Function(
    "require",
    "module",
    "exports",
    result.outputFiles[0].text,
  )(customRequire, loadedModule, loadedModule.exports);
  return loadedModule.exports.default;
}

function mountComponent(component) {
  const renderer = createRenderer({
    cloneNode: (node) => ({ ...node }),
    createComment: (comment) => ({ comment }),
    createElement: (type) => ({ children: [], type }),
    createText: (text) => ({ text }),
    insert(child, parent) {
      (parent.children ||= []).push(child);
      child.parent = parent;
    },
    insertStaticContent: () => [{}, {}],
    nextSibling: () => null,
    parentNode: (node) => node.parent || null,
    patchProp: () => {},
    querySelector: () => null,
    remove: () => {},
    setElementText(node, text) {
      node.text = text;
    },
    setScopeId: () => {},
    setText(node, text) {
      node.text = text;
    },
  });
  const app = renderer.createApp(component);
  const instance = app.mount({ children: [] });
  return { app, instance };
}

test("multi-lot serialization does not mutate watched editor rows", async () => {
  const bus = new TestBus();
  const component = await loadComponent(bus);
  globalThis.frappe = { call: () => {} };
  globalThis.cur_frm = { dirty: () => {}, doc: { docstatus: 0 } };
  const { app, instance } = mountComponent(component);
  const items = [
    {
      items: [
        {
          values: {
            default: {
              ref_docname: "PO-ITEM-1",
              lot_rows: [
                {
                  lot: "LOT-A",
                  received: 5,
                  secondary_received: null,
                },
                {
                  lot: "LOT-B",
                  received: null,
                  secondary_received: null,
                },
              ],
            },
          },
        },
      ],
    },
  ];
  const before = JSON.parse(JSON.stringify(items));

  instance.load_data({ items }, true);
  await nextTick();
  const serialized = instance.get_items();
  await nextTick();

  assert.deepEqual(items, before);
  assert.deepEqual(serialized[0].items[0].values.default.lot_rows, [
    { lot: "LOT-A", received: 5, secondary_received: 0 },
  ]);
  app.unmount();
});

test("unmount removes the GRN update listener", async () => {
  const bus = new TestBus();
  const component = await loadComponent(bus);
  globalThis.frappe = { call: () => {} };
  globalThis.cur_frm = { dirty: () => {}, doc: { docstatus: 0 } };
  const { app } = mountComponent(component);

  assert.equal(bus.listenerCount("update_grn_details"), 1);
  app.unmount();

  assert.equal(bus.listenerCount("update_grn_details"), 0);
});
