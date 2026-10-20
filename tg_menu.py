from telethon import TelegramClient, events
from telethon.tl.types import PeerUser
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
import asyncio
import json
import os
from datetime import datetime
import threading
import time
import re
import urllib.request
import urllib.error
import base64
from telethon.tl import functions

# ==================== 配置 ====================
# 敏感信息一律从环境变量读取（本地可写入 .env 或直接 export，切勿提交到仓库）
def _env_int(name, default=0):
    try:
        return int(os.environ.get(name, '') or default)
    except (TypeError, ValueError):
        return default


API_ID = _env_int('TG_API_ID', 0)
API_HASH = os.environ.get('TG_API_HASH', '')
CONFIG_FILE = 'accounts_config.json'
CHECKIN_FILE = 'checkin_targets.json'

# ==================== AI 人机验证配置 ====================
# 当签到机器人返回无法直接解析的验证（如"找不同"）时，调用 AI 判断要点哪个按钮
AI_VERIFY_ENABLED = True
AI_VERIFY_URL = os.environ.get('AI_VERIFY_URL', 'https://freeshare.cc.cd/v1/chat/completions')
AI_VERIFY_KEY = os.environ.get('AI_API_KEY', '')
AI_VERIFY_MODEL = os.environ.get('AI_VERIFY_MODEL', 'agnes-3.0-flash')
AI_VERIFY_TIMEOUT = 60  # 秒（图片型验证需要更长时间）
# ======================================================

# 自动签到状态
auto_checkin_running = False
auto_checkin_thread = None

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'保存配置失败: {e}')

def load_checkin_targets():
    if os.path.exists(CHECKIN_FILE):
        try:
            with open(CHECKIN_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_checkin_targets(targets):
    try:
        with open(CHECKIN_FILE, 'w', encoding='utf-8') as f:
            json.dump(targets, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'保存签到目标失败: {e}')

def restore_sessions_from_env():
    """从环境变量还原本地 .session 文件（用于 GitHub Actions 等无本地凭证的环境）。

    约定环境变量名：SESSION_<账号名>，值为 StringSession 字符串。
    例如 SESSION_四惠东 / SESSION_新星焉。已存在 .session 文件时不覆盖。
    """
    restored = []
    for key, value in os.environ.items():
        if not key.startswith('SESSION_') or not value.strip():
            continue
        name = key[len('SESSION_'):].strip()
        if not name:
            continue
        path = f'{name}.session'
        if os.path.exists(path):
            continue
        try:
            from telethon.sessions import StringSession, SQLiteSession
            src = StringSession(value.strip())
            dst = SQLiteSession(path)
            dst.set_dc(src.dc_id, src.server_address, src.port)
            dst.auth_key = src.auth_key
            dst.save()
            dst.close()
            restored.append(name)
        except Exception as e:
            print(f'⚠️ 还原账号 {name} 失败: {e}')
    if restored:
        print(f'🔑 已从环境变量还原 {len(restored)} 个账号: {", ".join(restored)}')
    return restored


def get_sessions():
    try:
        return sorted([f[:-8] for f in os.listdir('.') if f.endswith('.session') and os.path.isfile(f)])
    except Exception:
        return []

async def resolve_entity(client, uid):
    """解析签到目标实体，带 iter_dialogs 兜底。

    顺序：
    1. get_entity(数字ID/用户名) —— 依赖本地 session 缓存的 access_hash；
    2. 失败则 iter_dialogs 扫描对话列表（账号与目标建立过会话即可从服务器拉到，
       适用于"App 里建了会话但本地 session 未缓存 access_hash"的目标）。
    返回实体对象或 None。
    """
    try:
        if isinstance(uid, int):
            return await client.get_entity(uid)
        uid_int = int(uid) if str(uid).lstrip('-').isdigit() else uid
        return await client.get_entity(uid_int)
    except Exception:
        pass
    # 兜底：扫描对话列表（最多 1000 个，防止太慢）
    target_id = int(uid) if isinstance(uid, str) and uid.lstrip('-').isdigit() else uid
    username = str(uid).lstrip('@') if isinstance(uid, str) else None
    try:
        async for dlg in client.iter_dialogs(limit=1000):
            ent = dlg.entity
            ent_id = getattr(ent, 'id', None)
            ent_username = getattr(ent, 'username', '') or ''
            if (target_id is not None and ent_id == target_id) or \
               (username and ent_username.lower() == username.lower()):
                print(f"  🔍 [resolve] 对话列表找到实体: type={type(ent).__name__} id={ent_id}")
                return ent
    except Exception as e:
        print(f"  ⚠️ [resolve] 扫描对话列表失败: {e}")
    return None

def show_main_menu():
    """显示主菜单"""
    global auto_checkin_running
    print("\n" + "="*60)
    print("                 Telegram 多账号管理器")
    print("="*60)
    print("  1. 查看账号列表")
    print("  2. 登录新账号")
    print("  3. 修改账号备注")
    print("  4. 删除账号")
    print("  5. 签到管理")
    print("  6. 执行一键签到")
    auto_status = "✅ 运行中" if auto_checkin_running else "⭕ 已停止"
    print(f"  7. 自动签到管理 [{auto_status}]")
    print("  0. 退出程序")
    print("="*60)

def show_checkin_menu():
    """显示签到管理菜单"""
    print("\n" + "="*60)
    print("                    签到管理")
    print("="*60)
    print("  1. 查看签到目标列表")
    print("  2. 添加签到目标")
    print("  3. 编辑签到目标")
    print("  4. 删除签到目标")
    print("  5. 执行一键签到")
    print("  0. 返回主菜单")
    print("="*60)

def view_accounts():
    """查看账号列表"""
    config = load_config()
    sessions = get_sessions()
    
    if not sessions:
        print("\n暂无账号，请先登录新账号")
        return
    
    print("\n" + "="*60)
    print("账号列表:")
    print("-"*60)
    for i, session in enumerate(sessions, 1):
        remark = config.get(session, {}).get('remark', session)
        print(f"  {i}. {remark}")
        print(f"     Session: {session}")
        print("-"*60)

async def login_account():
    """登录新账号"""
    print("\n--- 登录新账号 ---")
    session = input("请输入 session 名称（英文/数字）: ").strip()
    if not session:
        print("❌ Session 名称不能为空")
        return
    
    if os.path.exists(f"{session}.session"):
        print("❌ 该 session 已存在")
        return
    
    remark = input("请输入备注名称（可选，直接回车跳过）: ").strip()
    phone = input("请输入手机号（带国家代码，如 +8613800000000）: ").strip()
    
    if not phone:
        print("❌ 手机号不能为空")
        return
    
    try:
        client = TelegramClient(session, API_ID, API_HASH)
        await client.connect()
        
        print("📤 正在发送验证码...")
        await client.send_code_request(phone)
        
        code = input("请输入收到的验证码: ").strip()
        
        try:
            await client.sign_in(phone, code)
            print("✅ 登录成功！")
            
            # 保存备注
            config = load_config()
            if session not in config:
                config[session] = {}
            config[session]['remark'] = remark or session
            config[session]['phone'] = phone
            save_config(config)
            
        except SessionPasswordNeededError:
            password = input("此账号开启了两步验证，请输入密码: ").strip()
            await client.sign_in(password=password)
            print("✅ 登录成功！")
            
            # 保存备注
            config = load_config()
            if session not in config:
                config[session] = {}
            config[session]['remark'] = remark or session
            config[session]['phone'] = phone
            save_config(config)
        
        await client.disconnect()
        
    except PhoneCodeInvalidError:
        print("❌ 验证码错误")
    except PhoneCodeExpiredError:
        print("❌ 验证码已过期")
    except Exception as e:
        print(f"❌ 登录失败: {e}")

def edit_remark():
    """修改备注"""
    sessions = get_sessions()
    if not sessions:
        print("\n❌ 暂无可用账号")
        return
    
    config = load_config()
    print("\n可用账号:")
    for i, session in enumerate(sessions, 1):
        remark = config.get(session, {}).get('remark', session)
        print(f"  {i}. {remark} ({session})")
    
    choice = input("\n请输入要修改备注的账号编号（直接回车取消）: ").strip()
    if not choice:
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(sessions):
            session = sessions[idx]
            new_remark = input("请输入新的备注名称: ").strip()
            if new_remark:
                if session not in config:
                    config[session] = {}
                config[session]['remark'] = new_remark
                save_config(config)
                print(f"✅ 备注已更新为: {new_remark}")
            else:
                print("❌ 备注不能为空")
        else:
            print("❌ 无效的编号")
    except ValueError:
        print("❌ 请输入有效的数字")

def delete_account():
    """删除账号"""
    sessions = get_sessions()
    if not sessions:
        print("\n❌ 暂无可用账号")
        return
    
    config = load_config()
    print("\n可用账号:")
    for i, session in enumerate(sessions, 1):
        remark = config.get(session, {}).get('remark', session)
        print(f"  {i}. {remark} ({session})")
    
    choice = input("\n请输入要删除的账号编号（直接回车取消）: ").strip()
    if not choice:
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(sessions):
            session = sessions[idx]
            remark = config.get(session, {}).get('remark', session)
            
            # 三次确认
            confirm1 = input(f"\n⚠️  确定要删除账号 '{remark}' 吗？(yes/no): ").strip().lower()
            if confirm1 != 'yes':
                print("已取消")
                return
            
            confirm2 = input(f"⚠️  此操作将永久删除该账号的登录凭证！确认继续？(yes/no): ").strip().lower()
            if confirm2 != 'yes':
                print("已取消")
                return
            
            confirm3 = input(f"⚠️  最后确认：真的要删除吗？删除后无法恢复！(yes/no): ").strip().lower()
            if confirm3 != 'yes':
                print("已取消")
                return
            
            # 执行删除
            try:
                session_file = f"{session}.session"
                journal_file = f"{session}.session-journal"
                
                if os.path.exists(session_file):
                    os.remove(session_file)
                if os.path.exists(journal_file):
                    os.remove(journal_file)
                
                if session in config:
                    del config[session]
                    save_config(config)
                
                print(f"✅ 账号 '{remark}' 已删除")
            except Exception as e:
                print(f"❌ 删除失败: {e}")
        else:
            print("❌ 无效的编号")
    except ValueError:
        print("❌ 请输入有效的数字")

def view_checkin_targets():
    """查看签到目标"""
    targets = load_checkin_targets()
    if not targets:
        print("\n暂无签到目标")
        return
    
    print("\n" + "="*60)
    print("签到目标列表:")
    print("-"*60)
    for i, target in enumerate(targets, 1):
        print(f"  {i}. 命令: {target['cmd']}")
        print(f"     ID: {target['uid']}")
        print("-"*60)

def add_checkin_target():
    """添加签到目标"""
    print("\n--- 添加签到目标 ---")
    uid = input("请输入目标 ID 或用户名（数字ID 或 @username）: ").strip()
    if not uid:
        print("❌ 目标不能为空")
        return
    
    # 移除开头的@符号（如果有）
    if uid.startswith('@'):
        uid = uid[1:]
    
    cmd = input("请输入发送内容（如 /checkin 或 /qd）: ").strip()
    if not cmd:
        print("❌ 发送内容不能为空")
        return
    
    targets = load_checkin_targets()
    targets.append({'uid': uid, 'cmd': cmd})
    save_checkin_targets(targets)
    print(f"✅ 已添加签到目标: {cmd} → {uid}")

def edit_checkin_target():
    """编辑签到目标"""
    targets = load_checkin_targets()
    if not targets:
        print("\n❌ 暂无签到目标")
        return
    
    print("\n签到目标:")
    for i, target in enumerate(targets, 1):
        print(f"  {i}. {target['cmd']} → {target['uid']}")
    
    choice = input("\n请输入要编辑的目标编号（直接回车取消）: ").strip()
    if not choice:
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(targets):
            uid = input("请输入新的 ID 或用户名（直接回车保持不变）: ").strip()
            cmd = input("请输入新的命令（直接回车保持不变）: ").strip()
            
            if uid:
                # 移除开头的@符号（如果有）
                if uid.startswith('@'):
                    uid = uid[1:]
                targets[idx]['uid'] = uid
            
            if cmd:
                targets[idx]['cmd'] = cmd
            
            save_checkin_targets(targets)
            print("✅ 已更新")
        else:
            print("❌ 无效的编号")
    except ValueError:
        print("❌ 请输入有效的数字")

def delete_checkin_target():
    """删除签到目标"""
    targets = load_checkin_targets()
    if not targets:
        print("\n❌ 暂无签到目标")
        return
    
    print("\n签到目标:")
    for i, target in enumerate(targets, 1):
        print(f"  {i}. {target['cmd']} → {target['uid']}")
    
    choice = input("\n请输入要删除的目标编号（直接回车取消）: ").strip()
    if not choice:
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(targets):
            target = targets[idx]
            confirm = input(f"确定删除 '{target['cmd']}' → {target['uid']}？(yes/no): ").strip().lower()
            if confirm == 'yes':
                targets.pop(idx)
                save_checkin_targets(targets)
                print("✅ 已删除")
            else:
                print("已取消")
        else:
            print("❌ 无效的编号")
    except ValueError:
        print("❌ 请输入有效的数字")

def ai_ask_verification(msg, image_b64=None):
    """把验证消息的完整 JSON 发给 AI，让 AI 返回验证方法。
    返回结构：{"action": "click", "text": "<按钮文字>"} 或 {"action": "reply", "text": "<回答文本>"}
    解析失败或 AI 不可用时返回 None

    参数 image_b64: 若验证消息含图片，传入图片的 base64 编码字符串，
    将以多模态方式请求 AI（text+image_url），使 AI 能"看图答题"。
    """
    if not AI_VERIFY_ENABLED:
        return None
    prompt = (
        '你是 Telegram 签到机器人的人机验证助手。下面是一条机器人发来的人机验证消息的 JSON，'
        '包含文本内容、按钮列表（每个按钮有 text、data_b64、type、callback 字段）。\n'
        '请分析这是一道什么类型的验证题，并给出正确的通过方法：\n'
        '【核心规则】\n'
        '1. 只要按钮的 callback 为 true（内联回调按钮 KeyboardButtonCallback，type 以 Callback 结尾'
        ' 或 data_b64 不为 null），你必须使用 action="click"，text 填正确按钮的原文文字。'
        '即使是算术题（如"40+14=?"按钮为69/74/54/38），也要 click 正确的选项按钮，'
        '绝对不要用 reply 发送数字文本——机器人不认打字，只认按钮点击。\n'
        '2. 只有当所有按钮的 callback 都为 false（纯键盘按钮 KeyboardButton，无回调能力）时，'
        '才可以用 action="reply" 直接发送答案文本。\n'
        '3. 找不同/指定水果类：click 正确按钮文字。\n'
        '4. 频道加入类（"请先加入频道...点我检测"）：click 检测按钮文字。\n'
        '5. 图片选择类（"哪个序号代表XX？"）：看图片找出正确答案，click 对应序号按钮文字。\n'
        '要求：只输出一个合法的 JSON 对象 {"action":"click或reply","text":"..."}，不要任何解释。\n'
        f'验证消息 JSON：\n{msg}\n'
        '你的回答（仅 JSON）：'
    )
    try:
        if image_b64:
            # 多模态请求：文本 + 图片
            content = [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{image_b64}'}}
            ]
            payload = {
                'model': AI_VERIFY_MODEL,
                'messages': [{'role': 'user', 'content': content}],
                'temperature': 0,
                'max_tokens': 80,
            }
        else:
            payload = {
                'model': AI_VERIFY_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0,
                'max_tokens': 80,
            }
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            AI_VERIFY_URL, data=body,
            headers={'Content-Type': 'application/json',
                     'Authorization': 'Bearer ' + AI_VERIFY_KEY})
        with urllib.request.urlopen(req, timeout=AI_VERIFY_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        answer = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        print(f"  🤖 AI 原始返回: {answer!r}")
        # 提取 JSON 片段
        m = re.search(r'\{.*\}', answer, re.S)
        if not m:
            return None
        obj = json.loads(m.group(0))
        action = str(obj.get('action', '')).strip().lower()
        text = str(obj.get('text', '')).strip()
        if action in ('click', 'reply') and text:
            return {'action': action, 'text': text}
        return None
    except Exception as e:
        print(f"  ⚠️ AI 调用失败: {e}")
        return None

async def click_button(client, peer, msg, btn, remark=''):
    """点击验证按钮，返回是否成功。

    判定规则（关键）：
    - 内联回调按钮 KeyboardButtonCallback（无论 data 是否读得到）：
      一律用 GetBotCallbackAnswerRequest 触发回调——这是机器人唯一认的"点击"方式。
      注意：Actions 环境可能因 Telethon 版本差异导致 getattr(b,'data') 拿不到，
      但只要按钮类型是 KeyboardButtonCallback，就按回调点击（data 为空时传 None 即可）。
    - 其他类型按钮（KeyboardButton/KeyboardButtonUrl/KeyboardButtonSwitchInline 等）：
      不属于验证回调，不应点击；仅当它是普通键盘按钮且需要发送文字时由调用方处理。
    """
    try:
        btn_text = getattr(btn, 'text', '')
        btype = type(btn).__name__
        data = getattr(btn, 'data', None)
        # 兼容不同 Telethon 版本的回调按钮命名变体（KeyboardButtonCallback / KeyboardInlineButton）
        is_callback = ('Callback' in btype or 'Inline' in btype) or (data is not None)

        if is_callback:
            print(f"  🕹️ [{remark}] 点击内联回调按钮({btype}): {btn_text}")
            result = await client(functions.messages.GetBotCallbackAnswerRequest(
                peer=peer,
                msg_id=msg.id,
                data=data,
            ))
            if result:
                hint = getattr(result, 'message', None)
                print(f"  ✅ [{remark}] 回调已触发: {hint or ''}")
            return True
        # 非回调按钮：仅支持普通键盘按钮（KeyboardButton），发送按钮文字等价点击；
        # URL/switch 等按钮无法点击，直接返回 False
        if btn_text and btype == 'KeyboardButton':
            await client.send_message(peer, btn_text)
            print(f"  🖱️ [{remark}] 点击普通按钮(发送): {btn_text}")
            return True
        print(f"  ⚠️ [{remark}] 按钮类型 {btype} 不支持点击")
        return False
    except Exception as e:
        print(f"  ⚠️ [{remark}] 点击按钮失败: {e}")
        return False

# 检测签到成功的关键词（仅用于"没有验证消息"时判断是否已签到成功）
# 注意：不要包含宽泛英文词（如 success），避免误判跳过验证处理
VERIFY_SUCCESS_KEYWORDS = ('签到成功', '已签到', '打卡成功', '签到完成', '今日签到', '签到记录')

async def handle_verification(client, peer, remark='', resend_cmd=None, max_attempts=6, wait_secs=3, min_msg_id=None):
    """处理人机验证：轮询等待机器人回复验证消息，把验证消息 JSON 交给 AI 判定验证方法并执行。

    关键点：
    - 验证消息检测【优先于】签到成功检测：只要发现验证消息就必须处理，
      绝不能因为历史消息含"签到成功"字样就跳过验证；
    - 以"验证"为关键词，检测到机器人发来含"验证"的消息即视为验证；
    - 把该消息的完整 JSON（文本 + 按钮+data）发给 AI，由 AI 决定验证方法：
      click=点击某个按钮 / reply=直接回复答案文本（如算术题）；
    - 机器人回复验证消息常有数秒延迟，必须轮询等待，不能只等一次就放弃；
    - 执行完成后：若提供 resend_cmd 则重发签到命令（验证通过后需再次触发签到）。
    """
    # 先把 peer 解析成可用的实体，避免 iter_messages 对纯数字 ID 解析失败
    entity = peer
    try:
        if isinstance(peer, str) or isinstance(peer, int):
            ent = await resolve_entity(client, peer)
            if ent is not None:
                entity = ent
    except Exception as e:
        print(f"  ⚠️ [{remark}] 解析签到目标实体失败: {e}，仍尝试直接使用原 ID")
        entity = peer

    acted_any = False   # 是否已执行过点击/回复
    no_verify_rounds = 0
    sent_resend = False
    processed_msg_ids = set()  # 已处理过的验证消息 ID，防止同一道题反复作答

    # 非验证类消息的排除词（宣传文案/成功提示中恰好含"验证"二字的情况）
    VERIFY_FALSE_POSITIVE_KEYWORDS = (
        '严格验证', '今日已配给', '今日已领取', '一键分享',
        '独家算法', '远超同行', '邀请好友',
    )

    def is_real_verify_text(text):
        """判断是否为真正的人机验证消息，排除宣传/成功文案"""
        if '验证' not in text:
            return False
        if '无需验证' in text or '不需要验证' in text:
            return False
        # 命中多条非验证类关键词 → 大概率是宣传文案误触发
        hit_count = sum(1 for kw in VERIFY_FALSE_POSITIVE_KEYWORDS if kw in text)
        if hit_count >= 2:
            return False
        # "严格验证"单独出现且无"人机"字样 → 宣传语
        if '严格验证' in text and '人机' not in text:
            return False
        return True

    # 序列化一条消息为传给 AI 的 JSON（含文本、按钮文字、按钮 data 的 base64 与类型名）
    def serialize_msg(msg):
        info = {'text': msg.text or ''}
        # 检测消息是否含图片（photo 属性）
        photo = getattr(msg, 'photo', None)
        info['has_photo'] = photo is not None
        markup = getattr(msg, 'reply_markup', None)
        btns = []
        if markup:
            for row in markup.rows:
                for b in row.buttons:
                    bd = getattr(b, 'data', None)
                    btype = type(b).__name__
                    # 内联回调按钮（KeyboardButtonCallback / KeyboardInlineButton 等命名变体）
                    # 即使 data 暂时读不到也必须标记为回调，避免 AI 误判为普通按钮而走 reply
                    # 发送文字（机器人不认文字，只认回调点击）
                    is_callback = ('Callback' in btype or 'Inline' in btype) or (bd is not None)
                    btns.append({
                        'text': getattr(b, 'text', ''),
                        'data_b64': base64.b64encode(bd).decode() if bd else None,
                        'type': btype,
                        'callback': is_callback,
                    })
        info['buttons'] = btns
        return json.dumps(info, ensure_ascii=False), btns, photo is not None

    for attempt in range(1, max_attempts + 1):
        if attempt == 1:
            # 首次给机器人回复留时间
            await asyncio.sleep(2)
        else:
            await asyncio.sleep(wait_secs)

        # 扫描最近 10 条消息：优先找含"验证"关键词的【未处理过】的消息
        verify_msg = None
        verify_json = None
        verify_btns = []
        verify_has_photo = False
        latest_text = ''
        async for msg in client.iter_messages(entity, limit=10):
            # 加限制：只处理"发送签到命令之后新出现"的验证消息，
            # 跳过历史旧验证消息（防止 bot 超时后把旧题反复翻出来点击刷屏）
            if min_msg_id is not None and msg.id <= min_msg_id:
                continue
            text = msg.text or ''
            if not text:
                continue
            if not latest_text:
                latest_text = text  # 最新一条有文本的消息（用于成功检测）

            if not is_real_verify_text(text):
                continue
            # 已处理过这条消息 → 跳过，找下一条
            if msg.id in processed_msg_ids:
                continue
            verify_msg = msg
            verify_json, verify_btns, verify_has_photo = serialize_msg(msg)
            break

        # 有验证消息：必须处理（成功检测绝不能覆盖验证处理）
        if verify_msg is not None:
            no_verify_rounds = 0
            processed_msg_ids.add(verify_msg.id)
            print(f"  🔍 [{remark}] 检测到验证消息(id={verify_msg.id})，交给 AI 判定验证方法...")
            print(f"     消息JSON: {verify_json}")

            # 如果验证消息含图片，先下载图片转 base64
            image_b64 = None
            if verify_has_photo:
                try:
                    print(f"  📸 [{remark}] 验证消息含图片，正在下载...")
                    buf = await client.download_media(verify_msg, file=bytes)
                    if buf:
                        image_b64 = base64.b64encode(buf).decode()
                        print(f"  📸 [{remark}] 图片下载成功，大小={len(buf)} bytes")
                    else:
                        print(f"  ⚠️ [{remark}] 图片下载返回空")
                except Exception as e:
                    print(f"  ⚠️ [{remark}] 下载验证图片失败: {e}")

            act = ai_ask_verification(verify_json, image_b64=image_b64)
            if not act:
                print(f"  ❌ [{remark}] AI 未能判定验证方法，放弃处理")
                break

            action = act['action']
            value = act['text']

            # ---- 安全兜底：AI 返回 reply 但文本恰好匹配某个回调按钮 → 强制 click ----
            if action == 'reply':
                for b in verify_btns:
                    if b.get('text') == value and b.get('callback'):
                        print(f"  ⚠️ [{remark}] AI 返回 reply:{value!r} 但匹配到回调按钮，强制改为 click")
                        action = 'click'
                        break

            success = False
            if action == 'click':
                # 找到对应文字的内联按钮并点击
                hit = None
                markup = getattr(verify_msg, 'reply_markup', None)
                if markup:
                    hit = next(
                        (b for row in markup.rows for b in row.buttons
                         if getattr(b, 'text', '') == value),
                        None)
                if hit is None:
                    print(f"  ⚠️ [{remark}] AI 指定按钮 {value!r} 不在候选按钮中")
                elif await click_button(client, entity, verify_msg, hit, remark):
                    success = True
                else:
                    print(f"  ❌ [{remark}] 点击验证按钮失败")
            elif action == 'reply':
                # 直接发送文本答案（仅用于无 data 的纯键盘按钮场景）
                try:
                    await client.send_message(entity, value)
                    print(f"  💬 [{remark}] 发送验证答案: {value}")
                    success = True
                except Exception as e:
                    print(f"  ⚠️ [{remark}] 发送验证答案失败: {e}")
            else:
                print(f"  ❌ [{remark}] AI 返回未知动作: {action!r}")

            if success:
                acted_any = True
                # 执行成功后：若提供了签到命令且尚未重发，则重发一次
                if resend_cmd and not sent_resend:
                    await asyncio.sleep(1.5)
                    try:
                        await client.send_message(entity, resend_cmd)
                        sent_resend = True
                        print(f"  🔁 [{remark}] 验证通过，重新发送签到命令: {resend_cmd}")
                    except Exception as e:
                        print(f"  ⚠️ [{remark}] 重发签到命令失败: {e}")
                continue  # 处理成功后进入下一轮复查是否通过/新验证
            else:
                # 处理失败：本轮不丢失计数，但避免无限循环
                if attempt >= max_attempts:
                    print(f"  ❌ [{remark}] 验证处理多次失败，放弃")
                continue

        # ---- 无验证消息（或全部已处理过） ----
        no_verify_rounds += 1
        # 仅当最新一条消息明确含签到成功关键词，才判定成功
        if latest_text and any(k in latest_text for k in VERIFY_SUCCESS_KEYWORDS):
            print(f"  ✅ [{remark}] 检测到签到成功消息: {latest_text[:30]}")
            break

        # 已处理过：连续 2 轮无新验证 → 视为完成；未处理过：连续 3 轮无验证 → 视为无需验证
        limit = 2 if acted_any else 3
        if no_verify_rounds >= limit:
            if acted_any:
                print(f"  ✅ [{remark}] 人机验证处理完成")
            else:
                print(f"  ℹ️ [{remark}] 未发现人机验证消息（可能无需验证或已签到成功）")
            break
        print(f"  ⏳ [{remark}] 等待机器人回复验证消息（第 {attempt}/{max_attempts} 轮）...")
    return acted_any

async def do_checkin():
    """执行签到"""
    targets = load_checkin_targets()
    if not targets:
        print("\n❌ 请先添加签到目标")
        return
    
    sessions = get_sessions()
    if not sessions:
        print("\n❌ 暂无可用账号")
        return
    
    config = load_config()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[{current_time}] 开始执行签到...")
    print("="*60)
    
    for session in sessions:
        remark = config.get(session, {}).get('remark', session)
        try:
            client = TelegramClient(session, API_ID, API_HASH)
            await client.connect()
            
            if not await client.is_user_authorized():
                print(f"⚠️  [{remark}] 未授权，跳过")
                await client.disconnect()
                continue
            
            print(f"\n📱 [{remark}] 开始签到...")

            # 阶段1：快速发送所有签到命令（不等待验证回复）
            sent_targets = []  # (uid, cmd, peer)
            for target in targets:
                try:
                    uid_str = target['uid']
                    cmd = target['cmd']

                    # 目标可能限定特定账号（sessions 白名单），不匹配的跳过
                    allowed = target.get('sessions')
                    if allowed and session not in allowed:
                        print(f"  ⏭️ 跳过 {cmd} → {uid_str}（仅限账号 {allowed}）")
                        continue

                    # 尝试多种方式发送消息
                    sent_peer = None
                    base_id = None  # 基线：发送命令前的最大消息 id，只处理之后新出现的验证消息
                    try:
                        # 方式1: 直接使用数字ID
                        if uid_str.lstrip('-').isdigit():
                            uid = int(uid_str)
                            # 记录发送前的基线消息 id（用于加限制：只处理新验证消息）
                            try:
                                last = await client.get_messages(uid, limit=1)
                                if last:
                                    base_id = last[0].id
                            except Exception:
                                pass
                            await client.send_message(uid, cmd)
                            sent_peer = uid
                            print(f"  ✅ 发送成功: {cmd} → ID:{uid} (基线id={base_id})")
                        # 方式2: 使用username
                        else:
                            await client.send_message(uid_str, cmd)
                            sent_peer = uid_str
                            print(f"  ✅ 发送成功: {cmd} → @{uid_str}")
                    except Exception as e1:
                        # 方式3: 尝试获取实体后发送（含 iter_dialogs 扫描兜底）
                        try:
                            entity = await resolve_entity(client, uid_str)
                            if entity is None:
                                raise ValueError(f"无法解析实体: {uid_str}")
                            # 记录发送前的基线消息 id
                            try:
                                last = await client.get_messages(entity, limit=1)
                                if last:
                                    base_id = last[0].id
                            except Exception:
                                pass
                            await client.send_message(entity, cmd)
                            sent_peer = entity
                            print(f"  ✅ 发送成功（方式2）: {cmd} → {uid_str} (基线id={base_id})")
                        except Exception as e2:
                            print(f"  ❌ 发送失败: {cmd} → {uid_str}")
                            print(f"     错误1: {e1}")
                            print(f"     错误2: {e2}")
                            continue

                    if sent_peer is not None:
                        sent_targets.append((uid_str, cmd, sent_peer, base_id))
                    await asyncio.sleep(1.2)  # 发送间隔，避免触发限流
                except Exception as e:
                    print(f"  ❌ 发送异常: {target.get('cmd', 'unknown')} → {target.get('uid', 'unknown')} ({e})")

            # 阶段2：所有命令已发送，逐个处理可能出现的验证
            # 机器人一般需要几秒才回复，此时处理更可能命中验证消息
            for uid_str, cmd, sent_peer, base_id in sent_targets:
                try:
                    # 处理验证；无论验证是否触发成功，处理完都再发一次签到命令，
                    # 确保部分 bot 在验证后需要再次触发才会真正签到
                    # min_msg_id=base_id：只处理发送命令后新出现的验证消息，不翻旧题
                    handled = await handle_verification(client, sent_peer, remark, resend_cmd=None, min_msg_id=base_id)
                    if handled:
                        await asyncio.sleep(1.5)
                        try:
                            await client.send_message(sent_peer, cmd)
                            print(f"  🔁 [{remark}] 验证处理后重发签到命令: {cmd} → {uid_str}")
                        except Exception as e:
                            print(f"  ⚠️ [{remark}] 重发签到命令失败 {uid_str}: {e}")
                            # 可能是实体缓存丢失，尝试用原始 ID 再发一次
                            try:
                                raw_id = int(uid_str) if uid_str.lstrip('-').isdigit() else uid_str
                                await client.send_message(raw_id, cmd)
                                print(f"  🔁 [{remark}] 用原始ID重发成功: {cmd} → {raw_id}")
                            except Exception as e2:
                                print(f"  ⚠️ [{remark}] 原始ID重发也失败: {e2}")
                except Exception as e:
                    print(f"  ⚠️ [{remark}] 处理验证异常 {uid_str}: {e}")
                await asyncio.sleep(1)

            await client.disconnect()
            
        except Exception as e:
            print(f"❌ [{remark}] 签到失败: {e}")
    
    print("\n" + "="*60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 签到执行完毕")

def auto_checkin_worker():
    """自动签到后台线程"""
    global auto_checkin_running
    
    while auto_checkin_running:
        try:
            # 执行签到
            asyncio.run(do_checkin())
            
            # 如果还在运行，等待24小时
            if auto_checkin_running:
                print(f"\n⏰ 下次签到时间: {datetime.fromtimestamp(time.time() + 86400).strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 每隔60秒检查一次是否需要停止
                for _ in range(1440):  # 24小时 = 1440分钟
                    if not auto_checkin_running:
                        break
                    time.sleep(60)
        except Exception as e:
            print(f"\n❌ 自动签到异常: {e}")
            if auto_checkin_running:
                print("⏰ 10分钟后重试...")
                for _ in range(10):
                    if not auto_checkin_running:
                        break
                    time.sleep(60)

def start_auto_checkin():
    """启动自动签到"""
    global auto_checkin_running, auto_checkin_thread
    
    if auto_checkin_running:
        print("\n⚠️  自动签到已在运行中")
        return
    
    targets = load_checkin_targets()
    if not targets:
        print("\n❌ 请先添加签到目标")
        return
    
    sessions = get_sessions()
    if not sessions:
        print("\n❌ 暂无可用账号")
        return
    
    auto_checkin_running = True
    auto_checkin_thread = threading.Thread(target=auto_checkin_worker, daemon=True)
    auto_checkin_thread.start()
    
    print("\n✅ 自动签到已启动")
    print("📅 将每隔24小时自动执行签到")
    print("💡 提示: 程序需要保持运行状态")

def stop_auto_checkin():
    """停止自动签到"""
    global auto_checkin_running
    
    if not auto_checkin_running:
        print("\n⚠️  自动签到未运行")
        return
    
    auto_checkin_running = False
    print("\n✅ 自动签到已停止")

def auto_checkin_menu():
    """自动签到管理菜单"""
    global auto_checkin_running
    
    while True:
        print("\n" + "="*60)
        print("                  自动签到管理")
        print("="*60)
        status = "✅ 运行中" if auto_checkin_running else "⭕ 已停止"
        print(f"  当前状态: {status}")
        print("-"*60)
        print("  1. 启动自动签到（每24小时）")
        print("  2. 停止自动签到")
        print("  3. 立即执行一次签到")
        print("  0. 返回主菜单")
        print("="*60)
        
        choice = input("\n请选择操作: ").strip()
        
        if choice == '1':
            start_auto_checkin()
        elif choice == '2':
            stop_auto_checkin()
        elif choice == '3':
            asyncio.run(do_checkin())
        elif choice == '0':
            break
        else:
            print("❌ 无效的选项")
        
        if choice != '0':
            input("\n按回车继续...")

def checkin_menu():
    """签到管理菜单"""
    while True:
        show_checkin_menu()
        choice = input("\n请选择操作: ").strip()
        
        if choice == '1':
            view_checkin_targets()
        elif choice == '2':
            add_checkin_target()
        elif choice == '3':
            edit_checkin_target()
        elif choice == '4':
            delete_checkin_target()
        elif choice == '5':
            asyncio.run(do_checkin())
        elif choice == '0':
            break
        else:
            print("❌ 无效的选项")
        
        input("\n按回车继续...")

def main():
    """主程序"""
    while True:
        show_main_menu()
        choice = input("\n请选择操作: ").strip()
        
        if choice == '1':
            view_accounts()
        elif choice == '2':
            asyncio.run(login_account())
        elif choice == '3':
            edit_remark()
        elif choice == '4':
            delete_account()
        elif choice == '5':
            checkin_menu()
        elif choice == '6':
            asyncio.run(do_checkin())
        elif choice == '7':
            auto_checkin_menu()
        elif choice == '0':
            # 停止自动签到
            global auto_checkin_running
            if auto_checkin_running:
                print("\n正在停止自动签到...")
                auto_checkin_running = False
                time.sleep(1)
            print("\n👋 再见！")
            break
        else:
            print("❌ 无效的选项，请重新选择")
        
        if choice != '0':
            input("\n按回车继续...")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 程序已退出")
    except Exception as e:
        print(f"\n❌ 程序错误: {e}")
