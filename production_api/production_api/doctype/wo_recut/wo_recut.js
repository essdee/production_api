// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("WO Recut", {
  refresh(frm) {
    if (frm.is_new()) {
      frm.fields_dict["recut_items"].$wrapper.hide();
      return;
    }

    $(frm.fields_dict["recut_items"].wrapper).html("");
    frm.recut_items = new frappe.production.ui.Deliverables(
      frm.fields_dict["recut_items"].wrapper,
    );

    if (frm.doc.__onload && frm.doc.__onload.recut_item_details) {
      frm.doc["recut_item_details"] = JSON.stringify(
        frm.doc.__onload.recut_item_details,
      );
      frm.recut_items.load_data(frm.doc.__onload.recut_item_details);
    } else {
      frm.recut_items.load_data([]);
    }

    frm.recut_items.update_status(frm.doc.docstatus);

    frappe.production.ui.eventBus.$on("wo_updated", () => {
      frm.dirty();
    });
  },

  validate(frm) {
    if (!frm.is_new() && frm.recut_items) {
      let items = frm.recut_items.get_deliverables_data();
      frm.doc["recut_item_details"] = JSON.stringify(items);
    }
  },
});
