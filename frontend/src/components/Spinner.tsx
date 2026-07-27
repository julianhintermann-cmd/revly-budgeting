export function Spinner({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center p-6 ${className}`} role="status" aria-label="loading">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-emerald-600 dark:border-slate-700 dark:border-t-emerald-500" />
    </div>
  )
}
