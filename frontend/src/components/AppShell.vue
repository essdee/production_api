<template>
	<div class="w-screen bg-gray-100 text-base">
		<TopBar />
		<div class="flex mx-auto w-full max-w-7xl overflow-hidden">
			<RouterView :key="route.fullPath" />
		</div>
	</div>
</template>

<script setup>
import TopBar from '@/components/TopBar.vue'
import auth from '@/utils/auth'
import { useRoute } from 'vue-router'
const route = useRoute()
</script>