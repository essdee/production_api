<template>
    <div>
        <h3>Colours</h3>
        <button @click="toggle_colours()" v-if="docstatus == 0" 
            style="margin-bottom:10px; padding:4px 10px; border-radius:6px; background:#eee; border:1px solid #ccc;"
        >
            {{ all_colours_selected ? 'Unselect All Colours' : 'Select All Colours' }}
        </button>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:6px; margin-bottom:10px;">
            <div v-for="c in colours" :key="c" style="display:flex; align-items:center;">
                <label style="display:flex; align-items:center; gap:6px;">
                    <input type="checkbox" v-model="c.selected" @click="make_dirty()" :disabled="docstatus != 0"/>
                    {{ c.colour }}
                </label>
            </div>
        </div>
    </div>
    <div style="margin-top:15px;">
        <h3>Sizes</h3>
        <button @click="toggle_sizes()" v-if="docstatus == 0"
            style="margin-bottom:10px; padding:4px 10px; border-radius:6px; background:#eee; border:1px solid #ccc;"
        >
            {{ all_sizes_selected ? 'Unselect All Sizes' : 'Select All Sizes' }}
        </button>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:6px;">
            <div v-for="s in sizes" :key="s" style="display:flex; align-items:center;">
                <label style="display:flex; align-items:center; gap:6px;">
                    <input type="checkbox" v-model="s.selected" @click="make_dirty()" :disabled="docstatus != 0"/>
                    {{ s.size }}
                </label>
            </div>
        </div>
    </div>
</template>


<script setup>
import { ref, onMounted, computed } from "vue";

let colours = ref([]);
let sizes = ref([]);
let docstatus = cur_frm.doc.docstatus

const all_colours_selected = computed(() => {
    return colours.value.length > 0 && colours.value.every(c => c.selected);
});

const all_sizes_selected = computed(() => {
    return sizes.value.length > 0 && sizes.value.every(s => s.selected);
});

function toggle_colours() {
    const value = !all_colours_selected.value;
    colours.value.forEach(c => c.selected = value);
    make_dirty();
}

function toggle_sizes() {
    const value = !all_sizes_selected.value;
    sizes.value.forEach(s => s.selected = value);
    make_dirty();
}

function get_data(){
    return {
        "colours": colours.value,
        "sizes": sizes.value,
    }
}

function make_dirty(){
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
}

function load_data(colour_size_data){
    colours.value = colour_size_data['colours']
    sizes.value = colour_size_data['sizes']
}

defineExpose({
    get_data,
    load_data
});
</script>
