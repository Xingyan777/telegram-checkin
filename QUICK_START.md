# GitHub Actions 部署快速开始

## 🚀 三步完成部署（无需服务器，完全免费）

### 第一步：创建GitHub仓库

1. 访问 https://github.com 并登录（没有账号就注册一个，免费）
2. 点击右上角 `+` → `New repository`
3. 填写：
   - Repository name: `telegram-checkin`
   - ✅ 勾选 `Private`（重要！保护隐私）
   - ✅ 勾选 `Add a README file`
4. 点击 `Create repository`

### 第二步：上传文件

1. 在仓库页面，点击 `Add file` → `Upload files`
2. 拖拽上传以下文件：
   ```
   ✅ tg_menu.py
   ✅ auto_run.py
   ✅ accounts_config.json
   ✅ checkin_targets.json
   ✅ 所有 .session 文件
   ```
3. 点击 `Commit changes`

### 第三步：创建自动化工作流

#### 3.1 创建目录结构
1. 点击 `Add file` → `Create new file`
2. 文件名输入：`.github/workflows/checkin.yml`
   - 注意：输入 `/` 会自动创建文件夹
3. 粘贴以下内容：

```yaml
name: Telegram Auto Checkin

on:
  schedule:
    - cron: '0 1 * * *'  # 每天北京时间9点
  workflow_dispatch:  # 允许手动触发

jobs:
  checkin:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    - run: pip install telethon
    - run: python auto_run.py
    - run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add *.session
        git diff --quiet && git diff --staged --quiet || git commit -m "Update"
        git push || echo "No changes"
```

4. 点击 `Commit changes`

### 第四步：启用并测试

1. 点击仓库顶部的 `Actions` 标签
2. 看到提示点击 `I understand my workflows, go ahead and enable them`
3. 点击左侧 `Telegram Auto Checkin`
4. 点击右侧 `Run workflow` → `Run workflow` 进行测试
5. 等待1-2分钟，查看是否成功

---

## ✅ 完成！

现在每天北京时间9点会自动签到，无需任何操作。

## 📋 常用操作

### 修改签到时间

编辑 `.github/workflows/checkin.yml`，修改 `cron` 表达式：

```yaml
# 每天早上6点
- cron: '0 22 * * *'

# 每天中午12点
- cron: '0 4 * * *'

# 每天晚上10点
- cron: '0 14 * * *'

# 每12小时（0点和12点）
- cron: '0 16,4 * * *'
```

**时区换算：** 北京时间 = UTC时间 + 8小时

### 手动触发签到

1. 进入 `Actions` 标签
2. 点击 `Telegram Auto Checkin`
3. 点击 `Run workflow`

### 查看运行日志

1. 进入 `Actions` 标签
2. 点击任意运行记录
3. 点击 `checkin` 查看详细日志

### 停止自动签到

1. 进入 `Actions` 标签
2. 点击左侧 `Telegram Auto Checkin`
3. 点击右上角 `...` → `Disable workflow`

---

## ⚠️ 重要提示

1. **务必使用私有仓库**，session文件包含账号凭证
2. **不要分享仓库链接**
3. **每月免费额度2000分钟**，每天运行一次完全够用
4. **首次可能需等待几分钟**才能看到工作流

---

## 🆘 遇到问题？

### 工作流没有运行
- 检查是否启用了Actions
- 首次创建后手动触发一次
- 检查cron表达式格式

### 导入失败
- 确认所有文件都已上传
- 确认文件名正确（区分大小写）

### 签到失败
- 查看Actions日志中的错误信息
- 检查session文件是否有效
- 确认签到目标配置正确

### 改名 session 后签到被跳过/备注丢失
- 程序按 `.session` 文件名（去后缀）识别账号
- 改名后必须同步 `accounts_config.json` 的键名，以及 `checkin_targets.json` 中相关目标的 `sessions` 白名单

---

## 📚 更多信息

详细文档请查看：`github_actions_guide.md`

---

**祝你使用愉快！🎉**