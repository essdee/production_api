<template>
  <div ref="root">
    <table class="table table-sm table-bordered">
      <tr v-for="(i, item_index) in list_item" :key="item_index">
        <td v-if="i.primary_attribute">
          <table
            v-if="i.items && i.items.length > 0"
            class="table table-sm table-bordered"
          >
            <tr>
              <th>S.No.</th>
              <th>Item</th>
              <th v-for="(j, idx) in i.final_state_attr" :key="idx">{{ j }}</th>
              <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                {{ j }}
              </th>
              <th v-if="docstatus == 0 && t_and_a == 0">Edit</th>
            </tr>
            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
              <td :rowspan="3">{{ item1_index + 1 }}</td>
              <td :rowspan="3">{{ i.item }}</td>
              <td v-for="(k, idx) in j.attributes" :key="idx" :rowspan="3">{{ k }}</td>

              <td v-for="(k, idx) in Object.keys(j.values)" :key="'qty-' + idx">
                Qty: {{ j.values[k]['qty'] }}
              </td>
              <td :rowspan="3" v-if="docstatus == 0">
                <div
                  class="pull-left cursor-pointer"
                  @click="edit_item(item1_index)"
                  v-html="frappe.utils.icon('edit', 'md', 'mr-1')"
                ></div>
                <div
                  class="pull-left cursor-pointer"
                  @click="delete_item(item1_index)"
                  v-html="frappe.utils.icon('delete', 'md')"
                ></div>
              </td>
            </tr>
            <tr v-for="(j, item1_index) in i.items" :key="'ratio-' + item1_index">
              <td v-for="(k, idx) in Object.keys(j.values)" :key="'ratio-' + idx">
                Ratio: {{ j.values[k]['ratio'] }}
              </td>
            </tr>
            <tr v-for="(j, item1_index) in i.items" :key="'mrp-' + item1_index">
              <td v-for="(k, idx) in Object.keys(j.values)" :key="'mrp-' + idx">
                MRP: {{ j.values[k]['mrp'] }}
              </td>
            </tr>
          </table>

        </td>
        <td v-else>
          <table
            v-if="i.items && i.items.length > 0"
            class="table table-sm table-bordered"
          >
            <tr>
              <th>S.No.</th>
              <th>Item</th>
              <th v-for="(j, idx) in i.final_state_attr" :key="idx">{{ j }}</th>
              <th>Qty</th>
              <th>Ratio</th>
              <th>MRP</th>
              <th v-if='docstatus == 0'>Edit</th>
            </tr>
            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
              <td>{{ item1_index + 1 }}</td>
              <td>{{ i.item }}</td>
              <template v-if="i.final_state_attr">
                <td v-for="(k, idx) in j.attributes" :key="idx">{{ k }}</td>
              </template>
              <td>{{ j.values.qty }}</td>
              <td>{{ j.values.ratio }}</td>
              <td>{{ j.values.mrp }}</td>
              <td v-if='docstatus == 0'>
                <div
                  class="pull-left cursor-pointer"
                  @click="edit_item(item1_index)"
                  v-html="frappe.utils.icon('edit', 'md', 'mr-1')"
                ></div>
                <div
                  class="pull-left cursor-pointer"
                  @click="delete_item(item1_index)"
                  v-html="frappe.utils.icon('delete', 'md')"
                ></div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    <div>
      <div v-if='!show_parameters'>
        <button 
          class="btn btn-success" 
          @click="show_add_items()"
        >
          Fetch Item
        </button>
      </div>
    </div>

    <div>
      <form @submit.prevent>
        <div>
          <div
            class="dependent-attr row pl-4"
            style="display: flex; gap: 10px"
          ></div>
        </div>
        <div>
          <div
            class="primary-attr row pl-4"
            style="display: flex; gap: 10px"
          ></div>
          <div
            class="ratio-attr row pl-4"
            style="display: flex; gap: 10px"
          ></div>
          <div
            class="mrp-attr row pl-4"
            style="display: flex; gap: 10px"
          ></div>
        </div>
        <div>
          <div class="comment-attr col-md-5"></div>
        </div>
        <div v-if="button_show">
          <button v-if="edit" class="btn btn-success" @click="add_item()">
            Update Item
          </button>
          <button v-if="!edit" class="btn btn-success" @click="add_item()">
            Add Item
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from "vue";
const root = ref(null);
const sample_doc = ref({});
const item = ref([]);
const docstatus = ref(null);
const list_item = ref([]);
let primary_values = {};
let dependent_values = {};
let comment = {};
const edit = ref(false);
const edit_index = ref(null);
const button_show = ref(false);
const show_parameters = ref(false)
let t_and_a = ref(cur_frm.doc.lot_time_and_action_details.length)

onMounted(() => {
  docstatus.value = cur_frm.doc.docstatus;
  if(cur_frm.is_new()){
    show_parameters.value = true
  }
});

function show_add_items(){
  if(show_parameters.value == false){
    show_parameters.value = true
    create_input_fields()
  }
  else{
    make_clean()
    show_parameters.value = false
  }
}

function make_clean() {
  let el = root.value;
  $(el).find(".primary-attr").html("");
  $(el).find(".ratio-attr").html("");
  $(el).find(".mrp-attr").html("");
  $(el).find(".dependent-attr").html("");
  $(el).find(".comment-attr").html("");
}

function load_data(items) {
  make_clean();
  if (items.length == 0) {
    button_show.value = false;
    list_item.value = [];
  } else {
    list_item.value[0] = items;
    if (cur_frm.is_new()) {
      create_input_fields();
    }
  }
}

function create_input_fields() {
  let qty_params = [];
  let ratio_params = []
  let mrp_params = []
  let el = root.value;
  $(el).find(".primary-attr").html("");
  $(el).find(".ratio-attr").html("");
  button_show.value = true;
  if (list_item.value[0].primary_attribute != null && list_item.value[0].primary_attribute != "") {
    primary_values = {};
    list_item.value[0].primary_attribute_values.forEach((attr, ind) => {
      qty_params[ind] = frappe.ui.form.make_control({
        parent: $(el).find(".primary-attr"),
        df: {
          fieldtype: "Float",
          fieldname: attr,
          label: attr + " " + list_item.value[0].default_uom,
          reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
      });
      let attrs = {"qty":qty_params[ind]}
      ratio_params[ind] = frappe.ui.form.make_control({
        parent: $(el).find(".ratio-attr"),
        df: {
          fieldtype: "Float",
          fieldname: attr+'_ratio',
          label: "Ratio",
          reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
      });
      attrs['ratio'] = ratio_params[ind] 
      mrp_params[ind] = frappe.ui.form.make_control({
        parent: $(el).find(".mrp-attr"),
        df: {
          fieldtype: "Float",
          fieldname: attr+'_mrp',
          label: "MRP",
          reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
      });
      attrs['mrp'] = mrp_params[ind]
      primary_values[attr] = attrs;
      if (edit.value) {
        qty_params[ind].set_value(
          list_item.value[0].items[edit_index.value]["values"][attr]['qty']
        );
        ratio_params[ind].set_value(
          list_item.value[0].items[edit_index.value]["values"][attr]['ratio']
        )
        mrp_params[ind].set_value(
          list_item.value[0].items[edit_index.value]["values"][attr]['mrp']
        )
      }
    });
  } 
  else if (list_item.value[0].primary_attribute == null || list_item.value[0].primary_attribute == "") {
    primary_values = {};
    let qty_field = frappe.ui.form.make_control({
      parent: $(el).find(".primary-attr"),
      df: {
        fieldtype: "Float",
        fieldname: "qty",
        label: list_item.value[0].default_uom,
        reqd: true,
      },
      doc: sample_doc.value,
      render_input: true,
    });
    primary_values["qty"] = qty_field;
    let ratio_field = frappe.ui.form.make_control({
      parent: $(el).find(".ratio-attr"),
      df: {
        fieldtype: "Float",
        fieldname: 'ratio',
        label: "Ratio",
        reqd: true,
      },
      doc: sample_doc.value,
      render_input: true,
    });
    primary_values['ratio'] = ratio_field
    let mrp_field = frappe.ui.form.make_control({
      parent: $(el).find(".mrp-attr"),
      df: {
        fieldtype: "Float",
        fieldname: 'mrp',
        label: "MRP",
        reqd: true,
      },
      doc: sample_doc.value,
      render_input: true,
    });
    primary_values['mrp'] = mrp_field
    if (edit.value) {
      qty_field.set_value(
        list_item.value[0].items[edit_index.value]["values"]["qty"]
      );
      ratio_field.set_value(
        list_item.value[0].items[edit_index.value]["values"]["ratio"]
      );
      mrp_field.set_value(
        list_item.value[0].items[edit_index.value]["values"]["mrp"]
      );
    }
  }
  create_dependent_attribute();
}

function create_dependent_attribute() {
  let el = root.value;
  $(el).find(".dependent-attr").html("");
  let dep_attr = [];
  list_item.value[0]["final_state_attr"].forEach((attr, ind) => {
    dep_attr[ind] = frappe.ui.form.make_control({
      parent: $(el).find(".dependent-attr"),
      df: {
        fieldtype: "Link",
        fieldname: attr + "_value",
        options: "Item Attribute Value",
        label: attr,
        only_select: true,
        get_query: function () {
          return {
            query:
              "production_api.production_api.doctype.item.item.get_item_attribute_values",
            filters: {
              item: list_item.value[0].item,
              attribute: attr,
              production_detail: cur_frm.doc.production_detail,
            },
          };
        },
        reqd: true,
      },
      doc: sample_doc.value,
      render_input: true,
    });
    if (edit.value) {
      dep_attr[ind].set_value(
        list_item.value[0].items[edit_index.value]["attributes"][attr]
      );
    }
    dependent_values[attr] = dep_attr[ind];
  });
}

function add_item() {
  cur_frm.dirty();
  let primary = {};
  let dependent = {};
  let item = {};
  let check = true
  if (list_item.value[0].primary_attribute){
    Object.keys(primary_values).forEach((data, index) => {
      primary[data] = {
        "qty":primary_values[data]['qty'].get_value(),
        "ratio":primary_values[data]['ratio'].get_value(),
        "mrp":primary_values[data]['mrp'].get_value(),
      };
      if(primary[data]['qty'] > 0){
        check = false
      }
      // primary_values[data].set_value(0);
    });
  }
  else{
    Object.keys(primary_values).forEach((data, index) => {
      primary[data] = primary_values[data].get_value()
      if(primary[data] > 0 && data == 'qty'){
        check = false
      }
      // primary_values[data].set_value(0);
    });
  }
  
  Object.keys(dependent_values).forEach((data, index) => {
    dependent[data] = dependent_values[data].get_value();
    if (dependent[data] == null || dependent[data] == "") {
      frappe.throw("Enter value for " + data);
    }
    dependent_values[data].set_value("");
  });
  
  if(check){
    frappe.throw("Fill The Quantity")
  }

  item["attributes"] = dependent;
  item["primary_attribute"] = list_item.value[0].primary_attribute;
  item["values"] = primary;

  if (edit.value) {
    list_item.value[0].items[edit_index.value] = item;
    edit.value = false;
    edit_index.value = null;
  } else {
    if(list_item.value[0].items.length == 0){
      list_item.value[0].items.push(item);
    }
    else{
      check = {}
      for(let i = 0; i < list_item.value[0].final_state_attr.length; i++){
        check[list_item.value[0].final_state_attr[i]] = item["attributes"][list_item.value[0].final_state_attr[i]]
      }
      let pushed = false
      for(let i = 0; i < list_item.value[0].items.length; i++){
        if(deepEqual(list_item.value[0].items[i]['attributes'],check)){
          Object.keys(list_item.value[0].items[i].values).forEach(row => {
            if(list_item.value[0].primary_attribute){
              list_item.value[0].items[i].values[row]['qty'] += item['values'][row]['qty'] 
              list_item.value[0].items[i].values[row]['ratio'] = item['values'][row]['ratio']
              list_item.value[0].items[i].values[row]['mrp'] = item['values'][row]['mrp']
            }
            else{
              if (row == 'qty'){
                list_item.value[0].items[i].values[row] += item['values'][row]
              }
              else{
                list_item.value[0].items[i].values[row] = item['values'][row]
              }
            }
            pushed = true
          })
          break;
        }
      }
      if(!pushed){
        list_item.value[0].items.push(item);
      }  
    }
  }
  primary_values = {};
  dependent_values = {};
  make_clean();
  show_parameters.value = false
  button_show.value = false
}
function deepEqual(obj1, obj2) {
  if (obj1 === obj2) {
    return true;
  }

  if (typeof obj1 !== 'object' || obj1 === null || typeof obj2 !== 'object' || obj2 === null) {
    return false;
  }

  let keys1 = Object.keys(obj1);
  let keys2 = Object.keys(obj2);

  if (keys1.length !== keys2.length) {
    return false;
  }

  for (let key of keys1) {
    if (!keys2.includes(key) || !deepEqual(obj1[key], obj2[key])) {
      return false;
    }
  }

  return true;
}
function delete_item(index) {
  cur_frm.dirty();
  let len = list_item.value[0].items.length;
  let item_list = list_item.value[0].items;

  if (index == 0) {
    list_item.value[0].items = item_list.slice(1, len);
  } 
  else if (index == len - 1) {
    list_item.value[0].items = item_list.slice(0,index);
  } 
  else {
    let lis = item_list.slice(0, index);
    let lis2 = item_list.slice(index + 1, len);
    list_item.value[0].items = lis.concat(lis2);
  }
}

function edit_item(index) {
  make_clean()
  show_parameters.value = true
  edit.value = true;
  edit_index.value = index;
  create_input_fields();
}

defineExpose({
  list_item,
  load_data,
});
</script>

