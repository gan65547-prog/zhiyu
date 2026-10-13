# 编码规范

## Python代码规范

### 代码风格

- **缩进**: 使用4个空格进行缩进
- **行宽**: 每行不超过79个字符
- **空行**: 函数和类之间使用两个空行，方法之间使用一个空行
- **导入**: 按标准库、第三方库、本地模块的顺序导入

### 命名规范

- **变量**: 小写字母，单词之间用下划线分隔 (`user_name`)
- **函数**: 小写字母，单词之间用下划线分隔 (`get_user_info`)
- **类**: 首字母大写，驼峰命名法 (`UserService`)
- **常量**: 全部大写，单词之间用下划线分隔 (`MAX_RETRY_COUNT`)
- **模块**: 小写字母，单词之间用下划线分隔 (`user_service.py`)

### 代码示例

```python
# 导入顺序
import os
import sys

import requests
from fastapi import FastAPI

from app.services.user_service import UserService

# 常量定义
MAX_RETRY_COUNT = 3

# 类定义
class UserManager:
    """用户管理类"""
    
    def __init__(self, user_service):
        self.user_service = user_service
    
    def get_user(self, user_id):
        """获取用户信息"""
        for i in range(MAX_RETRY_COUNT):
            try:
                return self.user_service.get_user_by_id(user_id)
            except Exception as e:
                if i == MAX_RETRY_COUNT - 1:
                    raise
                continue

# 函数定义
def calculate_total(a, b):
    """计算两个数的和"""
    return a + b

# 变量命名
user_name = "张三"
user_age = 30
```

### 注释规范

- **模块注释**: 模块顶部添加模块说明
- **类注释**: 类定义后添加类说明
- **函数注释**: 函数定义后添加函数说明，包括参数和返回值
- **代码注释**: 复杂逻辑添加注释说明

```python
"""用户服务模块

提供用户管理相关的功能
"""

class UserService:
    """用户服务类
    
    负责用户的创建、查询、更新和删除操作
    """
    
    def create_user(self, user_data):
        """创建用户
        
        Args:
            user_data: 用户数据字典
            
        Returns:
            dict: 创建的用户信息
        """
        # 验证用户数据
        if not user_data.get('name'):
            raise ValueError("用户名不能为空")
        
        # 创建用户
        # ...
        return user_info
```

## TypeScript代码规范

### 代码风格

- **缩进**: 使用2个空格进行缩进
- **行宽**: 每行不超过80个字符
- **分号**: 语句结束使用分号
- **引号**: 使用单引号

### 命名规范

- **变量**: 驼峰命名法 (`userName`)
- **函数**: 驼峰命名法 (`getUserInfo`)
- **类**: 首字母大写，驼峰命名法 (`UserService`)
- **常量**: 全部大写，单词之间用下划线分隔 (`MAX_RETRY_COUNT`)
- **接口**: 首字母大写，驼峰命名法，以 `I` 开头 (`IUser`)

### 代码示例

```typescript
// 导入
import axios from 'axios';
import { User } from './types';

// 常量定义
const MAX_RETRY_COUNT = 3;

// 接口定义
interface IUser {
  id: number;
  name: string;
  email: string;
}

// 类定义
class UserManager {
  private userService: UserService;
  
  constructor(userService: UserService) {
    this.userService = userService;
  }
  
  async getUser(userId: number): Promise<IUser> {
    for (let i = 0; i < MAX_RETRY_COUNT; i++) {
      try {
        return await this.userService.getUserById(userId);
      } catch (error) {
        if (i === MAX_RETRY_COUNT - 1) {
          throw error;
        }
        continue;
      }
    }
  }
}

// 函数定义
function calculateTotal(a: number, b: number): number {
  return a + b;
}

// 变量命名
const userName: string = '张三';
const userAge: number = 30;
```

### 类型定义

- **使用TypeScript类型**: 为所有变量和函数参数添加类型
- **接口定义**: 为复杂数据结构定义接口
- **泛型**: 合理使用泛型

```typescript
// 接口定义
interface IApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

// 泛型函数
function fetchData<T>(url: string): Promise<IApiResponse<T>> {
  return axios.get<IApiResponse<T>>(url);
}

// 使用
interface IUser {
  id: number;
  name: string;
}

const response = await fetchData<IUser>('/api/users');
```

## 命名规范

### 通用命名规则

- **清晰明了**: 变量和函数命名应清晰表达其用途
- **避免缩写**: 除非是广泛认可的缩写（如 `id`、`url`）
- **一致性**: 项目中保持命名风格一致
- **避免单字母变量**: 除了循环变量和数学公式外

### 文件名命名

- **Python文件**: 小写字母，单词之间用下划线分隔 (`user_service.py`)
- **TypeScript文件**: 驼峰命名法 (`userService.ts`)
- **组件文件**: 首字母大写，驼峰命名法 (`UserComponent.vue`)

### 目录命名

- **小写字母**: 目录名使用小写字母
- **单词之间用下划线分隔**: `user_management`
- **简洁明了**: 目录名应清晰表达其用途

## 注释规范

### Python注释

- **模块注释**: 模块顶部添加模块说明
- **类注释**: 类定义后添加类说明
- **函数注释**: 函数定义后添加函数说明，使用 docstring
- **行注释**: 复杂逻辑添加行注释

### TypeScript注释

- **单行注释**: `// 注释内容`
- **多行注释**: `/* 注释内容 */`
- **JSDoc注释**: 为函数和类添加JSDoc注释

```typescript
/**
 * 用户服务类
 * 负责用户的创建、查询、更新和删除操作
 */
class UserService {
  /**
   * 创建用户
   * @param userData 用户数据
   * @returns 创建的用户信息
   */
  createUser(userData: IUser): Promise<IUser> {
    // 实现逻辑
  }
}
```

## 代码组织

### 模块划分

- **功能模块化**: 按功能划分模块
- **单一职责**: 每个模块只负责一个功能
- **依赖关系**: 低耦合，高内聚

### 可执行结构约束

- 单个 Python 文件不超过 800 行；单个函数不超过 120 行；圈复杂度不超过 15。
- 超过阈值的历史代码必须登记在 `scripts/quality/code-quality-baseline.json`，新代码不得复制或扩大该债务。
- 一个业务用例拆为输入、权限、领域处理、持久化/事件和输出阶段；出现多个嵌套分支、多个外部客户端或多次提交时必须拆分策略或端口。
- API、Service、Core、Infrastructure 只能按单向依赖流动；禁止 API 直接访问 ORM，禁止 Core 反向依赖 API。
- 异步任务只传资源标识、租户标识和幂等信息，任务体不携带原文；任务必须可重试、可观测、可恢复。

这些约束由 `scripts/quality/check-code-structure.py` 和 `scripts/quality/run-quality-gates.sh` 自动执行，不以人工审查替代。

### 文件结构

- **Python项目结构**:
  - `api/`: API路由
  - `services/`: 业务逻辑
  - `models/`: 数据模型
  - `schemas/`: 数据验证
  - `core/`: 核心功能
  - `infrastructure/`: 基础设施

- **TypeScript项目结构**:
  - `components/`: 组件
  - `views/`: 页面
  - `services/`: API服务
  - `stores/`: 状态管理
  - `utils/`: 工具函数
  - `types/`: 类型定义

### 代码分层

- **API层**: 处理HTTP请求和响应
- **服务层**: 处理业务逻辑
- **数据层**: 处理数据存储和检索
- **工具层**: 提供通用工具函数

## 错误处理

### Python错误处理

- **使用异常**: 合理使用异常处理
- **具体异常**: 捕获具体的异常类型
- **错误信息**: 提供清晰的错误信息
- **日志记录**: 记录错误日志

```python
def process_user(user_id):
    try:
        user = get_user(user_id)
        if not user:
            raise ValueError(f"用户 {user_id} 不存在")
        # 处理用户
    except DatabaseError as e:
        logger.error(f"数据库错误: {e}")
        raise
    except ValueError as e:
        logger.warning(f"业务错误: {e}")
        raise
    except Exception as e:
        logger.error(f"未知错误: {e}")
        raise
```

### TypeScript错误处理

- **使用try-catch**: 合理使用try-catch
- **Promise错误处理**: 使用async/await和try-catch
- **错误类型**: 定义错误类型
- **错误边界**: 使用错误边界处理UI错误

```typescript
async function fetchUser(userId: number): Promise<IUser> {
  try {
    const response = await axios.get(`/api/users/${userId}`);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error('API错误:', error.response?.data);
      throw new Error(`获取用户失败: ${error.response?.data?.message || '未知错误'}`);
    } else {
      console.error('未知错误:', error);
      throw new Error('获取用户失败');
    }
  }
}
```

## 性能优化

### Python性能优化

- **使用生成器**: 处理大量数据时使用生成器
- **避免频繁IO**: 批量处理IO操作
- **使用缓存**: 缓存频繁访问的数据
- **优化数据库查询**: 使用索引，避免N+1查询
- **使用异步**: 对于IO密集型操作使用异步

### TypeScript性能优化

- **减少重渲染**: 使用React.memo或Vue的computed
- **懒加载**: 组件和路由懒加载
- **虚拟滚动**: 处理长列表
- **防抖和节流**: 优化事件处理
- **Web Workers**: 处理耗时操作

## 安全最佳实践

### Python安全

- **SQL注入防护**: 使用参数化查询
- **XSS防护**: 对用户输入进行转义
- **CSRF防护**: 使用CSRF令牌
- **密码安全**: 使用bcrypt等安全的哈希算法
- **权限验证**: 实现细粒度的权限控制

### TypeScript安全

- **输入验证**: 验证用户输入
- **XSS防护**: 使用安全的渲染方法
- **CSRF防护**: 实现CSRF令牌验证
- **API安全**: 使用HTTPS，实现认证和授权
- **依赖安全**: 定期更新依赖，检查安全漏洞

## 测试规范

### 单元测试

- **测试覆盖率**: 目标覆盖率 > 80%
- **测试命名**: 清晰表达测试目的
- **测试隔离**: 测试之间相互隔离
- **测试数据**: 使用测试数据工厂

### 集成测试

- **测试场景**: 测试完整的业务流程
- **测试环境**: 使用独立的测试环境
- **测试数据**: 准备测试数据

### 测试工具

- **Python**: pytest, unittest
- **TypeScript**: Jest, Vitest

## 代码审查

### 审查要点

- **代码风格**: 符合编码规范
- **逻辑正确性**: 业务逻辑正确
- **性能优化**: 代码性能良好
- **安全问题**: 无安全漏洞
- **测试覆盖**: 有足够的测试覆盖

### 审查流程

1. **提交代码**: 开发者提交代码
2. **代码审查**:  reviewer 审查代码
3. **反馈修改**: 开发者根据反馈修改
4. **合并代码**: 代码通过审查后合并

## 版本控制

### 提交规范

- **提交信息**: 清晰描述提交内容
- **提交格式**: `<type>: <description>`
- **类型**: feat, fix, docs, style, refactor, test, chore

### 分支管理

- **main**: 主分支，稳定版本
- **develop**: 开发分支
- **feature**: 功能分支
- **bugfix**: 修复分支
- **release**: 发布分支

### 提交示例

```
feat: 添加用户注册功能
fix: 修复登录失败的问题
docs: 更新API文档
refactor: 重构用户服务
```

## 工具推荐

### Python工具

- **代码格式化**: black, isort
- **代码检查**: flake8, pylint
- **类型检查**: mypy
- **测试**: pytest
- **依赖管理**: pipenv, poetry

### TypeScript工具

- **代码格式化**: prettier
- **代码检查**: eslint
- **类型检查**: tsc
- **测试**: jest, vitest
- **构建工具**: webpack, vite

## 最佳实践

1. **代码可读性**: 优先考虑代码可读性
2. **可维护性**: 编写易于维护的代码
3. **可测试性**: 编写可测试的代码
4. **性能**: 考虑代码性能
5. **安全**: 考虑代码安全
6. **一致性**: 保持代码风格一致
7. **文档**: 编写清晰的文档
8. **测试**: 编写充分的测试
