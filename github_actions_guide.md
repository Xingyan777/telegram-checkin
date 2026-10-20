# GitHub Actions 自动签到部署指南

## 一、准备工作

### 1. 注册GitHub账号
访问 https://github.com 注册免费账号（如已有则跳过）

### 2. 创建私有仓库
1. 点击右上角 `+` → `New repository`
2. 仓库名：`telegram-checkin`
3. 勾选 `Private`（私有仓库，保护隐私）
4. 勾选 `Add a README file`
5. 点击 `Create repository`

## 二、上传程序文件

### 方法一：网页上传（简单）
1. 进入仓库页面
2. 点击 `Add file` → `Upload files`
3. 拖拽上传以下文件：
   - `tg_menu.py`
   - `accounts_config.json`
   - `checkin_targets.json`
   - 所有 `.session` 文件
4. 点击 `Commit changes`

### 方法二：Git命令（高级）
```bash
git clone https://github.com/你的用户名/telegram-checkin.git
cd telegram-checkin
cp /storage/emulated/0/Download/tg_menu.py .
cp /storage/emulated/0/Download/*.json .
cp /storage/emulated/0/Download/*.session .
git add .
git commit -m "Add telegram checkin files"
git push
```

## 三、修改程序以适配GitHub Actions

由于GitHub Actions是非交互式环境，需要修改 `tg_menu.py`：

创建新文件 `auto_run.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime

# 从原程序导入签到函数
import sys
sys.path.insert(0, '.')

async def auto_checkin():
    """自动签到入口"""
    print(f"\n{'='*50}")
    print(f"🤖 GitHub Actions 自动签到")
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")
    
    # 导入原有的签到逻辑
    from tg_menu import do_checkin
    await do_checkin()
    
    print(f"\n{'='*50}")
    print(f"✅ 签到任务执行完毕")
    print(f"{'='*50}\n")

if __name__ == '__main__':
    asyncio.run(auto_checkin())
```

## 四、创建GitHub Actions工作流

在仓库中创建文件：`.github/workflows/checkin.yml`

```yaml
name: Telegram Auto Checkin

on:
  # 定时触发（每天北京时间上午9点）
  schedule:
    - cron: '0 1 * * *'  # UTC时间1点 = 北京时间9点
  
  # 手动触发
  workflow_dispatch:

jobs:
  checkin:
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v3
    
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: 安装依赖
      run: |
        pip install telethon
    
    - name: 执行签到
      run: |
        python auto_run.py
    
    - name: 提交更新（如果有session变化）
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add *.session
        git diff --quiet && git diff --staged --quiet || git commit -m "Update session files"
        git push || echo "No changes to push"
```

## 五、配置定时时间

修改 `cron` 表达式来设置签到时间：

```yaml
# 格式：分 时 日 月 周（UTC时间）
# 北京时间 = UTC时间 + 8小时

# 每天北京时间9点
- cron: '0 1 * * *'

# 每天北京时间0点
- cron: '0 16 * * *'

# 每12小时一次（北京时间0点和12点）
- cron: '0 16,4 * * *'

# 每天北京时间6点、14点、22点
- cron: '0 22,6,14 * * *'
```

## 六、启用工作流

1. 进入仓库的 `Actions` 标签页
2. 如果看到提示，点击 `I understand my workflows, go ahead and enable them`
3. 找到 `Telegram Auto Checkin` 工作流
4. 点击 `Enable workflow`

## 七、测试运行

### 手动触发测试
1. 进入 `Actions` 标签页
2. 点击左侧 `Telegram Auto Checkin`
3. 点击右侧 `Run workflow` → `Run workflow`
4. 等待执行完成（约1-2分钟）
5. 点击运行记录查看日志

### 查看日志
1. 点击任意运行记录
2. 点击 `checkin` 任务
3. 展开 `执行签到` 步骤查看详细日志

## 八、注意事项

### 1. Session文件安全
- 务必使用 **Private（私有）** 仓库
- 不要分享仓库链接
- Session文件包含账号凭证，泄露会导致账号被盗

### 2. 运行时间限制
- 单次最长6小时
- 对于签到任务完全够用（通常1-5分钟完成）

### 3. 免费额度
- 私有仓库：每月2000分钟
- 公共仓库：无限制（但不建议用公共仓库，不安全）
- 每天运行一次，每次5分钟 = 每月150分钟（远低于上限）

### 4. 时区问题
- GitHub Actions使用UTC时间
- 北京时间 = UTC时间 + 8小时
- 北京时间9点 = UTC时间1点 = cron: '0 1 * * *'

### 5. 失败通知
如果希望接收失败通知，可以添加：

```yaml
    - name: 发送失败通知
      if: failure()
      run: |
        echo "签到失败，请检查日志"
        # 可以配置邮件、Telegram通知等
```

## 九、高级配置

### 使用GitHub Secrets保护敏感信息

本项目已把全部凭证改为从环境变量读取，仓库中不含任何密钥。

1. 进入仓库 `Settings` → `Secrets and variables` → `Actions`
2. 点击 `New repository secret`，依次添加：

| Secret 名称 | 说明 |
| --- | --- |
| `TG_API_ID` | Telegram API ID（在 my.telegram.org 申请） |
| `TG_API_HASH` | Telegram API Hash |
| `AI_API_KEY` | 人机验证所用大模型 API Key |
| `SESSION_SIHUIDONG` | 四惠东账号的 StringSession |
| `SESSION_XINXINGYAN` | 新星焉账号的 StringSession |

`tg_menu.py` 中的读取方式：
```python
API_ID = int(os.environ.get('TG_API_ID', '0'))
API_HASH = os.environ.get('TG_API_HASH', '')
AI_VERIFY_KEY = os.environ.get('AI_API_KEY', '')
```

`auto_run.py` 启动时会调用 `restore_sessions_from_env()`，
把 `SESSION_<账号名>` 环境变量还原成同名的本地 `.session` 文件，
再交给签到流程使用。环境变量名里的账号名需与 `accounts_config.json` 的键一致。

对应 `checkin.yml`：
```yaml
    - name: 执行签到
      env:
        TG_API_ID: ${{ secrets.TG_API_ID }}
        TG_API_HASH: ${{ secrets.TG_API_HASH }}
        AI_API_KEY: ${{ secrets.AI_API_KEY }}
        SESSION_四惠东: ${{ secrets.SESSION_SIHUIDONG }}
        SESSION_新星焉: ${{ secrets.SESSION_XINXINGYAN }}
      run: python auto_run.py
```

> 注意：Secrets 名称不能含中文，因此用到的是 `SESSION_SIHUIDONG`，
> 但注入到环境变量时用的是中文键 `SESSION_四惠东`，两者不要混淆。

## 十、故障排查

### 问题1：工作流不运行
- 检查是否启用了Actions
- 检查cron表达式是否正确
- 首次创建需要等待，或手动触发一次

### 问题2：导入模块失败
- 确认 `tg_menu.py` 已上传
- 确认 `auto_run.py` 中的导入路径正确

### 问题3：Session过期
- Session文件有效期通常很长
- 如果过期需要重新登录生成新的session文件
- 将新session文件重新上传到仓库

### 问题4：签到失败
- 查看Actions日志中的错误信息
- 检查网络连接（GitHub服务器在国外，访问Telegram畅通）
- 确认签到目标配置正确

### 问题5：重命名 session 文件后账号备注丢失/签到被跳过
- 程序按 `.session` 文件名（去掉后缀）作为账号标识
- 改名后必须同步：
  - `accounts_config.json` 中的键名（`"星焉"` → `"四惠东"`）
  - `checkin_targets.json` 中对应目标的 `sessions` 白名单（如 `"sessions": ["星焉"]` → `["四惠东"]`）

## 十一、常见问题

**Q: GitHub Actions会不会封号？**
A: 不会，这是正常的自动化用途，符合GitHub使用条款。

**Q: 可以签到多个账号吗？**
A: 可以，只要所有账号的session文件都在仓库中。

**Q: 可以修改签到频率吗？**
A: 可以，修改cron表达式即可，但不建议过于频繁（避免被Telegram限流）。

**Q: 如何停止自动签到？**
A: 进入Actions页面，点击工作流右上角的 `...` → `Disable workflow`

---

## 总结

GitHub Actions是完全免费、无需信用卡的最佳方案：
- ✅ 不需要自己的服务器
- ✅ 不需要信用卡
- ✅ 不需要付费
- ✅ 稳定可靠
- ✅ 自动运行

唯一的学习成本是需要了解基本的Git和GitHub操作，但这些都是程序员的基本技能。
