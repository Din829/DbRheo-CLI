"""
DatabaseConnectTool - 让Agent自主连接数据库的工具
支持连接字符串、配置字典等多种方式
设计原则：最大灵活性，让Agent像人一样连接数据库
"""

from typing import Optional, Dict, Any
from .base import DatabaseTool
from ..types.tool_types import ToolResult
from ..types.core_types import AbortSignal
from ..config.base import DatabaseConfig
from ..adapters.adapter_factory import get_adapter, list_supported_databases
from ..adapters.connection_string import ConnectionStringParser


class DatabaseConnectTool(DatabaseTool):
    """
    数据库连接工具
    让Agent能够：
    1. 使用连接字符串连接新数据库
    2. 切换已配置的数据库连接
    3. 测试连接可用性
    4. 查看支持的数据库类型
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        
        super().__init__(
            name="database_connect",
            display_name=self._('db_connect_tool_name', default="数据库连接器") if i18n else "数据库连接器",
            description=(
                "Connect to databases using connection strings or switch between configured databases. "
                "Supports: mysql://user:pass@host/db, postgresql://user:pass@host/db, sqlite:///path/to/db. "
                "Can also test connections and list available database types. "
                "The tool auto-detects database type and handles missing drivers gracefully."
            ),
            parameter_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["connect", "test", "list", "switch"],
                        "description": "Action to perform: connect (new connection), test (test connection), list (list supported types), switch (change active connection)",
                        "default": "connect"
                    },
                    "connection_string": {
                        "type": "string",
                        "description": "Database connection string (for connect/test actions). Examples: mysql://root:pass@localhost/mydb, postgresql://user:pass@host:5432/db"
                    },
                    "alias": {
                        "type": "string",
                        "description": "Optional alias name for this connection (for easy reference)"
                    },
                    "database_name": {
                        "type": "string",
                        "description": "Database name to switch to (for switch action)"
                    }
                },
                "required": ["action"]
            },
            is_output_markdown=True,
            can_update_output=True,
            i18n=i18n  # 传递i18n给基类
        )
        self.config = config
        # 存储活跃连接
        self._active_connections: Dict[str, Any] = {}
        self._current_connection: Optional[str] = None
        
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        action = params.get("action", "connect")
        
        if action in ["connect", "test"]:
            if not params.get("connection_string"):
                return self._('db_connect_need_connection_string', default="connect和test操作需要提供connection_string")
        elif action == "switch":
            if not params.get("database_name"):
                return self._('db_connect_need_database_name', default="switch操作需要提供database_name")
                
        return None
        
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        action = params.get("action", "connect")
        
        if action == "connect":
            cs = params.get("connection_string", "")
            # 隐藏密码
            if "://" in cs and "@" in cs:
                parts = cs.split("://", 1)
                if "@" in parts[1]:
                    auth_part, rest = parts[1].split("@", 1)
                    if ":" in auth_part:
                        user = auth_part.split(":", 1)[0]
                        cs = f"{parts[0]}://{user}:****@{rest}"
            return self._('db_connect_action_connect', default="连接到数据库: {cs}", cs=cs)
        elif action == "test":
            return self._('db_connect_action_test', default="测试数据库连接")
        elif action == "list":
            return self._('db_connect_action_list', default="列出支持的数据库类型")
        elif action == "switch":
            db_name = params.get('database_name', '')
            return self._('db_connect_action_switch', default="切换到数据库: {database_name}", database_name=db_name)
        
        return self._('db_connect_action_default', default="数据库操作")
        
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> bool:
        """
        数据库连接工具不需要确认
        - test和list操作是只读的
        - connect操作已经需要明确的连接字符串
        - switch只是切换已有连接
        """
        return False
        
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """执行数据库连接操作"""
        action = params.get("action", "connect")
        
        if action == "list":
            return await self._list_databases(update_output)
        elif action == "test":
            return await self._test_connection(params, update_output)
        elif action == "connect":
            return await self._connect_database(params, update_output)
        elif action == "switch":
            return await self._switch_database(params, update_output)
        else:
            return ToolResult(
                error=self._('db_connect_unknown_action', default="未知操作: {action}", action=action),
                summary=self._('db_connect_operation_failed', default="操作失败")
            )
    
    async def _list_databases(self, update_output: Optional[Any]) -> ToolResult:
        """列出支持的数据库类型"""
        if update_output:
            update_output(self._('db_connect_checking_types', default="🔍 Checking supported database types..."))
        
        supported = list_supported_databases()
        
        # 格式化输出
        display_lines = [f"## {self._('db_supported_types')}\n"]
        
        # 分类显示
        ready_dbs = []
        need_driver_dbs = []
        
        for db_type, info in supported.items():
            if info['driver_available']:
                ready_dbs.append(self._('db_connect_driver_ready', default="✅ **{type}** - Driver installed, ready to use", type=db_type))
            else:
                need_driver_dbs.append(f"⚠️ **{db_type}** - {info['message']}")
        
        if ready_dbs:
            display_lines.append(f"### {self._('db_available')}")
            display_lines.extend(ready_dbs)
            display_lines.append("")
        
        if need_driver_dbs:
            display_lines.append(f"### {self._('db_need_driver')}")
            display_lines.extend(need_driver_dbs)
            display_lines.append("")
        
        # 添加连接示例
        display_lines.extend([
            f"### {self._('db_connection_examples')}",
            "```",
            "# MySQL/MariaDB",
            "mysql://username:password@localhost:3306/database",
            "",
            "# PostgreSQL", 
            "postgresql://username:password@localhost:5432/database",
            "",
            "# SQLite",
            "sqlite:///path/to/database.db",
            "sqlite:///:memory:  # 内存数据库",
            "",
            "# SQL Server",
            "mssql://username:password@server:1433/database",
            "",
            "# Oracle",
            "oracle://username:password@host:1521/service",
            "```"
        ])
        
        display_text = "\n".join(display_lines)
        
        # 构建Agent友好的结构化信息
        llm_content = {
            "supported_databases": supported,
            "ready_to_use": [db for db, info in supported.items() if info['driver_available']],
            "need_driver": [db for db, info in supported.items() if not info['driver_available']],
            "examples": {
                "mysql": "mysql://user:pass@host:3306/db",
                "postgresql": "postgresql://user:pass@host:5432/db",
                "sqlite": "sqlite:///file.db or sqlite:///:memory:"
            }
        }
        
        return ToolResult(
            summary=self._('db_connect_found_types', default="Found {count} available database types", count=len(ready_dbs)),
            llm_content=llm_content,
            return_display=display_text
        )
    
    async def _test_connection(self, params: Dict[str, Any], update_output: Optional[Any]) -> ToolResult:
        """测试数据库连接"""
        connection_string = params.get("connection_string", "")
        
        if update_output:
            update_output(self._('db_connect_testing', default="🔌 Testing database connection..."))
        
        try:
            # 解析连接字符串
            parser = ConnectionStringParser()
            conn_config = parser.parse(connection_string)
            db_type = conn_config.get('type', 'unknown')
            
            if update_output:
                update_output(self._('db_connect_detected_type', default="📊 Detected database type: {type}", type=db_type))
            
            # 尝试创建适配器
            adapter = await get_adapter(connection_string)
            
            # 尝试连接
            await adapter.connect()
            
            # 执行健康检查
            if hasattr(adapter, 'health_check'):
                health = await adapter.health_check()
            else:
                # 简单的连接测试
                await adapter.execute_query("SELECT 1")
                health = True
            
            # 获取版本信息
            version = None
            if hasattr(adapter, 'get_version'):
                version = await adapter.get_version()
            
            # 断开连接
            await adapter.disconnect()
            
            display_text = f"""✅ {self._('db_test_success')}

**{self._('db_connect_type')}**: {db_type}
**{self._('db_connect_host')}**: {conn_config.get('host', 'localhost')}
**{self._('db_connect_port')}**: {conn_config.get('port', 'default')}
**{self._('db_connect_database')}**: {conn_config.get('database', 'N/A')}
**{self._('db_connect_version')}**: {version or self._('db_connect_unknown_version', default='未知')}
"""
            
            return ToolResult(
                summary=self._('db_connect_test_success_summary', default="Connection test successful"),
                llm_content={
                    "success": True,
                    "db_type": db_type,
                    "version": version,
                    "connection_info": conn_config
                },
                return_display=display_text
            )
            
        except Exception as e:
            error_msg = str(e)
            
            # 提供有用的错误提示
            display_text = f"""❌ {self._('db_test_failed')}

**{self._('db_connect_error_info', default='错误信息')}**: {error_msg}

**{self._('db_connect_possible_reasons', default='可能的原因')}**:
1. {self._('db_connect_reason_service_not_started', default='数据库服务未启动')}
2. {self._('db_connect_reason_wrong_params', default='连接参数错误（主机、端口、用户名、密码）')}
3. {self._('db_connect_reason_network_issue', default='网络连接问题')}
4. {self._('db_connect_reason_driver_not_installed', default='数据库驱动未安装')}

**{self._('db_connect_suggestions', default='建议')}**:
- {self._('db_connect_suggestion_check_service', default='检查数据库服务状态')}
- {self._('db_connect_suggestion_verify_string', default='验证连接字符串格式')}
- {self._('db_connect_suggestion_check_firewall', default='确认防火墙设置')}
- {self._('db_connect_suggestion_list_drivers', default="使用 action='list' 查看需要安装的驱动")}
"""
            
            return ToolResult(
                error=error_msg,
                summary=self._('db_connect_test_failed_summary', default="Connection test failed"),
                return_display=display_text
            )
    
    async def _connect_database(self, params: Dict[str, Any], update_output: Optional[Any]) -> ToolResult:
        """连接到新数据库"""
        connection_string = params.get("connection_string", "")
        alias = params.get("alias")
        
        if update_output:
            update_output(self._('db_connect_connecting', default="🔗 Connecting to database..."))
        
        try:
            # 解析连接字符串
            parser = ConnectionStringParser()
            conn_config = parser.parse(connection_string)
            db_type = conn_config.get('type', 'unknown')
            
            # 创建适配器
            adapter = await get_adapter(connection_string)
            
            # 连接数据库
            await adapter.connect()
            
            # 获取数据库信息
            version = None
            if hasattr(adapter, 'get_version'):
                version = await adapter.get_version()
            
            # 生成连接标识
            if not alias:
                # 自动生成别名
                host = conn_config.get('host', 'localhost')
                db = conn_config.get('database', 'default')
                alias = f"{db_type}_{host}_{db}"
            
            # 保存连接
            self._active_connections[alias] = {
                'adapter': adapter,
                'config': conn_config,
                'connection_string': connection_string,
                'version': version
            }
            
            # 设置为当前连接
            self._current_connection = alias
            
            # 注册到adapter_factory，让其他工具可以使用
            from ..adapters.adapter_factory import register_active_connection
            register_active_connection(alias, adapter)
            
            # 更新配置，让其他工具可以使用这个连接
            # 注意：DatabaseConfig可能没有set方法，需要灵活处理
            if hasattr(self.config, 'set'):
                self.config.set(f"databases.{alias}", conn_config)
                self.config.set("default_database", alias)
            else:
                # 直接设置属性或使用其他方式
                # 为了保持灵活性，我们将连接信息存储在内部
                # 其他工具可以通过database参数使用别名
                pass
            
            display_text = f"""✅ {self._('db_connect_success')}

**{self._('db_connect_alias')}**: {alias}
**{self._('db_connect_type')}**: {db_type}
**{self._('db_connect_version')}**: {version or self._('db_connect_unknown_version', default='未知')}
**{self._('db_connect_status')}**: {self._('db_connect_active')}

{self._('db_connect_important_note', default="重要：使用SQL工具时，请在database参数中使用别名 '{alias}'", alias=alias)}
{self._('db_connect_example_usage', default='示例: sql_execute(sql="SELECT * FROM users", database="{alias}")', alias=alias)}
"""
            
            # 尝试获取基本的schema信息
            try:
                schema_info = await adapter.get_schema_info()
                if schema_info.get('success'):
                    schema = schema_info['schema']
                    display_text += "\n" + self._('db_connect_overview', default="**Database Overview**:") + "\n"
                    display_text += f"- {self._('db_connect_table_count_label', default='表数量')}: {schema.get('total_tables', 0)}\n"
                    display_text += f"- {self._('db_connect_view_count_label', default='视图数量')}: {schema.get('total_views', 0)}\n"
                    if 'size_mb' in schema:
                        display_text += f"- {self._('db_connect_size_label', default='数据库大小')}: {schema['size_mb']:.2f} MB\n"
            except:
                pass
            
            return ToolResult(
                summary=self._('db_connect_already_connected', default='已连接到{db_type}数据库', db_type=db_type),
                llm_content={
                    "success": True,
                    "alias": alias,
                    "db_type": db_type,
                    "version": version,
                    "is_active": True,
                    "connection_info": conn_config
                },
                return_display=display_text
            )
            
        except Exception as e:
            return ToolResult(
                error=str(e),
                summary=self._('db_connect_failed', default='连接失败'),
                return_display=f"❌ {self._('db_connect_failed_error', default='连接失败: {error}', error=str(e))}"
            )
    
    async def _switch_database(self, params: Dict[str, Any], update_output: Optional[Any]) -> ToolResult:
        """切换活动数据库连接"""
        database_name = params.get("database_name", "")
        
        # 检查是否是已保存的连接
        if database_name in self._active_connections:
            self._current_connection = database_name
            # 灵活处理配置更新
            if hasattr(self.config, 'set'):
                self.config.set("default_database", database_name)
            
            conn_info = self._active_connections[database_name]
            return ToolResult(
                summary=self._('db_connect_switched_to_conn', default="Switched to connection: {name}", name=database_name),
                llm_content={
                    "success": True,
                    "active_connection": database_name,
                    "db_type": conn_info['config'].get('type')
                },
                return_display=self._('db_connect_switched_to_conn_display', default="✅ Switched to database connection: {name}", name=database_name)
            )
        
        # 检查是否是配置中的数据库
        db_config = self.config.get(f"databases.{database_name}")
        if db_config:
            if hasattr(self.config, 'set'):
                self.config.set("default_database", database_name)
            return ToolResult(
                summary=self._('db_connect_switched_to_config', default="Switched to configured database: {name}", name=database_name),
                return_display=self._('db_connect_switched_to_db_display', default="✅ Switched to database: {name}", name=database_name)
            )
        
        # 列出可用的连接
        available = list(self._active_connections.keys())
        configured = []
        
        # 查找配置中的数据库
        for key in ['databases', 'database']:
            databases = self.config.get(key, {})
            if isinstance(databases, dict):
                configured.extend(databases.keys())
        
        display_text = self._('db_connect_not_found_header', default="❌ Database connection not found: {name}", name=database_name) + "\n"
        
        display_text += f"""
{self._('db_connect_active_connections', default="**Active connections**:")}
{chr(10).join([f"- {name}" for name in available]) if available else self._('db_connect_no_connections', default='无')}

**{self._('db_connect_configured_databases', default='配置的数据库')}**:
{chr(10).join([f"- {name}" for name in configured]) if configured else self._('db_connect_no_connections', default='无')}
"""
        
        return ToolResult(
            error=self._('db_connect_not_found_error', default="Database connection not found: {name}", name=database_name),
            summary=self._('db_connect_switch_failed', default='切换失败'),
            return_display=display_text
        )
    
    async def _list_active_connections(self, update_output: Optional[Any]) -> ToolResult:
        """列出所有活动连接"""
        # 获取本地保存的连接
        local_connections = list(self._active_connections.keys())
        
        # 获取全局注册的连接
        try:
            from ..adapters.adapter_factory import _active_connections as global_connections
            if global_connections is not None:
                global_aliases = list(global_connections.keys())
            else:
                global_aliases = []
        except (ImportError, AttributeError):
            global_aliases = []
        
        display_text = f"📋 **{self._('db_connect_active_db_connections', default='活动数据库连接')}**\n\n"
        
        if local_connections:
            display_text += f"{self._('db_connect_local_connections', default='本地连接')}：\n"
            for alias in local_connections:
                conn_info = self._active_connections[alias]
                display_text += f"- **{alias}**: {conn_info['config'].get('type')} @ {conn_info['config'].get('host')}\n"
        
        if global_aliases:
            display_text += f"\n{self._('db_connect_global_connections', default='全局注册连接')}：\n"
            for alias in global_aliases:
                display_text += f"- {alias}\n"
        
        if not local_connections and not global_aliases:
            display_text += f"{self._('db_connect_no_active_connections', default='没有活动的数据库连接')}\n"
            display_text += f"\n{self._('db_connect_use_connect_hint', default="使用 action='connect' 创建新连接")}"
        
        return ToolResult(
            summary=self._('db_connect_found_connections', default="Found {count} active connections", count=len(set(local_connections + global_aliases))),
            llm_content={
                "local_connections": local_connections,
                "global_connections": global_aliases,
                "current_connection": self._current_connection
            },
            return_display=display_text
        )