import { OTLPHttpProtoTraceExporter, registerOTel } from "@vercel/otel";

// İzleme (ADR-0017): web sunucusu her istek için span açar ve API'ye giden çağrıya traceparent ekler.
// Yalnızca sunucuda çalışır; tarayıcı paketine girmez. Gönderim OTEL_EXPORT=true iken yapılır.
export function register() {
  const exporting = process.env.OTEL_EXPORT === "true";
  const endpoint = process.env.OTEL_ENDPOINT ?? "http://127.0.0.1:4318";
  const api = process.env.API_URL ?? "http://localhost:8080";
  registerOTel({
    serviceName: "meridian-web",
    attributes: {
      "service.namespace": "meridian",
      "deployment.environment": process.env.DEPLOYMENT_ENVIRONMENT ?? "local",
    },
    // Gönderim yoksa işlemci de yok: span ve iz kimliği yine üretilir, yalnızca bir yere yazılmaz.
    ...(exporting
      ? { traceExporter: new OTLPHttpProtoTraceExporter({ url: `${endpoint}/v1/traces` }) }
      : { spanProcessors: [] }),
    // Bağlam yalnızca çekirdek API'ye taşınır; Keycloak gibi dış adreslere iz kimliği gitmez.
    instrumentationConfig: { fetch: { propagateContextUrls: [api] } },
  });
}
