/**
 * 查询结果表格组件 - 展示SQL查询结果
 * 支持分页、排序、导出等功能
 */
import React from 'react'

interface ResultTableProps {
  data?: any[]
  columns?: string[]
  loading?: boolean
}

export function ResultTable({ data = [], columns = [], loading = false }: ResultTableProps) {
  if (loading) {
    return (
      <div className="border border-gray-300 rounded-md p-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-2 text-gray-500">正在执行查询...</p>
        </div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="border border-gray-300 rounded-md p-8">
        <div className="text-center text-gray-500">
          暂无查询结果
        </div>
      </div>
    )
  }

  return (
    <div className="border border-gray-300 rounded-md overflow-hidden">
      <div className="bg-gray-50 px-3 py-2 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">
            查询结果 ({data.length} 行)
          </span>
          <div className="flex space-x-2">
            <button className="text-xs text-gray-500 hover:text-gray-700">
              导出CSV
            </button>
            <button className="text-xs text-gray-500 hover:text-gray-700">
              复制
            </button>
          </div>
        </div>
      </div>
      
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {columns.map((column, index) => (
                <th
                  key={index}
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {data.map((row, rowIndex) => (
              <tr key={rowIndex} className="hover:bg-gray-50">
                {columns.map((column, colIndex) => (
                  <td
                    key={colIndex}
                    className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
                  >
                    {row[column]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default ResultTable
