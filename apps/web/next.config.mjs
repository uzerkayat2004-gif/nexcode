/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['@nexcode/shared', '@nexcode/db', '@nexcode/ui'],
  experimental: {
    serverActions: {
      bodySizeLimit: '2mb',
    },
  },
};

export default nextConfig;
