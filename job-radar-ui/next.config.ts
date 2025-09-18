import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  env: {
    PUBLIC_READONLY: process.env.PUBLIC_READONLY ?? 'false'
  }
};

export default nextConfig;
