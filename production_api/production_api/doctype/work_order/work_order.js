// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt
frappe.ui.form.on("Work Order", {
  setup(frm) {
    frm.set_query("supplier_address", function (doc) {
      if (!doc.supplier) {
        frappe.throw(
          __("Please set {0}", [
            __(frappe.meta.get_label(doc.doctype, "supplier", doc.name)),
          ]),
        );
      }
      return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: {
          link_doctype: "Supplier",
          link_name: doc.supplier,
        },
      };
    });
    frm.set_query("delivery_address", function (doc) {
      if (!doc.delivery_location) {
        frappe.throw(
          __("Please set {0}", [
            __(
              frappe.meta.get_label(doc.doctype, "delivery_location", doc.name),
            ),
          ]),
        );
      }
      return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: {
          link_doctype: "Supplier",
          link_name: doc.delivery_location,
        },
      };
    });
    frm.set_query("parent_wo", function (doc) {
      return {
        filters: {
          name: ["!=", doc.name],
        },
      };
    });
  },
  async refresh(frm) {
    $(".layout-side-section").css("display", "None");
    frm.set_df_property("work_order_tracking_logs", "cannot_add_rows", true);
    frm.set_df_property("work_order_tracking_logs", "cannot_delete_rows", true);
    if (frm.doc.docstatus == 1 && frm.doc.is_rework) {
      frappe.realtime.on("get_receivables_data", () => {
        let receivables = frm.receivable_items.get_receivables_data();
        frappe.call({
          method:
            "production_api.production_api.doctype.work_order.work_order.update_receivables",
          args: {
            receivables_data: receivables,
            doc_name: frm.doc.name,
          },
          callback: function () {
            frm.reload_doc();
          },
        });
      });
    }
    frm.val = null;
    if (frm.is_new()) {
      hide_field(["deliverable_items", "receivable_items"]);
    } else {
      unhide_field(["deliverable_items", "receivable_items"]);
      $(frm.fields_dict["deliverable_items"].wrapper).html("");
      $(frm.fields_dict["receivable_items"].wrapper).html("");
      if (!frm.doc.is_rework) {
        frm.deliverable_items = new frappe.production.ui.Deliverables(
          frm.fields_dict["deliverable_items"].wrapper,
        );
        frm.receivable_items = new frappe.production.ui.Receivables(
          frm.fields_dict["receivable_items"].wrapper,
        );
      } else {
        frm.deliverable_items = new frappe.production.ui.WOReworkDeliverables(
          frm.fields_dict["deliverable_items"].wrapper,
        );
        frm.receivable_items = new frappe.production.ui.WOReworkReceivables(
          frm.fields_dict["receivable_items"].wrapper,
        );
      }
      if (frm.doc.is_rework) {
        frm.val = true;
      }
      if (frm.doc.docstatus == 0 && frm.doc.item && !frm.doc.is_rework) {
        frm.add_custom_button("Calculate Items", function () {
          if (frm.is_dirty()) {
            frappe.msgprint("Save the file before calculate");
            return;
          }
          frappe.call({
            method:
              "production_api.production_api.doctype.work_order.work_order.get_lot_items",
            args: {
              lot: frm.doc.lot,
              doc_name: frm.doc.name,
              process: frm.doc.process_name,
              includes_packing: frm.doc.includes_packing,
            },
            callback: async function (r) {
              let d = new frappe.ui.Dialog({
                title: "Lot Items",
                fields: [{ fieldtype: "HTML", fieldname: "lot_items_html" }],
                size: "extra-large",
                primary_action() {
                  frm.trigger("calculate_del_and_rec");
                  d.hide();
                },
              });
              frm.order_detail = new frappe.production.ui.WorkOrderItemView(
                d.fields_dict.lot_items_html.wrapper,
              );
              await frm.order_detail.load_data(r.message);
              frm.order_detail.create_input_attributes();
              d.show();
            },
          });
        });
      }
      if (frm.doc.open_status == "Open" && frm.doc.docstatus == 1) {
        frm.add_custom_button("Material Issue", () => {
          if (!frm.doc.supplier) {
            frappe.throw(__("Supplier is required to create a Material Issue Stock Entry."));
          }

          let stock_entry = frappe.model.get_new_doc("Stock Entry");
          stock_entry.purpose = "Material Issue";
          stock_entry.against = "Work Order";
          stock_entry.against_id = frm.doc.name;
          stock_entry.from_warehouse = frm.doc.supplier;
          stock_entry.transfer_supplier = frm.doc.supplier;
          stock_entry.posting_date = frappe.datetime.nowdate();
          stock_entry.posting_time = new Date().toTimeString().split(" ")[0];
          frappe.set_route("Form", stock_entry.doctype, stock_entry.name);
        }, "Create");

        frm.add_custom_button("Change Delivery Date", () => {
          var d = new frappe.ui.Dialog({
            title: "Change Delivery Date",
            fields: [
              {
                fieldname: "date",
                fieldtype: "Date",
                label: "Delivery Date",
                default: frm.doc.expected_delivery_date,
                reqd: 1,
              },
              {
                fieldname: "reason",
                fieldtype: "Data",
                label: "Reason",
                reqd: 1,
              },
            ],
            primary_action_label: "Submit",
            primary_action(values) {
              frappe.call({
                method:
                  "production_api.production_api.doctype.work_order.work_order.add_comment",
                args: {
                  doc_name: frm.doc.name,
                  date: values.date,
                  reason: values.reason,
                },
              });
              d.hide();
            },
          });
          d.show();
        });
        if (frappe.user.has_role("System Manager")) {
          frm.add_custom_button("Create Sewing Plan", () => {
            frappe.call({
              method:
                "production_api.production_api.doctype.sewing_plan.sewing_plan.create_sewing_plan",
              args: {
                work_order: frm.doc.name,
              },
            });
          });
        }
        frm.add_custom_button("Close", () => {
          frappe.call({
            method:
              "production_api.production_api.doctype.work_order.work_order.fetch_summary_details",
            args: {
              doc_name: frm.doc.name,
              production_detail: frm.doc.production_detail,
            },
            callback: function (r) {
              let item_detail = JSON.parse(
                JSON.stringify(r.message.item_detail),
              );

              // Filter each group: keep only items where total_delivered - total_received > 0
              let has_pending = false;
              for (let group of item_detail) {
                if (!group.items) continue;
                group.items = group.items.filter((item) => {
                  return (item.total_delivered || 0) - (item.total_received || 0) > 0;
                });
                if (group.items.length > 0) {
                  has_pending = true;
                  // Recalculate total_details and overall totals for filtered items
                  let total_details = {};
                  let overall_planned = 0;
                  let overall_delivered = 0;
                  let overall_received = 0;
                  for (let item of group.items) {
                    for (let attr of Object.keys(item.values)) {
                      if (!total_details[attr]) {
                        total_details[attr] = {
                          planned: 0,
                          delivered: 0,
                          received: 0,
                        };
                      }
                      total_details[attr].planned +=
                        item.values[attr]?.qty || 0;
                      total_details[attr].delivered +=
                        item.values[attr]?.delivered || 0;
                      total_details[attr].received +=
                        item.values[attr]?.received || 0;
                    }
                    overall_planned += item.total_qty || 0;
                    overall_delivered += item.total_delivered || 0;
                    overall_received += item.total_received || 0;
                  }
                  group.total_details = total_details;
                  group.overall_planned = overall_planned;
                  group.overall_delivered = overall_delivered;
                  group.overall_received = overall_received;
                }
              }

              // Remove empty groups
              item_detail = item_detail.filter(
                (group) => group.items && group.items.length > 0,
              );

              // Fetch recut details in parallel
              frappe.call({
                method:
                  "production_api.production_api.doctype.work_order.work_order.get_wo_recut_details",
                args: {
                  work_order: frm.doc.name,
                },
                callback: function (recut_r) {
                  let recut_data = recut_r.message || [];

                  let d = new frappe.ui.Dialog({
                    title: "Pending Items - Close Work Order",
                    fields: [
                      {
                        fieldtype: "HTML",
                        fieldname: "summary_html",
                      },
                      {
                        fieldtype: "HTML",
                        fieldname: "recut_html",
                      },
                      {
                        fieldtype: "HTML",
                        fieldname: "debit_list_html",
                      },
                      {
                        fieldtype: "Select",
                        fieldname: "with_debit",
                        label: "Debit",
                        options: "Without Debit\nWith Debit",
                        default: "Without Debit",
                      },
                      {
                        fieldtype: "Button",
                        fieldname: "create_debit_btn",
                        label: "Create Debit",
                        depends_on: "eval: doc.with_debit == 'With Debit' && !doc.essdee_debit",
                        click: () => {
                          open_debit_dialog(frm, d);
                        },
                      },
                      {
                        fieldtype: "Link",
                        fieldname: "essdee_debit",
                        label: "Essdee Debit",
                        options: "Essdee Debit",
                        read_only: 1,
                        depends_on: "eval: doc.with_debit == 'With Debit'",
                        mandatory_depends_on: "eval: doc.with_debit == 'With Debit'",
                      },
                      {
                        fieldtype: "Select",
                        fieldname: "close_reason",
                        label: "Close Reason",
                        options: "\nCutting Shortage\nPrinting Shortage\nSewing Shortage\nSewing Missing\nOthers",
                        reqd: 1,
                      },
                      {
                        fieldtype: "Data",
                        fieldname: "close_other_reason",
                        label: "Other Reason",
                        depends_on: "eval: doc.close_reason == 'Others'",
                        mandatory_depends_on: "eval: doc.close_reason == 'Others'",
                      },
                      {
                        fieldtype: "Small Text",
                        fieldname: "close_remarks",
                        label: "Close Remarks",
                      },
                    ],
                    primary_action_label: "Close Work Order",
                    size: "extra-large",
                    primary_action() {
                      let values = d.get_values();
                      if (!values) return;
                      d.hide();
                      let x = new frappe.ui.Dialog({
                        title:
                          "Are you sure want to close this work order",
                        primary_action_label: "Yes",
                        secondary_action_label: "No",
                        primary_action: () => {
                          x.hide();
                          frappe.call({
                            method:
                              "production_api.production_api.doctype.work_order.work_order.update_stock",
                            args: {
                              work_order: frm.doc.name,
                              close_reason: values.close_reason,
                              close_other_reason: values.close_other_reason || "",
                              close_remarks: values.close_remarks || "",
                            },
                            callback: function () {
                              frm.refresh();
                            },
                          });
                        },
                        secondary_action: () => {
                          x.hide();
                        },
                      });
                      x.show();
                    },
                  });
                  d.show();
                  fetch_and_render_debit_list(frm, d);

                  let wrapper = d.fields_dict.summary_html.wrapper;
                  if (has_pending) {
                    let summary = new frappe.production.ui.WOSummary(
                      wrapper,
                    );
                    summary.load_data(item_detail, [], {
                      show_pending: true,
                    });
                  } else {
                    $(wrapper).html(
                      '<p class="text-muted text-center" style="padding: 20px;">All items fully received</p>',
                    );
                  }

                  // Render recut details below summary
                  let recut_wrapper = $(
                    d.fields_dict.recut_html.wrapper,
                  );
                  if (recut_data.length > 0) {
                    let html = '<hr><h4>WO Recut Details</h4>';
                    for (let recut of recut_data) {
                      html +=
                        '<div style="margin-bottom: 15px;">' +
                        '<strong><a href="/app/wo-recut/' +
                        recut.name +
                        '" target="_blank">' +
                        recut.name +
                        "</a></strong>";
                      for (let group of recut.items) {
                        html +=
                          '<table class="table table-sm table-bordered" style="margin-top: 8px;">';
                        // Header row
                        html += "<thead><tr>";
                        html += "<th>S.No.</th>";
                        html += "<th>Item</th>";
                        for (let attr of (group.attributes || [])) {
                          html += "<th>" + attr + "</th>";
                        }
                        if (group.primary_attribute) {
                          for (let pv of (group.primary_attribute_values || [])) {
                            html += "<th>" + pv + "</th>";
                          }
                        } else {
                          html += "<th>Quantity</th>";
                        }
                        html += "<th>Total</th>";
                        html += "</tr></thead><tbody>";

                        // Item rows
                        for (
                          let idx = 0;
                          idx < group.items.length;
                          idx++
                        ) {
                          let item = group.items[idx];
                          html += "<tr>";
                          html += "<td>" + (idx + 1) + "</td>";
                          html += "<td>" + (item.name || "") + "</td>";
                          for (let attr of (group.attributes || [])) {
                            html +=
                              "<td>" +
                              (item.attributes?.[attr] || "") +
                              "</td>";
                          }
                          let total = 0;
                          if (group.primary_attribute) {
                            for (let pv of (group.primary_attribute_values || [])) {
                              let qty =
                                item.values?.[pv]?.qty || 0;
                              total += qty;
                              html +=
                                "<td>" +
                                (qty > 0 ? qty : "--") +
                                "</td>";
                            }
                          } else {
                            let qty =
                              item.values?.["default"]?.qty || 0;
                            total = qty;
                            html +=
                              "<td>" +
                              (qty > 0 ? qty : "--") +
                              "</td>";
                          }
                          html +=
                            "<td><strong>" + total + "</strong></td>";
                          html += "</tr>";
                        }
                        html += "</tbody></table>";
                      }
                      html += "</div>";
                    }
                    recut_wrapper.html(html);
                  }
                },
              });
            },
          });
        });
        if (frm.doc.__onload && frm.doc.__onload.is_cutting) {
          frm.add_custom_button(
            __("Make Cutting Plan"),
            function () {
              let x = frappe.model.get_new_doc("Cutting Plan");
              x.work_order = frm.doc.name;
              x.lot = frm.doc.lot;
              x.item = frm.doc.item;
              x.maximum_no_of_plys = 100;
              frappe.set_route("Form", x.doctype, x.name);
            },
            __("Create"),
          );
        }
        frm.add_custom_button(
          __("Make DC"),
          function () {
            let x = frappe.model.get_new_doc("Delivery Challan");
            x.work_order = frm.doc.name;
            x.naming_series = "DC-";
            x.posting_date = frappe.datetime.nowdate();
            x.posting_time = new Date().toTimeString().split(" ")[0];
            x.is_rework = frm.doc.is_rework;
            x.includes_packing = frm.doc.includes_packing;
            frappe.set_route("Form", x.doctype, x.name);
          },
          __("Create"),
        );
        frm.add_custom_button(
          __("Make GRN"),
          function () {
            let y = frappe.model.get_new_doc("Goods Received Note");
            y.against = "Work Order";
            y.naming_series = "GRN-";
            y.against_id = frm.doc.name;
            y.supplier = frm.doc.supplier;
            y.supplier_address = frm.doc.supplier_address;
            y.posting_date = frappe.datetime.nowdate();
            y.delivery_date = frappe.datetime.nowdate();
            y.posting_time = new Date().toTimeString().split(" ")[0];
            y.is_rework = frm.doc.is_rework;
            y.includes_packing = frm.doc.includes_packing;
            frappe.set_route("Form", y.doctype, y.name);
          },
          __("Create"),
        );
      }
      if (frm.doc.open_status == "Close Request" && frm.doc.docstatus == 1) {
        frm.dashboard.add_comment(
          __("Close has been requested for this Work Order."),
          "yellow",
          true,
        );
        frm.add_custom_button("Approve Close", () => {
          frappe.call({
            method:
              "production_api.production_api.doctype.work_order.work_order.fetch_summary_details",
            args: {
              doc_name: frm.doc.name,
              production_detail: frm.doc.production_detail,
            },
            callback: function (r) {
              let item_detail = JSON.parse(
                JSON.stringify(r.message.item_detail),
              );

              let has_pending = false;
              for (let group of item_detail) {
                if (!group.items) continue;
                group.items = group.items.filter((item) => {
                  return (item.total_delivered || 0) - (item.total_received || 0) > 0;
                });
                if (group.items.length > 0) {
                  has_pending = true;
                  let total_details = {};
                  let overall_planned = 0;
                  let overall_delivered = 0;
                  let overall_received = 0;
                  for (let item of group.items) {
                    for (let attr of Object.keys(item.values)) {
                      if (!total_details[attr]) {
                        total_details[attr] = {
                          planned: 0,
                          delivered: 0,
                          received: 0,
                        };
                      }
                      total_details[attr].planned +=
                        item.values[attr]?.qty || 0;
                      total_details[attr].delivered +=
                        item.values[attr]?.delivered || 0;
                      total_details[attr].received +=
                        item.values[attr]?.received || 0;
                    }
                    overall_planned += item.total_qty || 0;
                    overall_delivered += item.total_delivered || 0;
                    overall_received += item.total_received || 0;
                  }
                  group.total_details = total_details;
                  group.overall_planned = overall_planned;
                  group.overall_delivered = overall_delivered;
                  group.overall_received = overall_received;
                }
              }
              item_detail = item_detail.filter(
                (group) => group.items && group.items.length > 0,
              );

              frappe.call({
                method:
                  "production_api.production_api.doctype.work_order.work_order.get_wo_recut_details",
                args: {
                  work_order: frm.doc.name,
                },
                callback: function (recut_r) {
                  let recut_data = recut_r.message || [];

                  let d = new frappe.ui.Dialog({
                    title: "Approve Close - Work Order",
                    fields: [
                      {
                        fieldtype: "HTML",
                        fieldname: "summary_html",
                      },
                      {
                        fieldtype: "HTML",
                        fieldname: "recut_html",
                      },
                      {
                        fieldtype: "HTML",
                        fieldname: "debit_list_html",
                      },
                      {
                        fieldtype: "Select",
                        fieldname: "with_debit",
                        label: "Debit",
                        options: "Without Debit\nWith Debit",
                        default: "Without Debit",
                      },
                      {
                        fieldtype: "Button",
                        fieldname: "create_debit_btn",
                        label: "Create Debit",
                        depends_on: "eval: doc.with_debit == 'With Debit' && !doc.essdee_debit",
                        click: () => {
                          open_debit_dialog(frm, d);
                        },
                      },
                      {
                        fieldtype: "Link",
                        fieldname: "essdee_debit",
                        label: "Essdee Debit",
                        read_only: 1,
                        options: "Essdee Debit",
                        depends_on: "eval: doc.with_debit == 'With Debit'",
                        mandatory_depends_on: "eval: doc.with_debit == 'With Debit'",
                      },
                      {
                        fieldtype: "Data",
                        fieldname: "debit_type",
                        label: "Debit Type",
                        read_only: 1,
                        depends_on: "eval: doc.essdee_debit",
                      },
                      {
                        fieldtype: "Currency",
                        fieldname: "debit_value",
                        label: "Debit Value",
                        read_only: 1,
                        depends_on: "eval: doc.essdee_debit",
                      },
                      {
                        fieldtype: "Select",
                        fieldname: "close_reason",
                        label: "Close Reason",
                        options: "\nCutting Shortage\nPrinting Shortage\nSewing Shortage\nSewing Missing\nOthers",
                        reqd: 1,
                        default: frm.doc.close_reason || "",
                      },
                      {
                        fieldtype: "Data",
                        fieldname: "close_other_reason",
                        label: "Other Reason",
                        depends_on: "eval: doc.close_reason == 'Others'",
                        mandatory_depends_on: "eval: doc.close_reason == 'Others'",
                        default: frm.doc.close_other_reason || "",
                      },
                      {
                        fieldtype: "Small Text",
                        fieldname: "close_remarks",
                        label: "Close Remarks",
                        default: frm.doc.close_remarks || "",
                      },
                    ],
                    primary_action_label: "Approve Close",
                    size: "extra-large",
                    primary_action() {
                      let values = d.get_values();
                      if (!values) return;
                      if (d.essdee_debits && d.essdee_debits.some(db => db.status !== "Approved")) {
                        frappe.msgprint(__("All Essdee Debits must be approved before closing."));
                        return;
                      }
                      d.hide();
                      let x = new frappe.ui.Dialog({
                        title:
                          "Are you sure you want to approve closing this work order?",
                        primary_action_label: "Yes",
                        secondary_action_label: "No",
                        primary_action: () => {
                          x.hide();
                          frappe.call({
                            method:
                              "production_api.production_api.doctype.work_order.work_order.update_stock",
                            args: {
                              work_order: frm.doc.name,
                              close_reason: values.close_reason,
                              close_other_reason: values.close_other_reason || "",
                              close_remarks: values.close_remarks || "",
                            },
                            callback: function () {
                              frm.refresh();
                            },
                          });
                        },
                        secondary_action: () => {
                          x.hide();
                        },
                      });
                      x.show();
                    },
                  });
                  d.show();
                  fetch_and_render_debit_list(frm, d);

                  let wrapper = d.fields_dict.summary_html.wrapper;
                  if (has_pending) {
                    let summary = new frappe.production.ui.WOSummary(
                      wrapper,
                    );
                    summary.load_data(item_detail, [], {
                      show_pending: true,
                    });
                  } else {
                    $(wrapper).html(
                      '<p class="text-muted text-center" style="padding: 20px;">All items fully received</p>',
                    );
                  }

                  let recut_wrapper = $(
                    d.fields_dict.recut_html.wrapper,
                  );
                  if (recut_data.length > 0) {
                    let html = '<hr><h4>WO Recut Details</h4>';
                    for (let recut of recut_data) {
                      html +=
                        '<div style="margin-bottom: 15px;">' +
                        '<strong><a href="/app/wo-recut/' +
                        recut.name +
                        '" target="_blank">' +
                        recut.name +
                        "</a></strong>";
                      for (let group of recut.items) {
                        html +=
                          '<table class="table table-sm table-bordered" style="margin-top: 8px;">';
                        html += "<thead><tr>";
                        html += "<th>S.No.</th>";
                        html += "<th>Item</th>";
                        for (let attr of (group.attributes || [])) {
                          html += "<th>" + attr + "</th>";
                        }
                        if (group.primary_attribute) {
                          for (let pv of (group.primary_attribute_values || [])) {
                            html += "<th>" + pv + "</th>";
                          }
                        } else {
                          html += "<th>Quantity</th>";
                        }
                        html += "<th>Total</th>";
                        html += "</tr></thead><tbody>";

                        for (
                          let idx = 0;
                          idx < group.items.length;
                          idx++
                        ) {
                          let item = group.items[idx];
                          html += "<tr>";
                          html += "<td>" + (idx + 1) + "</td>";
                          html += "<td>" + (item.name || "") + "</td>";
                          for (let attr of (group.attributes || [])) {
                            html +=
                              "<td>" +
                              (item.attributes?.[attr] || "") +
                              "</td>";
                          }
                          let total = 0;
                          if (group.primary_attribute) {
                            for (let pv of (group.primary_attribute_values || [])) {
                              let qty =
                                item.values?.[pv]?.qty || 0;
                              total += qty;
                              html +=
                                "<td>" +
                                (qty > 0 ? qty : "--") +
                                "</td>";
                            }
                          } else {
                            let qty =
                              item.values?.["default"]?.qty || 0;
                            total = qty;
                            html +=
                              "<td>" +
                              (qty > 0 ? qty : "--") +
                              "</td>";
                          }
                          html +=
                            "<td><strong>" + total + "</strong></td>";
                          html += "</tr>";
                        }
                        html += "</tbody></table>";
                      }
                      html += "</div>";
                    }
                    recut_wrapper.html(html);
                  }
                },
              });
            },
          });
        });
      }
      if (frm.doc.__onload && frm.doc.__onload.deliverable_item_details) {
        frm.doc["deliverable_item_details"] = JSON.stringify(
          frm.doc.__onload.deliverable_item_details,
        );
        frm.deliverable_items.load_data(
          frm.doc.__onload.deliverable_item_details,
        );
      } else {
        frm.deliverable_items.load_data([]);
      }
      if (!frm.doc.is_rework) {
        frm.deliverable_items.update_status(frm.val);
        frm.receivable_items.update_status(true);
      }
      if (frm.doc.__onload && frm.doc.__onload.receivable_item_details) {
        frm.doc["receivable_item_details"] = JSON.stringify(
          frm.doc.__onload.receivable_item_details,
        );
        frm.receivable_items.load_data(
          frm.doc.__onload.receivable_item_details,
        );
      } else {
        frm.receivable_items.load_data([]);
      }
      if (!frm.doc.is_rework) {
        frappe.production.ui.eventBus.$on("wo_updated", (e) => {
          frm.dirty();
        });
      }
      if (frm.doc.docstatus == 1 && !frm.doc.is_rework) {
        frappe.call({
          method:
            "production_api.production_api.doctype.work_order.work_order.fetch_summary_details",
          args: {
            doc_name: frm.doc.name,
            production_detail: frm.doc.production_detail,
          },
          callback: function (r) {
            $(frm.fields_dict["wo_summary_html"].wrapper).html("");
            frm.summary = new frappe.production.ui.WOSummary(
              frm.fields_dict["wo_summary_html"].wrapper,
            );
            frm.summary.load_data(
              r.message.item_detail,
              r.message.deliverables,
            );
          },
        });
      }
      if (
        frm.doc.docstatus == 1 &&
        !frm.doc.is_rework &&
        frm.doc.open_status == "Open"
      ) {
        frm.add_custom_button("Create Rework", () => {
          let d = new frappe.ui.Dialog({
            title: "Select the type of rework",
            fields: [
              {
                fieldname: "supplier_type",
                fieldtype: "Select",
                label: "Supplier Type",
                options: "Same Supplier\nDifferent Supplier",
                reqd: true,
              },
              {
                fieldname: "rework_type",
                fieldtype: "Select",
                label: "Rework Type",
                options: "No Cost\nNet Cost Nil\nAdditional Cost",
                reqd: true,
              },
            ],
            primary_action(values) {
              if (values.supplier_type == "Different Supplier") {
                d.hide();
                let dialog = new frappe.ui.Dialog({
                  title: "Select Supplier",
                  fields: [
                    {
                      fieldname: "supplier",
                      fieldtype: "Link",
                      options: "Supplier",
                      label: "Supplier",
                    },
                    {
                      fieldname: "supplier_address",
                      fieldtype: "Link",
                      options: "Address",
                      label: "Supplier Address",
                    },
                  ],
                  primary_action(val) {
                    dialog.hide();
                    make_rework(
                      frm,
                      val.supplier,
                      val.supplier_address,
                      values.rework_type,
                      values.supplier_type,
                    );
                  },
                });
                dialog.show();
              } else {
                d.hide();
                make_rework(
                  frm,
                  frm.doc.supplier,
                  frm.doc.supplier_address,
                  values.rework_type,
                  values.supplier_type,
                );
              }
            },
          });
          d.show();
        },__("Create"),);
      }
      if (frm.doc.docstatus == 1 && frm.doc.open_status == "Open") {
        frm.add_custom_button("Create Recut", () => {
          let d = new frappe.ui.Dialog({
            title: "Create Recut",
            size: "extra-large",
            fields: [{ fieldname: "recut_html", fieldtype: "HTML" }],
            primary_action_label: "Create",
            primary_action() {
              let items = recut_fetcher.get_deliverables_data();
              frappe.call({
                method:
                  "production_api.production_api.doctype.work_order.work_order.create_wo_recut",
                args: {
                  work_order: frm.doc.name,
                  items: items,
                },
                freeze: true,
                freeze_message: __("Creating WO Recut..."),
                callback: function (r) {
                  d.hide();
                  frappe.set_route("Form", "WO Recut", r.message);
                },
              });
            },
          });
          let recut_fetcher = new frappe.production.ui.Deliverables(
            d.fields_dict.recut_html.wrapper,
          );
          recut_fetcher.load_data([]);
          d.show();
        },__("Create"),);
      }
      if (frm.doc.docstatus == 1 && frappe.user.has_role("System Manager")) {
        frm.add_custom_button("Calculate Pieces", () => {
          frm.trigger("calculate_pieces");
        });
      }
      if (frm.doc.docstatus == 1) {
        frm.add_custom_button("Create Debit", () => {
          open_debit_dialog(frm);
        }, __("Create"));
      }
    }
  },
  calculate_pieces(frm) {
    frappe.call({
      method:
        "production_api.production_api.doctype.work_order.work_order.calculate_completed_pieces",
      args: {
        doc_name: frm.doc.name,
      },
    });
  },
  calculate_del_and_rec(frm) {
    let items = frm.order_detail.get_work_order_items();
    frappe.call({
      method:
        "production_api.production_api.doctype.work_order.work_order.get_deliverable_receivable",
      args: {
        items: items,
        doc_name: frm.doc.name,
      },
      freeze: true,
      freeze_message: __("Calculate Deliverables and Receivables..."),
      callback: function () {
        frm.reload_doc();
      },
    });
  },
  validate(frm) {
    if (frm.val == null && !frm.is_new()) {
      if (!frm.doc.is_rework) {
        let deliverables = frm.deliverable_items.get_deliverables_data();
        frm.doc["deliverable_item_details"] = JSON.stringify(deliverables);
      }
    }
    if (!frm.is_new()) {
      let receivables = frm.receivable_items.get_receivables_data();
      frm.doc["receivable_item_details"] = JSON.stringify(receivables);
    }
  },
  supplier: async function (frm) {
    if (frm.doc.supplier) {
      frappe.production.ui.eventBus.$emit("supplier_updated", frm.doc.supplier);
    }
    if (frm.doc.supplier) {
      frappe.call({
        method:
          "production_api.production_api.doctype.supplier.supplier.get_primary_address",
        args: {
          supplier: frm.doc.supplier,
        },
        callback: function (r) {
          if (r.message) {
            frm.set_value("supplier_address", r.message);
          } else {
            frm.set_value("supplier_address", "");
          }
        },
      });
    } else {
      frm.set_value("supplier_address", "");
    }
  },
  planned_end_date(frm) {
    if (frm.doc.planned_end_date) {
      frm.doc.expected_delivery_date = frm.doc.planned_end_date;
    } else {
      frm.doc.expected_delivery_date = null;
    }
    frm.refresh_field("expected_delivery_date");
  },
  delivery_location: function (frm) {
    if (frm.doc.delivery_location) {
      frappe.production.ui.eventBus.$emit(
        "supplier_updated",
        frm.doc.delivery_location,
      );
    }
    if (frm.doc.delivery_location) {
      frappe.call({
        method:
          "production_api.production_api.doctype.supplier.supplier.get_primary_address",
        args: {
          supplier: frm.doc.delivery_location,
        },
        callback: function (r) {
          if (r.message) {
            frm.set_value("delivery_address", r.message);
          } else {
            frm.set_value("delivery_address", "");
          }
        },
      });
    } else {
      frm.set_value("delivery_address", "");
    }
  },
  supplier_address: function (frm) {
    if (frm.doc["supplier_address"]) {
      frappe.call({
        method:
          "production_api.production_api.doctype.purchase_order.purchase_order.get_address_display",
        args: {
          address_dict: frm.doc["supplier_address"],
        },
        callback: function (r) {
          if (r.message) {
            frm.set_value("supplier_address_details", r.message);
          } else {
            frm.set_value("supplier_address_details", "");
          }
        },
      });
    } else {
      frm.set_value("supplier_address_details", "");
    }
  },
  delivery_address: function (frm) {
    if (frm.doc["delivery_address"]) {
      frappe.call({
        method:
          "production_api.production_api.doctype.purchase_order.purchase_order.get_address_display",
        args: {
          address_dict: frm.doc["delivery_address"],
        },
        callback: function (r) {
          if (r.message) {
            frm.set_value("delivery_address_details", r.message);
          }
        },
      });
    } else {
      frm.set_value("delivery_address_details", "");
    }
  },
});

function fetch_and_render_debit_list(frm, dialog) {
  // Check merch manager role first for approve button visibility
  frappe.call({
    method: "production_api.production_api.doctype.purchase_invoice.purchase_invoice.get_merch_roles",
    callback: function (role_r) {
      let is_merch_manager = role_r.message === "merch_manager";
      _fetch_debit_list(frm, dialog, is_merch_manager);
    },
  });
}

function _fetch_debit_list(frm, dialog, is_merch_manager) {
  frappe.call({
    method: "frappe.client.get_list",
    args: {
      doctype: "Essdee Debit",
      filters: { against: "Work Order", against_id: frm.doc.name, docstatus: 1 },
      fields: ["name", "debit_type", "debit_no", "debit_value", "inspection", "status", "on_close"],
      order_by: "creation asc",
      limit_page_length: 0,
    },
    callback: function (r) {
      let debits = r.message || [];
      dialog.essdee_debits = debits;
      let debit_wrapper = $(dialog.fields_dict.debit_list_html.wrapper);

      if (debits.length > 0) {
        let has_unapproved = debits.some(db => db.status !== "Approved");
        let show_action = has_unapproved && is_merch_manager;
        let html = '<hr><h4>Essdee Debits</h4>';
        html += '<table class="table table-sm table-bordered">';
        html += '<thead><tr>';
        html += '<th>S.No.</th><th>Name</th><th>Debit Type</th><th>Debit No</th><th>Debit Value</th><th>Inspection</th><th>Status</th>';
        if (show_action) html += '<th>Action</th>';
        html += '</tr></thead><tbody>';
        for (let i = 0; i < debits.length; i++) {
          let db = debits[i];
          let status_color = db.status === "Approved" ? "green" : "orange";
          html += '<tr data-debit="' + db.name + '">';
          html += '<td>' + (i + 1) + '</td>';
          html += '<td><a href="/app/essdee-debit/' + db.name + '" target="_blank">' + db.name + '</a></td>';
          html += '<td>' + (db.debit_type || '') + '</td>';
          html += '<td>' + (db.debit_no || '') + '</td>';
          html += '<td>' + format_currency(db.debit_value || 0) + '</td>';
          html += '<td style="text-align: center;"><input type="checkbox" disabled ' + (db.inspection ? 'checked' : '') + '></td>';
          html += '<td class="debit-status"><span style="color: ' + status_color + '; font-weight: bold;">' + (db.status || '') + '</span></td>';
          if (show_action) {
            if (db.status !== "Approved") {
              html += '<td><button class="btn btn-xs btn-primary approve-debit-btn" data-name="' + db.name + '">Approve</button></td>';
            } else {
              html += '<td></td>';
            }
          }
          html += '</tr>';
        }
        let total_value = debits.reduce((sum, db) => sum + (db.debit_value || 0), 0);
        let col_span = show_action ? 8 : 7;
        html += '</tbody><tfoot><tr>';
        html += '<td colspan="4" style="text-align: right; font-weight: bold;">Total</td>';
        html += '<td style="font-weight: bold;">' + format_currency(total_value) + '</td>';
        html += '<td colspan="' + (col_span - 5) + '"></td>';
        html += '</tr></tfoot></table>';
        debit_wrapper.html(html);

        // Bind approve button clicks
        debit_wrapper.find('.approve-debit-btn').on('click', function () {
          let debit_name = $(this).data('name');
          let btn = $(this);
          frappe.confirm(
            __("Are you sure you want to approve {0}?", [debit_name]),
            () => {
              btn.prop('disabled', true);
              frappe.call({
                method: "production_api.production_api.doctype.essdee_debit.essdee_debit.approve_debit",
                args: { name: debit_name },
                callback: function () {
                  // Update local state
                  let db = debits.find(d => d.name === debit_name);
                  if (db) db.status = "Approved";
                  dialog.essdee_debits = debits;
                  // Update row UI
                  let row = debit_wrapper.find('tr[data-debit="' + debit_name + '"]');
                  row.find('.debit-status').html('<span style="color: green; font-weight: bold;">Approved</span>');
                  btn.closest('td').html('');
                  // If all approved now, remove the Action header
                  if (!debits.some(d => d.status !== "Approved")) {
                    debit_wrapper.find('th:last-child').remove();
                    debit_wrapper.find('tbody tr').each(function () {
                      $(this).find('td:last').remove();
                    });
                  }
                },
                error: function () {
                  btn.prop('disabled', false);
                },
              });
            },
          );
        });

        // Pre-populate on_close debit fields if applicable
        let on_close_debit = debits.find(d => d.on_close);
        if (on_close_debit && dialog.fields_dict.essdee_debit) {
          dialog.set_value("with_debit", "With Debit");
          dialog.set_value("essdee_debit", on_close_debit.name);
          dialog.set_value("debit_type", on_close_debit.debit_type);
          dialog.set_value("debit_value", on_close_debit.debit_value);
        }
      }
    },
  });
}

function open_debit_dialog(frm, parentDialog) {
  let d = new frappe.ui.Dialog({
    title: "Create Essdee Debit",
    fields: [
      {
        fieldname: "debit_type",
        fieldtype: "Select",
        label: "Debit Type",
        options: "Permanent",
        default: "Permanent",
        hidden: 1,
        reqd: 1,
      },
      {
        fieldname: "debit_no",
        fieldtype: "Data",
        label: "Debit No",
        reqd: 1,
      },
      {
        fieldname: "debit_value",
        fieldtype: "Currency",
        label: "Debit Value",
        reqd: 1,
      },
      {
        fieldname: "reason",
        fieldtype: "Small Text",
        label: "Reason",
        reqd: 1,
      },
      {
        fieldname: "debit_document",
        fieldtype: "Attach",
        label: "Debit Document",
      },
    ],
    primary_action_label: "Create",
    primary_action(values) {
      frappe.call({
        method: "frappe.client.insert",
        args: {
          doc: {
            doctype: "Essdee Debit",
            against: "Work Order",
            against_id: frm.doc.name,
            debit_type: values.debit_type,
            debit_no: values.debit_no,
            debit_value: values.debit_value,
            reason: values.reason,
            debit_document: values.debit_document,
            on_close: parentDialog ? 1 : 0,
            docstatus: 1,
          },
        },
        callback(r) {
          if (r.message) {
            frappe.show_alert({
              message: __("Essdee Debit {0} created and submitted", [r.message.name]),
              indicator: "green",
            });
            d.hide();
            if (parentDialog) {
              parentDialog.set_value("essdee_debit", r.message.name);
            }
          }
        },
      });
    },
  });
  d.show();
}

function make_rework(
  frm,
  supplier,
  supplier_address,
  rework_type,
  supplier_type,
) {
  frappe.call({
    method:
      "production_api.production_api.doctype.work_order.work_order.get_grn_rework_items",
    args: {
      doc_name: frm.doc.name,
    },
    callback: function (r) {
      if (Object.keys(r.message).length == 0) {
        frappe.msgprint("No Rework Items");
      } else {
        let d = new frappe.ui.Dialog({
          title: "Rework Items",
          fields: [{ fieldtype: "HTML", fieldname: "rework_items_html" }],
          size: "extra-large",
          primary_action() {
            let items = frm.rework_items.get_items();
            frappe.call({
              method:
                "production_api.production_api.doctype.work_order.work_order.create_rework",
              args: {
                doc_name: frm.doc.name,
                items: items,
                supplier: supplier,
                supplier_address: supplier_address,
                rework_type: rework_type,
                supplier_type: supplier_type,
              },
              callback: function (r) {
                frappe.set_route("Form", "Work Order", r.message);
              },
            });
            d.hide();
          },
        });
        frm.rework_items = new frappe.production.ui.WOReworkPopUp(
          d.fields_dict.rework_items_html.wrapper,
        );
        frm.rework_items.load_data(r.message);
        d.show();
      }
    },
  });
}
