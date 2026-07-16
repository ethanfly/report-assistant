import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import dayjs from 'dayjs';
import {
  Sparkles,
  RefreshCw,
  FileText,
  Trash2,
  Download,
  FolderOpen,
  CalendarDays,
  CalendarClock,
  CalendarRange,
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { Textarea, Select } from '../components/Input';
import DatePicker from '../components/DatePicker';
import WeekPicker from '../components/WeekPicker';
import MonthPicker from '../components/MonthPicker';
import Tabs from '../components/Tabs';
import MarkdownView from '../components/MarkdownView';
import LoadingOverlay from '../components/LoadingOverlay';
import {
  deleteReport,
  exportReport,
  generateReport,
  getReport,
  listReports,
  listTemplates,
} from '../api/ipc';
import type {
  ExportFormat,
  Report,
  ReportKind,
  ReportTemplate,
} from '../api/types';
import { useToast } from '../hooks/useToast';
import { useConfig } from '../hooks/useConfig';
import { open as openDialog } from '@tauri-apps/plugin-dialog';
import { revealItemInDir } from '@tauri-apps/plugin-opener';
import clsx from 'clsx';

type TabKey = 'Daily' | 'Weekly' | 'Monthly';

const TABS = [
  { key: 'Daily' as const, label: '日报', icon: <CalendarDays size={14} /> },
  { key: 'Weekly' as const, label: '周报', icon: <CalendarRange size={14} /> },
  { key: 'Monthly' as const, label: '月报', icon: <CalendarClock size={14} /> },
];

/** 把 invoke 抛回来的各种形态（Error / 字符串 / 对象）正规化成可读字符串。 */
function formatError(e: unknown): string {
  if (e == null) return '未知错误';
  if (typeof e === 'string') return e;
  if (e instanceof Error) return e.message || String(e);
  if (typeof e === 'object') {
    const anyE = e as { message?: unknown; toString?: () => string };
    if (typeof anyE.message === 'string') return anyE.message;
    try {
      return JSON.stringify(e);
    } catch {
      return String(e);
    }
  }
  return String(e);
}

export default function Reports() {
  const toast = useToast();
  const { config } = useConfig();
  const [searchParams, setSearchParams] = useSearchParams();

  // tab 当前激活的报告类型
  const [tab, setTab] = useState<TabKey>('Daily');

  // 表单字段
  const [anchor, setAnchor] = useState<string>(dayjs().format('YYYY-MM-DD'));
  const [template, setTemplate] = useState<string>('');
  const [extra, setExtra] = useState<string>('');
  const [includeShots, setIncludeShots] = useState(true);
  const [includeGit, setIncludeGit] = useState(true);

  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [selected, setSelected] = useState<Report | null>(null);
  const [loadingList, setLoadingList] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);

  const refresh = useCallback(async () => {
    setLoadingList(true);
    try {
      const items = await listReports(50);
      setReports(items);
    } catch (e: any) {
      toast.error(`加载报告失败: ${e}`);
    } finally {
      setLoadingList(false);
    }
  }, [toast]);

  const refreshTemplates = useCallback(async () => {
    try {
      const t = await listTemplates();
      setTemplates(t);
    } catch (e: any) {
      console.warn('list_templates failed', e);
    }
  }, []);

  useEffect(() => {
    void refresh();
    void refreshTemplates();
  }, [refresh, refreshTemplates]);

  // 从 URL ?kind=daily|weekly|monthly 同步 tab（仅首次）
  useEffect(() => {
    const k = (searchParams.get('kind') || '').toLowerCase();
    const map: Record<string, TabKey> = {
      daily: 'Daily',
      weekly: 'Weekly',
      monthly: 'Monthly',
    };
    if (k && map[k]) {
      setTab(map[k]);
      const next = new URLSearchParams(searchParams);
      next.delete('kind');
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (config && !template) {
      setTemplate(config.report.default_template || '');
    }
  }, [config, template]);

  // 当前 tab 过滤后的报告列表
  const filteredReports = useMemo(() => {
    return reports.filter(
      (r) => r.kind.toLowerCase() === tab.toLowerCase()
    );
  }, [reports, tab]);

  // tab 切换或列表更新时同步 selected
  useEffect(() => {
    if (
      selected &&
      selected.kind.toLowerCase() !== tab.toLowerCase()
    ) {
      setSelected(filteredReports[0] ?? null);
    } else if (!selected && filteredReports.length) {
      setSelected(filteredReports[0]);
    }
  }, [tab, filteredReports, selected]);

  const onSelect = async (r: Report) => {
    setSelected(r);
    try {
      const full = await getReport(r.id);
      if (full) setSelected(full);
    } catch (e: any) {
      toast.error(`加载报告内容失败: ${e}`);
    }
  };

  const onGenerate = async () => {
    if (generating) return;
    setGenerating(true);
    try {
      const r = await generateReport({
        kind: tab as ReportKind,
        anchor: dayjs(anchor).toISOString(),
        template: template || undefined,
        extra_notes: extra,
        include_screenshots: includeShots,
        include_git: includeGit,
      });
      toast.success(
        `已生成${kindLabel(r.kind)}（待办 ${r.todo_count ?? 0} / 提交 ${r.commit_count} / 截图 ${r.screenshot_count}）`
      );
      await refresh();
      const full = await getReport(r.report_id);
      if (full) setSelected(full);
    } catch (e: any) {
      const raw = formatError(e);
      const isTimeout = /timeout|timed out|超时/i.test(raw);
      const message = isTimeout
        ? `响应超时：LLM 没有在配置的超时时间内返回结果。\n\n建议：\n· 增大设置 → LLM 的「超时（秒）」\n· 检查网络或代理是否可访问 base_url\n· 切换为更快的模型，或减少时间窗口内的截图/提交数量`
        : raw;
      toast.alert(message, {
        title: isTimeout ? '响应超时' : `生成${kindLabel(tab as ReportKind)}失败`,
        kind: 'error',
      });
    } finally {
      setGenerating(false);
    }
  };

  const onDelete = async (r: Report) => {
    if (
      !confirm(
        `确认删除报告「${kindLabel(r.kind)} · ${dayjs(r.period_start).format('YYYY-MM-DD')}」？`
      )
    )
      return;
    try {
      const ok = await deleteReport(r.id);
      if (ok) {
        toast.success('已删除');
        if (selected?.id === r.id) setSelected(null);
        await refresh();
      } else {
        toast.error('报告不存在');
      }
    } catch (e: any) {
      toast.error(`删除失败: ${e}`);
    }
  };

  const onExport = async (fmt: ExportFormat) => {
    if (!selected || exporting) return;
    setExporting(fmt);
    try {
      const dir = await openDialog({
        directory: true,
        multiple: false,
        title: '选择导出目录',
      });
      if (!dir || typeof dir !== 'string') {
        setExporting(null);
        return;
      }
      const path = await exportReport(selected.id, fmt, dir);
      toast.success(`已导出: ${path}`);
      try {
        await revealItemInDir(path);
      } catch (_) {
        /* ignore reveal failure */
      }
    } catch (e: any) {
      toast.error(`导出失败: ${e}`);
    } finally {
      setExporting(null);
    }
  };

  const anchorHint =
    tab === 'Weekly'
      ? '将取所在自然周'
      : tab === 'Monthly'
      ? '将取所在自然月'
      : '取该日 0:00 - 23:59';

  return (
    <div className="p-6 space-y-5">
      <LoadingOverlay
        open={generating}
        title={`正在生成${kindLabel(tab as ReportKind)}...`}
      />
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink text-pix">报告</h1>
          <p className="text-sm text-ink2 mt-1">
            生成日报 / 周报 / 月报，并管理历史报告
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          icon={<RefreshCw size={14} />}
          onClick={() => void refresh()}
          loading={loadingList}
        >
          刷新
        </Button>
      </header>

      {/* 报告类型 Tabs */}
      <Tabs tabs={TABS} value={tab} onChange={setTab} />

      <div
        key={tab}
        className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5 animate-fadein"
      >
        {/* 左列：生成表单（按当前 tab） */}
        <Card
          title={`生成${kindLabel(tab)}`}
          description="选择锚点日期，并可附加备注"
        >
          <div className="space-y-3">
            {/* 不同 kind 切换不同选择器 */}
            {tab === 'Daily' && (
              <DatePicker
                label="锚点日期"
                value={anchor}
                onChange={setAnchor}
                hint={anchorHint}
              />
            )}
            {tab === 'Weekly' && (
              <WeekPicker
                label="选择周"
                value={anchor}
                onChange={setAnchor}
                hint={anchorHint}
              />
            )}
            {tab === 'Monthly' && (
              <MonthPicker
                label="选择月"
                value={anchor}
                onChange={setAnchor}
                hint={anchorHint}
              />
            )}

            <Select
              label="模板"
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
            >
              <option value="">（默认）</option>
              {templates.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </Select>

            <Textarea
              label="补充备注（可选）"
              placeholder="例如：今日重点上线了 xxx 模块……"
              rows={4}
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
            />

            <div className="space-y-2 pt-1">
              <label className="flex items-center gap-2 text-sm cursor-pointer text-ink">
                <input
                  type="checkbox"
                  checked={includeGit}
                  onChange={(e) => setIncludeGit(e.target.checked)}
                  className="accent-primary"
                />
                包含 Git 提交
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer text-ink">
                <input
                  type="checkbox"
                  checked={includeShots}
                  onChange={(e) => setIncludeShots(e.target.checked)}
                  className="accent-primary"
                />
                包含截图分析
              </label>
            </div>

            <Button
              className="w-full"
              icon={<Sparkles size={14} />}
              loading={generating}
              onClick={() => void onGenerate()}
            >
              生成{kindLabel(tab)}
            </Button>
          </div>
        </Card>

        {/* 右列：列表 + 预览 */}
        <div className="space-y-4">
          <Card
            title={`历史${kindLabel(tab)}`}
            description={`共 ${filteredReports.length} 份`}
            noPadding
            hoverable={false}
          >
            {filteredReports.length === 0 ? (
              <div className="py-10 text-center text-sm text-ink2">
                还没有{kindLabel(tab)}，先在左侧生成一份吧
              </div>
            ) : (
              <ul className="max-h-[260px] overflow-auto divide-y divide-border">
                {filteredReports.map((r) => (
                  <li
                    key={r.id}
                    onClick={() => void onSelect(r)}
                    className={clsx(
                      'px-5 py-3 cursor-pointer flex items-center gap-3 transition-colors',
                      selected?.id === r.id
                        ? 'bg-primary-50'
                        : 'hover:bg-bg'
                    )}
                  >
                    <span className="w-7 h-7 rounded-pix bg-primary-50 text-primary-700 flex items-center justify-center shrink-0 border border-primary-200">
                      <FileText size={14} />
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate text-ink">
                        {kindLabel(r.kind)} ·{' '}
                        {dayjs(r.period_start).format('YYYY-MM-DD')}
                        {r.period_start !== r.period_end &&
                          ` ~ ${dayjs(r.period_end).format('MM-DD')}`}
                      </div>
                      <div className="text-[11px] text-ink2 mt-0.5">
                        生成于 {dayjs(r.created_at).format('YYYY-MM-DD HH:mm')}
                        {r.template && ` · ${r.template}`}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        void onDelete(r);
                      }}
                      className="p-1.5 rounded-pix text-ink2 hover:text-red-500 hover:bg-red-50 transition-colors"
                      title="删除"
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card
            title="报告预览"
            description={
              selected
                ? `${kindLabel(selected.kind)} · ${dayjs(selected.period_start).format('YYYY-MM-DD')}`
                : '从上方列表选择一份报告'
            }
            hoverable={false}
            footer={
              selected && (
                <div className="flex items-center gap-2 flex-wrap">
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Download size={14} />}
                    loading={exporting === 'md'}
                    onClick={() => void onExport('md')}
                  >
                    导出 MD
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Download size={14} />}
                    loading={exporting === 'html'}
                    onClick={() => void onExport('html')}
                  >
                    导出 HTML
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Download size={14} />}
                    loading={exporting === 'docx'}
                    onClick={() => void onExport('docx')}
                  >
                    导出 Word
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Download size={14} />}
                    loading={exporting === 'txt'}
                    onClick={() => void onExport('txt')}
                  >
                    导出 TXT
                  </Button>
                  <span className="ml-auto text-[11px] text-ink2 flex items-center gap-1">
                    <FolderOpen size={12} />
                    导出后将定位到目录
                  </span>
                </div>
              )
            }
          >
            {selected ? (
              <div className="max-h-[480px] overflow-auto selectable">
                <MarkdownView content={selected.content} />
              </div>
            ) : (
              <div className="py-12 text-center text-sm text-ink2">
                未选中任何报告
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function kindLabel(k: string): string {
  switch (k.toLowerCase()) {
    case 'daily':
      return '日报';
    case 'weekly':
      return '周报';
    case 'monthly':
      return '月报';
    default:
      return k;
  }
}
