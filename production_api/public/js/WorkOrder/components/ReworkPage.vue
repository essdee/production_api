<template>
    <div ref="root" class="rework-container">
        <div class="input-row">
            <div class="lot-input col-md-3"></div>
            <div class="item-input col-md-3"></div>
            <div class="colour-input col-md-3"></div>
            <div class="btn-wrapper">
                <button class="btn btn-primary" @click="get_rework_items()">Get Rework Items</button>
            </div>
            <div class="btn-wrapper">
                <button class="btn btn-primary" @click="download()">Download XL</button>
            </div>
        </div>
        <div v-if="items && Object.keys(items).length > 0" class="table-wrapper">
            <table class="table table-sm table-sm-bordered">
                <tr>
                    <th>Print</th>
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
                        <td @click="redirect_to_print(value['grn_number'])">
                            <svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" 
                                width="25px" height="25px" viewBox="0 0 32 32" xml:space="preserve">
                            <path class="blueprint_een" d="M31,10h-5V1c0-0.552-0.448-1-1-1H7C6.448,0,6,0.448,6,1v9H1c-0.552,0-1,0.448-1,1v12
                                c0,0.552,0.448,1,1,1h5v7c0,0.552,0.448,1,1,1h18c0.552,0,1-0.448,1-1v-7h5c0.552,0,1-0.448,1-1V11C32,10.448,31.552,10,31,10z M8,2
                                h16v9H8V2z M8,19h16v11H8V19z M30,22h-5v-3c0-0.552-0.448-1-1-1H8c-0.552,0-1,0.448-1,1v3H2V12h28V22z M4,14h1v1H4V14z M6,14h1v1H6
                                V14z M10,21h12v1H10V21z M10,24h12v1H10V24z M10,27h12v1H10V27z"/>
                            </svg>
                        </td>
                        <td>{{ key }}</td>
                        <td>{{ get_date(value['date']) }}</td>
                        <td>
                            <div @click="map_to_grn(value['grn_number'])" class="hover-style">{{ value['grn_number'] }}</div>
                        </td>
                        <td>{{ value['lot'] }}</td>
                        <td>{{ value['item'] }}</td>
                        <td>{{ Object.keys(value['rework_detail'])[0].split("-").slice(1).join("-") }}</td>
                        <td v-for="ty in items['types']">
                            <span v-if="ty in value['types']">
                                {{value['types'][ty] - value['rejection_detail'][ty]}}
                            </span>
                            <span v-else>0</span>
                        </td>
                        <th> {{ value['total'] - value['total_rejection'] }}</th>
                    </tr>
                    <tr v-if="expandedRowKey === key">
                        <td :colspan="1000" class="expanded-row-content">
                            <template v-for="(colour_data, colour_mistake) in value['rework_detail']">
                                <h4 style="padding-top:8px;">{{ colour_mistake }}</h4>
                                <table style="width:100%;">
                                    <tr>
                                        <th>Size</th>
                                        <th v-for="size in colour_data['items']">
                                            {{ size[value['size']] }}
                                        </th>
                                    </tr>
                                    <tr>
                                        <td>Total {{ colour_mistake.split("-")[0] }}</td>
                                        <td v-for="size in colour_data['items']">
                                            {{ size['rework_qty'] }}
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>Rejection</td>
                                        <th v-for="size in colour_data['items']">
                                            <input type="number" v-model="size['rejected']" @blur="update_changed(key, colour_mistake)" class="form-control"/>
                                        </th>
                                    </tr>
                                    <tr>
                                        <td>Reworked</td>
                                        <th v-for="size in colour_data['items']">
                                            <input type="number" v-model="size['rework']" @blur="update_changed(key, colour_mistake)" class="form-control"/>
                                        </th>
                                    </tr>
                                </table>
                                <div style="width:100%;display:flex;justify-content: end;margin-top: 10px;">
                                    <div style="padding-right: 10px;">
                                        <button class="btn btn-primary" @click="update_items(colour_data['items'], colour_data['changed'], 0, value['lot'], key, colour_mistake)">Update Rejection Qty</button>
                                    </div>
                                    <div style="padding-right: 10px;">
                                        <button class="btn btn-primary" @click="update_rework(colour_data['items'], value['lot'], key, colour_mistake)">Update Reworked Piece</button>
                                    </div>
                                    <div style="padding-right: 10px;">
                                        <button class="btn btn-primary" @click="update_items(colour_data['items'], 1, 1, value['lot'], key, colour_mistake)">Complete Rework</button>
                                    </div>
                                </div>
                            </template>
                        </td>
                    </tr>
                </template>
                <tr>
                    <th>Total</th> 
                    <th></th>
                    <th></th>
                    <th></th>
                    <th></th>
                    <th></th>
                    <th></th>
                    <th v-for="ty in items['types']">
                        <span v-if="ty in items['total_detail']">{{items['total_detail'][ty] - items['total_rejection_detail'][ty]}}</span>
                        <span v-else>0</span>
                    </th>
                    <th> {{ items['total_sum'] - items['total_rejection'] }}</th>
                </tr>
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
let item = null
let colour = null

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
    $(el).find(".item-input").html("");
    item = frappe.ui.form.make_control({
        parent: $(el).find(".item-input"),
        df: {
            fieldname: "item",
            fieldtype: "Link",
            options: "Item",
            label: "Item",
        },
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".colour-input").html("");
    colour = frappe.ui.form.make_control({
        parent: $(el).find(".colour-input"),
        df: {
            fieldname: "colour",
            fieldtype: "Data",
            label: "Colour",
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
            item: item.get_value(),
            colour: colour.get_value(),
        },
        callback: function (r) {
            items.value = r.message;
        },
    });
}

function redirect_to_print(grn_number){
    let w = window.open(
        frappe.urllib.get_full_url(
            "/printview?" + "doctype=" + encodeURIComponent("Goods Received Note") + "&name=" +
                encodeURIComponent(grn_number) + "&trigger_print=1" + "&format=" + 
                encodeURIComponent("Rework Print") + "&no_letterhead=1"
        )
    );
    if (!w) {
        frappe.msgprint(__("Please enable pop-ups"));
        return;
    }
}

function toggle_row(key) {
    expandedRowKey.value = expandedRowKey.value === key ? null : key;
}

function update_changed(name, colour){
    items.value["report_detail"][name]['rework_detail'][colour]['changed'] = 1
}

function update_items(data, changed, completed, lot, series_key, mistake_key){
    if(completed == 1 || completed === 1){
        let d =  new frappe.ui.Dialog({
            title: "Are you sure want to final the item",
            primary_action_label: "Yes",
            secondary_action_label: "No",
            primary_action(){
                update(data, completed, lot)
                frappe.show_alert({
                    message: __("Rework Completed"),
                    indicator: "info",
                });
                if (items?.value?.report_detail?.[series_key]?.rework_detail) {
                    delete items.value.report_detail[series_key].rework_detail[mistake_key];
                    if (Object.keys(items.value.report_detail[series_key]['rework_detail']).length == 0){
                        delete items.value.report_detail[series_key]       
                    }
                }
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

function update_rework(data, lot, key, colour_mistake){
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
                    get_updated_rework_details(key, colour_mistake)
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

function get_updated_rework_details(key, colour_mistake){
    frappe.call({
        method: "production_api.production_api.doctype.grn_rework_item.grn_rework_item.get_partial_reworked_qty",
        args: {
            "doc_name": key,
            "colour_mistake": colour_mistake,
            "data": items.value
        },
        callback: function(r){
            items.value = r.message
        }
    })
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
    })
}

function map_to_grn(grn){
    const url = `/app/goods-received-note/${grn}`;
    window.open(url, '_blank');
}

function download(){
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/method/production_api.production_api.doctype.grn_rework_item.grn_rework_item.download_xl', true);
	xhr.setRequestHeader('X-Frappe-CSRF-Token',frappe.csrf_token)
	xhr.responseType = 'arraybuffer';
	xhr.onload = function (success) {
		if (this.status === 200) {
			var blob = new Blob([success.currentTarget.response], {type: "application/xlsx"});
			var filename = ""
			var disposition = xhr.getResponseHeader('Content-Disposition');
			if (disposition && disposition.indexOf('filename') !== -1) {
				var filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
				var matches = filenameRegex.exec(disposition);
				if (matches != null && matches[1]) filename = matches[1].replace(/['"]/g, '');
			}
	
			if (typeof window.navigator.msSaveBlob !== 'undefined') {
				window.navigator.msSaveBlob(blob, filename);
			} 
            else {
				var URL = window.URL || window.webkitURL;
				var downloadUrl = URL.createObjectURL(blob);
				if (filename) {
					var a = document.createElement("a");
					if (typeof a.download === 'undefined') {
						window.location.href = downloadUrl;
					} 
                    else {
						a.href = downloadUrl;
						a.download = filename;
						document.body.appendChild(a);
						a.click();
					}
				} 
                else {
					window.location.href = downloadUrl;
				}
				setTimeout(function () { URL.revokeObjectURL(downloadUrl); }, 100);
			}
		}
		else{
			var dec = new TextDecoder("utf-8")
			var data = dec.decode(this.response)
			frappe.request.cleanup({}, JSON.parse(data))
		}
	};
	xhr.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
	xhr.send($.param({"data" : JSON.stringify(items.value)}, true));
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
