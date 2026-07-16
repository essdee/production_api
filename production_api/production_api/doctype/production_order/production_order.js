// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production Order", {
  setup(frm) {
    frm.set_query("production_term", (doc) => {
      return {
        filters: {
          docstatus: 1,
        },
      };
    });
  },
  refresh(frm) {
    render_production_order_editor(frm);
    const is_submitted = frm.doc.docstatus == 1;
    frm.set_df_property("delivery_date", "read_only", is_submitted);
    frm.set_df_property("dont_deliver_after", "read_only", is_submitted);

    if (frm.doc.docstatus == 1) {
      frm.add_custom_button("Update Price", () => {
        let d = new frappe.ui.Dialog({
          title: "Update Price",
          size: "extra-large",
          fields: [
            {
              fieldname: "price_html",
              fieldtype: "HTML",
            },
          ],
          primary_action: function () {
            let res = frm.pop_up.get_data();
            frappe.call({
              method:
                "production_api.production_api.doctype.production_order.production_order.update_price",
              args: {
                production_order: frm.doc.name,
                item_details: res,
              },
              callback: function (response) {
                frm.reload_doc();
                frappe.show_alert({
                message: __("Price update completed"),
                indicator: "green",
                  });
              },
            });
            d.hide();
          },
        });
        frm.pop_up = new frappe.production.ui.UpdatePrice(
          d.fields_dict.price_html.$wrapper,
        );
        frappe.call({
          method:
            "production_api.production_api.doctype.production_order.production_order.get_price_update_context",
          args: {
            production_order: frm.doc.name,
          },
          callback: function (response) {
            frm.pop_up.load_data(response.message || {});
            d.show();
          },
        });
      });

      frm.add_custom_button("Change Dates", () => {
        const get_current_date = () =>
          d.get_value("date_field") == "Don't Deliver After"
            ? frm.doc.dont_deliver_after
            : frm.doc.delivery_date;
        let d = new frappe.ui.Dialog({
          title: "Change Production Order Date",
          fields: [
            {
              fieldname: "date_field",
              fieldtype: "Select",
              label: "Date to Change",
              options: "Delivery Date\nDon't Deliver After",
              default: "Delivery Date",
              reqd: 1,
              onchange: function () {
                let current_date = get_current_date();
                d.set_value("old_date", current_date);
                d.set_value("new_date", current_date);
              },
            },
            {
              fieldname: "old_date",
              fieldtype: "Date",
              label: "Old Date",
              default: frm.doc.delivery_date,
              read_only: 1,
            },
            {
              fieldname: "new_date",
              fieldtype: "Date",
              label: "New Date",
              default: frm.doc.delivery_date,
              reqd: 1,
            },
            {
              fieldname: "reason",
              fieldtype: "Small Text",
              label: "Reason",
              reqd: 1,
            },
          ],
          primary_action_label: "Update",
          primary_action: function () {
            let values = d.get_values();
            if (!values) return;

            frappe.call({
              method:
                "production_api.production_api.doctype.production_order.production_order.update_production_order_date",
              args: {
                production_order: frm.doc.name,
                date_field: values.date_field,
                new_date: values.new_date,
                reason: values.reason,
              },
              callback: function () {
                d.hide();
                frm.reload_doc();
                frappe.show_alert({
                  message: __("Date change tracked"),
                  indicator: "green",
                });
              },
            });
          },
        });
        d.show();
      }, "Change");

      frm.add_custom_button("Change Status", () => {
        let d = new frappe.ui.Dialog({
          title: "Change Production Order Status",
          fields: [
            {
              fieldname: "new_status",
              fieldtype: "Select",
              label: "New Status",
              options: "Open\nItem Changed\nNot Processed",
              default: frm.doc.status,
              reqd: 1,
            },
            {
              fieldname: "reason",
              fieldtype: "Small Text",
              label: "Reason",
              reqd: 1,
            },
          ],
          primary_action_label: "Update",
          primary_action: function () {
            let values = d.get_values();
            if (!values) return;

            frappe.call({
              method:
                "production_api.production_api.doctype.production_order.production_order.change_status",
              args: {
                production_order: frm.doc.name,
                new_status: values.new_status,
                reason: values.reason,
              },
              callback: function () {
                d.hide();
                frm.reload_doc();
                frappe.show_alert({
                  message: __("Status updated"),
                  indicator: "green",
                });
              },
            });
          },
        });
        d.show();
      }, "Change");

      if (!(frm.doc.production_ordered_details || []).length) {
        frm.add_custom_button("Update Quantity", () => {
          frappe.call({
            method:
              "production_api.production_api.doctype.production_order.production_order.get_production_order_details",
            args: {
              production_order: frm.doc.name,
            },
            callback: function (r) {
              show_update_quantity_dialog(frm, r.message || {});
            },
          });
        });
      }

      frm.add_custom_button("Create Lot", () => {
        let d = new frappe.ui.Dialog({
          title: "Create Lot",
          fields: [
            {
              fieldname: "lot_name",
              fieldtype: "Data",
              label: "Lot Name",
              reqd: 1,
            },
          ],
          primary_action: function () {
            let values = d.get_values();
            if (!values) return;

            frappe.call({
              method:
                "production_api.production_api.doctype.production_order.production_order.create_lot",
              args: {
                production_order: frm.doc.name,
                lot_name: values.lot_name,
              },
              callback: function (response) {
                d.hide();
                frappe.open_in_new_tab = true;
                frappe.set_route("Form", "Lot", response.message);
              },
            });
          },
        });
        d.show();
      }, "Lot");
      if (!frappe.perm.has_perm("Production Order", 0, "submit")) {
        frm.set_df_property("comments", "read_only", true);
        frm.refresh_field("comments");
      }
      frm.add_custom_button("Print", () => {
        window.open(
          frappe.urllib.get_full_url(
            "/printview?doctype=Production Order" +
              "&name=" +
              encodeURIComponent(frm.doc.name) +
              "&format=Production Order" +
              "&trigger_print=1",
          ),
          "_blank",
        );
      });
      frm.add_custom_button("Link Lot", () => {
        let d = new frappe.ui.Dialog({
          title: "Link Lot",
          fields: [
            {
              fieldname: "lot_name",
              fieldtype: "Link",
              label: "Lot Name",
              reqd: 1,
              options: "Lot",
            },
          ],
          primary_action: function () {
            let values = d.get_values();
            if (!values) return;

            frappe.call({
              method:
                "production_api.production_api.doctype.production_order.production_order.link_lot",
              args: {
                production_order: frm.doc.name,
                lot_name: values.lot_name,
              },
              callback: function (response) {
                d.hide();
                frappe.open_in_new_tab = true;
                frappe.set_route("Form", "Lot", values.lot_name);
              },
            });
          },
        });
        d.show();
      }, "Lot");
    }
  },
  item(frm) {
    render_production_order_editor(frm);
  },
  validate(frm) {
    if (frm.doc.item && frm.packed_item) {
      let items = frm.packed_item.get_data();
      frm.doc["item_details"] = JSON.stringify(items);
    } else {
      frappe.throw(__("Please refresh and try again."));
    }
  },
});

function show_update_quantity_dialog(frm, size_details) {
  // size_details comes from get_production_order_details: {size: {qty, ...}}
  // in the same size order as the rendered grid.
  const sizes = Object.keys(size_details);
  if (!sizes.length) {
    frappe.msgprint(__("Production Order has no size details to update"));
    return;
  }

  let d = null;
  const update_total = () => {
    let total = 0;
    sizes.forEach((size, idx) => {
      total += cint(d.get_value("qty_" + idx));
    });
    d.set_value("total_quantity", total);
  };

  let fields = sizes.map((size, idx) => ({
    fieldname: "qty_" + idx,
    fieldtype: "Int",
    label: size,
    default: cint(size_details[size].qty),
    reqd: 1,
    onchange: update_total,
  }));
  fields.push(
    {
      fieldname: "total_quantity",
      fieldtype: "Int",
      label: "Total",
      read_only: 1,
      default: sizes.reduce((total, size) => total + cint(size_details[size].qty), 0),
    },
    {
      fieldname: "requested_by",
      fieldtype: "Select",
      label: "Who Told to Change",
      options: "Sales Team\nProduction Team\nMerch Team",
      reqd: 1,
    },
    {
      fieldname: "reason",
      fieldtype: "Small Text",
      label: "Reason",
      reqd: 1,
    },
  );

  d = new frappe.ui.Dialog({
    title: "Update Quantity",
    fields: fields,
    primary_action_label: "Update",
    primary_action: function () {
      let values = d.get_values();
      if (!values) return;

      let size_quantities = {};
      sizes.forEach((size, idx) => {
        size_quantities[size] = values["qty_" + idx];
      });

      frappe.call({
        method:
          "production_api.production_api.doctype.production_order.production_order.update_quantity",
        args: {
          production_order: frm.doc.name,
          size_quantities: size_quantities,
          requested_by: values.requested_by,
          reason: values.reason,
        },
        callback: function () {
          d.hide();
          frm.reload_doc();
          frappe.show_alert({
            message: __("Quantity updated"),
            indicator: "green",
          });
        },
      });
    },
  });
  d.show();
}

function render_production_order_editor(frm) {
  let details_field = frm.fields_dict["details_html"];
  if (!details_field) return;

  details_field.$wrapper.html("");
  frm.packed_item = null;

  if (!frm.doc.item) return;

  frm.packed_item = new frappe.production.ui.ProductionOrder(
    details_field.wrapper,
  );
  frappe.call({
    method:
      "production_api.production_api.doctype.production_order.production_order.get_order_editor_context",
    args: {
      item: frm.doc.item,
      production_order: frm.is_new()
        ? frm.doc.amended_from || null
        : frm.doc.name,
    },
    callback: function (response) {
      let context = response.message || {};
      frm.doc["item_details"] = JSON.stringify(context.items || {});
      if (frm.packed_item) {
        frm.packed_item.load_data(context);
      }
    },
  });
}
