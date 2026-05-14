import type { ReactNode, ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  children: ReactNode
}

export default function Button({ variant = 'primary', children, className = '', ...rest }: ButtonProps) {
  const base = 'rounded-md px-4 py-2 text-sm font-semibold transition-colors duration-150 disabled:opacity-50 cursor-pointer'
  const styles: Record<Variant, string> = {
    primary:   'bg-accent hover:bg-accent-hover text-bg-base',
    secondary: 'border border-accent text-accent hover:bg-accent-subtle',
    ghost:     'text-text-secondary hover:text-text-primary',
  }
  return (
    <button className={`${base} ${styles[variant]} ${className}`} {...rest}>
      {children}
    </button>
  )
}
