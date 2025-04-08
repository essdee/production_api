<template>
    <div ref="root">
        <div class="row pb-4">
            <div class="lot-name col-md-2"></div>
            <div class="item-name col-md-3"></div>
            <div class="item-variant col-md-3"></div>
            <div class="warehouse col-md-2"></div>
            <div class="received-type col-md-2"></div>
            <button class="btn btn-success ml-3" @click="get_filters()">Generate</button>
        </div>
        <div v-if="items.length > 0 && show_table">
            <button class="btn btn-primary" @click="create_bulk_stock_entry()">Create Bulk Stock Entry</button>                            
            <table class="table table-sm table-bordered">
                <thead>
                    <tr>
                        <th>S.No</th>
                        <th>Lot</th>
                        <th>Item</th>
                        <th>Item Variant</th>
                        <th>Warehouse</th>
                        <th>Warehouse Name</th>
                        <th>Received Type</th>
                        <th>Stock Balance</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="(item, index) in items" :key="index">
                        <td style="display:flex;">
                            <div>
                                {{ index + 1 }}
                            </div>
                            <div style="padding-top:1px;padding-left:5px;">
                                <input  type="checkbox" v-model="selectedItems" :value="item">
                            </div>
                        </td>
                        <td>{{ item.lot }}</td>
                        <td>{{ item.item }}</td>
                        <td>{{ item.item_variant }}</td>
                        <td>{{ item.warehouse }}</td>
                        <td>{{ item.warehouse_name }}</td>
                        <td>{{ item.received_type }}</td>
                        <td>{{ item.actual_qty }}</td>
                        <td>
                            <button class="btn btn-success" @click="create_stock_entry(item)">Create</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

let root = ref(null);
let lot, item, item_variant, warehouse, received_type = null;
let sample_doc = ref({});
let items = ref([]);
let selectedItems = ref([]);
let show_table = ref(true);

onMounted(() => {
    let el = root.value;
    $(el).find(".lot-name").html("");
    lot = frappe.ui.form.make_control({
        parent: $(el).find(".lot-name"),
        df: {
            fieldname: "lot",
            fieldtype: "Link",
            options: "Lot",
            label: "Lot",
        },
        doc: sample_doc.value,
        render_input: true,
    });

    $(el).find(".item-name").html("");
    item = frappe.ui.form.make_control({
        parent: $(el).find(".item-name"),
        df: {
            fieldname: "item",
            fieldtype: "Link",
            options: "Item",
            label: "Item",
        },
        doc: sample_doc.value,
        render_input: true,
    });

    $(el).find(".item-variant").html("");
    item_variant = frappe.ui.form.make_control({
        parent: $(el).find(".item-variant"),
        df: {
            fieldname: "item_variant",
            fieldtype: "Link",
            options: "Item Variant",
            label: "Item Variant",
        },
        doc: sample_doc.value,
        render_input: true,
    });

    $(el).find(".warehouse").html("");
    warehouse = frappe.ui.form.make_control({
        parent: $(el).find(".warehouse"),
        df: {
            fieldname: "warehouse",
            fieldtype: "Link",
            options: "Supplier",
            label: "Warehouse",
        },
        doc: sample_doc.value,
        render_input: true,
    });

    $(el).find(".received-type").html("");
    received_type = frappe.ui.form.make_control({
        parent: $(el).find(".received-type"),
        df: {
            fieldname: "received_type",
            fieldtype: "Link",
            options: "GRN Item Type",
            label: "Received Type",
        },
        doc: sample_doc.value,
        render_input: true,
    });
});

function get_filters() {
    show_table.value = false;
    selectedItems.value = []
    frappe.call({
        method: "production_api.mrp_stock.doctype.stock_summary.stock_summary.get_stock_summary",
        args: {
            lot: lot.get_value(),
            item: item.get_value(),
            item_variant: item_variant.get_value(),
            warehouse: warehouse.get_value(),
            received_type: received_type.get_value(),
        },
        callback: function (r) {
            items.value = r.message || [];
            show_table.value = true;
        }
    });
}

function create_stock_entry(item) {
    let type_dialog = new frappe.ui.Dialog({
        title: "Select Purpose",
        fields: get_purpose_field(),
        primary_action_label: __("Create"),
        primary_action: function (values) {
            type_dialog.hide()
            let purpose = values.purpose;
            let fields = get_fields(purpose, item)
            let d = new frappe.ui.Dialog({
                title: "Create Stock Entry",
                fields: fields,
                size:"extra-large",
                primary_action_label: __("Create"),
                primary_action: function (stock_values) {
                    d.hide()
                    frappe.call({
                        method: "production_api.mrp_stock.doctype.stock_summary.stock_summary.create_stock_entry",
                        args: {
                            stock_values: stock_values
                        },
                        callback: function (r) {
                            frappe.set_route("Form", "Stock Entry", r.message)
                        }
                    })
                }
            })
            d.show()
        }
    })
    type_dialog.show()
}

function create_bulk_stock_entry(){
    if(selectedItems.value.length === 0){
        frappe.msgprint("Please select at least one item.");
        return;
    }
    let selected = selectedItems.value
    let location = selected[0]['warehouse']
    for(let i = 0 ; i < selected.length ; i++){
        let cur_location = selected[i]['warehouse']
        if(location != cur_location){
            frappe.throw("Please select Item from same location")
        }
    }
    let type_dialog = new frappe.ui.Dialog({
        title: "Select Purpose",
        fields: get_purpose_field(),
        primary_action_label: __("Create"),
        primary_action: function (values) {
            type_dialog.hide()
            let purpose = values.purpose
            let d = new frappe.ui.Dialog({
                title: "Create Stock Entry",
                fields: get_location_fields(purpose, location),
                primary_action_label: __("Create"),
                primary_action: function (location_values) {
                    d.hide()
                    frappe.call({
                        method:"production_api.mrp_stock.doctype.stock_summary.stock_summary.create_bulk_stock_entry",
                        args:{
                            locations: location_values,
                            selected_items: selected,
                            purpose: purpose,
                        },
                        callback: function(){
                            frappe.set_route("Form", "Stock Entry", r.message)
                        }
                    })
                }
            })
            d.show()
        }
    })
    type_dialog.show()
}

function get_fields(purpose, item){
    let fields = [
        { fieldname: "lot", label: __("Lot"), fieldtype: "Link", options: "Lot", read_only: 1, default: item.lot},
        { fieldname:"section_break1", fieldtype:"Section Break",},
        { fieldname: "posting_date", label: __("Posting Date"), fieldtype: "Date", read_only: 1, default: frappe.datetime.get_today()},
        { fieldname:"column_break1", fieldtype:"Column Break",},
        { fieldname: "posting_time", label: __("Posting Time"), fieldtype: "Time", read_only: 1, default: frappe.datetime.now_time()},
        { fieldname:"section_break2", fieldtype:"Section Break",},
        { fieldname: "item", label: __("Item"), fieldtype: "Link", options: "Item", read_only: 1, default: item.item},
        { fieldname:"column_break2", fieldtype:"Column Break",},
        { fieldname: "item_variant", label: __("Item Variant"), fieldtype: "Link", options: "Item Variant", read_only: 1, default: item.item_variant},
        { fieldname:"section_break3", fieldtype:"Section Break",},
    ]
    fields = fields.concat(get_location_fields(purpose, item.warehouse))
    fields = fields.concat([
        { fieldname:"section_break4", fieldtype:"Section Break"},
        { fieldname: "received_type", label: __("Received Type"), fieldtype: "Link", options: "GRN Item Type", read_only: 1, default: item.received_type},
        { fieldname:"column_break4", fieldtype:"Column Break"},
        { fieldname: "qty", label: __("Quantity"), fieldtype: "Float", reqd: 1, default: item.actual_qty},
        { fieldname:"section_break5", fieldtype:"Section Break"},
        { fieldname:"uom", fieldtype:"Data", label:"UOM", read_only:1, default:item.stock_uom},
        { fieldname:"column_break5", fieldtype:"Column Break"},
        { fieldname:"purpose", fieldtype:"Data", label:"Purpose", default: purpose, read_only:1},
    ])
    return fields
}

function get_location_fields(purpose, warehouse){
    if (purpose == "Material Receipt"){
        return [{ fieldname: "to_warehouse", label: __("To Warehouse"), fieldtype: "Link", options: "Supplier", read_only: 1, default: warehouse}]
    }
    else if (purpose == "Material Issue"){
        return [{ fieldname: "from_warehouse", label: __("From Warehouse"), fieldtype: "Link", options: "Supplier", read_only: 1, default: warehouse}]
    }
    else if (purpose == "Material Consumed"){
        return [{ fieldname: "from_warehouse", label: __("From Warehouse"), fieldtype: "Link", options: "Supplier", read_only: 1, default: warehouse}]
    }
    return [
        { fieldname: "from_warehouse", label: __("From Warehouse"), fieldtype: "Link", options: "Supplier", read_only: 1, default: warehouse},
        { fieldname:"column_break4", fieldtype:"Column Break"},
        { fieldname: "to_warehouse", label: __("To Warehouse"), fieldtype: "Link", options: "Supplier", reqd:1},
    ]
}

function get_purpose_field(){
    return [{
        fieldname: "purpose",
        label: __("Purpose"),
        fieldtype: "Select",
        options: ["Send to Warehouse", "Material Receipt","Material Issue","Material Consumed"],
        reqd:1,
    }]
}
</script>
