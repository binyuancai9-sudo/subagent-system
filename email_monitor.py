#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
email_monitor.py — 报童（邮件监听 Agent）
使用 Playwright 浏览器自动化方案监控阿里内网邮箱，
搜索包含指定关键词的最新邮件，下载正文图片并汇总输出为 Markdown 文件。

方案背景：阿里内网邮箱 IMAP 仅支持 OAuth2 认证，不支持密码登录，
因此改用 Playwright 打开邮箱网页版读取邮件。

已确认的工作方式：
- 直接通过 URL 搜索（不操作搜索框）
- 搜索结果为三栏布局，点击 article 后右侧显示正文，不离开搜索页
- 使用 force=True 点击 article
"""

import base64
import datetime
import os
import re
import logging
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, BrowserContext, Page

# ─────────────────────────────────────────────
# 路径常量
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
IMAGE_DIR = Path(os.getenv("EMAIL_IMAGE_DIR", str(Path.home() / "邮件下载")))
# 邮件信息日志（追加模式，不按天重建）
EMAIL_LOG_FILE = IMAGE_DIR / "报童_log.txt"
LOGS_DIR = BASE_DIR / "logs"
LOG_FILE = LOGS_DIR / "email_monitor.log"

# 邮箱网址
MAIL_URL = "https://mail.alibaba-inc.com"
# 备用网址
MAIL_URL_FALLBACK = "https://qiye.aliyun.com"

# 通用超时（毫秒）
DEFAULT_TIMEOUT = 15_000


# ─────────────────────────────────────────────
# 日志配置
# ─────────────────────────────────────────────
def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )


def log(message: str):
    logging.info(message)


# ─────────────────────────────────────────────
# HTML → 纯文本（备用工具）
# ─────────────────────────────────────────────
class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self):
        return "".join(self._parts)


def strip_html(html_content: str) -> str:
    """将 HTML 内容剥离标签，返回纯文本。"""
    stripper = _HTMLStripper()
    stripper.feed(html_content)
    return stripper.get_text()


def compress_blank_lines(text: str) -> str:
    """将多余空行压缩为最多 2 个连续空行。"""
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ─────────────────────────────────────────────
# 浏览器上下文管理
# ─────────────────────────────────────────────
def create_context(pw, profile_dir: str) -> BrowserContext:
    """使用 persistent context 启动浏览器，复用登录态。"""
    expanded_dir = os.path.expanduser(profile_dir)
    os.makedirs(expanded_dir, exist_ok=True)
    context = pw.chromium.launch_persistent_context(
        user_data_dir=expanded_dir,
        headless=False,
        # 常用参数，避免部分环境下的兼容问题
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    context.set_default_timeout(DEFAULT_TIMEOUT)
    return context


# ─────────────────────────────────────────────
# 登录检测
# ─────────────────────────────────────────────
def is_login_page(page: Page) -> bool:
    """判断当前页面是否为登录页面。"""
    url = page.url.lower()
    # URL 中包含 login 关键字
    if "login" in url:
        return True
    # 页面中存在登录表单元素（密码输入框）
    try:
        password_input = page.query_selector('input[type="password"]')
        if password_input:
            return True
    except Exception:
        pass
    return False


# ─────────────────────────────────────────────
# 邮件搜索（通过 URL 直接搜索）
# ─────────────────────────────────────────────
def search_emails(page: Page, keyword: str) -> int:
    """
    通过 URL 直接搜索邮件，返回搜索结果数量。
    搜索后页面停留在搜索结果页（三栏布局）。
    """
    log(f"搜索关键词: {keyword}")

    search_url = (
        f"https://mail.alibaba-inc.com/alimail/entries/v5.1/search"
        f"?keyword={quote(keyword)}&usedFilterKeys=keyword"
    )
    page.goto(search_url, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)  # 等待搜索结果加载

    # 尝试从页面文本中解析 "搜索结果 约N"
    count = 0
    try:
        full_text = page.inner_text("body")
        m = re.search(r"搜索结果\s*约\s*(\d+)", full_text)
        if m:
            count = int(m.group(1))
            log(f"搜索结果数量（页面文本解析）: {count}")
    except Exception as e:
        log(f"解析搜索结果数量时出错: {e}")

    # 记录页面 article 总数（含收件箱列表，供调试参考）
    try:
        article_count = page.locator("article").count()
        log(f"页面共有 article 元素数量: {article_count}（含收件箱列表）")
    except Exception:
        pass

    if count == 0:
        log("未找到匹配的搜索结果")
    return count


# ─────────────────────────────────────────────
# 获取搜索结果面板中的 article 列表
# ─────────────────────────────────────────────
def get_search_result_articles(page: Page) -> list:
    """
    从搜索结果页面的"搜索结果"面板中获取 article 列表，
    排除收件箱列表中的 article，返回摘要信息列表。
    每个元素：{ subject, sender, time, snippet, article_index, in_panel }
    """
    emails = []

    # 策略：找到显示"搜索结果 约N"的标题元素，向上找包含 article 的祖先容器
    search_panel = None
    try:
        header_locator = page.get_by_text(re.compile(r"搜索结果\s*约"))
        if header_locator.count() > 0:
            for ancestor_sel in [
                "xpath=ancestor::div[.//article][1]",
                "xpath=ancestor::section[.//article][1]",
                "xpath=ancestor::*[.//article][1]",
            ]:
                try:
                    candidate = header_locator.first.locator(ancestor_sel)
                    if candidate.count() > 0:
                        art_count = candidate.first.locator("article").count()
                        if 0 < art_count <= 20:  # 合理的搜索结果数量
                            search_panel = candidate.first
                            log(f"搜索结果面板通过标题祖先定位，包含 {art_count} 个 article")
                            break
                except Exception:
                    continue
    except Exception as e:
        log(f"定位搜索结果面板失败: {e}")

    # 若面板定位成功，在面板内获取 article；否则取全部 article 的第1个
    if search_panel is not None:
        article_locator = search_panel.locator("article")
        in_panel = True
    else:
        log("未定位到搜索结果面板，取页面全部 article")
        article_locator = page.locator("article")
        in_panel = False

    count = article_locator.count()
    log(f"搜索结果面板内 article 数量: {count}")

    for i in range(count):
        try:
            art = article_locator.nth(i)
            full_text = art.inner_text().strip()
            lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]

            subject = lines[0] if lines else ""
            sender = lines[1] if len(lines) > 1 else "（未知）"
            time_str = lines[-1] if len(lines) > 2 else "（未知）"
            snippet = "\n".join(lines[2:-1]) if len(lines) > 3 else ""

            emails.append({
                "subject": subject,
                "sender": sender,
                "time": time_str,
                "snippet": snippet,
                "article_index": i,
                "in_panel": in_panel,
            })
            log(f"  article[{i}] 主题: {subject[:50]}")
        except Exception as e:
            log(f"解析 article[{i}] 出错: {e}")
            continue

    return emails


# ─────────────────────────────────────────────
# 读取邮件正文（从 iframe 中提取 FBI 邮件内容）
# ─────────────────────────────────────────────
def read_email_body(page: Page, keyword: str = "", mail_index: int = 0) -> dict:
    """
    从邮件详情的 iframe 中提取正文内容。
    FBI 邮件结构：iframe 内含标题 <p>、数据图片 <img>、报表链接 <a>。
    返回 dict: {title, image_path, link, text}
    """
    result = {"title": "", "image_path": "", "link": "", "text": ""}

    try:
        # ── 取第一个 iframe（无 src 属性的可见 iframe）──
        fl = page.frame_locator('iframe').first

        # 1. 提取标题（report-view 中 font-size:18px 的 p 标签）
        try:
            title_loc = fl.locator('.report-view p').first
            title_text = title_loc.inner_text(timeout=5000).strip()
            if title_text:
                result["title"] = title_text
                log(f"  iframe 标题提取成功: {title_text}")
        except Exception as e:
            log(f"  iframe 标题提取失败: {e}")

        # 2. 提取报表链接（href 以 https://fbi. 开头的 <a>）
        try:
            link_loc = fl.locator('a[href*="fbi.alibaba-inc.com"]').first
            link_href = link_loc.get_attribute("href", timeout=5000)
            if link_href:
                result["link"] = link_href
                log(f"  iframe 链接提取成功: {link_href}")
        except Exception as e:
            log(f"  iframe 链接提取失败: {e}")

        # 3. 保存图片（优先直接下载 img src，分辨率更高；失败则 fallback 截图）
        try:
            IMAGE_DIR.mkdir(parents=True, exist_ok=True)
            today_str = datetime.date.today().strftime("%Y%m%d")
            safe_keyword = re.sub(r'[\\/:*?"<>|]', '_', keyword) if keyword else "email"

            # 优先尝试直接下载 img src（分辨率更高）
            download_success = False
            try:
                img_loc = fl.locator('.aym_scale_wrap img, img').first
                img_src = img_loc.get_attribute("src", timeout=5000)
                if img_src:
                    # 拼接完整 URL
                    if img_src.startswith("/"):
                        img_url = f"https://mail.alibaba-inc.com{img_src}"
                    else:
                        img_url = img_src
                    # 使用 page.context.request 下载
                    response = page.context.request.get(img_url)
                    if response.ok:
                        img_filename = f"{safe_keyword}_{today_str}_{mail_index}.jpeg"
                        img_save_path = str(IMAGE_DIR / img_filename)
                        with open(img_save_path, "wb") as f:
                            f.write(response.body())
                        log(f"  图片直接下载成功: {img_save_path}")
                        result["image_path"] = img_save_path
                        download_success = True
            except Exception as e:
                log(f"  图片直接下载失败，将尝试截图: {e}")

            # fallback：截图方式
            if not download_success:
                img_filename = f"{safe_keyword}_{today_str}_{mail_index}.png"
                img_save_path = str(IMAGE_DIR / img_filename)

                # 优先截图 aym_scale_wrap（数据图片容器），fallback 截图整个 iframe
                try:
                    img_container = fl.locator('.aym_scale_wrap').first
                    img_container.screenshot(path=img_save_path, timeout=8000)
                    log(f"  截图保存成功（aym_scale_wrap）: {img_save_path}")
                except Exception:
                    # fallback：截图整个 iframe 元素
                    iframe_el = page.query_selector('iframe')
                    if iframe_el:
                        iframe_el.screenshot(path=img_save_path)
                        log(f"  截图保存成功（iframe fallback）: {img_save_path}")
                    else:
                        img_save_path = ""
                        log("  未找到 iframe 元素，跳过截图")

                if img_save_path and os.path.exists(img_save_path):
                    result["image_path"] = img_save_path
        except Exception as e:
            log(f"  图片保存失败: {e}")

        # 4. 提取 iframe 内纯文本（备用）
        try:
            body_html = fl.locator('body').inner_text(timeout=5000).strip()
            if body_html:
                result["text"] = compress_blank_lines(body_html)
        except Exception:
            pass

    except Exception as e:
        log(f"iframe 正文提取失败: {e}")

    return result


# ─────────────────────────────────────────────
# 从正文全文中解析邮件元信息
# ─────────────────────────────────────────────
def parse_email_meta_from_text(text: str) -> dict:
    """
    从正文全文中解析标题、发件人、时间等元信息。
    返回 { title, sender, time, body }
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    title = lines[0] if lines else ""
    sender = ""
    time_str = ""

    # 发件人通常包含 @ 或 "发件人" 关键字
    for ln in lines[1:6]:
        if "@" in ln or "发件人" in ln or "From" in ln.lower():
            sender = ln
            break

    # 时间通常包含日期格式
    time_pattern = re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}")
    for ln in lines[1:10]:
        if time_pattern.search(ln):
            time_str = ln
            break

    # 正文：跳过前几行元信息
    body_start = 3
    body_lines = lines[body_start:] if len(lines) > body_start else lines
    body = "\n".join(body_lines)

    return {
        "title": title,
        "sender": sender or "（未知）",
        "time": time_str or "（未知）",
        "body": body,
    }


# ─────────────────────────────────────────────
# 重新定位搜索结果面板中的指定 article
# ─────────────────────────────────────────────
def locate_panel_article(page: Page, article_index: int, in_panel: bool):
    """
    重新定位搜索结果面板中第 article_index 个 article locator。
    三栏布局中点击邮件后面板仍存在，需重新定位避免 stale element。
    """
    if in_panel:
        try:
            header_locator = page.get_by_text(re.compile(r"搜索结果\s*约"))
            if header_locator.count() > 0:
                for ancestor_sel in [
                    "xpath=ancestor::div[.//article][1]",
                    "xpath=ancestor::section[.//article][1]",
                    "xpath=ancestor::*[.//article][1]",
                ]:
                    try:
                        candidate = header_locator.first.locator(ancestor_sel)
                        if candidate.count() > 0:
                            art_count = candidate.first.locator("article").count()
                            if 0 < art_count <= 20:
                                return candidate.first.locator("article").nth(article_index)
                    except Exception:
                        continue
        except Exception:
            pass
    # fallback：取全局 article
    return page.locator("article").nth(article_index)


# ─────────────────────────────────────────────
# 输出邮件日志（追加模式）
# ─────────────────────────────────────────────
def write_output(mails_info: list, keyword: str):
    """将邮件信息追加写入日志文件（同一个 txt，不按天重建）。"""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [f"\n{'='*50}", f"[{now_str}] {keyword} 邮件摘要", f"{'='*50}"]
    for m in mails_info:
        lines.append(f"主题：{m['subject']}")
        lines.append(f"发件人：{m['sender']}")
        lines.append(f"时间：{m['time']}")
        if m.get("image_path"):
            lines.append(f"图片：{m['image_path']}")
        if m.get("link"):
            lines.append(f"链接：{m['link']}")
        if m.get("body_text"):
            lines.append(f"正文：{m['body_text'][:200]}")
        lines.append("")

    # 追加模式写入
    with open(EMAIL_LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log(f"邮件信息已追加写入：{EMAIL_LOG_FILE}")


# ─────────────────────────────────────────────
# 主逻辑
# ─────────────────────────────────────────────
def main():
    setup_logging()
    log("报童启动 — 开始检查邮件（Playwright 浏览器方案）")

    # 加载 .env
    load_dotenv(BASE_DIR / ".env")
    keyword = os.getenv("MAIL_KEYWORD", "行业日报")
    profile_dir = os.getenv("MAIL_PROFILE_DIR", "~/.email_monitor_profile")

    pw = sync_playwright().start()
    context = None

    try:
        # 启动浏览器（复用 persistent context 中的登录态）
        context = create_context(pw, profile_dir)
        page = context.new_page()

        # --- 打开邮箱主页（确认登录态） ---
        log(f"打开邮箱: {MAIL_URL}")
        page.goto(MAIL_URL, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
        page.wait_for_timeout(3000)

        # 如果主地址无法加载，尝试备用地址
        current_url = page.url
        if "error" in current_url.lower() or page.title() == "":
            log(f"主地址加载异常，尝试备用地址: {MAIL_URL_FALLBACK}")
            page.goto(MAIL_URL_FALLBACK, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
            page.wait_for_timeout(3000)

        # --- 登录检测 ---
        if is_login_page(page):
            log("检测到需要登录！请先运行 email_monitor_login.py 完成首次登录。")
            print("⚠️  检测到需要登录！请先运行: python3 email_monitor_login.py")
            return

        log("登录态有效，继续执行")

        # --- 通过 URL 直接搜索邮件 ---
        result_count = search_emails(page, keyword)

        if result_count == 0:
            log("未找到匹配邮件，跳过输出")
            return

        # --- 获取搜索结果面板中的 article 列表（含摘要）---
        email_items = get_search_result_articles(page)

        if not email_items:
            log("未能解析到搜索结果 article，跳过输出")
            return

        log(f"共获取到 {len(email_items)} 封搜索结果邮件")

        # --- 只处理最新一封邮件（搜索结果默认按时间倒序，email_items[0] 即最新）---
        mails_info = []

        for idx, email_item in enumerate(email_items[:1], start=1):  # 只处理日期最新的一封邮件
            subject_preview = email_item["subject"][:40]
            log(f"只处理最新一封邮件: {subject_preview}")

            body_text = None
            sender = email_item["sender"]
            time_str = email_item["time"]
            subject = email_item["subject"]

            # ── 策略1：force=True 点击 article，等待右侧面板加载，提取正文 ──
            try:
                # 重新定位 article（避免 stale element）
                article_loc = locate_panel_article(
                    page,
                    email_item["article_index"],
                    email_item["in_panel"],
                )
                article_loc.scroll_into_view_if_needed(timeout=5000)
                article_loc.click(force=True)
                log(f"  已点击 article[{email_item['article_index']}]（force=True）")
                page.wait_for_timeout(3000)  # 等待右侧正文加载

                # 提取右侧正文（FBI 邮件：iframe 内含标题/图片/链接）
                body_dict = read_email_body(page, keyword=keyword, mail_index=idx)

                # 优先用 iframe 提取的标题覆盖列表摘要中的 subject
                if body_dict.get("title") and len(body_dict["title"]) > 3:
                    subject = body_dict["title"]
                body_text = body_dict  # 保存完整 dict
                log(f"  策略1成功，title={body_dict.get('title')}, "
                    f"image={'有' if body_dict.get('image_path') else '无'}, "
                    f"link={'有' if body_dict.get('link') else '无'}")

            except Exception as e1:
                log(f"  策略1失败（点击读取正文）: {e1}")

            # ── fallback：使用列表摘要 ──
            if not body_text:
                log(f"  邮件 {idx} 正文提取失败，使用列表摘要作为 fallback")
                body_text = {"title": "", "image_path": "", "link": "",
                             "text": email_item["snippet"] or "（无法提取正文，仅有摘要）"}

            # body_text 可能是 dict（策略1成功）或 str（旧 fallback）
            if isinstance(body_text, dict):
                img_path = body_text.get("image_path", "")
                link = body_text.get("link", "")
                body_str = body_text.get("text", "")
            else:
                img_path = ""
                link = ""
                body_str = body_text

            mails_info.append({
                "index": idx,
                "sender": sender,
                "subject": subject,
                "time": time_str,
                "image_path": img_path,
                "link": link,
                "body_text": body_str,
            })

        # --- 追加写入邮件日志 ---
        if mails_info:
            write_output(mails_info, keyword)
        else:
            log("所有邮件均读取失败，跳过输出")

    except Exception as e:
        log(f"发生异常：{e}")
        raise
    finally:
        # 清理浏览器资源
        if context:
            try:
                context.close()
            except Exception:
                pass
        pw.stop()
        log("浏览器已关闭，执行结束")


if __name__ == "__main__":
    main()
