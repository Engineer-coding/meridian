/** Kimlik: token'dan kullanıcıyı ve kiracı bağlamını çıkarır, /v1/me. */
@ApplicationModule(displayName = "Kimlik", allowedDependencies = {"tenancy", "contract"})
package dev.meridian.api.identity;

import org.springframework.modulith.ApplicationModule;
