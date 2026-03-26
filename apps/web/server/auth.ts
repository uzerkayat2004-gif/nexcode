import NextAuth from 'next-auth';
import Google from 'next-auth/providers/google';
import GitHub from 'next-auth/providers/github';
import Credentials from 'next-auth/providers/credentials';
import type { Provider } from 'next-auth/providers';

const providers: Provider[] = [
  Google({
    clientId: process.env.GOOGLE_CLIENT_ID || '',
    clientSecret: process.env.GOOGLE_CLIENT_SECRET || '',
  }),
  GitHub({
    clientId: process.env.GITHUB_CLIENT_ID || '',
    clientSecret: process.env.GITHUB_CLIENT_SECRET || '',
  }),
  Credentials({
    id: 'email',
    name: 'Email',
    credentials: {
      email: { label: 'Email', type: 'email' },
      code: { label: 'Verification Code', type: 'text' },
    },
    async authorize(credentials) {
      if (!credentials?.email || !credentials?.code) return null;
      
      // TODO: Verify the OTP code against stored verification
      // For now, return a mock user
      return {
        id: '1',
        email: credentials.email as string,
        name: null,
        image: null,
      };
    },
  }),
  Credentials({
    id: 'api-key',
    name: 'API Key',
    credentials: {
      apiKey: { label: 'API Key', type: 'text' },
    },
    async authorize(credentials) {
      if (!credentials?.apiKey) return null;
      
      const apiKey = credentials.apiKey as string;
      if (!apiKey.startsWith('nxc_sk_')) return null;
      
      // TODO: Validate API key against database
      // For now, return a mock user
      return {
        id: '2',
        email: 'apikey@nexcode.app',
        name: 'API Key User',
        image: null,
      };
    },
  }),
];

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers,
  pages: {
    signIn: '/auth/login',
  },
  session: {
    strategy: 'jwt',
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      if (token && session.user) {
        session.user.id = token.id as string;
      }
      return session;
    },
  },
});

export const providerMap = providers
  .filter((p) => p.type === 'oauth' || p.type === 'email')
  .map((p) => ({
    id: p.id,
    name: p.name,
  }));
