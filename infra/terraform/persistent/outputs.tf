output "ip" {
  value = hcloud_primary_ip.demo.ip_address
}

output "name" {
  value = hcloud_primary_ip.demo.name
}
