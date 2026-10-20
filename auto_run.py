#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 自动签到入口文件
此文件专门用于在GitHub Actions环境中自动执行签到任务
"""

import asyncio
import sys
from datetime import datetime

# 确保能导入同目录下的模块
sys.path.insert(0, '.')

async def auto_checkin():
    """自动签到入口"""
    print(f"\n{'='*60}")
    print(f"🤖 Telegram 自动签到 - GitHub Actions")
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    try:
        # 从主程序导入签到函数
        from tg_menu import do_checkin, restore_sessions_from_env, get_sessions

        # 先从环境变量还原 StringSession 为本地 .session 文件
        restore_sessions_from_env()

        sessions = get_sessions()
        if not sessions:
            print("❌ 未发现任何账号：请确认已配置 SESSION_<账号名> 环境变量")
            sys.exit(1)
        print(f"👤 待签到账号: {', '.join(sessions)}")

        # 执行签到
        await do_checkin()
        
        print(f"\n{'='*60}")
        print(f"✅ 签到任务执行完毕")
        print(f"⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ 签到执行出错: {e}")
        print(f"{'='*60}\n")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(auto_checkin())
