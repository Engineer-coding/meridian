variable "ip_name" {
  description = "Kalıcı IP'nin adı (infra/terraform/persistent)."
  type        = string
  default     = "meridian-demo"
}

variable "location" {
  type    = string
  default = "hel1"
}

variable "server_type" {
  description = "CPX32: 4 vCPU, 8 GB. Tam yığın kind'da ~5,2 GiB ölçüldü."
  type        = string
  default     = "cpx32"
}

variable "expires_at" {
  description = "Unix saniye; bu andan sonra zamanlanmış iş sunucuyu siler (infra/demo/reaper.py)."
  type        = number
}

variable "operator_cidr" {
  description = "SSH (22) ve Kubernetes API (6443) yalnızca bu adresten; ör. 203.0.113.7/32."
  type        = string
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "k3s_version" {
  description = "infra/versions.env içindeki K3S_VERSION."
  type        = string
}
