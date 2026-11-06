package dev.meridian.api.apikeys;

import java.util.Collection;
import java.util.regex.Pattern;

/**
 * Hangi kapsamın hangi uca izin verdiği. Listede olmayan her uç reddedilir: yeni bir uç, kapsam
 * açıkça tanımlanana kadar anahtarla çağrılamaz. Anahtar yönetimi, kullanım ve denetim kayıtları
 * bu yüzden yalnızca oturumla açılır.
 *
 * @param path adresin {@code /v1/tenants/{id}} sonrası
 */
public final class ApiKeyScopes {

    private static final Pattern SOURCES_READ = Pattern.compile("/(sources(/[^/]+)?|collections)");
    private static final Pattern SOURCES_WRITE = Pattern.compile("/(sources(/[^/]+(/retry)?)?|collections)");
    private static final Pattern CHAT = Pattern.compile("/conversations(/[^/]+/messages)?");

    private ApiKeyScopes() {
    }

    public static boolean allows(Collection<String> scopes, String method, String path) {
        boolean read = "GET".equals(method);
        boolean write = "POST".equals(method) || "DELETE".equals(method);
        return (scopes.contains("sources:read") && read && SOURCES_READ.matcher(path).matches())
            || (scopes.contains("sources:write") && write && SOURCES_WRITE.matcher(path).matches())
            || (scopes.contains("chat") && (read || "POST".equals(method)) && CHAT.matcher(path).matches());
    }
}
