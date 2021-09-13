<template>
    <div class="new-item frappe-control">

        <table class="table table-sm table-bordered">
            <tr v-for="(i, index) in items" :key="index">
                <td>
                    <div class="row">
                        <div class="col">
                            <span class="bold"> Item: </span>{{ i.item }}
                        </div>
                        <div class="col">
                            <span class="bold"> Delivery Location: </span>{{ i.delivery_location }}
                        </div>
                        <div class="col">
                            <span class="bold"> Expected Delivery Date: </span>{{ i.delivery_date }}
                        </div>
                    </div>
                    <div v-if="is_local" class="pull-right cursor-pointer" @click="removeAt(index)" v-html="frappe.utils.icon('delete', 'md')"></div>
                    <div v-if="is_local" class="pull-right cursor-pointer" @click="edit(index)" v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
                    <table class="table table-sm table-bordered" v-if="i.variants && i.variants.length > 0">
                        <tr>
                            <th>S.No.</th>
                            <th>Lot</th>
                            <th v-for="attr in Object.keys(i.variants[0].attributes)" :key="attr">{{ attr }}</th>
                            <th v-for="attr in Object.keys(i.variants[0].values)" :key="attr">{{ attr == 'default' ? 'Quantity' : attr }}</th>
                        </tr>
                        <tr v-for="(variant, index) in i.variants" :key="index">
                            <td>{{ index + 1 }}</td>
                            <td>{{ variant.lot }}</td>
                            <td v-for="attr in variant.attributes" :key="attr">{{ attr }}</td>
                            <td v-for="attr in variant.values" :key="attr">
                                <div v-if="attr.qty">
                                    {{ attr.qty + ' ' + i.default_uom}}
                                    <span v-if="attr.secondary_qty">
                                        <br>
                                        ({{ attr.secondary_qty + ' ' + i.secondary_uom }})
                                    </span>
                                    <br>
                                    Rate: {{ attr.rate }}
                                </div>
                                <div v-else class="text-center">
                                    ---
                                </div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <form name="formp" class="form-horizontal" autocomplete="off" @submit.prevent="addItem()" v-if="is_local">
            <div class="row">
                <div class="item-control col-md-6"></div>
                <div class="col-md-2">
                    <button type="submit" class="btn btn-success">Add Item</button>
                </div>

            </div>
        </form>
    </div>
</template>

<script>
import NewItemDialog from './NewItemDialog.vue';

export default {
    name: 'new-item',
    data() {
        return {
            items: [],
            item: {},
            is_local: cur_frm.doc.__islocal,
            is_edit: false,
            edit_index: -1
        }
    },
    mounted() {
        console.log('new-item mounted');
        if(!cur_frm.doc.__islocal)
            this.items = cur_frm.doc.__onload.item_details;
        else
            this.create_item_input();
    },
    methods: {
        create_item_input: function() {
            this.item_input = frappe.ui.form.make_control({
                parent: $(this.$el).find('.item-control'),
                df: {
                    fieldtype: 'Link',
                    options: 'Item',
                    label: 'Item',
                    reqd: 1
                },
                render_input: true,
            });
        },
        clear_item_input: function() {
            this.item_input.set_input("");
        },
        show_item_dialog(item) {
            let me = this;
            this.d = new frappe.ui.Dialog({
                title: __('Item Details'),
                static: true,
                primary_action_label: 'Save',
                primary_action(values) {
                    let save_item = me.itemvm.$children[0].saveitem()
                    if(save_item) {
                        if(me.is_edit) {
                            me.$set(me.items, me.edit_index, save_item);
                            // me.items[me.edit_index] = save_item;
                            me.is_edit = false;
                            me.edit_index = -1;
                        } else {
                            me.items.push(save_item);
                        }
                        me.d.hide();
                        me.clear_item_input();
                        // To be uncommented if there is problem in escape shortcut key
                        // frappe.ui.keys.on('escape', function(e) {
                        //     me.close_grid_and_dialog();
                        // });

                        // frappe.ui.keys.on('esc', function(e) {
                        //     me.close_grid_and_dialog();
                        // });
                    }
                },
                secondary_action_label: 'Cancel',
                secondary_action(values) {
                    me.d.hide();
                }
            });
            frappe.call({
                method: 'production_api.production_api.doctype.item.item.get_attribute_details',
                args: {
                    item_name: item.item
                },
                callback: function(r) {
                    if(r.message) {
                        let attributes = r.message;
                        item['default_uom'] = attributes.default_uom,
                        item['secondary_uom'] = attributes.secondary_uom,
                        console.log(attributes);
                        me.itemvm = new Vue({
                        el: me.d.body,
                        render: (h) =>
                            h(NewItemDialog, {
                            props: {
                                item: item,
                                attributes: attributes.attributes,
                                primary_attribute_values: attributes.primary_attribute_values,
                                primary_attribute: attributes.primary_attribute,
                                default_uom: attributes.default_uom,
                                secondary_uom: attributes.secondary_uom,
                            },
                            }),
                        });
                        me.d.show();
                        frappe.ui.keys.off('escape');
			            frappe.ui.keys.off('esc');
                        // console.log(vm,d);
                        me.d.$wrapper.find('.modal-dialog').css("max-width", "1000px");
                    }
                }
            });
        },

        addItem() {
            var me = this;
            if(!this.item_input.get_value()) return;
            this.item = {
                item: this.item_input.get_value(),
                variants: []
            }
            this.show_item_dialog(this.item);
        },
        
        close_grid_and_dialog: function() {
            // close open grid row
            var open_row = $(".grid-row-open");
            if (open_row.length) {
                var grid_row = open_row.data("grid_row");
                grid_row.toggle_view(false);
                return false;
            }

            // close open dialog
            if (cur_dialog && !cur_dialog.no_cancel_flag) {
                cur_dialog.cancel();
                return false;
            }
        },

        removeAt(index) {
            if(this.is_edit){
                if(this.edit_index > index){
                    this.edit_index--;
                }
                else if(this.edit_index == index){
                    this.cancel_edit();
                }
            }
            this.items.splice(index, 1);
        },

        edit(index) {
            if(!this.is_edit) this.is_edit = !this.is_edit;
            this.edit_index = index;
            this.show_item_dialog(JSON.parse(JSON.stringify(this.items[index])));
        },

        cancel_edit() {
            this.is_edit = !this.is_edit;
            this.edit_index = -1;
            this.newVariant();
            this.clear_attribute_input();
        },
    }
}
</script>