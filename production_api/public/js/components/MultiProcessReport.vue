<template>
    <div ref="root">
        <div class="collapsible-container">
            <button class="toggle-btn" @click="showTable = !showTable">
                {{ showTable ? 'Hide Process' : 'Show Process' }}
            </button>
            <transition name="collapse">
                <div v-show="showTable" class="collapsible-content" style="display:flex;">
                    <div style="width:100%;">
                        <table v-if="process_list.length > 0" class="table table-sm-bordered process-table">
                            <tr>
                                <th>S.No</th>
                                <th>Process</th>
                                <th>Delete</th>
                            </tr>
                            <tr v-for="(process, idx) in process_list" :key="idx">
                                <td>{{ idx + 1 }}</td>
                                <td>{{ process.process_name }}</td>
                                <td>
                                    <div class="cursor-pointer" @click="delete_item(idx)" v-html="frappe.utils.icon('delete', 'md')"></div>
                                </td>
                            </tr>
                        </table>
                        <div class="process-input-row">
                            <div class="process-input col-md-5"></div>
                        </div>
                        <div class="btn-wrapper">
                            <button class="btn btn-success" @click="add_process_list()">Add</button>
                        </div>
                    </div>
                </div>
            </transition>
        </div>
    </div>
</template>

<script setup>

import {ref, onMounted} from 'vue';

let root = ref(null)
let sample_doc = ref({})
let process_list = ref([])
let process_name = null
let showTable = ref(false)

onMounted(()=> {
    let el = root.value
    $(el).find(".process-input").html("");
    process_name = frappe.ui.form.make_control({
        parent: $(el).find(".process-input"),
        df: {
            fieldname: "process",
            fieldtype: "Link",
            options: "Process",
            label: "Process",
        },
        doc: sample_doc.value,
        render_input: true,
    })
})

function add_process_list(){
    let p_value = process_name.get_value()
    if(!p_value){
        frappe.msgprint("Please Set Process Name")
    }
    else{
        process_list.value.push({
            "process_name": p_value,
        })
        process_name.set_value(null)
    }
}

function delete_item(idx){
    process_list.value.splice(idx, 1)
}

defineExpose({
    process_list
})

</script>
<style scoped>

.checkbox-style{
    display: inline-flex; 
    align-items: center; 
    gap: 4px;
    padding-right:10px;
}
.collapsible-container {
    border: 1px solid #dcdcdc;
    border-radius: 8px;
    padding: 10px;
    width: 100%;
    margin: 10px 0;
    overflow: visible !important;
}
.toggle-btn {
    background-color: #007bff;
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: 5px;
    cursor: pointer;
    margin-bottom: 10px;
    transition: background 0.2s ease;
}

.toggle-btn:hover {
    background-color: #0056b3;
}

.collapsible-content {
    overflow: hidden;
    transition: all 0.3s ease-in-out;
}

.process-table {
    width: 50%;
    border-collapse: collapse;
    margin-bottom: 10px;
}

.process-table th, .process-table td {
    border: 1px solid #dee2e6;
    padding: 8px;
    text-align: center;
}

.process-input-row {
    display: flex;
    z-index: 9999;
    overflow: visible !important;
}

.btn-wrapper {
    padding-top: 20px;
}

.collapse-enter-active, .collapse-leave-active {
    transition: all 0.3s ease;
}
.collapse-enter-from, .collapse-leave-to {
    max-height: 0;
    opacity: 0;
}
.collapse-enter-to, .collapse-leave-from {
    max-height: 500px;
    opacity: 1;
}
.process-input-row, .collapsible-container, .collapsible-content {
    overflow: visible !important;
}
</style>