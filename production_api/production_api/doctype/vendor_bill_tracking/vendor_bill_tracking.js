// Copyright (c) 2025, Aerele Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vendor Bill Tracking", {
  async refresh(frm) {
    if (!frm.is_new() && frm.doc.docstatus == 1) {
      let show_next_action = await can_show_actions(frm);
      if (show_next_action) {
        if (
          frm.doc.form_status == "Open" ||
          frm.doc.form_status == "Assigned" ||
          frm.doc.form_status == "Reopen" || frm.doc.form_status == 'Amended'
        ) {
          frm.add_custom_button(__("Assign"), () => {
            show_and_get_assignment(frm);
          });
        }
        frm.page.btn_secondary.hide();
        if (!frm.doc.purchase_invoice && !frm.doc.mrp_purchase_invoice) {
          frm.add_custom_button(__("Cancel"), () => {
            get_remarks_and_cancel(frm);
          });
          frm.add_custom_button(__("Create MRP PI"), () => {
            let x = frappe.model.get_new_doc("Purchase Invoice");
            x.supplier = frm.doc.supplier;
            x.bill_date = frm.doc.bill_date;
            x.bill_no = frm.doc.bill_no;
            x.vendor_bill_tracking = frm.doc.name;
            frappe.set_route("Form", x.doctype, x.name);
          });
          frm.add_custom_button(__("Create ERP PI"), () => {
            frappe.call({
              method:
                "production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.get_accounting_system_purchase_invoice",
              args: {
                doc_name: frm.doc.name,
              },
              callback: (r) => {
                const defaults = {
                  supplier: r.message.supplier,
                  bill_no: r.message.bill_no,
                  bill_date: r.message.bill_date,
                  doctype: r.message.doctype,
                  vendor_bill_tracking: r.message.vendor_bill_tracking,
                  action: "new",
                };
                const params = new URLSearchParams(defaults).toString();
                window.open(`${r.message.url}/app/erp-mrp-connector?${params}`);
              },
            });
          });
        }
      } else {
        if (frm.doc.assigned_to == frappe.user.name && frm.doc.form_status != 'Closed') {
          frm.add_custom_button(__("Bill Recieved"), () => {
            frappe.call({
              "method" : "production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.make_bill_recieved_acknowledgement",
              "args" : {
                "doc_name" : frm.doc.name
              },
              "callback" : (r)=>{
                frm.reload_doc();
              }
            })
          });
        }
      }
    }
  }
});

async function can_show_actions(frm){
  if(!frm.doc.assigned_to){
    return true;
  }
  let last_item = null;
  for(let i=0;i<frm.doc.vendor_bill_tracking_history.length;i++){
    if(frm.doc.vendor_bill_tracking_history[i]['assigned_to'] == frm.doc.assigned_to){
      last_item = frm.doc.vendor_bill_tracking_history[i];
    }
  }
  if(!last_item){
    return true;
  }
  if(last_item['received']){
    return true;
  }
  return false;
}

function get_remarks_and_cancel(frm) {
  let dialog = new frappe.ui.Dialog({
    title: "Cancelling...",
    fields: [
      {
        label: "Cancel Reason",
        fieldname: "cancel_reason",
        fieldtype: "Small Text",
        reqd: 1,
      },
    ],
    primary_action_label: "Cancel",
    primary_action: (values) => {
      make_cancel_action(values["cancel_reason"]);
      dialog.hide();
    },
  });
  dialog.show();
}

function make_cancel_action(reason) {
  frappe.call({
    method:
      "production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.cancel_vendor_bill",
    freeze: true,
    freeze_msg: "Cancelling Document",
    args: {
      name: cur_frm.doc.name,
      cancel_reason: reason,
    },
    callback: (response) => {
      cur_frm.reload_doc();
    },
  });
}

function show_and_get_assignment(frm) {
  let dialog = new frappe.ui.Dialog({
    title: "Assign Vendor Bill",
    fields: [
      {
        label: "Assigned To",
        fieldname: "assigned_to",
        fieldtype: "Link",
        options: "User",
        reqd: 1,
      },
      {
        label: "Remarks",
        fieldname: "remarks",
        fieldtype: "Small Text",
      },
    ],
    primary_action_label: "Submit",
    primary_action: (values) => {
      make_assignement_action(values);
      dialog.hide();
    },
  });
  dialog.show();
}

function make_assignement_action(values) {
  frappe.call({
    method:
      "production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.assign_vendor_bill",
    freeze: true,
    freeze_msg: "Assigning Document",
    args: {
      name: cur_frm.doc.name,
      assigned_to: values["assigned_to"],
      remarks: values["remarks"],
    },
    callback: (response) => {
      cur_frm.reload_doc();
    },
  });
}
