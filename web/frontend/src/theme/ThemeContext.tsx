import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type ThemeMode = 'system' | 'light' | 'dark'
type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = 'dml_theme_mode'

interface ThemeContextValue {
  mode: ThemeMode
  resolvedTheme: ResolvedTheme
  setMode: (mode: ThemeMode) => void
  cycleMode: () => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function systemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function resolve(mode: ThemeMode): ResolvedTheme {
  return mode === 'system' ? (systemPrefersDark() ? 'dark' : 'light') : mode
}

const ORDER: ThemeMode[] = ['system', 'light', 'dark']

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system'
  })
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => resolve(mode))

  useEffect(() => {
    const apply = () => {
      const resolved = resolve(mode)
      setResolvedTheme(resolved)
      // Explicit single-value color-scheme (rather than the ambient "light dark") gives native
      // form controls (date/time pickers, scrollbars) an unambiguous signal, so they always
      // match our own theme instead of silently following the OS scheme when the two disagree.
      document.documentElement.dataset.theme = resolved
      document.documentElement.style.colorScheme = resolved
    }
    apply()

    if (mode !== 'system') return
    const mql = window.matchMedia('(prefers-color-scheme: dark)')
    mql.addEventListener('change', apply)
    return () => mql.removeEventListener('change', apply)
  }, [mode])

  function setMode(next: ThemeMode) {
    localStorage.setItem(STORAGE_KEY, next)
    setModeState(next)
  }

  function cycleMode() {
    setMode(ORDER[(ORDER.indexOf(mode) + 1) % ORDER.length])
  }

  const value = useMemo(() => ({ mode, resolvedTheme, setMode, cycleMode }), [mode, resolvedTheme])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider')
  return ctx
}
