---
id: auto-delete-temp-scripts
title: "[偏好] 临时Python脚本完成后自动删除"
category: preferences
tags: [Python, 临时脚本, 自动删除, 清理]
date: 2026-05-18
status: stable
source: 导入自钉钉记忆, ID: 654ca4b7
related: []
---

# [偏好] 临时Python脚本完成后自动删除

> **一句话摘要**: 为任务创建的临时 Python 脚本，任务完成后默认自动删除，不保留中间产物。

---

## 背景

用户在工作中频繁使用 Python 脚本生成数据（Excel、图表等），这些脚本是一次性的，任务完成后无保留价值。

## 核心内容

- 为完成任务而创建的临时 Python 脚本（如生成 Excel、数据处理、格式转换等）
- 在任务完成并确认输出正确后，**必须默认自动删除**，不要留在用户目录中
- 只保留最终产出物（如 Excel、PNG 等），不保留中间脚本文件
- **无需询问用户是否删除**，直接清理
