// Copyright (c) 2025, Aerele Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vendor Bill Tracking", {
  refresh(frm) {
    if (!frm.is_new() && frm.doc.docstatus == 1) {
      if (
        frm.doc.form_status == "Open" ||
        frm.doc.form_status == "Assigned" ||
        frm.doc.form_status == "Reopen"
      ) {
        frm.add_custom_button(__("Assign"), () => {
          show_and_get_assignment(frm);
        });
      }
      // else if (frm.doc.form_status == "Closed" && !frm.doc.purchase_invoice) {
      // const reopenable_roles = [
      //   "System Manager",
      //   "Administrator",
      //   "Accounts Manager",
      // ];
      // for (let i = 0; i < reopenable_roles.length; i++) {
      //   if (frappe.user_roles.includes(reopenable_roles[i])) {
      //     add_reopen_button(frm);
      //     break;
      //   }
      // }
      // }
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
    }
  },
  new_supplier(frm) {
    if (frm.doc.new_supplier) {
      frm.doc.supplier = null;
      frm.toggle_display("supplier", false);
    } else {
      frm.toggle_display("supplier", true);
    }
  },
});

// function add_reopen_button(frm) {
//   frm.add_custom_button(__("Reopen"), () => {
//     let dialog = new frappe.ui.Dialog({
//       title: "Reopen Vendor Bill Tracking",
//       fields: [
//         {
//           label: "Reopen Reason",
//           fieldname: "reopen_reason",
//           fieldtype: "Small Text",
//           reqd: 1,
//         },
//         {
//           label: "Assigned To",
//           fieldname: "assigned_to",
//           fieldtype: "Link",
//           reqd: 1,
//           options: "User",
//         },
//       ],
//       primary_action_label: "Reopen And Assign",
//       primary_action: (values) => {
//         dialog.hide();
//         frappe.call({
//           method:
//             "production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.reopen_vendor_bill",
//           args: {
//             name: frm.doc.name,
//             remarks: values["reopen_reason"],
//             assigned_to: values["assigned_to"],
//           },
//           freeze: true,
//           freeze_msg: "Reopening form",
//           callback: (r) => {
//             frm.reload_doc();
//           },
//         });
//       },
//     });
//     dialog.show();
//   });
// }

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
