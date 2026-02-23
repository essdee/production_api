<template>
    <div ref="root" class="rejection-container">
        <h3 style="font-weight:700;margin-bottom:15px;color:#333;text-align:center;">Rejection Details</h3>
        <div class="input-row">
            <div class="start-date-input col-md-2"></div>
            <div class="end-date-input col-md-2"></div>
            <div class="lot-input col-md-2"></div>
            <div class="item-input col-md-2"></div>
            <div class="colour-input col-md-2"></div>
            <div class="btn-wrapper">
                <button class="btn btn-primary" @click="get_rejection_items()">Get Rejection Items</button>
            </div>
            <div class="btn-wrapper">
                <button class="btn btn-primary" @click="download()">Download XL</button>
            </div>
        </div>
        <div v-if="items && Object.keys(items).length > 0 && items['report_detail'] && Object.keys(items['report_detail']).length > 0" class="table-wrapper">
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
                            <div @click.stop="map_to_grn(value['grn_number'])" class="hover-style">{{ value['grn_number'] }}</div>
                        </td>
                        <td>{{ value['lot'] }}</td>
                        <td>{{ value['item'] }}</td>
                        <td>{{ Object.keys(value['rejection_detail'])[0].split("-").slice(1).join("-") }}</td>
                        <td v-for="ty in items['types']">
                            <span v-if="ty in value['types']">{{ value['types'][ty] }}</span>
                            <span v-else>0</span>
                        </td>
                        <th>{{ value['total'] }}</th>
                    </tr>
                    <tr v-if="expandedRowKey === key">
                        <td :colspan="1000" class="expanded-row-content">
                            <template v-for="(colour_data, colour_type) in value['rejection_detail']">
                                <h4 style="padding-top:8px;">{{ colour_type }}</h4>
                                <table style="width:100%;">
                                    <tr>
                                        <th>Size</th>
                                        <th v-for="size in colour_data['items']">
                                            {{ size[value['size']] }}
                                        </th>
                                    </tr>
                                    <tr>
                                        <td>Rejected Qty</td>
                                        <td v-for="size in colour_data['items']">
                                            {{ size['rejected_qty'] }}
                                        </td>
                                    </tr>
                                </table>
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
                    <th v-for="ty in items['types']">
                        <span v-if="ty in items['total_detail']">{{ items['total_detail'][ty] }}</span>
                        <span v-else>0</span>
                    </th>
                    <th>{{ items['total_sum'] }}</th>
                </tr>
            </table>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

let root = ref(null);
let sample_doc = ref({});
let items = ref({});
let expandedRowKey = ref(null);
let start_date = null;
let end_date = null;
let lot = null;
let item = null;
let colour = null;

onMounted(() => {
    let el = root.value;

    let today = frappe.datetime.get_today();
    let last_month = frappe.datetime.add_months(today, -1);
    let last_month_start = frappe.datetime.month_start(last_month);
    let last_month_end = frappe.datetime.month_end(last_month);

    $(el).find(".start-date-input").html("");
    start_date = frappe.ui.form.make_control({
        parent: $(el).find(".start-date-input"),
        df: {
            fieldname: "start_date",
            fieldtype: "Date",
            label: "Start Date",
            "default": last_month_start,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    start_date.set_value(last_month_start);

    $(el).find(".end-date-input").html("");
    end_date = frappe.ui.form.make_control({
        parent: $(el).find(".end-date-input"),
        df: {
            fieldname: "end_date",
            fieldtype: "Date",
            label: "End Date",
            "default": last_month_end,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    end_date.set_value(last_month_end);

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

function get_rejection_items() {
    if (!start_date.get_value() || !end_date.get_value()) {
        frappe.msgprint(__("Please enter both Start Date and End Date"));
        return;
    }
    if (start_date.get_value() > end_date.get_value()) {
        frappe.msgprint(__("Start Date should be less than End Date"));
        return;
    }
    frappe.call({
        method: "production_api.production_api.doctype.grn_rework_item.grn_rework_item.get_rejection_items",
        freeze: true,
        freeze_message: "Loading Rejection Items...",
        args: {
            start_date: start_date.get_value(),
            end_date: end_date.get_value(),
            lot: lot.get_value(),
            item: item.get_value(),
            colour: colour.get_value(),
        },
        callback: function (r) {
            items.value = r.message;
        },
    });
}

function toggle_row(key) {
    expandedRowKey.value = expandedRowKey.value === key ? null : key;
}

function get_date(date) {
    if (date) {
        let x = new Date(date);
        return x.getDate() + "-" + (x.getMonth() + 1) + "-" + x.getFullYear();
    }
}

function map_to_grn(grn) {
    const url = `/app/goods-received-note/${grn}`;
    window.open(url, '_blank');
}

function download() {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/method/production_api.production_api.doctype.grn_rework_item.grn_rework_item.download_rejection_xl', true);
    xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);
    xhr.responseType = 'arraybuffer';
    xhr.onload = function (success) {
        if (this.status === 200) {
            var blob = new Blob([success.currentTarget.response], { type: "application/xlsx" });
            var filename = "";
            var disposition = xhr.getResponseHeader('Content-Disposition');
            if (disposition && disposition.indexOf('filename') !== -1) {
                var filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                var matches = filenameRegex.exec(disposition);
                if (matches != null && matches[1]) filename = matches[1].replace(/['"]/g, '');
            }
            if (typeof window.navigator.msSaveBlob !== 'undefined') {
                window.navigator.msSaveBlob(blob, filename);
            } else {
                var URL = window.URL || window.webkitURL;
                var downloadUrl = URL.createObjectURL(blob);
                if (filename) {
                    var a = document.createElement("a");
                    if (typeof a.download === 'undefined') {
                        window.location.href = downloadUrl;
                    } else {
                        a.href = downloadUrl;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                    }
                } else {
                    window.location.href = downloadUrl;
                }
                setTimeout(function () { URL.revokeObjectURL(downloadUrl); }, 100);
            }
        } else {
            var dec = new TextDecoder("utf-8");
            var data = dec.decode(this.response);
            frappe.request.cleanup({}, JSON.parse(data));
        }
    };
    xhr.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
    xhr.send($.param({ "data": JSON.stringify(items.value) }, true));
}
</script>

<style scoped>
.rejection-container {
    background-color: #f8f9fa;
    border-radius: 8px;
    padding: 20px;
}

.page-title {
    font-weight: 700;
    margin-bottom: 15px;
    color: #333;
    text-align: center;
}

.input-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.btn-wrapper {
    padding-top: 27px;
}

.table-wrapper {
    margin-top: 15px;
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

.hover-style:hover {
    text-decoration: underline;
}
</style>
