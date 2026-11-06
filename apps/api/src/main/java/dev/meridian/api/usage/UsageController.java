package dev.meridian.api.usage;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.UUID;
import java.util.stream.Collectors;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RestController;

import dev.meridian.api.audit.Policy;
import dev.meridian.api.contract.api.UsageApi;
import dev.meridian.api.contract.model.UsageDay;
import dev.meridian.api.contract.model.UsageSummary;

/** OpenAPI sözleşmesinden üretilen {@link UsageApi} arayüzünü uygular. */
@RestController
class UsageController implements UsageApi {

    private final Policy policy;
    private final UsageMeter meter;
    private final UsageRepository usage;

    UsageController(Policy policy, UsageMeter meter, UsageRepository usage) {
        this.policy = policy;
        this.meter = meter;
        this.usage = usage;
    }

    @Override
    public ResponseEntity<UsageSummary> getUsage(UUID tenantId, Integer days) {
        policy.require("usage.read", Policy.ADMINS);
        int count = days == null ? 30 : days;
        var today = meter.todayStart();
        var since = today.minusDays(count - 1L);

        var byDate = usage.daysSince(since).stream()
            .collect(Collectors.toMap(UsageRepository.Day::date, day -> day));
        var series = new ArrayList<UsageDay>(count);
        for (LocalDate date = since.toLocalDate(); !date.isAfter(today.toLocalDate()); date = date.plusDays(1)) {
            var day = byDate.get(date);
            series.add(new UsageDay(date, day == null ? 0 : day.tokens(), day == null ? 0 : day.answers()));
        }

        String plan = usage.plan();
        var totals = usage.totalsSince(since);
        return ResponseEntity.ok(new UsageSummary(UsageSummary.PlanEnum.fromValue(plan), meter.dailyLimit(plan),
            series.getLast().getTokens(), meter.resetsAt(), totals.estimatedTokens(),
            totals.costUsd().doubleValue(), series));
    }
}
