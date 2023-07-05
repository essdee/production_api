// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

let total_count = 0;

frappe.ui.form.on('Lotwise Item Profit', {
	refresh: function(frm) {
		frm.add_custom_button(__('Recalculate'), function() {
			calculate_all(frm);
		});
		frm.page.add_menu_item(__("Calculate"), function() {
			calculate_all(frm);
		}, false, 'Ctrl+E', false);
	},

	validate: function(frm){
		calculate_all(frm);
	},

	item: function(frm) {
		if (frm.doc.item) {
			frappe.db.get_doc("FG Item Master", frm.doc.item).then(result => {
				console.log(result);
				let sizes = result.available_sizes.split(',');
				let prices_str = result.prices;
				let prices = []
				if (prices_str) {
					prices = prices_str.split(',');
				}
				console.log(sizes)
				console.log(prices)
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
	}
});

frappe.ui.form.on('Lotwise Item Profit Qty Rate', {
	rate: function(frm, cdt, cdn) {
		calculate_all(frm);
	},
	qty: function(frm, cdt, cdn) {
		calculate_all(frm);
	}
});

frappe.ui.form.on('Lotwise Item Profit Cloth Value', {
	qty: function(frm, cdt, cdn) {
		calculate_all(frm);
	},
	rate: function(frm, cdt, cdn) {
		calculate_all(frm);
	},
	knitting_cost: function(frm, cdt, cdn) {
		calculate_all(frm);
	},
	dyeing_cost: function(frm, cdt, cdn) {
		calculate_all(frm);
	},
	compacting_cost: function(frm, cdt, cdn) {
		calculate_all(frm);
	},
});

frappe.ui.form.on('Lotwise Item Profit Breakup', {
	cost: function(frm, cdt, cdn) {
		calculate_all(frm);
	}
});

frappe.ui.form.on('Lotwise Item Profit Additional Cost', {
	based_on: function(frm, cdt, cdn) {
		calculate_all(frm);
	},
	rate: function(frm, cdt, cdn) {
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
	let total_qty = 0, total_value = 0
	$.each(frm.doc.qty_rate_chart || [], function(i, v) {
		calculate_qty_rate(v)
		total_qty += (v.qty || 0);
		total_value += (v.net_rate || 0);
    })
	frm.doc.total_qty = total_qty;
	frm.doc.total_selling_value = total_value;
}

function calculate_total_cloth_value(frm) {
	let total = 0;
	$.each(frm.doc.cloth_value || [], function(i, v) {
        calculate_cloth_value(v)
		total += (v.net_rate || 0);
    })
	frm.doc.total_cloth_value = total;
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
	frm.doc.profit = get_numeric_value(frm, 'total_selling_value') - get_numeric_value(frm, 'cost_price');
	frm.doc.profit_percent = get_numeric_value(frm, 'profit') / get_numeric_value(frm, 'cost_price', 1) * 100;
}

function get_numeric_value(frm, key, fallback) {
	return frm.doc[key] || fallback || 0;
}

function calculate_qty_rate(row) {
	row.net_rate = (row.rate || 0) * (row.qty || 0);
}

function calculate_cloth_value(row) {
	row.total_cost = (row.rate || 0) + (row.knitting_cost || 0) + (row.dyeing_cost || 0) + (row.compacting_cost || 0);
	row.net_rate = (row.total_cost || 0) * (row.qty || 0);
}

const based_on_map = {
	'Total Qty': 'total_qty',
	'Total Value': 'total_selling_value',
	'Production Cost': 'production_cost',
}

function calculate_additional_cost(frm, row) {
	let calc_by_percent = ['Total Value', 'Production Cost'];
	if (calc_by_percent.includes(row.based_on)) {
		let value = frm.doc[based_on_map[row.based_on]] || 0;
		if (value) {
			row.total = ((row.rate || 0) / 100) * (value || 0);
		}
	} else {
		let value = frm.doc[based_on_map[row.based_on]];
		if (value) {
			row.total = (row.rate || 0) * (value || 0);
		}
	}
}