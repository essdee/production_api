// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Box Sticker Print", {
    setup(frm){
        frm.set_query('size','box_sticker_print_details', ()=> {
            return {
                filters: {
                    attribute_name : 'Size'    
                }
            }
        })
        frm.set_query('fg_item',(doc)=> {
            return {
                filters: {
                    is_temp_item : 0,
                    disabled: 0,
                }
            }
        })
    },
    refresh(frm){
        removeDefaultPrintEvent();
        $('[data-original-title=Print]').hide();
        $("li:has(a:has(span[data-label='Print']))").remove();
        if(frm.doc.docstatus == 1){
            frm.add_custom_button("Print", ()=> {
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
                                },
                            ],
                            size:'small',
                            primary_action:function(){
                                d.hide()
                                let printer = get_printer()
                                let dialog = new frappe.ui.Dialog({
                                    title:"Select only one Item",
                                    fields: [
                                        {
                                            fieldname: 'item_list_html',
                                            fieldtype: 'HTML',
                                        },
                                    ],
                                    size:'large',
                                    primary_action_label:"Print",
                                    primary_action:async function(){
                                        let print_items =await get_print_items(frm)
                                        if(print_items.length > 0){
                                            dialog.hide()
                                            print_labels(frm,print_items, printer)
                                        }
                                    }
                                })
                                dialog.show()
                                dialog.fields_dict.item_list_html.$wrapper.html("")
                                dialog.fields_dict.item_list_html.$wrapper.append(get_item_list(frm.doc.box_sticker_print_details))
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
        if(frm.doc.print_format){
            frappe.call({
                method:'production_api.essdee_production.doctype.box_sticker_print.box_sticker_print.get_raw_code',
                args: {
                    doc_name: frm.doc.name,
                },
                callback: async function(r){
                    let data = encodeURI(r.message.code);
                    const imageUrl = `http://api.labelary.com/v1/printers/12dpmm/labels/${r.message.width}x${r.message.height}/0/"${data}"`
                    frm.fields_dict['preview'].df.options = `<img src=${imageUrl} style="border: 2px solid #000;">`
                    frm.fields_dict['preview'].refresh()
                }
            })
        }
    },
    lot(frm){
        if(!frm.doc.lot){
            frm.set_value('box_sticker_print_details',[])
        }
    },
    fg_item(frm){
        if(frm.doc.fg_item){
            frappe.call({
                method:'production_api.essdee_production.doctype.box_sticker_print.box_sticker_print.get_fg_details',
                args: {
                    fg_item: frm.doc.fg_item,
                },
                callback: function(r){
                    frm.set_value("box_sticker_print_details", r.message)
                }
            })
        }
        else{
            frm.set_value('box_sticker_print_details',[])
        } 
    }
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
    htmlContent += `
            </tbody>
        </table>
    `;
    return htmlContent
}

function get_item_list(items){
    let htmlContent = `
    <table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 18px; text-align: left;">
        <thead>
            <tr>
                <th style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-size: 15px;">S.No</th>
                <th style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-size: 15px;">Size</th>
                <th style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-size: 15px;">MRP</th>
                <th style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-size: 15px;">Total Quantity</th>
                <th style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-size: 15px;">Printed Quantity</th>
                <th style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-size: 15px;">Print Quantity</th>
            </tr>
        </thead>
        <tbody>
    `;

    for (let i = 0; i < items.length; i++) {
        htmlContent += `
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;">${i + 1}</td>
                <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;">${items[i].size}</td>
                <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;">${items[i].mrp}</td>
                <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;">${items[i].quantity}</td>
                <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;">${items[i].printed_quantity}</td>
                <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;">
                    <input type="number" class="quantity-input" data-response="${i}" style="width: 100%; padding: 5px; border: 1px solid #ccc;" />
                </td>
            </tr>
        `;
    }

    htmlContent += `
            </tbody>
        </table>
    `;

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

async function get_print_items(frm){
    let items = []
    document.querySelectorAll('.quantity-input').forEach(async (input, index) => {
        let itemIndex = input.getAttribute('data-response');
        let quantity = input.value || 0; 
        if(quantity > 0){
            items.push({
                quantity:quantity,
                size: frm.doc.box_sticker_print_details[itemIndex].size,
                mrp:frm.doc.box_sticker_print_details[itemIndex].mrp,
                doc_name:frm.doc.box_sticker_print_details[itemIndex].name,
            })
        }
        input.remove()
    })
    return items
}

function print_labels(frm,print_items, printer){
    frappe.call({
        method:'production_api.essdee_production.doctype.box_sticker_print.box_sticker_print.get_print_format',
        args: {
            print_format : frm.doc.print_format,
            piece_per_box: frm.doc.piece_per_box,
            fg_item: frm.doc.fg_item,
            printer:printer,
            lot:frm.doc.lot,
            use_item_name: frm.doc.use_item_name,
            print_items: print_items,
        },
        callback: function(r){
            if(r.message){
                let config = qz.configs.create(r.message.printer)
                qz.print(config,[r.message.print_format]).then().catch((err)=>{
                    frappe.call({
                        method:'production_api.essdee_production.doctype.box_sticker_print.box_sticker_print.override_print_quantity',
                        args: {
                            print_items: print_items,
                            print_format: frm.doc.print_format,
                        },
                    })
                })
            }
        }
    })
}
