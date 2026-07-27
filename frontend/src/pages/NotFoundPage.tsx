import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <span className="text-5xl">🧭</span>
      <h1 className="text-2xl font-bold">404</h1>
      <Link to="/" className="text-emerald-600 hover:underline dark:text-emerald-400">
        revly budgeting
      </Link>
    </div>
  )
}
