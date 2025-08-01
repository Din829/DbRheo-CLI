/**
 * 对话容器组件 - 管理与数据库Agent的对话交互
 * 实现流式对话、工具调用确认等核心功能
 */
import React from 'react'

interface ChatContainerProps {
  // TODO: 定义props类型
}

export function ChatContainer(props: ChatContainerProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4">
        {/* 消息列表区域 */}
        <div className="space-y-4">
          <div className="text-center text-gray-500 text-sm">
            对话容器组件 - 待实现
          </div>
        </div>
      </div>
      
      <div className="border-t p-4">
        {/* 消息输入区域 */}
        <div className="flex space-x-2">
          <input
            type="text"
            placeholder="输入您的数据库查询需求..."
            className="flex-1 border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button className="btn-primary">
            发送
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChatContainer
