---
id: local-agent-roster
title: "[项目] 本地Subagent清单与分工"
category: projects
tags: [agent, 包工头, 书写者, sql-optimizer, 学习者, 调度]
date: 2026-05-19
status: stable
source: 对话创建，2026-05-19
related: [project-function-tree]
---

# [项目] 本地Subagent清单与分工

> **一句话摘要**：本项目有四个专业subagent，由"包工头"统一调度，各司其职节约主上下文空间。

---

## 背景

本地agent项目通过拆分专职subagent来隔离上下文、提升效率。包工头负责需求拆解和任务调度，其余三个agent负责具体执行。

## 核心内容

### Agent清单

| Agent | 文件 | 专长 | 发包触发 |
|-------|------|------|---------|
| **包工头** | `.qoder/agents/包工头.md` | 需求拆解、任务调度、跨域协调 | 复合需求、多领域任务 |
| **书写者** | `.qoder/agents/书写者.md` | 业务周报/文档生成，钉钉文档读取 | 写报告、写周报、生成文档 |
| **sql-optimizer**（代码工人）| `.qoder/agents/sql-optimizer.md` | SQL优化、PyODPS跑数、数据验证 | 优化SQL、跑数、取数验证 |
| **学习者** | `.qoder/agents/学习者.md` | 文档知识提取，归档到wiki | 学习文档、提取经验、知识归档 |

### 包工头调度逻辑

```
用户复杂需求
    ↓
包工头拆解（展示子任务表格 + 确认）
    ↓
并行/串行发包给专业agent
    ↓
汇总产出 + 经验归档评估
```

### 直发规则

- 单一领域任务 → 直接调用对应agent，不经包工头
- 复合需求（≥2个领域）→ 走包工头调度

## 引用 / 证据

- 文件路径：`.qoder/agents/`

## 更新记录

- 2026-05-19: 创建页面，包工头agent正式上线
