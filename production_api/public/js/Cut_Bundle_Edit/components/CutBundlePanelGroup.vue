<template>
    <div>
        <div v-if="props.panels">
            <table style="width:100%;">
                <tr>
                    <th style="width:5%;">S.No</th>
                    <th style="width:30%;">Group Panel</th>
                    <th style="width:40%;">Split Groups</th>
                    <th style="width:25%;"></th>
                </tr>
                <tr v-for="(panel, idx) in props.panels" :key="panel">
                    <td>{{ idx + 1 }}</td>
                    <td>{{ panel }}</td>
                    <td>
                        <div v-for="(group, index) in panel_groups[panel]" :key="index" class="group-item">
                            <span>{{ group }}</span>
                            <svg class="x-icon" xmlns="http://www.w3.org/2000/svg"
                                viewBox="0 0 24 24" @click="removeGroup(panel, index)" title="Remove group">
                                <line x1="18" y1="6" x2="6" y2="18" />
                                <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </div>
                        <div style="text-align: center;" @click="create_tool_tip_index(idx, panel)">
                            <button class="plus-btn-style">Add Group</button>
                        </div>
                    </td>
                    <td>
                        <div v-if="tooltipindex === idx" class="tooltip-area">
                            <div v-for="(key, panel) in current_group" :key="panel" class="checkbox-row">
                            <label>
                                <input type="checkbox" v-model="current_group[panel]" />
                                {{ panel }}
                            </label>
                            </div>
                            <button class="plus-btn-style" @click="add_groups(panel)">Add</button>
                        </div>
                    </td>
                </tr>
            </table>
        </div>
    </div>
</template>
  
<script setup>
import { watch, ref } from 'vue'

const props = defineProps(['panels'])
let panel_groups = ref({})
let tooltipindex = ref(null)
let current_group = ref({})

function processPanels(panels) {
    for (let i = 0; i < panels.length; i++) {
        panel_groups.value[panels[i]] = []
    }
}

function create_tool_tip_index(index, panel) {
    tooltipindex.value = index
    current_group.value = {}
    let panels = panel.split(',')
    for (let i = 0; i < panels.length; i++) {
        current_group.value[panels[i]] = false
    }
}

function add_groups() {
    let selected_groups = []
    for (const [key, value] of Object.entries(current_group.value)) {
        if (value) {
        selected_groups.push(key)
        }
    }
    if (selected_groups.length > 0) {
        panel_groups.value[props.panels[tooltipindex.value]].push(selected_groups.join(","))
    }
    tooltipindex.value = null
    current_group.value = {}
}

function removeGroup(panel, index) {
    if (panel_groups.value[panel]) {
        panel_groups.value[panel].splice(index, 1)
    }
}

watch(
    () => props.panels,
    (newPanels) => {
        if (newPanels && newPanels.length) {
            processPanels(newPanels)
        }
    },
    { immediate: true }
)

defineExpose({
    panel_groups,
})
</script>

<style scoped>
table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin-top: 20px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    border-radius: 8px;
    overflow: hidden;
}

th,td {
    padding: 12px 16px;
    text-align: left;
    border-bottom: 1px solid #e0e0e0;
}

th {
    background-color: #f5f7fa;
    font-weight: 600;
    color: #333;
    font-size: 15px;
}

tr:hover td {
    background-color: #fafafa;
    transition: background-color 0.3s ease;
}

.group-item {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    padding: 6px 14px;
    background-color: #eef4fb;
    border-radius: 20px;
    font-size: 14px;
    color: #3178c6;
    box-shadow: 0 2px 6px rgba(49, 120, 198, 0.15);
    user-select: none;
}

.x-icon {
    width: 20px;
    height: 20px;
    cursor: pointer;
    stroke: #5a5a5a;
    stroke-width: 3;
    background-color: #d9e4f5;
    border-radius: 50%;
    padding: 2px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
    transition: all 0.25s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.x-icon:hover {
    stroke: #e74c3c;
    background-color: #f8d7da;
    box-shadow: 0 4px 8px rgba(231, 76, 60, 0.4);
}

.tooltip-area {
    margin-top: 10px;
    padding: 12px 18px;
    background: #ffffff;
    border: 1px solid #d1d9e6;
    border-radius: 8px;
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.08);
    font-size: 14px;
}

.checkbox-row {
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.plus-btn-style {
    background-color: #3178c6;
    border: none;
    color: white;
    font-size: 16px;
    padding: 0px 12px;
    border-radius: 24px;
    cursor: pointer;
    font-weight: 600;
    transition: background-color 0.3s ease;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    user-select: none;
}

.plus-btn-style:hover {
    background-color: #215a8e;
}

td > div[style*='text-align: right'] {
    cursor: pointer;
    padding: 6px;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    transition: background-color 0.2s ease;
    border-radius: 6px;
    user-select: none;
}

td > div[style*='text-align: right']:hover {
    background-color: #eef4fb;
}
</style>
  