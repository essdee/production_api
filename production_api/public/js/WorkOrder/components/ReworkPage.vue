<template>
    <div ref="root" class="rework-container">
        <div class="input-row">
            <div class="lot-input col-md-3"></div>
            <div class="btn-wrapper">
                <button class="btn btn-primary" @click="get_rework_items()">Get Rework Items</button>
            </div>
        </div>
        <div v-if="items && Object.keys(items).length > 0" class="table-wrapper">
            <table class="table table-sm table-sm-bordered">
                <tr>
                    <th>Series No</th>
                    <th>Date</th>
                    <th>GRN Number</th>
                    <th>Lot</th>
                    <th>Item</th>
                    <th>Colour</th>
                    <th v-for="type in items['types']">{{ type }}</th>
                    <th>Total</th>
                </tr>
                <template v-for="(value, key) in items['report_detail']" :key="key">
                    <tr @click="toggle_row(key)">
                        <td>{{ key }}</td>
                        <td>{{ get_date(value['date']) }}</td>
                        <td>
                            <div @click="map_to_grn(value['grn_number'])" class="hover-style">{{ value['grn_number'] }}</div>
                        </td>
                        <td>{{ value['lot'] }}</td>
                        <td>{{ value['item'] }}</td>
                        <td>{{ Object.keys(value['rework_detail'])[0].split("-").slice(1).join("-") }}</td>
                        <td v-for="ty in items['types']">
                            <span v-if="ty in value['types']">{{value['types'][ty]}}</span>
                            <span v-else>0</span>
                        </td>
                        <th> {{ value['total'] }}</th>
                    </tr>
                    <tr v-if="expandedRowKey === key">
                        <td :colspan="1000" class="expanded-row-content">
                            <template v-for="(colour_data, colour) in value['rework_detail']">
                                <h4 style="padding-top:8px;">{{ colour }}</h4>
                                <table style="width:100%;">
                                    <tr>
                                        <th>Size</th>
                                        <th v-for="size in colour_data['items']">
                                            {{ size[value['size']] }}
                                        </th>
                                    </tr>
                                    <tr>
                                        <td>Total Rework</td>
                                        <td v-for="size in colour_data['items']">
                                            {{ size['rework_qty'] }}
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>Rejection</td>
                                        <th v-for="size in colour_data['items']">
                                            <input type="number" v-model="size['rejected']" @blur="update_changed(key, colour)" class="form-control"/>
                                        </th>
                                    </tr>
                                    <tr>
                                        <td>Reworked</td>
                                        <th v-for="size in colour_data['items']">
                                            <input type="number" v-model="size['rework']" @blur="update_changed(key, colour)" class="form-control"/>
                                        </th>
                                    </tr>
                                </table>
                                <div style="width:100%;display:flex;justify-content: end;margin-top: 10px;">
                                    <div style="padding-right: 10px;">
                                        <button class="btn btn-primary" @click="update_items(colour_data['items'], colour_data['changed'], 0, value['lot'])">Update Rejection Qty</button>
                                    </div>
                                    <div style="padding-right: 10px;">
                                        <button class="btn btn-primary" @click="update_rework(colour_data['items'], value['lot'])">Update Reworked Piece</button>
                                    </div>
                                    <div style="padding-right: 10px;">
                                        <button class="btn btn-primary" @click="update_items(colour_data['items'], 1, 1, value['lot'])">Complete Rework</button>
                                    </div>
                                </div>
                            </template>
                        </td>
                    </tr>
                </template>
            </table>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

let lot = null;
let root = ref(null);
let sample_doc = ref({});
let items = ref({});
let expandedRowKey = ref(null);

onMounted(() => {
    let el = root.value;

    $(el).find(".lot-input").html("");
    lot = frappe.ui.form.make_control({
        parent: $(el).find(".lot-input"),
        df: {
            fieldname: "lot",
            fieldtype: "Link",
            options: "Lot",
            label: "Lot",
        },
        doc: sample_doc.value,
        render_input: true,
    });
});

function get_rework_items() {
    frappe.call({
        method: "production_api.production_api.doctype.grn_rework_item.grn_rework_item.get_rework_items",
        args: {
            lot: lot.get_value(),
        },
        callback: function (r) {
            items.value = r.message;
        },
    });
}

function toggle_row(key) {
    expandedRowKey.value = expandedRowKey.value === key ? null : key;
}

function update_changed(name, colour){
    items.value["report_detail"][name]['rework_detail'][colour]['changed'] = 1
}

function update_items(data, changed, completed, lot){
    if(completed == 1 || completed === 1){
        let d =  new frappe.ui.Dialog({
            title: "Are you sure want to final the item",
            primary_action_label: "Yes",
            secondary_action_label: "No",
            primary_action(){
                update(data, completed, lot)
                d.hide()
            },
            secondary_action(){
                d.hide()
            } 
        })
        d.show()
    }
    else{
        if(changed == 0 || changed === 0){
            frappe.msgprint("There is nothing was changed in this row")
            return
        }
        update(data, completed, lot)
        frappe.show_alert({
            message: __("Rejection Quantity Updated"),
            indicator: "info",
        });
    }
}

function update_rework(data, lot){
    let d =  new frappe.ui.Dialog({
        title: "Are you sure want to convert to reworked",
        primary_action_label: "Yes",
        secondary_action_label: "No",
        primary_action(){
            frappe.call({
                method: "production_api.production_api.doctype.grn_rework_item.grn_rework_item.update_partial_quantity",
                args: {
                    "data": data,
                    "lot": lot
                },
                callback: function(){
                    get_rework_items()
                }
            })
            d.hide()
        },
        secondary_action(){
            d.hide()
        } 
    })
    d.show()
}

function get_date(date){
    if(date){
        let x = new Date(date)
        return x.getDate() + "-" + (x.getMonth() + 1) + "-" + x.getFullYear()
    }
}

function update(data, completed, lot){
    frappe.call({
        method: "production_api.production_api.doctype.grn_rework_item.grn_rework_item.update_rejected_quantity",
        args: {
            "rejection_data": data,
            "completed": completed,
            "lot": lot
        },
        callback: function(){
            get_rework_items()
        }
    })
}

function map_to_grn(grn){
    const url = `/app/goods-received-note/${grn}`;
    window.open(url, '_blank');
}

</script>

<style scoped>
.rework-container {
    background-color: #f8f9fa;
    border-radius: 8px;
    padding: 20px;
}

.input-row {
    display: flex;
    align-items: center;
    gap: 10px;
}

.btn-wrapper {
    padding-top: 27px;
}

.table-sm-bordered {
    width: 100%;
    border-collapse: collapse;
    background-color: #fff;
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.table-sm-bordered th,
.table-sm-bordered td {
    border: 1px solid #dee2e6;
    padding: 8px 12px;
    font-size: 14px;
}

.table-sm-bordered th {
    background-color: #f1f3f5;
    font-weight: 600;
    color: #495057;
}

.table-sm-bordered tr:not(.expanded-row-content):hover {
    background-color: #f8f9fa;
    cursor: pointer;
}

.expanded-row-content {
    background-color: #fdfdfd;
    padding: 12px 16px !important;
    font-size: 13px;
    color: #555;
    border-top: 1px solid #dee2e6;
}

.btn-primary {
    background-color: #007bff;
    border-color: #007bff;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 14px;
    transition: all 0.2s ease;
}

.btn-primary:hover {
    background-color: #0069d9;
    border-color: #0062cc;
}

.hover-style:hover{
    text-decoration: underline;
}
</style>
