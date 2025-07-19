// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cut Bundle Edit", {
	refresh(frm) {
        frm.page.btn_secondary.hide()
        $(".layout-side-section").css("display", "None");
        if(frm.is_new() || frm.doc.docstatus == 2){
            $(frm.fields_dict['cut_bundles_html'].wrapper).html("")
            return
        }
        frm.cut_bundle = new frappe.production.ui.CutBundleEdit(frm.fields_dict['cut_bundles_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.movement_json){
            frm.cut_bundle.load_data(frm.doc.__onload.movement_json)
        }
        if(frm.doc.docstatus == 1){
            frm.add_custom_button("Cancel", ()=> {
                frm._cancel()
            })
            if(!frm.doc.printed_time){
                frm.add_custom_button("Print Labels", ()=> {
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
                })
            }
        }
    },
    validate(frm){
        if(frm.cut_bundle && !frm.is_new()){
            frm.doc['movement_data'] = frm.cut_bundle.get_items()
        }
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
        method:'production_api.production_api.doctype.cut_bundle_edit.cut_bundle_edit.print_labels',
        args: {
            doctype: frm.doc.doctype,
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

