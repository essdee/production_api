<template>
	<div class="flex flex-1 overflow-hidden bg-gray-50 text-base">
		<!-- Todo: Add Top Bar -->
		<div class="flex flex-1 flex-col overflow-hidden">
			<RouterView :key="route.fullPath" />
		</div>
	</div>
</template>

<script setup>
import auth from '@/utils/auth'
import { useRoute } from 'vue-router'
const route = useRoute()
</script>