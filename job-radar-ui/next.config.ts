import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  env: {
    PUBLIC_READONLY: process.env.PUBLIC_READONLY ?? 'false',
    ENABLE_EXPERIMENTAL: process.env.ENABLE_EXPERIMENTAL ?? 'false',
    NEXT_PUBLIC_ENABLE_EXPERIMENTAL: process.env.ENABLE_EXPERIMENTAL ?? 'false'
  }
};

export default nextConfig;
