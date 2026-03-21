/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    proxyTimeout: 600000,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
