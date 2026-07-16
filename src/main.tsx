import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import TodoPopup from './pages/TodoPopup';
import './index.css';

/**
 * 根据 URL ?window= 选择入口：
 * - todo-popup（及旧名 todo-quick / todo-list）：一体弹窗
 * - 默认：完整主应用
 */
function resolveRoot() {
  const params = new URLSearchParams(window.location.search);
  const win = params.get('window');
  if (win === 'todo-popup' || win === 'todo-quick' || win === 'todo-list') {
    return <TodoPopup />;
  }
  return (
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>{resolveRoot()}</React.StrictMode>
);
