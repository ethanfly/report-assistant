import { useCallback, useEffect, useMemo, useState } from 'react';
import dayjs from 'dayjs';
import {
  ChevronLeft,
  ChevronRight,
  GitBranch,
  Camera,
  FileText,
  Trash2,
  RefreshCw,
  Plus,
  X,
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { Select, Textarea } from '../components/Input';
import DatePicker from '../components/DatePicker';
import LoadingOverlay from '../components/LoadingOverlay';
import { addManualLog, deleteWorkLog, listWorkLogs } from '../api/ipc';
import type { WorkLog } from '../api/types';
import { useToast } from '../hooks/useToast';
import clsx from 'clsx';

type SourceFilter = 'all' | 'git' | 'screenshot' | 'manual';

export default function Timeline() {
  const toast = useToast();
  const [date, setDate] = useState<string>(dayjs().format('YYYY-MM-DD'));
  const [filter, setFilter] = useState<SourceFilter>('all');
  const [logs, setLogs] = useState<WorkLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  // 手动添加表单：modal 开关 + 草稿
  const [showAdd, setShowAdd] = useState(false);
  const [draftDesc, setDraftDesc] = useState('');
  const [draftTime, setDraftTime] = useState(''); // HH:mm，空 = 现在
  const [adding, setAdding] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const start = dayjs(date).startOf('day').toISOString();
      const end = dayjs(date).endOf('day').toISOString();
      const items = await listWorkLogs(
        start,
        end,
        filter === 'all' ? undefined : filter
      );
      setLogs(items);
    } catch (e: any) {
      toast.error(`加载失败: ${e}`);
    } finally {
      setLoading(false);
    }
  }, [date, filter, toast]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const grouped = useMemo(() => {
    const map = new Map<string, WorkLog[]>();
    for (const l of logs) {
      const h = dayjs(l.ts).format('HH:00');
      const arr = map.get(h) || [];
      arr.push(l);
      map.set(h, arr);
    }
    return Array.from(map.entries()).sort((a, b) =>
      a[0] < b[0] ? 1 : -1
    );
  }, [logs]);

  const onDelete = async (id: number) => {
    if (!confirm('确认删除该条记录？此操作不可撤销。')) return;
    try {
      const ok = await deleteWorkLog(id);
      if (ok) {
        toast.success('已删除');
        await refresh();
      } else {
        toast.error('记录不存在');
      }
    } catch (e: any) {
      toast.error(`删除失败: ${e}`);
    }
  };

  const openAdd = () => {
    setDraftDesc('');
    setDraftTime(dayjs().format('HH:mm'));
    setShowAdd(true);
  };

  const onSubmitAdd = async () => {
    const desc = draftDesc.trim();
    if (!desc) {
      toast.alert('请先填写工作描述', { kind: 'warning', title: '内容为空' });
      return;
    }
    if (adding) return;

    // 把当前选中日期 + 用户输入的 HH:mm 拼成 ISO 时间戳；时间空则用当下
    const iso = (() => {
      const t = draftTime.trim();
      if (!t) return undefined;
      const m = /^(\d{1,2}):(\d{1,2})$/.exec(t);
      if (!m) return null; // 标记格式错
      const hh = Number(m[1]);
      const mm = Number(m[2]);
      if (hh > 23 || mm > 59) return null;
      return dayjs(date)
        .hour(hh)
        .minute(mm)
        .second(0)
        .millisecond(0)
        .toISOString();
    })();

    if (iso === null) {
      toast.alert('时间格式应为 HH:mm，例如 14:30', {
        kind: 'warning',
        title: '时间无效',
      });
      return;
    }

    setAdding(true);
    try {
      const log = await addManualLog(desc, iso);
      setShowAdd(false);
      await refresh();
      toast.alert(
        [
          '已保存到时间线，已自动完成扩写与分类。',
          '',
          `分类：${log.category ?? '其他'}`,
          `标题：${log.title}`,
          '',
          '后续流程：',
          '1) 这条记录会与截图、Git 提交一起进入当天的工作日志',
          '2) 生成日报/周报/月报时会自动汇总进去',
          '3) 不满意可在时间线 hover 该条 → 点垃圾桶删除',
        ].join('\n'),
        {
          kind: 'success',
          title: '记录已添加',
          okLabel: '知道了',
        }
      );
    } catch (e: any) {
      const raw =
        typeof e === 'string'
          ? e
          : (e?.message as string | undefined) ?? String(e);
      const isTimeout = /timeout|timed out|超时/i.test(raw);
      toast.alert(
        isTimeout
          ? '响应超时：模型未在配置的超时时间内返回。建议增大设置 → LLM 的超时秒数，或换一个更快的文本模型。'
          : raw,
        { title: isTimeout ? '响应超时' : '添加失败', kind: 'error' }
      );
    } finally {
      setAdding(false);
    }
  };

  const shiftDay = (delta: number) => {
    setDate(dayjs(date).add(delta, 'day').format('YYYY-MM-DD'));
  };

  return (
    <div className="p-6 space-y-5">
      <LoadingOverlay
        open={adding}
        title="正在保存并扩写..."
        description="模型正在丰富你输入的工作描述，并自动归类。"
      />
      {showAdd && (
        <AddManualModal
          desc={draftDesc}
          time={draftTime}
          dateLabel={date}
          submitting={adding}
          onDescChange={setDraftDesc}
          onTimeChange={setDraftTime}
          onClose={() => !adding && setShowAdd(false)}
          onSubmit={() => void onSubmitAdd()}
        />
      )}
      <header className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink text-pix">时间线</h1>
          <p className="text-sm text-ink2 mt-1">查看指定日期的工作流水</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            icon={<Plus size={14} />}
            onClick={openAdd}
          >
            添加记录
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon={<RefreshCw size={14} />}
            onClick={() => void refresh()}
            loading={loading}
          >
            刷新
          </Button>
        </div>
      </header>

      <Card hoverable={false}>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              icon={<ChevronLeft size={14} />}
              onClick={() => shiftDay(-1)}
            >
              前一天
            </Button>
            <div className="w-[180px]">
              <DatePicker value={date} onChange={setDate} />
            </div>
            <Button
              variant="ghost"
              size="sm"
              icon={<ChevronRight size={14} />}
              onClick={() => shiftDay(1)}
            >
              后一天
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDate(dayjs().format('YYYY-MM-DD'))}
            >
              今天
            </Button>
          </div>

          <div className="ml-auto w-[160px]">
            <Select
              value={filter}
              onChange={(e) => setFilter(e.target.value as SourceFilter)}
            >
              <option value="all">全部来源</option>
              <option value="git">Git 提交</option>
              <option value="screenshot">截图</option>
              <option value="manual">手动</option>
            </Select>
          </div>

          <div className="text-xs text-ink2">共 {logs.length} 条</div>
        </div>
      </Card>

      {logs.length === 0 ? (
        <Card hoverable={false}>
          <div className="py-16 text-center text-sm text-ink2">
            该日期暂无记录
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {grouped.map(([hour, items]) => (
            <Card key={hour} noPadding hoverable={false}>
              <div className="px-5 pt-4 pb-2 flex items-center gap-2">
                <span className="text-xs font-mono text-primary-700 bg-primary-50 px-2 py-0.5 rounded-pix border border-primary-200">
                  {hour}
                </span>
                <span className="h-px flex-1 bg-border" />
                <span className="text-[11px] text-ink2">{items.length} 条</span>
              </div>
              <ul className="divide-y divide-border">
                {items.map((l) => {
                  const open = !!expanded[l.id];
                  return (
                    <li
                      key={l.id}
                      className="px-5 py-3 hover:bg-bg/60 transition-colors group"
                    >
                      <div className="flex items-start gap-3">
                        <div className="shrink-0 pt-0.5">
                          <SourceIcon source={l.source} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-medium text-ink truncate">
                              {l.title || '(无标题)'}
                            </span>
                            {l.category && (
                              <span className="text-[11px] px-1.5 py-0.5 rounded-pix bg-bg text-ink2 border border-border">
                                {l.category}
                              </span>
                            )}
                          </div>
                          {l.content && (
                            <div
                              className={clsx(
                                'text-xs text-ink2 mt-1 whitespace-pre-wrap',
                                !open && 'line-clamp-2'
                              )}
                            >
                              {l.content}
                            </div>
                          )}
                          {l.content && l.content.length > 100 && (
                            <button
                              className="text-[11px] text-primary-700 mt-1 hover:underline"
                              onClick={() =>
                                setExpanded((s) => ({ ...s, [l.id]: !open }))
                              }
                            >
                              {open ? '收起' : '展开'}
                            </button>
                          )}
                        </div>
                        <div className="shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <span className="text-[11px] text-ink2 font-mono mr-1">
                            {dayjs(l.ts).format('HH:mm:ss')}
                          </span>
                          <button
                            onClick={() => void onDelete(l.id)}
                            className="p-1.5 rounded-pix text-ink2 hover:text-red-500 hover:bg-red-50 transition-colors"
                            title="删除"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function SourceIcon({ source }: { source: string }) {
  if (source === 'git') {
    return (
      <span className="w-7 h-7 rounded-pix bg-primary-50 text-primary-700 flex items-center justify-center border border-primary-200">
        <GitBranch size={14} />
      </span>
    );
  }
  if (source === 'screenshot') {
    return (
      <span className="w-7 h-7 rounded-pix bg-primary-100 text-primary-800 flex items-center justify-center border border-primary-200">
        <Camera size={14} />
      </span>
    );
  }
  return (
    <span className="w-7 h-7 rounded-pix bg-accent-50 text-accent-600 flex items-center justify-center border border-accent-100">
      <FileText size={14} />
    </span>
  );
}

/**
 * 手动添加记录的模态框：让用户填一段简短描述 + 时间。
 * 关闭走外部传入的 onClose（提交中时禁用关闭）。
 */
function AddManualModal({
  desc,
  time,
  dateLabel,
  submitting,
  onDescChange,
  onTimeChange,
  onClose,
  onSubmit,
}: {
  desc: string;
  time: string;
  dateLabel: string;
  submitting: boolean;
  onDescChange: (v: string) => void;
  onTimeChange: (v: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40">
      <div
        role="dialog"
        aria-modal="true"
        className="max-w-lg w-[90%] bg-card border border-border rounded-lg shadow-lg"
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <div className="text-sm font-semibold text-ink">添加工作记录</div>
          <button
            type="button"
            className="text-ink2 hover:text-ink disabled:opacity-50"
            onClick={onClose}
            disabled={submitting}
            aria-label="关闭"
          >
            <X size={16} />
          </button>
        </div>
        <div className="px-5 py-4 space-y-3">
          <Textarea
            label="工作描述"
            value={desc}
            onChange={(e) => onDescChange(e.target.value)}
            rows={4}
            placeholder="例如：跟产品对齐了下周的迭代范围，确认两个新需求的边界"
            hint="保存后会调用文本模型扩写并自动分类，不要写敏感的人名/项目代号"
            disabled={submitting}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="w-full">
              <label className="label">日期</label>
              <div className="input-base flex items-center text-ink2 cursor-not-allowed select-none">
                {dateLabel}
              </div>
              <p className="hint">沿用页面顶部选中的日期</p>
            </div>
            <div className="w-full">
              <label className="label">时间（HH:mm）</label>
              <input
                type="text"
                value={time}
                onChange={(e) => onTimeChange(e.target.value)}
                placeholder="例如 14:30"
                disabled={submitting}
                className="input-base"
              />
              <p className="hint">留空则使用当前时间</p>
            </div>
          </div>
        </div>
        <div className="px-5 py-3 border-t border-border flex justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            disabled={submitting}
          >
            取消
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={onSubmit}
            loading={submitting}
          >
            保存并扩写
          </Button>
        </div>
      </div>
    </div>
  );
}
