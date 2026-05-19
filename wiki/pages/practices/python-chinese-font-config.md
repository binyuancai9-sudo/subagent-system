---
id: python-chinese-font-config
title: "[规范] Python 图表中文字体配置"
category: practices
tags: [matplotlib, 中文字体, PNG图表, unicode_minus, PingFang, 中文乱码]
date: 2026-05-18
status: stable
source: 导入自钉钉记忆, ID: 0859324b, ID: ae66ec9e
related: [png-default-output]
---

# [规范] Python 图表中文字体配置

> **一句话摘要**: matpotlib 生成 PNG 图表含中文时，必须配置中文字体，否则出现乱码。优先检测系统字体。

---

## 背景

matplotlib 中文乱码是反复出现的问题。需要通过标准化脚本解决。

## 核心内容

### 问题 → 根因 → 解法 → 教训

- **问题**：matplotlib 生成图表时中文显示为方框或乱码
- **根因**：matplotlib 默认字体不支持中文
- **解法**：脚本内置 `setup_chinese_font()` 自动检测系统字体

### 字体优先级

| 系统 | 优先字体 |
|------|----------|
| macOS | PingFang SC / PingFang.ttc / STHeitiMedium.ttc |
| Windows | SimHei |
| Linux | WenQuanYi Micro Hei |

### 必需配置

```python
plt.rcParams['font.family'] = detected_font
plt.rcParams['axes.unicode_minus'] = False
```

### 兜底方案

- 若系统字体均失败，手动安装中文字体或切换至 pyecharts 引擎

## 引用 / 证据

- 钉钉记忆 ID: 0859324b, ae66ec9e
- 已验证（2026-04-21）

## 更新记录

- 2026-05-18: 从钉钉记忆导入，合并规范与踩坑经验
