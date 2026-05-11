/** @type {import('next').NextConfig} */

const nextConfig = {
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
		],
	},
};

module.exports = nextConfig;
