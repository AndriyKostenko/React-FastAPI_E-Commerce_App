/** @type {import('next').NextConfig} */

const nextConfig = {
	// Pin the workspace root to this directory.  A stray package-lock.json two
	// levels up (~/Documents/Projects) otherwise wins the root inference, and
	// turbopack then resolves packages like @swc/helpers against a tree that has
	// no node_modules -- which poisons .next with unresolvable chunk aliases.
	turbopack: {
		root: __dirname,
	},
	allowedDevOrigins: ["127.0.0.1"],
	images: {
		remotePatterns: [
			{
				protocol: "http",
				hostname: "localhost",
				port: "8000",
			},
			{
				protocol: "http",
				hostname: "127.0.0.1",
				port: "8000",
			},
			{
				protocol: "https",
				hostname: "firebasestorage.googleapis.com",
			},
			{
				protocol: "https",
				hostname: "lh3.googleusercontent.com",
			},
			{
				protocol: "https",
				hostname: "placehold.co",
			},
			{
				protocol: "https",
				hostname: "cf.cjdropshipping.com",
			},
			{
				protocol: "https",
				hostname: "oss-cf.cjdropshipping.com",
			},
		],
	},
};

module.exports = nextConfig;
