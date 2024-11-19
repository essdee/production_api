// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting LaySheet", {
    refresh(frm) {
        frm.laysheet = new frappe.production.ui.LaySheetCloths(frm.fields_dict['cloths_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.item_details){
            frm.laysheet.load_data(frm.doc.__onload.item_details)
        }
        else{
            frm.laysheet.load_data([])
        }
        frm.set_df_property('cutting_laysheet_bundles','cannot_add_rows',true)
		frm.set_df_property('cutting_laysheet_bundles','cannot_delete_rows',true)
        if(frm.doc.cutting_laysheet_details.length > 0 && frm.doc.printed_time == null){
            frm.add_custom_button("Generate",()=> {
                frappe.call({
                    method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_parts",
                    args: {
                        cutting_marker: frm.doc.cutting_marker,
                    },
                    callback:function(r){
                        console.log(r.message)
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
                                })
                                d.hide()
                            }
                        })
                        d.show()
                    }
                })
            })
        }
        if(frm.doc.cutting_laysheet_bundles.length > 0 && frm.doc.printed_time == null ){
            frm.add_custom_button("Print Labels", ()=> {
                frappe.ui.form.qz_connect()
                    .then(function () {
                        return frappe.ui.form.qz_get_printer_list();
                    })
                    .then(function (printers) {
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
                    })
                    .catch(function (err) {
                        frappe.ui.form.qz_fail(err);
                    });
                })
        }
	},
    validate(frm){
        let items = frm.laysheet.get_items()
        frm.doc['item_details'] = JSON.stringify(items)
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
                    frm.save()
                }).catch((err)=>{
                    frm.set_value("printed_time",null)
                    frm.save()
                })
            }
        }
    })
}

