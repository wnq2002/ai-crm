#!/usr/bin/env sh
# 生成自签名证书，仅用于本地开发 / 冒烟测试。
# 生产环境必须替换为受信任 CA（如 Let's Encrypt）签发的证书，
# 文件名保持 fullchain.pem + privkey.pem，放在本目录（infra/certs/）。
set -e
cd "$(dirname "$0")"

openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout privkey.pem \
  -out fullchain.pem \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 privkey.pem
echo "已生成自签名证书：infra/certs/fullchain.pem + privkey.pem（仅用于开发/冒烟）"
