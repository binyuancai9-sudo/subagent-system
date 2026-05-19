---
id: png-default-output
title: "[偏好] data-visualization 技能默认输出 PNG"
category: preferences
tags: [data-visualization, matplotlib, PNG, 默认输出, 图表格式]
date: 2026-05-18
status: stable
source: 导入自钉钉记忆, ID: 73c1ffd3, ID: 68559485
related: [chart-legend-standard, chart-data-interpretation]
---

# [偏好] data-visualization 技能默认输出 PNG

> **一句话摘要**: 生成图表时优先用 matplotlib 输出 PNG，不用 pyecharts 的 HTML。折线图默认不标注数据值。

---

## 背景

用户明确要求 data-visualization 技能默认输出 PNG 图片而非 HTML 网页。此前默认使用 pyecharts 输出 HTML，带来不便。

## 核心内容

- **默认引擎**：matplotlib，输出 PNG 格式
- **不使用**：pyecharts 的 HTML 网页
- **折线图规则**：默认不标注数据值（`label_opts is_show=False`）

## 引用 / 证据

- 钉钉记忆 ID: 73c1ffd3, 68559485
- 已验证（2026-04-21）

## 更新记录

- 2026-05-18: 从钉钉记忆导入，合并偏好与经验两个来源
