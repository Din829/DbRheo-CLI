# Gemini SDK迁移说明

## 迁移背景
- 旧SDK `google-generativeai` 将于2025年8月31日停止支持
- 新SDK `google-genai` 支持显式缓存功能，可节省大量token成本
- 迁移时间：2025年8月3日

## 主要变更

### 1. SDK依赖更新
```bash
# 旧版
google-generativeai>=0.8.5

# 新版
google-genai>=1.0.0
```

### 2. 代码变更
- 文件：`packages/core/src/dbrheo/services/gemini_service.py`
- 备份：`packages/core/src/dbrheo/services/gemini_service_backup.py`

### 3. 新增功能
- **显式缓存支持**：系统指令和工具定义可缓存1小时
- **缓存阈值**：系统指令需要超过1024 tokens才会缓存
- **自动缓存管理**：基于内容哈希值自动创建和复用缓存

### 4. 兼容性
- 完全兼容现有接口，无需修改其他代码
- 支持原有的所有功能
- 缓存功能可通过配置禁用：`enable_explicit_cache: false`

## 使用说明

### 安装新依赖
```bash
pip-compile requirements.in
pip install -r requirements.txt
```

### 环境变量
新SDK支持两种API密钥：
- `GOOGLE_API_KEY`（兼容旧版）
- `GEMINI_API_KEY`（新版推荐）

### 缓存监控
启用DEBUG日志可查看缓存使用情况：
```bash
export DBRHEO_DEBUG_LEVEL=DEBUG
```

## 注意事项
1. 首次使用时会创建缓存，可能有轻微延迟
2. 缓存基于系统指令内容，内容变化会创建新缓存
3. 缓存自动过期时间为1小时

## 回滚方案
如遇问题，可快速回滚：
```bash
cp packages/core/src/dbrheo/services/gemini_service_backup.py packages/core/src/dbrheo/services/gemini_service.py
# 修改 requirements.in 恢复旧版SDK
pip-compile requirements.in
pip install -r requirements.txt
```