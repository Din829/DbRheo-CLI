/**
 * 主应用组件 - DbRheo数据库Agent Web界面
 * 提供聊天界面、SQL编辑器、结果展示等核心功能
 */
import React from 'react'

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <h1 className="text-2xl font-bold text-gray-900">
              DbRheo - 智能数据库Agent
            </h1>
            <div className="text-sm text-gray-500">
              MVP版本 - 基于Gemini CLI架构
            </div>
          </div>
        </div>
      </header>
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            欢迎使用DbRheo数据库Agent
          </h2>
          <p className="text-gray-600">
            这是MVP版本的基础界面。核心功能包括：
          </p>
          <ul className="mt-4 space-y-2 text-gray-600">
            <li>• SQLTool：智能SQL执行工具</li>
            <li>• SchemaDiscoveryTool：数据库结构探索工具</li>
            <li>• 基于Gemini CLI的Turn系统和工具调度</li>
            <li>• 渐进式数据库理解和智能风险评估</li>
          </ul>
          <div className="mt-6 p-4 bg-blue-50 rounded-md">
            <p className="text-blue-800 text-sm">
              <strong>开发状态：</strong> 当前处于Phase 1 (MVP)阶段，基础文件结构已创建，等待具体功能实现。
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
