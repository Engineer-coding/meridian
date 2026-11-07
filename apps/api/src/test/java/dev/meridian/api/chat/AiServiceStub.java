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
public final class AiServiceStub {

    @FunctionalInterface
    public interface Behavior {
        void respond(HttpExchange exchange) throws Exception;
    }

    public record Call(String token, String body, String upgrade) {
    }

    public final List<Call> calls = new CopyOnWriteArrayList<>();
    private volatile Behavior behavior = exchange -> ndjson(exchange, answer("Cevap [1]."));
    private final HttpServer server;

    public AiServiceStub() {
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
        server.createContext("/internal/v1/agent/run", exchange -> {
            calls.add(new Call(exchange.getRequestHeaders().getFirst("X-Internal-Token"),
                new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8),
                exchange.getRequestHeaders().getFirst("Upgrade")));
            try {
                behavior.respond(exchange);
            } catch (Exception e) {
                // Kasıtlı kesintiler dahil.
            } finally {
                exchange.close();
            }
        });
        server.createContext("/internal/v1/search", exchange -> {
            calls.add(new Call(exchange.getRequestHeaders().getFirst("X-Internal-Token"),
                new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8),
                exchange.getRequestHeaders().getFirst("Upgrade")));
            byte[] body = ("{\"hits\":[{\"documentPath\":\"a.md\",\"title\":\"A\",\"url\":null,\"section\":\"S\","
                + "\"content\":\"metin\",\"score\":0.9}]}").getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
    }

    public String url() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    public void behave(Behavior next) {
        behavior = next;
    }

    public void reset() {
        calls.clear();
        behavior = exchange -> ndjson(exchange, answer("Cevap [1]."));
    }

    public static String sources() {
        return """
            {"event":"sources","data":{"sources":[{"number":1,"documentPath":"kvkk/6698.md","title":"KVKK","url":null,\
            "section":"KVKK > Madde 13","content":"En geç otuz gün içinde sonuçlandırır."}]}}""";
    }

    public static String token(String text) {
        return "{\"event\":\"token\",\"data\":{\"text\":\"" + text + "\"}}";
    }

    public static String done(String answer, boolean abstained, boolean degraded) {
        return "{\"event\":\"done\",\"data\":{\"answer\":\"" + answer + "\",\"cited\":[1],\"invalidCitations\":[],"
            + "\"abstained\":" + abstained + ",\"degraded\":" + degraded + ",\"evidence\":\"otuz gün\","
            + "\"evidenceSource\":1,\"model\":\"ollama/test\"}}";
    }

    /** Sağlayıcının gerçek sayaçlarıyla "done". */
    public static String doneWithUsage(String answer, int promptTokens, int completionTokens) {
        return done(answer, false, false).replace("\"answer\":",
            "\"usage\":{\"promptTokens\":" + promptTokens + ",\"completionTokens\":" + completionTokens + "},\"answer\":");
    }

    public static String[] answer(String text) {
        return new String[] {sources(), token(text), done(text, false, false)};
    }

    public static void ndjson(HttpExchange exchange, String... lines) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", "application/x-ndjson");
        exchange.sendResponseHeaders(200, 0);
        try (OutputStream out = exchange.getResponseBody()) {
            for (String line : lines) {
                out.write((line + "\n").getBytes(StandardCharsets.UTF_8));
                out.flush();
            }
        }
    }

    public static String randomKey() {
        return "key-" + UUID.randomUUID();
    }
}
