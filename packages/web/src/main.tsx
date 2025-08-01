/**
 * Web应用入口点
 * 初始化React应用和全局配置 - DbRheo数据库Agent
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/global.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
