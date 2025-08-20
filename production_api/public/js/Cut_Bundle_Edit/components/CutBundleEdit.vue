<template>
    <div ref="root">
        <div style="display:flex;">
            <div class="colour-field col-md-5"></div>
            <div style="padding-top:25px;" v-if="docstatus == 0"> 
                <button class="btn btn-success" @click="fetch_bundles()">Fetch Bundles</button>
            </div>
        </div>
        <div>
            <CutPanelMovementBundle ref="bundleRef" :data="fetched_data" />
        </div>
        <div style="width:100%;display: flex;" v-if="docstatus == 0">
            <div>
                <button class="btn btn-success" @click="fetch_selected_bundles()">Fetch Selected Bundles</button>
            </div>
            <div style="padding-left: 10px;">
                <button class="btn btn-success" @click="split_bundles()">Split Bundles</button>
            </div>
        </div>
        <div v-if="input_bundles.length > 0 || output_bundles.length > 0">
            <div style="width: 100%; display: flex; padding-top: 20px;">
                <div style="width: 50%; border: 1px solid black; padding: 5px;">
                    <div style="display: flex; flex-wrap: wrap; gap: 5px;">
                        <div v-for="(input, index) in input_bundles" :key="index" class="catalog">
                            <div class="catalog-content">
                                <div class="catalog-footer" v-if="input.set_combination.hasOwnProperty('major_colour')">
                                    <strong> {{input.set_combination.major_colour }} </strong>
                                </div>
                                <div class="catalog-footer" v-else>
                                    <strong> {{input.colour }} </strong>
                                </div>
                                <table class="catalog-table">
                                    <tr v-if="!input.is_collapsed">
                                        <td colspan="2"><strong>Lay/Bundle - </strong>{{ input.lay_no }}/{{ input.bundle_no }}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Qty</strong> {{ input.qty }}</td>
                                        <td><strong>Shade</strong> {{ input.shade }}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Size</strong></td>
                                        <td>{{ input.size }}</td>
                                    </tr>
                                </table>
                                <div class="catalog-footer">
                                    <strong>{{ input.panel }}</strong>
                                </div>    
                            </div>
                        </div>
                    </div>
                </div>
                <div style="width: 50%; border: 1px solid black; padding: 5px;">
                    <div style="display: flex; flex-wrap: wrap; gap: 5px;">
                        <div v-for="(input, index) in output_bundles" :key="index" class="catalog">
                            <div v-if="docstatus === 0" @click="delete_bundle(index)" class="cancel-style">✖</div>
                            <div v-if="docstatus === 0" @click="edit_bundle(index)" class="edit-style">✎</div>
                            <div class="catalog-content">
                                <div class="catalog-footer" v-if="input.set_combination">
                                    <strong> {{input.set_combination.major_colour }} </strong>
                                </div>
                                <div class="catalog-footer" v-else>
                                    <strong> {{input.colour }} </strong>
                                </div>
                                <table class="catalog-table">
                                    <tr v-if="!input.is_collapsed">
                                        <td colspan="2"><strong>Lay/Bundle - </strong>{{ input.lay_no }}/{{ input.bundle_no }}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Qty</strong> {{ input.qty }}</td>
                                        <td><strong>Shade</strong> {{ input.shade }}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Size</strong></td>
                                        <td>{{ input.size }}</td>
                                    </tr>
                                </table>
                                <div class="catalog-footer">
                                    <strong>{{ input.panel }}</strong>
                                </div>
                            </div>
                        </div>
                        <div class="catalog-new" v-if="docstatus == 0">
                            <button class="plus-btn-style" @click="addBundle(input)">➕ Add</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import {ref, onMounted, createApp} from 'vue';
import CutPanelMovementBundle from '../../Cut_Panel_Movement/components/CutPanelMovementBundle.vue';
import CutBundlePanelGroup from "./CutBundlePanelGroup.vue";


const root = ref(null)
let colour = ref(null)
let sample_doc = ref({})
let posting_date = cur_frm.doc.posting_date
let posting_time = cur_frm.doc.posting_time
let from_location = cur_frm.doc.warehouse
let lot = cur_frm.doc.lot
let fetched_data = ref([])
let input_bundles = ref([])
let output_bundles = ref([])
let sizes = ref([])
let panels = ref([])
let colours = ref([])
const bundleRef = ref(null)
let cur_set_comb = ref(null)
let docstatus = cur_frm.doc.docstatus

onMounted(()=> {
    if(docstatus == 0 && !cur_frm.is_new()){
        frappe.call({
            method: "production_api.production_api.doctype.cut_bundle_edit.cut_bundle_edit.get_major_colours",
            args: {
                posting_date: posting_date,
                posting_time: posting_time,
                from_location: from_location,
                lot: lot,
            },
            callback: function(r){
                let el = root.value
                colour.value = frappe.ui.form.make_control({
                    parent: $(el).find(".colour-field"),
                    df: {
                        fieldname: "colour",
                        fieldtype: "Select",
                        label: "Select Colour",
                        options: r.message.colours,
                    },
                    doc: sample_doc.value,
                    render_input: true,
                });
                sizes.value = r.message.sizes
                panels.value = r.message.panels
                colours.value = r.message.colours
                if(cur_frm.doc.colour){
                    colour.value.set_value(cur_frm.doc.colour)
                    colour.value.refresh()
                }
            }
        })
    }
})

function delete_bundle(index) {
    output_bundles.value.splice(index, 1)
    make_dirty()
}

function edit_bundle(index){
    cur_set_comb.value = output_bundles.value[index].set_combination
    addBundle(index)
}


function fetch_bundles(){
    if(cur_frm.is_dirty()){
        frappe.msgprint("Save the file before fetch bundles");
    }
    if(!colour.value.get_value()){
        frappe.msgprint("Select the Colour")
        return
    }
    input_bundles.value = []
    output_bundles.value = []
    make_dirty()
    frappe.call({
        method: "production_api.production_api.doctype.cut_panel_movement.cut_panel_movement.get_cut_bundle_unmoved_data",
        args: {
            from_location: from_location,
            lot: lot,
            posting_date: posting_date,
            posting_time: posting_time,
            movement_from_cutting: 0,
            bundle_colour: colour.value.get_value(), 
            get_collapsed: true,
        },
        callback: function(r){
            fetched_data.value = r.message || []
        }
    })
}

function make_dirty(){
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
}

function get_items(){
    let bundles = bundleRef.value?.getData()
    return {
        "bundles": bundles,
        "inputs": input_bundles.value,
        "outputs": output_bundles.value,
        "selected_colour": colour.value.get_value(),
    }    
}

function load_data(item){
    if(item.hasOwnProperty("json_data")){
        fetched_data.value = item['json_data']
    }
    if(item.hasOwnProperty("inputs")){
        input_bundles.value = item['inputs']
    }
    if(item.hasOwnProperty("outputs")){
        output_bundles.value = item['outputs']
    }
}

function fetch_selected_bundles(){
    let bundles = bundleRef.value?.getData()
    let data = []
    let inputs = []

    if(Object.keys(bundles['data']).length > 0){
        let part = bundles['data'][colour.value.get_value()]['part']
        let panels = bundles['panels']
        if(part){
            panels = panels[part]
        }
        data = bundles['data'][colour.value.get_value()]['data']
        for(let i = 0; i < data.length; i++){
            for(let j = 0; j < panels.length; j++){
                let panel = panels[j]
                if(data[i].hasOwnProperty(panel) && data[i][panel+"_moved"]){
                    inputs.push({
                        "lay_no": data[i]['lay_no'],
                        "bundle_no": data[i]['bundle_no'],
                        "qty": data[i][panel],
                        "panel": panel,
                        "set_combination": data[i]['set_combination'],
                        "shade": data[i]['shade'],
                        "size": data[i]['size'],
                        "colour": data[i][panel+"_colour"],
                        "is_collapsed": false,
                    })
                }
            }
        }
    }

    data = bundles['collapsed_details']
    if (data.length > 0 ){
        for(let i = 0; i < data.length; i++){
            if(data[i]['moved']){
                inputs.push({
                    "lay_no": data[i]['lay_no'],
                    "bundle_no": data[i]['bundle_no'],
                    "qty": data[i]["quantity"],
                    "panel": data[i]['panel'],
                    "set_combination": data[i]['set_combination'],
                    "shade": data[i]['shade'],
                    "size": data[i]['size'],
                    "colour": data[i]["colour"],
                    "is_collapsed": true,
                })
            }
        }
    }
    if(inputs.length == 0){
        frappe.msgprint("Select Bundles")
        return
    }
    make_dirty()
    input_bundles.value = inputs
}

function addBundle(index=-1){
    frappe.model.with_doctype("Cut Panel Item", function(){
        let data_fields = [
            {
                fieldtype: "Select",
                fieldname: "size",
                label: "Size",
                options: sizes.value,
                reqd: true,
            },
            {
                fieldtype: "Select",
                fieldname: "colour",
                label: "Colour",
                options: colours.value,
                reqd: true,
                onchange: function(){
                    if(d.get_value('colour') && d.get_value("panel")){
                        get_major_and_set_colour(d.get_value('colour'), d.get_value("panel"))
                    }
                }
            },
            {
                fieldtype: "Table MultiSelect",
                fieldname: "panel",
                label: "Selected Panels",
                options: "Cut Panel Item",
                reqd: true,
                onchange: function(){
                    if(d.get_value('colour') && d.get_value("panel")){
                        get_major_and_set_colour(d.get_value('colour'), d.get_value("panel"))
                    }
                },
                get_query() {
                    return {
                        filters: {
                            name: ["in", panels.value],
                        }
                    }
                }
            },
            {
                fieldtype: "Data",
                fieldname: "shade",
                label: "Shade",
                reqd: true,
            },
            {
                fieldtype: "Int",
                fieldname: "lay_no",
                label: "Lay No",
                reqd: true,
            },
            {
                fieldtype: "Int",
                fieldname: "bundle_no",
                label: "Bundle No",
                reqd: true,
            },
            {
                fieldtype: "Int",
                fieldname: "quantity",
                label: "Quantity",
                reqd: true,
            }
        ]
        if(index != -1){
            let val = output_bundles.value[index]
            let panel = val.panel.split(",")
            data_fields[0]['default'] = val.size
            data_fields[1]['default'] = val.colour
            data_fields[2]['default'] = panel.map(p => ({panel: p}))
            data_fields[3]['default'] = val.shade
            data_fields[4]['default'] = val.lay_no
            data_fields[5]['default'] = val.bundle_no
            data_fields[6]['default'] = val.qty
        }
        var d = new frappe.ui.Dialog({
            title: "Enter the below details to create new bundle",
            fields: data_fields,
            primary_action(values){
                d.hide()
                let fields = []
                if(cur_set_comb.value.hasOwnProperty("major_colour")){
                    let x = {
                        fieldname: "major_colour",
                        fieldtype: "Select",
                        options: colours.value,
                        label: "Major Colour",
                        reqd: true,
                    }
                    if(cur_set_comb.value.major_colour){
                        x['default'] = cur_set_comb.value.major_colour
                        x['read_only'] = true
                    }
                    fields.push(x)
                }
                if(cur_set_comb.value.hasOwnProperty("set_colour")){
                    let x = {
                        fieldname: "set_colour",
                        fieldtype: "Select",
                        options: colours.value,
                        label: "Set Colour",
                        reqd: true,
                    }
                    if(cur_set_comb.value.set_colour){
                        x['default'] = cur_set_comb.value.set_colour
                        x['read_only'] = true
                    }
                    fields.push(x)
                }
                let d2 = new frappe.ui.Dialog({
                    title: "Update or Verify the Set Colours",
                    fields: fields,
                    primary_action(val){
                        d2.hide()
                        make_dirty()
                        cur_set_comb.value.major_colour = val.major_colour
                        if(val.set_colour){
                            cur_set_comb.value.set_colour = val.set_colour
                        }
                        let p = ""
                        for(let i = 0; i < values.panel.length; i++){
                            p += values.panel[i]['panel'] + ","
                        }
                        p = p.slice(0, -1)
                        let bundle_val = {
                            "lay_no": values.lay_no,
                            "bundle_no": values.bundle_no,
                            "qty": values.quantity,
                            "panel": p,
                            "set_combination": cur_set_comb.value,
                            "shade": values.shade,
                            "size": values.size,
                            "colour": values.colour,
                        }
                        if(index != -1){
                            output_bundles.value[index] = bundle_val
                        }
                        else{
                            output_bundles.value.push(bundle_val)
                        }
                    }
                })
                d2.show()
            }
        })
        d.show()
    })
}

function get_major_and_set_colour(colour, panel){
    panel = panel[0]['panel']
    frappe.call({
        method: "production_api.production_api.doctype.cut_bundle_edit.cut_bundle_edit.get_major_set_colours",
        args: {
            colour: colour,
            panel: panel,
            lot: lot,
        },
        callback: function(r){
            cur_set_comb.value = r.message
        }
    })
}

function split_bundles(){
    if(input_bundles.value.length == 0){
        frappe.msgprint("No input bundles to split")
        return
    }
    let panels = []
    for(let i = 0; i < input_bundles.value.length; i++){
        if(panels.includes(input_bundles.value[i].panel)){
            continue
        }
        if(input_bundles.value[i].panel.split(",").length == 1){
            frappe.msgprint("Cannot split bundles with single panel")
            return
        }
        panels.push(input_bundles.value[i].panel)
    }
    let i;
    let d = new frappe.ui.Dialog({
        title: "Split Bundles",
        size: "extra-large",
        fields: [
            {
                fieldtype: "HTML",
                fieldname: "panel_group_html",
            },
        ],
        primary_action(){
            const panelGroupsData = i.panel_groups;
            Object.keys(panelGroupsData).forEach((panel_grp) => {
                let grp = panel_grp.split(",")
                let new_groups = []
                for(let j = 0; j < panelGroupsData[panel_grp].length; j++){
                    let panels = panelGroupsData[panel_grp][j].split(",")
                    for(let k = 0; k < panels.length; k++){
                        if(new_groups.includes(panels[k])){
                            frappe.throw(`Panel ${panels[k]} is already part of the group ${panel_grp}`)
                            return
                        }
                        new_groups.push(panels[k])
                    }
                }
                if(new_groups.length != grp.length){
                    frappe.throw(`Panel group ${panel_grp} does not have all panels selected`)
                    return
                }
            });
            output_bundles.value = []
            Object.keys(panelGroupsData).forEach((panel_grp) => {
                console.log(panel_grp)
                for(let j = 0; j < panelGroupsData[panel_grp].length; j++){
                    for(let k = 0; k < input_bundles.value.length; k++){
                        let bundle = input_bundles.value[k]
                        if(bundle.panel == panel_grp){
                            let new_bundle = Object.assign({}, bundle)
                            new_bundle.panel = panelGroupsData[panel_grp][j]
                            output_bundles.value.push(new_bundle)
                        }
                    }
                }
            });
            d.hide()
            make_dirty()
        }
    })
    d.fields_dict['panel_group_html'].$wrapper.html("")
    d.show()
    const el = d.fields_dict["panel_group_html"].$wrapper.get(0);
    const props = { panels: panels,};
    const vueApp = createApp(CutBundlePanelGroup, props);
    i = vueApp.mount(el);
}

defineExpose({
    load_data,
    get_items,
})

</script>
<style scoped>
.plus-btn-style{
    border: none;
    background: white;
}

.catalog-new {
    width: 150px;
    height: 150px;
    border: 1px solid #ccc;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 1px 1px 5px rgba(0, 0, 0, 0.1);
    background-color: #fff;
    box-sizing: border-box;
}

.catalog {
  position: relative;
  width: calc(33.33% - 8px);
  border: 1px solid #ccc;
  border-radius: 12px;
  background-color: #fff;
  box-shadow: 1px 1px 5px rgba(0, 0, 0, 0.1);
  font-family: sans-serif;
  padding: 5px;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  transition: box-shadow 0.2s ease;
}

.catalog-content {
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.catalog-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 8px;
}

.catalog-table {
  width: 100%;
  table-layout: fixed; /* This ensures equal column widths */
  border-collapse: collapse;
}

.catalog-table td {
  width: 50%;
  padding: 4px 6px;
  vertical-align: top;
  word-wrap: break-word;
}

.catalog-footer {
  text-align: center;
  font-weight: bold;
  font-size: 14px;
}

.cancel-style {
    position: absolute; 
    top: 6px; 
    right: 10px; 
    cursor: pointer; 
    font-weight: bold; 
    color: red; 
    font-size: 18px;
}

.edit-style {
    position: absolute; 
    top: 6px; 
    right: 27px; 
    cursor: pointer; 
    font-weight: bold; 
    color: red; 
    font-size: 18px;
}

</style>