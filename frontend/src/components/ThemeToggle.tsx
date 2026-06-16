import React from 'react'
import { Sun, Moon, Accessibility } from 'lucide-react'
import { useTheme } from '@/hooks/useTheme'
import type { Theme } from '@/hooks/useTheme'
import { cn } from '@/lib/utils'

const THEMES: { id: Theme; icon: React.ComponentType<{ className?: string }>; label: string }[] = [
  { id: 'light',     icon: Sun,           label: 'Светлая (ГОСТ)'               },
  { id: 'projector', icon: Accessibility, label: 'Доступность — 1С-стиль, крупный шрифт' },
  { id: 'dark',      icon: Moon,          label: 'Тёмная'                       },
]

export const ThemeToggle: React.FC = () => {
  const { theme, setTheme } = useTheme()

  return (
    <div className="inline-flex items-center rounded-full bg-muted/70 p-0.5 gap-0.5">
      {THEMES.map(({ id, icon: Icon, label }) => (
        <button
          key={id}
          type="button"
          onClick={() => setTheme(id)}
          title={label}
          className={cn(
            'h-7 w-7 flex items-center justify-center rounded-full transition-all duration-200',
            theme === id
              ? 'bg-card text-foreground shadow-sm scale-105'
              : 'text-muted-foreground hover:text-foreground hover:bg-card/50',
          )}
        >
          <Icon className="h-3.5 w-3.5" />
        </button>
      ))}
    </div>
  )
}
