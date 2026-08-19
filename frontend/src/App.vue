<template>
  <router-view v-if="$route.path === '/login' || $route.path.startsWith('/admin')" />
  <AppShell v-else>
    <router-view />
  </AppShell>
  <AppToasts />
</template>

<script setup lang="ts">
import AppShell from './components/AppShell.vue'
import AppToasts from './components/AppToasts.vue'
</script>
