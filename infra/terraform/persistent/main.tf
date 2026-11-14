# Kalıcı IPv4 (ADR-0009): demo sunucusu silinip yeniden açıldığında link (meridian.<ip>.sslip.io) aynı kalır.
# Bu state demo'dan ayrıdır; make demo-down buna dokunmaz.
resource "hcloud_primary_ip" "demo" {
  name        = var.name
  type        = "ipv4"
  auto_delete = false
  location    = var.location
  labels = {
    app = "meridian-demo-ip"
  }

  lifecycle {
    prevent_destroy = true
  }
}
