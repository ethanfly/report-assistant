import { invoke } from '@tauri-apps/api/core';
import { listen, UnlistenFn } from '@tauri-apps/api/event';
import type {
  Config,
  ExportFormat,
  GenerateRequest,
  GenerateResult,
  LlmProvider,
  MonitorInfo,
  PurgeStats,
  Report,
  ReportTemplate,
  StorageStats,
  Todo,
  WatchEvent,
  WorkLog,
} from './types';

// ===== 配置 =====
export const loadConfig = () => invoke<Config>('load_config');
export const saveConfig = (cfg: Config) => invoke<void>('save_config', { cfg });

// ===== 存储 =====
export const listWorkLogs = (start: string, end: string, source?: string) =>
  invoke<WorkLog[]>('list_work_logs', { start, end, source });

export const listReports = (limit: number) =>
  invoke<Report[]>('list_reports', { limit });

export const getReport = (id: number) =>
  invoke<Report | null>('get_report', { id });

export const deleteReport = (id: number) =>
  invoke<boolean>('delete_report', { id });

export const deleteWorkLog = (id: number) =>
  invoke<boolean>('delete_work_log', { id });

export const storageStats = () => invoke<StorageStats>('storage_stats');

export const purgeBefore = (days: number) =>
  invoke<PurgeStats>('purge_before', { days });

export const purgeAll = () => invoke<PurgeStats>('purge_all');

// ===== 截图 =====
export const listMonitors = () => invoke<MonitorInfo[]>('list_monitors');

export const captureOnce = () => invoke<WorkLog>('capture_once');

export const startWatch = () => invoke<void>('start_watch');

export const stopWatch = () => invoke<void>('stop_watch');

export const isWatching = () => invoke<boolean>('is_watching');

// ===== Git =====
export const syncGit = () => invoke<number>('sync_git');

// ===== 时间线手动记录 =====
export const addManualLog = (description: string, ts?: string) =>
  invoke<WorkLog>('add_manual_log', { description, ts });

// ===== 待办 =====
export const addTodo = (content: string) =>
  invoke<Todo>('add_todo', { content });

export const listTodos = (status?: string) =>
  invoke<Todo[]>('list_todos', { status });

export const completeTodo = (id: number) =>
  invoke<Todo>('complete_todo', { id });

export const deleteTodo = (id: number) =>
  invoke<boolean>('delete_todo', { id });

export const updateTodo = (id: number, content: string) =>
  invoke<Todo>('update_todo', { id, content });

/** 打开待办一体弹窗（输入 + 列表） */
export const showTodoPopup = () => invoke<void>('show_todo_popup');

/** @deprecated 使用 showTodoPopup */
export const showTodoQuick = () => invoke<void>('show_todo_popup');

/** @deprecated 使用 showTodoPopup */
export const showTodoList = () => invoke<void>('show_todo_popup');

export const onTodosChanged = (
  cb: () => void
): Promise<UnlistenFn> => listen('todos-changed', () => cb());

// ===== 报告 =====
export const generateReport = (request: GenerateRequest) =>
  invoke<GenerateResult>('generate_report', { request });

export const listTemplates = () => invoke<ReportTemplate[]>('list_templates');

export const exportReport = (id: number, format: ExportFormat, outDir: string) =>
  invoke<string>('export_report', { id, format, outDir });

// ===== LLM =====
export const testLlmConnection = (provider: LlmProvider) =>
  invoke<[boolean, string]>('test_llm_connection', { provider });

// ===== 其它 =====
export const openLogDir = () => invoke<void>('open_log_dir');

// ===== 事件 =====
export const onWatchEvent = (
  cb: (e: WatchEvent) => void
): Promise<UnlistenFn> => listen<WatchEvent>('watch-event', (evt) => cb(evt.payload));
