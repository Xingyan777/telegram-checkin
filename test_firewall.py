# -*- coding: utf-8 -*-
"""关键词防火墙本地自测。

实现方式：用 AST 从 tg_menu.py 中抽取防火墙相关的定义（关键词表 + 函数），
在隔离命名空间里执行，避免引入 telethon 依赖。这样测的是**真实源码**，不是副本。
"""
import ast
import re
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tg_menu.py')
source = open(SRC, encoding='utf-8').read()
tree = ast.parse(source)

WANT_FUNCS = {'_env_keywords', 'verify_firewall', 'answer_firewall'}
WANT_ASSIGN = {'VERIFY_TRIGGER_KEYWORDS', 'VERIFY_DENY_KEYWORDS'}

pieces = []
found_funcs = set()
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in WANT_FUNCS:
        pieces.append(ast.get_source_segment(source, node))
        found_funcs.add(node.name)
    elif isinstance(node, ast.Assign):
        names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if names & WANT_ASSIGN:
            pieces.append(ast.get_source_segment(source, node))

missing = WANT_FUNCS - found_funcs
if missing:
    print(f'❌ 未能从源码抽取到: {missing}')
    sys.exit(1)

ns = {'os': os, 're': re}
exec('\n\n'.join(pieces), ns)
verify_firewall = ns['verify_firewall']
answer_firewall = ns['answer_firewall']

print(f'✅ 已从 tg_menu.py 抽取 {len(pieces)} 段定义，函数实测开始')

inbound = [
    ("请完成人机验证：点击下方按钮开始", True, "标准人机验证"),
    ("哪个序号代表化妆镜？", True, "图片选择题"),
    ("请找不同：以下哪个图形与其他不同", True, "找不同"),
    ("请回答：40+14=?", True, "算术题"),
    ("请选择正确的答案", True, "选择题"),
    ("今日已签到成功，明天再来", False, "签到成功提示"),
    ("严格验证的独家算法，远超同行", False, "宣传文案"),
    ("无需验证，直接领取奖励", False, "无需验证"),
    ("邀请好友一起赚积分，一键分享", False, "邀请好友"),
    ("今日已领取今日已配给", False, "已领取"),
    ("你好，在吗", False, "无关消息"),
    ("涨价通知：会员价格调整", False, "广告通知"),
]

outbound = [
    ("69", True, "数字答案"),
    ("第三个", True, "序号短语"),
    ("检测", True, "按钮文字"),
    ("https://evil.example.com/steal", False, "含链接"),
    ("第一行\n第二行", False, "含换行"),
    ("今日已签到成功", False, "含反向词"),
    ("啊" * 50, False, "过长"),
    ("", False, "空"),
]

fails = 0
print()
print("=" * 66)
print("入站防火墙（消息 → 是否交给 AI）")
print("=" * 66)
for text, expect, desc in inbound:
    got, reason = verify_firewall(text)
    ok = (got == expect)
    fails += 0 if ok else 1
    print(f"{'✅' if ok else '❌'} [{desc}] {'放行' if got else '拦截'} | {reason} | {text[:26]!r}")

print()
print("=" * 66)
print("出站防火墙（AI 答案 → 是否可发送）")
print("=" * 66)
for text, expect, desc in outbound:
    got, reason = answer_firewall(text)
    ok = (got == expect)
    fails += 0 if ok else 1
    print(f"{'✅' if ok else '❌'} [{desc}] {'放行' if got else '拦截'} | {reason} | {text[:26]!r}")

print()
print("=" * 66)
total = len(inbound) + len(outbound)
if fails == 0:
    print(f"🎉 全部 {total} 个用例通过")
else:
    print(f"⚠️ {fails}/{total} 个用例未通过")
    sys.exit(1)