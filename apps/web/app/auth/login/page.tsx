'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Terminal, Github, Mail, Key } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);

  const handleGoogleLogin = async () => {
    setLoading(true);
    // TODO: Implement Google OAuth
    window.location.href = '/api/auth/signin/google';
  };

  const handleGitHubLogin = async () => {
    setLoading(true);
    // TODO: Implement GitHub OAuth
    window.location.href = '/api/auth/signin/github';
  };

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    // TODO: Implement magic link email
    console.log('Sending magic link to:', email);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0a0a0f] px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex items-center gap-2">
            <Terminal className="h-8 w-8 text-cyan-400" />
            <span className="text-2xl font-bold">NexCode</span>
          </div>
          <h1 className="mb-2 text-xl font-semibold">Welcome back</h1>
          <p className="text-sm text-gray-400">Sign in to continue to NexCode</p>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-950 p-6">
          <div className="space-y-3">
            <button
              onClick={handleGoogleLogin}
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-md border border-gray-700 bg-gray-900 px-4 py-2.5 text-sm font-medium text-gray-200 hover:bg-gray-800 transition-colors disabled:opacity-50"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24">
                <path
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  fill="#4285F4"
                />
                <path
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  fill="#34A853"
                />
                <path
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  fill="#FBBC05"
                />
                <path
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  fill="#EA4335"
                />
              </svg>
              Continue with Google
            </button>

            <button
              onClick={handleGitHubLogin}
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-md border border-gray-700 bg-gray-900 px-4 py-2.5 text-sm font-medium text-gray-200 hover:bg-gray-800 transition-colors disabled:opacity-50"
            >
              <Github className="h-5 w-5" />
              Continue with GitHub
            </button>
          </div>

          <div className="my-6 flex items-center gap-4">
            <div className="flex-1 border-t border-gray-800" />
            <span className="text-xs text-gray-500">or continue with email</span>
            <div className="flex-1 border-t border-gray-800" />
          </div>

          <form onSubmit={handleEmailLogin} className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-gray-300">
                Email address
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="flex h-9 w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-1 text-sm text-gray-100 placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 transition-colors disabled:opacity-50"
            >
              <Mail className="h-4 w-4" />
              Send Magic Link
            </button>
          </form>

          <div className="mt-6 rounded-lg border border-gray-800 bg-gray-900/50 p-4">
            <div className="flex items-start gap-3">
              <Key className="mt-0.5 h-4 w-4 text-cyan-400" />
              <div>
                <p className="text-sm font-medium text-gray-200">CLI Authentication</p>
                <p className="mt-1 text-xs text-gray-400">
                  Run <code className="rounded bg-gray-800 px-1.5 py-0.5">nexcode auth login</code> in your terminal for CLI access.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
