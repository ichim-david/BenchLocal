import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
	plugins: [react()],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
			"@core": path.resolve(__dirname, "../packages/benchlocal-core/src"),
			"@benchpack-host": path.resolve(
				__dirname,
				"../packages/benchpack-host/src",
			),
		},
	},
	build: {
		outDir: "out/renderer-out",
		emptyOutDir: true,
	},
	server: {
		port: 4300,
		host: "0.0.0.0",
		proxy: {
			"/api": {
				target: "http://localhost:4300",
				changeOrigin: true,
			},
		},
	},
});
