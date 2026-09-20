<template>
  <router-view v-if="$route.path === '/login' || $route.path.startsWith('/admin')" />
  <AppShell v-else>
    <router-view v-slot="{ Component, route }">
      <Transition name="page" mode="out-in">
        <component :is="Component" :key="String(route.name ?? route.path)" />
      </Transition>
    </router-view>
  </AppShell>
  <CurrentAgentFloat v-if="$route.path !== '/login' && !$route.path.startsWith('/admin')" />
  <OnboardingLayer v-if="$route.path !== '/login' && !$route.path.startsWith('/admin')" />
  <AppToasts />
</template>

<script setup lang="ts">
import AppShell from './components/AppShell.vue'
import AppToasts from './components/AppToasts.vue'
import CurrentAgentFloat from './components/CurrentAgentFloat.vue'
import OnboardingLayer from './components/onboarding/OnboardingLayer.vue'
</script>
