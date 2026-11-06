package dev.meridian.api.chat;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.Executors;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

/** AI servisinin iç ucunu taklit eden gerçek bir HTTP sunucusu: akış, hata ve kesinti denenebilir. */
final class AiServiceStub {

    @FunctionalInterface
    interface Behavior {
        void respond(HttpExchange exchange) throws Exception;
    }

    record Call(String token, String body, String upgrade) {
    }

    final List<Call> calls = new CopyOnWriteArrayList<>();
    private volatile Behavior behavior = exchange -> ndjson(exchange, answer("Cevap [1]."));
    private final HttpServer server;

    AiServiceStub() {
        try {
            server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
        server.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
        server.createContext("/internal/v1/answer", exchange -> {
            calls.add(new Call(exchange.getRequestHeaders().getFirst("X-Internal-Token"),
                new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8),
                exchange.getRequestHeaders().getFirst("Upgrade")));
            try {
                behavior.respond(exchange);
            } catch (Exception e) {
                // Kasıtlı kesintiler (bağlantıyı kapatma) dahil.
            } finally {
                exchange.close();
            }
        });
        server.start();
    }

    String url() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    void behave(Behavior next) {
        behavior = next;
    }

    void reset() {
        calls.clear();
        behavior = exchange -> ndjson(exchange, answer("Cevap [1]."));
    }

    static String sources() {
        return """
            {"event":"sources","data":{"sources":[{"number":1,"documentPath":"kvkk/6698.md","title":"KVKK","url":null,\
            "section":"KVKK > Madde 13","content":"En geç otuz gün içinde sonuçlandırır."}]}}""";
    }

    static String token(String text) {
        return "{\"event\":\"token\",\"data\":{\"text\":\"" + text + "\"}}";
    }

    static String done(String answer, boolean abstained, boolean degraded) {
        return "{\"event\":\"done\",\"data\":{\"answer\":\"" + answer + "\",\"cited\":[1],\"invalidCitations\":[],"
            + "\"abstained\":" + abstained + ",\"degraded\":" + degraded + ",\"evidence\":\"otuz gün\","
            + "\"evidenceSource\":1,\"model\":\"ollama/test\"}}";
    }

    /** Sağlayıcının gerçek sayaçlarıyla "done". */
    static String doneWithUsage(String answer, int promptTokens, int completionTokens) {
        return done(answer, false, false).replace("\"answer\":",
            "\"usage\":{\"promptTokens\":" + promptTokens + ",\"completionTokens\":" + completionTokens + "},\"answer\":");
    }

    static String[] answer(String text) {
        return new String[] {sources(), token(text), done(text, false, false)};
    }

    static void ndjson(HttpExchange exchange, String... lines) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", "application/x-ndjson");
        exchange.sendResponseHeaders(200, 0);
        try (OutputStream out = exchange.getResponseBody()) {
            for (String line : lines) {
                out.write((line + "\n").getBytes(StandardCharsets.UTF_8));
                out.flush();
            }
        }
    }

    static String randomKey() {
        return "key-" + UUID.randomUUID();
    }
}
