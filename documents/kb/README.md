# 知识库同步入口

此目录是团队知识库的本地同步入口。放入此目录的 `.md` 文件可通过导入脚本同步到 RAG 平台。

## 快速开始

### 1. 放入文档

将 markdown 文件放置在此目录下，支持子目录组织：

```
documents/kb/
├── README.md
├── 产品设计/
│   ├── 需求文档.md
│   └── 技术方案.md
└── 会议记录/
    └── 周会-2026-05-23.md
```

### 2. 预览导入

```bash
python3.12 scripts/import_directory_to_ganfy.py \
  --source documents/kb \
  --dataset "团队知识库" \
  --dry-run
```

### 3. 执行导入

```bash
python3.12 scripts/import_directory_to_ganfy.py \
  --source documents/kb \
  --dataset "团队知识库" \
  --knowledge-type reference \
  --base-url https://your-domain.example \
  --all
```

## 文档编写规范

- 文件名作为标题，首个 `# 标题` 优先
- 子目录名自动作为标签
- 建议每个 `.md` 文件 500-5000 字
- 文件名避免特殊字符和过长名称

## 知识类型

导入时可指定 `--knowledge-type`：
- `reference` — 参考文档（默认）
- `topic` — 领域全景
- `concept` — 深度概念
- `summary` — 项目复盘
- `recipe` — 工程食谱
- `errata` — 勘误记录

## 环境变量

```bash
export GANFY_BASE_URL="https://your-domain.example"
export GANFY_EMAIL="your-email@example.com"
export GANFY_PASSWORD="your-password"
```
