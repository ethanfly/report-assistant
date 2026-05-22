import { useCallback, useEffect, useState } from 'react';
import dayjs from 'dayjs';
import {
  Sparkles,
  RefreshCw,
  FileText,
  Trash2,
  Download,
  FolderOpen,
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { Input, Textarea, Select } from '../components/Input';
import MarkdownView from '../components/MarkdownView';
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

export default function Reports() {
  const toast = useToast();
  const { config } = useConfig();

  const [kind, setKind] = useState<ReportKind>('Daily');
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
      if (items.length && !selected) setSelected(items[0]);
    } catch (e: any) {
      toast.error(`加载报告失败: ${e}`);
    } finally {
      setLoadingList(false);
    }
  }, [toast, selected]);

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

  useEffect(() => {
    if (config && !template) {
      setTemplate(config.report.default_template || '');
    }
  }, [config, template]);

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
        kind,
        anchor: dayjs(anchor).toISOString(),
        template: template || undefined,
        extra_notes: extra,
        include_screenshots: includeShots,
        include_git: includeGit,
      });
      toast.success(
        `已生成${kindLabel(r.kind)}（提交 ${r.commit_count} / 截图 ${r.screenshot_count}）`
      );
      await refresh();
      const full = await getReport(r.report_id);
      if (full) setSelected(full);
    } catch (e: any) {
      toast.error(`生成失败: ${e}`);
    } finally {
      setGenerating(false);
    }
  };

  const onDelete = async (r: Report) => {
    if (!confirm(`确认删除报告「${kindLabel(r.kind)} · ${dayjs(r.period_start).format('YYYY-MM-DD')}」？`)) return;
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

  return (
    <div className="p-6 space-y-5">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">报告</h1>
          <p className="text-sm text-muted mt-1">生成日报 / 周报 / 月报，并管理历史报告</p>
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

      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5">
        {/* 左列：生成表单 */}
        <Card title="生成新报告" description="选择类型与锚点日期，并可附加备注">
          <div className="space-y-3">
            <Select
              label="报告类型"
              value={kind}
              onChange={(e) => setKind(e.target.value as ReportKind)}
            >
              <option value="Daily">日报</option>
              <option value="Weekly">周报</option>
              <option value="Monthly">月报</option>
            </Select>

            <Input
              label="锚点日期"
              type="date"
              value={anchor}
              onChange={(e) => setAnchor(e.target.value)}
              hint={
                kind === 'Weekly'
                  ? '将取所在自然周'
                  : kind === 'Monthly'
                  ? '将取所在自然月'
                  : '取该日 0:00 - 23:59'
              }
            />

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
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeGit}
                  onChange={(e) => setIncludeGit(e.target.checked)}
                  className="accent-primary"
                />
                包含 Git 提交
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
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
              生成报告
            </Button>
          </div>
        </Card>

        {/* 右列：列表 + 预览 */}
        <div className="space-y-4">
          <Card
            title="历史报告"
            description={`已生成 ${reports.length} 份`}
            noPadding
          >
            {reports.length === 0 ? (
              <div className="py-10 text-center text-sm text-muted">
                还没有报告，先在左侧生成一份吧
              </div>
            ) : (
              <ul className="max-h-[260px] overflow-auto divide-y divide-border">
                {reports.map((r) => (
                  <li
                    key={r.id}
                    onClick={() => void onSelect(r)}
                    className={clsx(
                      'px-5 py-3 cursor-pointer flex items-center gap-3 transition',
                      selected?.id === r.id
                        ? 'bg-primary-50/70'
                        : 'hover:bg-zinc-50'
                    )}
                  >
                    <span className="w-7 h-7 rounded-md bg-primary-50 text-primary flex items-center justify-center shrink-0">
                      <FileText size={14} />
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">
                        {kindLabel(r.kind)} ·{' '}
                        {dayjs(r.period_start).format('YYYY-MM-DD')}
                        {r.period_start !== r.period_end &&
                          ` ~ ${dayjs(r.period_end).format('MM-DD')}`}
                      </div>
                      <div className="text-[11px] text-muted mt-0.5">
                        生成于 {dayjs(r.created_at).format('YYYY-MM-DD HH:mm')}
                        {r.template && ` · ${r.template}`}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        void onDelete(r);
                      }}
                      className="p-1.5 rounded-md text-muted hover:text-red-500 hover:bg-red-50"
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
                    loading={exporting === 'txt'}
                    onClick={() => void onExport('txt')}
                  >
                    导出 TXT
                  </Button>
                  <span className="ml-auto text-[11px] text-muted flex items-center gap-1">
                    <FolderOpen size={12} />
                    导出后将定位到目录
                  </span>
                </div>
              )
            }
          >
            {selected ? (
              <div className="max-h-[480px] overflow-auto">
                <MarkdownView content={selected.content} />
              </div>
            ) : (
              <div className="py-12 text-center text-sm text-muted">
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
