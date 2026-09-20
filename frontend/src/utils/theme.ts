import { computed, ref } from 'vue'

type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'theme'

const readStored = (): ThemeMode | null => {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

const media = window.matchMedia('(prefers-color-scheme: dark)')
const stored = readStored()

// 没手动选过主题时跟随系统；手动切换后固定下来并记住
let followSystem = stored === null
export const themeMode = ref<ThemeMode>(stored ?? (media.matches ? 'dark' : 'light'))
export const isDark = computed(() => themeMode.value === 'dark')

const apply = () => document.documentElement.setAttribute('data-theme', themeMode.value)

export function initTheme() {
  apply()
  media.addEventListener('change', (e) => {
    if (!followSystem) return
    themeMode.value = e.matches ? 'dark' : 'light'
    apply()
  })
}

export function toggleTheme() {
  followSystem = false
  themeMode.value = themeMode.value === 'dark' ? 'light' : 'dark'
  try {
    localStorage.setItem(STORAGE_KEY, themeMode.value)
  } catch {
    /* 隐私模式下写不进去，本次会话内仍然生效 */
  }
  apply()
}
