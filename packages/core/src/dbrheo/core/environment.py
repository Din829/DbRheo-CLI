"""
DatabaseEnvironmentCollector - 数据库环境上下文收集器
完全对齐Gemini CLI的getEnvironment方法，收集数据库相关的环境信息
"""

import os
import sys
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import glob
import json

from ..config.base import DatabaseConfig
from ..types.core_types import Part


class DatabaseEnvironmentCollector:
    """
    数据库环境上下文收集器 - 完全对齐Gemini CLI
    收集并格式化数据库相关的环境信息，供Agent初始化时使用
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        
    async def get_environment(self) -> List[Part]:
        """
        收集数据库环境信息 - 完全参考Gemini CLI的getEnvironment方法
        返回Part列表，包含环境上下文信息
        """
        cwd = self.config.get_working_dir()
        today = datetime.now().strftime("%A, %B %d, %Y")
        platform = sys.platform
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.patch}"
        
        # 获取文件夹结构（类似Gemini CLI的getFolderStructure）
        folder_structure = await self._get_folder_structure(cwd)
        
        # 基础环境信息（与Gemini CLI格式一致）
        context = f"""This is the Database Agent (DbRheo). We are setting up the context for our database session.
Today's date is {today}.
My operating system is: {platform}
Python version: {python_version}
I'm currently working in the directory: {cwd}
{folder_structure}"""
        
        initial_parts = [Part(text=context.strip())]
        
        # 数据库特定的环境信息
        db_context_parts = await self._collect_database_context()
        if db_context_parts:
            initial_parts.extend(db_context_parts)
            
        # Git仓库信息（如果有）
        git_info = await self._get_git_info(cwd)
        if git_info:
            initial_parts.append(Part(text=git_info))
            
        return initial_parts
        
    async def _get_folder_structure(self, directory: str) -> str:
        """
        获取文件夹结构 - 参考Gemini CLI的getFolderStructure
        重点关注数据库相关的目录和文件
        """
        try:
            structure_parts = ["## Project Structure"]
            
            # 检查常见的数据库相关目录和文件
            db_related_patterns = [
                # 数据库迁移和架构
                "migrations/", "db/", "database/", "schema/", "models/",
                "alembic/", "flyway/", "liquibase/",
                
                # SQL文件
                "*.sql", "**/*.sql",
                
                # 数据库文件
                "*.db", "*.sqlite", "*.sqlite3",
                
                # 配置文件
                "alembic.ini", "database.yml", "database.yaml",
                "db.config.json", ".env", ".env.local",
                
                # ORM配置
                "models.py", "database.py", "db.py",
                
                # 项目配置文件
                "requirements.txt", "pyproject.toml", "setup.py",
                "package.json", "Gemfile", "go.mod",
            ]
            
            found_items = []
            seen_dirs = set()
            
            for pattern in db_related_patterns:
                # 使用glob查找匹配的文件
                matches = glob.glob(os.path.join(directory, pattern), recursive=True)
                
                for match in matches:
                    rel_path = os.path.relpath(match, directory)
                    
                    # 避免重复和过深的路径
                    if rel_path.count(os.sep) > 3:
                        continue
                        
                    # 对于目录，只记录一次
                    if os.path.isdir(match):
                        if rel_path not in seen_dirs:
                            seen_dirs.add(rel_path)
                            found_items.append((rel_path, True))
                    else:
                        found_items.append((rel_path, False))
                        
            # 排序并格式化输出
            found_items.sort(key=lambda x: (x[0].count(os.sep), x[0]))
            
            # 构建树形结构
            added_count = 0
            for item_path, is_dir in found_items[:20]:  # 限制显示前20个
                depth = item_path.count(os.sep)
                indent = "  " * depth
                prefix = "├── " if added_count < len(found_items) - 1 else "└── "
                suffix = "/" if is_dir else ""
                
                structure_parts.append(f"{indent}{prefix}{os.path.basename(item_path)}{suffix}")
                added_count += 1
                
            if len(found_items) > 20:
                structure_parts.append("└── ... (and more)")
                
            if len(structure_parts) == 1:  # 只有标题，没有找到相关文件
                structure_parts.append("├── (no database-related files detected)")
                
            return "\n".join(structure_parts)
            
        except Exception as e:
            return f"## Project Structure\n(Unable to analyze project structure: {str(e)})"
            
    async def _collect_database_context(self) -> List[Part]:
        """收集数据库特定的上下文信息"""
        context_parts = []
        
        # 1. 检测数据库连接配置
        db_info = await self._detect_database_connections()
        if db_info:
            context_parts.append(Part(text=f"## Database Connections\n{db_info}"))
            
        # 2. 检测数据库迁移工具
        migration_info = await self._detect_migration_tools()
        if migration_info:
            context_parts.append(Part(text=f"## Database Migration Tools\n{migration_info}"))
            
        # 3. 检测ORM框架
        orm_info = await self._detect_orm_frameworks()
        if orm_info:
            context_parts.append(Part(text=f"## ORM Framework\n{orm_info}"))
            
        return context_parts
        
    async def _detect_database_connections(self) -> Optional[str]:
        """检测数据库连接信息"""
        connections = []
        
        # 从配置中获取数据库URL
        db_url = self.config.get("database_url")
        if db_url and db_url != "sqlite:///./default.db":
            # 隐藏敏感信息
            safe_url = self._mask_connection_string(db_url)
            connections.append(f"- Default: {safe_url}")
            
        # 检查环境变量中的其他数据库连接
        env_patterns = ["DATABASE_URL", "DB_URL", "MYSQL_URL", "POSTGRES_URL", "MONGODB_URI"]
        for pattern in env_patterns:
            for key, value in os.environ.items():
                if pattern in key and value:
                    safe_value = self._mask_connection_string(value)
                    connections.append(f"- {key}: {safe_value}")
                    
        # 检查常见的数据库配置文件
        config_files = [".env", ".env.local", "database.yml", "database.yaml", "config/database.yml"]
        for config_file in config_files:
            if os.path.exists(config_file):
                connections.append(f"- Config file found: {config_file}")
                
        return "\n".join(connections) if connections else None
        
    async def _detect_migration_tools(self) -> Optional[str]:
        """检测数据库迁移工具"""
        tools = []
        
        # 检测常见的迁移工具
        tool_indicators = {
            "Alembic": ["alembic.ini", "alembic/", "migrations/alembic.ini"],
            "Django Migrations": ["migrations/", "manage.py"],
            "Flyway": ["flyway.conf", "sql/", "flyway/"],
            "Liquibase": ["liquibase.properties", "changelog/"],
            "SQLAlchemy-Migrate": ["migrate.cfg", "versions/"],
        }
        
        for tool_name, indicators in tool_indicators.items():
            for indicator in indicators:
                if os.path.exists(indicator):
                    tools.append(f"- {tool_name} (detected: {indicator})")
                    break
                    
        return "\n".join(tools) if tools else None
        
    async def _detect_orm_frameworks(self) -> Optional[str]:
        """检测ORM框架"""
        frameworks = []
        
        # 检查Python项目文件
        if os.path.exists("requirements.txt"):
            try:
                with open("requirements.txt", "r") as f:
                    content = f.read().lower()
                    if "sqlalchemy" in content:
                        frameworks.append("- SQLAlchemy (Python ORM)")
                    if "django" in content:
                        frameworks.append("- Django ORM")
                    if "peewee" in content:
                        frameworks.append("- Peewee ORM")
                    if "tortoise" in content:
                        frameworks.append("- Tortoise ORM")
            except Exception:
                pass
                
        # 检查pyproject.toml
        if os.path.exists("pyproject.toml"):
            try:
                with open("pyproject.toml", "r") as f:
                    content = f.read().lower()
                    if "sqlalchemy" in content:
                        frameworks.append("- SQLAlchemy (detected in pyproject.toml)")
            except Exception:
                pass
                
        # 检查其他语言的ORM
        if os.path.exists("package.json"):
            frameworks.append("- Possible Node.js project (check for Sequelize, TypeORM, Prisma)")
            
        if os.path.exists("Gemfile"):
            frameworks.append("- Possible Ruby project (check for ActiveRecord)")
            
        if os.path.exists("go.mod"):
            frameworks.append("- Possible Go project (check for GORM)")
            
        return "\n".join(frameworks) if frameworks else None
        
    async def _get_git_info(self, directory: str) -> Optional[str]:
        """获取Git仓库信息"""
        if not os.path.exists(os.path.join(directory, ".git")):
            return None
            
        info_parts = ["## Git Repository"]
        
        try:
            # 获取当前分支
            proc = await asyncio.create_subprocess_exec(
                "git", "branch", "--show-current",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=directory
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0 and stdout:
                branch = stdout.decode().strip()
                info_parts.append(f"Current branch: {branch}")
                
            # 获取最近的提交
            proc = await asyncio.create_subprocess_exec(
                "git", "log", "-1", "--oneline",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=directory
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0 and stdout:
                commit = stdout.decode().strip()
                info_parts.append(f"Latest commit: {commit}")
                
            # 检查是否有未提交的更改
            proc = await asyncio.create_subprocess_exec(
                "git", "status", "--porcelain",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=directory
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0 and stdout:
                changes = len(stdout.decode().strip().split('\n'))
                info_parts.append(f"Uncommitted changes: {changes} files")
                
        except Exception:
            pass
            
        return "\n".join(info_parts) if len(info_parts) > 1 else None
        
    def _mask_connection_string(self, conn_str: str) -> str:
        """隐藏连接字符串中的敏感信息"""
        # 隐藏密码
        import re
        
        # 匹配各种格式的密码
        patterns = [
            (r'://([^:]+):([^@]+)@', r'://\1:****@'),  # user:pass@host
            (r'password=([^&\s]+)', r'password=****'),  # password=xxx
            (r'pwd=([^&\s]+)', r'pwd=****'),           # pwd=xxx
        ]
        
        masked = conn_str
        for pattern, replacement in patterns:
            masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)
            
        return masked