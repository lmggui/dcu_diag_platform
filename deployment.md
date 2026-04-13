# DCU 诊断平台部署文档

## 1. 准备环境

1. 克隆仓库并进入目录：
   ```bash
   git clone <仓库地址> /opt/dcu_diag_platform
   cd /opt/dcu_diag_platform
   ```
2. 创建虚拟环境并安装依赖：
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install gunicorn
   ```

## 2. Gunicorn 启动方式

当前应用入口为 `app.py`，Flask 对象名为 `app`。

### 测试启动

```bash
cd /opt/dcu_diag_platform
source venv/bin/activate
gunicorn -w 4 -b 127.0.0.1:8000 app:app
```

### 说明
- `-w 4`：4 个 worker，可根据机器 CPU 调整
- `-b 127.0.0.1:8000`：绑定本机 8000 端口
- 先确保本机访问 `http://127.0.0.1:8000` 正常

## 3. systemd 服务配置

创建 `/etc/systemd/system/dcu_diag_platform.service`：

```ini
[Unit]
Description=DCU 诊断平台 Flask 应用
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/dcu_diag_platform
Environment="PATH=/opt/dcu_diag_platform/venv/bin"
ExecStart=/opt/dcu_diag_platform/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 app:app
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

### 启用服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable dcu_diag_platform
sudo systemctl start dcu_diag_platform
sudo systemctl status dcu_diag_platform
```

## 4. Nginx 反向代理配置

创建 `/etc/nginx/sites-available/dcu_diag_platform`：

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    client_max_body_size 0;
    proxy_buffering off;

    access_log /var/log/nginx/dcu_diag_platform.access.log;
    error_log /var/log/nginx/dcu_diag_platform.error.log;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 120s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /static/ {
        alias /opt/dcu_diag_platform/static/;
    }
}
```

### 启用 Nginx 配置

```bash
sudo ln -s /etc/nginx/sites-available/dcu_diag_platform /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 5. 可选：使用 Unix Socket

如果希望使用 Unix socket，与 Nginx 配合配置如下。

### systemd 中启动命令调整为：

```ini
ExecStart=/opt/dcu_diag_platform/venv/bin/gunicorn -w 4 -b unix:/tmp/dcu_diag_platform.sock app:app
```

### Nginx 对应配置：

```nginx
location / {
    proxy_pass http://unix:/tmp/dcu_diag_platform.sock;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_connect_timeout 120s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
}
```

## 6. 大文件上传注意事项

- 代码中已移除 Flask 应用内部的固定 `MAX_CONTENT_LENGTH` 限制
- Nginx 的 `client_max_body_size 0;` 表示不限制上传体积
- 仍需保证部署服务器的内存和磁盘空间足够
- 若仍出现 `413`，请检查上游负载均衡、云网关、或其他反向代理的 body size 限制

## 7. 调试建议

1. 先测试 `gunicorn` 本地是否可访问：`http://127.0.0.1:8000`
2. 再测试 Nginx 反代是否可访问
3. 若出现错误，优先查看：
   - `/var/log/nginx/dcu_diag_platform.error.log`
   - `/var/log/nginx/error.log`
   - `systemctl status dcu_diag_platform`

---

部署完成后，建议将系统启动命令、Nginx 配置与日志路径统一梳理，便于后续运维维护。