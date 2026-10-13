# 贡献指南

感谢你对企业级RAG系统的关注！本文档将指导你如何参与项目贡献。

---

## 📋 贡献方式

### 代码贡献
- 修复Bug
- 新功能开发
- 性能优化
- 代码重构
- 测试用例补充

### 文档贡献
- 文档错误修正
- 文档内容补充
- 翻译工作
- 示例代码完善

### 其他贡献
- 问题反馈
- 功能建议
- 设计改进
- 代码审查

---

## 🚀 开始贡献

### 1. 准备环境

```bash
# 克隆仓库
git clone <repository-url> rag-system
cd rag-system

# 创建分支
git checkout -b feature/your-feature-name

# 安装后端依赖
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-test.txt

# 安装前端依赖
cd ../frontend
npm install
```

### 2. 开发流程

#### 后端开发
```bash
cd backend
source venv/bin/activate

# 启动开发服务器
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 运行测试
pytest tests/ -v

# 检查代码质量
black .
isort .
flake8 .
```

#### 前端开发
```bash
cd frontend

# 启动开发服务器
npm run dev

# 运行测试
npm test

# 检查代码质量
npm run lint
```

### 3. 提交代码

#### 提交信息格式

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type 类型**:
- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构（不是新功能，也不是修复）
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具/辅助工具

**示例**:
```
feat(auth): 添加OAuth2.0登录支持

实现Google和GitHub的OAuth2.0登录流程，
包括回调处理和Token管理。

Closes #123
```

#### 分支命名规范

```
feature/xxx     新功能
fix/xxx         Bug修复
docs/xxx        文档更新
refactor/xxx    重构
test/xxx        测试相关
hotfix/xxx      紧急修复
```

**示例**:
```
feature/oauth2-login
fix/user-auth-error
docs/api-overview
refactor/database-connection
test/chat-module
```

---

## 📝 编码规范

### Python (后端)

#### 代码风格
- 使用 Black 格式化工具
- 使用 isort 排序导入
- 行宽限制: 88字符
- 使用类型注解

#### 命名规范
- **变量/函数**: snake_case (`user_name`, `get_user()`)
- **类**: PascalCase (`UserService`)
- **常量**: UPPER_SNAKE_CASE (`MAX_RETRY_COUNT`)
- **模块**: snake_case (`user_service.py`)

#### 文档字符串
使用 Google 风格的 docstring:

```python
def get_user(user_id: int) -> Optional[User]:
    """根据ID获取用户信息。
    
    Args:
        user_id: 用户唯一标识符
        
    Returns:
        用户对象，如果不存在则返回None
        
    Raises:
        UserNotFoundError: 当用户不存在时
    """
    # 实现
```

### TypeScript (前端)

#### 代码风格
- 使用 Prettier 格式化
- 使用 ESLint 检查
- 使用分号
- 使用单引号

#### 命名规范
- **变量/函数**: camelCase (`userName`, `getUser()`)
- **类**: PascalCase (`UserService`)
- **常量**: UPPER_SNAKE_CASE (`MAX_RETRY_COUNT`)
- **接口**: PascalCase + I前缀 (`IUser`)

#### 类型定义
始终为函数参数和返回值添加类型:

```typescript
interface IUser {
  id: string;
  name: string;
  email: string;
}

async function getUser(userId: string): Promise<IUser | null> {
  // 实现
}
```

---

## 🧪 测试要求

### 单元测试
- 核心业务逻辑必须有单元测试
- 测试覆盖率目标: > 80%
- 使用 pytest (Python) / Jest (TypeScript)

### 测试示例

**Python**:
```python
def test_create_user_success(mock_db):
    """测试成功创建用户"""
    service = UserService(mock_db)
    user_data = {
        "name": "张三",
        "email": "zhangsan@example.com",
        "password": "password123"
    }
    
    user = service.create_user(user_data)
    
    assert user.name == "张三"
    assert user.email == "zhangsan@example.com"
    mock_db.add.assert_called_once()
```

**TypeScript**:
```typescript
it('should create user successfully', async () => {
  const userData = {
    name: '张三',
    email: 'zhangsan@example.com',
    password: 'password123'
  };
  
  const result = await userService.createUser(userData);
  
  expect(result.name).toBe('张三');
  expect(result.email).toBe('zhangsan@example.com');
});
```

---

## 🔍 Pull Request 流程

### 1. 提交PR前检查清单

- [ ] 代码遵循编码规范
- [ ] 所有测试通过
- [ ] 新功能有对应的测试
- [ ] 文档已更新（如需要）
- [ ] 提交信息符合规范
- [ ] 没有引入新的警告或错误

### 2. PR描述模板

```markdown
## 📋 变更描述
简要描述这个PR做了什么

## 🎯 变更类型
- [ ] Bug修复
- [ ] 新功能
- [ ] 重构
- [ ] 文档更新
- [ ] 性能优化
- [ ] 其他: _______

## 🧪 测试说明
- [ ] 已添加单元测试
- [ ] 已添加集成测试
- [ ] 手动测试通过

## 📸 截图（UI变更）
如有UI变更，请提供截图

## 📝 相关Issue
Closes #issue_number

## ✅ 检查清单
- [ ] 代码自审完成
- [ ] 测试全部通过
- [ ] 文档已更新
```

### 3. 代码审查标准

**必须满足**:
- 无明显的Bug或安全问题
- 符合项目编码规范
- 有足够的测试覆盖
- 文档已同步更新

**建议优化**:
- 性能优化建议
- 代码可读性改进
- 更好的错误处理
- 更完善的日志记录

---

## 🐛 报告问题

### Issue模板

使用GitHub Issue报告问题时，请包含：

**Bug报告**:
```markdown
## 问题描述
清晰描述遇到的问题

## 复现步骤
1. 进入'...'
2. 点击'....'
3. 滚动到'....'
4. 看到错误

## 期望行为
描述应该发生什么

## 实际行为
描述实际发生了什么

## 截图
如果适用，请添加截图

## 环境
- OS: [e.g. macOS, Windows]
- Browser: [e.g. Chrome 120]
- Version: [e.g. v2.0.0]

## 其他信息
关于问题的其他上下文信息
```

**功能请求**:
```markdown
## 功能描述
清晰描述你想要的功能

## 解决的问题
这个功能解决了什么问题或痛点

## 建议方案
如果有，描述你的解决方案想法

## 替代方案
你考虑过的其他替代方案

## 其他信息
其他上下文、截图等
```

---

## 📚 文档贡献

### 文档结构
项目文档位于 `documents/` 目录：
- `architecture/` - 架构文档
- `api/` - API文档
- `deployment/` - 部署文档
- `development/` - 开发文档
- `reports/` - 审核报告
- `archive/` - 归档文档

### 文档编写规范
1. 使用中文（项目主要语言）
2. Markdown格式
3. 清晰的结构和层次
4. 包含代码示例
5. 添加必要的图表

### 文档更新流程
1. Fork仓库并创建分支
2. 修改或新增文档
3. 更新 documents/README.md 索引
4. 提交Pull Request

---

## 💬 社区交流

### 讨论渠道
- **GitHub Issues**: Bug报告和功能请求
- **GitHub Discussions**: 技术讨论和问答
- **Slack**: 实时交流（邀请制）

### 行为准则
- 尊重他人
- 保持专业
- 建设性反馈
- 帮助新人

---

## 🙏 致谢

所有贡献者都将被列入项目的贡献者列表。

感谢你的时间和付出！

---

## ❓ 常见问题

**Q: 我可以贡献小改动吗？**
A: 当然！任何有价值的贡献都欢迎，包括错别字修正、文档改进等。

**Q: 我不懂代码能贡献吗？**
A: 可以！文档翻译、bug报告、功能建议等都是很好的贡献方式。

**Q: 我的PR多久会被审查？**
A: 我们通常在1-3个工作日内进行首次审查。复杂的功能可能需要更长时间。

**Q: 如何成为核心贡献者？**
A: 持续贡献高质量代码，参与社区讨论，帮助其他开发者。

---

**最后更新**: 2026-04-05  
**维护人**: 项目团队