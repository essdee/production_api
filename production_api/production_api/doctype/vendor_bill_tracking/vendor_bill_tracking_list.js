frappe.listview_settings["Vendor Bill Tracking"] = {
  refresh: (frm) => {
    frm.page.add_inner_button(__("Show Assigned To Me"), () => {
      frappe.call({
        method: "production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.get_bills_assigned_to_me",
        callback: async (r) => {
            if(r.message && r.message.length != 0){
                await frm.filter_area.set([['Vendor Bill Tracking', 'name', 'in', r.message]]);
                frm.refresh();
            } else {
                frappe.msgprint("Nothing Assigned To You");
            }
        },
      });
    });
  },
};
