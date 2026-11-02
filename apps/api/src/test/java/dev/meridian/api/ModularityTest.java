package dev.meridian.api;

import org.junit.jupiter.api.Test;
import org.springframework.modulith.core.ApplicationModules;

/**
 * Modül sınırları (ADR-0001): her modül yalnızca package-info.java'da izin verilen modüllere
 * ve onların üst paketlerindeki tiplere bağımlı olabilir; döngüsel bağımlılık yasaktır.
 */
class ModularityTest {

    @Test
    void modulesRespectTheirDeclaredBoundaries() {
        ApplicationModules.of(ApiApplication.class).verify();
    }
}
