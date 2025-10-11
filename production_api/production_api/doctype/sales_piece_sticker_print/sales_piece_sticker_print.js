// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Piece Sticker Print", {
	refresh(frm) {
        removeDefaultPrintEvent();
        $('[data-original-title=Print]').hide();
        $("li:has(a:has(span[data-label='Print']))").remove();
        frm.set_df_property("sales_piece_sticker_print_details", "cannot_add_rows", true)
        frm.set_df_property("sales_piece_sticker_print_details", "cannot_delete_rows", true)
        if(frm.doc.print_format){
            frm.add_custom_button("Print", ()=> {
                frappe.ui.form.qz_connect()
                    .then(function () {
                        return frappe.ui.form.qz_get_printer_list();
                    })
                    .then(function (printers) {
                        frappe.call({
                            method:'production_api.essdee_production.doctype.box_sticker_print.box_sticker_print.get_printer',
                            args: {
                                printers: printers,
                            },
                            callback: function(r){
                                let d = new frappe.ui.Dialog({
                                    title:"Select any one printer",
                                    fields: [
                                        {
                                            fieldname: 'printer_list_html',
                                            fieldtype: 'HTML',
                                        }
                                    ],
                                    size:'small',
                                    primary_action:function(){
                                        d.hide()
                                        let printer = get_printer()
                                        print_labels(frm, printer)
                                    }
                                })
                                d.fields_dict.printer_list_html.$wrapper.html('');
                                d.fields_dict.printer_list_html.$wrapper.append(get_printers_html(r.message))
                                d.show()
                            }
                        })
                    })
                    .catch(function (err) {
                        frappe.ui.form.qz_fail(err);
                    });
            })
        }
	},
});

function removeDefaultPrintEvent(){
    $(document).on('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && (e.key == "p" || e.charCode == 16 || e.charCode == 112 || e.keyCode == 80)) {
            e.cancelBubble = true;
            e.preventDefault();
            e.stopImmediatePropagation();
        }  
    });
}


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

    htmlContent += `<tr>
                        <td></td>
                        <td>&nbsp;</td>
                    </tr>
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

function print_labels(frm, printer){
    frappe.call({
        method:'production_api.production_api.doctype.sales_piece_sticker_print.sales_piece_sticker_print.get_print_format',
        args: {
            doc_name : frm.doc.name, 
        },
        callback: function(r){
            if(r.message){
                let config = qz.configs.create(printer)
                qz.print(config,[r.message]).then().catch((err)=>{
                    
                })
            }
        }
    })
}