// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

let total_count = 0;

frappe.ui.form.on('Lotwise Item Profit', {
	setup: function(frm) {
		frm.set_query('trade_discounts_template', function(doc) {
			return{
				filters: {
					type: 'Discounts',
				}
			}
		});
		frm.set_query('other_costs_template', function(doc) {
			return{
				filters: {
					type: 'Other',
				}
			}
		});
	},

	refresh: function(frm) {
		frm.add_custom_button(__('Recalculate'), function() {
			calculate_all(frm);
		});
		frm.page.add_menu_item(__("Calculate"), function() {
			calculate_all(frm);
		}, false, 'Ctrl+E', false);

		frm.add_custom_button(__('Calculate Rate'), function() {
			frappe.prompt({
				label: 'Markdown Percent',
				fieldname: 'percent',
				fieldtype: 'Percent',
			}, (values) => {
				calculate_backwards_rate(frm, values.percent);
			}, 'Enter the Required Percent')
		});

		frm.add_custom_button(__('Fetch Lot Qty'), function() {
			if (!frm.doc.lot) {
				frappe.msgprint("Please set Lot");
				return;
			}
			if (!frm.doc.lot_costing_type) {
				frappe.msgprint("Please set Lot Costing Type");
				return;
			}
			if (frm.doc.lot_costing_type != "Costing") {
				console.log("fetching lot")
				fetch_lot_qty(frm);
			}
		});
	},

	validate: function(frm){
		calculate_all(frm);
	},

	item: function(frm) {
		if (frm.doc.item) {
			frappe.db.get_doc("FG Item Master", frm.doc.item).then(result => {
				let sizes = result.available_sizes.split(',');
				let prices_str = result.prices;
				let prices = []
				if (prices_str) {
					prices = prices_str.split(',');
				}
				frm.doc.qty_rate_chart = []
				for (var i = 0;i < sizes.length;i++) {
					var price = 0
					if (sizes.length == prices.length) {
						price = prices[i];
					}
					frm.add_child('qty_rate_chart', {
						'size': sizes[i],
						'qty': 0,
						'rate': price,
					});
				}
				frm.refresh_field('qty_rate_chart')
			});
		}
	},

	gst: function(frm) {
		calculate_all(frm);
	},

	add_rate: function(frm) {
		let add_rate = get_numeric_value(frm, 'additional_rate');
		$.each(frm.doc.qty_rate_chart || [], (i, v) => {
			v.rate += add_rate;
		})
		frm.doc.additional_rate = 0;
		calculate_all(frm);
	},

	get_size_cloth_combination: function(frm) {
		let sizes = []
		$.each(frm.doc.qty_rate_chart || [], function(i, v) {
			if (!sizes.includes(v.size)) {
				sizes.push(v.size);
			}
		})
		let cloth_group = []
		$.each(frm.doc.cloth_value || [], function(i, v) {
			if (!cloth_group.includes(v.yarn)) {
				cloth_group.push(v.yarn);
			}
		})
		if (sizes.length > 0 && cloth_group.length > 0) {
			frm.doc.piece_cloth_weight = []
			for (let i = 0; i<cloth_group.length; i++) {
				for (let j = 0; j<sizes.length; j++) {
					frm.add_child('piece_cloth_weight', {
						'size': sizes[j],
						'cloth_group': cloth_group[i],
						'weight': 0.00,
					});
				}
			}
			frm.refresh_field('piece_cloth_weight');
		}
	},

	calculate_cloth_qty: function(frm) {
		let cloth_group_weight = {}
		$.each(frm.doc.piece_cloth_weight || [], function(i, v) {
			if (cloth_group_weight.hasOwnProperty(v.cloth_group)){
				cloth_group_weight[v.cloth_group] += (((v.weight || 0) / 1000) * get_size_qty(frm, v.size))
			} else {
				cloth_group_weight[v.cloth_group] = (((v.weight || 0) / 1000) * get_size_qty(frm, v.size))
			}
		})
		$.each(frm.doc.cloth_value || [], function(i, v) {
			if (cloth_group_weight.hasOwnProperty(v.yarn)) {
				v.qty = cloth_group_weight[v.yarn]
			}
		})
		frm.refresh_field('cloth_value')
		calculate_all(frm);
	},

	calculate_all: function(frm) {
		calculate_all(frm);
	},

	set_discount_template: function(frm) {
		if (!frm.doc.trade_discounts_template) return
		frappe.db.get_doc("Lotwise Item Profit Additional Cost Template", frm.doc.trade_discounts_template)
			.then(result => {
				console.log(result);
				frm.doc.trade_discounts = []
				$.each(result.value || [], function(i, v) {
					frm.add_child('trade_discounts', {
						'costing_name': v['costing_name'],
						'based_on': v['based_on'],
						'rate': v['rate'],
					});
				})
				frm.refresh_field('trade_discounts');
				calculate_all(frm);
			})
	},

	set_other_cost_template: function(frm) {
		if (!frm.doc.other_costs_template) return
		frappe.db.get_doc("Lotwise Item Profit Additional Cost Template", frm.doc.other_costs_template)
			.then(result => {
				console.log(result);
				frm.doc.other_costs = []
				$.each(result.value || [], function(i, v) {
					frm.add_child('other_costs', {
						'costing_name': v['costing_name'],
						'based_on': v['based_on'],
						'rate': v['rate'],
					});
				})
				frm.refresh_field('other_costs');
				calculate_all(frm);
			})
	},

	set_production_cost_template: function(frm) {
		if (!frm.doc.production_cost_template) return
		frappe.db.get_doc("Lotwise Item Profit Breakup Template", frm.doc.production_cost_template)
			.then(result => {
				console.log(result);
				frm.doc.cmt = []
				$.each(result.cmt || [], function(i, v) {
					frm.add_child('cmt', {
						'costing_name': v['costing_name'],
						'cost': v['cost'],
					});
				});
				frm.refresh_field('cmt');

				frm.doc.packing_materials = []
				$.each(result.packing_materials || [], function(i, v) {
					frm.add_child('packing_materials', {
						'costing_name': v['costing_name'],
						'cost': v['cost'],
					});
				});
				frm.refresh_field('packing_materials');

				frm.doc.trims = []
				$.each(result.trims || [], function(i, v) {
					frm.add_child('trims', {
						'costing_name': v['costing_name'],
						'cost': v['cost'],
					});
				});
				frm.refresh_field('trims');
				calculate_all(frm);
			})
	},
});

function fetch_lot_qty(frm) {
	console.log("fetching lot qty")
	let m = {
		"Planned Qty": "qty",
		"Cutting Qty": "cut_qty",
		"Final Qty": "final_qty",
	}
	frappe.call({
		method: "production_api.product_development.doctype.lotwise_item_profit.lotwise_item_profit.get_lot_qty",
		args: {
			"lot": frm.doc.lot,
			"type": m[frm.doc.lot_costing_type],
		}
	}).then((r) => {
		let data = r.message;
		$.each(frm.doc.qty_rate_chart || [], function(i, v) {
			if (data[frm.doc.qty_rate_chart[i].size]) {
				console.log(data[frm.doc.qty_rate_chart[i].size]);
				frm.doc.qty_rate_chart[i].qty = data[frm.doc.qty_rate_chart[i].size];
			}
		});
		frm.refresh_field("qty_rate_chart");
		calculate_all(frm)
	})
}

function get_size_qty(frm, size) {
	let qty = 0;
	$.each(frm.doc.qty_rate_chart || [], function(i, v) {
		if (frm.doc.qty_rate_chart[i].size == size) {
			qty = frm.doc.qty_rate_chart[i].qty;
			return false;
		}
	})
	return qty;
}

function calculate_backwards_rate(frm, percent) {
	// Calculate Groupwise avg_weight
	let qty_groups = {};
	$.each(frm.doc.qty_rate_chart || [], function(i, v) {
		if (qty_groups.hasOwnProperty(v.group_index)) {
			console.log('Qty', v.qty)
			let cloth_group = qty_groups[v.group_index].cloth_group || {}
			$.each(frm.doc.piece_cloth_weight || [], function(i, weight) {
				if (v.size == weight.size) {
					if (cloth_group.hasOwnProperty(weight.cloth_group)) {
						console.log('Value', (weight.weight/1000 * v.qty))
						cloth_group[weight.cloth_group] = {
							'total_qty': cloth_group[weight.cloth_group].total_qty + v.qty,
							'total_weight': cloth_group[weight.cloth_group].total_weight + (weight.weight/1000 * v.qty),
						}
					} else {
						console.log("Shouldnt happen")
						cloth_group[weight.cloth_group] = {
							'total_qty': v.qty,
							'total_weight': weight.weight/1000 * v.qty,
						}
					}
				}
			})
			qty_groups[v.group_index].values.push(v);
			qty_groups[v.group_index].cloth_group = cloth_group;
		} else  {
			let cloth_group = {}
			$.each(frm.doc.piece_cloth_weight || [], function(i, weight) {
				if (v.size == weight.size) {
					if (cloth_group.hasOwnProperty(weight.cloth_group)) {
						cloth_group[weight.cloth_group] = {
							'total_qty': cloth_group[weight.cloth_group].total_qty + v.qty,
							'total_weight': cloth_group[weight.cloth_group].total_weight + (weight.weight/1000 * v.qty),
						}
					} else {
						cloth_group[weight.cloth_group] = {
							'total_qty': v.qty,
							'total_weight': weight.weight/1000 * v.qty,
						}
					}
				}
			})
			qty_groups[v.group_index] = {
				values: [v],
				cloth_group: cloth_group,
			};
		}
		console.log(v.size, JSON.parse(JSON.stringify(qty_groups)))
    })
	// Calculate avg rate of cloth used
	let cloth_value = {};
	$.each(frm.doc.cloth_value || [], function(i, v) {
		cloth_value[v.yarn] = v.total_cost;
    })
	// Add other costs and percentage
	let cmt = get_numeric_value(frm, 'total_cmt');
	let pm = get_numeric_value(frm, 'packing_materials_total');
	let trims = get_numeric_value(frm, 'trims_total');
	let gst = get_numeric_value(frm, 'gst');

	let extra_per_cost = 0;
	let extra_mu = 0; // markup percent
	let total_md = (percent || 0) + (gst || 0); // markdown percent
	$.each(frm.doc.trade_discounts || [], function(i, v) {
		if (v.based_on == 'Total Qty') {
			extra_per_cost += v.rate;
		} else if (v.based_on == 'Total Value') {
			total_md += v.rate;
		} else if (v.based_on == 'Production Cost') {
			extra_mu += v.rate;
		}
	})
	$.each(frm.doc.other_costs || [], function(i, v) {
		if (v.based_on == 'Total Qty') {
			extra_per_cost += v.rate;
		} else if (v.based_on == 'Total Value') {
			total_md += v.rate;
		} else if (v.based_on == 'Production Cost') {
			extra_mu += v.rate;
		}
	})
	console.log('qty_groups', qty_groups)
	console.log('cloth_value', cloth_value)
	console.log('extra_per_cost', extra_per_cost)
	console.log('extra_mu', extra_mu)
	console.log('total_md', total_md)

	Object.entries(qty_groups).forEach(([k, v]) => {
		console.log('Group index: ', k)
		let total_cloth_value = 0;
		$.each(v.cloth_group, function(k1, v1) {
			let c_value = 0;
			if (cloth_value.hasOwnProperty(k1)) {
				let avg_weight = 0;
				if (v1.total_qty) {
					avg_weight = v1.total_weight / v1.total_qty
				}
				console.log(k1, "Cloth Weight", avg_weight)
				c_value = avg_weight * cloth_value[k1];
			}
			console.log(k1, "Cloth Value", c_value)
			total_cloth_value += c_value;
		})
		console.log('Cloth Value Per Pcs', total_cloth_value)
		let rate = total_cloth_value + cmt + pm + trims + extra_per_cost;
		console.log('rate', rate)
		rate += ((extra_mu/100) * rate);
		console.log('rate', rate)
		
		let final_rate = rate / (1 - (total_md/100));
		console.log('final_rate', final_rate)

		$.each(v.values || [], function(i, vi) {
			vi.rate = final_rate;
		})
	});

	calculate_all(frm);
}

frappe.ui.form.on('Lotwise Item Profit Qty Rate', {
	group_index: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.group_index = parseInt(row.group_index);
		calculate_all(frm);
	},
	weight: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.weight = parseFloat(row.weight);
		calculate_all(frm);
	},
	ratio: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.ratio = parseInt(row.ratio);
		calculate_all(frm);
	},
	rate: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.rate = parseFloat(row.rate);
		calculate_all(frm);
	},
	qty: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.qty = parseInt(row.qty);
		calculate_all(frm);
	}
});

frappe.ui.form.on('Lotwise Item Profit Cloth Value', {
	ratio: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.qty = parseInt(row.qty);
		calculate_all(frm);
	},
	qty: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.rate = parseFloat(row.rate);
		calculate_all(frm);
	},
	rate: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.rate = parseFloat(row.rate);
		calculate_all(frm);
	},
	knitting_cost: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.knitting_cost = parseFloat(row.knitting_cost);
		calculate_all(frm);
	},
	dyeing_cost: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.dyeing_cost = parseFloat(row.dyeing_cost);
		calculate_all(frm);
	},
	compacting_cost: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.compacting_cost = parseFloat(row.compacting_cost);
		calculate_all(frm);
	},
	wastage_allowance: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.wastage_allowance = parseFloat(row.wastage_allowance);
		calculate_all(frm);
	},
});

frappe.ui.form.on('Lotwise Item Profit Breakup', {
	cost: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.cost = parseFloat(row.cost);
		calculate_all(frm);
	}
});

frappe.ui.form.on('Lotwise Item Profit Additional Cost', {
	based_on: function(frm, cdt, cdn) {
		calculate_all(frm);
	},
	rate: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn)
		row.rate = parseFloat(row.rate);
		calculate_all(frm);
	},
});

function refresh_fields(frm, fields) {
	if (!fields || fields.length == 0) {
		fields = [];
		frm.layout.fields.forEach(field => {
			let non_refresh_fields = ['Column Break', 'Section Break', 'Tab Break'];
			if (!non_refresh_fields.includes(field.fieldtype)) {
				fields.push(field.fieldname);
			}
		})
	}
	fields.forEach(field => {
		frm.refresh_field(field)
	})
}

function calculate_all(frm) {
	calculate_qty_rate_chart(frm);
	calculate_total_cloth_value(frm);
	calculate_production_cost(frm);
	calculate_additional_costs(frm);
	calculate_total(frm);
	refresh_fields(frm);
	frm.dirty();
	console.log(++total_count);
}

function calculate_qty_rate_chart(frm) {
	let total_qty = 0, total_value = 0, total_weight = 0;
	$.each(frm.doc.qty_rate_chart || [], function(i, v) {
		calculate_qty_rate(v)
		total_weight += ((v.qty || 0) * (v.weight || 0))
		total_qty += (v.qty || 0);
		total_value += (v.net_rate || 0);
    })
	frm.doc.total_qty = total_qty;
	frm.doc.total_selling_value = total_value;
	frm.doc.total_weight = total_weight;
}

function calculate_total_cloth_value(frm) {
	let total = 0;
	$.each(frm.doc.cloth_value || [], function(i, v) {
        calculate_cloth_value(v)
		total += (v.net_rate || 0);
    })
	frm.doc.total_cloth_value = total;
	if (frm.doc.total_qty) {
		frm.doc.cloth_value_per_piece = total / frm.doc.total_qty;
	} else {
		frm.doc.cloth_value_per_piece = 0;
	}
}

function calculate_production_cost(frm) {
	let cmt = 0;
	$.each(frm.doc.cmt || [], function(i, v) {
        cmt += (v.cost || 0);
    })
	let packing_material = 0;
	$.each(frm.doc.packing_materials || [], function(i, v) {
        packing_material += (v.cost || 0);
    })
	let trims = 0;
	$.each(frm.doc.trims || [], function(i, v) {
        trims += (v.cost || 0);
    })
	let total = (cmt + packing_material + trims) * (frm.doc.total_qty || 0);
	frm.doc.total_cmt = cmt;
	frm.doc.packing_materials_total = packing_material;
	frm.doc.trims_total = trims;
	frm.doc.production_cost_per_piece = cmt + packing_material + trims
	frm.doc.production_cost = (frm.doc.total_cloth_value || 0) + total;
}

function calculate_additional_costs(frm) {
	let trade_discount = 0;
	$.each(frm.doc.trade_discounts || [], function(i, v) {
        calculate_additional_cost(frm, v);
		trade_discount += (v.total || 0);
    })
	let other_cost = 0;
	$.each(frm.doc.other_costs || [], function(i, v) {
        calculate_additional_cost(frm, v)
        other_cost += (v.total || 0);
    })
	frm.doc.total_trade_discount = trade_discount;
	frm.doc.total_other_cost = other_cost;
}

function calculate_total(frm) {
	let gst = (get_numeric_value(frm, 'gst') / 100) * (get_numeric_value(frm, 'total_selling_value') - get_numeric_value(frm, 'total_trade_discount'))
	frm.doc.gst_value = gst;
	frm.doc.cost_price = get_numeric_value(frm, 'production_cost') + get_numeric_value(frm, 'total_trade_discount') + get_numeric_value(frm, 'total_other_cost') + gst;
	if (frm.doc.total_qty) {
		frm.doc.avg_cost_per_piece = get_numeric_value(frm, 'cost_price') / frm.doc.total_qty;
		frm.doc.avg_rate_per_piece = get_numeric_value(frm, 'total_selling_value') / frm.doc.total_qty;
	} else {
		frm.doc.avg_cost_per_piece = 0
		frm.doc.avg_rate_per_piece = 0
	}
	frm.doc.profit = get_numeric_value(frm, 'total_selling_value') - get_numeric_value(frm, 'cost_price');
	frm.doc.profit_percent = get_numeric_value(frm, 'profit') / get_numeric_value(frm, 'cost_price', 1) * 100;
	frm.doc.profit_percent_markdown = get_numeric_value(frm, 'profit') / get_numeric_value(frm, 'total_selling_value', 1) * 100;
}

function get_numeric_value(frm, key, fallback) {
	return numeric_value(frm.doc, key, 0);
	return Number(frm.doc[key]) || fallback || 0;
}

function numeric_value(data, key, fallback) {
	return Number(data[key]) || fallback || 0;
}

function calculate_qty_rate(row) {
	row.net_rate = numeric_value(row,'rate') * numeric_value(row, 'qty');
}

function calculate_cloth_value(row) {
	row.total_cost = numeric_value(row, 'rate') + numeric_value(row, 'knitting_cost') + numeric_value(row, 'dyeing_cost') + numeric_value(row, 'compacting_cost');
	row.total_cost = numeric_value(row, 'total_cost') + (numeric_value(row, 'total_cost') * numeric_value(row, 'wastage_allowance')/100);
	row.net_rate = numeric_value(row, 'total_cost') * numeric_value(row, 'qty');
}

const based_on_map = {
	'Total Qty': 'total_qty',
	'Total Value': 'total_selling_value',
	'Production Cost': 'production_cost',
}

function calculate_additional_cost(frm, row) {
	let calc_by_percent = ['Total Value', 'Production Cost'];
	if (calc_by_percent.includes(row.based_on)) {
		let value = numeric_value(frm.doc, based_on_map[row.based_on]);
		if (value) {
			row.total = (numeric_value(row, 'rate') / 100) * (value || 0);
		}
	} else {
		let value = numeric_value(frm.doc, based_on_map[row.based_on]);
		if (value) {
			row.total = numeric_value(row, 'rate') * (value || 0);
		}
	}
}