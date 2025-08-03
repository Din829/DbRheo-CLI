# DbRheo CLI 项目架构文档

## 项目概述

DbRheo CLI 是一个基于 Gemini CLI 架构的智能数据库分析代理系统，采用现代化的多包架构设计，支持自然语言数据库操作、智能SQL生成、schema探索和风险评估。

### 核心特性

- **智能Agent架构**: 基于Google Gemini API的对话式数据库操作
- **多数据库支持**: PostgreSQL、MySQL、SQLite等主流数据库
- **安全风险评估**: 内置危险操作检测和确认机制
- **工具生态系统**: 可扩展的工具注册表和能力映射
- **多界面支持**: CLI、Web界面和API服务
- **配置分层**: System > Workspace > User的配置优先级

## 技术栈

### 后端核心
- **Python 3.9+**: 主要开发语言
- **FastAPI**: Web API框架
- **SQLAlchemy 2.0**: 异步ORM和数据库抽象
- **Google Generative AI**: Gemini API集成
- **Rich**: 终端界面渲染
- **OpenTelemetry**: 监控和遥测

### 前端界面
- **React 19**: 现代化前端框架
- **TypeScript**: 类型安全
- **Vite 6.0**: 构建工具
- **Tailwind CSS**: 样式框架
- **Monaco Editor**: 代码编辑器
- **Socket.IO**: 实时通信

### 数据库驱动
- **asyncpg**: PostgreSQL异步驱动
- **aiomysql**: MySQL异步驱动
- **aiosqlite**: SQLite异步驱动

## 项目结构

```
DbRheo_CLI/
├── packages/                           # 多包架构根目录
│   ├── cli/                           # 命令行界面包 (v0.1.0)
│   │   ├── src/
│   │   │   └── dbrheo_cli/
│   │   │       ├── app/               # CLI应用核心
│   │   │       │   ├── cli.py         # 主CLI控制器
│   │   │       │   └── config.py      # CLI配置管理
│   │   │       ├── handlers/          # 事件和输入处理
│   │   │       │   ├── event_handler.py    # 事件调度
│   │   │       │   ├── input_handler.py    # 输入处理和验证
│   │   │       │   └── tool_handler.py     # 工具执行处理
│   │   │       ├── ui/                # 用户界面组件
│   │   │       │   ├── ascii_art.py        # ASCII艺术和Logo
│   │   │       │   ├── console.py          # 控制台抽象
│   │   │       │   ├── layout_manager.py   # 布局管理
│   │   │       │   ├── messages.py         # 消息格式化
│   │   │       │   ├── startup.py          # 启动画面
│   │   │       │   ├── streaming.py        # 流式输出处理
│   │   │       │   └── tools.py            # 工具界面展示
│   │   │       ├── constants.py       # 常量定义
│   │   │       ├── i18n.py           # 国际化支持
│   │   │       └── main.py           # CLI入口点
│   │   └── pyproject.toml            # CLI包配置
│   │
│   ├── core/                         # 核心业务逻辑包 (v1.0.0)
│   │   └── src/
│   │       └── dbrheo/
│   │           ├── adapters/         # 数据库适配器系统
│   │           │   ├── adapter_factory.py      # 适配器工厂
│   │           │   ├── base.py                 # 适配器基类
│   │           │   ├── connection_manager.py   # 连接管理
│   │           │   ├── connection_string.py    # 连接字符串解析
│   │           │   ├── dialect_parser.py       # 方言解析
│   │           │   ├── mysql_adapter.py        # MySQL适配器
│   │           │   ├── postgresql_adapter.py   # PostgreSQL适配器
│   │           │   ├── sqlite_adapter.py       # SQLite适配器
│   │           │   └── transaction_manager.py  # 事务管理
│   │           │
│   │           ├── api/              # FastAPI Web服务
│   │           │   ├── routes/       # API路由
│   │           │   │   ├── chat.py          # 聊天API
│   │           │   │   ├── database.py      # 数据库操作API
│   │           │   │   └── websocket.py     # WebSocket支持
│   │           │   ├── app.py        # FastAPI应用创建
│   │           │   └── dependencies.py      # 依赖注入
│   │           │
│   │           ├── config/           # 配置系统
│   │           │   ├── base.py       # 分层配置管理
│   │           │   └── test_config.py        # 测试配置
│   │           │
│   │           ├── core/             # 核心Agent逻辑
│   │           │   ├── chat.py       # 聊天会话管理
│   │           │   ├── client.py     # 主控制器
│   │           │   ├── compression.py        # 历史压缩
│   │           │   ├── environment.py        # 环境管理
│   │           │   ├── memory.py     # 记忆系统
│   │           │   ├── next_speaker.py       # 下一话者判断
│   │           │   ├── prompts.py    # 提示词管理
│   │           │   ├── scheduler.py  # 工具调度器
│   │           │   └── turn.py       # 对话轮次
│   │           │
│   │           ├── prompts/          # 提示词模板
│   │           │   ├── database_agent_prompt.py     # 数据库代理提示词
│   │           │   ├── optimized_database_prompt.py # 优化提示词
│   │           │   └── safe_response.md             # 安全响应模板
│   │           │
│   │           ├── services/         # AI服务集成
│   │           │   ├── claude_service.py    # Claude API服务
│   │           │   ├── gemini_service.py    # Gemini API服务
│   │           │   ├── llm_factory.py       # LLM工厂
│   │           │   └── openai_service.py    # OpenAI API服务
│   │           │
│   │           ├── telemetry/        # 监控和遥测
│   │           │   ├── logger.py     # 日志系统
│   │           │   ├── metrics.py    # 指标收集
│   │           │   └── tracer.py     # 链路追踪
│   │           │
│   │           ├── tools/            # 工具系统
│   │           │   ├── base.py       # 工具基类
│   │           │   ├── registry.py   # 工具注册表
│   │           │   ├── risk_evaluator.py    # 风险评估器
│   │           │   ├── code_execution_tool.py       # 代码执行
│   │           │   ├── database_connect_tool.py     # 数据库连接
│   │           │   ├── database_export_tool.py      # 数据导出
│   │           │   ├── directory_list_tool.py       # 目录浏览
│   │           │   ├── file_read_tool.py            # 文件读取
│   │           │   ├── file_write_tool.py           # 文件写入
│   │           │   ├── schema_discovery.py          # Schema探索
│   │           │   ├── shell_tool.py                # Shell执行
│   │           │   ├── sql_tool.py                  # SQL执行
│   │           │   ├── table_details_tool.py        # 表详情
│   │           │   ├── web_fetch_tool.py            # 网页获取
│   │           │   └── web_search_tool.py           # 网络搜索
│   │           │
│   │           ├── types/            # 类型定义
│   │           │   ├── core_types.py # 核心类型
│   │           │   ├── file_types.py # 文件类型
│   │           │   └── tool_types.py # 工具类型
│   │           │
│   │           └── utils/            # 工具函数
│   │               ├── debug_logger.py      # 调试日志
│   │               ├── encoding_utils.py    # 编码工具
│   │               ├── errors.py            # 错误处理
│   │               ├── function_response.py # 函数响应处理
│   │               ├── log_integration.py   # 日志集成
│   │               ├── parameter_sanitizer.py      # 参数清理
│   │               ├── realtime_logger.py   # 实时日志
│   │               ├── retry.py             # 重试机制
│   │               ├── retry_with_backoff.py       # 退避重试
│   │               └── type_converter.py    # 类型转换
│   │
│   └── web/                          # Web界面包 (v1.0.0 MVP)
│       ├── src/
│       │   ├── components/           # React组件
│       │   │   ├── chat/             # 聊天组件
│       │   │   │   └── ChatContainer.tsx
│       │   │   └── database/         # 数据库组件
│       │   │       ├── QueryEditor.tsx      # SQL编辑器
│       │   │       └── ResultTable.tsx      # 结果展示
│       │   ├── styles/               # 样式文件
│       │   │   └── global.css
│       │   ├── App.tsx               # 主应用组件
│       │   └── main.tsx              # 应用入口
│       ├── package.json              # 前端依赖配置
│       ├── vite.config.ts            # Vite构建配置
│       └── tailwind.config.js        # Tailwind配置
│
├── testdata/                         # 测试数据
│   ├── adult.data                    # 示例数据集
│   ├── adult.names                   # 数据描述
│   └── adult.test                    # 测试数据
│
├── logs/                             # 日志目录
├── .env.example                      # 环境变量模板
├── log_config.yaml                   # 日志配置
├── pyproject.toml                    # 根项目配置
├── requirements.txt                  # Python依赖
└── README.md                         # 项目说明
```

## 核心架构设计

### 1. 多包架构 (Monorepo)

项目采用多包架构设计，每个包负责特定功能：

#### CLI包 (`packages/cli/`)
- **职责**: 命令行界面和用户交互
- **特点**: Rich终端UI、多行输入、流式输出
- **依赖**: 依赖Core包提供业务逻辑

#### Core包 (`packages/core/`)
- **职责**: 核心业务逻辑和Agent系统
- **特点**: 数据库抽象、AI服务集成、工具系统
- **设计**: 可独立使用，支持API和CLI调用

#### Web包 (`packages/web/`)
- **职责**: Web界面（MVP状态）
- **特点**: React现代化界面、实时通信
- **状态**: 基础架构已实现，功能待完善

### 2. Agent架构 (基于Gemini CLI)

```
用户输入 → CLI/Web界面 → DatabaseClient → Turn系统 → Tool调度 → 数据库操作
    ↑                                                          ↓
结果展示 ← 流式响应处理 ← Gemini API ← 工具执行结果 ← 工具注册表
```

#### 核心组件

1. **DatabaseClient** (`core/client.py`)
   - 主控制器，管理会话和递归逻辑
   - 实现`send_message_stream`方法处理用户消息
   - 支持历史压缩和next_speaker判断

2. **DatabaseTurn** (`core/turn.py`)
   - 单轮对话处理
   - 收集待执行的工具调用
   - 流式响应处理

3. **DatabaseToolScheduler** (`core/scheduler.py`)
   - 工具执行调度器
   - 异步工具执行
   - 风险评估和确认机制

4. **DatabaseChat** (`core/chat.py`)
   - 聊天会话管理
   - 历史记录维护
   - 上下文管理

## 数据库适配器系统

### 适配器工厂模式

```python
# 适配器注册和创建
_adapter_registry: Dict[str, Type[DatabaseAdapter]] = {}

async def get_adapter(config_or_connection_string) -> DatabaseAdapter:
    # 支持多种输入格式：
    # 1. DatabaseConfig对象
    # 2. 连接字符串
    # 3. 配置字典
```

### 支持的数据库

| 数据库 | 驱动 | 适配器类 | 状态 |
|--------|------|----------|------|
| SQLite | aiosqlite | SQLiteAdapter | ✅ 完整支持 |
| PostgreSQL | asyncpg | PostgreSQLAdapter | ✅ 完整支持 |
| MySQL | aiomysql | MySQLAdapter | ✅ 完整支持 |
| MariaDB | aiomysql | MySQLAdapter | ✅ 复用MySQL |

### 连接管理特性

- **连接池**: 异步连接池管理
- **健康检查**: 自动连接验证
- **缓存机制**: 适配器实例缓存
- **活动连接**: 支持命名连接别名
- **事务管理**: 自动事务处理

## 工具系统架构

### 工具注册表 (`tools/registry.py`)

基于能力的智能工具管理系统：

```python
class ToolCapability(Enum):
    QUERY = "query"              # 查询数据
    MODIFY = "modify"            # 修改数据
    SCHEMA_CHANGE = "schema_change"  # 变更表结构
    EXPLORE = "explore"          # 探索数据库
    ANALYZE = "analyze"          # 分析数据
    EXPORT = "export"            # 导出数据
    # ... 更多能力
```

### 核心工具集

| 工具名称 | 能力标签 | 优先级 | 功能描述 |
|---------|----------|--------|----------|
| SQLTool | QUERY, MODIFY, SCHEMA_CHANGE | 90 | SQL执行和查询 |
| SchemaDiscoveryTool | EXPLORE, ANALYZE | 85 | 数据库结构探索 |
| DatabaseConnectTool | EXPLORE | 88 | 数据库连接管理 |
| CodeExecutionTool | ANALYZE, MODIFY | 88 | Python/JS代码执行 |
| DatabaseExportTool | EXPORT, QUERY | 80 | 数据导出 |
| FileReadTool | READ, IMPORT | 75 | 文件读取 |
| FileWriteTool | WRITE, EXPORT | 75 | 文件写入 |
| ShellTool | MODIFY, BACKUP | 85 | 系统Shell执行 |

### 工具能力查询

```python
# 基于能力获取工具
registry.get_tools_by_capability(ToolCapability.QUERY)

# 智能搜索工具
registry.search_tools("数据库", capabilities=[ToolCapability.EXPLORE])

# 多能力匹配
registry.get_tools_by_capabilities([
    ToolCapability.QUERY, 
    ToolCapability.ANALYZE
], match_all=False)
```

## AI服务集成架构

### LLM工厂模式 (`services/llm_factory.py`)

支持多AI服务的统一接口：

```python
def create_llm_service(config: DatabaseConfig):
    model = config.get_model()
    if "gemini" in model.lower():
        return GeminiService(config)
    elif "claude" in model.lower():
        return ClaudeService(config)
    elif "gpt" in model.lower():
        return OpenAIService(config)
```

### 支持的AI服务

#### 1. Gemini Service (`services/gemini_service.py`)
- **模型**: gemini-2.5-flash (默认)
- **特性**: 流式响应、函数调用、JSON模式
- **配置**: 温度0.7、top_p 0.8、max_tokens 8192

#### 2. Claude Service (`services/claude_service.py`)
- **模型**: claude-3.5-sonnet, claude-3-haiku
- **特性**: 高质量推理、长上下文
- **API**: Anthropic API集成

#### 3. OpenAI Service (`services/openai_service.py`)
- **模型**: gpt-4-turbo, gpt-3.5-turbo
- **特性**: 函数调用、流式响应
- **配置**: 可自定义API端点

### 流式响应处理

所有AI服务都支持统一的流式响应格式：

```python
{
    "text": "生成的文本内容",
    "function_calls": [
        {
            "id": "call_123",
            "name": "sql_tool",
            "args": {"query": "SELECT * FROM users"}
        }
    ]
}
```

## 配置系统架构

### 分层配置 (`config/base.py`)

采用优先级配置系统：Environment > System > Workspace > User

```
Environment Variables (最高优先级)
├── GOOGLE_API_KEY
├── DBRHEO_MODEL
├── DBRHEO_DEBUG
└── DATABASE_URL
    ↓
System Config (/etc/dbrheo/config.yaml)
├── 系统级默认配置
└── 管理员策略设置
    ↓
Workspace Config (.dbrheo.yaml)
├── 项目特定配置
└── 团队共享设置
    ↓
User Config (~/.dbrheo/config.yaml)
├── 个人偏好设置
└── 用户级默认值
    ↓
Built-in Defaults (最低优先级)
```

### 环境变量映射

| 环境变量 | 配置键 | 默认值 | 说明 |
|---------|--------|--------|------|
| GOOGLE_API_KEY | google_api_key | - | Gemini API密钥 |
| DBRHEO_MODEL | model | gemini-2.5-flash | AI模型选择 |
| DBRHEO_DEBUG | debug | false | 调试模式 |
| DATABASE_URL | database_url | sqlite:///./default.db | 数据库连接 |
| DBRHEO_MAX_TURNS | max_session_turns | 100 | 最大对话轮次 |

### 配置访问方法

```python
config = DatabaseConfig()

# 基础访问
config.get("model", "gemini-2.5-flash")

# 嵌套键访问
config.get("databases.production.url")

# 便捷方法
config.get_model()
config.is_debug()
config.allows_dangerous_operations()
```

## 类型系统 (`types/`)

### 核心类型定义

完全对齐Gemini CLI的TypeScript类型：

```python
# 内容部分类型
@dataclass
class Part:
    text: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    function_response: Optional[Dict[str, Any]] = None

# 内容类型
@dataclass
class Content:
    role: str  # 'user' | 'model' | 'function'
    parts: List[Part]

# 中止信号
class AbortSignal(ABC):
    @property
    @abstractmethod
    def aborted(self) -> bool: ...
```

### 工具类型系统

```python
# 工具参数类型
ToolParameter = Dict[str, Any]

# 工具响应类型
ToolResponse = Dict[str, Any]

# 工具调用类型
@dataclass
class ToolCall:
    id: str
    name: str
    args: Dict[str, Any]
    status: str  # 'pending' | 'running' | 'completed' | 'error'
```

## 安全和风险评估

### 风险评估器 (`tools/risk_evaluator.py`)

智能风险检测系统：

```python
class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskEvaluator:
    def evaluate_sql(self, query: str) -> RiskAssessment:
        # 检测危险操作：DROP, DELETE, TRUNCATE
        # 分析影响范围和数据量
        # 评估业务风险
```

### 安全特性

1. **操作确认**: 危险操作需要用户确认
2. **权限检查**: 基于配置的权限控制  
3. **审计日志**: 完整的操作记录
4. **连接限制**: 防止未授权数据库访问
5. **参数清理**: SQL注入防护

## 监控和遥测 (`telemetry/`)

### OpenTelemetry集成

```python
# 链路追踪
tracer = trace.get_tracer("dbrheo")

# 指标收集
metrics = Metrics()
metrics.record_query_duration(duration)
metrics.record_tool_execution(tool_name, status)

# 结构化日志
logger = StructuredLogger()
logger.info("database_connected", database=db_name)
```

### 监控指标

- **性能指标**: 查询执行时间、API响应时间
- **使用指标**: 工具调用次数、错误率
- **业务指标**: 成功率、用户满意度
- **系统指标**: 内存使用、连接池状态

## 开发指南

### 环境设置

```bash
# 1. 克隆项目
git clone https://github.com/Din829/DbRheo-CLI.git
cd DbRheo-CLI

# 2. 设置Python环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate    # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 设置 GOOGLE_API_KEY

# 5. 运行CLI
cd packages/cli
python cli.py
```

### 开发模式

```bash
# 安装开发依赖
pip install -e "packages/core[dev]"
pip install -e "packages/cli[dev]"

# 代码质量检查
black packages/
ruff check packages/
mypy packages/

# 运行测试
pytest packages/core/tests/
pytest packages/cli/tests/
```

### 添加新工具

1. **创建工具类**:
```python
class MyTool(DatabaseTool):
    def __init__(self, config: DatabaseConfig):
        super().__init__(
            name="my_tool",
            description="工具描述",
            parameter_schema={...}
        )
    
    async def execute(self, **kwargs) -> ToolResponse:
        # 实现工具逻辑
        pass
```

2. **注册工具**:
```python
# 在registry.py中注册
my_tool = MyTool(config)
registry.register_tool(
    tool=my_tool,
    capabilities={ToolCapability.QUERY},
    tags={"custom", "analysis"},
    priority=70
)
```

### 添加新数据库适配器

1. **实现适配器**:
```python
class NewDBAdapter(DatabaseAdapter):
    async def connect(self): ...
    async def execute_query(self, query): ...
    async def get_schema(self): ...
```

2. **注册适配器**:
```python
# 在adapter_factory.py中
register_adapter('newdb', NewDBAdapter, check_driver)
```

## 部署架构

### 生产部署

```yaml
# docker-compose.yml
version: '3.8'
services:
  dbrheo-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - DATABASE_URL=${DATABASE_URL}
    
  dbrheo-web:
    build: ./packages/web
    ports:
      - "3000:3000"
    depends_on:
      - dbrheo-api
```

### 扩展性考虑

1. **水平扩展**: 无状态设计支持多实例部署
2. **缓存策略**: Redis缓存查询结果和会话状态
3. **负载均衡**: API网关分发请求
4. **监控告警**: Prometheus + Grafana监控体系

## 未来规划

### 短期目标 (Q1-Q2)

1. **Web界面完善**: 实现完整的Web聊天界面
2. **更多数据库**: 支持Oracle、SQL Server、MongoDB
3. **高级分析**: 数据可视化、报表生成
4. **团队协作**: 多用户会话、权限管理

### 长期愿景 (Q3-Q4)

1. **AI模型扩展**: 支持更多开源模型
2. **插件生态**: 第三方工具插件系统
3. **云原生**: Kubernetes部署、微服务架构
4. **企业版**: SSO集成、审计报告、合规性

## 最佳实践

### 代码规范

1. **类型注解**: 所有公共API必须有类型注解
2. **文档字符串**: 重要函数需要详细文档
3. **错误处理**: 使用结构化异常处理
4. **日志记录**: 关键操作必须记录日志

### 性能优化

1. **异步优先**: 所有I/O操作使用async/await
2. **连接复用**: 数据库连接池管理
3. **缓存策略**: 合理使用缓存减少重复计算
4. **流式响应**: 大结果集使用流式处理

### 安全考虑

1. **输入验证**: 所有用户输入必须验证
2. **权限控制**: 基于角色的访问控制
3. **审计日志**: 敏感操作完整记录
4. **加密存储**: API密钥和敏感配置加密

---

## 结语

DbRheo CLI项目采用现代化的架构设计，充分利用了AI技术的优势，为数据库操作和分析提供了智能化的解决方案。通过模块化的设计和可扩展的架构，项目能够适应不断变化的需求，为用户提供优秀的使用体验。

项目的成功离不开完善的架构设计和严格的开发规范。希望这份文档能够帮助开发者更好地理解项目结构，参与到项目的开发和维护中来。

---

*最后更新: 2025-08-02*  
*文档版本: v1.0.0*  
*项目版本: CLI v0.1.0, Core v1.0.0, Web v1.0.0*