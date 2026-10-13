<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

const props = withDefaults(
  defineProps<{
    option: EChartsOption
    height?: string
  }>(),
  { height: '300px' },
)

const emit = defineEmits<{ (e: 'click', params: Record<string, unknown>): void }>()

const el = ref<HTMLDivElement | null>(null)
let chart: ReturnType<typeof echarts.init> | null = null

function render(): void {
  if (!el.value) return
  if (!chart) {
    chart = echarts.init(el.value)
    chart.on('click', (params) => emit('click', params as unknown as Record<string, unknown>))
  }
  chart.setOption(props.option, true)
}

function resize(): void {
  chart?.resize()
}

function dispose(): void {
  chart?.dispose()
  chart = null
}

onMounted(() => {
  render()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  dispose()
})

watch(
  () => props.option,
  () => render(),
  { deep: true },
)
</script>

<template>
  <div ref="el" class="base-chart" :style="{ height }" />
</template>

<style scoped>
.base-chart {
  width: 100%;
}
</style>
