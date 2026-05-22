import { useEffect, useState } from 'react';
import {
  Save,
  CheckCircle2,
  Loader2,
  FolderOpen,
  Plug,
  Trash2,
  ListTree,
  AlertTriangle,
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { Input, Textarea, Select } from '../components/Input';
import {
  openLogDir,
  purgeAll,
  purgeBefore,
  storageStats,
  testLlmConnection,
} from '../api/ipc';
import { useConfig } from '../hooks/useConfig';
import type { Config, StorageStats } from '../api/types';
import { useToast } from '../hooks/useToast';
import dayjs from 'dayjs';

export default function Settings() {
  const toast = useToast();
  const { config, save, saving, loading } = useConfig();
  const [draft, setDraft] = useState<Config | null>(null);
  const [testing, setTesting] = useState(false);
  const [stats, setStats] = useState<StorageStats | null>(null);
  const [purging, setPurging] = useState(false);
  const [purgeDays, setPurgeDays] = useState(30);

  useEffect(() => {
    if (config) setDraft(structuredClone(config));
  }, [config]);

  const refreshStats = async () => {
    try {
      const s = await storageStats();
      setStats(s);
    } catch (e: any) {
      console.warn('storage_stats failed', e);
    }
  };

  useEffect(() => {
    void refreshStats();
  }, []);

  if (loading || !draft) {
    return (
      <div className="p-6 text-sm text-muted flex items-center gap-2">
        <Loader2 className="animate-spin" size={14} /> 加载配置中...
      </div>
    );
  }

  const onSave = async () => {
    try {
      await save(draft);
      toast.success('已保存');
    } catch (e: any) {
      toast.error(`保存失败: ${e}`);
    }
  };

  const onTest = async () => {
    if (testing) return;
    setTesting(true);
    try {
      const [ok, msg] = await testLlmConnection(draft.llm);
      if (ok) toast.success(`连接成功：${msg || ''}`);
      else toast.error(`连接失败：${msg}`);
    } catch (e: any) {
      toast.error(`测试失败: ${e}`);
    } finally {
      setTesting(false);
    }
  };

  const onOpenLogDir = async () => {
    try {
      await openLogDir();
    } catch (e: any) {
      toast.error(`打开日志目录失败: ${e}`);
    }
  };

  const onPurgeBefore = async () => {
    if (!confirm(`将清理 ${purgeDays} 天之前的所有工作流水与报告，是否继续？`))
      return;
    setPurging(true);
    try {
      const r = await purgeBefore(purgeDays);
      toast.success(
        `已清理：流水 ${r.work_logs} 条，报告 ${r.reports} 条`
      );
      await refreshStats();
    } catch (e: any) {
      toast.error(`清理失败: ${e}`);
    } finally {
      setPurging(false);
    }
  };

  const onPurgeAll = async () => {
    if (
      !confirm(
        '⚠ 危险操作：将清空所有工作流水与历史报告，且无法恢复。是否确认？'
      )
    )
      return;
    setPurging(true);
    try {
      const r = await purgeAll();
      toast.success(
        `已清空：流水 ${r.work_logs} 条，报告 ${r.reports} 条`
      );
      await refreshStats();
    } catch (e: any) {
      toast.error(`清空失败: ${e}`);
    } finally {
      setPurging(false);
    }
  };

  const update = <K extends keyof Config>(key: K, value: Config[K]) =>
    setDraft((d) => (d ? { ...d, [key]: value } : d));

  return (
    <div className="p-6 space-y-5 pb-24">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">设置</h1>
          <p className="text-sm text-muted mt-1">
            配置 LLM、Git、截图、报告与应用行为
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={<FolderOpen size={14} />}
            onClick={() => void onOpenLogDir()}
          >
            打开日志目录
          </Button>
          <Button
            icon={<Save size={14} />}
            onClick={() => void onSave()}
            loading={saving}
          >
            保存配置
          </Button>
        </div>
      </header>

      {/* LLM */}
      <Card title="LLM 配置" description="用于生成报告与截图分析的大模型">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Input
            label="Provider"
            value={draft.llm.provider}
            onChange={(e) =>
              update('llm', { ...draft.llm, provider: e.target.value })
            }
            placeholder="openai / azure / ollama / anthropic..."
          />
          <Input
            label="Base URL"
            value={draft.llm.base_url}
            onChange={(e) =>
              update('llm', { ...draft.llm, base_url: e.target.value })
            }
            placeholder="https://api.openai.com/v1"
          />
          <Input
            label="API Key"
            type="password"
            value={draft.llm.api_key}
            onChange={(e) =>
              update('llm', { ...draft.llm, api_key: e.target.value })
            }
            placeholder="sk-..."
          />
          <Input
            label="文本模型"
            value={draft.llm.model}
            onChange={(e) =>
              update('llm', { ...draft.llm, model: e.target.value })
            }
            placeholder="gpt-4o-mini"
          />
          <Input
            label="视觉模型"
            value={draft.llm.vision_model}
            onChange={(e) =>
              update('llm', { ...draft.llm, vision_model: e.target.value })
            }
            placeholder="gpt-4o"
          />
          <Input
            label="Temperature"
            type="number"
            step="0.1"
            min="0"
            max="2"
            value={draft.llm.temperature}
            onChange={(e) =>
              update('llm', {
                ...draft.llm,
                temperature: Number(e.target.value),
              })
            }
          />
          <Input
            label="超时（秒）"
            type="number"
            min="1"
            value={draft.llm.timeout}
            onChange={(e) =>
              update('llm', {
                ...draft.llm,
                timeout: Number(e.target.value),
              })
            }
          />
        </div>
        <div className="mt-3">
          <Button
            variant="secondary"
            size="sm"
            icon={<Plug size={14} />}
            onClick={() => void onTest()}
            loading={testing}
          >
            测试连接
          </Button>
        </div>
      </Card>

      {/* Git */}
      <Card
        title="Git 监听"
        description="多仓库提交采集与作者过滤（每行一条）"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Textarea
            label="仓库路径"
            rows={4}
            value={draft.git.repos.join('\n')}
            onChange={(e) =>
              update('git', {
                ...draft.git,
                repos: splitLines(e.target.value),
              })
            }
            placeholder={'C:/workspace/repo-a\nC:/workspace/repo-b'}
          />
          <div className="grid grid-cols-1 gap-3">
            <Textarea
              label="作者邮箱白名单"
              rows={2}
              value={draft.git.author_emails.join('\n')}
              onChange={(e) =>
                update('git', {
                  ...draft.git,
                  author_emails: splitLines(e.target.value),
                })
              }
              placeholder="me@example.com"
            />
            <Textarea
              label="作者名称白名单"
              rows={2}
              value={draft.git.author_names.join('\n')}
              onChange={(e) =>
                update('git', {
                  ...draft.git,
                  author_names: splitLines(e.target.value),
                })
              }
              placeholder="Ethan"
            />
          </div>
          <Input
            label="轮询间隔（秒）"
            type="number"
            min="10"
            value={draft.git.poll_interval_seconds}
            onChange={(e) =>
              update('git', {
                ...draft.git,
                poll_interval_seconds: Number(e.target.value),
              })
            }
          />
          <label className="flex items-center gap-2 text-sm self-end pb-2">
            <input
              type="checkbox"
              checked={draft.git.include_merges}
              onChange={(e) =>
                update('git', {
                  ...draft.git,
                  include_merges: e.target.checked,
                })
              }
              className="accent-primary"
            />
            包含 Merge 提交
          </label>
        </div>
      </Card>

      {/* Screenshot */}
      <Card title="截图" description="周期截图与视觉理解">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Input
            label="间隔（秒）"
            type="number"
            min="10"
            value={draft.screenshot.interval_seconds}
            onChange={(e) =>
              update('screenshot', {
                ...draft.screenshot,
                interval_seconds: Number(e.target.value),
              })
            }
          />
          <Input
            label="空闲跳过（秒，0 关闭）"
            type="number"
            min="0"
            value={draft.screenshot.idle_skip_seconds}
            onChange={(e) =>
              update('screenshot', {
                ...draft.screenshot,
                idle_skip_seconds: Number(e.target.value),
              })
            }
          />
          <Input
            label="显示器索引"
            type="number"
            min="0"
            value={draft.screenshot.monitor_index}
            onChange={(e) =>
              update('screenshot', {
                ...draft.screenshot,
                monitor_index: Number(e.target.value),
              })
            }
            hint="0 表示主显示器"
          />
          <Input
            label="输出目录"
            value={draft.screenshot.output_dir}
            onChange={(e) =>
              update('screenshot', {
                ...draft.screenshot,
                output_dir: e.target.value,
              })
            }
            placeholder="留空使用默认"
          />
          <label className="flex items-center gap-2 text-sm self-end pb-2">
            <input
              type="checkbox"
              checked={draft.screenshot.enabled}
              onChange={(e) =>
                update('screenshot', {
                  ...draft.screenshot,
                  enabled: e.target.checked,
                })
              }
              className="accent-primary"
            />
            启用截图
          </label>
          <label className="flex items-center gap-2 text-sm self-end pb-2">
            <input
              type="checkbox"
              checked={draft.screenshot.auto_start}
              onChange={(e) =>
                update('screenshot', {
                  ...draft.screenshot,
                  auto_start: e.target.checked,
                })
              }
              className="accent-primary"
            />
            启动时自动开始监听
          </label>
          <label className="flex items-center gap-2 text-sm self-end pb-2 md:col-span-2">
            <input
              type="checkbox"
              checked={draft.screenshot.keep_after_analysis}
              onChange={(e) =>
                update('screenshot', {
                  ...draft.screenshot,
                  keep_after_analysis: e.target.checked,
                })
              }
              className="accent-primary"
            />
            分析后保留图片文件
          </label>
        </div>
      </Card>

      {/* Report */}
      <Card title="报告偏好" description="用于生成的默认值">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Input
            label="默认模板 Key"
            value={draft.report.default_template}
            onChange={(e) =>
              update('report', {
                ...draft.report,
                default_template: e.target.value,
              })
            }
            placeholder="daily_default"
          />
          <Select
            label="语言"
            value={draft.report.language}
            onChange={(e) =>
              update('report', {
                ...draft.report,
                language: e.target.value,
              })
            }
          >
            <option value="zh-CN">中文（简体）</option>
            <option value="zh-TW">中文（繁体）</option>
            <option value="en-US">English</option>
            <option value="ja-JP">日本語</option>
          </Select>
          <Input
            label="姓名"
            value={draft.report.user_name}
            onChange={(e) =>
              update('report', {
                ...draft.report,
                user_name: e.target.value,
              })
            }
          />
          <Input
            label="团队"
            value={draft.report.team}
            onChange={(e) =>
              update('report', { ...draft.report, team: e.target.value })
            }
          />
        </div>
      </Card>

      {/* App */}
      <Card title="应用" description="开机自启与数据保留策略">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="flex items-center gap-2 text-sm self-end pb-2">
            <input
              type="checkbox"
              checked={draft.app.auto_launch_on_boot}
              onChange={(e) =>
                update('app', {
                  ...draft.app,
                  auto_launch_on_boot: e.target.checked,
                })
              }
              className="accent-primary"
            />
            开机自启
          </label>
          <Input
            label="自动清理（天数，0 关闭）"
            type="number"
            min="0"
            value={draft.app.cleanup_keep_days}
            onChange={(e) =>
              update('app', {
                ...draft.app,
                cleanup_keep_days: Number(e.target.value),
              })
            }
          />
          <Input
            label="数据库路径"
            value={draft.db_path}
            onChange={(e) => update('db_path', e.target.value)}
            hint="留空使用默认位置"
          />
        </div>
      </Card>

      {/* Storage / Cleanup */}
      <Card
        title="数据管理"
        description="存储统计与清理"
        footer={
          <div className="flex items-center gap-2 flex-wrap text-xs text-muted">
            <AlertTriangle size={12} />
            清理操作不可撤销，请谨慎
          </div>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
          <Stat
            icon={<ListTree size={18} className="text-primary" />}
            label="工作流水"
            value={stats?.work_logs_total ?? '—'}
          />
          <Stat
            icon={<CheckCircle2 size={18} className="text-emerald-600" />}
            label="报告数"
            value={stats?.reports_total ?? '—'}
          />
          <Stat
            icon={<Save size={18} className="text-amber-600" />}
            label="时间范围"
            value={
              stats?.earliest_log
                ? `${dayjs(stats.earliest_log).format('YY-MM-DD')} ~ ${dayjs(
                    stats.latest_log
                  ).format('YY-MM-DD')}`
                : '—'
            }
          />
        </div>

        <div className="flex items-end gap-3 flex-wrap">
          <Input
            label="清理多少天之前"
            type="number"
            min="1"
            value={purgeDays}
            onChange={(e) => setPurgeDays(Number(e.target.value))}
            className="w-[200px]"
          />
          <Button
            variant="secondary"
            icon={<Trash2 size={14} />}
            onClick={() => void onPurgeBefore()}
            loading={purging}
          >
            清理早于 {purgeDays} 天的数据
          </Button>
          <Button
            variant="danger"
            icon={<Trash2 size={14} />}
            onClick={() => void onPurgeAll()}
            loading={purging}
          >
            清空全部
          </Button>
        </div>
      </Card>
    </div>
  );
}

function Stat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border p-3 flex items-center gap-3">
      <span className="w-8 h-8 rounded-md bg-zinc-50 flex items-center justify-center">
        {icon}
      </span>
      <div className="min-w-0">
        <div className="text-xs text-muted">{label}</div>
        <div className="text-sm font-semibold mt-0.5 truncate">{value}</div>
      </div>
    </div>
  );
}

function splitLines(s: string): string[] {
  return s
    .split(/\r?\n/)
    .map((x) => x.trim())
    .filter(Boolean);
}
