variable "name" {
  description = "Kalıcı IP'nin adı; demo state'i IP'yi bu adla bulur."
  type        = string
  default     = "meridian-demo"
}

variable "location" {
  description = "Hetzner konumu; demo sunucusu aynı konumda açılmalı."
  type        = string
  default     = "hel1"
}
