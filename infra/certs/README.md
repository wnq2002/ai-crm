# TLS 证书目录

Nginx 从本目录挂载证书（`compose.yaml` 中以 `./infra/certs:/etc/nginx/certs:ro` 挂载）。

## 证书文件（Nginx 配置 `infra/nginx/app.conf` 引用）

| 文件 | 用途 |
|---|---|
| `fullchain.pem` | 完整证书链（服务器证书 + 中间证书） |
| `privkey.pem` | 私钥（权限 600） |

## 本地开发 / 冒烟测试

```bash
./infra/certs/generate-selfsigned.sh   # 生成自签名证书
```

## 生产

使用受信任 CA（如 Let's Encrypt）签发的证书，覆盖上述两个文件名即可。
私钥属于敏感凭据，仅存放于服务器本地，绝不提交到版本库（`*.pem` 已在 `.gitignore` 排除）。
