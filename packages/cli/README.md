# DbRheo CLI

智能数据库Agent的专业命令行界面。

## 特性

- **流式输出**: 实时显示Agent响应，提供流畅的交互体验
- **Markdown渲染**: 支持代码高亮、表格等富文本显示
- **工具可视化**: 清晰展示工具执行状态和结果
- **专业UI**: 基于Rich库的简洁专业界面

## 安装

```bash
# 开发安装
pip install -e .

# 包含开发依赖
pip install -e ".[dev]"
```

## 使用

```bash
# 启动CLI
dbrheo

# 查看帮助
dbrheo --help
```

## 开发

### 项目结构

```
src/dbrheo_cli/
├── display/      # 显示层：负责所有终端渲染
├── components/   # UI组件：可复用的界面元素
└── utils/        # 工具函数：通用功能支持
```

### 运行测试

```bash
pytest
```

### 代码检查

```bash
# 格式化
black src/

# 类型检查
mypy src/

# 代码质量
ruff src/
```

## 设计理念

- **简洁专业**: 避免过度装饰，专注内容展示
- **性能优先**: 大输出时保持流畅响应
- **用户友好**: 清晰的视觉层次和交互反馈

## 许可证

MIT License