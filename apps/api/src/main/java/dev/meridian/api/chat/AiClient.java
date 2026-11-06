package dev.meridian.api.chat;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.UUID;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.stereotype.Component;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * AI servisinin iç ucunu çağırır ve satır satır gelen olayları iletir. Kiracı, üyeliği doğrulanmış
 * bağlamdan gelir (ADR-0001). İstek bu thread'de bloklanır: sanal thread'de bu ucuzdur ve kiracı
 * bağlamı ({@code ScopedValue}) akış boyunca bağlı kalır.
 */
@Component
@EnableConfigurationProperties(AiClient.AiProperties.class)
class AiClient {

    @ConfigurationProperties("meridian.ai")
    record AiProperties(URI url, String internalToken, Duration answerDeadline) {
    }

    @FunctionalInterface
    interface Listener {
        void onEvent(String event, JsonNode data);
    }

    /** AI servisine ulaşılamadı, isteği reddetti ya da akış yarıda kesildi. */
    static class Unavailable extends Exception {
        Unavailable(String message, Throwable cause) {
            super(message, cause);
        }
    }

    private final AiProperties properties;
    private final JsonMapper json;
    // Varsayılan HTTP/2 yükseltme başlığıyla (h2c) uvicorn isteğin gövdesini okumaz.
    private final HttpClient http = HttpClient.newBuilder()
        .version(HttpClient.Version.HTTP_1_1)
        .connectTimeout(Duration.ofSeconds(5))
        .build();

    AiClient(AiProperties properties, JsonMapper json) {
        this.properties = properties;
        this.json = json;
    }

    void answer(UUID tenantId, String question, List<UUID> collectionIds, Listener listener) throws Unavailable {
        var body = new LinkedHashMap<String, Object>();
        body.put("tenantId", tenantId);
        body.put("question", question);
        if (collectionIds != null && !collectionIds.isEmpty()) {
            body.put("collectionIds", collectionIds);
        }
        var request = HttpRequest.newBuilder(properties.url().resolve("/internal/v1/answer"))
            .header("Content-Type", "application/json")
            .header("X-Internal-Token", properties.internalToken())
            // Yalnızca başlıklara kadar geçerli; ilk satır modelden önce, arama bitince gelir.
            .timeout(Duration.ofSeconds(60))
            .POST(HttpRequest.BodyPublishers.ofString(json.writeValueAsString(body)))
            .build();

        boolean finished = false;
        try {
            HttpResponse<InputStream> response = http.send(request, HttpResponse.BodyHandlers.ofInputStream());
            try (InputStream stream = response.body()) {
                if (response.statusCode() != 200) {
                    throw new IOException("HTTP " + response.statusCode());
                }
                // HttpClient gövde okumaya süre sınırı koymaz; asılı kalan bir akışı bekçi kapatır.
                Thread watchdog = Thread.startVirtualThread(() -> closeAfterDeadline(stream));
                try (var lines = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = lines.readLine()) != null) {
                        JsonNode event = json.readTree(line);
                        String name = event.get("event").asString();
                        finished |= "done".equals(name);
                        listener.onEvent(name, event.get("data"));
                    }
                } finally {
                    watchdog.interrupt();
                }
            }
        } catch (IOException | JacksonException e) {
            throw new Unavailable("AI servisi kullanılamıyor: " + e.getMessage(), e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new Unavailable("AI servisi çağrısı kesildi", e);
        }
        if (!finished) {
            throw new Unavailable("AI servisi akışı bitirmeden kapattı", null);
        }
    }

    private void closeAfterDeadline(InputStream stream) {
        try {
            Thread.sleep(properties.answerDeadline());
            stream.close();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (IOException e) {
            // Zaten kapanıyor; okuyan taraf hatayı görür.
        }
    }
}
