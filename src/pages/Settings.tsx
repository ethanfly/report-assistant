import { useEffect, useState, type KeyboardEvent } from 'react';
import {
  Save,
  CheckCircle2,
  FolderOpen,
  Plug,
  Trash2,
  ListTree,
  AlertTriangle,
  Cpu,
  GitBranch,
  Camera,
  FileText,
  Settings as SettingsIcon,
  Database,
  FolderGit2,
  FolderPlus,
  Plus,
  Mail,
  User,
} from 'lucide-react';
import { open as openDialog } from '@tauri-apps/plugin-dialog';
import Card from '../components/Card';
import Button from '../components/Button';
import Tabs from '../components/Tabs';
import Spinner from '../components/Spinner';
import { Input, Select } from '../components/Input';
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

type TabKey = 'llm' | 'git' | 'screenshot' | 'report' | 'app' | 'data';

const SETTING_TABS = [
  { key: 'llm' as const, label: 'LLM', icon: <Cpu size={14} /> },
  { key: 'git' as const, label: 'Git', icon: <GitBranch size={14} /> },
  { key: 'screenshot' as const, label: '截图', icon: <Camera size={14} /> },
  { key: 'report' as const, label: '报告', icon: <FileText size={14} /> },
  { key: 'app' as const, label: '应用', icon: <SettingsIcon size={14} /> },
  { key: 'data' as const, label: '数据', icon: <Database size={14} /> },
];

export default function Settings() {
  const toast = useToast();
  const { config, save, saving, loading } = useConfig();
  const [tab, setTab] = useState<TabKey>('llm');
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
      <div className="p-6 text-sm text-ink2 flex items-center gap-2">
        <Spinner size={4} /> 加载配置中...
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
      toast.success(`已清理：流水 ${r.work_logs} 条，报告 ${r.reports} 条`);
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
      toast.success(`已清空：流水 ${r.work_logs} 条，报告 ${r.reports} 条`);
      await refreshStats();
    } catch (e: any) {
      toast.error(`清空失败: ${e}`);
    } finally {
      setPurging(false);
    }
  };

  const update = <K extends keyof Config>(key: K, value: Config[K]) =>
    setDraft((d) => (d ? { ...d, [key]: value } : d));

  // 浏览并添加 Git 仓库目录（支持多选）
  const browseRepos = async () => {
    try {
      const picked = await openDialog({
        directory: true,
        multiple: true,
        title: '选择 Git 仓库目录（可多选）',
      });
      if (!picked) return;
      const list = Array.isArray(picked) ? picked : [picked];
      const next = Array.from(new Set([...draft.git.repos, ...list]));
      update('git', { ...draft.git, repos: next });
    } catch (e: any) {
      toast.error(`选择目录失败: ${e}`);
    }
  };

  return (
    <div className="p-6 space-y-5 pb-24">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink text-pix">设置</h1>
          <p className="text-sm text-ink2 mt-1">
            配置 LLM、Git、截图、报告与应用行为
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* 顶部按钮统一 md 尺寸，保证视觉等高 */}
          <Button
            variant="ghost"
            size="md"
            icon={<FolderOpen size={14} />}
            onClick={() => void onOpenLogDir()}
          >
            打开日志目录
          </Button>
          <Button
            size="md"
            icon={<Save size={14} />}
            onClick={() => void onSave()}
            loading={saving}
          >
            保存配置
          </Button>
        </div>
      </header>

      {/* 设置 Tabs */}
      <Tabs tabs={SETTING_TABS} value={tab} onChange={setTab} />

      <div key={tab} className="animate-fadein">
        {/* LLM */}
        {tab === 'llm' && (
          <Card
            title="LLM 配置"
            description="用于生成报告与截图分析的大模型"
            hoverable={false}
          >
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
                  update('llm', {
                    ...draft.llm,
                    vision_model: e.target.value,
                  })
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
        )}

        {/* Git */}
        {tab === 'git' && (
          <Card
            title="Git 监听"
            description="多仓库提交采集与作者过滤"
            hoverable={false}
          >
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* 仓库路径列表 */}
              <div className="lg:col-span-2">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-ink">仓库路径</label>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<FolderPlus size={14} />}
                    onClick={() => void browseRepos()}
                  >
                    浏览并添加...
                  </Button>
                </div>
                <ListBox
                  empty="尚未添加任何仓库，点击上方按钮添加。"
                  items={draft.git.repos}
                  renderIcon={() => (
                    <FolderGit2 size={14} className="text-primary shrink-0" />
                  )}
                  onRemove={(i) =>
                    update('git', {
                      ...draft.git,
                      repos: draft.git.repos.filter((_, idx) => idx !== i),
                    })
                  }
                />
              </div>

              {/* 作者邮箱白名单 */}
              <ListEditor
                label="作者邮箱白名单"
                placeholder="me@example.com"
                items={draft.git.author_emails}
                icon={<Mail size={14} className="text-primary shrink-0" />}
                onChange={(next) =>
                  update('git', { ...draft.git, author_emails: next })
                }
              />

              {/* 作者名称白名单 */}
              <ListEditor
                label="作者名称白名单"
                placeholder="Ethan"
                items={draft.git.author_names}
                icon={<User size={14} className="text-primary shrink-0" />}
                onChange={(next) =>
                  update('git', { ...draft.git, author_names: next })
                }
              />

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
              <label className="flex items-center gap-2 text-sm self-end pb-2 text-ink">
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
        )}

        {/* Screenshot */}
        {tab === 'screenshot' && (
          <Card title="截图" description="周期截图与视觉理解" hoverable={false}>
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
              <label className="flex items-center gap-2 text-sm self-end pb-2 text-ink">
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
              <label className="flex items-center gap-2 text-sm self-end pb-2 text-ink">
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
              <label className="flex items-center gap-2 text-sm self-end pb-2 md:col-span-2 text-ink">
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
        )}

        {/* Report */}
        {tab === 'report' && (
          <Card
            title="报告偏好"
            description="用于生成的默认值"
            hoverable={false}
          >
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
        )}

        {/* App */}
        {tab === 'app' && (
          <Card
            title="应用"
            description="开机自启与数据保留策略"
            hoverable={false}
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="flex items-center gap-2 text-sm self-end pb-2 text-ink">
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
        )}

        {/* Data */}
        {tab === 'data' && (
          <Card
            title="数据管理"
            description="存储统计与清理"
            hoverable={false}
            footer={
              <div className="flex items-center gap-2 flex-wrap text-xs text-ink2">
                <AlertTriangle size={12} />
                清理操作不可撤销，请谨慎
              </div>
            }
          >
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
              <Stat
                icon={<ListTree size={18} className="text-primary-700" />}
                label="工作流水"
                value={stats?.work_logs_total ?? '—'}
              />
              <Stat
                icon={<CheckCircle2 size={18} className="text-primary-600" />}
                label="报告数"
                value={stats?.reports_total ?? '—'}
              />
              <Stat
                icon={<Save size={18} className="text-accent-600" />}
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
        )}
      </div>
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
    <div className="rounded-pix border border-border p-3 flex items-center gap-3 bg-bg/40 hover:bg-primary-50/50 transition-colors">
      <span className="w-8 h-8 rounded-pix bg-white flex items-center justify-center border border-border">
        {icon}
      </span>
      <div className="min-w-0">
        <div className="text-xs text-ink2">{label}</div>
        <div className="text-sm font-semibold mt-0.5 truncate text-ink">{value}</div>
      </div>
    </div>
  );
}

// ----------------- 列表 UI 子组件 -----------------

// 通用只读列表：每行显示文本，hover 显示删除按钮
function ListBox({
  items,
  empty,
  renderIcon,
  onRemove,
}: {
  items: string[];
  empty: string;
  renderIcon?: (item: string, idx: number) => React.ReactNode;
  onRemove: (idx: number) => void;
}) {
  return (
    <div className="border border-border rounded-md divide-y divide-border bg-card">
      {items.length === 0 ? (
        <div className="px-3 py-4 text-sm text-ink2 text-center">{empty}</div>
      ) : (
        items.map((item, i) => (
          <div
            key={`${item}-${i}`}
            className="flex items-center gap-2 px-3 py-2 hover:bg-bg group"
          >
            {renderIcon?.(item, i)}
            <span
              className="text-sm text-ink truncate flex-1"
              title={item}
            >
              {item}
            </span>
            <button
              type="button"
              onClick={() => onRemove(i)}
              className="opacity-0 group-hover:opacity-100 text-ink2 hover:text-red-500 transition"
              title="删除"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))
      )}
    </div>
  );
}

// 带输入框的列表编辑器：用于邮箱/姓名等纯文本数组
function ListEditor({
  label,
  placeholder,
  items,
  icon,
  onChange,
}: {
  label: string;
  placeholder?: string;
  items: string[];
  icon?: React.ReactNode;
  onChange: (next: string[]) => void;
}) {
  const [input, setInput] = useState('');

  const add = () => {
    const v = input.trim();
    if (!v) return;
    if (items.includes(v)) {
      setInput('');
      return;
    }
    onChange([...items, v]);
    setInput('');
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      add();
    }
  };

  return (
    <div>
      <label className="text-sm font-medium text-ink mb-2 block">{label}</label>
      <div className="flex items-center gap-2 mb-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder={placeholder}
          className="flex-1 h-9 px-3 text-sm rounded-md border border-border bg-card text-ink placeholder:text-ink2 focus:outline-none focus:ring-2 focus:ring-primary/40"
        />
        <Button
          variant="secondary"
          size="sm"
          icon={<Plus size={14} />}
          onClick={add}
        >
          添加
        </Button>
      </div>
      <ListBox
        items={items}
        empty="暂无，输入后回车或点击添加"
        renderIcon={() => icon}
        onRemove={(i) => onChange(items.filter((_, idx) => idx !== i))}
      />
    </div>
  );
}
