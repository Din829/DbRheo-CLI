/**
 * SQL查询编辑器组件 - 基于Monaco Editor
 * 提供SQL语法高亮、自动补全、错误检查等功能
 */
import React from 'react'

interface QueryEditorProps {
  value?: string
  onChange?: (value: string) => void
  readOnly?: boolean
}

export function QueryEditor({ value = '', onChange, readOnly = false }: QueryEditorProps) {
  return (
    <div className="border border-gray-300 rounded-md overflow-hidden">
      <div className="bg-gray-50 px-3 py-2 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">SQL编辑器</span>
          <div className="flex space-x-2">
            <button className="text-xs text-gray-500 hover:text-gray-700">
              格式化
            </button>
            <button className="text-xs text-gray-500 hover:text-gray-700">
              执行
            </button>
          </div>
        </div>
      </div>
      
      <div className="h-64 p-4 bg-white">
        <textarea
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          readOnly={readOnly}
          placeholder="-- 输入您的SQL查询
SELECT * FROM users WHERE id = 1;"
          className="w-full h-full resize-none border-none outline-none font-mono text-sm"
        />
      </div>
      
      <div className="bg-gray-50 px-3 py-2 border-t border-gray-200">
        <div className="text-xs text-gray-500">
          Monaco Editor集成 - 待实现语法高亮和自动补全
        </div>
      </div>
    </div>
  )
}

export default QueryEditor
