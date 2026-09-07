const internalApiUrl = process.env.INTERNAL_API_URL || 'http://api:8000';

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${internalApiUrl}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
