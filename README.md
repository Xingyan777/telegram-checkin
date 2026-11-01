# Telegram 多账号自动签到

基于 [Telethon](https://github.com/LonamiWebs/Telethon) 的多账号 Telegram 签到管理器。
支持多账号、多目标、人机验证自动作答、双层关键词防火墙，可在 GitHub Actions 上每日无人值守运行，也可在本地用交互式菜单手动操作。

---

## 特性

| 能力 | 说明 |
|------|------|
| 多账号 | 一个 `.session` 文件即一个账号，数量不限，支持备注名 |
| 多目标 | 每个签到目标可配置独立命令（`/checkin`、`/qd`、`/sign`、`每日签到`…） |
| 按账号分发 | 目标可指定 `sessions` 白名单，只让指定账号发送，避免所有账号都去骚扰同一个机器人 |
| 人机验证 | 自动识别验证题（图片题 / 文字题 / 找不同 / 算术题），交给 AI 判定后点击正确按钮或回复答案 |
| 双层防火墙 | 入站只放行真正的验证题，出站拦截可疑答案，省 AI 额度、防误判 |
| 两阶段执行 | 先批量发送所有签到命令，再统一处理验证回复，比逐个等待快得多 |
| 无人值守 | GitHub Actions 每天定时跑，凭证走 Secrets，仓库里不落地 |
| 本地菜单 | 登录/备注/删除账号、增删改签到目标、手动一键签到、内置定时 worker |

---

## 工作原理

```
auto_run.py
   │
   ├─ restore_sessions_from_env()   SESSION_<账号名> → 本地 .session
   ├─ get_sessions()                扫描 *.session 得到账号列表
   │
   └─ do_checkin()
         │
         for 每个账号:
            │
            ├─ 阶段 1：批量发送
            │     遍历 checkin_targets.json
            │     跳过 sessions 白名单不匹配的目标
            │     逐条发送命令，不等待回复
            │
            └─ 阶段 2：统一处理验证
                  handle_verification()
                     │
                     ├─ 入站防火墙 verify_firewall()  不是验证题 → 丢弃
                     ├─ AI 判定 ai_ask_verification()  返回应点按钮序号/答案
                     ├─ 出站防火墙 answer_firewall()   答案可疑 → 丢弃
                     ├─ click_button()                 点击回调按钮
                     └─ 命中成功关键词 → 记为签到成功
```

关键点：

- **验证处理最多 6 轮，每轮间隔 3 秒**，超时后放弃该目标，不影响其他目标。
- **实体解析有兜底**：`get_entity()` 拿不到 `access_hash` 时，回退到 `iter_dialogs()` 扫描对话列表，所以「App 里建过会话但本地没缓存」的目标也能发出去。
- **Telethon 版本锁定 `1.44.0`**：不锁版本时 Actions 可能装到其他版本，`getattr(button, 'data')` 取不到回调数据，导致验证分支误判。

---

## 目录结构

```
telegram-checkin/
├── tg_menu.py                 主程序（菜单 + 签到 + 验证 + 防火墙）
├── auto_run.py                GitHub Actions 入口（无交互，直接跑签到）
├── accounts_config.json       账号配置：备注名、手机号
├── checkin_targets.json       签到目标：uid + 命令 + 可选账号白名单
├── .github/workflows/
│   └── checkin.yml            每日定时工作流
├── test_firewall.py           防火墙规则自测
├── FIREWALL.md                防火墙设计说明
├── QUICK_START.md             快速部署
├── github_actions_guide.md    Actions 详细教程
├── deploy_guide.md            VPS / systemd / Docker 部署
└── FREE_ALTERNATIVES.md       各种免费方案对比
```

`.gitignore` 已排除 `*.session`、`string_sessions.txt`、`.env`，凭证不会进仓库。

---

## 快速开始（GitHub Actions，推荐）

### 1. 准备本地账号

```bash
pip install telethon==1.44.0
python tg_menu.py
```

选 `2. 登录新账号`，输入 session 名（英文数字）、备注、手机号、验证码，需要两步验证时再输密码。登录成功后目录下会出现 `<名字>.session`。

### 2. 导出 StringSession 字符串

GitHub Actions 没有你的本地 session 文件，需要把登录态转成字符串存进 Secrets。新建一个临时脚本运行：

```python
# export_session.py —— 用完即删，别提交
import asyncio, os
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ['TG_API_ID'])
API_HASH = os.environ['TG_API_HASH']
NAME = '四惠东'   # 你的 session 名

async def main():
    client = TelegramClient(NAME, API_ID, API_HASH)
    await client.connect()
    print(StringSession.save(client.session))
    await client.disconnect()

asyncio.run(main())
```

输出的那一长串就是该账号的 StringSession。

### 3. 配置仓库 Secrets

仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`：

| Secret 名 | 值 |
|-----------|-----|
| `TG_API_ID` | 从 [my.telegram.org](https://my.telegram.org) 获取的 api_id |
| `TG_API_HASH` | 同上，api_hash |
| `AI_API_KEY` | 验证题 AI 判定用的 API Key |
| `SESSION_四惠东` | 上面导出的 StringSession（账号名要和本地一致） |
| `SESSION_新星焉` | 同上 |

> 账号名用中文没问题，`SESSION_` 后面的部分会被当成 session 文件名还原。

### 4. 上传代码

```bash
git add -A
git commit -m "init"
git push
```

`.session` 文件不会被提交（已被 `.gitignore` 排除），这是预期行为。

### 5. 启用工作流

仓库 → `Actions` → 选中 `Telegram Auto Checkin` → `Enable workflow` → `Run workflow` 手动跑一次验证。

默认 cron 是 `0 1 * * *`（UTC 1 点 = 北京时间 9 点）。GitHub 的定时任务有排队延迟，实际启动时间可能晚 10 分钟到 1 小时不等。

---

## 本地使用

```bash
export TG_API_ID=1234567
export TG_API_HASH=abcdef0123456789abcdef0123456789
export AI_API_KEY=sk-xxxx
python tg_menu.py
```

主菜单：

```
1. 查看账号列表        列出所有 .session 及其备注
2. 登录新账号          手机号 + 验证码登录，自动存备注
3. 修改账号备注        只改显示名，不动 session
4. 删除账号            三重确认，会删掉登录凭证
5. 签到管理            目标增删改查 + 一键签到
6. 执行一键签到        立即跑一次全部账号
7. 自动签到管理        内置定时 worker，可设间隔
0. 退出
```

签到管理子菜单：

```
1. 查看签到目标列表
2. 添加签到目标        输入 uid 或 @username + 命令
3. 编辑签到目标
4. 删除签到目标
5. 执行一键签到
0. 返回
```

---

## 配置文件

### accounts_config.json

```json
{
  "四惠东": { "remark": "四惠东", "phone": "+8613800000000" },
  "新星焉": { "remark": "新星焉" }
}
```

键名必须与 `.session` 文件名（去后缀）一致，否则备注丢失。

### checkin_targets.json

```json
[
  { "uid": "7622987039", "cmd": "/checkin" },
  { "uid": "8286060286", "cmd": "/qd", "sessions": ["四惠东"] },
  { "uid": "9131741740", "cmd": "/checkin", "sessions": ["新星焉"] }
]
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `uid` | 是 | 数字 ID 或 `@username` |
| `cmd` | 是 | 发送的内容，可以是命令也可以是一段文字 |
| `sessions` | 否 | 账号白名单。省略 = 所有账号都发；给了 = 只有列出的账号发 |

> **重命名 session 文件时**，必须同步改 `accounts_config.json` 的键名和 `checkin_targets.json` 里的 `sessions` 白名单，否则备注丢失、白名单匹配失败导致跳过签到。

---

## 人机验证与防火墙

签到机器人常见的验证形态：图片选序号、点唯一不同的按钮、算术题、滑动验证。程序把消息和图片一起交给 AI，AI 返回应点击的按钮序号或回复内容。

为了不把每条无关消息都丢给 AI（烧额度 + 误判），加了两道关键词防火墙：

```
机器人回复
    │
    ▼
入站防火墙 verify_firewall()
    反向关键词命中  → 拦截（宣传文案里带"验证"二字的情况）
    正向关键词未命中 → 拦截
    两者都过        → 放行给 AI
    │
    ▼
AI 判定
    │
    ▼
出站防火墙 answer_firewall()
    过长 / 含换行 / 含链接 / 含反向词 → 拦截
    其余                              → 允许发送
```

关键词表可用环境变量覆盖（逗号或换行分隔）：

```bash
export FIREWALL_VERIFY_KEYWORDS="验证,请选择,请点击,找不同,序号"
export FIREWALL_DENY_KEYWORDS="严格验证,无需验证,今日已领取"
```

详见 [FIREWALL.md](FIREWALL.md)，规则自测：`python test_firewall.py`。

---

## 常见问题

**Q：Actions 里报「未发现任何账号」**
`SESSION_<账号名>` 没配，或配了但值为空。注意账号名要和本地 `.session` 文件名完全一致。

**Q：验证按钮点了报 `message ID is invalid`**
消息已过期或被机器人删除。程序会重发签到命令再试，通常能补上；如果反复出现，说明该机器人的验证时效很短。

**Q：某个目标一直签到失败**
先用 `python tg_menu.py` 本地跑一次看日志。常见原因：session 失效需要重新登录、目标拉黑了该账号、命令改了（`/qd` 变成 `/sign` 之类）。

**Q：定时任务没按点跑**
GitHub 的 `schedule` 在高负载时会延迟，最长可能一小时。要求准点的话用 VPS + systemd，见 [deploy_guide.md](deploy_guide.md)。

**Q：会不会用完 Actions 免费额度**
公共仓库免费无限；私有仓库每月 2000 分钟，一次签到约 4 分钟，一个月 120 分钟左右。

**Q：能加多少个账号**
理论上不限，但所有账号串行执行，每多一个账号多几秒到几十秒。目前 2 个账号单次约 4 分钟。

---

## 安全须知

1. **`.session` 文件等于账号登录态**，泄露即等于账号被盗。永远不要提交，不要发群里，不要放公开网盘。
2. **优先用私有仓库**。仓库为 Public 时 `checkin_targets.json` 里的机器人 ID 是公开可见的（虽然不含凭证）。
3. **凭证只放 Secrets**，不要写进代码、不要 `echo` 到日志。
4. **PAT 用最小权限**。只需要 `repo` 就能读写代码和 Secrets；要手动触发 Actions 或改 workflow 文件才需要额外的 `workflow`。
5. **定期轮换**。session 和 API Key 换掉旧的就失效，出过事的立刻重登。

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [QUICK_START.md](QUICK_START.md) | 最短路径部署 GitHub Actions |
| [github_actions_guide.md](github_actions_guide.md) | Actions 配置细节与排错 |
| [deploy_guide.md](deploy_guide.md) | VPS / systemd / Docker 部署 |
| [FREE_ALTERNATIVES.md](FREE_ALTERNATIVES.md) | 六种免费或低成本方案对比 |
| [FIREWALL.md](FIREWALL.md) | 关键词防火墙设计 |

---

## 更新日志

### v1.2
- 📝 README 重写：补齐工作原理、StringSession 导出流程、配置字段说明、安全须知
- 🔒 文档明确凭证边界与最小权限建议

### v1.1
- 🔄 session 改名适配：`星焉.session` → `四惠东.session`
- ✅ `accounts_config.json` 键名与 `checkin_targets.json` 白名单同步
- ✅ 支持向 Telegram 个人频道发送消息（实体经 `iter_dialogs` 解析）

### v1.0
- ✅ 命令行菜单界面
- ✅ 多账号管理
- ✅ 批量签到
- ✅ 人机验证 AI 判定
- ✅ 关键词防火墙
- ✅ GitHub Actions 无人值守
