import React from 'react'
import type { TextBlock } from '@/types/blocks'
import { cn } from '@/lib/utils'

const styleMap = {
  body: 'prose prose-sm max-w-none text-foreground',
  heading: 'text-xl font-semibold text-foreground mt-2',
  callout: 'border-l-4 border-primary pl-4 bg-primary/5 py-3 rounded-r-lg text-sm',
  quote: 'border-l-4 border-muted-foreground/30 pl-4 italic text-muted-foreground',
}

export const TextBlockComponent: React.FC<TextBlock> = ({ content, style = 'body', title }) => (
  <div className="space-y-2">
    {title && style !== 'heading' && (
      <h3 className="font-semibold text-foreground">{title}</h3>
    )}
    <div className={cn(styleMap[style])}>
      {style === 'heading' ? (
        <h2 className="text-xl font-bold">{content}</h2>
      ) : (
        <p className="whitespace-pre-wrap leading-relaxed">{content}</p>
      )}
    </div>
  </div>
)
