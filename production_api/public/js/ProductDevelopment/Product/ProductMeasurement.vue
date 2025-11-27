<template>
    <div class="wrapper">
        <div class="table-card" v-for="(rows, key) in items" :key="key">
            <div class="table-header">
                {{ key }} Description
            </div>
            <div class="table-body">
                <div class="row-item" v-for="(row, idx) in rows" :key="idx">
                    <div class="sno">{{ idx + 1 }}</div>
                    <input 
                        type="text" 
                        v-model="items[key][idx]"
                        class="input-box" 
                        placeholder="Enter text..."
                        @blur="make_dirty()"
                    />
                    <button class="delete-btn" @click="delete_row(key, idx)">
                        ✕
                    </button>
                </div>
                <button class="add-btn" @click="add_row(key)">
                    + Add Row
                </button>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from "vue";

let items = ref({});

function add_row(key) {
    items.value[key].push("");
}

function delete_row(key, idx) {
    items.value[key].splice(idx, 1);
}

onMounted(() => {
    if (cur_frm.doc.is_set_item) {
        items.value.Top = items.value.Top || [];
        items.value.Bottom = items.value.Bottom || [];
    } else {
        items.value.Product = items.value.Product || [];
    }
});

function load_data(data) {
    items.value = {};
    Object.assign(items.value, data);
}

function get_data() {
    return items.value;
}

function make_dirty(){
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
}

defineExpose({
    load_data,
    get_data
});
</script>

<style> 

.wrapper { 
    width: 100%;
    display: flex;
    gap: 16px;
} 
.table-card { 
    width: 100%;
    border: 1px solid #e3e6ea;
    border-radius: 8px;
    background: #ffffff;
    padding: 12px 16px;
    box-shadow: 0px 1px 3px rgba(0,0,0,0.05);
} 
.table-header { 
    font-size: 15px;
    font-weight: 600;
    color: #333;
    margin-bottom: 10px;
} 
.table-body { 
    display: flex;
    flex-direction: column;
    gap: 10px;
} 
.row-item { 
    display: flex;
    align-items: center;
    gap: 8px;
} 
.input-box { 
    width: 100%;
    padding: 7px 10px;
    border: 1px solid #cfd3d8;
    border-radius: 6px;
    font-size: 14px;
    outline: none;
    background: #fafbfd;
    transition: 0.2s;
} 
.input-box:focus { 
    border-color: #4a8df6;
    background: #fff;
} 
.add-btn { 
    align-self: start;
    padding: 6px 12px;
    font-size: 13px;
    border-radius: 6px;
    border: 1px solid #d0d5dd;
    background: #f7f8fa;
    cursor: pointer;
    transition: 0.2s;
} 
.add-btn:hover { 
    background: #eef0f3;
} 
.delete-btn { 
    border: none;
    background: #f2f3f5;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    color: #666;
    transition: 0.2s;
} 
.delete-btn:hover { 
    background: #e3e5e8;
    color: #c00;
}
.sno {
    width: 28px;
    text-align: center;
    font-size: 13px;
    color: #444;
    background: #f1f2f4;
    padding: 6px 0;
    border-radius: 4px;
    border: 1px solid #dcdfe3;
}
</style>