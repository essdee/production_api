<template>
  <div ref="root" class="frappe-control">
    <div v-if='against =="Work Order"'>
      <p>Pending Items</p>
    </div>
    <table v-if="docstatus !== 0" class="table table-sm table-bordered">
      <tr v-for="(i, item_index) in items1" :key="item_index">
        <td v-if="i.primary_attribute">
          <table
            class="table table-sm table-bordered"
            v-if="i.items && i.items.length > 0"
          >
            <tr>
              <th>S.No.</th>
              <th>Item</th>
              <th>Lot</th>
              <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
              <th v-for="attr in i.primary_attribute_values" :key="attr">
                {{ attr }}
              </th>
              <th>Comments</th>
            </tr>
            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
              <td>{{ item1_index + 1 }}</td>
              <td>{{ j.name }}</td>
              <td>{{ j.lot }}</td>
              <td v-for="attr in i.attributes" :key="attr">
                {{ j.attributes[attr] }}
              </td>
              <td v-for="attr in j.values" :key="attr">
                <div v-if="against == 'Purchase Order'">
                  <div v-if="attr.received">
                    {{ attr.received
                    }}<span v-if="j.default_uom">{{
                      " " + j.default_uom
                    }}</span>
                    <span v-if="attr.secondary_qty">
                      ({{ attr.secondary_received
                      }}<span v-if="j.secondary_uom">{{
                        " " + j.secondary_uom
                      }}</span
                      >)
                    </span>
                  </div>
                  <div v-else class="text-center">---</div>
                </div>
                <div v-else>
                  <div v-if='attr.qty > 0'>
                    {{ attr.qty}}
                    <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                  </div>
                  <div v-else> -- </div>
                </div>
              </td>
              <td>{{ j.comments }}</td>
            </tr>
          </table>
        </td>
        <td v-else>
          <table
            class="table table-sm table-bordered"
            v-if="i.items && i.items.length > 0"
          >
            <tr>
              <th>S.No.</th>
              <th>Item</th>
              <th>Lot</th>
              <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
              <th>Received Quantity</th>
              <th>Comments</th>
            </tr>
            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
              <td>{{ item1_index + 1 }}</td>
              <td>{{ j.name }}</td>
              <td>{{ j.lot }}</td>
              <td v-for="attr in i.attributes" :key="attr">
                {{ j.attributes[attr] }}
              </td>
              <td v-if="against == 'Purchase Order'">
                {{ j.values["default"].received
                }}<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                <span v-if="j.values['default'].secondary_received">
                  <br />
                  ({{ j.values["default"].secondary_received
                  }}<span v-if="j.secondary_uom">{{
                    " " + j.secondary_uom
                  }}</span
                  >)
                </span>
              </td>
              <td v-else>
                <div v-if='j.values["default"].qty > 0'>
                  {{ j.values["default"].qty}}
                <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                </div>
                <div v-else> -- </div>
                
              </td>
              <td>{{ j.comments }}</td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    <table v-else-if="against_id" class="table table-sm table-bordered">
      <tr v-for="(i, item_index) in items1" :key="item_index">
        <td v-if="i.primary_attribute">
          <table
            class="table table-sm table-bordered"
            v-if="i.items && i.items.length > 0"
          >
            <tr>
              <th>S.No.</th>
              <th>Item</th>
              <th>Lot</th>
              <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
              <th v-for="attr in i.primary_attribute_values" :key="attr">
                {{ attr }}
              </th>
              <th>Comments</th>
              <th v-if="against == 'Work Order'">Edit</th>
            </tr>
            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
              <td>{{ item1_index + 1 }}</td>
              <td>{{ j.name }}</td>
              <td>{{ j.lot }}</td>
              <td v-for="attr in i.attributes" :key="attr">
                {{ j.attributes[attr] }}
              </td>
              <td v-for="attr in j.values" :key="attr">
                <div v-if="attr.qty">
                  {{ attr.qty
                  }}<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                  <span v-if="attr.secondary_qty">
                    ({{ attr.secondary_qty
                    }}<span v-if="j.secondary_uom">{{
                      " " + j.secondary_uom
                    }}</span
                    >)
                  </span>

                  <form v-if="against == 'Purchase Order'">
                    <input
                      class="form-control"
                      type="number"
                      v-model.number="attr.received"
                      @blur="update_received_qty(attr, 'received')"
                      min="0"
                      step="0.001"
                    />
                    <!-- <input
                      class="form-control"
                      v-if="attr.secondary_qty"
                      type="number"
                      v-model.number="attr.secondary_received"
                      @blur="update_received_qty(attr, 'secondary_received')"
                      min="0"
                      step="0.001"
                    /> -->
                  </form>
                </div>

                <div v-else class="text-center">---</div>
              </td>
              <td>
                <input class="form-control" type="text" v-model="j.comments" />
              </td>
              <td v-if="against == 'Work Order'">
                <div
                  class="pull-right cursor-pointer"
                  @click="edit_item(item_index, item1_index)"
                  v-html="frappe.utils.icon('edit', 'md', 'mr-1')"
                ></div>
              </td>
            </tr>
          </table>
        </td>
        <td v-else>
          <table
            class="table table-sm table-bordered"
            v-if="i.items && i.items.length > 0"
          >
            <tr>
              <th>S.No.</th>
              <th>Item</th>
              <th>Lot</th>
              <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
              <th>Pending Quantity</th>
              <th v-if="against == 'Purchase Order'">Received Quantity</th>
              <th>Comments</th>
              <th v-if="against == 'Work Order'">Edit</th>
            </tr>
            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
              <td>{{ item1_index + 1 }}</td>
              <td>{{ j.name }}</td>
              <td>{{ j.lot }}</td>
              <td v-for="attr in i.attributes" :key="attr">
                {{ j.attributes[attr] }}
              </td>
              <td v-if="against == 'Purchase Order'">
                {{ j.values["default"].pending_qty
                }}<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                <span v-if="j.values['default'].secondary_qty">
                  <br />
                  ({{ j.values["default"].secondary_qty
                  }}<span v-if="j.secondary_uom">{{
                    " " + j.secondary_uom
                  }}</span
                  >)
                </span>
              </td>
              <td v-else>
                {{ j.values["default"].qty
                }}<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                <span v-if="j.values['default'].secondary_qty">
                  <br />
                  ({{ j.values["default"].secondary_qty
                  }}<span v-if="j.secondary_uom">{{
                    " " + j.secondary_uom
                  }}</span
                  >)
                </span>
              </td>
              <td v-if="against == 'Purchase Order'">
                <form>
                  <input
                    class="form-control"
                    type="number"
                    v-model.number="j.values['default'].received"
                    step="0.001"
                    @blur="update_received_qty(j.values['default'], 'received')"
                    min="0"
                  />
                  <!-- <input
                    class="form-control"
                    v-if="j.values['default'].secondary_qty"
                    type="number"
                    min="0"
                    step="0.001"
                    v-model.number="j.values['default'].secondary_received"
                    @blur="
                      update_received_qty(
                        j.values['default'],
                        'secondary_received'
                      )
                    "
                  /> -->
                </form>
              </td>
              <td>
                <input class="form-control" type="text" v-model="j.comments" />
              </td>
              <td v-if="against == 'Work Order'">
                <div
                  class="pull-right cursor-pointer"
                  @click="edit_item(item_index, item1_index)"
                  v-html="frappe.utils.icon('edit', 'md', 'mr-1')"
                ></div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    <div v-if='against =="Work Order"'>
      <p>Delivered Items</p>
    </div>
    <table class="table table-sm table-bordered" v-if='against =="Work Order"'>
      <tr v-for="(i, item_index) in items" :key="item_index">
        <td v-if="i.primary_attribute && i.created === 1">
          <table
            class="table table-sm table-bordered"
            v-if="i.items && i.items.length > 0"
          >
            <thead>
              <tr>
                <th>S.No.</th>
                <th>Item</th>
                <th>Lot</th>
                <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                <th>Type</th>
                <th v-for="attr in i.primary_attribute_values" :key="attr">
                  {{ attr }}
                </th>
                <th>Comments</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(j, item1_index) in i.items" :key='item1_index'>
                <template v-if="i.created && j.created">
                  <tr v-for='m in j.types' :key='m'>
                    <td>{{ get_index(item_index) }}</td>
                    <td>{{ j.name }}</td>
                    <td>{{ j.lot }}</td>
                    <td v-for="attr in i.attributes" :key="attr">
                      {{ j.attributes[attr] }}
                    </td>
                    <td>{{m}}</td>
                    <template v-for="attr in Object.keys(j.values)">
                      <template v-if="j.values[attr].qty == 0" :key='attr'>
                        <td>--</td>
                      </template>
                      <template v-else>
                        <template v-for="v in j.values[attr]['val']" :key='v'>
                          <td v-if="v['received_type'] == m">{{v["received_quantity"]}}</td>
                        </template>
                      </template>
                    </template>
                    <td>{{ j.comments }}</td>
                  </tr>
                </template>  
              </template>
            </tbody>
          </table>
        </td>
        <td v-else>
          <table
            class="table table-sm table-bordered"
            v-if="i.items && i.items.length > 0 && i.created === 1"
          >
            <thead>
              <tr>
                <th>S.No.</th>
                <th>Item</th>
                <th>Lot</th>
                <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                <th>Type</th>
                <th>Quantity</th>
                <th>Comments</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(j, item1_index) in i.items" :key='item1_index'>
                  <template v-if="i.created && j.created">
                    <tr v-for='m in j.types' :key='m'>
                      <td>{{ get_index(item_index) }}</td>
                      <td>{{ j.name }}</td>
                      <td>{{ j.lot }}</td>
                      <td v-for="attr in i.attributes" :key="attr">
                        {{ j.attributes[attr] }}
                      </td>
                      <td>{{m}}</td>
                      <template v-for="attr in Object.keys(j.values)">
                        <template v-if="j.values[attr].qty == 0">
                          --
                        </template>
                        <template v-else>
                          <template v-for="v in j.values[attr]['val']" :key='v'>
                            <td v-if="v['received_type'] == m">{{v["received_quantity"]}}</td>
                          </template>
                        </template>
                      </template>
                      <td>{{ j.comments }}</td>
                    </tr>
                  </template>  
                </template>
            </tbody>
          </table>
        </td>
      </tr>
    </table>
    <div class="html-container">
      <div class="row">
        <div class="lot-name col-md-5"></div>
        <div class="item-name col-md-5"></div>
      </div>
      <div class="row">
        <div class="attributes col-md-5"></div>
        <div class="attributes-right col-md-5"></div>
      </div>
      <div class="row">
        <div class="type-parameters col-md-5"></div>
      </div>
      <div>
        <div
          class="qty-parameters row p-4"
          style="display: flex; gap: 10px"
        ></div>
      </div>
      <div v-if="show_button">
        <button class="btn btn-success pull-left" @click="add_item()">
          Add Item
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import EventBus from "../../bus";

import { ref, onMounted, computed, watch } from "vue";
const root = ref(null);
let i = 0;
const docstatus = ref(0);
const items = ref([]);
const items1 = ref([])
const supplier = ref(null);
const against = ref(null);
const against_id = ref(null);
let _skip_watch = false;
const attribute_values = ref([]);
const qty_attributes = ref([]);
const edit_index = ref(-1);
const edit_index1 = ref(-1);
const cur_item = ref(null);
const cur_lot = ref(null);
let lot_input = null;
let item_input = null;
const sample_doc = ref({});
const controlRefs = ref({
  quantities: [],
});
const show_button = ref(false);
let types = null;
let qty_parameters = [];
let indexes = [];

function get_index(idx) {
  if (!indexes.includes(idx)) {
    indexes.push(idx);
    i = 0;
  }
  i = i + 1;
  return i;
}

function edit_item(index, index1) {
  let el = root.value;
  controlRefs.value.quantities = [];
  edit_index.value = index;
  edit_index1.value = index1;
  attribute_values.value = [];
  qty_attributes.value = [];
  cur_item.value = null;
  cur_lot.value = null;
  show_button.value = true;
  $(el).find(".qty-parameters").html("");
  let row = items1.value[index].items[index1];
  let data1 = row.values;
  let data2 = row.attributes;
  cur_item.value = row.name;
  cur_lot.value = row.lot;
  Object.keys(data1).forEach((key) => {
    const qty = data1[key].qty;
    qty_attributes.value.push({ [key]: qty });
  });
  Object.keys(data2).forEach((key) => {
    const attr = data2[key];
    attribute_values.value.push({ [key]: attr });
  });
  create_attributes(
    attribute_values.value,
    qty_attributes.value,
    cur_item.value,
    cur_lot.value,
    index,
    index1
  );
}

function getControlValues(refs) {
  const values = [];
  refs.forEach((control) => {
    const value = control.get_value();
    values.push(value);
    control.set_value(0);
  });
  return values;
}

function create_attributes(attributes, quantities, item, lot, idx, idx1) {
  let el = root.value;
  $(el).find(".lot-name").html("");
  let lot_input = frappe.ui.form.make_control({
    parent: $(el).find(".lot-name"),
    df: {
      fieldtype: "Data",
      fieldname: "lot",
      label: "Lot",
      default: lot,
      reqd: true,
    },
    doc: sample_doc.value,
    render_input: true,
  });
  lot_input.set_value(lot);
  lot_input.df.read_only = 1;
  lot_input.refresh();
  $(el).find(".item-name").html("");
  let item_input = frappe.ui.form.make_control({
    parent: $(el).find(".item-name"),
    df: {
      fieldtype: "Data",
      fieldname: "item",
      label: "Item",
      default: item,
      reqd: true,
    },
    doc: sample_doc.value,
    render_input: true,
  });
  item_input.set_value(item);
  item_input.df.read_only = 1;
  item_input.refresh();
  $(el).find(".attributes").html("");
  $(el).find(".attributes-right").html("");

  let attribute_parameters = [];
  attributes.forEach((row, id) => {
    let classname = "";
    Object.keys(row).forEach((key, index) => {
      if (id % 2 == 0) {
        classname += ".attributes";
      } else {
        classname += ".attributes-right";
      }
      attribute_parameters[index] = frappe.ui.form.make_control({
        parent: $(el).find(classname),
        df: {
          fieldtype: "Data",
          fieldname: key + "_parameter",
          label: key,
          reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
      });
      attribute_parameters[index].set_value(row[key]);
      attribute_parameters[index].df.read_only = 1;
      attribute_parameters[index].refresh();
    });
  });
  $(el).find(".type-parameters").html("");
  types = frappe.ui.form.make_control({
    parent: $(el).find(".type-parameters"),
    df: {
      fieldtype: "Link",
      fieldname: "types",
      label: "Type",
      options: "GRN Item Type",
      onchange: () => {
        const selectedValue = types.get_value();
        if (selectedValue !== "" && selectedValue !== null) {
          handleQtyParameters(quantities, selectedValue);
        } else {
          $(el).find(".qty-parameters").html("");
        }
      },
      reqd: true,
    },
    doc: sample_doc.value,
    render_input: true,
  });
  types.set_value("");
  types.refresh();
}
// Function to handle creation of quantity parameter controls
function handleQtyParameters(quantities, value) {
  controlRefs.value.quantities = [];
  let el = root.value;
  $(el).find(".qty-parameters").html("");
  qty_parameters = [];
  quantities.forEach((row, idx) => {
    Object.keys(row).forEach((key, index) => {
      let x = key;
      if (key == "default") {
        key = "Qty";
      }
      qty_parameters[idx] = frappe.ui.form.make_control({
        parent: $(el).find(".qty-parameters"),
        df: {
          fieldtype: "Float",
          fieldname: key + "_" + value,
          label: key + " - " + row[x],
        },
        doc: sample_doc.value,
        render_input: true,
      });
      controlRefs.value.quantities.push(qty_parameters[idx]);
    });
  });
}

function add_item() {
  if(items.value.length == 0){
    items.value = items1.value
    get_items_structure()
  }
  let data = getControlValues(controlRefs.value.quantities);
  console.log(data)
  let x = 0;
  controlRefs.value.quantities = [];
  let type_selected = types.get_value();
  if(items.value[edit_index.value].items[edit_index1.value]['types'].indexOf(type_selected) == -1){
    items.value[edit_index.value].items[edit_index1.value]['types'].push(type_selected)
  }
  // items.value[edit_index.value].items[edit_index1.value]
  Object.keys(
    items.value[edit_index.value].items[edit_index1.value].values
  ).forEach((row, index) => {
    let bool = true
    items.value[edit_index.value].items[edit_index1.value]["values"][row]['val'].forEach((dict,idx)=> {
      if(dict['received_type'] == type_selected){
        dict['received_quantity'] += data[x]
        bool = false
      }
    })
    if(bool){
      items.value[edit_index.value].items[edit_index1.value]["values"][row]['val'].push({
        'received_type':type_selected,
        'received_quantity':data[x]
      })
    }
    x = x + 1;
  });
  items.value[edit_index.value]["created"] = 1;
  items.value[edit_index.value].items[edit_index1.value]["created"] = 1;
  make_clean()
}

function make_clean(){
  let el = root.value;
  $(el).find(".qty-parameters").html("");
  $(el).find(".type-parameters").html("");
  $(el).find(".attributes").html("");
  $(el).find(".attributes-right").html("");
  $(el).find(".lot-name").html("");
  $(el).find(".item-name").html("");
  show_button.value = false;
}

onMounted(() => {
  console.log("new-grn-item mounted");
  EventBus.$on("update_grn_details", (data) => {
    load_data(data);
  });
});

function load_data(data, skip_watch = false) {
  if (data) {
    // Only update the values which are present in the data object
    // let keys = ['supplier', 'against', 'against_id', 'docstatus', 'items']
    // for (let key in keys) {
    //     if (data.hasOwnProperty(key)) {
    //         this[key] = data[key];
    //     }
    // }

    if (data.hasOwnProperty("supplier")) {
      supplier.value = data["supplier"];
    }
    if (data.hasOwnProperty("against")) {
      against.value = data["against"];
    }
    if (data.hasOwnProperty("against_id")) {
      against_id.value = data["against_id"];
    }
    if (data.hasOwnProperty("docstatus")) {
      docstatus.value = data["docstatus"];
    }
    if (data.hasOwnProperty("items")) {
      if(against.value == "Purchase Order"){
        items1.value = data["items"];
      }
      else{
        items.value = data["items"];
      }
    }
    if (data.hasOwnProperty("pending_items")) {
      items1.value = data["pending_items"];
    }
    if (data.hasOwnProperty("against_id") && !skip_watch) {
      against_id_changed();
    }
    if (data.hasOwnProperty("items")) {
      _skip_watch = skip_watch;
    }
  }
}

function update_status() {
  docstatus.value = cur_frm.doc.docstatus;
}

function get_purchase_order_items() {
  frappe.call({
    method:
      "production_api.production_api.doctype.purchase_order.purchase_order.get_purchase_order_items",
    args: {
      purchase_order: against_id.value,
    },
    callback: function (r) {
      if (r.message) {
        items.value = r.message;
        items1.value = r.message;
      }
    },
  });
}
function get_work_order_items() {
  frappe.call({
    method:
      "production_api.production_api.doctype.work_order.work_order.get_work_order_items",
    args: {
      work_order: against_id.value,
    },
    callback: function (r) {
      if (r.message) {
        items.value = r.message;
        items1.value = r.message
        get_items_structure()
      }
    },
  });
}

function get_items_structure(){
  for(let i = 0 ; i < items.value.length; i++){
    for(let j = 0 ; j < items.value[i]['items'].length; j++){
      items.value[i]['items'][j]['types'] = []
      Object.keys(items.value[i].items[j].values).forEach((key, val)=> {
        items.value[i].items[j].values[key]['val'] = []
      })
    }
  }
}

function clear_items() {
  items.value = [];
}

function against_id_changed() {
  if (against_id.value) {
    if (against.value == "Purchase Order") {
      get_purchase_order_items();
    } else {
      get_work_order_items();
    }
  } else {
    clear_items();
  }
}

function get_items() {
  // Parse the received values to 0 if it is empty or null
  for (let i in items.value) {
    for (let j in items.value[i].items) {
      for (let k in items.value[i].items[j].values) {
        if (
          items.value[i].items[j].values[k].received == null ||
          items.value[i].items[j].values[k].received == ""
        ) {
          items.value[i].items[j].values[k].received = 0;
        }
        if (
          items.value[i].items[j].values[k].received_quantity == null ||
          items.value[i].items[j].values[k].received_quantity == ""
        ) {
          items.value[i].items[j].values[k].received_quantity = 0;
        }
        if (
          items.value[i].items[j].values[k].rework_details == null ||
          items.value[i].items[j].values[k].rework_details == ""
        ) {
          items.value[i].items[j].values[k].rework_details = "";
        }
        if (
          items.value[i].items[j].values[k].secondary_received == null ||
          items.value[i].items[j].values[k].secondary_received == ""
        ) {
          items.value[i].items[j].values[k].secondary_received = 0;
        }
      }
    }
  }
  if(against.value == 'Purchase Order'){
    return items1.value
  }
  return [items.value, items1.value];
}
function update_reworks(item, key) {
  item[key] = item[key];
}
function update_received_qty(item, key) {
  item[key] = parseFloat(parseFloat(item[key]).toFixed(3));
  cur_frm.dirty()
}

watch(
  items,
  (newVal, oldVal) => {
    console.log("Item Updated", _skip_watch);
    if (_skip_watch) {
      _skip_watch = false;
      return;
    }
    EventBus.$emit("grn_updated", true);
  },
  { deep: true }
);

defineExpose({
  items,
  load_data,
  update_status,
  get_items,
});
</script>
