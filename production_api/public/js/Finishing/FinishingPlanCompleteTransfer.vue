<template>
    <div>
        <div style="display:flex;width:100%;gap:20px;">
            <div v-if="dc_list && Object.keys(dc_list).length > 0" style="width:50%;">
                <h3>DC List</h3>
                <table class="table table-sm table-sm-bordered bordered-table">
                    <thead class="dark-border">
                        <tr>
                            <th>Delivery Challan</th>
                        </tr>
                    </thead>
                    <tbody class="dark-border">
                        <tr v-for="(date, dc) in dc_list">
                            <td style="cursor: pointer;" @click="redirect_to('Delivery Challan', dc)">{{ dc }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div v-if="grn_list && Object.keys(grn_list).length > 0" style="width:50%;">
                <h3>GRN List</h3>
                <table class="table table-sm table-sm-bordered bordered-table">
                    <thead class="dark-border">
                        <tr>
                            <th>Goods Received Note</th>
                        </tr>
                    </thead>
                    <tbody class="dark-border">
                        <tr v-for="(date, grn) in grn_list">
                            <td style="cursor: pointer;" @click="redirect_to('Goods Received Note', grn)">{{ grn }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>    
</template>

<script setup>

let dc_list = JSON.parse(cur_frm.doc.incomplete_transfer_dc_list || "{}")
let grn_list = JSON.parse(cur_frm.doc.incomplete_transfer_grn_list || "{}")

function redirect_to(doctype, docname){
    frappe.open_in_new_tab = true;
    frappe.set_route("Form", doctype, docname);
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

.dark-border{
    border: 2px solid black;
}
</style>