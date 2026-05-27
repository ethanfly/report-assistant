// 类型定义 - 与 Rust 后端完全对应

export interface LlmProvider {
  id: string;
  /** 显示名称；空时回退到 provider+model */
  name: string;
  provider: string;
  base_url: string;
  api_key: string;
  model: string;
  temperature: number;
  timeout: number;
}

export interface LlmConfig {
  providers: LlmProvider[];
  /** 默认文本 provider 的 id */
  default_text_id: string;
  /** 默认视觉 provider 的 id */
  default_vision_id: string;
}

export interface RepoEntry {
  path: string;
  /** 显示名称；为空则使用路径末段 */
  alias?: string;
}

export interface GitConfig {
  repos: RepoEntry[];
  author_emails: string[];
  author_names: string[];
  include_merges: boolean;
  poll_interval_seconds: number;
}

export interface ScreenshotConfig {
  enabled: boolean;
  interval_seconds: number;
  keep_after_analysis: boolean;
  output_dir: string;
  auto_start: boolean;
  monitor_index: number;
  idle_skip_seconds: number;
}

export interface ReportConfig {
  default_template: string;
  language: string;
  user_name: string;
  team: string;
}

export interface AppConfig {
  auto_launch_on_boot: boolean;
  silent_launch: boolean;
  cleanup_keep_days: number;
}

export interface Config {
  llm: LlmConfig;
  git: GitConfig;
  screenshot: ScreenshotConfig;
  report: ReportConfig;
  app: AppConfig;
  db_path: string;
}

export interface WorkLog {
  id: number;
  ts: string;
  source: string;
  category?: string;
  title: string;
  content: string;
  meta: any;
  created_at: string;
}

export interface Report {
  id: number;
  kind: string;
  period_start: string;
  period_end: string;
  template?: string;
  content: string;
  created_at: string;
}

export interface MonitorInfo {
  index: number;
  label: string;
  width: number;
  height: number;
}

export interface ReportTemplate {
  key: string;
  label: string;
  system_prompt: string;
  user_prompt_hint: string;
}

export type ReportKind = 'Daily' | 'Weekly' | 'Monthly';

export interface GenerateRequest {
  kind: ReportKind;
  anchor: string;
  template?: string;
  extra_notes: string;
  include_screenshots: boolean;
  include_git: boolean;
}

export interface GenerateResult {
  kind: string;
  period_start: string;
  period_end: string;
  template: string;
  content: string;
  commit_count: number;
  screenshot_count: number;
  report_id: number;
}

export interface StorageStats {
  work_logs_total: number;
  reports_total: number;
  earliest_log?: string;
  latest_log?: string;
}

export interface PurgeStats {
  work_logs: number;
  reports: number;
}

export type WatchEvent =
  | { type: 'started'; interval_seconds: number }
  | {
      type: 'captured';
      ts: string;
      category: string;
      title: string;
      summary: string;
      keywords: string[];
    }
  | { type: 'failed'; message: string }
  | { type: 'idle_skipped'; idle_seconds: number }
  | { type: 'stopped' };

export type ExportFormat = 'md' | 'html' | 'txt' | 'docx';
