import path from "node:path";
import { fileURLToPath } from "node:url";
import fastifyStatic from "@fastify/static";
import Fastify from "fastify";
import { registerApiRoutes } from "./api-routes";
import { activeRunManager } from "./run-manager";
import { registerSseRoute } from "./sse-route";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
	const server = Fastify({ logger: { level: "info" } });

	registerApiRoutes(server);
	registerSseRoute(server);

	// Serve the React SPA build output
	const rendererOut = path.join(__dirname, "..", "renderer-out");
	server.register(fastifyStatic, { root: rendererOut, prefix: "/" });

	// SPA fallback
	server.setNotFoundHandler((req, reply) => {
		if (req.url.startsWith("/api/")) {
			return reply.code(404).send({ error: "Not found" });
		}
		return reply.type("text/html").sendFile("index.html");
	});

	const port = Number(process.env.BENCHLOCAL_PORT) || 4300;
	const host = process.env.BENCHLOCAL_HOST || "0.0.0.0";

	await server.listen({ port, host });
	console.log(`BenchLocal running at http://${host}:${port}`);
}

// Graceful shutdown
process.on("SIGINT", async () => {
	console.log("Shutting down...");
	await activeRunManager.shutdown();
	process.exit(0);
});
process.on("SIGTERM", async () => {
	await activeRunManager.shutdown();
	process.exit(0);
});

main();
