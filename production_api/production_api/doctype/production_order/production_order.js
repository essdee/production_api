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
      const has_transfer_marker = !!frappe.meta.has_field(
        "Production Order",
        "transferred_to_ppo",
      );
      const is_transferred =
        has_transfer_marker && !!frm.doc.transferred_to_ppo;
      const has_pending_change_request =
        frm.doc.status === "Pending Request" ||
        !!frm.doc.quantity_ratio_request ||
        !!frm.doc.status_change_request;
      const incoming_transfer_request =
        (frm.doc.__onload || {}).incoming_quantity_transfer_request || {};
      const has_pending_incoming_transfer =
        !!frm.doc.incoming_quantity_transfer_request;
      const is_status_change_locked = ["Item Changed", "Not Processed"].includes(
        frm.doc.status,
      );

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

      if (
        !is_transferred &&
        !has_pending_change_request &&
        !has_pending_incoming_transfer &&
        !is_status_change_locked
      ) {
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
                callback: function (r) {
                  d.hide();
                  frm.reload_doc();
                  const approval_required =
                    (r.message || {}).approval_required;
                  frappe.show_alert({
                    message: approval_required
                      ? __("Status change sent for approval")
                      : __("Status updated"),
                    indicator: approval_required ? "orange" : "green",
                  });
                },
              });
            },
          });
          d.show();
        }, "Change");
      }

      if (
        frm.doc.status === "Pending Request" &&
        !has_pending_incoming_transfer &&
        (frm.doc.__onload || {}).can_approve_production_order_request
      ) {
        const request =
          (frm.doc.__onload || {}).pending_production_order_request || {};
        const is_status_request = request.request_type === "status";
        const approval_label = is_status_request
          ? __("Approve {0}", [request.requested_status])
          : __("Approve Quantity Changed");
        frm.add_custom_button(
          approval_label,
          () => {
            if (is_status_request) {
              show_approve_status_change_dialog(frm, request);
            } else {
              show_approve_quantity_ratio_dialog(frm, request);
            }
          },
          __("Change"),
        );
      }

      if (
        has_pending_incoming_transfer &&
        (frm.doc.__onload || {}).can_approve_quantity_transfer_request
      ) {
        frm.add_custom_button(
          __("Approve Transfer Quantity"),
          () => {
            show_approve_quantity_transfer_dialog(
              frm,
              incoming_transfer_request,
            );
          },
          __("Change"),
        );
      }

      // transferred_to_ppo ships with the doctype, so on a bench that has not migrated
      // yet the value reads as undefined and the one-shot guard would wave everyone
      // through - check the field exists before offering the button at all.
      const alternative_items = (frm.doc.__onload || {}).alternative_items || [];
      if (
        has_transfer_marker &&
        !frm.doc.transferred_to_ppo &&
        !has_pending_incoming_transfer &&
        ["Item Changed", "Not Processed"].includes(frm.doc.status) &&
        alternative_items.length &&
        !(frm.doc.production_ordered_details || []).length
      ) {
        frm.add_custom_button(
          __("Transfer Quantity"),
          () => {
            show_transfer_quantity_dialog(frm, alternative_items);
          },
          "Change",
        );
      }

      if (
        frm.doc.status === "Open" &&
        !is_transferred &&
        !has_pending_change_request &&
        !has_pending_incoming_transfer &&
        !(frm.doc.production_ordered_details || []).length
      ) {
        frm.add_custom_button("Update Quantity & Ratio", () => {
          frappe.call({
            method:
              "production_api.production_api.doctype.production_order.production_order.get_production_order_details",
            args: {
              production_order: frm.doc.name,
            },
            callback: function (r) {
              show_update_qty_ratio_dialog(frm, r.message || {});
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

// Render a horizontal size grid into a dialog HTML field wrapper: sizes across
// the top as a header row (with a leading "Size" corner cell), then one labeled
// input row per entry in `rows`. Each row is
//   { key, label, values: {size: value}, step: "1"|"any", parse, onInput? }
// where the leading column holds the row's label and `key` tags each input so
// read_size_grid_values can read that row back.
function build_horizontal_size_grid($wrapper, sizes, rows) {
  $wrapper.empty();

  const $container = $(
    '<div class="po-size-grid-wrap" style="overflow-x:auto; margin-bottom:12px;"></div>',
  );
  const $table = $(
    '<table class="po-size-grid table table-bordered" style="margin-bottom:0; width:auto; min-width:100%;"></table>',
  );

  const $thead = $("<thead></thead>");
  const $headRow = $("<tr></tr>");
  $("<th></th>")
    .text("Size")
    .css({
      "text-align": "left",
      "white-space": "nowrap",
      "font-size": "11px",
    })
    .appendTo($headRow);
  sizes.forEach((size) => {
    $("<th></th>")
      .text(size)
      .css({
        "text-align": "center",
        "white-space": "nowrap",
        "font-size": "11px",
      })
      .appendTo($headRow);
  });
  $thead.append($headRow);

  const $tbody = $("<tbody></tbody>");
  rows.forEach((row) => {
    const $tr = $("<tr></tr>");
    $("<td></td>")
      .text(row.label)
      .css({
        "font-weight": "bold",
        "white-space": "nowrap",
        "vertical-align": "middle",
      })
      .appendTo($tr);
    sizes.forEach((size) => {
      const $td = $("<td></td>").css({ padding: "3px" });
      const $input = $('<input type="number" class="form-control input-sm" />')
        .attr("data-size", size)
        .attr("data-row", row.key)
        .attr("step", row.step || "1")
        .attr("min", "0")
        .css({ "text-align": "center", "min-width": "64px" });
      const initVal = row.values ? row.values[size] : undefined;
      if (initVal !== undefined && initVal !== null) {
        $input.val(initVal);
      }
      if (row.onInput) {
        $input.on("input", row.onInput);
      }
      $td.append($input);
      $tr.append($td);
    });
    $tbody.append($tr);
  });

  $table.append($thead).append($tbody);
  $container.append($table);
  $wrapper.append($container);
}

// Read one grid row's inputs (selected by row key) back into {size: value}.
// HTML-field inputs are NOT surfaced by d.get_values(), so they must be read
// from the DOM. `parse` is cint for quantities, flt for ratios.
function read_size_grid_values($wrapper, key, parse) {
  const values = {};
  $wrapper.find('input[data-row="' + key + '"]').each(function () {
    const size = $(this).attr("data-size");
    values[size] = parse($(this).val());
  });
  return values;
}

function show_update_qty_ratio_dialog(frm, size_details) {
  // size_details comes from get_production_order_details: {size: {qty, ratio, ...}}
  // in the same size order as the rendered grid.
  const sizes = Object.keys(size_details);
  if (!sizes.length) {
    frappe.msgprint(__("Production Order has no size details to update"));
    return;
  }

  let d = null;
  const recompute_total = () => {
    const vals = read_size_grid_values(
      d.fields_dict.size_grid.$wrapper,
      "quantity",
      cint,
    );
    let total = 0;
    sizes.forEach((size) => {
      total += cint(vals[size]);
    });
    d.set_value("total_quantity", total);
  };

  const initial_qty = {};
  const initial_ratio = {};
  sizes.forEach((size) => {
    initial_qty[size] = cint(size_details[size].qty);
    initial_ratio[size] = flt(size_details[size].ratio);
  });
  const initial_total = sizes.reduce(
    (total, size) => total + initial_qty[size],
    0,
  );

  d = new frappe.ui.Dialog({
    title: "Update Quantity & Ratio",
    size: "large",
    fields: [
      {
        fieldname: "size_grid",
        fieldtype: "HTML",
      },
      {
        fieldname: "total_quantity",
        fieldtype: "Int",
        label: "Total Quantity",
        read_only: 1,
        default: initial_total,
      },
      {
        fieldname: "requested_by",
        fieldtype: "Select",
        label: "Who Told to Change",
        options: "Sales Team\nPlanning Team\nMerch Team",
        reqd: 1,
      },
      {
        fieldname: "reason",
        fieldtype: "Small Text",
        label: "Reason",
        reqd: 1,
      },
    ],
    primary_action_label: "Request Approval",
    primary_action: function () {
      let values = d.get_values();
      if (!values) return;

      let size_quantities = read_size_grid_values(
        d.fields_dict.size_grid.$wrapper,
        "quantity",
        cint,
      );
      let size_ratios = read_size_grid_values(
        d.fields_dict.size_grid.$wrapper,
        "ratio",
        flt,
      );

      frappe.call({
        method:
          "production_api.production_api.doctype.production_order.production_order.update_quantity_and_ratio",
        args: {
          production_order: frm.doc.name,
          size_quantities: size_quantities,
          size_ratios: size_ratios,
          requested_by: values.requested_by,
          reason: values.reason,
        },
        callback: function () {
          d.hide();
          frm.reload_doc();
          frappe.show_alert({
            message: __("Quantity & ratio update sent for approval"),
            indicator: "orange",
          });
        },
      });
    },
  });

  build_horizontal_size_grid(d.fields_dict.size_grid.$wrapper, sizes, [
    {
      key: "quantity",
      label: "Quantity",
      values: initial_qty,
      step: "1",
      parse: cint,
      onInput: recompute_total,
    },
    {
      key: "ratio",
      label: "Ratio",
      values: initial_ratio,
      step: "any",
      parse: flt,
    },
  ]);
  d.show();
}

function build_quantity_approval_preview($wrapper, request) {
  const display_value = (value) => String(value == null ? 0 : value);
  const requested_quantities = request.requested_quantities || {};
  const requested_ratios = request.requested_ratios || {};
  const original_quantities = request.original_quantities || {};
  const original_ratios = request.original_ratios || {};
  const sizes = Object.keys(requested_quantities).filter(
    (size) =>
      flt(original_quantities[size]) !== flt(requested_quantities[size]) ||
      flt(original_ratios[size]) !== flt(requested_ratios[size]),
  );

  $wrapper.empty();
  const $table = $(
    '<table class="table table-bordered" style="margin-bottom:0;"></table>',
  );
  const $head = $("<tr></tr>");
  [__("Size"), __("Quantity"), __("Ratio")].forEach((label) => {
    $("<th></th>").text(label).appendTo($head);
  });
  const $body = $("<tbody></tbody>");
  sizes.forEach((size) => {
    const $row = $("<tr></tr>");
    $("<td></td>").text(size).appendTo($row);
    $("<td></td>")
      .text(
        display_value(original_quantities[size]) +
          " -> " +
          display_value(requested_quantities[size]),
      )
      .appendTo($row);
    $("<td></td>")
      .text(
        display_value(original_ratios[size]) +
          " -> " +
          display_value(requested_ratios[size]),
      )
      .appendTo($row);
    $body.append($row);
  });
  $table.append($("<thead></thead>").append($head)).append($body);
  $wrapper.append(
    $('<div style="overflow-x:auto;"></div>').append($table),
  );
}

function show_approve_quantity_ratio_dialog(frm, request) {
  if (!request.requested_quantities) {
    frappe.msgprint(__("Pending request details are missing"));
    return;
  }

  const d = new frappe.ui.Dialog({
    title: __("Approve Quantity Changed"),
    size: "large",
    fields: [
      {
        fieldname: "change_preview",
        fieldtype: "HTML",
      },
      {
        fieldname: "requested_user",
        fieldtype: "Data",
        label: __("Requested By"),
        default: request.requested_user,
        read_only: 1,
      },
      {
        fieldname: "requested_by",
        fieldtype: "Data",
        label: __("Who Told to Change"),
        default: request.requested_by,
        read_only: 1,
      },
      {
        fieldname: "requested_on",
        fieldtype: "Datetime",
        label: __("Requested On"),
        default: request.requested_on,
        read_only: 1,
      },
      {
        fieldname: "reason",
        fieldtype: "Small Text",
        label: __("Reason"),
        default: request.reason,
        read_only: 1,
      },
    ],
    primary_action_label: __("Approve Quantity Changed"),
    primary_action: function () {
      frappe.call({
        method:
          "production_api.production_api.doctype.production_order.production_order.approve_quantity_and_ratio",
        args: {
          production_order: frm.doc.name,
        },
        callback: function () {
          d.hide();
          frm.reload_doc();
          frappe.show_alert({
            message: __("Quantity & ratio update approved"),
            indicator: "green",
          });
        },
      });
    },
  });
  build_quantity_approval_preview(
    d.fields_dict.change_preview.$wrapper,
    request,
  );
  d.show();
}

function show_approve_status_change_dialog(frm, request) {
  if (!request.requested_status) {
    frappe.msgprint(__("Pending status request details are missing"));
    return;
  }

  const approval_label = __("Approve {0}", [request.requested_status]);
  const d = new frappe.ui.Dialog({
    title: approval_label,
    fields: [
      {
        fieldname: "previous_status",
        fieldtype: "Data",
        label: __("Current Status"),
        default: request.previous_status,
        read_only: 1,
      },
      {
        fieldname: "requested_status",
        fieldtype: "Data",
        label: __("Requested Status"),
        default: request.requested_status,
        read_only: 1,
      },
      {
        fieldname: "requested_user",
        fieldtype: "Data",
        label: __("Requested By"),
        default: request.requested_user,
        read_only: 1,
      },
      {
        fieldname: "requested_on",
        fieldtype: "Datetime",
        label: __("Requested On"),
        default: request.requested_on,
        read_only: 1,
      },
      {
        fieldname: "reason",
        fieldtype: "Small Text",
        label: __("Reason"),
        default: request.reason,
        read_only: 1,
      },
    ],
    primary_action_label: approval_label,
    primary_action: function () {
      frappe.call({
        method:
          "production_api.production_api.doctype.production_order.production_order.approve_status_change",
        args: {
          production_order: frm.doc.name,
        },
        callback: function () {
          d.hide();
          frm.reload_doc();
          frappe.show_alert({
            message: __("{0} approved", [request.requested_status]),
            indicator: "green",
          });
        },
      });
    },
  });
  d.show();
}

// Read-only size -> quantity table for the Transfer Quantity dialog. The whole source
// quantity moves and the source is not reduced, so there is nothing here to edit.
function build_transfer_preview($wrapper, transfers) {
  const sizes = Object.keys(transfers);
  $wrapper.empty();

  const $container = $(
    '<div class="po-transfer-preview-wrap" style="overflow-x:auto; margin-bottom:12px;"></div>',
  );
  const $table = $(
    '<table class="po-transfer-preview table table-bordered" style="margin-bottom:0; width:auto; min-width:100%;"></table>',
  );

  const $headRow = $("<tr></tr>");
  $("<th></th>")
    .text(__("Size"))
    .css({
      "text-align": "left",
      "white-space": "nowrap",
      "font-size": "11px",
    })
    .appendTo($headRow);
  sizes.forEach((size) => {
    $("<th></th>")
      .text(size)
      .css({
        "text-align": "center",
        "white-space": "nowrap",
        "font-size": "11px",
      })
      .appendTo($headRow);
  });

  const $bodyRow = $("<tr></tr>");
  $("<td></td>")
    .text(__("Quantity"))
    .css({ "font-weight": "bold", "white-space": "nowrap" })
    .appendTo($bodyRow);
  let total = 0;
  sizes.forEach((size) => {
    total += flt(transfers[size]);
    $("<td></td>")
      .text(transfers[size])
      .css({ "text-align": "center" })
      .appendTo($bodyRow);
  });

  $table
    .append($("<thead></thead>").append($headRow))
    .append($("<tbody></tbody>").append($bodyRow));
  $container.append($table);
  $container.append(
    $('<div class="text-muted" style="margin-top:6px;"></div>').text(
      __("Total") + ": " + total,
    ),
  );
  $wrapper.append($container);
}

function build_transfer_approval_preview($wrapper, request) {
  const transfers = request.transfers || {};
  const original_quantities = request.target_original_quantities || {};
  const sizes = Object.keys(transfers);
  $wrapper.empty();

  const $table = $(
    '<table class="table table-bordered" style="margin-bottom:0;"></table>',
  );
  const $head = $("<tr></tr>");
  [
    __("Size"),
    __("Current Quantity"),
    __("Transfer Quantity"),
    __("After Approval"),
  ].forEach((label) => {
    $("<th></th>").text(label).appendTo($head);
  });
  const $body = $("<tbody></tbody>");
  sizes.forEach((size) => {
    const current = flt(original_quantities[size]);
    const transfer = flt(transfers[size]);
    const $row = $("<tr></tr>");
    $("<td></td>").text(size).appendTo($row);
    $("<td></td>").text(current).appendTo($row);
    $("<td></td>").text(transfer).appendTo($row);
    $("<td></td>").text(current + transfer).appendTo($row);
    $body.append($row);
  });
  $table.append($("<thead></thead>").append($head)).append($body);
  $wrapper.append(
    $('<div style="overflow-x:auto;"></div>').append($table),
  );
}

function show_approve_quantity_transfer_dialog(frm, request) {
  if (!request.source_production_order || !request.transfers) {
    frappe.msgprint(__("Pending quantity transfer details are missing"));
    return;
  }

  const d = new frappe.ui.Dialog({
    title: __("Approve Transfer Quantity"),
    size: "large",
    fields: [
      {
        fieldname: "source_production_order",
        fieldtype: "Link",
        label: __("Source Production Order"),
        options: "Production Order",
        default: request.source_production_order,
        read_only: 1,
      },
      {
        fieldname: "source_status",
        fieldtype: "Data",
        label: __("Source Status"),
        default: request.source_status,
        read_only: 1,
      },
      {
        fieldname: "target_previous_status",
        fieldtype: "Data",
        label: __("Destination Status Before Request"),
        default: request.target_previous_status,
        read_only: 1,
      },
      {
        fieldname: "transfer_preview",
        fieldtype: "HTML",
        label: __("Quantity Changes"),
      },
      {
        fieldname: "requested_user",
        fieldtype: "Data",
        label: __("Requested By"),
        default: request.requested_user,
        read_only: 1,
      },
      {
        fieldname: "requested_on",
        fieldtype: "Datetime",
        label: __("Requested On"),
        default: request.requested_on,
        read_only: 1,
      },
      {
        fieldname: "reason",
        fieldtype: "Small Text",
        label: __("Reason"),
        default: request.reason,
        read_only: 1,
      },
    ],
    primary_action_label: __("Approve Transfer Quantity"),
    primary_action: function () {
      frappe.call({
        method:
          "production_api.production_api.doctype.production_order.production_order.approve_quantity_transfer",
        args: {
          production_order: frm.doc.name,
        },
        callback: function () {
          d.hide();
          frm.reload_doc();
          frappe.show_alert({
            message: __("Transfer quantity approved"),
            indicator: "green",
          });
        },
      });
    },
  });
  build_transfer_approval_preview(
    d.fields_dict.transfer_preview.$wrapper,
    request,
  );
  d.show();
}

function show_transfer_quantity_dialog(frm, alternative_items) {
  // __onload.items is get_order_qty's {size: {qty, ratio, ...}} for this doc's rows.
  const size_details = (frm.doc.__onload || {}).items || {};
  const transfers = {};
  Object.keys(size_details).forEach((size) => {
    const qty = flt(size_details[size].qty);
    if (qty > 0) {
      transfers[size] = qty;
    }
  });
  if (!Object.keys(transfers).length) {
    frappe.msgprint(__("Production Order has no quantity to transfer"));
    return;
  }

  let d = new frappe.ui.Dialog({
    title: __("Transfer Quantity"),
    size: "large",
    fields: [
      {
        fieldname: "target_production_order",
        fieldtype: "Link",
        label: __("Target Production Order"),
        options: "Production Order",
        reqd: 1,
        get_query: () => {
          return {
            filters: {
              docstatus: 1,
              status: ["in", ["Open", "Item Changed", "Not Processed"]],
              name: ["!=", frm.doc.name],
              item: ["in", alternative_items],
              transferred_to_ppo: ["is", "not set"],
              incoming_quantity_transfer_request: ["is", "not set"],
            },
          };
        },
      },
      {
        fieldname: "transfer_preview",
        fieldtype: "HTML",
        label: __("Quantity to Transfer"),
      },
      {
        fieldname: "reason",
        fieldtype: "Small Text",
        label: __("Reason"),
        reqd: 1,
      },
    ],
    primary_action_label: __("Request Transfer Approval"),
    primary_action: function () {
      let values = d.get_values();
      if (!values) return;

      frappe.call({
        method:
          "production_api.production_api.doctype.production_order.production_order.transfer_quantity_to_ppo",
        args: {
          source_production_order: frm.doc.name,
          target_production_order: values.target_production_order,
          reason: values.reason,
        },
        callback: function () {
          d.hide();
          frm.reload_doc();
          frappe.show_alert({
            message: __("Quantity transfer sent for approval"),
            indicator: "orange",
          });
        },
      });
    },
  });

  build_transfer_preview(d.fields_dict.transfer_preview.$wrapper, transfers);
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
