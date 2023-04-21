<template>
    <!-- Display List Of GRN -->
    <List 
        v-if="grns && grns.data" 
        :data="grns.data" 
        :columns="columns" 
        :actions="[
            {
                label: 'New GRN',
                appearance: 'primary',
                iconLeft: 'plus',
                handler: () => router.push('/grn/create'),
            },
        ]"
        :rowClick="({ name }) => router.push({ name: 'GRNDetail', params: { name } })"
        class="m-6 px-6 py-2 rounded-md bg-white"
    >
        <template #title>
				<div class="flex items-center space-x-4">
					<div class="text-3xl font-medium text-gray-900">GRN</div>
				</div>
			</template>
			<template #empty-state>
				<div
					v-if="grns.data.length === 0"
					class="mt-2 flex h-full w-full flex-col items-center justify-center rounded-md text-base font-light text-gray-500"
				>
					<div class="text-base font-light text-gray-500">No GRN</div>
				</div>
			</template>
    </List>

</template>

<script setup>
import List from '@/components/List.vue'
import { ref, computed } from 'vue'
import { grns } from '@/data/grn.js'
import { useRouter } from 'vue-router'

const router = useRouter()

const columns = [
	{ label: 'Name', key: 'name'},
	{ label: 'Supplier', key: 'supplier'},
	{ label: 'Against', key: 'against'},
	{ label: 'Against Id', key: 'against_id'},
	{ label: 'Last Modified', key: 'modified'},
]
</script>