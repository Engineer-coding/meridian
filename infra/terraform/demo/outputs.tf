output "ip" {
  value = data.hcloud_primary_ip.demo.ip_address
}

output "host" {
  value = "meridian.${data.hcloud_primary_ip.demo.ip_address}.sslip.io"
}

output "server_id" {
  value = hcloud_server.demo.id
}
