import type { NextConfig } from 'next';
const config: NextConfig = {async rewrites() {return [{source:'/auth/:path*',destination:`${process.env.API_URL || 'http://api:8000'}/auth/:path*`},{source:'/api/:path*',destination:`${process.env.API_URL || 'http://api:8000'}/api/:path*`}];}};
export default config;
