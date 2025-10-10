<template>
    <div class="table-container">
		<table>
			<tr>
				<th></th>
				<th v-for="action in Object.keys(items)" :key="action">{{ action }}</th>
			</tr>
			<tr>
				<td>Planned Date</td>
				<td v-for="(action, key) in items" :key="key">{{ get_date(action['planned']) }}</td>
			</tr>
			<tr style="background-color: bisque;">
				<td>Freeze Date</td>
				<td v-for="(action, key) in items" :key="key">{{ get_date(action['freeze_date']) }}</td>
			</tr>
			<template v-for="(row, idx) in items[Object.keys(items)[0]]['rescheduled_dates']" :key="idx">
				<tr>
					<td>Rescheduled Date {{ idx + 1 }}</td>
					<td v-for="(action, key) in items" :key="key">{{ get_date(action['rescheduled_dates'][idx]) }}</td>
				</tr>
			</template>
			<tr>
				<td>Delay</td>
				<td v-for="(action, key) in items" :key="key">{{ action['date_diff'] }}</td>
			</tr>
			<tr>
				<td>Cumulative Actual Delay</td>
				<td v-for="(action, key) in items" :key="key">{{ action['actual_delay'] }}</td>
			</tr>
			<tr>
				<td>Cumulative Rescheduled Delay</td>
				<td v-for="(action, key) in items" :key="key">{{ action['cumulative_delay'] }}</td>
			</tr>
			<tr>
				<td>Reason</td>
				<td v-for="(action, key) in items" :key="key">{{ action['reason'] }}</td>
			</tr>
			<tr>
				<td>Performance</td>
				<td v-for="(action, key) in items" :key="key">{{ action['performance'] }}%</td>
			</tr>
		</table>
    </div>
</template>
  
<script setup>
import { ref, watch } from 'vue'

const props = defineProps(['rescheduled_details'])
const items = ref({})

watch(
() => props.rescheduled_details,
(newVal) => {
	items.value = newVal
},
{ immediate: true }
)

function get_date(date){
    if(date){
        let x = new Date(date)
        return x.getDate() + "-" + (x.getMonth() + 1) + "-" + x.getFullYear()
    }
    return ""
}

</script>

<style scoped>
.table-container {
	width: 100%;
	max-height: 400px; 
	overflow: auto; 
	border-radius: 8px;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
	background: #fff;
	max-width: 100%;
	padding-bottom: 4px;
}

.table-container::-webkit-scrollbar {
	height: 6px;
	width: 6px;
}
.table-container::-webkit-scrollbar-thumb {
	background: #c5c5c5;
	border-radius: 3px;
}
.table-container::-webkit-scrollbar-thumb:hover {
	background: #999;
}

table {
	min-width: 600px;
	border-collapse: collapse;
	font-family: 'Inter', sans-serif;
	font-size: 13px;
	background: #fff;
}

th, td {
	border: 1px solid #ddd;
	padding: 6px 10px;
	text-align: center;
	vertical-align: middle;
	white-space: nowrap;
}

th {
	background-color: #f5f6fa;
	color: #333;
	font-weight: 600;
	text-transform: capitalize;
	position: sticky;
	top: 0;
	z-index: 3;
}

td:first-child, th:first-child {
	background-color: #f9fafc;
	font-weight: 500;
	text-align: left;
	position: sticky;
	left: 0;
	z-index: 4;
}

tr:nth-child(even) td {
	background-color: #fafafa;
}

/* tr:hover td {
	background-color: #f0f7ff;
	transition: background-color 0.2s ease;
} */

table tr:first-child th:first-child {
	border-top-left-radius: 8px;
}

table tr:first-child th:last-child {
	border-top-right-radius: 8px;
}
</style>
