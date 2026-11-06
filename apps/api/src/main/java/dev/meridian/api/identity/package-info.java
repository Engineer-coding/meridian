/** Kimlik: token ya da API anahtarından kullanıcıyı ve kiracı bağlamını çıkarır, /v1/me. */
@ApplicationModule(displayName = "Kimlik", allowedDependencies = {"tenancy", "apikeys", "contract"})
package dev.meridian.api.identity;

import org.springframework.modulith.ApplicationModule;
