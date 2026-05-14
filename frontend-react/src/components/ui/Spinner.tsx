export default function Spinner() {
  return (
    <div
      className="w-5 h-5 rounded-full border-2 animate-spin"
      style={{ borderColor: 'var(--color-border)', borderTopColor: 'var(--color-accent)' }}
    />
  )
}
