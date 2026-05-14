export default function SectionLabel({ children }: { children: string }) {
  return (
    <p
      className="uppercase mb-3 pb-2"
      style={{
        fontSize: 'var(--text-xs)',
        fontFamily: 'var(--font-body)',
        letterSpacing: 'var(--tracking-caps)',
        color: 'var(--color-text-secondary)',
        borderBottom: '1px solid var(--color-border)',
      }}
    >
      {children}
    </p>
  )
}
