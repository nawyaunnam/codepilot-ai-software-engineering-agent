import type { NextConfig } from 'next';

const config: NextConfig = {
  experimental: {
    // Allow a model response and two sequential test runs (up to 300 seconds each).
    proxyTimeout: 900_000,
    proxyClientMaxBodySize: '55mb',
  },
  async rewrites() {
    const api = process.env.API_URL || 'http://api:8000';
    return [
      { source: '/auth/:path*', destination: `${api}/auth/:path*` },
      { source: '/api/:path*', destination: `${api}/api/:path*` },
    ];
  },
};
export default config;
