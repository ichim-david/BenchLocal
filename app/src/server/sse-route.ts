import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import { sseBus } from "./sse-bus";

export function registerSseRoute(server: FastifyInstance) {
	server.get(
		"/api/events/sse",
		{ handlerTimeout: 0 },
		async (req: FastifyRequest, reply: FastifyReply) => {
			reply.header("Content-Type", "text/event-stream");
			reply.header("Cache-Control", "no-cache");
			reply.header("Connection", "keep-alive");
			reply.header("X-Accel-Buffering", "no");
			reply.raw.write(": connected\n\n");

			const channels = [
				"run-event",
				"benchpack-mutation-progress",
				"verifier-progress",
			];

			const unsubscribers = channels.map((ch) =>
				sseBus.on(ch, (data) => {
					reply.raw.write(`event: ${ch}\ndata: ${JSON.stringify(data)}\n\n`);
				}),
			);

			const keepAlive = setInterval(() => {
				reply.raw.write(": heartbeat\n\n");
			}, 15000);

			req.raw.on("close", () => {
				unsubscribers.forEach((u) => u());
				clearInterval(keepAlive);
			});

			return new Promise<never>(() => {});
		},
	);
}
