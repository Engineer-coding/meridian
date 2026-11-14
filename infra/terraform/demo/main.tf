# Demo sunucusu (ADR-0009): tek düğümlü k3s; açılıp kapanır. Uygulama sırları buradan geçmez.
data "hcloud_primary_ip" "demo" {
  name = var.ip_name
}

resource "hcloud_ssh_key" "operator" {
  name       = "meridian-demo"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "hcloud_firewall" "demo" {
  name = "meridian-demo"

  rule {
    description = "HTTP (Let's Encrypt ve HTTPS yönlendirmesi)"
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  rule {
    description = "HTTPS"
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  rule {
    description = "SSH, yalnızca kurulumu yapan"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = [var.operator_cidr]
  }

  rule {
    description = "Kubernetes API, yalnızca kurulumu yapan"
    direction   = "in"
    protocol    = "tcp"
    port        = "6443"
    source_ips  = [var.operator_cidr]
  }
}

resource "hcloud_server" "demo" {
  name         = "meridian-demo"
  server_type  = var.server_type
  image        = "ubuntu-24.04"
  location     = var.location
  ssh_keys     = [hcloud_ssh_key.operator.id]
  firewall_ids = [hcloud_firewall.demo.id]
  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    k3s_version = var.k3s_version
    ip          = data.hcloud_primary_ip.demo.ip_address
  })

  public_net {
    ipv4_enabled = true
    ipv4         = data.hcloud_primary_ip.demo.id
    ipv6_enabled = false
  }

  labels = {
    app          = "meridian-demo"
    "expires-at" = tostring(var.expires_at)
  }
}
