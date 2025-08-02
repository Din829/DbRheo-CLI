"""
国际化(i18n)支持
统一管理所有显示文本，方便后续多语言切换
"""

import os
import locale
from typing import Dict, Any


def detect_system_language() -> str:
    """
    检测系统语言
    返回支持的语言代码：zh_CN（中文）、ja_JP（日文）、en_US（英文）
    """
    # 优先级1：环境变量 DBRHEO_LANG
    env_lang = os.environ.get('DBRHEO_LANG')
    if env_lang:
        return env_lang
    
    # 优先级2：系统locale
    try:
        system_locale = locale.getdefaultlocale()[0]
        if system_locale:
            # 日文环境
            if system_locale.startswith('ja'):
                return 'ja_JP'
            # 中文环境
            elif system_locale.startswith('zh'):
                return 'zh_CN'
            # 英文环境
            elif system_locale.startswith('en'):
                return 'en_US'
    except:
        pass
    
    # 默认中文
    return 'zh_CN'


class I18n:
    """
    简单的国际化支持类
    未来可以扩展为完整的i18n系统
    """
    
    # 当前语言（自动检测）
    current_lang = detect_system_language()
    
    # 同步到环境变量
    os.environ['DBRHEO_LANG'] = current_lang
    
    # 所有文本定义
    _messages = {
        'zh_CN': {
            # 主程序消息
            'welcome_title': 'DbRheo CLI',
            'welcome_subtitle': '数据库智能助手',
            'help_hint': '输入 /help 查看帮助信息',
            'user_interrupt': '用户中断，正在退出...',
            'error_occurred': '发生错误: {error}',
            'signal_received': 'Received signal {signum}, shutting down gracefully...',
            'debug_level_set': 'Debug level set to {level}',
            'log_enabled': 'Realtime logging enabled',
            
            # CLI消息
            'unknown_command': '未知命令: {command}',
            'debug_level_range': '调试级别必须在 0-5 之间',
            'current_debug_level': '当前调试级别: {level}',
            'debug_usage': '用法: /debug <0-5>',
            'debug_reload_warning': '警告：无法重新加载日志模块: {error}',
            'error_processing': '处理消息时出错: {error}',
            'error_continuing': '确认后继续时出错: {error}',
            'tool_count': '本次对话调用了 {count} 个工具',
            
            # 语言相关
            'current_language': '当前语言: {lang}',
            'language_set': '语言已切换为: {lang}',
            'language_not_supported': '不支持的语言: {lang}',
            'language_usage': '用法: /lang [zh|ja|en]',
            'available_languages': '可用语言: zh（中文）, ja（日文）, en（英文）',
            
            # 帮助文本
            'help_title': '可用命令',
            'help_exit': '退出 CLI',
            'help_clear': '清屏',
            'help_debug': '设置调试级别',
            'help_lang': '切换显示语言',
            'help_multiline': '多行输入（输入 ``` 或 <<< 开始）',
            'help_esc': '按 ESC 清空当前输入',
            'tool_confirmation_title': '工具确认',
            'tool_confirmation_help': '''当工具需要确认时：
  - 输入 '1' 或 'confirm' 确认执行
  - 输入 '2' 或 'cancel' 取消执行
  - 输入 'confirm all' 确认所有待执行工具''',
            
            # 工具相关
            'tool_confirm_title': '工具需要确认: {tool_name}',
            'risk_level': '风险级别',
            'risk_description': '风险说明',
            'parameters': '参数',
            'please_choose': '请选择',
            'please_input': '请输入',
            'confirm_execute': '确认执行',
            'cancel_execute': '取消执行',
            'confirm_all_tools': '确认所有待执行工具',
            'tool_confirmed': '确认执行工具',
            'tool_rejected': '取消执行工具',
            'tool_confirmed_all': '确认执行所有工具',
            'tool_error': '确认工具时出错: {error}',
            'tool_result': '执行结果',
            'tool_failed': '执行失败: {error}',
            'more_items': '... 还有 {count} 项',
            
            # 事件消息
            'max_session_turns': '已达到最大会话轮数限制',
            'chat_compressed': '会话历史已压缩',
            
            # 状态指示器
            'status_pending': '[待定]',
            'status_confirm': '[确认]',
            'status_approved': '[已批准]',
            'status_running': '[执行中]',
            'status_success': '[成功]',
            'status_error': '[错误]',
            'status_cancelled': '[已取消]',
            'status_unknown': '[未知]',
            
            # 输入提示
            'clipboard_hint': '复制多行文本后按Enter键自动粘贴 | 或输入 \'\'\' 开始多行模式',
            'multiline_mode_hint': '进入多行输入模式，再次输入 ``` 或 <<< 结束',
            'startup_tips_title': '使用提示:',
            'input_halfwidth_hint': '（日语系统请输入半角数字）',
            
            # 工具执行消息
            'tool_executing': '执行工具: {tool_name}',
            
            # 系统状态消息
            'exiting': '退出中...',
            'cleaning_resources': '清理资源...',
            
            # 启动提示
            'startup_tip_1': '1. 提出问题、执行SQL多种操作、分析数据',
            'startup_tip_2': '2. 使用具体描述获得最佳结果',
            'startup_tip_3': '3. /help 查看更多信息',
            'startup_tip_4': '4. 支持多种数据库：SQLite、MySQL、PostgreSQL',
            'startup_tip_5': '5. 集成 Python 运行时环境进行数据处理与可视化',
            'startup_tip_6': '6. 支持多种AI模型：Gemini、Claude、GPT (/model 切换)',
            'home_dir_warning': '你正在主目录运行 DbRheo CLI。建议在项目目录中运行。',
            
            # 模型相关
            'model_switched': '已切换到模型: {model}',
            'model_switch_failed': '切换模型失败: {error}',
            'current_model': '当前模型: {model}',
            'model_usage': '使用方法',
            'available_models': '可用模型',
            'latest': '最新',
            'reasoning': '推理增强',
            'fast': '快速',
            'default': '默认',
            'example': '示例',
            'supported_models': '支持的模型：',
            'model_gemini': '- Gemini: gemini, gemini-2.5-flash, gemini-2.0',
            'model_claude': '- Claude: claude, sonnet, opus, sonnet4, opus4',
            'model_openai': '- OpenAI: gpt-4, gpt-4.1, o1, o3',
            'help_model': '切换AI模型',
            
            # API Key 相关
            'api_key_missing': '⚠️  未检测到 {model} 的 API Key',
            'api_key_setup': '请在 .env 文件中设置以下环境变量：',
            'api_key_gemini': 'GOOGLE_API_KEY 或 GEMINI_API_KEY',
            'api_key_claude': 'ANTHROPIC_API_KEY 或 CLAUDE_API_KEY',
            'api_key_openai': 'OPENAI_API_KEY',
            'api_key_instructions': '获取 API Key 请访问：',
            'api_key_gemini_url': 'https://aistudio.google.com/apikey',
            'api_key_claude_url': 'https://console.anthropic.com/settings/keys',
            'api_key_openai_url': 'https://platform.openai.com/api-keys',
            'api_key_reminder': '设置完成后请重启 CLI',
            
            # Token 统计相关
            'token_usage_title': 'Token 使用统计',
            'token_usage_total': '总计：{total} tokens ({calls} 次调用)',
            'token_usage_detail': '├─ 输入：{prompt} tokens',
            'token_usage_detail_output': '└─ 输出：{completion} tokens',
            'token_usage_by_model': '按模型统计：',
            'token_usage_model_detail': '  {model}：{total} tokens ({calls} 次调用)',
            'token_command_hint': '使用 /token 查看当前统计',
            'help_token': '查看 Token 使用统计',
            'token_statistics_unavailable': 'Token 统计功能不可用',
            'no_token_usage_yet': '暂无 Token 使用记录',
            
            # cli.py 相关
            'esc_abort': '用户按下ESC，中止输出...',
            'traditional_layout': '使用传统布局模式',
            'enhanced_layout': '使用增强布局模式（底部固定输入框）',
            'continuing': '继续处理...',
            'tool_calls_summary': '本次对话调用了 {count} 个工具: {tools}',
            'tool_calls_continue': '继续处理中调用了 {count} 个工具: {tools}',
            'error_format': 'Error: {error}',
            'enhanced_layout_shortcuts': 'ESC: 清空/退出  |  Ctrl+C: 复制后Enter自动粘贴  |  \'\'\': 多行模式',
            
            # tool_handler.py 相关
            'executing_code': '即将执行的 {param_key}:',
            'tool_success': '工具 {name} 执行成功',
            'tool_failed_with_error': '工具 {name} 执行失败: {error}',
            'tool_cancelled': '工具 {name} 已取消',
            'execution_result': '执行结果:',
            'rows_truncated': '... 还有 {count} 行数据（已截断）',
            'total_rows': '共 {count} 行',
            
            # simple_multiline_input.py 相关
            'paste_detect_error': '粘贴检测错误: {error}',
            'tkinter_unavailable': 'tkinter不可用，剪贴板功能已禁用',
            'tkinter_window_error': '无法创建tkinter窗口: {error}',
            'clipboard_read_error': '剪贴板读取失败: {error}',
            'clipboard_error': '剪贴板功能异常: {error}: {details}',
            'multiline_preview_title': '多行输入预览',
            'multiline_traditional_hint': '进入多行输入模式，再次输入 ``` 或 <<< 结束',
            'multiline_detected': '检测到多行粘贴内容，自动进入多行模式',
            'blank_lines_tip': '（提示：可用两个空行快速结束输入）',
            'sql_detected_hint': '检测到SQL语句，进入多行模式（空行结束）',
            'unclosed_delimiter_hint': '检测到未闭合的引号/括号，进入多行模式',
            'multiline_manual_hint': '多行模式：行尾加 \\ 继续，{end_hint}结束',
            'end_hint_semicolon_or_empty': '分号(;)或空行',
            'end_hint_complete_statement': '完成语句后空行',
            'end_hint_empty_line': '空行',
            'end_hint_double_empty': '双空行',
            
            # tool_confirmation.py 相关
            'risk_low': '低',
            'risk_medium': '中',
            'risk_high': '高',
            'risk_critical': '危险',
            'tool_status_executing': '执行中...',
            'tool_status_completed': '已完成',
            'request_id': '请求ID',
            'awaiting_confirmation': '等待确认',
            'pending_tools': '待执行工具',
            
            # streaming.py 相关
            'code_block_detected': '检测到代码块',
            'code_language': '语言: {language}',
            
            # 工具输出相关 - database_connect_tool
            'db_connect_testing': '测试数据库连接...',
            'db_connect_detected_type': '检测到数据库类型: {db_type}',
            'db_connect_test_success': '连接测试成功!',
            'db_connect_test_failed': '连接测试失败',
            'db_connect_connecting': '正在连接数据库...',
            'db_connect_success': '数据库连接成功!',
            'db_connect_alias': '连接别名',
            'db_connect_type': '数据库类型',
            'db_connect_version': '版本',
            'db_connect_status': '状态',
            'db_connect_active': '已设为当前活动连接',
            'db_connect_overview': '数据库概览',
            'db_connect_table_count': '表数量',
            'db_connect_view_count': '视图数量',
            'db_connect_size': '数据库大小',
            'db_connect_table_count_label': '表数量',
            'db_connect_view_count_label': '视图数量',
            'db_connect_size_label': '数据库大小',
            'db_connect_switched': '已切换到数据库连接: {name}',
            'db_connect_switched_config': '已切换到数据库: {name}',
            'db_connect_check_supported': '检查支持的数据库类型...',
            'db_connect_driver_installed': '驱动已安装，可以使用',
            'db_connect_supported_title': '支持的数据库类型',
            'db_connect_available_db': '可用的数据库:',
            'db_connect_need_driver': '需要安装驱动的数据库:',
            'db_connect_example_title': '连接字符串示例:',
            'db_supported_types': '支持的数据库类型',
            'db_available': '可用的数据库:',
            'db_need_driver': '需要安装驱动的数据库:',
            'db_connection_examples': '连接字符串示例:',
            'db_test_success': '连接测试成功!',
            'db_test_failed': '连接测试失败',
            'db_connect_error': '连接失败',
            'db_connect_host': '主机',
            'db_connect_port': '端口',
            'db_connect_database': '数据库',
            'db_connect_unknown': '未知',
            'db_connect_error_reason': '可能的原因',
            'db_connect_error_suggest': '建议',
            'db_connect_check_service': '检查数据库服务状态',
            'db_connect_verify_string': '验证连接字符串格式',
            'db_connect_check_firewall': '确认防火墙设置',
            'db_connect_use_list': '使用 action=\'list\' 查看需要安装的驱动',
            'db_connect_need_connection_string': 'connect和test操作需要提供connection_string',
            'db_connect_need_database_name': 'switch操作需要提供database_name',
            'db_connect_action_connect': '连接到数据库: {cs}',
            'db_connect_action_test': '测试数据库连接',
            'db_connect_action_list': '列出支持的数据库类型',
            'db_connect_action_switch': '切换到数据库: {database_name}',
            'db_connect_action_default': '数据库操作',
            'db_connect_tool_name': '数据库连接器',
            
            # 工具输出相关 - schema_discovery
            'schema_discovery_getting': '获取数据库表名',
            'schema_discovery_pattern': '（匹配模式: {pattern}）',
            'schema_discovery_include_views': '，包含视图',
            'schema_discovery_getting_failed': '获取表名失败: {error}',
            'schema_discovery_failed': '获取表名失败',
            'schema_discovery_summary': '{db_type} {version} 数据库，包含{count}个表',
            'schema_discovery_summary_no_version': '{db_type} 数据库，包含{count}个表',
            'schema_discovery_db_name': '数据库名: {name}',
            'schema_discovery_tip': '提示: {tip}',
            'schema_discovery_object_list': '数据库对象列表:',
            'schema_discovery_table': '表',
            'schema_discovery_view': '视图',
            'schema_discovery_count': '({count}个):',
            
            # 工具输出相关 - database_export_tool
            'export_success': '导出成功',
            'export_file': '文件: {name}',
            'export_format': '格式: {format}',
            'export_rows': '数据行: {count}',
            'export_size': '文件大小: {size}',
            'export_mode_append': '追加到现有文件',
            
            # 工具输出相关 - file_read_tool
            'file_read_reading': '读取文件: {name}',
            'file_read_from_line': '(从第{line}行开始)',
            'file_read_limit_lines': '(限制{count}行)',
            'file_read_failed': '读取文件失败: {error}',
            'file_read_lines_read': '读取了 {count} 行',
            'file_read_total_lines': '总行数: {count}',
            'file_read_image': '图片文件: {name}',
            'file_read_binary': '二进制文件',
            'file_read_truncated': '... [截断]',
            'file_read_only_lines': '文件只有 {total} 行，但请求从第 {requested} 行开始读取',
            'file_read_sql_script': '读取SQL脚本: {name} ({lines}行)',
            'file_read_partial': '[部分内容]',
            'file_read_statement_count': '语句数: ~{count}',
            'file_read_type': '类型: {type}',
            'file_read_json': '读取JSON文件: {name}',
            'file_read_yaml': '读取YAML配置文件: {name}',
            'file_read_csv': '读取CSV文件: {name} ({rows}行数据)',
            'file_read_columns': '列数: {count}',
            'file_read_column_names': '列名: {names}',
            'file_read_data_rows': '数据行: {count}',
            'file_read_empty_csv': '空CSV文件',
            'file_read_structure': '结构: {structure}',
            'file_read_encoding': '编码: {encoding}',
            'file_read_file_size': '文件大小: {size}',
            'file_read_more_content': '文件有更多内容',
            
            # 工具输出相关 - code_execution_tool
            'code_exec_success': '{language}代码执行成功',
            'code_exec_time': '执行时间：{time:.2f}秒',
            'code_exec_output': '输出结果',
            'code_exec_error': '执行错误',
            'code_exec_variables': '定义的变量',
            'code_exec_created_files': '创建的文件',
            'code_exec_modified_files': '修改的文件',
            
            # 工具输出相关 - sql_tool
            'sql_exec_rows': '返回 {count} 行',
            'sql_exec_affected': '影响了 {count} 行',
            'sql_exec_success': '执行成功',
            'sql_exec_no_results': '查询未返回结果',
            'sql_exec_fields': '字段: {fields}',
            'sql_exec_sample': '数据样本',
            'sql_exec_more_rows': '... 还有 {count} 行',
            
            # 工具输出相关 - table_details_tool
            'table_details_structure': '表结构: {table}',
            'table_details_columns': '列信息',
            'table_details_indexes': '索引信息',
            'table_details_foreign_keys': '外键约束',
            'table_details_check_constraints': '检查约束',
            'table_details_row_count': '数据行数: {count}',
            'table_details_sample_data': '数据样本 (前{count}行)',
            'table_details_tool_name': '表结构详情',
            'table_details_get_description': '获取表结构详情: {table_name}',
            'table_details_stats_info': '统计信息',
            'table_details_include_extras': ' (包含: {extras})',
            'table_details_table_title': '表: {table_name}',
            'table_details_db_type': '数据库类型: {dialect}',
            'table_details_columns_info': '列信息:',
            'table_details_primary_key': '主键: {keys}',
            'table_details_statistics': '统计信息:',
            'table_details_size': '  - 大小: {size} MB',
            'table_details_sample_data_title': '样本数据:',
            'table_details_summary': '获取表 {table_name} 的完整结构信息',
            'table_details_table_not_found': "表 '{table_name}' 不存在",
            'table_details_suggestions': '。您是否想查看: {suggestions}',
            
            # 工具输出相关 - file_write_tool
            'file_write_tool_name': '文件写入',
            'file_write_written': '{icon} 已写入 {filename}',
            'file_write_size': '大小: {size}',
            'file_write_location': '位置: {location}',
            'file_write_compression': '压缩: {compression}',
            'file_write_duration': '耗时: {duration:.1f}秒',
        },
        'ja_JP': {
            # 日文翻译
            # 主程序消息
            'welcome_title': 'DbRheo CLI',
            'welcome_subtitle': 'データベースインテリジェントアシスタント',
            'help_hint': '/help でヘルプ情報を表示',
            'user_interrupt': 'ユーザー割り込み、終了中...',
            'error_occurred': 'エラーが発生しました: {error}',
            'signal_received': 'シグナル {signum} を受信しました、正常に終了中...',
            'debug_level_set': 'デバッグレベルを {level} に設定しました',
            'log_enabled': 'リアルタイムログが有効になりました',
            
            # CLI消息
            'unknown_command': '不明なコマンド: {command}',
            'debug_level_range': 'デバッグレベルは 0-5 の範囲で指定してください',
            'current_debug_level': '現在のデバッグレベル: {level}',
            'debug_usage': '使用法: /debug <0-5>',
            'debug_reload_warning': '警告: ログモジュールの再読み込みに失敗しました: {error}',
            'error_processing': 'メッセージ処理中にエラーが発生しました: {error}',
            'error_continuing': '確認後の続行中にエラーが発生しました: {error}',
            'tool_count': '今回の会話で {count} 個のツールを呼び出しました',
            
            # 语言相关
            'current_language': '現在の言語: {lang}',
            'language_set': '言語を {lang} に切り替えました',
            'language_not_supported': 'サポートされていない言語: {lang}',
            'language_usage': '使用法: /lang [zh|ja|en]',
            'available_languages': '使用可能な言語: zh（中国語）、ja（日本語）、en（英語）',
            
            # 帮助文本
            'help_title': '使用可能なコマンド',
            'help_exit': 'CLI を終了',
            'help_clear': '画面をクリア',
            'help_debug': 'デバッグレベルを設定',
            'help_lang': '表示言語を切り替え',
            'help_multiline': '複数行入力（``` または <<< で開始）',
            'help_esc': 'ESCキーで入力をクリア',
            'tool_confirmation_title': 'ツール確認',
            'tool_confirmation_help': '''ツール確認が必要な場合:
  - '1' または 'confirm' で実行を確認
  - '2' または 'cancel' で実行をキャンセル
  - 'confirm all' ですべての待機中ツールを確認''',
            
            # 工具相关
            'tool_confirm_title': 'ツール確認が必要です: {tool_name}',
            'risk_level': 'リスクレベル',
            'risk_description': 'リスクの説明',
            'risk_critical': '重大',
            'risk_high': '高',
            'risk_medium': '中',
            'risk_low': '低',
            'risk_dangerous_pattern': '危険な操作パターンを検出: {pattern}',
            'risk_high_operation': '高リスク操作：データの永久的な損失の可能性があります',
            'risk_no_where': 'WHERE条件なし：全データに影響する可能性があります',
            'risk_multiple_tables': '複数テーブル({count}個)：操作の複雑度が高い',
            'risk_large_table': '大規模テーブル操作({table})：パフォーマンスに影響する可能性',
            'risk_foreign_key': '外部キー制約に影響する可能性',
            'risk_full_scan': 'フルテーブルスキャンの可能性',
            'risk_complex_join': '複雑なJOIN操作({count}個)：パフォーマンスに影響する可能性',
            'risk_sql_injection': 'SQLインジェクションパターンを検出',
            'risk_recommend_test': 'テスト環境で事前に検証することを推奨します',
            'risk_recommend_where': 'WHERE条件を追加して影響範囲を限定することを推奨',
            'risk_recommend_backup': 'データのバックアップを先に作成することを推奨',
            'risk_recommend_index': '適切なインデックスまたはWHERE条件の追加を推奨',
            'parameters': 'パラメーター',
            'please_choose': '選択してください',
            'please_input': '入力してください',
            'confirm_execute': '実行を確認',
            'cancel_execute': '実行をキャンセル',
            'confirm_all_tools': 'すべての待機中ツールを確認',
            'tool_confirmed': 'ツールの実行を確認しました',
            'tool_rejected': 'ツールの実行をキャンセルしました',
            'tool_confirmed_all': 'すべてのツールの実行を確認しました',
            'tool_error': 'ツール確認時にエラーが発生しました: {error}',
            'tool_result': '実行結果',
            'tool_failed': '実行に失敗しました: {error}',
            'more_items': '... その他 {count} 項目',
            
            # 事件消息
            'max_session_turns': '最大会話ターン数に達しました',
            'chat_compressed': '会話履歴が圧縮されました',
            
            # 状态指示器
            'status_pending': '[保留中]',
            'status_confirm': '[確認]',
            'status_approved': '[承認済み]',
            'status_running': '[実行中]',
            'status_success': '[成功]',
            'status_error': '[エラー]',
            'status_cancelled': '[キャンセル]',
            'status_unknown': '[不明]',
            
            # 输入提示
            'clipboard_hint': '複数行テキストをコピー後Enterキーで自動貼り付け | または \'\'\'で複数行モード開始',
            'multiline_mode_hint': '複数行入力モードに入りました、再度 ``` または <<< で終了',
            'startup_tips_title': '使用のヒント:',
            'input_halfwidth_hint': '（半角数字で入力してください）',
            
            # 工具执行消息
            'tool_executing': 'ツール実行中: {tool_name}',
            
            # 系统状态消息
            'exiting': '終了中...',
            'cleaning_resources': 'リソースをクリーンアップ中...',
            
            # 启动提示
            'startup_tip_1': '1. 質問の提示、SQL実行、データ分析など多様な操作',
            'startup_tip_2': '2. 具体的な説明で最良の結果を取得',
            'startup_tip_3': '3. /help で詳細情報を表示',
            'startup_tip_4': '4. 対応データベース：SQLite、MySQL、PostgreSQL',
            'startup_tip_5': '5. Python実行環境を統合してデータ処理と可視化',
            'startup_tip_6': '6. 複数のAIモデルをサポート：Gemini、Claude、GPT (/model で切り替え)',
            'home_dir_warning': 'ホームディレクトリで DbRheo CLI を実行しています。プロジェクトディレクトリでの実行をお勧めします。',
            
            # モデル関連
            'model_switched': 'モデルを {model} に切り替えました',
            'model_switch_failed': 'モデルの切り替えに失敗しました: {error}',
            'current_model': '現在のモデル: {model}',
            'model_usage': '使用方法',
            'available_models': '利用可能なモデル',
            'latest': '最新',
            'reasoning': '推論強化',
            'fast': '高速',
            'default': 'デフォルト',
            'example': '例',
            'supported_models': 'サポートされているモデル：',
            'model_gemini': '- Gemini: gemini, gemini-2.5-flash, gemini-2.0',
            'model_claude': '- Claude: claude, sonnet, opus, sonnet4, opus4',
            'model_openai': '- OpenAI: gpt-4, gpt-4.1, o1, o3',
            'help_model': 'AIモデルを切り替える',
            
            # API Key 関連
            'api_key_missing': '⚠️  {model} の API Key が検出されませんでした',
            'api_key_setup': '.env ファイルに以下の環境変数を設定してください：',
            'api_key_gemini': 'GOOGLE_API_KEY または GEMINI_API_KEY',
            'api_key_claude': 'ANTHROPIC_API_KEY または CLAUDE_API_KEY',
            'api_key_openai': 'OPENAI_API_KEY',
            'api_key_instructions': 'API Key の取得はこちら：',
            'api_key_gemini_url': 'https://aistudio.google.com/apikey',
            'api_key_claude_url': 'https://console.anthropic.com/settings/keys',
            'api_key_openai_url': 'https://platform.openai.com/api-keys',
            'api_key_reminder': '設定後は CLI を再起動してください',
            
            # Token 統計関連
            'token_usage_title': 'Token 使用統計',
            'token_usage_total': '合計：{total} tokens ({calls} 回呼び出し)',
            'token_usage_detail': '├─ 入力：{prompt} tokens',
            'token_usage_detail_output': '└─ 出力：{completion} tokens',
            'token_usage_by_model': 'モデル別統計：',
            'token_usage_model_detail': '  {model}：{total} tokens ({calls} 回)',
            'token_command_hint': '/token を使用して現在の統計を表示',
            'help_token': 'Token 使用統計を表示',
            'token_statistics_unavailable': 'Token 統計機能は使用できません',
            'no_token_usage_yet': 'まだ Token 使用記録がありません',
            
            # cli.py 相关
            'esc_abort': 'ユーザーがESCを押しました、出力を中止中...',
            'traditional_layout': '従来のレイアウトモードを使用',
            'enhanced_layout': '拡張レイアウトモードを使用（下部固定入力ボックス）',
            'continuing': '処理を続行中...',
            'tool_calls_summary': '今回の会話で {count} 個のツールを呼び出しました: {tools}',
            'tool_calls_continue': '続行処理中に {count} 個のツールを呼び出しました: {tools}',
            'error_format': 'エラー: {error}',
            'enhanced_layout_shortcuts': 'ESC: クリア/終了  |  Ctrl+C: コピー後Enterで自動貼り付け  |  \'\'\': 複数行モード',
            
            # tool_handler.py 相关
            'executing_code': '実行予定の {param_key}:',
            'tool_success': 'ツール {name} が正常に実行されました',
            'tool_failed_with_error': 'ツール {name} の実行に失敗しました: {error}',
            'tool_cancelled': 'ツール {name} がキャンセルされました',
            'execution_result': '実行結果:',
            'rows_truncated': '... 他 {count} 行のデータ（切り捨て済み）',
            'total_rows': '合計 {count} 行',
            
            # simple_multiline_input.py 相关
            'paste_detect_error': '貼り付け検出エラー: {error}',
            'tkinter_unavailable': 'tkinterが利用できません、クリップボード機能は無効です',
            'tkinter_window_error': 'tkinterウィンドウを作成できません: {error}',
            'clipboard_read_error': 'クリップボードの読み取りに失敗しました: {error}',
            'clipboard_error': 'クリップボード機能の異常: {error}: {details}',
            'multiline_preview_title': '複数行入力のプレビュー',
            'multiline_traditional_hint': '複数行入力モードに入りました、再度 ``` または <<< で終了',
            'multiline_detected': '複数行の貼り付け内容を検出、自動的に複数行モードに入ります',
            'blank_lines_tip': '（ヒント：2つの空行で素早く入力を終了できます）',
            'sql_detected_hint': 'SQL文を検出、複数行モードに入ります（空行で終了）',
            'unclosed_delimiter_hint': '閉じられていない引用符/括弧を検出、複数行モードに入ります',
            'multiline_manual_hint': '複数行モード：行末に \\ で継続、{end_hint}で終了',
            'end_hint_semicolon_or_empty': 'セミコロン(;)または空行',
            'end_hint_complete_statement': '文の完成後に空行',
            'end_hint_empty_line': '空行',
            'end_hint_double_empty': '2つの空行',
            
            # tool_confirmation.py 相关
            'risk_low': '低',
            'risk_medium': '中',
            'risk_high': '高',
            'risk_critical': '危険',
            'tool_status_executing': '実行中...',
            'tool_status_completed': '完了',
            'request_id': 'リクエストID',
            'awaiting_confirmation': '確認待ち',
            'pending_tools': '待機中のツール',
            
            # streaming.py 相关
            'code_block_detected': 'コードブロックを検出',
            'code_language': '言語: {language}',
            
            # 工具输出相关 - database_connect_tool
            'db_connect_tool_name': 'データベース接続ツール',
            'db_connect_testing': 'データベース接続をテスト中...',
            'db_connect_detected_type': '検出されたデータベースタイプ: {db_type}',
            'db_connect_test_success': '接続テスト成功！',
            'db_connect_test_failed': '接続テスト失敗',
            'db_connect_connecting': 'データベースに接続中...',
            'db_connect_success': 'データベース接続成功！',
            'db_connect_alias': '接続エイリアス',
            'db_connect_type': 'データベースタイプ',
            'db_connect_version': 'バージョン',
            'db_connect_status': 'ステータス',
            'db_connect_active': 'アクティブ接続に設定されました',
            'db_connect_overview': 'データベース概要',
            'db_connect_table_count': 'テーブル数',
            'db_connect_view_count': 'ビュー数',
            'db_connect_size': 'データベースサイズ',
            'db_connect_table_count_label': 'テーブル数',
            'db_connect_view_count_label': 'ビュー数',
            'db_connect_size_label': 'データベースサイズ',
            'db_connect_switched': 'データベース接続を切り替えました: {name}',
            'db_connect_switched_config': 'データベースを切り替えました: {name}',
            'db_connect_check_supported': 'サポートされているデータベースタイプを確認中...',
            'db_connect_driver_installed': 'ドライバーがインストール済み、使用可能',
            'db_connect_supported_title': 'サポートされているデータベースタイプ',
            'db_connect_available_db': '使用可能なデータベース:',
            'db_connect_need_driver': 'ドライバーのインストールが必要なデータベース:',
            'db_connect_example_title': '接続文字列の例:',
            'db_connect_host': 'ホスト',
            'db_connect_port': 'ポート',
            'db_connect_database': 'データベース',
            'db_connect_unknown': '不明',
            'db_connect_error_reason': '考えられる原因',
            'db_connect_error_suggest': '提案',
            'db_connect_check_service': 'データベースサービスの状態を確認',
            'db_connect_verify_string': '接続文字列の形式を検証',
            'db_connect_check_firewall': 'ファイアウォール設定を確認',
            'db_connect_use_list': 'action=\'list\' を使用してインストールが必要なドライバーを表示',
            'db_connect_error': '接続失敗',
            'db_supported_types': 'サポートされているデータベースタイプ',
            'db_test_success': '接続テスト成功！',
            'db_test_failed': '接続テスト失敗',
            'db_connect_need_connection_string': 'connectとtest操作にはconnection_stringの指定が必要です',
            'db_connect_need_database_name': 'switch操作にはdatabase_nameの指定が必要です',
            'db_connect_action_connect': 'データベースに接続: {cs}',
            'db_connect_action_test': 'データベース接続をテスト',
            'db_connect_action_list': 'サポートされているデータベースタイプを一覧表示',
            'db_connect_action_switch': 'データベースを切り替え: {database_name}',
            'db_connect_action_default': 'データベース操作',
            'db_connection_examples': '接続文字列の例:',
            'db_need_driver': 'ドライバーのインストールが必要なデータベース',
            'db_connect_driver_ready': 'ドライバーがインストール済み',
            'db_connect_checking_types': '対応データベースタイプの確認中...',
            'db_connect_found_types': '検出されたデータベースタイプ',
            'db_available': '利用可能なデータベース',
            'db_connect_important_note': '重要：SQLツール使用時は、databaseパラメータにエイリアス \'{alias}\' を指定してください',
            'db_connect_example_usage': '例: sql_execute(sql="SELECT * FROM users", database="{alias}")',
            
            # 工具输出相关 - schema_discovery
            'schema_discovery_getting': 'データベーステーブル名を取得中',
            'schema_discovery_pattern': '（マッチングパターン: {pattern}）',
            'schema_discovery_include_views': '、ビューを含む',
            'schema_discovery_getting_failed': 'テーブル名の取得に失敗しました: {error}',
            'schema_discovery_failed': 'テーブル名の取得に失敗しました',
            'schema_discovery_summary': '{db_type} {version} データベース、{count}個のテーブルを含む',
            'schema_discovery_summary_no_version': '{db_type} データベース、{count}個のテーブルを含む',
            'schema_discovery_db_name': 'データベース名: {name}',
            'schema_discovery_tip': 'ヒント: {tip}',
            'schema_discovery_object_list': 'データベースオブジェクトリスト:',
            'schema_discovery_table': 'テーブル',
            'schema_discovery_view': 'ビュー',
            'schema_discovery_count': '({count}個):',
            
            # 工具输出相关 - database_export_tool
            'export_success': 'エクスポート完了',
            'export_file': 'ファイル: {name}',
            'export_format': 'フォーマット: {format}',
            'export_rows': 'データ行: {count}',
            'export_size': 'ファイルサイズ: {size}',
            'export_mode_append': '既存ファイルに追加',
            
            # 工具输出相关 - file_read_tool
            'file_read_reading': 'ファイルを読み込み中: {name}',
            'file_read_from_line': '({line}行目から開始)',
            'file_read_limit_lines': '({count}行に制限)',
            'file_read_failed': 'ファイル読み込み失敗: {error}',
            'file_read_lines_read': '{count} 行を読み込みました',
            'file_read_total_lines': '総行数: {count}',
            'file_read_image': '画像ファイル: {name}',
            'file_read_binary': 'バイナリファイル',
            'file_read_truncated': '... [省略]',
            'file_read_only_lines': 'ファイルは{total}行しかありませんが、{requested}行目から読み込むよう指定されました',
            'file_read_sql_script': 'SQLスクリプトを読み込み: {name} ({lines}行)',
            'file_read_partial': '[部分内容]',
            'file_read_statement_count': 'ステートメント数: ~{count}',
            'file_read_type': 'タイプ: {type}',
            'file_read_json': 'JSONファイルを読み込み: {name}',
            'file_read_yaml': 'YAML設定ファイルを読み込み: {name}',
            'file_read_csv': 'CSVファイルを読み込み: {name} ({rows}行のデータ)',
            'file_read_columns': '列数: {count}',
            'file_read_column_names': '列名: {names}',
            'file_read_data_rows': 'データ行: {count}',
            'file_read_empty_csv': '空CSVファイル',
            'file_read_structure': '構造: {structure}',
            'file_read_encoding': 'エンコーディング: {encoding}',
            'file_read_file_size': 'ファイルサイズ: {size}',
            'file_read_more_content': 'ファイルにはさらに内容があります',
            
            # 工具输出相关 - code_execution_tool
            'code_exec_tool_name': 'コード実行ツール',
            'code_exec_python_desc': 'Pythonコード（データ分析、自動化スクリプト）',
            'code_exec_js_desc': 'JavaScriptコード（Node.js環境）',
            'code_exec_shell_desc': 'Shellスクリプト（システムコマンド、ファイル操作）',
            'code_exec_sql_desc': 'SQLスクリプト（直接実行）',
            'code_exec_unsupported_lang': 'サポートされていない言語：{language}。サポート言語：{supported}',
            'code_exec_invalid_timeout': 'タイムアウトは1-300秒の範囲で指定してください',
            'code_exec_lang_danger': '{language}の危険な操作を含む：{pattern}',
            'code_exec_preview': '\n\nコードプレビュー：\n{code}...',
            'code_exec_running': '{language}コードを実行中...\n```{language}\n{code}\n```',
            'code_exec_success_summary': '{language}コード実行成功',
            'code_exec_exception': 'コード実行例外：{error}\n{trace}',
            'code_exec_failed': 'コード実行失敗',
            'code_exec_context_comment': '# 自動注入されたコンテキスト',
            'code_exec_sql_result_comment': '# SQLクエリ結果',
            'code_exec_dataframe_comment': '# テーブルデータの場合、自動的にDataFrameに変換',
            'code_exec_user_code_sep': '\n\n# ユーザーコード\n',
            'code_exec_js_context_comment': '// 自動注入されたコンテキスト',
            'code_exec_js_sql_comment': '// SQLクエリ結果',
            'code_exec_js_user_code_sep': '\n\n// ユーザーコード\n',
            'code_exec_lang_not_supported': 'サポートされていない言語：{language}',
            'code_exec_output_truncated': '\n... [出力は切り詰められました]',
            'code_exec_error_truncated': '\n... [エラー出力は切り詰められました]',
            'code_exec_confirm_title': '{language}コードの実行を確認',
            'code_exec_danger_detected': '潜在的に危険な操作を検出しました',
            'code_exec_error_syntax': '構文エラー',
            'code_exec_error_syntax_suggest': 'コード構文を確認してください：括弧の対応、インデント、コロンなど',
            'code_exec_timeout': 'タイムアウト: {timeout}秒',
            'code_exec_failed': 'コード実行失敗: {error}',
            'code_exec_error_module': 'モジュールエラー',
            'code_exec_error_module_suggest': 'モジュールがインストールされているか確認してください',
            'code_exec_error_runtime': 'ランタイムエラー',
            'code_exec_error_runtime_suggest': '変数、データ型、配列インデックスを確認してください',
            'code_exec_description': '{language}コードを実行',
            'code_exec_empty': 'コードを指定してください',
            'code_exec_success': '{language}コード実行成功',
            'code_exec_success_title': '{language}コード実行成功',
            'code_exec_time': '実行時間：{time:.2f}秒',
            'code_exec_output': '出力結果',
            'code_exec_error': '実行エラー',
            'code_exec_stdout_title': '### 標準出力：',
            'code_exec_stderr_title': '### 標準エラー：',
            'code_exec_failed_title': '{language}コード実行失敗',
            'code_exec_failed_summary': '{language}コード実行失敗：{error_type}',
            'code_exec_failed_display': '実行失敗\n\n{error}',
            'code_exec_error_title': '### エラー情報：',
            'code_exec_variables': '定義された変数',
            'code_exec_created_files': '作成されたファイル',
            'code_exec_modified_files': '変更されたファイル',
            
            # 工具输出相关 - sql_tool
            'sql_tool_name': 'SQL実行ツール',
            'sql_exec_rows': '{count} 行を返しました',
            'sql_exec_affected': '{count} 行に影響を与えました',
            'sql_exec_success': '実行成功',
            'sql_exec_no_results': 'クエリは結果を返しませんでした',
            'sql_exec_fields': 'フィールド: {fields}',
            'sql_exec_sample': 'データサンプル',
            'sql_exec_more_rows': '... さらに {count} 行あります',
            'sql_confirm_title': '{operation}操作の実行を確認',
            'sql_execution_failed': 'SQL実行失敗: {error}',
            'sql_dangerous_no_where': '警告: WHERE条件なしの{type}操作は全データに影響します',
            'sql_execution_time': '実行時間: {time}',
            'sql_processing': 'SQL処理中...',
            'sql_mode_execute': '実行モード',
            'sql_mode_validate': '検証モード',
            'sql_mode_dry_run': 'ドライランモード',
            'sql_executing_query': 'クエリ実行中...',
            'sql_executing_command': 'コマンド実行中...',
            'sql_affected_rows': '影響を受けた行数: {rows}',
            'sql_empty_error': 'SQLクエリが空です',
            'sql_op_insert': '挿入',
            'sql_op_update': '更新',
            'sql_op_delete': '削除',
            'sql_op_create': '作成',
            'sql_op_alter': '変更',
            'sql_op_drop': '削除',
            'sql_op_dml': 'データ操作',
            'sql_op_ddl': '構造定義',
            'sql_op_generic': '{type}操作',
            'sql_type_label': 'SQLタイプ: {type}',
            'sql_query_success': 'クエリ成功、{count}行のデータを返しました',
            'sql_query_no_data': 'クエリ完了、データなし。\n実行時間: {time:.2f}秒',
            'sql_query_result_header': 'クエリが{count}行を返しました（実行時間: {time:.2f}秒）\n',
            'sql_feature_disabled': '機能が無効です',
            'sql_validate_disabled_error': 'validateモードは無効です。安全なSQL実行にはdry_runモードを使用するか、直接実行してデータベースエンジンで構文を検証してください。',
            'sql_validate_disabled_llm': 'validateモードは無効です。dry_runを使用してください。',
            'sql_dry_run_no_transaction': '現在のデータベースはトランザクションをサポートしていないため、dry_runモードを実行できません',
            'sql_dry_run_unavailable': 'ドライランは利用できません',
            'sql_dry_run_query_success': '[DRY RUN] クエリ成功、{count}行のデータを返しました',
            'sql_dry_run_mode_prefix': 'DRY RUN モード',
            'sql_dry_run_mode_rollback': 'DRY RUN モード（ロールバック済み）',
            'sql_dry_run_rollback_notice': 'すべての変更がロールバックされ、データベースは変更されていません',
            'sql_dry_run_summary_rollback': '[DRY RUN] {summary}（ロールバック済み）',
            'sql_dry_run_failed_error': 'ドライラン実行失敗: {error}',
            'sql_dry_run_failed_summary': 'ドライラン失敗',
            'sql_dry_run_failed_display': 'ドライラン実行失敗: {error}',
            
            # 工具输出相关 - table_details_tool
            'table_details_structure': 'テーブル構造: {table}',
            'table_details_columns': 'カラム情報',
            'table_details_indexes': 'インデックス情報',
            'table_details_foreign_keys': '外部キー制約',
            'table_details_check_constraints': 'チェック制約',
            'table_details_row_count': 'データ行数: {count}',
            'table_details_sample_data': 'データサンプル (先頭{count}行)',
            'table_details_tool_name': 'テーブル構造詳細',
            'table_details_get_description': 'テーブル構造詳細を取得: {table_name}',
            'table_details_stats_info': '統計情報',
            'table_details_include_extras': ' (含む: {extras})',
            'table_details_table_title': 'テーブル: {table_name}',
            'table_details_db_type': 'データベースタイプ: {dialect}',
            'table_details_columns_info': 'カラム情報:',
            'table_details_primary_key': '主キー: {keys}',
            'table_details_statistics': '統計情報:',
            'table_details_row_count': '  - 行数: {count:,}',
            'table_details_size': '  - サイズ: {size} MB',
            'table_details_sample_data_title': 'サンプルデータ:',
            'table_details_summary': 'テーブル {table_name} の完全な構造情報を取得',
            'table_details_table_not_found': "テーブル '{table_name}' は存在しません",
            'table_details_suggestions': '。次を確認しますか: {suggestions}',
            
            # 工具输出相关 - file_write_tool
            'file_write_tool_name': 'ファイル書き込み',
            'file_write_written': '{icon} {filename} に書き込みました',
            'file_write_path_empty': 'ファイルパスを指定してください',
            'file_write_confirm_overwrite': '{filename} を上書きしますか？',
            'file_write_access_denied': 'アクセス拒否: {path} は許可されたディレクトリ外です。\n\n許可されたディレクトリ:\n{dirs}\n\nファイルパスを確認し、許可されたディレクトリ内のパスで再試行してください。',
            'file_write_creating_progress': '新規ファイル作成中...',
            'file_write_appending_progress': 'ファイルに追記中...',
            'file_write_failed': 'ファイル書き込み失敗: {error}',
            'file_write_content_none': 'コンテンツを指定してください',
            'file_write_dangerous_path': '警告: このパスは重要なシステムファイルです',
            'file_write_size': 'サイズ: {size}',
            'file_write_location': '場所: {location}',
            'file_write_compression': '圧縮: {compression}',
            'file_write_duration': '処理時間: {duration:.1f}秒',
            
            # 其他缺失的工具名称
            'schema_tool_name': 'テーブル発見ツール',
            'file_read_tool_name': 'ファイル読み込み',
            'file_read_access_denied': 'アクセス拒否: {path} は許可されたディレクトリ外です。\n\n許可されたディレクトリ:\n{dirs}\n\nファイルパスを確認し、許可されたディレクトリ内のパスで再試行してください。',
            'file_read_path_empty': 'ファイルパスを指定してください',
            'file_read_not_found': 'ファイルが見つかりません: {path}',
            'file_read_not_file': '{path} はファイルではありません',
            'file_read_too_large': 'ファイルが大きすぎます: {size}。分割読み込みを使用してください',
            'file_read_lines_count': '行数: {count}',
            'file_read_json_invalid': '無効なJSONファイル: {error}',
            'file_read_yaml_invalid': '無効なYAMLファイル: {error}',
            'file_read_csv_empty': 'CSVファイルが空です',
            'file_read_sql_found': 'SQLファイルを検出、{count}個のステートメントを含む',
            'file_read_sql_content': 'SQLスクリプト内容:\n\n{content}',
            'file_read_offset_suffix': ' (第{line}行から)',
            'file_read_offset_out_of_range': '[ファイルは{total}行しかありませんが、第{line}行から読み込むよう指定されました]\n',
            'file_read_sql_summary': 'SQLスクリプトを読み込み: {filename} ({lines}行)',
            'file_read_partial_suffix': ' [部分内容]',
            'file_read_sql_statements': 'ステートメント数: ~{count}',
            'file_read_sql_types': 'タイプ: {types}',
            'file_read_text_read': '{filename} を読み込み',
            'file_read_text_from_line': '第{line}行から',
            'file_read_text_lines': '{lines}行',
            'file_read_text_partial': '部分内容',
            'file_read_partial_content': '[ファイル部分内容: {context}]\n\n{content}',
            'file_read_use_pagination': '\n[offsetとlimitパラメータを使用してさらに内容を読み込めます]',
            'export_tool_name': 'データエクスポート',
            'export_path_empty': '出力パスを指定してください',
            'export_path_not_allowed': '{path} へのエクスポートは許可されていません',
            'export_path_invalid': '無効な出力パス: {error}',
            'export_format_unsupported': 'サポートされていないファイル形式: {format}',
            'export_confirm_overwrite_title': 'ファイル上書きの確認',
            'export_confirm_overwrite_message': 'ファイル {filename} は既に存在します。上書きしますか？',
            'export_confirm_overwrite_details': 'フルパス: {path}',
            'export_progress': '{format} 形式でデータをエクスポート中...\nファイル: {filename}',
            'export_rows_progress': '{count:,} 行をエクスポート済み...',
            'export_sql_empty': 'SQLクエリを指定してください',
            'export_sql_failed': 'SQLエクスポート失敗: {error}',
            'export_csv_failed': 'CSVエクスポート失敗: {error}',
            'export_json_failed': 'JSONエクスポート失敗: {error}',
            'export_excel_failed': 'Excelエクスポート失敗: {error}',
            'export_excel_missing_lib': 'Excelエクスポートにはopenpyxlライブラリが必要です',
            'export_failed_display': 'エクスポート失敗',
            'export_failed_error': 'エクスポートエラー: {error}',
            'export_failed_summary': 'データエクスポート失敗',
            'web_search_tool_name': 'ウェブ検索',
            'web_search_query_empty': '検索クエリを指定してください',
            'web_search_failed': '{backend}での検索失敗: {error}',
            'web_search_failed_display': '検索失敗',
            'web_search_no_results': '結果が見つかりませんでした',
            'web_search_no_results_llm': '{backend}で \'{query}\' の検索結果が見つかりませんでした',
            'web_search_no_results_display': '検索結果なし',
            'web_search_no_results_text': '検索結果が見つかりませんでした。',
            'web_search_searching': '検索中: {query}',
            'web_search_found_results': '{count}件の結果が見つかりました',
            'web_search_results_header': '検索結果:',
            'web_search_result_url': 'URL: {url}',
            'web_search_result_summary': '{title}\n{snippet}',
            'web_search_description': 'ウェブを検索',
            'web_search_no_desc': '説明なし',
            'web_search_fallback': '代替検索エンジンに切り替えています...',
            'web_search_results_footer': '検索結果は以上です',
            'web_search_display_header': '検索結果: {query}',
            'web_fetch_tool_name': 'ウェブコンテンツ取得',
            'web_fetch_invalid_url': '無効なURL: {url}',
            'web_fetch_risk_private': '内部ネットワークリソースへのアクセス',
            'web_fetch_confirm_private': '内部ネットワークへのアクセスを確認',
            'web_fetch_no_urls': 'URLを指定してください',
            'web_fetch_no_urls_error': 'URLリストが空です',
            'web_fetch_too_many_urls': 'URLが多すぎます（最大{max}個）',
            'web_fetch_progress': 'URL {current}/{total} を取得中...',
            'web_fetch_all_failed': 'すべてのURL取得に失敗しました',
            'web_fetch_success_count': '{count}個のURL取得成功',
            'web_fetch_fail_count': '{count}個のURL取得失敗',
            'web_fetch_results_header': '取得結果:',
            'web_fetch_summary': '{success}個成功、{fail}個失敗',
            'web_fetch_summary_errors': '{success}個成功、{fail}個失敗\n\nエラー:\n{errors}',
            'web_fetch_error_line': '- {url}: {error}',
            'web_fetch_content_truncated': '[コンテンツは切り詰められました]',
            'web_fetch_desc_single': 'URLからコンテンツを取得',
            'web_fetch_desc_multiple': '複数のURLからコンテンツを取得',
            'web_fetch_preview': 'プレビュー: {preview}...',
            'dir_list_tool_name': 'ディレクトリブラウザ',
            'dir_list_path_empty': 'ディレクトリパスを指定してください',
            'dir_list_access_denied': 'アクセス拒否: {path} は許可されたディレクトリ外です',
            'dir_list_access_denied_detail': 'アクセス拒否: {path} は許可されたディレクトリ外です。\n\n許可されたディレクトリ:\n{dirs}\n\nディレクトリパスを確認し、許可されたディレクトリ内のパスで再試行してください。',
            'dir_list_not_directory': 'パスはディレクトリではありません: {path}',
            'dir_list_failed': 'ディレクトリ一覧の取得に失敗: {error}',
            'dir_list_result_summary': '{path} 内の {count} 個の項目を表示',
            'dir_list_not_found': 'ディレクトリが見つかりません: {path}',
            'dir_list_invalid_path': '無効なパス: {path}',
            'dir_list_base_path': 'ベースパス: {path}',
            'dir_list_pattern_suffix': ' (パターン: {pattern})',
            'dir_list_recursive_suffix': ' [再帰的]',
            'dir_list_total_suffix': ' (合計: {total})',
            'dir_list_truncated': '... さらに {count} 個の項目があります',
            'dir_list_summary': '{path} のディレクトリ内容を一覧表示',
            'dir_list_description': 'ディレクトリ内容を一覧表示',
            'dir_list_invalid_pattern': '無効なパターン: {pattern}',
            'shell_tool_name': 'Shell実行ツール',
            'shell_confirm_title': 'Shellコマンドの実行を確認',
            'shell_command_empty': 'コマンドを指定してください',
            'shell_execution_error': '実行エラー: {error}',
            'shell_security_check_failed': 'セキュリティチェック失敗: {reason}',
            'shell_timeout_message': '実行タイムアウト {timeout}秒',
            'shell_blocked_summary': 'コマンドはセキュリティポリシーによりブロックされました',
            'shell_command_blacklisted': 'コマンド \'{command}\' は実行が禁止されています',
            'shell_command_not_whitelisted': '厳格モードでは、コマンド \'{command}\' は許可リストにありません',
            'shell_dir_not_exist': 'ディレクトリが存在しません: {dir}',
            'shell_path_not_dir': 'パスはディレクトリではありません: {dir}',
            'shell_invalid_timeout': '無効なタイムアウト値: {timeout}',
            'shell_executing': 'コマンド実行中: {command}',
            'shell_exit_code': '終了コード: {code}',
            'shell_execution_time': '実行時間: {time:.2f}秒',
            'shell_stdout_header': '### 標準出力:',
            'shell_stderr_header': '### 標準エラー:',
            'shell_error_header': '### エラー:',
            'shell_success_title': 'Shell命令実行成功',
            'shell_success_summary': 'Shellコマンドが正常に実行されました (終了コード: {code})',
            'shell_failed_title': 'コマンド実行失敗',
            'shell_failed_summary': 'Shellコマンドの実行に失敗しました',
            'shell_failed_display': 'コマンド実行失敗: {error}'
        },
        'en_US': {
            # English translations
            # 主程序消息
            'welcome_title': 'DbRheo CLI',
            'welcome_subtitle': 'Database Intelligence Assistant',
            'help_hint': 'Type /help for help information',
            'user_interrupt': 'User interrupted, exiting...',
            'error_occurred': 'Error occurred: {error}',
            'signal_received': 'Received signal {signum}, shutting down gracefully...',
            'debug_level_set': 'Debug level set to {level}',
            'log_enabled': 'Realtime logging enabled',
            
            # CLI消息
            'unknown_command': 'Unknown command: {command}',
            'debug_level_range': 'Debug level must be between 0-5',
            'current_debug_level': 'Current debug level: {level}',
            'debug_usage': 'Usage: /debug <0-5>',
            'debug_reload_warning': 'Warning: Failed to reload logging module: {error}',
            'error_processing': 'Error processing message: {error}',
            'error_continuing': 'Error continuing after confirmation: {error}',
            'tool_count': 'Called {count} tools in this conversation',
            
            # 语言相关
            'current_language': 'Current language: {lang}',
            'language_set': 'Language switched to: {lang}',
            'language_not_supported': 'Unsupported language: {lang}',
            'language_usage': 'Usage: /lang [zh|ja|en]',
            'available_languages': 'Available languages: zh (Chinese), ja (Japanese), en (English)',
            
            # 帮助文本
            'help_title': 'Available commands',
            'help_exit': 'Exit CLI',
            'help_clear': 'Clear screen',
            'help_debug': 'Set debug level',
            'help_lang': 'Switch display language',
            'help_multiline': 'Multiline input (start with ``` or <<<)',
            'help_esc': 'Press ESC to clear input',
            'tool_confirmation_title': 'Tool Confirmation',
            'tool_confirmation_help': '''When tool confirmation is required:
  - Enter '1' or 'confirm' to confirm execution
  - Enter '2' or 'cancel' to cancel execution
  - Enter 'confirm all' to confirm all pending tools''',
            
            # 工具相关
            'tool_confirm_title': 'Tool requires confirmation: {tool_name}',
            'risk_level': 'Risk Level',
            'risk_description': 'Risk Description',
            'parameters': 'Parameters',
            'please_choose': 'Please choose',
            'please_input': 'Please input',
            'confirm_execute': 'Confirm execution',
            'cancel_execute': 'Cancel execution',
            'confirm_all_tools': 'Confirm all pending tools',
            'tool_confirmed': 'Tool execution confirmed',
            'tool_rejected': 'Tool execution cancelled',
            'tool_confirmed_all': 'All tools execution confirmed',
            'tool_error': 'Error confirming tool: {error}',
            'tool_result': 'Execution Result',
            'tool_failed': 'Execution failed: {error}',
            'more_items': '... {count} more items',
            
            # 事件消息
            'max_session_turns': 'Maximum session turns reached',
            'chat_compressed': 'Chat history compressed',
            
            # 状态指示器
            'status_pending': '[Pending]',
            'status_confirm': '[Confirm]',
            'status_approved': '[Approved]',
            'status_running': '[Running]',
            'status_success': '[Success]',
            'status_error': '[Error]',
            'status_cancelled': '[Cancelled]',
            'status_unknown': '[Unknown]',
            
            # 输入提示
            'clipboard_hint': 'Copy multiline text and press Enter to auto-paste | Or type \'\'\' to start multiline mode',
            'multiline_mode_hint': 'Entering multiline input mode, type ``` or <<< again to finish',
            'startup_tips_title': 'Tips:',
            'input_halfwidth_hint': '(Please enter half-width numbers for Japanese systems)',
            
            # 工具执行消息
            'tool_executing': 'Executing tool: {tool_name}',
            
            # 系统状态消息
            'exiting': 'Exiting...',
            'cleaning_resources': 'Cleaning up resources...',
            
            # 启动提示
            'startup_tip_1': '1. Ask questions, execute SQL queries, analyze data and more',
            'startup_tip_2': '2. Use specific descriptions for best results',
            'startup_tip_3': '3. Type /help for more information',
            'startup_tip_4': '4. Supported databases: SQLite, MySQL, PostgreSQL',
            'startup_tip_5': '5. Integrated Python runtime for data processing and visualization',
            'startup_tip_6': '6. Support for multiple AI models: Gemini, Claude, GPT (/model to switch)',
            'home_dir_warning': 'You are running DbRheo CLI in your home directory. It is recommended to run in a project directory.',
            
            # Model related
            'model_switched': 'Switched to model: {model}',
            'model_switch_failed': 'Failed to switch model: {error}',
            'current_model': 'Current model: {model}',
            'model_usage': 'Usage',
            'available_models': 'Available models',
            'latest': 'latest',
            'reasoning': 'reasoning',
            'fast': 'fast',
            'default': 'default',
            'example': 'Example',
            'supported_models': 'Supported models:',
            'model_gemini': '- Gemini: gemini, gemini-2.5-flash, gemini-2.0',
            'model_claude': '- Claude: claude, sonnet, opus, sonnet4, opus4',
            'model_openai': '- OpenAI: gpt-4, gpt-4.1, o1, o3',
            'help_model': 'Switch AI model',
            
            # API Key related
            'api_key_missing': '⚠️  No API Key detected for {model}',
            'api_key_setup': 'Please set the following environment variable in .env file:',
            'api_key_gemini': 'GOOGLE_API_KEY or GEMINI_API_KEY',
            'api_key_claude': 'ANTHROPIC_API_KEY or CLAUDE_API_KEY',
            'api_key_openai': 'OPENAI_API_KEY',
            'api_key_instructions': 'Get your API Key at:',
            'api_key_gemini_url': 'https://aistudio.google.com/apikey',
            'api_key_claude_url': 'https://console.anthropic.com/settings/keys',
            'api_key_openai_url': 'https://platform.openai.com/api-keys',
            'api_key_reminder': 'Please restart CLI after setup',
            
            # Token statistics
            'token_usage_title': 'Token Usage Statistics',
            'token_usage_total': 'Total: {total} tokens ({calls} calls)',
            'token_usage_detail': '├─ Input: {prompt} tokens',
            'token_usage_detail_output': '└─ Output: {completion} tokens',
            'token_usage_by_model': 'By Model:',
            'token_usage_model_detail': '  {model}: {total} tokens ({calls} calls)',
            'token_command_hint': 'Use /token to view current statistics',
            'help_token': 'View token usage statistics',
            'token_statistics_unavailable': 'Token statistics not available',
            'no_token_usage_yet': 'No token usage recorded yet',
            
            # cli.py 相关
            'esc_abort': 'User pressed ESC, aborting output...',
            'traditional_layout': 'Using traditional layout mode',
            'enhanced_layout': 'Using enhanced layout mode (fixed input box at bottom)',
            'continuing': 'Continuing...',
            'tool_calls_summary': 'Called {count} tools in this conversation: {tools}',
            'tool_calls_continue': 'Called {count} tools during continuation: {tools}',
            'error_format': 'Error: {error}',
            'enhanced_layout_shortcuts': 'ESC: Clear/Exit  |  Ctrl+C: Copy then Enter to auto-paste  |  \'\'\': Multiline mode',
            
            # tool_handler.py 相关
            'executing_code': 'About to execute {param_key}:',
            'tool_success': 'Tool {name} executed successfully',
            'tool_failed_with_error': 'Tool {name} execution failed: {error}',
            'tool_cancelled': 'Tool {name} cancelled',
            'execution_result': 'Execution result:',
            'rows_truncated': '... {count} more rows (truncated)',
            'total_rows': 'Total {count} rows',
            
            # simple_multiline_input.py 相关
            'paste_detect_error': 'Paste detection error: {error}',
            'tkinter_unavailable': 'tkinter unavailable, clipboard functionality disabled',
            'tkinter_window_error': 'Cannot create tkinter window: {error}',
            'clipboard_read_error': 'Failed to read clipboard: {error}',
            'clipboard_error': 'Clipboard functionality error: {error}: {details}',
            'multiline_preview_title': 'Multiline Input Preview',
            'multiline_traditional_hint': 'Entering multiline input mode, type ``` or <<< again to finish',
            'multiline_detected': 'Multiline paste detected, automatically entering multiline mode',
            'blank_lines_tip': '(Tip: Use two blank lines to quickly finish input)',
            'sql_detected_hint': 'SQL statement detected, entering multiline mode (blank line to finish)',
            'unclosed_delimiter_hint': 'Unclosed quote/bracket detected, entering multiline mode',
            'multiline_manual_hint': 'Multiline mode: Use \\ at line end to continue, {end_hint} to finish',
            'end_hint_semicolon_or_empty': 'semicolon (;) or blank line',
            'end_hint_complete_statement': 'blank line after completing statement',
            'end_hint_empty_line': 'blank line',
            'end_hint_double_empty': 'double blank lines',
            
            # tool_confirmation.py 相关
            'risk_low': 'Low',
            'risk_medium': 'Medium',
            'risk_high': 'High',
            'risk_critical': 'Critical',
            'tool_status_executing': 'Executing...',
            'tool_status_completed': 'Completed',
            'request_id': 'Request ID',
            'awaiting_confirmation': 'Awaiting Confirmation',
            'pending_tools': 'Pending Tools',
            
            # streaming.py 相关
            'code_block_detected': 'Code block detected',
            'code_language': 'Language: {language}',
            
            # 工具输出相关 - database_connect_tool
            'db_connect_tool_name': 'Database Connector',
            'db_connect_testing': 'Testing database connection...',
            'db_connect_detected_type': 'Detected database type: {db_type}',
            'db_connect_test_success': 'Connection test successful!',
            'db_connect_test_failed': 'Connection test failed',
            'db_connect_connecting': 'Connecting to database...',
            'db_connect_success': 'Database connection successful!',
            'db_connect_alias': 'Connection Alias',
            'db_connect_type': 'Database Type',
            'db_connect_version': 'Version',
            'db_connect_status': 'Status',
            'db_connect_active': 'Set as active connection',
            'db_connect_overview': 'Database Overview',
            'db_connect_table_count': 'Table Count',
            'db_connect_view_count': 'View Count',
            'db_connect_size': 'Database Size',
            'db_connect_table_count_label': 'Table Count',
            'db_connect_view_count_label': 'View Count',
            'db_connect_size_label': 'Database Size',
            'db_connect_switched': 'Switched to database connection: {name}',
            'db_connect_switched_config': 'Switched to database: {name}',
            'db_connect_check_supported': 'Checking supported database types...',
            'db_connect_driver_installed': 'Driver installed, ready to use',
            'db_connect_supported_title': 'Supported Database Types',
            'db_connect_available_db': 'Available databases:',
            'db_connect_need_driver': 'Databases requiring driver installation:',
            'db_connect_example_title': 'Connection string examples:',
            'db_connect_host': 'Host',
            'db_connect_port': 'Port',
            'db_connect_database': 'Database',
            'db_connect_unknown': 'Unknown',
            'db_connect_error_reason': 'Possible causes',
            'db_connect_error_suggest': 'Suggestions',
            'db_connect_check_service': 'Check database service status',
            'db_connect_verify_string': 'Verify connection string format',
            'db_connect_check_firewall': 'Check firewall settings',
            'db_connect_use_list': 'Use action=\'list\' to view drivers that need installation',
            
            # 工具输出相关 - schema_discovery
            'schema_discovery_getting': 'Getting database table names',
            'schema_discovery_pattern': '(matching pattern: {pattern})',
            'schema_discovery_include_views': ', including views',
            'schema_discovery_getting_failed': 'Failed to get table names: {error}',
            'schema_discovery_failed': 'Failed to get table names',
            'schema_discovery_summary': '{db_type} {version} database, containing {count} tables',
            'schema_discovery_summary_no_version': '{db_type} database, containing {count} tables',
            'schema_discovery_db_name': 'Database name: {name}',
            'schema_discovery_tip': 'Tip: {tip}',
            'schema_discovery_object_list': 'Database object list:',
            'schema_discovery_table': 'Table',
            'schema_discovery_view': 'View',
            'schema_discovery_count': '({count} items):',
            
            # 工具输出相关 - database_export_tool
            'export_success': 'Export successful',
            'export_file': 'File: {name}',
            'export_format': 'Format: {format}',
            'export_rows': 'Data rows: {count}',
            'export_size': 'File size: {size}',
            'export_mode_append': 'Append to existing file',
            
            # 工具输出相关 - file_read_tool
            'file_read_reading': 'Reading file: {name}',
            'file_read_from_line': '(starting from line {line})',
            'file_read_limit_lines': '(limited to {count} lines)',
            'file_read_failed': 'Failed to read file: {error}',
            'file_read_lines_read': 'Read {count} lines',
            'file_read_total_lines': 'Total lines: {count}',
            'file_read_image': 'Image file: {name}',
            'file_read_binary': 'Binary file',
            'file_read_truncated': '... [truncated]',
            'file_read_only_lines': 'File only has {total} lines, but requested to start from line {requested}',
            'file_read_sql_script': 'Reading SQL script: {name} ({lines} lines)',
            'file_read_partial': '[partial content]',
            'file_read_statement_count': 'Statement count: ~{count}',
            'file_read_type': 'Type: {type}',
            'file_read_json': 'Reading JSON file: {name}',
            'file_read_yaml': 'Reading YAML config file: {name}',
            'file_read_csv': 'Reading CSV file: {name} ({rows} rows of data)',
            'file_read_columns': 'Column count: {count}',
            'file_read_column_names': 'Column names: {names}',
            'file_read_data_rows': 'Data rows: {count}',
            'file_read_empty_csv': 'Empty CSV file',
            'file_read_structure': 'Structure: {structure}',
            'file_read_encoding': 'Encoding: {encoding}',
            'file_read_file_size': 'File size: {size}',
            'file_read_more_content': 'File has more content',
            
            # 工具输出相关 - code_execution_tool
            'code_exec_success': '{language} code execution successful',
            'code_exec_time': 'Execution time: {time:.2f} seconds',
            'code_exec_output': 'Output result',
            'code_exec_error': 'Execution error',
            'code_exec_variables': 'Defined variables',
            'code_exec_created_files': 'Created files',
            'code_exec_modified_files': 'Modified files',
            
            # 工具输出相关 - sql_tool
            'sql_exec_rows': 'Returned {count} rows',
            'sql_exec_affected': 'Affected {count} rows',
            'sql_exec_success': 'Execution successful',
            'sql_exec_no_results': 'Query returned no results',
            'sql_exec_fields': 'Fields: {fields}',
            'sql_exec_sample': 'Data sample',
            'sql_exec_more_rows': '... {count} more rows',
            
            # 工具输出相关 - table_details_tool
            'table_details_structure': 'Table structure: {table}',
            'table_details_columns': 'Column information',
            'table_details_indexes': 'Index information',
            'table_details_foreign_keys': 'Foreign key constraints',
            'table_details_check_constraints': 'Check constraints',
            'table_details_row_count': 'Data row count: {count}',
            'table_details_sample_data': 'Sample data (first {count} rows)',
            'table_details_tool_name': 'Table Structure Details',
            'table_details_get_description': 'Get table structure details: {table_name}',
            'table_details_stats_info': 'Statistics information',
            'table_details_include_extras': ' (includes: {extras})',
            'table_details_table_title': 'Table: {table_name}',
            'table_details_db_type': 'Database type: {dialect}',
            'table_details_columns_info': 'Column information:',
            'table_details_primary_key': 'Primary key: {keys}',
            'table_details_statistics': 'Statistics:',
            'table_details_size': '  - Size: {size} MB',
            'table_details_sample_data_title': 'Sample data:',
            'table_details_summary': 'Get complete structure information for table {table_name}',
            'table_details_table_not_found': "Table '{table_name}' does not exist",
            'table_details_suggestions': '. Did you mean to view: {suggestions}',
            
            # 工具输出相关 - file_write_tool
            'file_write_tool_name': 'File Writing',
            'file_write_written': '{icon} Written to {filename}',
            'file_write_size': 'Size: {size}',
            'file_write_location': 'Location: {location}',
            'file_write_compression': 'Compression: {compression}',
            'file_write_duration': 'Duration: {duration:.1f} seconds',
            
            # 其他缺失的工具名称
            'schema_tool_name': 'Table Discovery Tool',
            'file_read_tool_name': 'File Reader',
            'export_tool_name': 'Data Export',
            'code_exec_tool_name': 'Code Execution Tool',
            'sql_tool_name': 'SQL Executor',
            'web_search_tool_name': 'Web Search',
            'web_fetch_tool_name': 'Web Content Fetcher',
            'dir_list_tool_name': 'Directory Browser',
            'shell_tool_name': 'Shell Executor',
        }
    }
    
    @classmethod
    def get(cls, key: str, **kwargs) -> str:
        """
        获取文本消息
        
        Args:
            key: 消息键
            **kwargs: 格式化参数
            
        Returns:
            格式化后的消息文本
        """
        messages = cls._messages.get(cls.current_lang, cls._messages['zh_CN'])
        message = messages.get(key, key)  # 如果找不到，返回key本身
        
        # 格式化消息
        if kwargs:
            try:
                return message.format(**kwargs)
            except:
                return message
        return message
    
    @classmethod
    def set_language(cls, lang: str):
        """设置当前语言"""
        if lang in cls._messages:
            cls.current_lang = lang
            # 同时更新环境变量，供核心模块使用
            os.environ['DBRHEO_LANG'] = lang
    
    @classmethod
    def get_available_languages(cls) -> list:
        """获取可用语言列表"""
        return list(cls._messages.keys())
    
    @classmethod
    def get_language_name(cls, lang_code: str) -> str:
        """获取语言的显示名称"""
        lang_names = {
            'zh_CN': '中文',
            'ja_JP': '日文',
            'en_US': 'English'
        }
        return lang_names.get(lang_code, lang_code)


# 便捷函数
def _(key: str, **kwargs) -> str:
    """国际化文本获取的便捷函数"""
    return I18n.get(key, **kwargs)