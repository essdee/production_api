// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Excel Sticker Print", {
	refresh(frm) {
        removeDefaultPrintEvent();
        $('[data-original-title=Print]').hide();
        $("li:has(a:has(span[data-label='Print']))").remove();

        if (frm.doc.docstatus === 1 && frm.doc.print_format) {
            frappe.call({
                method: 'production_api.production_api.doctype.excel_sticker_print.excel_sticker_print.get_raw_code',
                args: { doc_name: frm.doc.name },
                callback: function (r) {
                    let data = encodeURI(r.message.code);
                    const imageUrl = `http://api.labelary.com/v1/printers/12dpmm/labels/${r.message.width}x${r.message.height}/0/"${data}"`;
                    frm.fields_dict['print_preview_html'].df.options = `<img src=${imageUrl} style="border: 2px solid #000;">`
                    frm.fields_dict['print_preview_html'].refresh()
                }
            });

            frm.add_custom_button("Print", () => {
                frappe.ui.form.qz_connect()
                    .then(function () {
                        return frappe.ui.form.qz_get_printer_list();
                    })
                    .then(function (printers) {
                        frappe.call({
                            method: 'production_api.essdee_production.doctype.box_sticker_print.box_sticker_print.get_printer',
                            args: {
                                printers: printers,
                            },
                            callback: function (r) {
                                let d = new frappe.ui.Dialog({
                                    title: "Select any one printer",
                                    fields: [
                                        {
                                            fieldname: 'printer_list_html',
                                            fieldtype: 'HTML',
                                        }
                                    ],
                                    size: 'small',
                                    primary_action: function () {
                                        let printer_info = get_printer();
                                        if (printer_info) {
                                            d.hide();
                                            let printer = printer_info.printer.slice(1, -1);
                                            print_labels(frm, printer, printer_info.res);
                                        }
                                    }
                                });
                                d.fields_dict.printer_list_html.$wrapper.html('');
                                d.fields_dict.printer_list_html.$wrapper.append(get_printers_html(r.message));
                                d.show();
                            }
                        });
                    })
                    .catch(function (err) {
                        frappe.ui.form.qz_fail(err);
                    });
            }, "Actions");
        }
	}
});

function removeDefaultPrintEvent() {
    $(document).on('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && (e.key == "p" || e.charCode == 16 || e.charCode == 112 || e.keyCode == 80)) {
            e.cancelBubble = true;
            e.preventDefault();
            e.stopImmediatePropagation();
        }
    });
}

function get_printers_html(printers) {
    let htmlContent = `
        <table class="table table-bordered">
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
                <tr>
                    <td colspan="2" style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-weight: bold;">Select Printer Resolution</td>
                </tr>
                <tr>
                    <td colspan="2" style="padding: 10px; border: 1px solid #ddd;">
                        <label style="margin-right: 20px; cursor: pointer;"><input type="radio" class="printers-radio" name="printerOption" data-response="200dpi" checked> 200dpi</label>
                        <label style="cursor: pointer;"><input type="radio" class="printers-radio" name="printerOption" data-response="300dpi"> 300dpi</label>
                    </td>
                </tr>
            </tbody>
        </table>`;

    return htmlContent;
}

function get_printer() {
    let checkedCheckboxes = $(`.printers-checkbox-${0}:checked`);
    let printers_list = new Set();
    checkedCheckboxes.each(function () {
        let p = $(this).data('response');
        if (p != null) {
            printers_list.add(p);
        }
    });
    
    let selectedRes = $(`.printers-radio:checked`).data('response');

    if (printers_list.size == 0) {
        frappe.throw("Select a printer");
        return null;
    }
    else if (printers_list.size > 1) {
        console.log(printers_list)
        frappe.throw("Select only one printer");
        return null;
    }
    else {
        let prints = [...printers_list];
        return {
            printer: prints[0],
            res: selectedRes
        };
    }
}

function print_labels(frm, printer, res) {
    frappe.call({
        method: 'production_api.production_api.doctype.excel_sticker_print.excel_sticker_print.get_print_format',
        args: {
            doc_name: frm.doc.name,
            printer_res: res
        },
        callback: function (r) {
            if (r.message) {
                let config = qz.configs.create(printer);
                qz.print(config, [r.message]).then(() => {
                    frappe.show_alert({ message: __("Printed successfully"), indicator: 'green' });
                }).catch((err) => {
                    console.error(err);
                    frappe.msgprint(__("Printing failed: {0}", [err]));
                });
            }
        }
    });
}