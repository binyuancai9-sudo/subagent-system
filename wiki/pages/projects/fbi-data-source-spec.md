---
id: fbi-data-source-spec
title: "[项目] FBI报表数据源四模式接入规范"
category: projects
tags: [FBI报表, 数据源, 临时文件清理, 四模式, fbi_report_interpret]
date: 2026-05-18
status: stable
source: 导入自钉钉记忆, ID: 7d68e5e7
related: [project-function-tree]
---

# [项目] FBI报表数据源四模式接入规范

> **一句话摘要**: 数据可视化支持 Excel/文本/ODPS/FBI 四种数据源，FBI 模式执行标准 5 步流程。

---

## 背景

项目数据可视化技能已扩展支持第四种数据源：FBI 报表直读。

## 核心内容

### 四种数据源模式

| 模式 | 说明 |
|------|------|
| Excel | 本地 Excel 文件读取 |
| 文本 | CSV/TSV 等文本格式 |
| ODPS | PyODPS 数据仓库查询 |
| FBI | FBI 报表直读 |

### FBI 模式 5 步流程

1. **报表定位**：调用 `fbi_report_interpret` skill
2. **数据查询落地**：输出为 `/tmp/fbi_report_<id>_<timestamp>.csv`
3. **数据预览**：确认横纵轴
4. **图表类型确认**
5. **强制询问是否保留 Excel**：若用户拒绝则立即删除临时 CSV

> 图表文件（PNG/HTML）不受影响，正常保留。

## 引用 / 证据

- 钉钉记忆 ID: 7d68e5e7

## 更新记录

- 2026-05-18: 从钉钉记忆导入
