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
              <th v-if='docstatus == 0'>Edit</th>
            </tr>
            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
              <td>{{ item1_index + 1 }}</td>
              <td>{{ i.item }}</td>
              <td v-for="(k, idx) in j.attributes" :key="idx">{{ k }}</td>
              <td v-for="(k, idx) in j.values" :key="idx">{{ k }}</td>
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
              <th v-if='docstatus == 0'>Edit</th>
            </tr>
            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
              <td>{{ item1_index + 1 }}</td>
              <td>{{ i.item }}</td>
              <template v-if="i.final_state_attr">
                <td v-for="(k, idx) in j.attributes" :key="idx">{{ k }}</td>
              </template>
              <td>{{ j.values.qty }}</td>
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
    <div v-if="docstatus != 1 && docstatus != 2">
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

onMounted(() => {
  docstatus.value = cur_frm.doc.docstatus;
});

function make_clean() {
  let el = root.value;
  $(el).find(".primary-attr").html("");
  $(el).find(".dependent-attr").html("");
  $(el).find(".comment-attr").html("");
}

function load_data(items) {
  make_clean();
  console.log(JSON.stringify(items))
  if (items.length == 0) {
    button_show.value = false;
    list_item.value = [];
  } else {
    list_item.value[0] = items;
    if (docstatus.value != 1 && docstatus.value != 2) {
      create_input_fields();
    }
  }
}

function create_input_fields() {
  let qty_params = [];
  let el = root.value;
  $(el).find(".primary-attr").html("");
  button_show.value = true;
  if (list_item.value[0].primary_attribute != null && list_item.value[0].primary_attribute != "") {
    console.log("PRIMARY")
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
      primary_values[attr] = qty_params[ind];
      if (edit.value) {
        qty_params[ind].set_value(
          list_item.value[0].items[edit_index.value]["values"][attr]
        );
      }
    });
  } else if (list_item.value[0].primary_attribute == null || list_item.value[0].primary_attribute == "") {
    console.log("IHUGUYYYF")
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
    if (edit.value) {
      qty_field.set_value(
        list_item.value[0].items[edit_index.value]["values"]["qty"]
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
  Object.keys(primary_values).forEach((data, index) => {
    primary[data] = primary_values[data].get_value();
    primary_values[data].set_value(0);
  });
  Object.keys(dependent_values).forEach((data, index) => {
    dependent[data] = dependent_values[data].get_value();
    if (dependent[data] == null || dependent[data] == "") {
      frappe.throw("Enter value for " + data);
    }
    dependent_values[data].set_value("");
  });
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
            list_item.value[0].items[i].values[row] += item['values'][row]
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
  create_input_fields();
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
  } else if (index == len - 1) {
    list_item.value[0].items = item_list.slice(0,index);
  } else {
    let lis = item_list.slice(0, index);
    let lis2 = item_list.slice(index + 1, len);
    list_item.value[0].items = lis.concat(lis2);
  }
}

function edit_item(index) {
  edit.value = true;
  edit_index.value = index;
  create_input_fields();
}

defineExpose({
  list_item,
  load_data,
});
</script>

