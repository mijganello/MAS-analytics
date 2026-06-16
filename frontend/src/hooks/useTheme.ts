import { useState, useEffect } from 'react'

export type Theme = 'light' | 'dark' | 'projector'

const STORAGE_KEY = 'mas-theme'

function applyTheme(theme: Theme) {
  const root = document.documentElement
  root.classList.remove('dark', 'projector')
  if (theme !== 'light') root.classList.add(theme)
  localStorage.setItem(STORAGE_KEY, theme)
}

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light'
  const stored = localStorage.getItem(STORAGE_KEY) as Theme | null
  if (stored === 'dark' || stored === 'projector') return stored
  return 'light'
}

// Apply before first paint to avoid flash
const initial = getInitialTheme()
if (typeof document !== 'undefined') applyTheme(initial)

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(initial)

  const setTheme = (t: Theme) => {
    applyTheme(t)
    setThemeState(t)
  }

  useEffect(() => {
    applyTheme(theme)
  }, [])

  return { theme, setTheme }
}
