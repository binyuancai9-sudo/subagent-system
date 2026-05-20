#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
email_monitor_login.py
首次登录辅助脚本 — 使用 headed 模式打开浏览器，手动完成邮箱登录，
登录成功后 session 保存到 profile_dir，后续 email_monitor.py 将复用此登录态。

用法:
    python3 email_monitor_login.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────
# 路径常量
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# 邮箱网址
MAIL_URL = "https://mail.alibaba-inc.com"


def main():
    # 加载 .env
    load_dotenv(BASE_DIR / ".env")
    profile_dir = os.getenv("MAIL_PROFILE_DIR", "~/.email_monitor_profile")
    expanded_dir = os.path.expanduser(profile_dir)

    print("=" * 60)
    print("  阿里邮箱 — 首次登录助手")
    print("=" * 60)
    print()
    print(f"  浏览器 Profile 目录: {expanded_dir}")
    print()
    print("  即将以有头模式（headless=False）启动 Chromium 浏览器，")
    print("  请在浏览器中手动完成邮箱登录。")
    print("  登录成功后，session 将自动保存到 Profile 目录。")
    print("  后续 email_monitor.py 将复用此登录态，无需再次登录。")
    print()
    print("-" * 60)

    pw = sync_playwright().start()

    try:
        # 使用 headed 模式启动 persistent context
        os.makedirs(expanded_dir, exist_ok=True)
        context = pw.chromium.launch_persistent_context(
            user_data_dir=expanded_dir,
            headless=False,  # 有头模式，方便手动操作
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context.set_default_timeout(60_000)

        page = context.new_page()

        # 打开邮箱登录页
        print(f"  正在打开邮箱: {MAIL_URL}")
        page.goto(MAIL_URL, wait_until="domcontentloaded", timeout=60_000)

        # 检查是否已经登录（可能 profile 中已有有效 session）
        current_url = page.url.lower()
        if "login" not in current_url and not page.query_selector('input[type="password"]'):
            print()
            print("  ✅ 检测到已有有效登录态，无需重新登录！")
        else:
            print()
            print("  📋 请在浏览器中完成登录操作...")
            print("  登录完成后，请回到终端按 Enter 键继续。")
            print()

            # 等待用户按 Enter
            input("  >>> 按 Enter 确认登录完成 ... ")

            # 再次检测登录状态
            current_url = page.url.lower()
            if "login" in current_url or page.query_selector('input[type="password"]'):
                print()
                print("  ⚠️  仍然检测到登录页面，登录可能未成功。")
                print("  如需重试，请再次运行此脚本。")
            else:
                print()
                print("  ✅ 登录成功！session 已保存。")

        # 额外等待确保 cookie/localStorage 写入完成
        page.wait_for_timeout(2000)

        # 关闭浏览器，触发 profile 持久化
        context.close()
        print()
        print(f"  Profile 已保存到: {expanded_dir}")
        print("  后续可运行 email_monitor.py 自动读取邮件。")
        print()

    except Exception as e:
        print(f"  ❌ 发生错误: {e}")
        sys.exit(1)
    finally:
        pw.stop()


if __name__ == "__main__":
    main()
