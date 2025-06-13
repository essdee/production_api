<template>
	<div>
        <div v-for="received_type in Object.keys(items)" :key="received_type">
            <h3>{{ received_type }}</h3>
            <table class="table table-sm table-bordered">
                <tr v-for="(i, item_index) in items[received_type]" :key="item_index">
                    <td v-if="i.primary_attribute">
                        <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                            <tr>
                                <th>S.No.</th>
                                <th>Item</th>
                                <th>Lot</th>
                                <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                                <th v-for="attr in i.primary_attribute_values" :key="attr"> {{ attr }} </th>
                            </tr>
                            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                <td>{{ item1_index + 1 }}</td>
                                <td>{{ j.name }}</td>
                                <td>{{ j.lot }}</td>
                                <td v-for="attr in i.attributes" :key="attr"> 
                                    {{ j.attributes[attr] }} 
                                    <span v-if="attr == i.pack_attr && j.attributes[attr] != j.item_keys['major_colour']">({{ j.item_keys['major_colour'] }})</span>
                                </td>
                                <td v-for="attr in j.values" :key="attr">
                                    {{ attr.qty}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                                    <div style="display:block;">Pending Qty:{{attr.pending_quantity}}</div>
                                </td>
                            </tr>
                        </table>
                    </td>
                    <td v-else>
                        <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                            <tr>
                                <th>S.No.</th>
                                <th>Item</th>
                                <th>Lot</th>
                                <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                                <th>Quantity</th>
                                <th>Pending Quantity</th>
                            </tr>
                            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                <td>{{ item1_index + 1 }}</td>
                                <td>{{ j.name }}</td>
                                <td>{{ j.lot }}</td>
                                <td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
                                <td>
                                    {{ j.values["default"].qty}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                                </td>
                                <td>
                                    {{ j.values['default']['pending_quantity'] }}
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </div>    
	</div>	
</template>
	
<script setup>
import { ref } from 'vue';

let items = ref({})

function load_data(item){
    items.value = item
}
defineExpose({
    load_data,
})

</script>
	