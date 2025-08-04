"""
DatabaseConnectTool - 让Agent自主连接数据库的工具
支持连接字符串、配置字典等多种方式
设计原则：最大灵活性，让Agent像人一样连接数据库
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path
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
                        "enum": ["connect", "test", "list", "switch", "save", "load", "list_saved"],
                        "description": "Action to perform: connect (new connection), test (test connection), list (list supported types), switch (change active connection), save (save connection config), load (load saved connection), list_saved (list saved connections)",
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
                    },
                    "ssh_tunnel": {
                        "type": "object",
                        "description": "Optional SSH tunnel configuration for connecting through a bastion/jump server",
                        "properties": {
                            "enabled": {
                                "type": "boolean",
                                "description": "Enable SSH tunnel",
                                "default": True
                            },
                            "ssh_host": {
                                "type": "string",
                                "description": "SSH server hostname (bastion/jump server)"
                            },
                            "ssh_port": {
                                "type": "integer",
                                "description": "SSH server port",
                                "default": 22
                            },
                            "ssh_user": {
                                "type": "string",
                                "description": "SSH username"
                            },
                            "ssh_password": {
                                "type": "string",
                                "description": "SSH password (if not using key)"
                            },
                            "ssh_key_file": {
                                "type": "string",
                                "description": "Path to SSH private key file"
                            },
                            "ssh_key_passphrase": {
                                "type": "string",
                                "description": "Passphrase for SSH key (if encrypted)"
                            },
                            "local_port": {
                                "type": "integer",
                                "description": "Local port for tunnel (0 for auto-assign)",
                                "default": 0
                            }
                        },
                        "required": ["ssh_host", "ssh_user"]
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
        # 存储SSH隧道信息
        self._ssh_tunnels: Dict[str, Any] = {}
        
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        action = params.get("action", "connect")
        
        if action in ["connect", "test"]:
            if not params.get("connection_string"):
                return self._('db_connect_need_connection_string', default="connect和test操作需要提供connection_string")
        elif action == "switch":
            if not params.get("database_name"):
                return self._('db_connect_need_database_name', default="switch操作需要提供database_name")
        elif action == "save":
            if not params.get("alias"):
                return self._('db_connect_need_alias_to_save', default="save操作需要提供alias")
        elif action == "load":
            if not params.get("alias"):
                return self._('db_connect_need_alias_to_load', default="load操作需要提供alias")
                
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
        elif action == "save":
            alias = params.get('alias', '')
            return self._('db_connect_action_save', default="保存连接配置: {alias}", alias=alias)
        elif action == "load":
            alias = params.get('alias', '')
            return self._('db_connect_action_load', default="加载连接配置: {alias}", alias=alias)
        elif action == "list_saved":
            return self._('db_connect_action_list_saved', default="列出保存的连接配置")
        
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
        elif action == "save":
            return await self._save_connection(params, update_output)
        elif action == "load":
            return await self._load_connection(params, update_output)
        elif action == "list_saved":
            return await self._list_saved_connections(update_output)
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
        ssh_config = params.get("ssh_tunnel")
        
        if update_output:
            update_output(self._('db_connect_testing', default="🔌 Testing database connection..."))
        
        try:
            # 如果有SSH配置，先建立SSH隧道
            tunnel_process = None
            if ssh_config and ssh_config.get("enabled", True):
                tunnel_info = await self._setup_ssh_tunnel(ssh_config, connection_string, update_output)
                if tunnel_info:
                    # 修改连接字符串使用本地隧道端口
                    connection_string = tunnel_info['local_connection_string']
                    tunnel_process = tunnel_info['process']
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
            
            # 清理SSH隧道（如果有）
            if tunnel_process:
                try:
                    tunnel_process.terminate()
                    tunnel_process.wait(timeout=2)
                except:
                    tunnel_process.kill()
            
            display_text = f"""✅ {self._('db_test_success')}

**{self._('db_connect_type')}**: {db_type}
**{self._('db_connect_host')}**: {conn_config.get('host', 'localhost')}
**{self._('db_connect_port')}**: {conn_config.get('port', 'default')}
**{self._('db_connect_database')}**: {conn_config.get('database', 'N/A')}
**{self._('db_connect_version')}**: {version or self._('db_connect_unknown_version', default='未知')}
"""
            
            # 如果使用了SSH隧道，添加隧道信息
            if ssh_config and ssh_config.get("enabled", True) and tunnel_process:
                display_text += f"""
**{self._('db_connect_ssh_tunnel_used', default='使用SSH隧道')}**: ✅
- {self._('db_connect_ssh_server', default='SSH服务器')}: {ssh_config.get('ssh_host')}
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
            
            # 清理SSH隧道（如果有）
            if 'tunnel_process' in locals() and tunnel_process:
                try:
                    tunnel_process.terminate()
                    tunnel_process.wait(timeout=2)
                except:
                    tunnel_process.kill()
            
            # 提供有用的错误提示
            display_text = f"""❌ {self._('db_test_failed')}

**{self._('db_connect_error_info', default='错误信息')}**: {error_msg}

**{self._('db_connect_possible_reasons', default='可能的原因')}**:
1. {self._('db_connect_reason_service_not_started', default='数据库服务未启动')}
2. {self._('db_connect_reason_wrong_params', default='连接参数错误（主机、端口、用户名、密码）')}
3. {self._('db_connect_reason_network_issue', default='网络连接问题')}
4. {self._('db_connect_reason_driver_not_installed', default='数据库驱动未安装')}"""
            
            # 如果使用了SSH隧道，添加SSH相关的可能原因
            if ssh_config and ssh_config.get("enabled", True):
                display_text += f"""
5. {self._('db_connect_reason_ssh_failed', default='SSH隧道建立失败')}
6. {self._('db_connect_reason_ssh_auth', default='SSH认证失败（密钥或密码错误）')}"""
            
            display_text += f"""

**{self._('db_connect_suggestions', default='建议')}**:
- {self._('db_connect_suggestion_check_service', default='检查数据库服务状态')}
- {self._('db_connect_suggestion_verify_string', default='验证连接字符串格式')}
- {self._('db_connect_suggestion_check_firewall', default='确认防火墙设置')}
- {self._('db_connect_suggestion_list_drivers', default="使用 action='list' 查看需要安装的驱动")}"""
            
            if ssh_config and ssh_config.get("enabled", True):
                display_text += f"""
- {self._('db_connect_suggestion_check_ssh', default='检查SSH服务器是否可达')}
- {self._('db_connect_suggestion_verify_ssh_key', default='验证SSH密钥文件权限（应该是600）')}"""
            
            display_text += "\n"
            
            return ToolResult(
                error=error_msg,
                summary=self._('db_connect_test_failed_summary', default="Connection test failed"),
                return_display=display_text
            )
    
    async def _connect_database(self, params: Dict[str, Any], update_output: Optional[Any]) -> ToolResult:
        """连接到新数据库"""
        connection_string = params.get("connection_string", "")
        alias = params.get("alias")
        ssh_config = params.get("ssh_tunnel")
        
        if update_output:
            update_output(self._('db_connect_connecting', default="🔗 Connecting to database..."))
        
        try:
            # 如果有SSH配置，先建立SSH隧道
            tunnel_id = None
            if ssh_config and ssh_config.get("enabled", True):
                tunnel_info = await self._setup_ssh_tunnel(ssh_config, connection_string, update_output)
                if tunnel_info:
                    # 修改连接字符串使用本地隧道端口
                    connection_string = tunnel_info['local_connection_string']
                    # 保存隧道信息
                    tunnel_id = f"{alias or 'tunnel'}_{tunnel_info['local_port']}"
                    self._ssh_tunnels[tunnel_id] = tunnel_info
            
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
            connection_info = {
                'adapter': adapter,
                'config': conn_config,
                'connection_string': connection_string,
                'version': version
            }
            
            # 如果有SSH隧道，保存隧道信息
            if ssh_config and ssh_config.get("enabled", True) and tunnel_id in self._ssh_tunnels:
                connection_info['ssh_tunnel'] = self._ssh_tunnels[tunnel_id]
                connection_info['original_connection_string'] = params.get("connection_string", "")
            
            self._active_connections[alias] = connection_info
            
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
"""

            # 如果使用了SSH隧道，显示隧道信息
            if tunnel_id and tunnel_id in self._ssh_tunnels:
                tunnel_info = self._ssh_tunnels[tunnel_id]
                display_text += f"""
**{self._('db_connect_ssh_tunnel', default='SSH隧道')}**: ✅ {self._('db_connect_active')}
- {self._('db_connect_ssh_server', default='SSH服务器')}: {tunnel_info['ssh_host']}
- {self._('db_connect_local_port', default='本地端口')}: {tunnel_info['local_port']}
- {self._('db_connect_remote_target', default='远程目标')}: {tunnel_info['remote_host']}:{tunnel_info['remote_port']}
"""

            display_text += f"""
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
            error_msg = str(e)
            
            # 分析错误类型，提供更智能的建议
            display_text = f"❌ {self._('db_connect_failed_error', default='连接失败: {error}', error=error_msg)}\n\n"
            
            # 检查是否是网络连接错误
            if "Can't connect" in error_msg or "无法连接" in error_msg:
                # 解析连接字符串获取主机信息
                parser = ConnectionStringParser()
                conn_info = parser.parse(connection_string)
                host = conn_info.get('host', 'localhost')
                
                # 判断是本地还是远程
                if host in ['localhost', '127.0.0.1', '::1']:
                    display_text += self._('db_connect_local_db_hint', default="""**这是本地数据库连接**
请检查：
1. 数据库服务是否在本机运行
2. 端口是否正确（MySQL默认3306）
3. 本地防火墙设置""")
                else:
                    display_text += self._('db_connect_remote_db_hint', default="""**这是远程数据库连接**
远程数据库通常需要：
1. SSH隧道连接（企业数据库常见）
2. VPN连接
3. 防火墙白名单

💡 提示：如果数据库在私有网络中，请使用SSH隧道：
database_connect(
    connection_string="mysql://user:pass@localhost:3306/db",
    ssh_tunnel={{
        "ssh_host": "{host}",
        "ssh_user": "your-ssh-user",
        "ssh_key_file": "path/to/key.pem"
    }}
)""").format(host=host)
            
            # SSH相关错误
            elif ssh_config and ("SSH" in error_msg or "tunnel" in error_msg):
                display_text += self._('db_connect_ssh_error_hint', default="""**SSH隧道错误**
请检查：
1. SSH服务器地址和端口是否正确
2. SSH用户名是否正确
3. SSH密钥文件路径是否正确（Windows路径需要双反斜杠）
4. SSH密钥文件权限（Linux/Mac需要chmod 600）""")
            
            return ToolResult(
                error=error_msg,
                summary=self._('db_connect_failed', default='连接失败'),
                return_display=display_text
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
    
    async def _setup_ssh_tunnel(self, ssh_config: Dict[str, Any], connection_string: str, update_output: Optional[Any]) -> Optional[Dict[str, Any]]:
        """建立SSH隧道"""
        try:
            # 记录调试信息
            from ..utils.debug_logger import log_info, DebugLogger
            log_info("SSH_TUNNEL", f"Starting SSH tunnel setup with config: {ssh_config}")
            
            # 解析原始连接字符串获取目标主机和端口
            parser = ConnectionStringParser()
            conn_config = parser.parse(connection_string)
            remote_host = conn_config.get('host', 'localhost')
            remote_port = conn_config.get('port', self._get_default_db_port(conn_config.get('type')))
            
            log_info("SSH_TUNNEL", f"Target database: {remote_host}:{remote_port}")
            
            # SSH配置
            ssh_host = ssh_config.get('ssh_host')
            ssh_port = ssh_config.get('ssh_port', 22)
            ssh_user = ssh_config.get('ssh_user')
            ssh_password = ssh_config.get('ssh_password')
            ssh_key_file = ssh_config.get('ssh_key_file')
            local_port = ssh_config.get('local_port', 0)
            
            if update_output:
                update_output(self._('db_connect_ssh_connecting', default="🔐 Establishing SSH tunnel to {host}...", host=ssh_host))
            
            # 尝试使用系统的ssh命令建立隧道（最小侵入性）
            import subprocess
            import socket
            
            # 如果local_port为0，找一个可用端口
            if local_port == 0:
                sock = socket.socket()
                sock.bind(('', 0))
                local_port = sock.getsockname()[1]
                sock.close()
            
            # 构建SSH命令
            ssh_cmd = ['ssh', '-N', '-L', f'{local_port}:{remote_host}:{remote_port}']
            
            # 添加更多SSH选项以避免交互式提示
            ssh_cmd.extend(['-o', 'StrictHostKeyChecking=no'])
            ssh_cmd.extend(['-o', 'UserKnownHostsFile=/dev/null'])
            
            if ssh_key_file:
                # 处理Windows路径格式
                key_path = os.path.expanduser(ssh_key_file)
                log_info("SSH_TUNNEL", f"SSH key file path: {key_path}")
                
                # 在Windows上，确保路径存在
                if os.name == 'nt':
                    if not os.path.exists(key_path):
                        log_info("SSH_TUNNEL", f"SSH key file not found at: {key_path}")
                        # 尝试不同的路径格式
                        if key_path.startswith('/mnt/c/'):
                            # WSL路径转Windows路径
                            win_path = key_path.replace('/mnt/c/', 'C:\\').replace('/', '\\')
                            if os.path.exists(win_path):
                                key_path = win_path
                                log_info("SSH_TUNNEL", f"Using converted path: {key_path}")
                    else:
                        log_info("SSH_TUNNEL", f"SSH key file found at: {key_path}")
                
                ssh_cmd.extend(['-i', key_path])
            
            ssh_cmd.extend(['-p', str(ssh_port)])
            ssh_cmd.append(f'{ssh_user}@{ssh_host}')
            
            # 启动SSH进程
            if update_output:
                # 显示更详细的SSH命令信息用于调试
                safe_cmd = ssh_cmd.copy()
                # 隐藏密钥文件的完整路径，只显示文件名
                for i, arg in enumerate(safe_cmd):
                    if i > 0 and safe_cmd[i-1] == '-i':
                        safe_cmd[i] = f".../{os.path.basename(arg)}"
                update_output(self._('db_connect_ssh_command', default="📝 SSH command: {cmd}", cmd=' '.join(safe_cmd)))
            
            # 记录完整的SSH命令用于调试
            log_info("SSH_TUNNEL", f"Full SSH command: {' '.join(ssh_cmd)}")
            
            # 检查SSH命令是否可用
            import shutil
            if not shutil.which('ssh'):
                log_info("SSH_TUNNEL", "SSH command not found in PATH")
                # 在Windows上，尝试一些常见位置
                if os.name == 'nt':
                    possible_ssh_paths = [
                        r"C:\Windows\System32\OpenSSH\ssh.exe",
                        r"C:\Program Files\Git\usr\bin\ssh.exe",
                        r"C:\Program Files (x86)\Git\usr\bin\ssh.exe"
                    ]
                    for ssh_path in possible_ssh_paths:
                        if os.path.exists(ssh_path):
                            ssh_cmd[0] = ssh_path
                            log_info("SSH_TUNNEL", f"Using SSH from: {ssh_path}")
                            break
            
            # 使用subprocess.Popen启动后台进程
            if os.name == 'nt':  # Windows
                # Windows需要特殊处理
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.Popen(
                    ssh_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo
                )
            else:
                process = subprocess.Popen(
                    ssh_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            # 等待隧道建立
            import time
            log_info("SSH_TUNNEL", "Waiting for SSH tunnel to establish...")
            time.sleep(3)  # 给SSH更多时间建立连接
            
            # 检查进程是否还在运行
            log_info("SSH_TUNNEL", f"Checking SSH process status...")
            if process.poll() is not None:
                # 进程已退出，获取错误信息
                stdout, stderr = process.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore')
                stdout_msg = stdout.decode('utf-8', errors='ignore')
                
                # 记录详细错误信息
                if update_output:
                    update_output(self._('db_connect_ssh_error_detail', default="❌ SSH隧道建立失败"))
                
                error_detail = f"SSH tunnel failed:\n"
                if stderr:
                    error_detail += f"错误输出: {error_msg}\n"
                if stdout:
                    error_detail += f"标准输出: {stdout_msg}\n"
                
                # 检查常见错误
                if "Permission denied" in error_msg:
                    error_detail += "\n可能的原因：\n- SSH密钥权限错误（应该是600）\n- SSH用户名错误\n- 密钥文件路径错误"
                elif "No such file or directory" in error_msg:
                    error_detail += f"\n可能的原因：\n- SSH密钥文件不存在: {ssh_key_file}\n- Windows路径格式问题"
                elif "Connection refused" in error_msg:
                    error_detail += f"\n可能的原因：\n- SSH服务器 {ssh_host}:{ssh_port} 不可达\n- 防火墙阻止连接"
                
                raise Exception(error_detail)
            
            # 构建新的本地连接字符串
            local_connection_string = connection_string.replace(
                f"{remote_host}:{remote_port}",
                f"localhost:{local_port}"
            ).replace(
                f"{remote_host}/",
                f"localhost:{local_port}/"
            )
            
            if update_output:
                update_output(self._('db_connect_ssh_established', default="✅ SSH tunnel established on local port {port}", port=local_port))
            
            return {
                'process': process,
                'local_port': local_port,
                'remote_host': remote_host,
                'remote_port': remote_port,
                'ssh_host': ssh_host,
                'local_connection_string': local_connection_string
            }
            
        except Exception as e:
            log_info("SSH_TUNNEL", f"SSH tunnel setup failed with exception: {str(e)}")
            if update_output:
                update_output(self._('db_connect_ssh_failed', default="❌ SSH tunnel failed: {error}", error=str(e)))
            # 不抛出异常，让连接继续尝试（可能是直连）
            return None
    
    def _get_default_db_port(self, db_type: str) -> int:
        """获取数据库默认端口"""
        default_ports = {
            'mysql': 3306,
            'postgresql': 5432,
            'postgres': 5432,
            'sqlserver': 1433,
            'oracle': 1521,
            'mongodb': 27017,
            'redis': 6379
        }
        return default_ports.get(db_type, 3306)
    
    def _get_connections_config_path(self) -> Path:
        """获取连接配置文件路径"""
        # 使用项目根目录下的 .dbrheo 目录
        config_dir = Path.cwd() / ".dbrheo"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "connections.yaml"
    
    def _load_saved_connections(self) -> Dict[str, Any]:
        """加载保存的连接配置"""
        config_path = self._get_connections_config_path()
        if not config_path.exists():
            return {}
        
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                return data.get('connections', {})
        except Exception:
            return {}
    
    def _save_connection_config(self, alias: str, config: Dict[str, Any]) -> bool:
        """保存连接配置到文件"""
        try:
            import yaml
            from datetime import datetime
            
            # 加载现有配置
            config_path = self._get_connections_config_path()
            existing_data = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_data = yaml.safe_load(f) or {}
            
            # 确保有connections键
            if 'connections' not in existing_data:
                existing_data['connections'] = {}
            
            # 添加时间戳
            config['saved_at'] = datetime.now().isoformat()
            
            # 保存配置
            existing_data['connections'][alias] = config
            
            # 写回文件
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(existing_data, f, default_flow_style=False, allow_unicode=True)
            
            return True
        except Exception:
            return False
    
    async def _save_connection(self, params: Dict[str, Any], update_output: Optional[Any]) -> ToolResult:
        """保存当前连接到配置文件"""
        alias = params.get("alias", "")
        
        if update_output:
            update_output(self._('db_connect_saving', default="💾 保存连接配置..."))
        
        # 检查是否有活动连接
        if alias not in self._active_connections:
            return ToolResult(
                error=self._('db_connect_no_active_connection', default="没有找到别名为 '{alias}' 的活动连接", alias=alias),
                summary=self._('db_connect_save_failed', default="保存失败"),
                return_display=self._('db_connect_save_no_connection', default="❌ 保存失败：请先使用该别名建立连接")
            )
        
        # 获取连接信息
        conn_info = self._active_connections[alias]
        
        # 构建保存的配置
        save_config = {
            'connection_string': conn_info.get('original_connection_string', conn_info['connection_string']),
            'type': conn_info['config'].get('type'),
            'description': params.get('description', ''),
            'version': conn_info.get('version')
        }
        
        # 如果有SSH隧道配置，保存它
        if 'ssh_tunnel' in conn_info and 'original_connection_string' in conn_info:
            tunnel_info = conn_info['ssh_tunnel']
            ssh_config = {
                'ssh_host': tunnel_info['ssh_host'],
                'ssh_port': tunnel_info.get('ssh_port', 22),
                'ssh_user': tunnel_info.get('ssh_user')
            }
            # 只保存非空的配置项
            if tunnel_info.get('ssh_key_file'):
                ssh_config['ssh_key_file'] = tunnel_info['ssh_key_file']
            if tunnel_info.get('ssh_password'):
                # 注意：密码不应该明文保存，这里只是示例
                ssh_config['ssh_password'] = tunnel_info['ssh_password']
            save_config['ssh_tunnel'] = ssh_config
        
        # 保存到文件
        if self._save_connection_config(alias, save_config):
            config_path = self._get_connections_config_path()
            display_text = f"""✅ {self._('db_connect_save_success', default='连接配置已保存')}

**{self._('db_connect_alias')}**: {alias}
**{self._('db_connect_type')}**: {save_config['type']}
**{self._('db_connect_config_file', default='配置文件')}**: {config_path}
"""
            if save_config.get('description'):
                display_text += f"**{self._('db_connect_description', default='描述')}**: {save_config['description']}\n"
            
            if 'ssh_tunnel' in save_config:
                display_text += f"\n**{self._('db_connect_ssh_info', default='SSH隧道信息')}**:\n"
                display_text += f"- {self._('db_connect_ssh_server', default='SSH服务器')}: {save_config['ssh_tunnel']['ssh_host']}\n"
                display_text += f"- {self._('db_connect_ssh_user', default='SSH用户')}: {save_config['ssh_tunnel']['ssh_user']}\n"
            
            return ToolResult(
                summary=self._('db_connect_saved', default="连接配置已保存: {alias}", alias=alias),
                llm_content={
                    "success": True,
                    "alias": alias,
                    "config_path": str(config_path),
                    "has_ssh_tunnel": 'ssh_tunnel' in save_config
                },
                return_display=display_text
            )
        else:
            return ToolResult(
                error=self._('db_connect_save_error', default="保存配置时出错"),
                summary=self._('db_connect_save_failed', default="保存失败"),
                return_display=self._('db_connect_save_failed_display', default="❌ 保存连接配置失败")
            )
    
    async def _load_connection(self, params: Dict[str, Any], update_output: Optional[Any]) -> ToolResult:
        """从配置文件加载连接"""
        alias = params.get("alias", "")
        
        if update_output:
            update_output(self._('db_connect_loading', default="📂 加载连接配置..."))
        
        # 加载保存的连接
        saved_connections = self._load_saved_connections()
        
        if alias not in saved_connections:
            available = list(saved_connections.keys())
            return ToolResult(
                error=self._('db_connect_config_not_found', default="未找到保存的连接: {alias}", alias=alias),
                summary=self._('db_connect_load_failed', default="加载失败"),
                return_display=f"""❌ {self._('db_connect_config_not_found', default="未找到保存的连接: {alias}", alias=alias)}

{self._('db_connect_available_configs', default='可用的连接配置')}:
{chr(10).join([f"- {name}" for name in available]) if available else self._('db_connect_no_saved_connections', default='没有保存的连接')}
"""
            )
        
        # 获取配置
        config = saved_connections[alias]
        connection_string = config.get('connection_string', '')
        ssh_config = config.get('ssh_tunnel')
        
        # 构建连接参数
        connect_params = {
            'action': 'connect',
            'connection_string': connection_string,
            'alias': alias
        }
        
        if ssh_config:
            connect_params['ssh_tunnel'] = ssh_config
        
        # 执行连接
        if update_output:
            update_output(self._('db_connect_connecting_saved', default="🔗 使用保存的配置连接..."))
        
        # 直接调用连接方法
        result = await self._connect_database(connect_params, update_output)
        
        # 如果成功，添加额外信息
        if not result.error:
            saved_at = config.get('saved_at', 'unknown')
            extra_info = f"\n\n{self._('db_connect_loaded_from_config', default='从保存的配置加载 (保存时间: {saved_at})', saved_at=saved_at)}"
            result.return_display += extra_info
        
        return result
    
    async def _list_saved_connections(self, update_output: Optional[Any]) -> ToolResult:
        """列出所有保存的连接配置"""
        if update_output:
            update_output(self._('db_connect_listing_saved', default="📋 列出保存的连接..."))
        
        # 加载保存的连接
        saved_connections = self._load_saved_connections()
        config_path = self._get_connections_config_path()
        
        if not saved_connections:
            return ToolResult(
                summary=self._('db_connect_no_saved_summary', default="没有保存的连接配置"),
                return_display=f"""📭 {self._('db_connect_no_saved_connections', default='没有保存的连接配置')}

{self._('db_connect_save_hint', default='使用以下命令保存当前连接')}:
`database_connect(action="save", alias="别名", description="描述")`

{self._('db_connect_config_location', default='配置文件位置')}: {config_path}
"""
            )
        
        # 构建显示内容
        display_lines = [
            f"📋 **{self._('db_connect_saved_connections', default='保存的连接配置')}**",
            f"{self._('db_connect_config_file', default='配置文件')}: `{config_path}`",
            ""
        ]
        
        for alias, config in saved_connections.items():
            display_lines.append(f"### 📌 {alias}")
            display_lines.append(f"- **{self._('db_connect_type')}**: {config.get('type', 'unknown')}")
            
            if config.get('description'):
                display_lines.append(f"- **{self._('db_connect_description', default='描述')}**: {config['description']}")
            
            saved_at = config.get('saved_at', 'unknown')
            display_lines.append(f"- **{self._('db_connect_saved_at', default='保存时间')}**: {saved_at}")
            
            if 'ssh_tunnel' in config:
                ssh = config['ssh_tunnel']
                display_lines.append(f"- **{self._('db_connect_ssh_tunnel', default='SSH隧道')}**: ✅")
                display_lines.append(f"  - {self._('db_connect_ssh_server', default='SSH服务器')}: {ssh.get('ssh_host')}")
                display_lines.append(f"  - {self._('db_connect_ssh_user', default='SSH用户')}: {ssh.get('ssh_user')}")
            
            display_lines.append(f"- **{self._('db_connect_load_command', default='加载命令')}**: `database_connect(action=\"load\", alias=\"{alias}\")`")
            display_lines.append("")
        
        return ToolResult(
            summary=self._('db_connect_found_saved', default="找到 {count} 个保存的连接", count=len(saved_connections)),
            llm_content={
                "saved_connections": list(saved_connections.keys()),
                "config_path": str(config_path),
                "connections": saved_connections
            },
            return_display="\n".join(display_lines)
        )