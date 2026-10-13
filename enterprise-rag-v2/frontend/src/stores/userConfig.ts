import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface SystemConfig {
  theme: 'light' | 'dark' | 'auto'
  language: 'zh-CN' | 'en-US'
  defaultPage: string
}

const STORAGE_KEY = 'app_user_config'

export const useUserConfigStore = defineStore('userConfig', () => {
  const config = ref<SystemConfig>({
    theme: 'light',
    language: 'zh-CN',
    defaultPage: '/'
  })

  const isLoaded = ref(false)

  const isDark = computed(() => {
    if (config.value.theme === 'auto') {
      return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
    }
    return config.value.theme === 'dark'
  })

  const effectiveTheme = computed<'light' | 'dark'>(() => {
    if (config.value.theme === 'auto') {
      return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
    }
    return config.value.theme as 'light' | 'dark'
  })

  const loadConfig = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        config.value = { ...config.value, ...parsed }
      }
      isLoaded.value = true
    } catch (e) {
      console.error('Failed to load user config:', e)
      isLoaded.value = true
    }
  }

  const saveConfig = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(config.value))
    } catch (e) {
      console.error('Failed to save user config:', e)
    }
  }

  const updateConfig = (newConfig: Partial<SystemConfig>) => {
    config.value = { ...config.value, ...newConfig }
    saveConfig()
    applyTheme()
  }

  const toggleTheme = () => {
    const currentTheme = config.value.theme
    let newTheme: 'light' | 'dark' | 'auto'

    if (currentTheme === 'light') {
      newTheme = 'dark'
    } else if (currentTheme === 'dark') {
      newTheme = 'auto'
    } else {
      newTheme = 'light'
    }

    updateConfig({ theme: newTheme })
  }

  const applyTheme = () => {
    const html = document.documentElement
    const themeToApply = effectiveTheme.value

    html.classList.add('theme-transition')

    if (themeToApply === 'dark') {
      html.classList.add('dark')
    } else {
      html.classList.remove('dark')
    }

    setTimeout(() => {
      html.classList.remove('theme-transition')
    }, 300)
  }

  const initThemeListener = () => {
    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        if (config.value.theme === 'auto') {
          applyTheme()
        }
      })
    }
  }

  const init = () => {
    loadConfig()
    applyTheme()
    initThemeListener()
  }

  return {
    config,
    isLoaded,
    isDark,
    effectiveTheme,
    loadConfig,
    saveConfig,
    updateConfig,
    toggleTheme,
    applyTheme,
    init
  }
})
