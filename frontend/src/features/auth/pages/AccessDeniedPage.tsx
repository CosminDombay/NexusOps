import { Link } from 'react-router-dom';

export function AccessDeniedPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 text-zinc-950">
      <section className="w-full max-w-md rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-semibold">Access denied</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Your current role does not have permission to open this area.
        </p>
        <Link
          className="mt-5 inline-flex rounded-md bg-zinc-900 px-4 py-2 text-sm font-semibold text-white hover:bg-zinc-800"
          to="/"
        >
          Back to inventory
        </Link>
      </section>
    </main>
  );
}
