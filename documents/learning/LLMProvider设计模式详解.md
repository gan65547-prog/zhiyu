# Provider 抽象类设计详解

## 一、核心设计模式：模板方法 + 策略模式 + 工厂模式

### 1. 数据类 ChatMessage 和 ChatResponse

```python
@dataclass
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}
```

等价 C++ 实现：

```cpp
struct ChatMessage {
    std::string role;
    std::string content;

    nlohmann::json to_dict() const {
        return {{"role", role}, {"content", content}};
    }
};
```

### 2. 抽象基类 LLMProvider

```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages, stream=True, **kwargs):
        raise NotImplementedError

    @abstractmethod
    async def validate_connection(self) -> bool:
        raise NotImplementedError
```

等价 C++ 实现：

```cpp
class ILLMProvider {
public:
    virtual ~ILLMProvider() = default;
    virtual Task<ChatResponse> chat(
        std::span<const ChatMessage> messages,
        bool stream = true
    ) = 0;
    virtual Task<bool> validate_connection() = 0;
};
```

### 3. 具体实现 OllamaProvider

```python
class OllamaProvider(LLMProvider):
    def __init__(self, base_url=None, model=None, timeout=None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL

    async def chat(self, messages, stream=True, **kwargs):
        if stream:
            return self._chat_stream(messages)
        else:
            return await self._chat_non_stream(messages)
```

---

## 二、为什么要这么设计？

| 设计目的 | 好处 | C++ 对应实现 |
|---------|------|-------------|
| 开闭原则 | 新增 LLM 提供者只需添加新类，不改现有代码 | 策略模式：用基类指针指向子类对象 |
| 依赖倒置 | 高层模块依赖抽象，不依赖具体实现 | 接口抽象：业务代码只依赖 `LLMProvider*` |
| 统一接口 | 调用方只调用 `chat()`，不关心是 Ollama 还是 OpenAI | 多态：所有提供者有相同接口 |
| 流式响应 | `AsyncIterator` 支持打字机效果，无需等待完整回答 | C++20 `co_await` + `std::generator` |

---

## 三、设计模式类比

```
                    ┌─────────────────┐
                    │  LLMProvider    │
                    │  (ABC)          │
                    ├─────────────────┤
                    │ + chat()        │
                    │ + validate()    │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ OllamaProvider  │ │ VLLMProvider    │ │ OpenAIProvider  │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ + chat()        │ │ + chat()        │ │ + chat()        │
│ - /api/chat     │ │ - /v1/chat/    │ │ - /chat/       │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## 四、C++ 对比实现

```cpp
// ========== 1. 数据结构 ==========
struct ChatMessage {
    std::string role;
    std::string content;

    nlohmann::json to_json() const {
        return {{"role", role}, {"content", content}};
    }
};

struct ChatResponse {
    std::string content;
    std::string model;
    std::optional<std::unordered_map<std::string, int>> usage;
};

// ========== 2. 抽象基类 ==========
class ILLMProvider {
public:
    virtual ~ILLMProvider() = default;
    virtual Task<ChatResponse> chat(
        std::span<const ChatMessage> messages,
        bool stream = true
    ) = 0;
    virtual Task<bool> validate_connection() = 0;
};

// ========== 3. Ollama 实现 ==========
class OllamaProvider : public ILLMProvider {
    std::string base_url_;
    std::string model_;
    int timeout_;

public:
    OllamaProvider(const std::string& base_url,
                   const std::string& model,
                   int timeout)
        : base_url_(base_url), model_(model), timeout_(timeout) {}

    Task<ChatResponse> chat(
        std::span<const ChatMessage> messages,
        bool stream = true
    ) override {
        nlohmann::json payload = {
            {"model", model_},
            {"messages", messages | std::views::transform(&ChatMessage::to_json)}
        };
        co_return response;
    }
};

// ========== 4. 工厂 ==========
enum class LLMType { Ollama, VLLM, OpenAI };

class LLMProviderFactory {
public:
    static std::unique_ptr<ILLMProvider> create(LLMType type) {
        switch (type) {
            case LLMType::Ollama:   return std::make_unique<OllamaProvider>(...);
            case LLMType::VLLM:     return std::make_unique<VLLMProvider>(...);
            case LLMType::OpenAI:   return std::make_unique<OpenAIProvider>(...);
        }
    }
};
```

---

## 五、其他设计方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| 当前设计（继承+抽象基类） | 接口统一、扩展性好 | 需要继承 | 多 LLM 提供者、需要灵活切换 |
| 策略模式（注入函数指针） | 更轻量、无继承开销 | 难以扩展方法 | LLM 种类固定、追求性能 |
| Protocol（Go/Rust 风格） | 无继承约束、更灵活 | 需要手动实现多态 | 动态语言、duck typing |

---

## 六、async def 详解（重点）

### 6.1 什么是 async/await？

`async def` 是 Python 的**协程**语法，用于编写**异步代码**。等价于 C++20 的 `co_await` / `co_return`。

### 6.2 对比：同步 vs 异步

**同步写法（阻塞）：**
```python
def get_data():
    result = requests.get("https://api.example.com/data")  # 阻塞等待
    return result.json()
```

**异步写法（非阻塞）：**
```python
async def get_data():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.example.com/data") as resp:  # 非阻塞
            return await resp.json()
```

### 6.3 C++ 对比

```cpp
// 同步：阻塞等待
ChatResponse get_data() {
    auto response = http_client.get("https://api.example.com/data"); // 阻塞
    return response;
}

// 异步：C++20 coroutine
Task<ChatResponse> get_data() {
    auto response = co_await http_client.async_get("https://api.example.com/data"); // 非阻塞
    co_return response;
}
```

### 6.4 async def 的三种返回值

```python
# 1. 普通 async 函数（返回 None）
async def simple():
    await asyncio.sleep(1)
    print("done")

# 2. 返回完整结果（用 await 调用）
async def get_result():
    result = await some_async_function()
    return result

# 3. 返回生成器（流式，用 async for 迭代）
async def stream_response():
    for i in range(10):
        yield f"chunk {i}"  # 每次 yield 一个数据块
        await asyncio.sleep(0.1)
```

### 6.5 流式响应示例

项目中的流式响应：

```python
async def _chat_stream(self, messages):
    """流式返回，每次收到 LLM 的一个 token 就 yield"""
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            async for line in resp.content:  # 遍历每个数据块
                data = json.loads(line)
                yield data["message"]["content"]  # yield 出去
```

调用方：

```python
async def main():
    provider = OllamaProvider()
    async for chunk in provider.chat(messages, stream=True):
        print(chunk, end="", flush=True)  # 实时打印，类似打字机效果
```

### 6.6 关键 Python 语法对照

| Python 语法 | C++ 等价 | 说明 |
|------------|---------|------|
| `async def f()` | `Task<T> f()` | 异步函数/coroutine |
| `await x` | `co_await x` | 等待异步操作完成 |
| `yield` | `co_yield` | 暂停函数，返回值 |
| `async for` | `for co_await` | 遍历异步生成器 |
| `AsyncIterator[T]` | `std::generator<T>` | 异步生成器 |

### 6.7 为什么用 async？

| 场景 | 同步 | 异步 |
|------|------|------|
| 等待 HTTP 响应 | 阻塞，CPU 空闲 | 不阻塞，可并发处理多个请求 |
| LLM 流式输出 | 需等全部返回才能显示 | 实时显示，提升用户体验 |
| 数据库查询 | 排队等待 | 并发处理多个查询 |
| 文件 I/O | 阻塞 | 不阻塞 |

---

### 6.8 协程（Coroutine）概念详解

#### 6.8.1 协程 vs 线程

**线程**是内核态的，由操作系统调度；**协程**是用户态的，由用户代码自己调度：

| | 线程 Thread | 协程 Coroutine |
|--|-----------|---------------|
| 调度者 | 操作系统内核 | 用户代码（事件循环） |
| 栈空间 | KB 级 | 更小，可定制 |
| 切换成本 | 约 1000-10000 CPU 周期 | 约 10-100 CPU 周期 |
| 阻塞影响 | 阻塞线程会导致内核重新调度 | 协程自己选择何时让出 |

#### 6.8.2 事件循环（Event Loop）机制

Python 的 async 不是真正的并行，而是**协作式多任务**：

```python
import asyncio

async def task1():
    print("1. task1 开始")
    await asyncio.sleep(1)  # 让出控制权！
    print("3. task1 继续完成")

async def task2():
    print("2. task2 开始")
    await asyncio.sleep(0.5)  # 让出控制权！
    print("4. task2 完成")

async def main():
    await asyncio.gather(task1(), task2())

asyncio.run(main())
```

**输出：**
```
1. task1 开始
2. task2 开始       ← task1 在 await 时让出，task2 开始执行
3. task1 继续完成   ← task2 在 await 时让出，task1 恢复执行
4. task2 完成
```

**底层原理图解：**

```
┌─────────────────────────────────────────────────────────┐
│                    Event Loop (单线程)                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐            │
│   │ Task 1 │    │ Task 2 │    │ Task 3 │   ← 用户代码  │
│   │ await  │───▶│ await  │───▶│ await  │             │
│   │ 让出   │    │ 让出   │    │ 让出   │             │
│   └────┬────┘    └────┬────┘    └────┬────┘            │
│        │               │               │                 │
│        └───────────────┴───────────────┘                 │
│                        │                                  │
│                        ▼                                  │
│              ┌─────────────────┐                        │
│              │  I/O 等待队列    │  ← 不占用 CPU          │
│              │  (sleep/网络等) │                        │
│              └─────────────────┘                        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

#### 6.8.3 await 关键字的三件事

```python
async def example():
    # await 的三件事：

    # 1. 暂停当前协程（让出 CPU 给其他协程执行）
    result = await some_async_function()

    # 2. 等待 some_async_function() 完成
    #    （此时不占用 CPU，事件循环去执行其他协程）

    # 3. 完成后恢复当前协程，继续执行
    print(result)
```

#### 6.8.4 C++ 回调模式 vs Python async 模式

**C++ 回调模式：**
```cpp
void do_async_work(std::function<void(int)> callback) {
    std::thread([callback]() {
        std::this_thread::sleep_for(1s);
        callback(42);  // 回调通知结果
    }).detach();
}

int main() {
    do_async_work([](int result) {
        std::cout << "收到结果: " << result << "\n";
    });
    std::cout << "主线程继续做事\n";  // 不阻塞
}
```

**回调地狱示例：**
```cpp
// 嵌套多了难以阅读
fetch_user([](User user) {
    fetch_orders(user.id, [](Orders orders) {
        fetch_products(orders.product_ids, [](Products products) {
            // 嵌套越来越深...
        });
    });
});
```

**Python async 模式：**
```python
# 看起来像同步代码，实际上是异步的
async def main():
    result = await do_async_work()  # 不阻塞！
    print("收到结果:", result)

async def business_logic():
    user = await fetch_user()
    orders = await fetch_orders(user.id)
    products = await fetch_products(orders.product_ids)
    # 顺序书写，无需嵌套
```

#### 6.8.5 Python vs C++ 异步对比

| | C++ (回调) | C++ (future/promise) | Python (async await) |
|--|-----------|---------------------|---------------------|
| 模型 | 回调 | `std::future` | `await` |
| 代码风格 | 嵌套回调 | `get()` 阻塞或 `.then()` | 顺序书写，看起来像同步 |
| 线程 | 可多线程 | 可多线程 | **单线程事件循环** |
| CPU 占用 | 取决于实现 | 取决于实现 | 等待 I/O 时几乎 0% |

#### 6.8.6 为什么 LLM 流式输出适合用 async？

```python
# 传统同步：等全部结果返回才能显示
def chat_sync():
    response = requests.post(url)  # 等 10 秒...
    return response.text           # 一次性显示

# async：边收边显示
async def chat_stream():
    async for chunk in stream_response():  # 每收到一个 token
        print(chunk, end="", flush=True)   # 立刻显示
        # 这期间事件循环可以处理其他请求！
```

#### 6.8.7 快速理解比喻

```python
# await = "我去排队等饭，你先吃"
# 不用站在窗口傻等，去做别的事，饭好了叫我

async def eat_restaurant():
    print("1. 去餐厅点菜")
    food = await kitchen.cook()  # 厨房去做，我让出位置
    print("5. 饭好了，开始吃")

async def work_at_desk():
    print("2. 回工位写代码")
    print("3. 继续写代码")
    print("4. 收到通知：饭好了")
```

事件循环调度：1 → 2 → 3 → 4 → 5（非阻塞交替执行）

---

## 七、关键 Python 语法解释

```python
**kwargs           # 可变关键字参数，类似 std::map<std::string, variant>
List[ChatMessage] # 类型注解，类似 C++ 的 std::vector<ChatMessage>
@dataclass        # 数据类，自动生成 __init__, __repr__, __eq__ 等方法
@abstractmethod    # 装饰器，标记子类必须实现的方法
```
