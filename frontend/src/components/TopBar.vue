<template>
    <!-- We are using tailwind css -->
    <!-- Top Bar with Logo in the Left -->
    <header class="bg-white shadow-sm">
        <nav class="mx-auto flex max-w-7xl items-center justify-between p-2 lg:px-8" aria-label="Global">
    <!-- <div class="flex items-center justify-between"> -->
        <!-- Logo -->
            <div class="flex items-center">
                <!-- <div class="w-10 h-10 rounded-full bg-gray-300"></div> -->
                <Avatar label="MRP" size="md" />
                <!-- <div class="ml-2 text-gray-700">MRP</div> -->
                <template v-for="item in topBarItems" :key="item.label">
                    <router-link
                        :to="item.route"
                        class="ml-2 text-gray-700"
                        :class="route.path === item.route ? 'text-gray-900' : 'text-gray-700'"
                    >
                        {{ item.label }}
                    </router-link>
                </template>
            </div>
            <!-- Right side of Top Bar -->
            <div class="flex items-center">
                <Dropdown
                    placement="left"
                    :options="[
                        {
                            label: 'Switch to Desk',
                            icon: 'grid',
                            handler: () => open('/app'),
                        },
                        {
                            label: 'Logout',
                            icon: 'log-out',
                            handler: () => auth.logout(),
                        },
                    ]"
                >
                    <template v-slot="{ open }">
                        <button
                            class="flex w-full items-center space-x-2 rounded-md p-2 text-left text-base font-medium"
                            :class="open ? 'bg-gray-300' : 'hover:bg-gray-200'"
                        >
                            <Avatar
                                :label="auth.user.full_name"
                                :imageURL="auth.user.user_image"
                                size="md"
                            />
                            <span
                                class="rg:inline ml-2 hidden overflow-hidden text-ellipsis whitespace-nowrap"
                            >
                                {{ auth.user.full_name }}
                            </span>
                            <FeatherIcon name="chevron-down" class="rg:inline hidden h-4 w-4" />
                        </button>
                    </template>
                </Dropdown>
            </div>
    <!-- </div> -->
        </nav>
    </header>
</template>
    
<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import auth from '@/utils/auth'
import { Avatar } from 'frappe-ui'

const route = useRoute()
const open = (url1) => window.open(url1, '_blank')

const topBarItems = ref([
    {
        label: 'GRN',
        // icon: 'home',
        route: '/grn',
    },
])
</script>