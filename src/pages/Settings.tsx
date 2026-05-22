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
  listTemplates,
  openLogDir,
  purgeAll,
  purgeBefore,
  storageStats,
  testLlmConnection,
} from '../api/ipc';
import { useConfig } from '../hooks/useConfig';
import type {
  Config,
  LlmProvider,
  ReportTemplate,
  StorageStats,
} from '../api/types';
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
  // 报告模板列表（来自后端 listTemplates）
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);

  // 拉取模板（一次性，挂载时）
  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .catch(() => setTemplates([]));
  }, []);
  const [purging, setPurging] = useState(false);
  const [purgeDays, setPurgeDays] = useState(30);
  // 当前选中编辑的 LLM provider id；默认选中第一个
  const [selectedProviderId, setSelectedProviderId] = useState<string>('');

  // draft 加载后，若已有 providers 而未选中任何项，自动选第一个
  useEffect(() => {
    if (!draft) return;
    const list = draft.llm.providers ?? [];
    if (selectedProviderId && list.some((p) => p.id === selectedProviderId)) return;
    setSelectedProviderId(list[0]?.id ?? '');
  }, [draft, selectedProviderId]);

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

  // 当前选中的 LLM provider 草稿；用于编辑面板
  const selectedProvider: LlmProvider | null =
    draft?.llm.providers.find((p) => p.id === selectedProviderId) ?? null;

  const onTest = async () => {
    if (!selectedProvider) {
      toast.error('请先选中要测试的 provider');
      return;
    }
    if (testing) return;
    setTesting(true);
    try {
      const [ok, msg] = await testLlmConnection(selectedProvider);
      if (ok) toast.success(`连接成功：${msg || ''}`);
      else toast.error(`连接失败：${msg}`);
    } catch (e: any) {
      toast.error(`测试失败: ${e}`);
    } finally {
      setTesting(false);
    }
  };

  /** 生成简单短随机 id，避免依赖 crypto.randomUUID 在低版本 webview 不可用 */
  const genProviderId = () => 'p-' + Math.random().toString(36).slice(2, 10);

  /** 添加新 provider；template 决定预填字段。返回新 id 以便选中。 */
  const addProvider = (template: 'openai' | 'claude' | 'custom') => {
    if (!draft) return;
    const id = genProviderId();
    let fresh: LlmProvider;
    switch (template) {
      case 'openai':
        fresh = {
          id,
          name: 'OpenAI',
          provider: 'openai',
          base_url: 'https://api.openai.com/v1',
          api_key: '',
          model: 'gpt-4o-mini',
          temperature: 0.4,
          timeout: 60,
        };
        break;
      case 'claude':
        // Anthropic 官方端点对 OpenAI 兼容协议有自己的网关；
        // 这里默认填官方 Messages API 路径。如要走 OpenAI 兼容代理可手动改 base_url。
        fresh = {
          id,
          name: 'Claude',
          provider: 'anthropic',
          base_url: 'https://api.anthropic.com/v1',
          api_key: '',
          model: 'claude-3-5-sonnet-latest',
          temperature: 0.4,
          timeout: 60,
        };
        break;
      default:
        fresh = {
          id,
          name: '',
          provider: 'openai',
          base_url: '',
          api_key: '',
          model: '',
          temperature: 0.4,
          timeout: 60,
        };
    }
    const next: Config = {
      ...draft,
      llm: {
        ...draft.llm,
        providers: [...draft.llm.providers, fresh],
        // 第一条添加时自动设为默认
        default_text_id: draft.llm.default_text_id || id,
        default_vision_id: draft.llm.default_vision_id || id,
      },
    };
    setDraft(next);
    setSelectedProviderId(id);
  };

  const updateProvider = (id: string, patch: Partial<LlmProvider>) => {
    if (!draft) return;
    const next: Config = {
      ...draft,
      llm: {
        ...draft.llm,
        providers: draft.llm.providers.map((p) =>
          p.id === id ? { ...p, ...patch } : p
        ),
      },
    };
    setDraft(next);
  };

  const removeProvider = (id: string) => {
    if (!draft) return;
    const list = draft.llm.providers.filter((p) => p.id !== id);
    const next: Config = {
      ...draft,
      llm: {
        ...draft.llm,
        providers: list,
        default_text_id:
          draft.llm.default_text_id === id ? '' : draft.llm.default_text_id,
        default_vision_id:
          draft.llm.default_vision_id === id ? '' : draft.llm.default_vision_id,
      },
    };
    setDraft(next);
    if (selectedProviderId === id) {
      setSelectedProviderId(list[0]?.id ?? '');
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
      const existing = new Set(draft.git.repos.map((r) => r.path));
      const additions = list
        .filter((p) => !existing.has(p))
        .map((p) => ({ path: p, alias: '' }));
      if (additions.length === 0) return;
      update('git', { ...draft.git, repos: [...draft.git.repos, ...additions] });
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
            description="管理多个大模型 provider，可分别指定默认文本模型与视觉模型"
            hoverable={false}
          >
            {/* 顶部：添加按钮 */}
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-medium text-ink">Providers</label>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Plus size={14} />}
                  onClick={() => addProvider('openai')}
                >
                  添加 OpenAI
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Plus size={14} />}
                  onClick={() => addProvider('claude')}
                >
                  添加 Claude
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Plus size={14} />}
                  onClick={() => addProvider('custom')}
                >
                  自定义
                </Button>
              </div>
            </div>

            {/* providers 列表 */}
            <div className="border border-border rounded-md divide-y divide-border bg-card mb-4">
              {draft.llm.providers.length === 0 ? (
                <div className="px-3 py-6 text-sm text-ink2 text-center">
                  尚未添加任何 provider。点击右上方按钮选择模板新建一个。
                </div>
              ) : (
                draft.llm.providers.map((p) => {
                  const isSelected = p.id === selectedProviderId;
                  const isText = p.id === draft.llm.default_text_id;
                  const isVision = p.id === draft.llm.default_vision_id;
                  return (
                    <div
                      key={p.id}
                      onClick={() => setSelectedProviderId(p.id)}
                      className={`flex items-center gap-2 px-3 py-2 cursor-pointer group ${
                        isSelected ? 'bg-primary-50' : 'hover:bg-bg'
                      }`}
                    >
                      <Cpu
                        size={14}
                        className={
                          isSelected ? 'text-primary-700' : 'text-ink2'
                        }
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-ink truncate">
                          {p.name?.trim()
                            ? p.name
                            : `${p.provider || '未命名'} · ${p.model || '未填模型'}`}
                        </div>
                        <div className="text-[11px] text-ink2 truncate">
                          {p.provider} · {p.model || '未填模型'} · {p.base_url || '未填 base_url'}
                        </div>
                      </div>
                      {isText && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary-100 text-primary-700">
                          文本默认
                        </span>
                      )}
                      {isVision && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-100 text-accent-700">
                          视觉默认
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeProvider(p.id);
                        }}
                        className="text-ink2 hover:text-red-500 px-1 opacity-0 group-hover:opacity-100 transition-opacity"
                        aria-label="移除"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  );
                })
              )}
            </div>

            {/* 编辑面板 */}
            {selectedProvider ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Input
                  label="显示名称"
                  value={selectedProvider.name}
                  onChange={(e) =>
                    updateProvider(selectedProvider.id, { name: e.target.value })
                  }
                  placeholder="用于在列表中识别这条 provider"
                />
                <Input
                  label="Provider"
                  value={selectedProvider.provider}
                  onChange={(e) =>
                    updateProvider(selectedProvider.id, {
                      provider: e.target.value,
                    })
                  }
                  placeholder="openai / azure / ollama / anthropic..."
                />
                <Input
                  label="Base URL"
                  value={selectedProvider.base_url}
                  onChange={(e) =>
                    updateProvider(selectedProvider.id, {
                      base_url: e.target.value,
                    })
                  }
                  placeholder="https://api.openai.com/v1"
                />
                <Input
                  label="API Key"
                  type="password"
                  value={selectedProvider.api_key}
                  onChange={(e) =>
                    updateProvider(selectedProvider.id, {
                      api_key: e.target.value,
                    })
                  }
                  placeholder="sk-..."
                />
                <Input
                  label="模型"
                  value={selectedProvider.model}
                  onChange={(e) =>
                    updateProvider(selectedProvider.id, {
                      model: e.target.value,
                    })
                  }
                  placeholder="gpt-4o-mini / claude-3-5-sonnet-latest"
                />
                <Input
                  label="Temperature"
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  value={selectedProvider.temperature}
                  onChange={(e) =>
                    updateProvider(selectedProvider.id, {
                      temperature: Number(e.target.value),
                    })
                  }
                />
                <Input
                  label="超时（秒）"
                  type="number"
                  min="1"
                  value={selectedProvider.timeout}
                  onChange={(e) =>
                    updateProvider(selectedProvider.id, {
                      timeout: Number(e.target.value),
                    })
                  }
                />
              </div>
            ) : null}

            {/* 默认选择 + 测试按钮 */}
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
              <Select
                label="默认文本模型"
                value={draft.llm.default_text_id}
                onChange={(e) =>
                  update('llm', { ...draft.llm, default_text_id: e.target.value })
                }
              >
                <option value="">— 未指定 —</option>
                {draft.llm.providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name?.trim() ? p.name : `${p.provider} · ${p.model}`}
                  </option>
                ))}
              </Select>
              <Select
                label="默认视觉模型"
                value={draft.llm.default_vision_id}
                onChange={(e) =>
                  update('llm', {
                    ...draft.llm,
                    default_vision_id: e.target.value,
                  })
                }
              >
                <option value="">— 未指定 —</option>
                {draft.llm.providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name?.trim() ? p.name : `${p.provider} · ${p.model}`}
                  </option>
                ))}
              </Select>
            </div>

            <div className="mt-3">
              <Button
                variant="secondary"
                size="sm"
                icon={<Plug size={14} />}
                onClick={() => void onTest()}
                loading={testing}
                disabled={!selectedProvider}
              >
                测试当前 provider
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
                <div className="border border-border rounded-md divide-y divide-border bg-card">
                  {draft.git.repos.length === 0 ? (
                    <div className="px-3 py-4 text-sm text-ink2 text-center">
                      尚未添加任何仓库，点击上方按钮添加。
                    </div>
                  ) : (
                    draft.git.repos.map((repo, i) => (
                      <div
                        key={`${repo.path}-${i}`}
                        className="flex items-center gap-2 px-3 py-2 hover:bg-bg group"
                      >
                        <FolderGit2
                          size={14}
                          className="text-primary shrink-0"
                        />
                        <span
                          className="text-sm text-ink truncate flex-1 min-w-0"
                          title={repo.path}
                        >
                          {repo.path}
                        </span>
                        <input
                          type="text"
                          value={repo.alias ?? ''}
                          placeholder="显示名称（可选）"
                          className="w-40 h-7 px-2 text-xs rounded border border-border bg-white focus:outline-none focus:ring-1 focus:ring-primary"
                          onChange={(e) => {
                            const next = draft.git.repos.map((r, idx) =>
                              idx === i
                                ? { ...r, alias: e.target.value }
                                : r
                            );
                            update('git', { ...draft.git, repos: next });
                          }}
                        />
                        <button
                          type="button"
                          onClick={() =>
                            update('git', {
                              ...draft.git,
                              repos: draft.git.repos.filter(
                                (_, idx) => idx !== i
                              ),
                            })
                          }
                          className="text-ink2 hover:text-red-500 px-1 opacity-0 group-hover:opacity-100 transition-opacity"
                          aria-label="移除"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))
                  )}
                </div>
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
              <Select
                label="默认模板"
                value={draft.report.default_template}
                onChange={(e) =>
                  update('report', {
                    ...draft.report,
                    default_template: e.target.value,
                  })
                }
              >
                {templates.length === 0 ? (
                  <option value={draft.report.default_template}>
                    {draft.report.default_template || 'standard'}
                  </option>
                ) : (
                  templates.map((t) => (
                    <option key={t.key} value={t.key}>
                      {t.label}（{t.key}）
                    </option>
                  ))
                )}
              </Select>
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
