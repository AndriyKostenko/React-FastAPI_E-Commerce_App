/** @type {import('next').NextConfig} */

const isProduction = process.env.NODE_ENV === "production";

// Catalogue images are served from the catalogue bucket's public origin: the
// local S3 server (SeaweedFS, :8333) in development, the CDN in production,
// named by CATALOGUE_IMAGE_HOST (e.g. "images.example.com").
const catalogueImagePatterns = [
	{ protocol: "http", hostname: "127.0.0.1", port: "8333" },
	{ protocol: "http", hostname: "localhost", port: "8333" },
	...(process.env.CATALOGUE_IMAGE_HOST
		? [{ protocol: "https", hostname: process.env.CATALOGUE_IMAGE_HOST }]
		: []),
];

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
		// Next 16 refuses to optimise an image whose host resolves to a
		// private address (an SSRF guard). The local S3 server is one, so the
		// guard is lifted in development only.
		dangerouslyAllowLocalIP: !isProduction,
		remotePatterns: [
			...catalogueImagePatterns,
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
			// CJ's CDN: a CJ image is served from there until it has been
			// copied into the catalogue bucket (or if copying gave up).
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
