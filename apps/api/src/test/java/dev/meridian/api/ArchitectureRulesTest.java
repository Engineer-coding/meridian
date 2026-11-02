package dev.meridian.api;

import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAPackage;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.Statement;

import org.junit.jupiter.api.Test;
import org.springframework.web.bind.annotation.RestController;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;

import dev.meridian.api.tenancy.TenantAwareTransactionManager;

/** Modül sınırlarının ötesindeki, bu projeye özgü mimari kurallar. */
class ArchitectureRulesTest {

    private static final JavaClasses PRODUCTION = new ClassFileImporter()
        .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
        .importPackages("dev.meridian.api");

    @Test
    void controllersImplementTheGeneratedContract() {
        classes().that().areAnnotatedWith(RestController.class)
            .should().implement(resideInAPackage("dev.meridian.api.contract.api"))
            .because("API sözleşme-önce geliştirilir: her uç nokta OpenAPI'den üretilen bir arayüzü uygular")
            .check(PRODUCTION);
    }

    @Test
    void onlyTheTransactionManagerTouchesRawJdbcConnections() {
        noClasses().that().doNotBelongToAnyOf(TenantAwareTransactionManager.class)
            .should().dependOnClassesThat().belongToAnyOf(Connection.class, PreparedStatement.class, Statement.class, DriverManager.class)
            .because("ham bağlantıya erişen kod kiracı bağlamını atlayabilir veya set_config ile başka bir kiracıyı taklit edebilir")
            .check(PRODUCTION);
    }

    @Test
    void requestContextIsNeverCarriedInThreadLocals() {
        noClasses().should().dependOnClassesThat().belongToAnyOf(ThreadLocal.class, InheritableThreadLocal.class)
            .because("kimlik bağlamı ScopedValue ile taşınır; ThreadLocal temizlenmezse sonraki isteğe sızar")
            .check(PRODUCTION);
    }
}
