---
id: excel-color-scheme
title: "[偏好] Excel生成优先橙色色系+灰色分隔"
category: preferences
tags: [Excel, openpyxl, 橙色, 配色, PatternFill, 灰色, 表头]
date: 2026-05-18
status: stable
source: 导入自钉钉记忆, ID: d9f8b36b
related: []
---

# [偏好] Excel生成优先橙色色系+灰色分隔

> **一句话摘要**: 生成 Excel 时主色调用橙色系（表头、一级分组），灰色系做子级分隔，不再用蓝色。

---

## 背景

用户对 Excel 输出有固定配色偏好，蓝色系已被淘汰。

## 核心内容

1. **主色调**：优先使用橙色色系
   - 表头背景：如 `F4A460` / `ED7D31` 等橙色
   - 一级分组标题行也使用橙色
2. **分隔色**：二级指标或子分组行使用灰色（如 `D9D9D9` / `F2F2F2`）
3. **禁用**：不再使用蓝色色系（如之前的 `4472C4` / `D6E4F0`）作为默认配色
4. 使用 openpyxl 的 `PatternFill` 设置时直接使用对应的十六进制色值

## 引用 / 证据

- 钉钉记忆 ID: d9f8b36b

## 更新记录

- 2026-05-18: 从钉钉记忆导入
