<template>
    <div v-if="items && Object.keys(items).length > 0">
        <table class="bordered-table">
            <thead class="dark-border">
                <tr>
                    <th>S.No</th>
                    <th>Process</th>
                    <th>Work Order</th>
                    <th>Type</th>
                    <th v-for="size in items['sizes']">{{ size }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <template v-for="(process, idx) in Object.keys(items['processes'])">
                    <tr>
                        <td :rowspan="3">{{ idx + 1 }}</td>
                        <td :rowspan="3">{{ process }}</td>
                        <td :rowspan="3">
                            <div>
                                <template v-for="(wo, i) in limited_wo(items['processes'][process]['wo_list'])">
                                    <div style="cursor: pointer;" @click="redirect_to_doc('Work Order', wo)">{{ wo }}</div>
                                </template>
                                <div v-if="items['processes'][process]['wo_list'].length > 3" class="more-btn-wrapper">
                                    <button class="more-btn" @click="redirect_to_wolist(process)">
                                        +{{ items['processes'][process]['wo_list'].length - 3 }} more
                                    </button>
                                </div>
                            </div>
                            <div>
                                <div v-if="items['processes'][process]['cp_list'].length > 0">
                                    <div><strong>Cutting Plan</strong></div>
                                    <div v-for="cp in items['processes'][process]['cp_list']">
                                        <div style="cursor: pointer;" @click="redirect_to_doc('Cutting Plan', cp)">{{ cp }}</div>
                                    </div>
                                </div>
                            </div>
                        </td>
                        <td>Sent</td>
                        <td v-for="size in items['sizes']">
                            {{ items['processes'][process]['data'][size]['sent'] }}
                        </td>
                        <td>{{ items['processes'][process]['total_sent'] }}</td>
                    </tr>

                    <tr>
                        <td>Received</td>
                        <td v-for="size in items['sizes']">
                            {{ items['processes'][process]['data'][size]['received'] }}
                        </td>
                        <td>{{ items['processes'][process]['total_received'] }}</td>
                    </tr>

                    <tr>
                        <td>Difference</td>
                        <td v-for="size in items['sizes']"
                            :style="get_style(
                                get_diff(
                                    items['processes'][process]['data'][size]['received'],
                                    items['processes'][process]['data'][size]['sent']
                                ))">
                            {{
                                get_diff(
                                    items['processes'][process]['data'][size]['received'],
                                    items['processes'][process]['data'][size]['sent']
                                ) 
                            }}
                        </td>
                        <td :style="get_style(
                            get_diff(
                                items['processes'][process]['total_received'], 
                                items['processes'][process]['total_sent']
                            ))">
                            {{ 
                                get_diff(
                                    items['processes'][process]['total_received'], 
                                    items['processes'][process]['total_sent']
                                ) 
                            }}
                        </td>
                    </tr>
                </template>
                <tr>
                    <td></td>
                    <td>Dispatch</td>
                    <td>
                        <div v-for="fp in items['finishing_plan_list']">
                            <div style="cursor:pointer;" @click="redirect_to_doc('Finishing Plan', fp)">{{ fp }}</div>
                        </div>
                        {{ items['finishing_plan'] }}
                    </td>
                    <td></td>
                    <td v-for="size in items['sizes']">{{ items['dispatch_detail'][size] }}</td>
                    <td>{{ items['total_dispatch'] }}</td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

let items = ref({})

onMounted(() => {
    frappe.call({
        method: "production_api.essdee_production.doctype.lot.lot.get_ocr_details",
        args: { lot: cur_frm.doc.name },
        callback: function (r) {
            items.value = r.message
        }
    })
})

function get_diff(val1, val2) {
    return val1 - val2
}

function get_style(val) {
    if (val < 0) return { background: "#f57f87" }
    else if (val > 0) return { background: "#98ebae" }
    return { background: "none" }
}

function limited_wo(wo_list) {
    return wo_list.slice(0, 3)
}

function redirect_to_wolist(process){
    localStorage.setItem("process", process)
    localStorage.setItem("lot", cur_frm.doc.name)
    frappe.open_in_new_tab = true
    frappe.set_route("Form", "Work Order")
}
function redirect_to_doc(doctype, docname){
    frappe.open_in_new_tab = true
    frappe.set_route("Form", doctype, docname)
}

</script>

<style scoped>
.bordered-table {
    width: 100%;
    border: 1px solid #ccc;
    border-collapse: collapse;
}

.bordered-table th,
.bordered-table td {
    border: 1px solid #ccc;
    padding: 6px 8px;
    text-align: center;
}

.bordered-table thead {
    background-color: #f8f9fa;
    font-weight: bold;
}

.dark-border {
    border: 2px solid black;
}

.more-btn-wrapper {
    position: relative;
    display: inline-block;
}

.more-btn {
    background: #007bff;
    color: white;
    border: none;
    padding: 2px 6px;
    font-size: 12px;
    border-radius: 4px;
    cursor: pointer;
    margin-top: 4px;
}

.more-btn:hover {
    background: #0056b3;
}

.dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    background: white;
    border: 1px solid #ccc;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
    padding: 4px 8px;
    z-index: 100;
    white-space: nowrap;
}

.dropdown div {
    padding: 2px 0;
}
</style>
