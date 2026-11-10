"""Yük testi penceresinde sunucu tarafı ölçümleri Prometheus'tan okur (ADR-0019).

    python server_metrics.py chat <başlangıç> <bitiş> "<api ai cpu>" "<api ai cpu>" <gecikme> <örnekleme> <havuz>

k6 istemcinin gördüğünü ölçer; ilk token, arama, kuyruk ve bağlantı havuzu yalnızca sunucuda görülür.
"""

import json
import sys
import urllib.parse
import urllib.request

PROMETHEUS = "http://127.0.0.1:19090"
API = 'service_name="meridian-api", uri!~"/actuator.*"'


def query(expr: str, at: int) -> list[dict]:
    url = f"{PROMETHEUS}/api/v1/query?" + urllib.parse.urlencode({"query": expr, "time": at})
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - sabit yerel adres
        return json.load(response)["data"]["result"]


def by_label(rows: list[dict], label: str | None) -> dict[str, float]:
    out = {}
    for row in rows:
        name = row["metric"].get(label, "toplam") if label else "toplam"
        value = float(row["value"][1])
        out[name] = None if value != value else round(value, 4)  # NaN → null
    return out


def main(argv: list[str]) -> None:
    scenario, start, end, cpu_start, cpu_end, delay, sampling, pool, workers, api_pool = argv
    start_s, end_s = int(start), int(end)
    window = f"{end_s - start_s}s"

    def q(expr: str, label: str | None = None) -> dict[str, float]:
        return by_label(query(expr, end_s), label)

    def p95(metric: str, selector: str = "", label: str | None = None) -> dict[str, float]:
        group = f"le, {label}" if label else "le"
        return q(f"histogram_quantile(0.95, sum by ({group}) (increase({metric}_bucket{{{selector}}}[{window}])))", label)

    # cpu.ps1 çıktısı "api_saniye ai_saniye"; fark / duvar saati = ortalama kullanılan çekirdek.
    def cores(index: int) -> float:
        return round((float(cpu_end.split()[index]) - float(cpu_start.split()[index])) / (end_s - start_s), 2)

    report = {
        "scenario": scenario,
        "window_seconds": end_s - start_s,
        "model_delay": delay,
        "trace_sampling": float(sampling),
        "ai_db_pool_size": int(pool),
        "ai_workers": int(workers),
        "api_db_pool_size": int(api_pool),
        "avg_cores": {"api": cores(0), "ai": cores(1)},
        "api_p95_by_uri": p95("http_server_requests_seconds", API, "uri"),
        "api_requests_by_status": q(f"sum by (status) (increase(http_server_requests_seconds_count{{{API}}}[{window}]))", "status"),
        "ai_request_p95_by_path": p95("meridian_ai_request_seconds", "", "path"),
        "ai_http_p95_ms": p95("http_server_duration_milliseconds", 'service_name="meridian-ai"'),
        "retrieval_p95": p95("meridian_retrieval_duration_seconds"),
        "llm_first_token_p95": p95("meridian_llm_first_token_seconds"),
        "llm_duration_p95_by_operation": p95("meridian_llm_duration_seconds", "", "gen_ai_operation_name"),
        "indexing_p95": p95("meridian_indexing_duration_seconds"),
        "answers_by_outcome": q(f"sum by (outcome) (increase(meridian_answers_total[{window}]))", "outcome"),
        "max_queue_depth": q(f'max by (queue) (max_over_time(rabbitmq_detailed_queue_messages{{queue=~"ai.indexing.*"}}[{window}]))', "queue"),
        "hikari_pending_max": q(f"max by (pool) (max_over_time(hikaricp_connections_pending[{window}]))", "pool"),
        "hikari_active_max": q(f"max by (pool) (max_over_time(hikaricp_connections_active[{window}]))", "pool"),
        "jvm_threads_live_max": q(f"max(max_over_time(jvm_threads_live_threads[{window}]))"),
        "alerts_fired": q(f'max by (alertname) (max_over_time(ALERTS{{alertstate="firing"}}[{window}]))', "alertname"),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
