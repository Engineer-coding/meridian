terraform {
  required_version = ">= 1.17.1"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "= 1.70.2"
    }
  }
}

# Token HCLOUD_TOKEN ortam değişkeninden okunur; state'e ya da koda girmez.
provider "hcloud" {}
