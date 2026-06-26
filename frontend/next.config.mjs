/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Type errors must fail the build; linting is handled separately.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
