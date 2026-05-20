#!/bin/bash
# 邮件监控定时任务 - 安装/卸载脚本
# 用法:
#   ./setup_email_monitor.sh install   - 安装定时任务
#   ./setup_email_monitor.sh uninstall - 卸载定时任务
#   ./setup_email_monitor.sh status    - 查看任务状态
#   ./setup_email_monitor.sh test      - 立即手动执行一次
#   ./setup_email_monitor.sh login     - 首次登录（保存浏览器 session）

PLIST_NAME="com.qorder.email-monitor"
PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/${PLIST_NAME}.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

case "$1" in
    install)
        echo ">>> 安装定时任务..."

        # 创建日志目录
        mkdir -p "${SCRIPT_DIR}/logs"

        # 复制 plist 到 LaunchAgents
        cp "$PLIST_SRC" "$PLIST_DST"
        echo "  已复制 plist -> $PLIST_DST"

        # 加载任务
        launchctl load "$PLIST_DST"
        echo "  已加载任务: $PLIST_NAME"
        echo ">>> 安装完成! 每天 10:00 将自动执行邮件监控。"
        echo ">>> 使用 './setup_email_monitor.sh status' 查看状态。"
        ;;

    uninstall)
        echo ">>> 卸载定时任务..."

        # 先卸载
        launchctl unload "$PLIST_DST" 2>/dev/null
        echo "  已卸载任务"

        # 删除 plist
        rm -f "$PLIST_DST"
        echo "  已删除 $PLIST_DST"
        echo ">>> 卸载完成。"
        ;;

    status)
        echo ">>> 任务状态:"
        launchctl list | grep "$PLIST_NAME" || echo "  任务未加载"
        echo ""
        echo ">>> 最近日志:"
        tail -20 "${SCRIPT_DIR}/logs/email_monitor.log" 2>/dev/null || echo "  暂无日志"
        ;;

    test)
        echo ">>> 手动执行邮件监控脚本..."

        # 检查浏览器 profile 目录是否存在
        PROFILE_DIR=$(python3 -c "import os; from dotenv import load_dotenv; from pathlib import Path; load_dotenv(Path('${SCRIPT_DIR}') / '.env'); print(os.getenv('MAIL_PROFILE_DIR', '~/.email_monitor_profile'))")
        EXPANDED_DIR=$(eval echo "${PROFILE_DIR}")
        if [ ! -d "${EXPANDED_DIR}" ]; then
            echo "⚠️  浏览器 Profile 目录不存在: ${EXPANDED_DIR}"
            echo "请先运行首次登录: ./setup_email_monitor.sh login"
            exit 1
        fi

        python3 "${SCRIPT_DIR}/email_monitor.py"
        ;;

    login)
        echo ">>> 启动首次登录（有头浏览器模式）..."
        echo "请在浏览器中完成邮箱登录，登录成功后 session 将自动保存。"
        python3 "${SCRIPT_DIR}/email_monitor_login.py"
        ;;

    *)
        echo "用法: $0 {install|uninstall|status|test|login}"
        echo ""
        echo "  install   - 安装定时任务 (每天 10:00 执行)"
        echo "  uninstall - 卸载定时任务"
        echo "  status    - 查看任务状态和最近日志"
        echo "  test      - 立即手动执行一次"
        echo "  login     - 首次登录（保存浏览器 session）"
        exit 1
        ;;
esac
