# GitHub Actions 部署快速开始

> 前提：已在本地用 `python tg_menu.py` 登录过账号，并导出过 StringSession。
> 没做过的话先看 [README.md](README.md) 的「快速开始」第 1、2 步。

## 🚀 四步完成部署（无需服务器，完全免费）

### 第一步：创建 GitHub 仓库

1. 访问 https://github.com 并登录
2. 点击右上角 `+` → `New repository`
3. 填写：
   - Repository name: `telegram-checkin`
   - 可见性：`Private` 或 `Public` 都可以（凭证和目标列表都不进仓库）
4. 点击 `Create repository`

### 第二步：上传代码

```bash
git clone https://github.com/<你的用户名>/telegram-checkin.git
cd telegram-checkin
# 把本地的 tg_menu.py / auto_run.py / accounts_config.json 等拷进来
git add -A && git commit -m "init" && git push
```

也可以网页操作：`Add file` → `Upload files`，拖拽上传：

```
✅ tg_menu.py
✅ auto_run.py
✅ accounts_config.json
✅ .github/workflows/checkin.yml
```

**不要上传**：`*.session`（凭证）、`checkin_targets.json`（目标列表）。
前者会被 `.gitignore` 挡掉，后者同样已被忽略——它的内容要放进 Secret。

### 第三步：配置 Secrets

仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`：

| Secret 名称 | 值 |
| --- | --- |
| `TG_API_ID` | Telegram API ID（在 my.telegram.org 申请） |
| `TG_API_HASH` | Telegram API Hash |
| `AI_API_KEY` | 人机验证所用大模型 API Key |
| `SESSION_1` | 账号 1 的 StringSession |
| `SESSION_2` | 账号 2 的 StringSession |
| `CHECKIN_TARGETS` | 签到目标 JSON 数组，和本地 `checkin_targets.json` 内容一致 |

`CHECKIN_TARGETS` 的值示例：

```json
[
  { "uid": "7622987039", "cmd": "/checkin" },
  { "uid": "8286060286", "cmd": "/qd", "sessions": ["1"] }
]
```

命令行一条搞定：

```bash
gh secret set CHECKIN_TARGETS < checkin_targets.json
```

> `SESSION_1` 会还原成 `1.session`，所以 `accounts_config.json` 的键和目标的
> `sessions` 白名单里都要写 `1` / `2`，不是中文备注名。

### 第四步：启用并测试

1. 点击仓库顶部的 `Actions` 标签
2. 点 `I understand my workflows, go ahead and enable them`
3. 左侧选 `Telegram Auto Checkin` → 右侧 `Run workflow`
4. 等 4-5 分钟，日志里应出现：

```
🔑 已从环境变量还原 2 个账号: 1, 2
🔑 已从环境变量还原 17 个签到目标
👤 待签到账号: 1, 2
   ✅ [四惠东] 检测到签到成功消息
```

---

## ✅ 完成！

现在每天北京时间 9 点自动签到，无需任何操作。

## 📋 常用操作

### 修改签到时间

编辑 `.github/workflows/checkin.yml` 的 `cron`：

```yaml
# 每天早上6点
- cron: '0 22 * * *'
# 每天中午12点
- cron: '0 4 * * *'
# 每天晚上10点
- cron: '0 14 * * *'
```

**时区换算：** 北京时间 = UTC + 8 小时

### 新增/修改签到目标

目标列表在 `CHECKIN_TARGETS` secret 里，**改本地文件不会自动生效**：

```bash
# 改完本地 checkin_targets.json 后
gh secret set CHECKIN_TARGETS < checkin_targets.json
```

或网页：`Settings` → `Secrets` → `CHECKIN_TARGETS` → `Update`。

### 手动触发签到

`Actions` → `Telegram Auto Checkin` → `Run workflow`，或命令行：

```bash
gh workflow run checkin.yml
```

### 查看运行日志

`Actions` → 点运行记录 → 点 `checkin` 展开。

### 停止自动签到

`Actions` → 左侧 `Telegram Auto Checkin` → 右上角 `...` → `Disable workflow`。

---

## ⚠️ 重要提示

1. **仓库可以公开**：凭证在 Secrets 里，`checkin_targets.json` 和 `*.session` 都不进仓库
2. **StringSession 等于账号登录态**，泄露即被盗号，别贴群里
3. **公共仓库 Actions 免费无限**；私有仓库每月 2000 分钟，一次约 4 分钟完全够用
4. **定时任务会延迟**：GitHub 高负载时可能晚 10 分钟到 1 小时
5. **PAT 权限**：只改代码需要 `repo`；要 `gh workflow run` 或改 workflow 文件还需 `workflow`

---

## 🆘 遇到问题？

### 工作流没有运行
- 检查 Actions 是否启用
- 首次创建后手动触发一次
- 检查 cron 表达式格式

### 「未发现任何账号」
- `SESSION_1` / `SESSION_2` 没配，或值为空
- StringSession 过期 → 重新登录导出并更新 secret

### 「请先添加签到目标」
- `CHECKIN_TARGETS` 没配，或不是合法 JSON 数组
- 本地验证：`python -c "import json;json.load(open('checkin_targets.json'))"`

### 签到失败
- 查看 Actions 日志里的错误
- 确认目标 `uid` 和命令正确（`/checkin`、`/qd`、`/sign`…）
- 确认该账号没被机器人拉黑

### 改名 session 后签到被跳过/备注丢失
- 程序按 `.session` 文件名（去后缀）识别账号
- 改名后必须同步三处：`accounts_config.json` 键名、目标的 `sessions` 白名单、
  GitHub 上的 `SESSION_*` secret 名

---

## 📚 更多信息

详细文档见 `github_actions_guide.md`。

---

**祝你使用愉快！🎉**
