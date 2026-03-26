import Link from 'next/link';
import { Terminal, Zap, Shield, Globe } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <Terminal className="h-6 w-6 text-cyan-400" />
            <span className="text-xl font-bold">NexCode</span>
          </div>
          <nav className="flex items-center gap-4">
            <Link
              href="/auth/login"
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/auth/login"
              className="inline-flex items-center justify-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
            >
              Get Started
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <section className="container mx-auto flex flex-col items-center justify-center px-4 py-24 text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-gray-800 bg-gray-900 px-4 py-1.5 text-sm text-gray-400">
            <Zap className="h-4 w-4 text-cyan-400" />
            <span>Multi-Provider AI Coding Assistant</span>
          </div>
          <h1 className="mb-6 text-5xl font-bold tracking-tight">
            Code with{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-500 to-cyan-400">
              any AI model
            </span>
          </h1>
          <p className="mb-8 max-w-2xl text-lg text-gray-400">
            NexCode is Claude Code, but for everyone, with every model.
            Plug in your API key from any provider and start coding with AI assistance.
          </p>
          <div className="flex gap-4">
            <Link
              href="/auth/login"
              className="inline-flex items-center justify-center rounded-md bg-indigo-600 px-6 py-3 text-base font-medium text-white hover:bg-indigo-700 transition-colors"
            >
              Start Coding
            </Link>
            <Link
              href="https://github.com/uzerkayat2004-gif/nexcode"
              className="inline-flex items-center justify-center rounded-md border border-gray-700 bg-transparent px-6 py-3 text-base font-medium text-gray-200 hover:bg-gray-800 transition-colors"
            >
              View on GitHub
            </Link>
          </div>
        </section>

        <section className="border-t border-gray-800 bg-gray-950/50 py-24">
          <div className="container mx-auto px-4">
            <div className="grid gap-8 md:grid-cols-3">
              <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
                <Globe className="mb-4 h-8 w-8 text-cyan-400" />
                <h3 className="mb-2 text-lg font-semibold">Multi-Provider</h3>
                <p className="text-sm text-gray-400">
                  OpenAI, Anthropic, Google, Mistral, Groq, Ollama, and more.
                  Use any model you want.
                </p>
              </div>
              <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
                <Shield className="mb-4 h-8 w-8 text-indigo-400" />
                <h3 className="mb-2 text-lg font-semibold">Secure</h3>
                <p className="text-sm text-gray-400">
                  Your API keys are encrypted with AES-256-GCM.
                  OAuth with Google, GitHub, and magic email.
                </p>
              </div>
              <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
                <Terminal className="mb-4 h-8 w-8 text-green-400" />
                <h3 className="mb-2 text-lg font-semibold">CLI + Web</h3>
                <p className="text-sm text-gray-400">
                  Use in your terminal with React Ink or in the browser
                  with Monaco Editor and xterm.js.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-gray-800 py-6">
        <div className="container mx-auto px-4 text-center text-sm text-gray-500">
          &copy; 2026 NexCode. Open source under MIT License.
        </div>
      </footer>
    </div>
  );
}
