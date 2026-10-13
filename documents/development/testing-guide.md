# 测试指南

## 测试策略

### 测试层次

| 测试类型 | 测试范围 | 目的 | 工具 |
|---------|---------|------|------|
| 单元测试 | 单个函数/方法 | 验证代码单元的正确性 | pytest, unittest |
| 集成测试 | 多个模块 | 验证模块之间的交互 | pytest, TestCase |
| 端到端测试 | 整个系统 | 验证系统功能完整性 | Selenium, Cypress |
| 性能测试 | 系统性能 | 验证系统性能指标 | Locust, JMeter |
| 安全测试 | 系统安全 | 验证系统安全性 | OWASP ZAP |

### 测试覆盖率目标

- **单元测试**: > 80%
- **集成测试**: > 60%
- **端到端测试**: 覆盖核心业务流程

## 单元测试

### Python单元测试

#### 测试框架

- **pytest**: 推荐使用
- **unittest**: 标准库

#### 测试结构

```
backend/
├── tests/
│   ├── test_services/
│   │   ├── test_user_service.py
│   │   └── test_chat_service.py
│   ├── test_api/
│   │   ├── test_auth.py
│   │   └── test_users.py
│   └── conftest.py
└── requirements-test.txt
```

#### 测试示例

```python
# test_user_service.py
import pytest
from services.user_service import UserService
from models.user import User

class TestUserService:
    def test_create_user(self, mock_db):
        """测试创建用户"""
        user_service = UserService(mock_db)
        user_data = {
            "name": "张三",
            "email": "zhangsan@example.com",
            "password": "password123"
        }
        user = user_service.create_user(user_data)
        assert user.name == "张三"
        assert user.email == "zhangsan@example.com"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_get_user_by_id(self, mock_db):
        """测试根据ID获取用户"""
        user_service = UserService(mock_db)
        mock_user = User(id=1, name="张三", email="zhangsan@example.com")
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_user
        user = user_service.get_user_by_id(1)
        assert user.id == 1
        assert user.name == "张三"
```

#### 运行测试

```bash
# 安装测试依赖
pip install -r requirements-test.txt

# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_services/test_user_service.py

# 运行特定测试方法
pytest tests/test_services/test_user_service.py::TestUserService::test_create_user

# 查看测试覆盖率
pytest --cov=services --cov-report=html
```

### TypeScript单元测试

#### 测试框架

- **Jest**: 推荐使用
- **Vitest**: 更快的替代方案

#### 测试结构

```
frontend/
├── tests/
│   ├── components/
│   │   ├── test-button.spec.ts
│   │   └── test-input.spec.ts
│   ├── services/
│   │   ├── test-user.service.spec.ts
│   │   └── test-api.service.spec.ts
│   └── utils/
│       └── test-helpers.spec.ts
└── package.json
```

#### 测试示例

```typescript
// test-user.service.spec.ts
import { UserService } from '@/services/user.service';
import axios from 'axios';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('UserService', () => {
  let userService: UserService;

  beforeEach(() => {
    userService = new UserService();
    jest.clearAllMocks();
  });

  test('should create user', async () => {
    const userData = {
      name: '张三',
      email: 'zhangsan@example.com',
      password: 'password123'
    };
    const expectedResponse = {
      id: 1,
      name: '张三',
      email: 'zhangsan@example.com'
    };

    mockedAxios.post.mockResolvedValue({ data: expectedResponse });

    const result = await userService.createUser(userData);
    expect(result).toEqual(expectedResponse);
    expect(mockedAxios.post).toHaveBeenCalledWith('/api/users', userData);
  });

  test('should get user by id', async () => {
    const expectedUser = {
      id: 1,
      name: '张三',
      email: 'zhangsan@example.com'
    };

    mockedAxios.get.mockResolvedValue({ data: expectedUser });

    const result = await userService.getUserById(1);
    expect(result).toEqual(expectedUser);
    expect(mockedAxios.get).toHaveBeenCalledWith('/api/users/1');
  });
});
```

#### 运行测试

```bash
# 运行所有测试
npm test

# 运行特定测试文件
npm test tests/services/test-user.service.spec.ts

# 查看测试覆盖率
npm test -- --coverage
```

## 集成测试

### 测试范围

- **API集成**: 测试API接口之间的交互
- **服务集成**: 测试服务之间的调用
- **数据库集成**: 测试与数据库的交互

### 测试环境

- **测试数据库**: 独立的测试数据库
- **测试配置**: 专门的测试配置
- **测试数据**: 测试专用数据

### 测试示例

```python
# test_api_integration.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

class TestAPIIntegration:
    def test_user_registration_and_login(self):
        """测试用户注册和登录流程"""
        # 注册用户
        register_response = client.post(
            "/api/auth/register",
            json={
                "name": "测试用户",
                "email": "test@example.com",
                "password": "password123"
            }
        )
        assert register_response.status_code == 201
        user_data = register_response.json()
        assert "id" in user_data
        assert user_data["email"] == "test@example.com"

        # 登录用户
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data

        # 使用token获取用户信息
        token = login_data["access_token"]
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["email"] == "test@example.com"
```

## 端到端测试

### 测试工具

- **Selenium**: 浏览器自动化测试
- **Cypress**: 现代前端测试工具
- **Playwright**: Microsoft的浏览器自动化工具

### 测试示例

```javascript
// cypress/e2e/login.cy.js
describe('登录测试', () => {
  it('应该能够成功登录', () => {
    // 访问登录页面
    cy.visit('/login');

    // 输入邮箱和密码
    cy.get('input[name="email"]').type('test@example.com');
    cy.get('input[name="password"]').type('password123');

    // 点击登录按钮
    cy.get('button[type="submit"]').click();

    // 验证登录成功后跳转到首页
    cy.url().should('include', '/dashboard');
    cy.contains('欢迎回来');
  });

  it('应该显示登录错误', () => {
    // 访问登录页面
    cy.visit('/login');

    // 输入错误的邮箱和密码
    cy.get('input[name="email"]').type('wrong@example.com');
    cy.get('input[name="password"]').type('wrongpassword');

    // 点击登录按钮
    cy.get('button[type="submit"]').click();

    // 验证错误信息显示
    cy.contains('邮箱或密码错误');
  });
});
```

### 运行测试

```bash
# 运行Cypress测试
npx cypress run

# 打开Cypress界面
npx cypress open
```

## 性能测试

### 测试工具

- **Locust**: Python编写的负载测试工具
- **JMeter**: Apache的负载测试工具
- **Gatling**: Scala编写的性能测试工具

### 测试场景

- **并发用户**: 模拟多个用户同时访问
- **响应时间**: 测试系统响应速度
- **吞吐量**: 测试系统处理能力
- **资源使用**: 测试系统资源消耗

### 测试示例

```python
# locustfile.py
from locust import HttpUser, task, between

class UserBehavior(HttpUser):
    wait_time = between(1, 5)

    @task
    def login(self):
        self.client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "password123"
        })

    @task
    def get_users(self):
        response = self.client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "password123"
        })
        token = response.json()["access_token"]
        self.client.get("/api/users", headers={
            "Authorization": f"Bearer {token}"
        })

    @task
    def create_chat(self):
        response = self.client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "password123"
        })
        token = response.json()["access_token"]
        self.client.post("/api/chats", json={
            "name": "测试对话"
        }, headers={
            "Authorization": f"Bearer {token}"
        })
```

### 运行测试

```bash
# 启动Locust
locust -f locustfile.py --host http://localhost:8000

# 访问 http://localhost:8089 开始测试
```

## 安全测试

### 测试工具

- **OWASP ZAP**: 开源安全测试工具
- **Burp Suite**: 专业安全测试工具
- **SonarQube**: 代码安全分析工具

### 测试内容

- **SQL注入**: 测试数据库注入漏洞
- **XSS攻击**: 测试跨站脚本漏洞
- **CSRF攻击**: 测试跨站请求伪造漏洞
- **认证漏洞**: 测试认证机制漏洞
- **授权漏洞**: 测试授权机制漏洞

### 测试示例

```bash
# 使用OWASP ZAP进行安全扫描
zap-cli quick-scan --self-contained --start-options "-config api.disablekey=true" http://localhost:8000
```

## 测试数据管理

### 测试数据工厂

- **Python**: factory_boy
- **TypeScript**: faker.js

### 数据清理

- **测试前**: 清理测试数据
- **测试后**: 清理测试数据
- **事务回滚**: 使用事务回滚确保数据干净

### 示例

```python
# factories.py
import factory
from models.user import User

class UserFactory(factory.Factory):
    class Meta:
        model = User

    name = factory.Faker('name')
    email = factory.Faker('email')
    password = factory.Faker('password')

# 测试中使用
def test_user_creation():
    user = UserFactory()
    assert user.name
    assert user.email
    assert user.password
```

## 测试最佳实践

### 测试设计

- **测试单一职责**: 每个测试只测试一个功能
- **测试边界情况**: 测试边界值和异常情况
- **测试隔离**: 测试之间相互独立
- **测试可读性**: 测试代码清晰易懂

### 测试执行

- **自动化测试**: 集成到CI/CD流程
- **定期运行**: 定期运行所有测试
- **并行测试**: 并行运行测试提高速度
- **测试报告**: 生成详细的测试报告

### 测试维护

- **测试更新**: 代码变更时更新测试
- **测试覆盖**: 确保新代码有测试覆盖
- **测试重构**: 定期重构测试代码
- **测试文档**: 维护测试文档

## CI/CD集成

### GitHub Actions

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Run tests
        run: pytest --cov=services --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### GitLab CI

```yaml
# .gitlab-ci.yml
test:
  stage: test
  script:
    - pip install -r requirements.txt
    - pip install -r requirements-test.txt
    - pytest --cov=services
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
```

## 测试工具推荐

### Python测试工具

- **pytest**: 测试框架
- **factory_boy**: 测试数据工厂
- **pytest-mock**: 模拟库
- **pytest-cov**: 测试覆盖率
- **fastapi.testclient**: FastAPI测试客户端

### TypeScript测试工具

- **Jest**: 测试框架
- **Vitest**: 快速测试框架
- **Cypress**: 端到端测试
- **Playwright**: 浏览器测试
- **MSW**: API模拟

### 性能测试工具

- **Locust**: 负载测试
- **JMeter**: 性能测试
- **Gatling**: 性能测试

### 安全测试工具

- **OWASP ZAP**: 安全扫描
- **SonarQube**: 代码分析
- **Bandit**: Python安全分析
- **ESLint**: TypeScript安全分析

## 常见问题

### 测试运行缓慢

- **原因**: 数据库操作、网络请求等
- **解决方法**: 使用模拟、缓存、并行测试

### 测试不稳定

- **原因**: 测试依赖外部资源、测试顺序等
- **解决方法**: 测试隔离、使用固定数据、重试机制

### 测试覆盖不足

- **原因**: 测试编写不全面
- **解决方法**: 代码审查、测试覆盖分析、TDD

### 测试维护困难

- **原因**: 测试代码质量差、测试耦合度高
- **解决方法**: 测试重构、测试抽象、测试工具

## 测试资源

### 学习资源

- **Python测试**: pytest文档、《Python测试驱动开发》
- **TypeScript测试**: Jest文档、Cypress文档
- **性能测试**: Locust文档、JMeter文档
- **安全测试**: OWASP文档、《Web应用安全权威指南》

### 工具文档

- [pytest文档](https://docs.pytest.org/)
- [Jest文档](https://jestjs.io/docs/getting-started)
- [Cypress文档](https://docs.cypress.io/)
- [Locust文档](https://docs.locust.io/)
- [OWASP ZAP文档](https://www.zaproxy.org/docs/)