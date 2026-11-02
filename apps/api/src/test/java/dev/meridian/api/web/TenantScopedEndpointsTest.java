package dev.meridian.api.web;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;
import java.util.stream.Stream;

import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;
import org.springframework.beans.factory.annotation.AnnotatedBeanDefinition;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.ClassPathScanningCandidateComponentProvider;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.RequestMapping;

import dev.meridian.api.PostgresIntegrationTest;
import dev.meridian.api.tenancy.Tenant;
import dev.meridian.api.tenancy.TenantContext;
import dev.meridian.api.tenancy.TenantContext.Identity;
import dev.meridian.api.tenancy.TenantRepository;

/**
 * Kiracı sızıntı paketi: OpenAPI sözleşmesinden üretilen arayüzlerdeki, adresinde
 * {@code {tenantId}} geçen HER işlem için "A kiracısının kullanıcısı B kiracısına
 * erişemez" testi üretir. Sözleşmeye yeni bir uç nokta eklendiğinde test kendiliğinden
 * oluşur; kimsenin hatırlaması gerekmez.
 */
@AutoConfigureMockMvc
class TenantScopedEndpointsTest extends PostgresIntegrationTest {

    private static final String GENERATED_API_PACKAGE = "dev.meridian.api.contract.api";

    @Autowired
    MockMvc mvc;

    @Autowired
    TenantRepository tenants;

    record Endpoint(HttpMethod method, String pathTemplate, String operation) {
    }

    @TestFactory
    Stream<DynamicTest> nonMemberCannotReachAnyTenantScopedEndpoint() throws Exception {
        UUID alice = UUID.randomUUID();
        Tenant otherTenant = TenantContext.callAs(new Identity(UUID.randomUUID(), UUID.randomUUID()),
            () -> tenants.createWithOwner("bob@beta.test", "beta-" + UUID.randomUUID().toString().substring(0, 8), "Beta"));

        List<Endpoint> endpoints = tenantScopedEndpoints();
        assertThat(endpoints).as("sözleşmede kiracıya bağlı uç nokta bulunamadı; tarama bozuk olabilir").hasSizeGreaterThanOrEqualTo(5);

        return endpoints.stream().map(endpoint -> DynamicTest.dynamicTest(
            endpoint.method() + " " + endpoint.pathTemplate() + " (" + endpoint.operation() + ")",
            () -> mvc.perform(request(endpoint.method(), concretePath(endpoint.pathTemplate(), otherTenant.id()))
                    .with(jwt().jwt(j -> j.subject(alice.toString()).claim("email", "alice@acme.test")))
                    .header("Idempotency-Key", "key-" + UUID.randomUUID())
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("{}"))
                .andExpect(status().isNotFound())));
    }

    private static List<Endpoint> tenantScopedEndpoints() throws ClassNotFoundException {
        var scanner = new ClassPathScanningCandidateComponentProvider(false) {
            @Override
            protected boolean isCandidateComponent(AnnotatedBeanDefinition definition) {
                return definition.getMetadata().isInterface();
            }
        };
        scanner.addIncludeFilter((reader, factory) -> reader.getClassMetadata().getClassName().endsWith("Api"));

        var endpoints = new ArrayList<Endpoint>();
        for (var definition : scanner.findCandidateComponents(GENERATED_API_PACKAGE)) {
            for (Method method : Class.forName(definition.getBeanClassName()).getMethods()) {
                RequestMapping mapping = method.getAnnotation(RequestMapping.class);
                if (mapping == null) {
                    continue;
                }
                for (String path : mapping.value()) {
                    if (path.contains("{tenantId}")) {
                        Arrays.stream(mapping.method()).forEach(m ->
                            endpoints.add(new Endpoint(HttpMethod.valueOf(m.name()), path, method.getName())));
                    }
                }
            }
        }
        return endpoints;
    }

    /** {tenantId} yerine hedef kiracıyı, diğer değişkenlerin yerine rastgele UUID koyar. */
    private static String concretePath(String template, UUID tenantId) {
        return template.replace("{tenantId}", tenantId.toString())
            .replaceAll("\\{[^}]+}", UUID.randomUUID().toString());
    }
}
