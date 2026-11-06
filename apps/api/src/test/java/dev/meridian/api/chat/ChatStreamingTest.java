package dev.meridian.api.chat;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import com.jayway.jsonpath.JsonPath;

import dev.meridian.api.PostgresIntegrationTest;

/**
 * Gerçek sunucu ve gerçek soket: cevabın biriktirilmeden aktığını kanıtlar. Sahte AI servisi ilk
 * token'dan sonra bekler; istemci o token'ı cevap bitmeden okuyabiliyorsa akış gerçektir.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ChatStreamingTest extends PostgresIntegrationTest {

    static final AiServiceStub AI = new AiServiceStub();

    @DynamicPropertySource
    static void ai(DynamicPropertyRegistry registry) {
        registry.add("meridian.ai.url", AI::url);
    }

    @LocalServerPort
    int port;

    @MockitoBean
    JwtDecoder jwtDecoder;

    final HttpClient http = HttpClient.newHttpClient();

    @Test
    void tokensReachTheClientBeforeTheAnswerIsFinished() throws Exception {
        UUID user = UUID.randomUUID();
        when(jwtDecoder.decode(anyString())).thenReturn(Jwt.withTokenValue("t").header("alg", "none")
            .subject(user.toString()).claim("email", user + "@acme.test")
            .issuedAt(Instant.now()).expiresAt(Instant.now().plusSeconds(60)).build());
        String tenant = JsonPath.read(post("/v1/tenants",
            "{\"name\":\"Acme\",\"slug\":\"acme-" + UUID.randomUUID().toString().substring(0, 8) + "\"}"), "$.id");
        String conversation = JsonPath.read(post("/v1/tenants/" + tenant + "/conversations", "{}"), "$.id");

        var clientSawToken = new CountDownLatch(1);
        var sawTokenBeforeEnd = new AtomicBoolean();
        AI.behave(exchange -> {
            exchange.sendResponseHeaders(200, 0);
            try (var out = exchange.getResponseBody()) {
                out.write((AiServiceStub.sources() + "\n" + AiServiceStub.token("İlk ") + "\n").getBytes(StandardCharsets.UTF_8));
                out.flush();
                // Doğrulama burada değil testin kendi thread'inde: buradaki hata teste yansımaz.
                sawTokenBeforeEnd.set(clientSawToken.await(10, TimeUnit.SECONDS));
                out.write((AiServiceStub.done("İlk parça", false, false) + "\n").getBytes(StandardCharsets.UTF_8));
            }
        });

        var request = request("/v1/tenants/" + tenant + "/conversations/" + conversation + "/messages", "{\"content\":\"soru\"}");
        HttpResponse<InputStream> response = http.send(request, HttpResponse.BodyHandlers.ofInputStream());
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.headers().firstValue("Content-Type").orElseThrow()).startsWith("text/event-stream");

        try (var lines = new BufferedReader(new InputStreamReader(response.body(), StandardCharsets.UTF_8))) {
            String line;
            boolean finished = false;
            while ((line = lines.readLine()) != null) {
                if (line.equals("event: token")) {
                    // AI servisi burada bekliyor: bu satırı okuyabilmek, cevabın biriktirilmediğinin kanıtı.
                    clientSawToken.countDown();
                }
                finished |= line.equals("event: done");
            }
            assertThat(finished).isTrue();
        }
        assertThat(sawTokenBeforeEnd).as("token, cevap bitmeden istemciye ulaşmalı").isTrue();
    }

    private String post(String path, String body) throws Exception {
        var response = http.send(request(path, body), HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode()).as(response.body()).isEqualTo(201);
        return response.body();
    }

    private HttpRequest request(String path, String body) {
        return HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
            .header("Authorization", "Bearer t")
            .header("Content-Type", "application/json")
            .header("Idempotency-Key", AiServiceStub.randomKey())
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();
    }
}
