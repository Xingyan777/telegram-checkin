# Telegram自动签到 - 部署方案完整指南

## 📚 文档索引

| 文档 | 说明 | 适合人群 |
|------|------|---------|
| **QUICK_START.md** | GitHub Actions快速开始（推荐） | 所有用户 |
| **github_actions_guide.md** | GitHub Actions详细教程 | 需要详细步骤的用户 |
| **FREE_ALTERNATIVES.md** | 所有免费方案对比 | 想了解多种选择的用户 |
| **deploy_guide.md** | 服务器部署指南（需SSH） | 有VPS的用户 |

---

## 🎯 快速决策

### 我没有信用卡 ➜ 用 GitHub Actions
- ✅ 完全免费
- ✅ 无需服务器
- ✅ 自动化运行
- 📖 查看：`QUICK_START.md`

### 我有云服务器 ➜ 用 systemd 服务
- ✅ 稳定可靠
- ✅ 完全掌控
- ✅ 无时间限制
- 📖 查看：`deploy_guide.md`

### 我有树莓派/NAS ➜ 本地部署
- ✅ 低功耗
- ✅ 长期运行
- ✅ 一次投资
- 📖 查看：`FREE_ALTERNATIVES.md` → 方案四

### 我想简单点 ➜ 本地电脑运行
- ✅ 最简单
- ❌ 需要24小时开机
- 📖 查看：`FREE_ALTERNATIVES.md` → 方案三

---

## 📦 所需文件清单

### 核心文件（必需）
```
✅ tg_menu.py           - 主程序
✅ accounts_config.json  - 账号配置
✅ checkin_targets.json  - 签到目标
✅ *.session            - 账号session文件
```

### GitHub Actions专用（推荐方案）
```
✅ auto_run.py                      - 自动运行入口
✅ .github/workflows/checkin.yml    - 工作流配置
```

### 服务器部署专用
```
📄 tg-checkin.service   - systemd服务配置
```

---

## 🚀 三分钟快速开始（GitHub Actions）

### 步骤1：注册GitHub
访问 https://github.com 注册账号（免费）

### 步骤2：创建仓库
1. 点击 `+` → `New repository`
2. 名称：`telegram-checkin`
3. 勾选 `Private`（私有）
4. 点击创建

### 步骤3：上传文件
拖拽上传以下文件到仓库：
- `tg_menu.py`
- `auto_run.py`
- `accounts_config.json`
- `checkin_targets.json`
- 所有 `.session` 文件

### 步骤4：创建工作流
1. 点击 `Add file` → `Create new file`
2. 文件名：`.github/workflows/checkin.yml`
3. 复制粘贴这段代码：

```yaml
name: Telegram Auto Checkin
on:
  schedule:
    - cron: '0 1 * * *'  # 每天北京时间9点
  workflow_dispatch:
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

### 步骤5：启用并测试
1. 进入 `Actions` 标签
2. 点击 `Enable workflow`
3. 点击 `Run workflow` 测试

**✅ 完成！** 现在每天会自动签到。

---

## 🔧 常见问题

### Q1: GitHub Actions什么时候运行？
**A:** 默认每天北京时间9点。可以修改 `cron` 表达式改变时间。

### Q2: 如何修改签到时间？
**A:** 编辑 `.github/workflows/checkin.yml`，修改这一行：
```yaml
- cron: '0 1 * * *'  # UTC 1点 = 北京时间 9点
```

常用时间：
- 北京时间 6点：`'0 22 * * *'`
- 北京时间 12点：`'0 4 * * *'`
- 北京时间 18点：`'0 10 * * *'`
- 北京时间 22点：`'0 14 * * *'`

### Q3: 会不会用完免费额度？
**A:** 不会。GitHub免费提供每月2000分钟，每天运行一次只需5分钟，一个月才150分钟。

### Q4: Session文件安全吗？
**A:** 只要仓库设置为Private（私有），就是安全的。不要设置为Public（公开）。

### Q5: 可以签到多个账号吗？
**A:** 可以。只要把所有账号的session文件都上传到仓库。

### Q5.5: 重命名 session 文件后需要注意什么？
**A:** 程序通过 `.session` 文件名（去掉后缀）识别账号，所以：
1. 如果重命名了 session 文件（如 `星焉.session` → `四惠东.session`），必须同步修改 `accounts_config.json` 里的键名和 `checkin_targets.json` 里对应目标的 `sessions` 白名单，否则账号备注会丢失、白名单匹配会失效（签到被跳过）。
2. 本地已登录的 session 若被 Git 改动挡住，先处理本地未提交的 session 变更，避免覆盖登录态。

### Q6: 如果签到失败怎么办？
**A:** 进入 Actions 查看日志，会显示具体错误信息。

### Q7: 如何停止自动签到？
**A:** 在 Actions 页面，点击工作流的 `...` → `Disable workflow`

### Q8: 我有VPS但没有信用卡，能用吗？
**A:** 可以。查看 `deploy_guide.md` 使用systemd方案。

### Q9: 国内服务器能用吗？
**A:** 可以，但需要配置代理才能访问Telegram。详见 `FREE_ALTERNATIVES.md`。

### Q10: 手机能当服务器吗？
**A:** 可以。使用Termux在Android手机上运行。详见 `FREE_ALTERNATIVES.md` 方案六。

---

## 💡 方案对比速查表

| 特性 | GitHub Actions | VPS服务器 | 树莓派 | 本地电脑 |
|------|---------------|----------|--------|---------|
| **费用** | 免费 | $5/月起 | 200元一次性 | 免费 |
| **需要信用卡** | ❌ | ✅ | ❌ | ❌ |
| **难度** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ |
| **稳定性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **维护成本** | 无 | 低 | 低 | 无 |
| **功耗** | 0 | 5-10W | 5-10W | 100-300W |
| **推荐度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## 📖 详细文档说明

### QUICK_START.md
**快速开始指南 - GitHub Actions部署**
- 三步完成部署
- 适合新手
- 有完整的步骤截图说明
- 5分钟即可完成

### github_actions_guide.md
**GitHub Actions详细教程**
- 完整的配置说明
- 高级功能配置
- 故障排查指南
- 适合想深入了解的用户

### FREE_ALTERNATIVES.md
**免费方案完整对比**
- 6种免费/低成本方案
- 详细的优劣对比
- 适合各种场景的用户
- 包含Termux、树莓派等方案

### deploy_guide.md
**服务器部署指南**
- systemd服务配置
- screen/tmux方案
- Docker容器化部署
- 适合有VPS的用户

---

## 🎓 推荐学习路径

### 新手用户
1. 先看 `QUICK_START.md` 了解基本流程
2. 按照步骤部署 GitHub Actions
3. 遇到问题查看 `github_actions_guide.md` 的故障排查

### 进阶用户
1. 先看 `FREE_ALTERNATIVES.md` 对比各种方案
2. 选择适合自己的方案
3. 查看对应的详细文档

### 专业用户
1. 直接看 `deploy_guide.md`
2. 使用 systemd 或 Docker 方案
3. 自定义配置和监控

---

## 🔐 安全建议

1. **务必使用私有仓库**
   - Session文件包含账号凭证
   - 泄露会导致账号被盗

2. **定期更新依赖**
   ```bash
   pip install --upgrade telethon
   ```

3. **备份重要文件**
   - Session文件
   - 配置文件
   - 签到目标

4. **使用GitHub Secrets**
   - 不要在代码中硬编码API密钥
   - 使用环境变量存储敏感信息

5. **监控运行日志**
   - 定期查看Actions日志
   - 及时发现异常

---

## 📞 获取帮助

### 查看日志
- GitHub Actions: 进入 Actions → 点击运行记录
- 服务器: `sudo journalctl -u tg-checkin -f`

### 常见错误
1. **导入失败**: 检查文件是否都已上传
2. **签到失败**: 检查session文件是否有效
3. **工作流不运行**: 检查是否启用了Actions

### 联系支持
- 查看项目文档
- 提交GitHub Issue
- 查看社区讨论

---

## 📝 更新日志

### v1.1
- 🔄 账号 session 改名适配：`星焉.session` → `四惠东.session`
- ✅ `accounts_config.json` 账号键、`checkin_targets.json` 白名单同步为 `四惠东`
- ✅ 支持向 Telegram 个人频道（Channel）发送消息（实体需通过 `iter_dialogs` 解析）

### v1.0
- ✅ 命令行菜单界面
- ✅ 多账号管理
- ✅ 签到目标管理
- ✅ 24小时自动签到
- ✅ GitHub Actions支持
- ✅ 服务器部署支持

---

## 🎉 总结

**对于大多数用户，我们强烈推荐使用 GitHub Actions 方案：**

- ✅ 完全免费
- ✅ 无需信用卡
- ✅ 无需服务器
- ✅ 自动化运行
- ✅ 稳定可靠
- ✅ 易于维护

**立即开始：** 查看 `QUICK_START.md`

**祝你使用愉快！🎊**
