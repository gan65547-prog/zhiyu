# 数据模型

## 请求模型

### 用户注册请求

```json
{
  "name": "string",
  "email": "string",
  "password": "string"
}
```

### 用户登录请求

```json
{
  "email": "string",
  "password": "string"
}
```

### 刷新令牌请求

```json
{
  "refresh_token": "string"
}
```

### 租户创建请求

```json
{
  "name": "string",
  "domain": "string"
}
```

### 工作空间创建请求

```json
{
  "name": "string",
  "description": "string",
  "tenant_id": "integer"
}
```

### 知识库创建请求

```json
{
  "name": "string",
  "description": "string",
  "workspace_id": "integer"
}
```

### 文档上传请求

```json
{
  "dataset_id": "integer",
  "name": "string",
  "file": "file"
}
```

### 对话创建请求

```json
{
  "name": "string",
  "workspace_id": "integer"
}
```

### 消息发送请求

```json
{
  "content": "string",
  "dataset_ids": "array"
}
```

## 响应模型

### 成功响应

```json
{
  "id": "integer",
  "name": "string",
  "created_at": "datetime"
}
```

### 错误响应

```json
{
  "error": "string",
  "message": "string",
  "code": "integer"
}
```

### 分页响应

```json
{
  "items": "array",
  "total": "integer",
  "page": "integer",
  "size": "integer"
}
```

## 数据模型定义

### User

| 字段 | 类型 | 描述 |
|------|------|------|
| id | integer | 用户ID |
| name | string | 用户名 |
| email | string | 邮箱 |
| password | string | 密码哈希 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### Tenant

| 字段 | 类型 | 描述 |
|------|------|------|
| id | integer | 租户ID |
| user_id | integer | 关联用户ID |
| name | string | 租户名称 |
| domain | string | 租户域名 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### Workspace

| 字段 | 类型 | 描述 |
|------|------|------|
| id | integer | 工作空间ID |
| tenant_id | integer | 关联租户ID |
| name | string | 工作空间名称 |
| description | string | 工作空间描述 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### Dataset

| 字段 | 类型 | 描述 |
|------|------|------|
| id | integer | 知识库ID |
| workspace_id | integer | 关联工作空间ID |
| name | string | 知识库名称 |
| description | string | 知识库描述 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### Document

| 字段 | 类型 | 描述 |
|------|------|------|
| id | integer | 文档ID |
| dataset_id | integer | 关联知识库ID |
| name | string | 文档名称 |
| content | string | 文档内容 |
| status | string | 处理状态 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### Chat

| 字段 | 类型 | 描述 |
|------|------|------|
| id | integer | 对话ID |
| workspace_id | integer | 关联工作空间ID |
| name | string | 对话名称 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### Message

| 字段 | 类型 | 描述 |
|------|------|------|
| id | integer | 消息ID |
| chat_id | integer | 关联对话ID |
| role | string | 角色 |
| content | string | 消息内容 |
| created_at | datetime | 创建时间 |

## 错误码

| 错误码 | 描述 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 403 | 禁止访问 |
| 404 | 资源不存在 |
| 409 | 资源已存在 |
| 413 | 文件过大 |
| 415 | 文件类型不支持 |
| 500 | 服务器内部错误 |

## 状态码

| 状态码 | 描述 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 204 | 删除成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 403 | 禁止访问 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |