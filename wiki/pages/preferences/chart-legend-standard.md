---
id: chart-legend-standard
title: "[偏好] 图表图例统一左上角、2xN网格排列"
category: preferences
tags: [图例, legend, 左上角, ncol, 2x2排列, matplotlib, 不遮挡, 不高于标题]
date: 2026-05-18
status: stable
source: 导入自钉钉记忆, ID: 97bd7597
related: [png-default-output, chart-data-interpretation]
---

# [偏好] 图表图例统一左上角、2xN网格排列

> **一句话摘要**: 所有 matplotlib 图表的图例放左上角外、2xN 网格排列、不遮挡数据线、不高于标题。

---

## 背景

图例遮挡数据线、占用绘图区域是反复出现的问题，用户要求统一图例行为。

## 核心内容

1. **位置**：统一放在左上角（`loc='upper left'`）
2. **不遮挡**：使用 `bbox_to_anchor` 将图例放在绘图区域外部左上方，不遮挡数据线
3. **排列**：尽量使用 2xN 网格排列（`ncol=2`），避免过长的一行或一列
4. **不高于标题**：图例位置不得高于图表标题

**实现示例**：
```python
ax.legend(loc='upper left', bbox_to_anchor=(0, 1.15), ncol=2, fontsize=9)
```

## 引用 / 证据

- 钉钉记忆 ID: 97bd7597

## 更新记录

- 2026-05-18: 从钉钉记忆导入
