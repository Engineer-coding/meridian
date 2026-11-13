#!/usr/bin/env bash
# Yerel kind kümesini ve içindeki her şeyi siler (veriler dahil).
set -euo pipefail
kind delete cluster --name meridian
