// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting LaySheet", {
    setup(frm){
        frm.set_query("cutting_marker", (doc)=> {
            if(!doc.cutting_plan){
                frappe.msgprint("Set the Cutting Plan First")
                return
            }
            return {
                filters:{
                    "cutting_plan":doc.cutting_plan,
                    "docstatus": 1,
                }
            }
        })
        frm.set_query("cutting_plan", ()=> {
            return{
                filters: {
                    "status":["!=","Completed"]
                }
            }
        })
    },
    refresh(frm) {
        // if (frappe.user.has_role('System Manager')){
        //     frm.add_custom_button("Update",()=> {
        //         frappe.call({
        //             method: "production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.update_cutting_plan",
        //             args : {
        //                 cutting_laysheet: frm.doc.name,
        //             }
        //         })
        //     })
        //     frm.add_custom_button("Make GRN Entry",()=> {
        //         frappe.call({
        //             method: "production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.create_grn_entry",
        //             args : {
        //                 doc_name: frm.doc.name,
        //             }
        //         })
        //     })
        // }
        removeDefaultPrintEvent();
        $('[data-original-title=Print]').hide();
        $("li:has(a:has(span[data-label='Print']))").remove();
        frm.laysheet = new frappe.production.ui.LaySheetCloths(frm.fields_dict['cloths_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.item_details){
            frm.laysheet.load_data(frm.doc.__onload.item_details)
        }
        else{
            frm.laysheet.load_data([])
        }

        frm.accessory = new frappe.production.ui.LaySheetAccessory(frm.fields_dict['accessory_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.item_accessories){
            frm.accessory.load_data(frm.doc.__onload.item_accessories)
        }
        else{
            frm.accessory.load_data([])
        }
        $(frm.fields_dict['cutting_marker_ratios_html'].wrapper).html("")
        if(!frm.doc.__islocal){
            frm.marker =new frappe.production.ui.CuttingMarker(frm.fields_dict['cutting_marker_ratios_html'].wrapper)
            frm.marker.load_data(frm.doc.__onload.marker_details)
        }

        frm.set_df_property('cutting_laysheet_bundles','cannot_add_rows',true)
		frm.set_df_property('cutting_laysheet_bundles','cannot_delete_rows',true)
        
        if(frm.doc.status != "Cancelled"){
            if(frm.doc.cutting_laysheet_details.length > 0 && (frm.doc.status == "Bundles Generated" || frm.doc.status == "Completed") ){
                frm.add_custom_button("Generate",()=> {
                    frappe.call({
                        method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_parts",
                        args: {
                            cutting_marker: frm.doc.cutting_marker,
                        },
                        callback:function(r){
                            let data = []
                            for(let i = 0 ; i < r.message.length ; i++){
                                data.push(
                                    {"part":r.message[i],"value":i+1},
                                )
                            }    
                            let d =  new frappe.ui.Dialog({
                                title : "Enter Details",
                                fields: [
                                    {
                                        fieldname:"parts_table",
                                        fieldtype:"Table",
                                        fields:[
                                            {"fieldname":'part',"fieldtype":"Data","read_only":true,"label":"Part","in_list_view":true},
                                            {"fieldname":"value","fieldtype":"Int","label":"Value","in_list_view":true}
                                        ],
                                        data:data,
                                        cannot_add_rows:true,
                                        cannot_delete_rows:true,
                                    },
                                    {
                                        fieldtype:"Int",
                                        fieldname:"maximum_no_of_plys",
                                        label:"Maximum No of Plys",
                                        default:frm.doc.maximum_no_of_plys,
                                        reqd:true,
                                    },
                                    {
                                        fieldname:"maximum_allow_percentage",
                                        fieldtype:"Int",
                                        label:"Maximum Allow Percent",
                                        default: frm.doc.maximum_allow_percentage,
                                        reqd:true,
                                    },
                                ],
                                primary_action:async function (values){
                                    frappe.call({
                                        method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_cut_sheet_data",
                                        args: {
                                            doc_name : frm.doc.name,
                                            cutting_marker:frm.doc.cutting_marker,
                                            item_details:frm.doc.cutting_laysheet_details,
                                            items:values.parts_table,
                                            max_plys:values.maximum_no_of_plys,
                                            maximum_allow : values.maximum_allow_percentage
                                        },
                                        freeze:true,
                                        freeze_message:"Generating Bundles",
                                        callback: function(){
                                            frm.reload_doc()
                                        }
                                    })
                                    d.hide()
                                }
                            })
                            d.show()
                        }
                    })
                })
            }
            if(frm.doc.cutting_laysheet_bundles.length > 0 && frm.doc.status == "Bundles Generated" ){
                frm.add_custom_button("Print Labels", ()=> {
                    frappe.call({
                        method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.update_cutting_plan",
                        args: {
                            cutting_laysheet: frm.doc.name, 
                            check_cp: true,
                        },
                        callback: function(){
                            frappe.ui.form.qz_connect().then(function () {
                                return frappe.ui.form.qz_get_printer_list();
                            }).then(function (printers) {
                                let d = new frappe.ui.Dialog({
                                    title:"Select any one printer",
                                    fields: [
                                        {
                                            fieldname: 'printer_list_html',
                                            fieldtype: 'HTML',
                                        }
                                    ],
                                    size:'small',
                                    primary_action_label:"Print",
                                    primary_action:function(){
                                        d.hide()
                                        let printer = get_printer()
                                        printer = printer.slice(1, -1);
                                        print_labels(frm,printer)
                                    }
                                })
                                d.fields_dict.printer_list_html.$wrapper.html('');
                                d.fields_dict.printer_list_html.$wrapper.append(get_printers_html(printers))
                                d.show()
                            }).catch(function (err) {
                                frappe.ui.form.qz_fail(err);
                            });
                        }
                    })
                }, "Print")
            }
            if(frm.doc.status == "Label Printed" || frm.doc.status == "Bundles Generated"){
                frm.add_custom_button("Print Movement Chart", ()=> {
                    let w = window.open(
                        frappe.urllib.get_full_url(
                            "/printview?" + "doctype=" + encodeURIComponent(frm.doc.doctype) + "&name=" +
                                encodeURIComponent(frm.doc.name) + "&trigger_print=1" + "&format=" + 
                                encodeURIComponent("Cutting Movement Chart") + "&no_letterhead=1"
                        )
                    );
                    if (!w) {
                        frappe.msgprint(__("Please enable pop-ups"));
                        return;
                    }
                }, "Print")
            }
            frm.add_custom_button("Print Laysheet", ()=> {
                let w = window.open(
                    frappe.urllib.get_full_url(
                        "/printview?" + "doctype=" + encodeURIComponent(frm.doc.doctype) + "&name=" +
                            encodeURIComponent(frm.doc.name) + "&trigger_print=1" + "&format=" + 
                            encodeURIComponent("Cutting LaySheet") + "&no_letterhead=1"
                    )
                );
                if (!w) {
                    frappe.msgprint(__("Please enable pop-ups"));
                    return;
                }
            }, "Print")
            if(frm.doc.status == "Label Printed" && frappe.user.has_role("System Manager")){
                frm.add_custom_button("Revert Labels", ()=> {
                    let d = new frappe.ui.Dialog({
                        title: "Are you sure want to Revert the Label",
                        primary_action_label : "Yes",
                        secondary_action_label: "No",
                        primary_action(){
                            d.hide()
                            frappe.call({
                                method: "production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.revert_labels",
                                args : {
                                    doc_name: frm.doc.name
                                },
                                freeze: true,
                                freeze_message:"Reverting the Label Printed",
                                callback: function(){
                                    frm.reload_doc()
                                }
                            })
                            d.hide()
                        },
                        secondary_action(){
                            d.hide()
                        }
                    })
                    d.show()
                })
            }
            if(frappe.user.has_role("System Manager")){
                if(frm.doc.reverted){
                    frm.add_custom_button("Update Status", ()=> {
                        let d = new frappe.ui.Dialog({
                            title: "Are you sure wanna update the Laysheet to Label Print Status",
                            primary_action_label: "Yes",
                            secondary_action_label: "No",
                            primary_action(){
                                d.hide()
                                frappe.call({
                                    method: "production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.update_label_print_status",
                                    args: {
                                        doc_name: frm.doc.name
                                    }
                                })
                            },
                            secondary_action(){
                                d.hide()
                            }
                        })
                        d.show()    
                    })
                }
                frm.add_custom_button("Cancel", ()=> {
                    let d = new frappe.ui.Dialog({
                        title: "Are you sure wanna cancel the Laysheet",
                        primary_action_label: "Yes",
                        secondary_action_label: "No",
                        primary_action(){
                            d.hide()
                            frappe.call({
                                method: "production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.cancel_laysheet",
                                args: {
                                    doc_name: frm.doc.name
                                }
                            })
                        },
                        secondary_action(){
                            d.hide()
                        }
                    })
                    d.show()
                })
            } 
        }
	},
    validate(frm){
        let items = frm.laysheet.get_items()
        frm.doc['item_details'] = JSON.stringify(items)
        let items2 = frm.accessory.get_items()
        frm.doc['item_accessory_details'] = JSON.stringify(items2)
    }
});

function get_printers_html(printers){
    let htmlContent = `
        <table>
            <thead>
                <tr>
                    <th style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-size: 15px;"></th>
                    <th style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-size: 15px;">Printer</th>
                </tr>
            </thead>
            <tbody>
    `;
    for (let i = 0; i < printers.length; i++) {
        htmlContent += `
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;"><input type="checkbox" class="printers-checkbox-${0}" data-response='${JSON.stringify(printers[i])}'></td>
                <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;">${printers[i]}</td>
            </tr>
        `;
    }

    htmlContent += `
                </tbody>
            </table>`

    return htmlContent
}

function removeDefaultPrintEvent(){
    $(document).on('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && (e.key == "p")) {
            e.preventDefault();
            e.stopImmediatePropagation();
        }  
    });
}

function get_printer(){
    let checkedCheckboxes = $(`.printers-checkbox-${0}:checked`);
    let printers_list = new Set()
    checkedCheckboxes.each(function() {
        let p = $(this).data('response')
        if(p!=null){
            printers_list.add(p);
        }
        $(this).data('response', null);
    });
    if(printers_list.size == 0){
        frappe.throw("Select a printer")
    }
    else if(printers_list.size > 1){
        frappe.throw("Select only one printer")
    }
    else{
        let prints = [...printers_list] 
        return prints[0]
    }
}

function print_labels(frm,printer){
    frappe.call({
        method:'production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.print_labels',
        args: {
            print_items: frm.doc.cutting_laysheet_bundles,
            lay_no:frm.doc.lay_no,
            cutting_plan: frm.doc.cutting_plan,
            doc_name:frm.doc.name,
        },
        callback: function(r){
            if(r.message){
                let config = qz.configs.create(printer)
                qz.print(config,[r.message]).then(()=> {
                    frm.set_value("printed_time",frappe.datetime.now_datetime())
                    frm.set_value("status","Label Printed")
                    frm.save()
                }).catch((err)=>{
                    frm.set_value("printed_time",null)
                    frm.save()
                })
            }
        }
    })
}

