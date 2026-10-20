# Telegram 自动签到服务器部署指南

## 准备工作

### 1. 服务器要求
- Linux 系统（Ubuntu/Debian/CentOS）
- Python 3.7+
- 稳定的网络连接

### 2. 安装依赖
```bash
# 更新系统
sudo apt update
sudo apt upgrade -y

# 安装 Python 和 pip
sudo apt install python3 python3-pip -y

# 安装 Telethon
pip3 install telethon
```

---

## 方案一：使用 systemd 服务（推荐）

### 1. 上传文件到服务器
```bash
# 在本地执行（从手机传到服务器）
scp /storage/emulated/0/Download/tg_menu.py user@your-server:/home/user/telegram/
scp /storage/emulated/0/Download/accounts_config.json user@your-server:/home/user/telegram/
scp /storage/emulated/0/Download/checkin_targets.json user@your-server:/home/user/telegram/
scp *.session user@your-server:/home/user/telegram/

# 或使用 SFTP 客户端上传
```

### 2. 创建 systemd 服务文件
```bash
# 在服务器上执行
sudo nano /etc/systemd/system/tg-checkin.service
```

复制以下内容：
```ini
[Unit]
Description=Telegram Auto Check-in Service
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/telegram
ExecStart=/usr/bin/python3 /home/your-username/telegram/tg_menu_daemon.py
Restart=always
RestartSec=10
StandardOutput=append:/home/your-username/telegram/logs/output.log
StandardError=append:/home/your-username/telegram/logs/error.log

[Install]
WantedBy=multi-user.target
```

### 3. 创建守护进程脚本
在服务器上创建 `tg_menu_daemon.py`：

```python
#!/usr/bin/env python3
"""
Telegram 自动签到守护进程
适用于服务器后台运行
"""
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入主程序中的函数
from tg_menu import start_auto_checkin, auto_checkin_running, get_sessions, load_checkin_targets
import time
import signal

def signal_handler(signum, frame):
    """处理退出信号"""
    global auto_checkin_running
    print("\n收到退出信号，正在停止...")
    auto_checkin_running = False
    sys.exit(0)

if __name__ == '__main__':
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("="*60)
    print("     Telegram 自动签到守护进程启动")
    print("="*60)
    
    # 检查配置
    sessions = get_sessions()
    targets = load_checkin_targets()
    
    if not sessions:
        print("❌ 错误：未找到账号配置")
        sys.exit(1)
    
    if not targets:
        print("❌ 错误：未找到签到目标")
        sys.exit(1)
    
    print(f"✅ 已加载 {len(sessions)} 个账号")
    print(f"✅ 已加载 {len(targets)} 个签到目标")
    print("-"*60)
    
    # 启动自动签到
    start_auto_checkin()
    
    # 保持运行
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n程序退出")
```

### 4. 创建日志目录
```bash
mkdir -p /home/your-username/telegram/logs
```

### 5. 启动服务
```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start tg-checkin

# 设置开机自启动
sudo systemctl enable tg-checkin

# 查看服务状态
sudo systemctl status tg-checkin

# 查看日志
tail -f /home/your-username/telegram/logs/output.log
```

### 6. 管理命令
```bash
# 停止服务
sudo systemctl stop tg-checkin

# 重启服务
sudo systemctl restart tg-checkin

# 查看日志
journalctl -u tg-checkin -f

# 禁用开机自启
sudo systemctl disable tg-checkin
```

---

## 方案二：使用 screen 或 tmux（简单快速）

### 1. 安装 screen
```bash
sudo apt install screen -y
```

### 2. 创建运行脚本
```bash
nano /home/your-username/telegram/run.sh
```

内容：
```bash
#!/bin/bash
cd /home/your-username/telegram
python3 tg_menu.py
```

赋予执行权限：
```bash
chmod +x /home/your-username/telegram/run.sh
```

### 3. 使用 screen 运行
```bash
# 创建新的 screen 会话
screen -S tg-checkin

# 运行程序
cd /home/your-username/telegram
python3 tg_menu.py
# 在菜单中选择 7 -> 1 启动自动签到

# 按 Ctrl+A 然后按 D 分离会话（程序继续后台运行）

# 重新连接会话
screen -r tg-checkin

# 查看所有会话
screen -ls

# 结束会话（在会话内）
exit
```

---

## 方案三：使用 Docker（高级）

### 1. 创建 Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装依赖
RUN pip install telethon

# 复制文件
COPY tg_menu.py /app/
COPY tg_menu_daemon.py /app/
COPY accounts_config.json /app/
COPY checkin_targets.json /app/
COPY *.session /app/

# 运行
CMD ["python3", "tg_menu_daemon.py"]
```

### 2. 构建并运行
```bash
# 构建镜像
docker build -t tg-checkin .

# 运行容器
docker run -d --name tg-checkin --restart unless-stopped tg-checkin

# 查看日志
docker logs -f tg-checkin

# 停止容器
docker stop tg-checkin

# 启动容器
docker start tg-checkin
```

---

## 监控和维护

### 1. 日志监控
```bash
# 实时查看日志
tail -f /home/your-username/telegram/logs/output.log

# 查看错误日志
tail -f /home/your-username/telegram/logs/error.log
```

### 2. 定时清理日志
添加到 crontab：
```bash
crontab -e

# 每周清理一次日志（保留最近1000行）
0 0 * * 0 tail -n 1000 /home/your-username/telegram/logs/output.log > /tmp/output.log && mv /tmp/output.log /home/your-username/telegram/logs/output.log
```

### 3. 设置告警（可选）
可以使用邮件或 Telegram Bot 发送运行状态通知

---

## 常见问题

### Q1: 如何备份 session 文件？
```bash
# 定期备份
cp *.session /backup/location/
```

### Q2: 程序崩溃怎么办？
systemd 服务会自动重启，日志在 `/home/your-username/telegram/logs/` 中查看

### Q3: 如何更新程序？
```bash
# 停止服务
sudo systemctl stop tg-checkin

# 更新文件
scp new_tg_menu.py user@server:/home/user/telegram/tg_menu.py

# 启动服务
sudo systemctl start tg-checkin
```

### Q4: 如何测试连接？
```bash
# 在服务器上手动运行一次
cd /home/your-username/telegram
python3 tg_menu.py
# 选择 6 执行一次签到测试
```

---

## 安全建议

1. **使用非 root 用户运行**
2. **设置文件权限**：
   ```bash
   chmod 600 *.session
   chmod 600 accounts_config.json
   chmod 600 checkin_targets.json
   ```
3. **定期备份配置文件**
4. **使用防火墙限制访问**
5. **定期更新系统和依赖包**

---

## 推荐配置

- 服务器：1核1G即可
- 流量：每月1-2GB足够
- 系统：Ubuntu 20.04 LTS / 22.04 LTS
- 云服务商：阿里云、腾讯云、AWS、Vultr 等

---

完成部署后，程序将每24小时自动执行签到，无需手动干预！
