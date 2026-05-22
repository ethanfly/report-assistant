import { useCallback, useEffect, useMemo, useState } from 'react';
import dayjs from 'dayjs';
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  GitBranch,
  Camera,
  FileText,
  Trash2,
  RefreshCw,
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { Select } from '../components/Input';
import { deleteWorkLog, listWorkLogs } from '../api/ipc';
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

  const shiftDay = (delta: number) => {
    setDate(dayjs(date).add(delta, 'day').format('YYYY-MM-DD'));
  };

  return (
    <div className="p-6 space-y-5">
      <header className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold">时间线</h1>
          <p className="text-sm text-muted mt-1">查看指定日期的工作流水</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          icon={<RefreshCw size={14} />}
          onClick={() => void refresh()}
          loading={loading}
        >
          刷新
        </Button>
      </header>

      <Card>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              icon={<ChevronLeft size={14} />}
              onClick={() => shiftDay(-1)}
            >
              前一天
            </Button>
            <div className="relative">
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="input-base pl-9 w-[180px]"
              />
              <Calendar
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
              />
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

          <div className="text-xs text-muted">共 {logs.length} 条</div>
        </div>
      </Card>

      {logs.length === 0 ? (
        <Card>
          <div className="py-16 text-center text-sm text-muted">
            该日期暂无记录
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {grouped.map(([hour, items]) => (
            <Card key={hour} noPadding>
              <div className="px-5 pt-4 pb-2 flex items-center gap-2">
                <span className="text-xs font-mono text-muted">{hour}</span>
                <span className="h-px flex-1 bg-border" />
                <span className="text-[11px] text-muted">{items.length} 条</span>
              </div>
              <ul className="divide-y divide-border">
                {items.map((l) => {
                  const open = !!expanded[l.id];
                  return (
                    <li
                      key={l.id}
                      className="px-5 py-3 hover:bg-zinc-50/60 transition group"
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
                              <span className="text-[11px] px-1.5 py-0.5 rounded bg-zinc-100 text-muted">
                                {l.category}
                              </span>
                            )}
                          </div>
                          {l.content && (
                            <div
                              className={clsx(
                                'text-xs text-muted mt-1 whitespace-pre-wrap',
                                !open && 'line-clamp-2'
                              )}
                            >
                              {l.content}
                            </div>
                          )}
                          {l.content && l.content.length > 100 && (
                            <button
                              className="text-[11px] text-primary mt-1 hover:underline"
                              onClick={() =>
                                setExpanded((s) => ({ ...s, [l.id]: !open }))
                              }
                            >
                              {open ? '收起' : '展开'}
                            </button>
                          )}
                        </div>
                        <div className="shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
                          <span className="text-[11px] text-muted font-mono mr-1">
                            {dayjs(l.ts).format('HH:mm:ss')}
                          </span>
                          <button
                            onClick={() => void onDelete(l.id)}
                            className="p-1.5 rounded-md text-muted hover:text-red-500 hover:bg-red-50"
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
      <span className="w-7 h-7 rounded-md bg-primary-50 text-primary flex items-center justify-center">
        <GitBranch size={14} />
      </span>
    );
  }
  if (source === 'screenshot') {
    return (
      <span className="w-7 h-7 rounded-md bg-emerald-50 text-emerald-600 flex items-center justify-center">
        <Camera size={14} />
      </span>
    );
  }
  return (
    <span className="w-7 h-7 rounded-md bg-amber-50 text-amber-600 flex items-center justify-center">
      <FileText size={14} />
    </span>
  );
}
