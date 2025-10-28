<template>
    <div ref="root" style="padding: 20px;">
        <div class="row pb-4">
            <div class="lot-name col-md-2"></div>
            <div class="item-name col-md-2"></div>
            <div class="row col-md-5">
                <div style="padding-top: 27px;">
                    <button class="btn btn-success ml-3" @click="get_filters()">Show Report</button>
                </div>
                <div style="padding-top: 27px;">
                    <button class="btn btn-primary ml-3" @click="sort()">Sort By Delay</button>
                </div>
                <div  style="padding-top: 27px;" v-if="same_action_list.length > 0">
                    <button class="btn btn-success ml-3" @click="update_all()">Update All</button>
                </div>
                <div style="padding-top: 27px;" v-if="approver">
                    <button class="btn btn-success ml-3" @click="update_revised_date()">Update Revised Date</button>
                </div>
            </div>
            <div class="col-md-3" v-if="is_edited" style="text-align:right;">
                <div style="padding-top: 27px;">
                    <span class="indicator-pill no-indicator-dot whitespace-nowrap orange">
                        <span>Not Saved</span>
                    </span>
                    <button class="btn btn-success ml-3" @click="update_t_and_a()">Save T&A</button>
                </div>
            </div>
        </div>
        <div class="scroll-container1" v-show="show_table">
            <h3 style="text-align:center;padding-top:15px;">Time and Action Update</h3>
            <div v-for="lot in Object.keys(items)" :key="lot" class="lot-container">
                <h3>Over all Performance {{ items[lot]['performance'] }}%</h3>
                <h3>Over all Delay {{ items[lot]['over_all_delay'] }}</h3>
                <div v-for="master in Object.keys(items[lot]['masters'])" :key="master">
                    <div>
                        <div class="lot-title">{{ lot }} ({{ master }})</div>
                        <div class="scroll-container2">
                            <div class="outer-table">
                                <table class="inner-table">
                                    <thead>
                                        <tr>
                                            <th class="sticky-col col1">S.No</th>
                                            <th class="sticky-col col2">Colour</th>
                                            <th class="sticky-col col3">Quantity</th>
                                            <th class="sticky-col col4">Start Date</th>
                                            <th class="sticky-col col5">Dispatch Date</th>
                                            <th class="sticky-col col6">Delay</th>
                                            <th class="sticky-col col7">Performance</th>
                                            <th class="sticky-col col8">Activity</th>
                                            <th v-for="(action, idx) in items[lot]['masters'][master]['actions']" :key="action"
                                                class="action-th-style" @mouseenter="hoveredAction = action; hoverMaster = master;" @mouseleave="hoveredAction = null; hoverMaster = null;">
                                                <div v-if="items[lot]['masters'][master]['datas'][0]['actions'][idx]['merge_action']">
                                                    <div style="display: flex;width:100%;" >
                                                        <div style="width:70%;">{{ action }}</div> 
                                                        <div style="width:30%;align-content: center;">
                                                            <svg xmlns="http://www.w3.org/2000/svg" fill="#000000" width="20px" height="20px" 
                                                                viewBox="0 0 52 52" enable-background="new 0 0 52 52" xml:space="preserve">
                                                                <path d="M42.3,44c-5.6-2.7-9.6-7.5-11.6-13c-0.8-2-1.3-4.3-1.5-6.3v-3.5H40c0.8,0,1.4-0.9,0.8-1.8l-14.2-17  
                                                                    c-0.5-0.6-1.6-0.6-2,0l-13.8,17c-0.5,0.6,0,1.8,0.8,1.8h10.9c0,1.5,0,3.4,0,3.4v0.1l0,0c-0.3,2.1-0.8,4.4-1.5,6.3  
                                                                    c-2,5.5-6,10.3-11.6,13c-0.8,0.3-1.1,1.3-0.8,2l1.3,3.1c0.4,0.8,1.3,1.1,2.1,0.6c6-2.9,10.8-7.5,13.7-13c3,5.5,7.7,10.1,13.8,13  
                                                                    c0.8,0.4,1.8,0.3,2.1-0.6l1.3-3.1C43.5,45.3,43.1,44.4,42.3,44z"/>
                                                            </svg>
                                                        </div>
                                                    </div>
                                                </div>
                                                <div v-else>
                                                    <div>{{ action }}</div> 
                                                </div>
                                                <div>
                                                    {{ items[lot]['masters'][master]['datas'][0]['actions'][idx]['lead_time'] }} 
                                                    <span v-if="items[lot]['masters'][master]['datas'][0]['actions'][idx]['lead_time'] > 1">Days</span>
                                                    <span v-else>Day</span>
                                                </div>
                                                
                                                <div v-if="hoveredAction === action && hoverMaster == master" class="popup">
                                                    <div v-if="items[lot]['masters'][master]['datas'][0]['actions'][idx]['dependent_details']">
                                                        <h4>Dependencies</h4>
                                                        <div v-for="(dept, val) in items[lot]['masters'][master]['datas'][0]['actions'][idx]['dependent_details']">
                                                            {{ val }}
                                                        </div>
                                                    </div>
                                                    <div v-else>
                                                        No Dependencies
                                                    </div>
                                                    <br>
                                                    <h4>Respective Department</h4>
                                                    {{ items[lot]['masters'][master]['datas'][0]['actions'][idx]['department'] }}
                                                </div>
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <template v-for="(data, idx) in items[lot]['masters'][master]['datas']" :key="data">
                                            <tr>
                                                <td class="sticky-col col1" rowspan="10">{{ idx + 1 }}</td>
                                                <td class="sticky-col col2" rowspan="10">{{ data.colour }}</td>
                                                <td class="sticky-col col3" rowspan="10">{{ data.qty }}</td>
                                                <td class="sticky-col col4" rowspan="10">{{ get_date(data.start_date) }}</td>
                                                <td class="sticky-col col5" rowspan="10" :style="{ backgroundColor: data.end_date_delay ? '#FFCCCB' : 'White'}">{{ get_date(data.end_date) }}</td>
                                                <td class="sticky-col col6" rowspan="10">
                                                    <div style="display:flex;flex-direction:column;height:100px;justify-content: space-between;">
                                                        <div>
                                                            Actual: {{ data.delay }} 
                                                        </div>
                                                        <div>
                                                            Rescheduled: {{ data.rescheduled_delay }}
                                                        </div>
                                                    </div>
                                                </td>
                                                <td class="sticky-col col7" rowspan="10">{{ data.performance }}%</td>
                                            </tr>
                                            <tr>
                                                <td class="sticky-col col8">Planned Date</td>
                                                <td v-for="d in data['actions']" :key="d.date">
                                                    <div style="width:100%;">
                                                        <div class="action-td-style">
                                                            {{ get_date(d.planned_start_date) }}
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="sticky-col col8">Freezed Date</td>
                                                <td v-for="d in data['actions']" :key="d.date">
                                                    <div style="width:100%;">
                                                        <div class="action-td-style">
                                                            {{ get_date(d.date) }}
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="sticky-col col8" style="cursor: pointer;" @click="show_popup(lot, master, idx)">Rescheduled Date {{ data['rescheduled_details'][Object.keys(data['rescheduled_details'])[0]]['rescheduled_dates'].length }}</td>
                                                <td v-for="d in data['actions']" :key="d.rescheduled_date">
                                                    <div style="width:100%;">
                                                        <div class="action-td-style">
                                                            {{ get_date(d.rescheduled_date) }}
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="sticky-col col8">Actual</td>
                                                <td v-for="d in data['actions']" :key="d.actual_date" :style="{ backgroundColor: d.actual_date > d.rescheduled_date ? '#FFCCCB' : d.actual_date ? '#90EE90' : 'White'}">
                                                    <div style="width:100%;">
                                                        <div class="action-td-style">
                                                            <div v-if="d.enable_date && (departments.includes(d.department) || is_administrator)">
                                                                <VueDatePicker v-model="d['allocated']" format="dd-MM-yyyy"
                                                                    :teleport="true"
                                                                    @update:model-value="(val) => call_func(val, lot, master, idx, d.index)"
                                                                    :input-class="'custom-input'">
                                                                </VueDatePicker>
                                                            </div>    
                                                            <div v-else style="display: flex; justify-content: center;">
                                                                <div>
                                                                    {{ get_date(d.actual_date) }}
                                                                </div>
                                                                <div v-if="d.remove_date" @click="remove_date(lot, master, idx, d.index)" class="cancel-style">
                                                                    ✖
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="sticky-col col8">Reason for Delay</td>
                                                <td v-for="d in data['actions']" :key="d.index">
                                                    <div style="width:100%;">
                                                        <div class="action-td-style">
                                                            <input type="text" v-model="d.reason" class="form-control" :class="{ 'custom-style-input': d.actual_date > d.rescheduled_date && !d.reason }" @blur="update_status()"/>
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="sticky-col col8">Performance</td>
                                                <td v-for="d in data['actions']" :key="d.index">
                                                    <div style="width:100%;">
                                                        <div class="action-td-style">
                                                            {{ d.performance }}%
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="sticky-col col8">Delay</td>
                                                <td v-for="d in data['actions']" :key="d">
                                                    <div style="width:100%;">
                                                        <div class="action-td-style">
                                                            {{ d.date_diff }}
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="sticky-col col8">Cumulative Actual Delay</td>
                                                <td v-for="d in data['actions']" :key="d">
                                                    <div style="width:100%;">
                                                        <div class="action-td-style">
                                                            {{ d.actual_delay }}
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="sticky-col col8">Cumulative Rescheduled Delay</td>
                                                <td v-for="d in data['actions']" :key="d">
                                                    <div style="width:100%;">
                                                        <div class="action-td-style">
                                                            {{ d.cumulative_delay }}
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                        </template>
                                    </tbody>
                                </table>
                            </div>
                        </div>    
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, nextTick, createApp, readonly } from 'vue';
import VueDatePicker from '@vuepic/vue-datepicker';
import '@vuepic/vue-datepicker/dist/main.css'
import TandARescheduledDates from "./TandARescheduledDates.vue";

let lot = null;
let item = null;
let root = ref(null);
let sample_doc = ref({});
let items = ref([])
let show_table = ref(false)
let same_action_list = ref([])
let is_edited = ref(false)
let hoveredAction = ref(null);
let hoverMaster = ref(null);
let approver = ref(false)
let departments = ref([])
let is_administrator = ref(false)

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
            onchange:async ()=> {
                let x = lot.get_value()
                if(x && x != "" && x != null){
                    let y = await frappe.db.get_value('Lot',x, "item")
                    item.set_value(y.message.item)
                    item.refresh()
                }
            } 
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
});

function show_popup(lot, master, idx){
    let colour = items.value[lot]['masters'][master]['datas'][idx]['colour']
    let d = new frappe.ui.Dialog({
        title: `${colour} Rescheduled Details`,
        size: "extra-large",
        fields: [
            {
                fieldtype: "HTML",
                fieldname: "rescheduled_details_html"
            }
        ]
    })
    d.fields_dict['rescheduled_details_html'].$wrapper.html("")
    d.show()
    const el = d.fields_dict["rescheduled_details_html"].$wrapper.get(0);
    const props = { "rescheduled_details": items.value[lot]['masters'][master]['datas'][idx]['rescheduled_details'],};
    const vueApp = createApp(TandARescheduledDates, props);
    i = vueApp.mount(el);
}

function get_filters() {
    show_table.value = false
    if(!lot.get_value()){
        frappe.msgprint("Enter the Value for Lot to Generate Report")
        return
    }
    frappe.call({
        method: "production_api.essdee_production.doctype.time_and_action.time_and_action.get_t_and_a_update_data",
        args: {
            "lot":lot.get_value(),
            "item": item.get_value(),
        },
        callback: function(r){
            items.value = r.message.data
            if(frappe.user.has_role(r.message.role) && r.message.revised_limit > r.message.max_revised){
                approver.value = true
            }
            else{
                approver.value = false
            }
            let lot_value = lot.get_value()
            departments.value = r.message.departments
            if(r.message.user == 'Administrator'){
                is_administrator.value = true
            }
            is_edited.value = false
            update_same_action(lot_value)
            show_table.value = true
        }
    })
}

function update_revised_date(){
    if(items.value.length == 0){
        frappe.msgprint("Generate Report to Revise the Date")
    }
    else{
        let lot_value = lot.get_value()
        let colour_d = {}
        let planned_date = null
        let rescheduled_date = null
        for (const master_val of Object.keys(items.value[lot_value]['masters'])) {
            const masterData = items.value[lot_value]['masters'][master_val]['datas']
            for (let i = 0; i < masterData.length; i++) {
                if(!colour_d.hasOwnProperty(masterData[i]['colour'])){
                    colour_d[masterData[i]['colour']] = {
                        "action": null,
                        "delay": null
                    }
                }
                const actions = masterData[i]['actions']
                if(!planned_date){
                    planned_date = actions[actions.length - 1]['date']
                    rescheduled_date = actions[actions.length - 1]['rescheduled_date']
                }
                else{
                    if(actions[actions.length - 1]['date'] > planned_date){
                        planned_date = actions[actions.length - 1]['date']
                    }
                    if(actions[actions.length - 1]['rescheduled_date'] > rescheduled_date){
                        rescheduled_date = actions[actions.length - 1]['rescheduled_date']
                    }
                }
                for (let j = 0; j < actions.length; j++) {
                    if (!actions[j]['actual_date'] && !actions[j]['one_colour_process']){
                        break
                    }
                    else{
                        colour_d[masterData[i]['colour']]['action'] = actions[j]['action']
                        colour_d[masterData[i]['colour']]['delay'] = actions[j]['date_diff']
                    } 
                }
            }
        }
        let data = []
        for(let colour in colour_d){
            data.push({
                "colour": colour,
                "action": colour_d[colour]['action'],
                "delay": colour_d[colour]['delay']
            })
        }
        let d = new frappe.ui.Dialog({
            title: `Dispatch Date Changes From ${get_date(planned_date)} to ${get_date(rescheduled_date)} 
                    <br>Are You Sure Want to Revise the dates`,
            fields: [
                {
                    label: "Delay Details",
                    fieldname: 'colour_data',
                    fieldtype: "Table",
                    cannot_add_rows: true,
                    cannot_delete_rows: true,
                    in_place_edit: false,
                    data: data,
                    fields: [
                        { fieldname: 'colour', fieldtype: 'Data', in_list_view: 1, label: 'Colour', read_only: 1},
                        { fieldname: 'action', fieldtype: 'Data', in_list_view: 1, label:'Action', read_only: 1},
                        { fieldname: 'delay', fieldtype: 'Int', in_list_view: 1, label:'Delay', read_only: 1}
                    ]
                },
                {
                    label: "Reason",
                    fieldname: "reason",
                    fieldtype: "Small Text",
                    reqd: 1,
                }
            ],
            primary_action_label: "Yes",
            secondary_action_label: "No",
            primary_action(values){
                d.hide()
                frappe.call({
                    method: "production_api.essdee_production.doctype.time_and_action.time_and_action.revise_date",
                    args: {
                        data: items.value,
                        reason: values.reason
                    },
                    callback: function(){
                        get_filters()
                    }
                })   
            },
            secondary_action(){
                d.hide()
            }
        })
        d.show()

    }
}

async function call_func(event, lot, master, idx, index){
    const day = String(event.getDate()).padStart(2, '0');
    const month = String(event.getMonth() + 1).padStart(2, '0');
    const year = event.getFullYear();
    const date = `${year}-${month}-${day}`
    const updated_action = items.value[lot]['masters'][master]['actions'][index]
    if(items.value[lot]['masters'][master]['datas'][idx]['actions'][index]['merge_action']){
        for (const master_val of Object.keys(items.value[lot]['masters'])) {
            const masterData = items.value[lot]['masters'][master_val]['datas']
            for (let i = 0; i < masterData.length; i++) {
                const actions = masterData[i]['actions']
                for (let j = 0; j < actions.length; j++) {
                    if (actions[j]['action'] !== updated_action) continue;
                    const r = await new Promise((resolve, reject) => {
                        frappe.call({
                            method: "production_api.essdee_production.doctype.time_and_action.time_and_action.get_update_rescheduled_date",
                            args: {
                                "updated_date": date,
                                "key": "updated",
                                "updated_action": updated_action,
                                "data_index": i,
                                "total_data": items.value,
                                "cur_index": j,
                                "lot": lot,
                                "master": master_val,
                            },
                            callback: function (res) {
                                resolve(res)
                            },
                            error: function (err) {
                                reject(err)
                            }
                        })
                    })
                    if (r && r.message && r.message.total_data) {
                        is_edited.value = true
                        items.value = r.message.total_data
                        if(r.message.diff < items.value[lot]['over_all_delay']){
                            items.value[lot]['over_all_delay'] = r.message.diff
                        }
                    }
                }
            }
        }
        update_same_action(lot)
    }
    else{
        frappe.call({
            method: "production_api.essdee_production.doctype.time_and_action.time_and_action.get_update_rescheduled_date",
            args: {
                "updated_date": date,
                "key": "updated",
                "updated_action": updated_action,
                "data_index": idx,
                "total_data": items.value,
                "cur_index": index,
                "lot": lot,
                "master": master,
            },
            callback: function(r){
                is_edited.value = true
                items.value = r.message.total_data
                if(r.message.diff < items.value[lot]['over_all_delay']){
                    items.value[lot]['over_all_delay'] = r.message.diff
                }
                let length = r.message.details.length - 1
                let data = r.message.details
                if(data[length]['date'] < data[length]['rescheduled_date'] && data[index]['actual_date'] > data[index]['rescheduled_date']){
                    frappe.msgprint(`${r.message.details[length]['action']} gets delay from ${get_date(data[length]['date'])} to ${get_date(data[length]['rescheduled_date'])}`)
                }
                update_same_action(lot)
            }
        })
    }
}

async function remove_date(lot, master, idx, index){
    let d = null
    const updated_action = items.value[lot]['masters'][master]['actions'][index]
    if(index !== 0){
        d = items.value[lot]['masters'][master]['datas'][idx]['actions'][index - 1]['actual_date']
    }
    else{
        d = items.value[lot]['masters'][master]['datas'][idx]['actions'][index]['rescheduled_date']
    }
    if(items.value[lot]['masters'][master]['datas'][idx]['actions'][index]['merge_action']){
        for (const master_val of Object.keys(items.value[lot]['masters'])) {
            const masterData = items.value[lot]['masters'][master_val]['datas']
            for (let i = 0; i < masterData.length; i++) {
                const actions = masterData[i]['actions']
                for (let j = 0; j < actions.length; j++) {
                    if (actions[j]['action'] !== updated_action) continue;
                    const r = await new Promise((resolve, reject) => {
                        frappe.call({
                            method: "production_api.essdee_production.doctype.time_and_action.time_and_action.get_update_rescheduled_date",
                            args: {
                                "updated_date": d,
                                "key": "removed",
                                "updated_action": updated_action,
                                "data_index": i,
                                "total_data": items.value,
                                "cur_index": j,
                                "lot": lot,
                                "master": master_val,
                            },
                            callback: function (res) {
                                resolve(res)
                            },
                            error: function (err) {
                                reject(err)
                            }
                        })
                    })
                    if (r && r.message && r.message.total_data) {
                        is_edited.value = true
                        items.value = r.message.total_data
                        if(r.message.diff < items.value[lot]['over_all_delay']){
                            items.value[lot]['over_all_delay'] = r.message.diff
                        }
                        items.value[lot]['masters'][master]['datas'][i]['actions'][j]['actual_date'] = null
                    }
                }
            }
        }
        update_same_action(lot)
    }
    else{
        frappe.call({
            method: "production_api.essdee_production.doctype.time_and_action.time_and_action.get_update_rescheduled_date",
            args: {
                "updated_date": d,
                "key": "removed",
                "updated_action": updated_action,
                "data_index": idx,
                "total_data": items.value,
                "cur_index": index,
                "lot": lot,
                "master": master,
            },
            callback: function(r){
                is_edited.value = true
                items.value = r.message.total_data
                if(r.message.diff < items.value[lot]['over_all_delay']){
                    items.value[lot]['over_all_delay'] = r.message.diff
                }
                items.value[lot]['masters'][master]['datas'][idx]['actions'][index]['actual_date'] = null
                update_same_action(lot)
            }
        })
    }
}

function update_same_action(lot){
    let same_dict = {}
    for (const master of Object.keys(items.value[lot]['masters'])) {
        for(let i = 0; i < items.value[lot]['masters'][master]['datas'].length; i++){
            for( let j = 0; j < items.value[lot]['masters'][master]['datas'][i]['actions'].length; j++){
                if(("enable_date" in items.value[lot]['masters'][master]['datas'][i]['actions'][j])){
                    if(items.value[lot]['masters'][master]['datas'][i]['actions'][j]['enable_date']){
                        if(!same_dict.hasOwnProperty(items.value[lot]['masters'][master]['datas'][i]['colour'])){
                            same_dict[items.value[lot]['masters'][master]['datas'][i]['colour']] = []
                        }
                        same_dict[items.value[lot]['masters'][master]['datas'][i]['colour']].push(items.value[lot]['masters'][master]['datas'][i]['actions'][j]['action'])
                    }
                }
            }
        }
    }
    let colour_length = Object.keys(same_dict).length
    let d = {}
    for(colour in same_dict){
        for(action of same_dict[colour]){
            if(!d.hasOwnProperty(action)){
                d[action] = 0
            }
            d[action] += 1
        }
    }
    let final_list = []
    for(act in d){
        if(d[act] == colour_length){
            final_list.push(act)
        }
    }
    same_action_list.value = final_list
}

function sort(){
    for (lot_value in items.value) {
        for (master in items.value[lot_value]['masters']) {
            items.value[lot_value]['masters'][master].datas.sort((a, b) => a.delay - b.delay);
        }
    }
}

function update_all(){
    let lot_value = lot.get_value()
    update_same_action(lot_value)
    nextTick(()=> {
        let dialog = new frappe.ui.Dialog({
            title : `Update for all`,
            fields : [
                {
                    "label": "Select the Action",
                    "fieldname": 'action',
                    "fieldtype": 'Select',
                    "options": same_action_list.value,
                    "reqd": 1,
                },
                {
                    "label": "Actual Date",
                    "fieldname": "actual_date",
                    "fieldtype": "Date",
                    "reqd": 1,
                },
                {
                    "fieldname" : "reason",
                    "fieldtype" : "Data",
                    "label" : "Reason",
                    "reqd": 1
                },
            ],
            async primary_action(values){
                dialog.hide()
                for (const master of Object.keys(items.value[lot_value]['masters'])) {
                    const masterData = items.value[lot_value]['masters'][master]['datas']
                    for (let i = 0; i < masterData.length; i++) {
                        const actions = masterData[i]['actions']
                        for (let j = 0; j < actions.length; j++) {
                            if (actions[j]['action'] !== values.action) continue;
                            const event = new Date(values.actual_date)
                            const date = `${event.getFullYear()}-${String(event.getMonth() + 1).padStart(2, '0')}-${String(event.getDate()).padStart(2, '0')}`
                            const updated_action = actions[j]
                            const r = await new Promise((resolve, reject) => {
                                frappe.call({
                                    method: "production_api.essdee_production.doctype.time_and_action.time_and_action.get_update_rescheduled_date",
                                    args: {
                                        "updated_date": date,
                                        "key": "updated",
                                        "updated_action": updated_action,
                                        "data_index": i,
                                        "total_data": items.value,
                                        "cur_index": j,
                                        "lot": lot_value,
                                        "master": master,
                                    },
                                    callback: function (res) {
                                        resolve(res)
                                    },
                                    error: function (err) {
                                        reject(err)
                                    }
                                })
                            })
                            if (r && r.message && r.message.total_data) {
                                is_edited.value = true
                                items.value = r.message.total_data
                            }
                        }
                    }
                }
                update_same_action(lot_value)
            }
        })
        dialog.show()
    })
}

function update_status(){
    is_edited.value = true
}

function get_date(date){
    if(date){
        let x = new Date(date)
        return x.getDate() + "-" + (x.getMonth() + 1) + "-" + x.getFullYear()
    }
    return ""
}

function update_t_and_a(){
    let check = check_reason()
    if(!check['val']){
        frappe.msgprint(`For ${check['colour']}, Please enter reason for the ${check['action']} delay`)
    }    
    else{
        frappe.call({
            method: "production_api.essdee_production.doctype.time_and_action.time_and_action.update_t_and_a",
            args: {
                data: items.value
            },
            freeze: true,
            freeze_message: "Updating T and A",
            callback: function(){
                get_filters()
            }
        })
    }
}

function check_reason(){
    for( lot_value in items.value){
        for ( master in items.value[lot_value]['masters']){
            for (row of items.value[lot_value]['masters'][master]['datas']){
                for (row1 of row['actions']){
                    if (!row1['reason'] && row1['actual_date'] && row1['actual_date'] > row1['rescheduled_date']){
                        return {
                            "val": false,
                            "action": row1['action'],
                            "colour": row['colour'],
                        }
                    }
                }
            }
        }
    }
    return {
        "val": true
    }
}

</script>

<style>
.scroll-container1 {
    width: 100%;
    overflow-x: hidden;
    border: 1px solid #ddd;
    position: relative;
    height:700px;
    overflow-y: scroll;
}

.cancel-style {
    cursor: pointer; 
    font-weight: bold; 
    color: red; 
    font-size: 15px;
}

.scroll-container2 {
    width: 100%;
    max-height: 700px;
    overflow: auto;
    position: relative;
}

.inner-table {
    min-width: 3200px;
}

.inner-table thead th.sticky-col {
  position: sticky;
  top: 0;
  z-index: 5;
  background: white;
}

.inner-table th, .inner-table td, .inner-table thead, .inner-table tbody{
    text-align: center;
    word-wrap: break-word; 
    border: 1px solid black;
}

.inner-table tbody tr:nth-child(odd) td {
  background-color: #f9f9f9; /* light gray */
}

.inner-table tbody tr:nth-child(even) td {
  background-color: #ffffff; /* white */
}

.inner-table tr{
    border: 1px solid black;
}

.inner-table th{
    background-color: #D3D3D3;
}

.lot-title {
    width: fit-content;
    position: sticky;
    z-index: 3;
    left: 0;
    background: white;
    padding: 10px;
}

table td {
  padding: 0px;
}

table th {
    cursor: pointer;
}

.inner-table thead {
    position: sticky;
    top: 0;
    z-index: 5;
    background: white; 
}

.sticky-col {
    border: 1px solid black;
    position: sticky;
    background: white;
    z-index: 1;
    border-right: 1px solid black;
    box-shadow: 2px 0 5px -2px black;
}

.action-td-style {
    width: 100%;
    word-wrap: break-word;
}

.action-th-style {
    max-width: 220px;
}

.col1 { left: 0;     box-shadow: inset 0 0 0 0.05rem black; width: 60px; }
.col2 { left: 60px;  box-shadow: inset 0 0 0 0.05rem black; width: 120px; }
.col3 { left: 180px; box-shadow: inset 0 0 0 0.05rem black; width: 70px;}
.col4 { left: 250px; box-shadow: inset 0 0 0 0.05rem black; width: 100px;}
.col5 { left: 350px; box-shadow: inset 0 0 0 0.05rem black; width: 120px;}
.col6 { left: 470px; box-shadow: inset 0 0 0 0.05rem black; width: 120px; }
.col7 { left: 590px; box-shadow: inset 0 0 0 0.05rem black; width: 110px; }
.col8 { left: 700px; box-shadow: inset 0 0 0 0.05rem black; width: 140px; }

:deep(.dp__menu) {
  z-index: 9999 !important;
}

.dp__theme_light,
.dp__theme_dark {
  --dp-cell-size: 20px !important;
  --dp-font-size: 12px !important;
  --dp-button-height: 0px !important;
  --dp-month-year-row-height: 15px !important;
  --dp-month-year-row-button-size: 15px !important;
  --dp-action-button-height: 22px !important;
  --dp-menu-min-width: 180px !important;
  --dp-menu-padding: 6px 8px !important;
  --dp-time-font-size: 12px !important;
  --dp-common-padding: 0px !important;
  --dp-button-icon-height: 0px !important;
  --dp-action-row-padding: 0px !important;
}

.custom-input {
  height: 26px;
  font-size: 12px;
  padding: 2px 6px;
  width: 120px;
  border-radius: 4px;
}

.custom-style-input {
  box-shadow: inset 2px 2px 0px red, inset 0px 0px 0px rgba(243, 76, 76, 0.3)
}

.popup {
  position: absolute;
  background: white;
  border: 1px solid #ddd;
  padding: 6px 10px;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  z-index: 20;
}

h3{
    margin: 0px;
    padding:5px;
}


</style>
