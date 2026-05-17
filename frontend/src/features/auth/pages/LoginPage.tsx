import { FormEvent, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import backgroundImage from '../../../assets/background.png';
import logoImage from '../../../assets/logo.png';
import { useAuth } from '../hooks/useAuth';

export function LoginPage() {
  const { isAuthenticated, isRestoring, login } = useAuth();
  const [usernameOrEmail, setUsernameOrEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/';

  if (!isRestoring && isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login({ username_or_email: usernameOrEmail, password });
      navigate(from, { replace: true });
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : 'Login failed.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main
      className="relative flex min-h-screen items-center justify-center overflow-hidden bg-zinc-950 px-4 py-10 text-zinc-950"
      style={{
        backgroundImage: `linear-gradient(rgba(2, 6, 23, 0.42), rgba(3, 7, 18, 0.76)), url(${backgroundImage})`,
        backgroundPosition: 'center',
        backgroundSize: 'cover',
      }}
    >
      <section className="w-full max-w-sm rounded-lg border border-cyan-400/20 bg-zinc-950/82 p-6 text-zinc-100 shadow-2xl shadow-cyan-950/40 backdrop-blur-md">
        <div className="mb-6 text-center">
          <div
            aria-label="NexusOps"
            className="mx-auto h-20 w-72 max-w-full bg-center bg-no-repeat"
            role="img"
            style={{
              backgroundImage: `url(${logoImage})`,
              backgroundSize: '245%',
            }}
          />
          <p className="mt-3 text-sm text-zinc-400">Sign in to manage infrastructure operations.</p>
        </div>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-zinc-300">
            Username or email
            <input
              className="mt-1 w-full rounded-md border border-zinc-700 bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 shadow-sm outline-none transition placeholder:text-zinc-500 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400"
              autoComplete="username"
              value={usernameOrEmail}
              onChange={(event) => setUsernameOrEmail(event.target.value)}
              required
            />
          </label>
          <label className="block text-sm font-medium text-zinc-300">
            Password
            <input
              className="mt-1 w-full rounded-md border border-zinc-700 bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 shadow-sm outline-none transition placeholder:text-zinc-500 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400"
              autoComplete="current-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error ? (
            <p className="rounded-md border border-rose-400/30 bg-rose-950/50 px-3 py-2 text-sm text-rose-200">
              {error}
            </p>
          ) : null}
          <button
            className="w-full rounded-md bg-cyan-400 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  );
}
