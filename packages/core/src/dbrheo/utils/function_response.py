"""
工具响应转换工具 - 将工具执行结果转换为Gemini API的functionResponse格式
完全参考Gemini CLI的convertToFunctionResponse实现
"""

from typing import Union, Dict, Any, List
from ..types.core_types import PartListUnion, Part
from ..utils.debug_logger import log_info


def _select_best_content_for_agent(tool_result, tool_name: str) -> str:
    """
    智能选择最适合Agent的内容
    根据工具类型和内容特征，灵活选择最有用的信息
    """
    log_info("FunctionResponse", f"🔍 DEBUG: _select_best_content_for_agent called")
    log_info("FunctionResponse", f"🔍 DEBUG: tool_name={tool_name}")
    log_info("FunctionResponse", f"🔍 DEBUG: tool_result.error={repr(tool_result.error)}")
    log_info("FunctionResponse", f"🔍 DEBUG: 'shell' in tool_name.lower()={'shell' in tool_name.lower()}")
    
    # 特别注意：shell工具即使有错误，也需要传递完整的执行信息给Agent
    # 只有非shell工具才在有错误时直接返回错误信息
    if tool_result.error and 'shell' not in tool_name.lower():
        # 格式化错误信息，让Agent更容易识别这是错误  
        error_msg = str(tool_result.error)
        log_info("FunctionResponse", f"🔍 DEBUG: 非shell工具有错误，返回错误信息: {error_msg}")
        return f"❌ TOOL EXECUTION FAILED: {error_msg}"
    
    # 对于shell工具，智能提取命令输出 - 修复stdout提取逻辑
    if 'shell' in tool_name.lower():
        log_info("FunctionResponse", f"🔍 DEBUG: 进入shell工具处理分支: {tool_name}")
        # shell工具有错误时，也要尝试提取完整信息
        if tool_result.error:
            log_info("FunctionResponse", f"🔍 DEBUG: Shell工具有错误，但仍尝试提取完整执行信息")
        
        log_info("FunctionResponse", f"🔍 DEBUG: tool_result.llm_content存在: {tool_result.llm_content is not None}")
        if tool_result.llm_content:
            content = str(tool_result.llm_content)
            log_info("FunctionResponse", f"llm_content前100字符: {content[:100]}")
            
            # 智能内容提取 - 基于模式识别而非硬编码字符串
            lines = content.split('\n')
            
            # 策略1: 寻找被标记包围的内容块（通用模式）
            output_lines = []
            in_output_block = False
            block_start_patterns = ['===', '---', '***', '>>>']  # 常见的分隔符模式
            
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                
                # 检测输出块开始（包含关键词如OUTPUT、RESULT、STDOUT等）
                if not in_output_block and any(marker in line for marker in block_start_patterns):
                    if any(keyword in line.upper() for keyword in ['OUTPUT', 'RESULT', 'STDOUT', 'RESPONSE']):
                        in_output_block = True
                        continue  # 跳过标题行
                        
                # 检测输出块结束
                elif in_output_block and any(marker in line for marker in block_start_patterns):
                    if any(keyword in line.upper() for keyword in ['END', 'FINISH', 'CLOSE']):
                        break  # 结束提取
                        
                # 收集输出内容
                elif in_output_block:
                    # 跳过明显的元数据行
                    if not line_stripped.startswith(('Command:', 'Platform:', 'Shell:', 'Directory:', 'Exit Code:', 'Execution Time:')):
                        output_lines.append(line_stripped)
            
            # 如果找到块内容，返回时包含执行状态
            if output_lines:
                result_content = '\n'.join(output_lines).strip()
                log_info("FunctionResponse", f"🔍 DEBUG: 策略1找到output_lines: {len(output_lines)}行")
                log_info("FunctionResponse", f"🔍 DEBUG: result_content: {repr(result_content)}")
                if result_content and result_content != '(empty)':
                    log_info("FunctionResponse", f"🔍 DEBUG: result_content非空，准备返回")
                    # 检查是否有错误状态
                    has_error = tool_result.error is not None
                    log_info("FunctionResponse", f"🔍 DEBUG: has_error={has_error}")
                    final_result = ""
                    if has_error:
                        final_result = f"❌ Shell命令执行失败，但产生了输出：\n{result_content}"
                    else:
                        final_result = f"✅ Shell命令执行成功，输出：\n{result_content}"
                    log_info("FunctionResponse", f"🔍 DEBUG: 策略1最终返回: {repr(final_result)}")
                    return final_result
            
            # 策略2: 智能识别真实命令输出（排除元数据）
            meaningful_lines = []
            metadata_keywords = ['Command:', 'Platform:', 'Shell:', 'Directory:', 'Exit Code:', 'Execution Time:', 'Stdout:', 'Stderr:']
            status_patterns = ['✅', '❌', 'Shell command', 'executed', 'failed', 'successfully']
            
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                    
                # 跳过元数据行
                if any(line_stripped.startswith(keyword) for keyword in metadata_keywords):
                    continue
                    
                # 跳过状态行  
                if any(pattern in line for pattern in status_patterns):
                    continue
                    
                # 收集看起来像实际输出的行
                if line_stripped and line_stripped not in ['(empty)', '(no output)']:
                    meaningful_lines.append(line_stripped)
            
            # 返回提取的有意义内容，包含状态信息
            if meaningful_lines:
                result_content = '\n'.join(meaningful_lines).strip()
                log_info("FunctionResponse", f"🔍 DEBUG: 策略2找到meaningful_lines: {len(meaningful_lines)}行")
                log_info("FunctionResponse", f"🔍 DEBUG: meaningful_lines内容: {meaningful_lines}")
                log_info("FunctionResponse", f"🔍 DEBUG: result_content: {repr(result_content)}")
                # 包含执行状态让Agent明确知道结果
                has_error = tool_result.error is not None
                log_info("FunctionResponse", f"🔍 DEBUG: has_error={has_error}")
                final_result = ""
                if has_error:
                    final_result = f"❌ Shell命令执行失败，但产生了输出：\n{result_content}"
                else:
                    final_result = f"✅ Shell命令执行成功，输出：\n{result_content}"
                log_info("FunctionResponse", f"🔍 DEBUG: 策略2最终返回: {repr(final_result)}")
                return final_result
            
            # 如果stdout提取失败或为空，尝试查找完整的命令输出
            # 检查是否包含实际的命令输出（而不仅仅是元数据）
            lines = content.split('\n')
            non_metadata_lines = []
            for line in lines:
                line_stripped = line.strip()
                # 跳过元数据行（以这些关键词开头的行）
                if not (line_stripped.startswith(('Command:', 'Platform:', 'Shell:', 'Directory:', 'Stdout:', 'Stderr:', 'Exit Code:', 'Execution Time:')) or 
                       line_stripped in ['(empty)', '']):
                    non_metadata_lines.append(line_stripped)
            
            # 如果找到非元数据内容，优先返回
            if non_metadata_lines:
                return '\n'.join(non_metadata_lines)
        
        # 如果没找到有效内容，返回完整的llm_content
        log_info("FunctionResponse", f"🔍 DEBUG: shell工具所有策略都未找到内容，回退到完整llm_content")
        if tool_result.llm_content:
            fallback_content = str(tool_result.llm_content)
            log_info("FunctionResponse", f"🔍 DEBUG: 回退内容: {repr(fallback_content)}")
            return fallback_content
    
    # 对于其他工具，使用更简单的策略
    log_info("FunctionResponse", f"🔍 DEBUG: 非shell工具，使用简单策略")
    # 优先级：llm_content > return_display > summary
    if tool_result.llm_content:
        log_info("FunctionResponse", f"🔍 DEBUG: 返回llm_content")
        return str(tool_result.llm_content)
    elif tool_result.return_display:
        log_info("FunctionResponse", f"🔍 DEBUG: 返回return_display")
        return str(tool_result.return_display)
    elif tool_result.summary:
        log_info("FunctionResponse", f"🔍 DEBUG: 返回summary")
        return str(tool_result.summary)
    
    log_info("FunctionResponse", f"🔍 DEBUG: 所有内容都为空，返回默认消息")
    return "Tool execution completed."


def create_function_response_part(call_id: str, tool_name: str, output: str) -> Part:
    """
    创建标准的functionResponse部分
    对应Gemini CLI的createFunctionResponsePart
    """
    return {
        'functionResponse': {
            'id': call_id,
            'name': tool_name,
            'response': {'output': output}
        }
    }


def convert_to_function_response(
    tool_name: str,
    call_id: str, 
    llm_content: PartListUnion
) -> PartListUnion:
    """
    将工具执行结果转换为functionResponse格式
    完全参考Gemini CLI的convertToFunctionResponse逻辑
    
    参数:
        tool_name: 工具名称
        call_id: 调用ID
        llm_content: 工具返回的内容（可能是字符串、字典、列表或ToolResult）
        
    返回:
        转换后的functionResponse格式
    """
    # 智能检测 ToolResult 对象（更灵活的处理）
    log_info("FunctionResponse", f"🔍 DEBUG: convert_to_function_response called")
    log_info("FunctionResponse", f"🔍 DEBUG: tool_name={tool_name}")
    log_info("FunctionResponse", f"🔍 DEBUG: call_id={call_id}")
    log_info("FunctionResponse", f"🔍 DEBUG: llm_content_type={type(llm_content)}")
    log_info("FunctionResponse", f"🔍 DEBUG: llm_content repr: {repr(llm_content)[:200]}...")
    
    if hasattr(llm_content, '__class__') and llm_content.__class__.__name__ == 'ToolResult':
        log_info("FunctionResponse", f"🔍 DEBUG: 检测到ToolResult对象，进入专用处理分支")
        # 处理 ToolResult 对象
        from ..types.tool_types import ToolResult
        if isinstance(llm_content, ToolResult):
            log_info("FunctionResponse", f"🔍 DEBUG: ToolResult属性检查:")
            log_info("FunctionResponse", f"🔍 DEBUG: - error: {repr(llm_content.error)}")
            log_info("FunctionResponse", f"🔍 DEBUG: - summary: {repr(llm_content.summary)}")
            log_info("FunctionResponse", f"🔍 DEBUG: - llm_content: {repr(str(llm_content.llm_content)[:200])}")
            log_info("FunctionResponse", f"🔍 DEBUG: - return_display: {repr(str(llm_content.return_display)[:200])}")
            
            # 智能选择最适合的内容，而不是硬编码优先级
            output_text = _select_best_content_for_agent(llm_content, tool_name)
            log_info("FunctionResponse", f"🔍 DEBUG: _select_best_content_for_agent返回: {repr(output_text)}")
            
            final_response = create_function_response_part(call_id, tool_name, output_text)
            log_info("FunctionResponse", f"🔍 DEBUG: create_function_response_part返回: {repr(final_response)}")
            
            return final_response
    else:
        log_info("FunctionResponse", f"没有检测到ToolResult对象，进入其他处理分支")
    
    # 处理单元素列表的情况
    content_to_process = llm_content
    if isinstance(llm_content, list) and len(llm_content) == 1:
        content_to_process = llm_content[0]
    
    # 字符串直接转换
    if isinstance(content_to_process, str):
        return create_function_response_part(call_id, tool_name, content_to_process)
    
    # 列表：添加成功消息并包含原始内容
    if isinstance(content_to_process, list):
        function_response = create_function_response_part(
            call_id, tool_name, 'Tool execution succeeded.'
        )
        return [function_response] + content_to_process
    
    # 字典类型的Part对象
    if isinstance(content_to_process, dict):
        # 已经是functionResponse格式
        if 'functionResponse' in content_to_process:
            # 如果有嵌套的response.content，提取文本
            response_content = content_to_process.get('functionResponse', {}).get('response', {}).get('content')
            if response_content:
                # 这里简化处理，实际可能需要更复杂的文本提取
                output_text = str(response_content)
                return create_function_response_part(call_id, tool_name, output_text)
            # 否则直接返回
            return content_to_process
        
        # 处理二进制数据（inlineData或fileData）
        if 'inlineData' in content_to_process or 'fileData' in content_to_process:
            mime_type = (
                content_to_process.get('inlineData', {}).get('mimeType') or
                content_to_process.get('fileData', {}).get('mimeType') or
                'unknown'
            )
            function_response = create_function_response_part(
                call_id, tool_name, f'Binary content of type {mime_type} was processed.'
            )
            return [function_response, content_to_process]
        
        # 处理text类型
        if 'text' in content_to_process:
            return create_function_response_part(call_id, tool_name, content_to_process['text'])
        
        # 处理结构化数据（来自数据库查询等）
        # 这是数据库工具常见的返回格式
        if any(key in content_to_process for key in ['columns', 'rows', 'tables', 'row_count']):
            # 将结构化数据转换为可读文本
            output_parts = []
            
            if 'tables' in content_to_process:
                # SchemaDiscoveryTool结果
                tables = content_to_process['tables']
                count = content_to_process.get('count', len(tables) if isinstance(tables, list) else 0)
                if count > 0:
                    output_parts.append(f"发现 {count} 个表: {', '.join(tables) if isinstance(tables, list) else str(tables)}")
                else:
                    output_parts.append("数据库中没有找到任何表")
                    
            elif 'columns' in content_to_process and 'rows' in content_to_process:
                # SQLTool查询结果
                columns = content_to_process['columns']
                rows = content_to_process.get('rows', [])
                row_count = content_to_process.get('row_count', len(rows))
                
                if row_count == 0:
                    output_parts.append("查询完成，无数据返回")
                else:
                    output_parts.append(f"查询返回 {row_count} 行数据")
                    if columns:
                        output_parts.append(f"列: {', '.join(columns)}")
                    # 添加前几行数据作为示例
                    if rows:
                        sample_rows = rows[:3]  # 只显示前3行
                        for i, row in enumerate(sample_rows):
                            row_str = ', '.join(f"{k}={v}" for k, v in row.items())
                            output_parts.append(f"行{i+1}: {row_str}")
                        if row_count > 3:
                            output_parts.append(f"... 还有 {row_count - 3} 行")
                            
            elif 'operation' in content_to_process:
                # SQLTool命令结果
                operation = content_to_process['operation']
                affected_rows = content_to_process.get('affected_rows', 0)
                success = content_to_process.get('success', True)
                
                if success:
                    if affected_rows > 0:
                        output_parts.append(f"{operation}操作成功，影响 {affected_rows} 行")
                    else:
                        output_parts.append(f"{operation}操作成功")
                else:
                    output_parts.append(f"{operation}操作失败")
                    
            if output_parts:
                output_text = '. '.join(output_parts)
                return create_function_response_part(call_id, tool_name, output_text)
        
        # 其他字典：转换为JSON字符串
        import json
        try:
            output_text = json.dumps(content_to_process, ensure_ascii=False, indent=2)
            return create_function_response_part(call_id, tool_name, output_text)
        except (TypeError, ValueError):
            # JSON序列化失败，转换为字符串
            output_text = str(content_to_process)
            return create_function_response_part(call_id, tool_name, output_text)
    
    # 默认情况
    return create_function_response_part(call_id, tool_name, 'Tool execution succeeded.')