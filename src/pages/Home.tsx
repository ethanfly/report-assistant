import { useEffect, useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import {
  Camera,
  GitBranch,
  FileText,
  Activity,
  Play,
  Square,
  RefreshCw,
  Monitor,
  CalendarDays,
  CalendarRange,
  CalendarClock,
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import {
  captureOnce,
  generateReport,
  listMonitors,
  listWorkLogs,
  startWatch,
  stopWatch,
  syncGit,
} from '../api/ipc';
import type { MonitorInfo, WorkLog } from '../api/types';
import { useConfig } from '../hooks/useConfig';
import { useWatchStatus } from '../hooks/useWatchStatus';
import { useToast } from '../hooks/useToast';
import clsx from 'clsx';

/** 顶部 4 张统计卡 */
function StatCard({
  label,
  value,
  icon,
  accent,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  icon: React.ReactNode;
  accent: string;
  hint?: string;
}) {
  return (
    <div className="card hover:-translate-y-px hover:shadow-soft flex items-center gap-4">
      <div
        className={clsx(
          'w-11 h-11 rounded-pix flex items-center justify-center border border-border',
          accent
        )}
      >
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs text-ink2">{label}</div>
        <div className="text-2xl font-semibold mt-0.5 text-ink">{value}</div>
        {hint && <div className="text-[11px] text-ink2 mt-1">{hint}</div>}
      </div>
    </div>
  );
}

export default function Home() {
  const toast = useToast();
  const navigate = useNavigate();
  const { config, save } = useConfig();
  const { status } = useWatchStatus();

  const [logs, setLogs] = useState<WorkLog[]>([]);
  const [monitors, setMonitors] = useState<MonitorInfo[]>([]);
  const [loading, setLoading] = useState(false);

  const [busy, setBusy] = useState<{ [k: string]: boolean }>({});

  const refreshLogs = useCallback(async () => {
    setLoading(true);
    try {
      const start = dayjs().startOf('day').toISOString();
      const end = dayjs().endOf('day').toISOString();
      const items = await listWorkLogs(start, end);
      setLogs(items);
    } catch (e: any) {
      toast.error(`加载今日记录失败: ${e}`);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const refreshMonitors = useCallback(async () => {
    try {
      const m = await listMonitors();
      setMonitors(m);
    } catch (e: any) {
      console.warn('list_monitors failed', e);
    }
  }, []);

  useEffect(() => {
    void refreshLogs();
    void refreshMonitors();
  }, [refreshLogs, refreshMonitors]);

  useEffect(() => {
    if (status.lastEvent && status.lastEvent.type === 'captured') {
      void refreshLogs();
    }
  }, [status.lastEvent, refreshLogs]);

  const todayCommits = useMemo(
    () => logs.filter((l) => l.source === 'git').length,
    [logs]
  );
  const todayShots = useMemo(
    () => logs.filter((l) => l.source === 'screenshot').length,
    [logs]
  );

  // 倒序：最新在前
  const sortedLogs = useMemo(
    () => [...logs].sort((a, b) => b.ts.localeCompare(a.ts)),
    [logs]
  );

  async function withBusy(key: string, fn: () => Promise<void>) {
    if (busy[key]) return;
    setBusy((s) => ({ ...s, [key]: true }));
    try {
      await fn();
    } finally {
      setBusy((s) => ({ ...s, [key]: false }));
    }
  }

  const onStart = () =>
    withBusy('start', async () => {
      try {
        await startWatch();
        toast.success('已开始截图监听');
      } catch (e: any) {
        toast.error(`启动失败: ${e}`);
      }
    });

  const onStop = () =>
    withBusy('stop', async () => {
      try {
        await stopWatch();
        toast.info('已停止监听');
      } catch (e: any) {
        toast.error(`停止失败: ${e}`);
      }
    });

  const onCapture = () =>
    withBusy('cap', async () => {
      try {
        const log = await captureOnce();
        toast.success(`已截图：${log.title || '无标题'}`);
        await refreshLogs();
      } catch (e: any) {
        toast.error(`截图失败: ${e}`);
      }
    });

  const onSyncGit = () =>
    withBusy('git', async () => {
      try {
        const n = await syncGit();
        toast.success(`Git 全量覆盖同步完成，已导入 ${n} 条提交`);
        await refreshLogs();
      } catch (e: any) {
        toast.error(`Git 同步失败: ${e}`);
      }
    });

  const onGenDaily = () =>
    withBusy('gen', async () => {
      try {
        const r = await generateReport({
          kind: 'Daily',
          anchor: dayjs().toISOString(),
          template: config?.report.default_template,
          extra_notes: '',
          include_screenshots: true,
          include_git: true,
        });
        toast.success(
          `已生成今日日报（提交 ${r.commit_count} 条 / 截图 ${r.screenshot_count} 条）`
        );
      } catch (e: any) {
        toast.error(`生成失败: ${e}`);
      }
    });

  const onChangeMonitor = async (idx: number) => {
    if (!config) return;
    const next = {
      ...config,
      screenshot: { ...config.screenshot, monitor_index: idx },
    };
    try {
      await save(next);
      toast.success(`已切换至显示器 #${idx}`);
    } catch (e: any) {
      toast.error(`保存配置失败: ${e}`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink text-pix">首页</h1>
          <p className="text-sm text-ink2 mt-1">
            欢迎{config?.report.user_name ? `，${config.report.user_name}` : ''}！查看今日工作概览。
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          icon={<RefreshCw size={14} />}
          onClick={() => void refreshLogs()}
          loading={loading}
        >
          刷新
        </Button>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="今日提交"
          value={todayCommits}
          icon={<GitBranch size={20} className="text-primary-700" />}
          accent="bg-primary-50"
        />
        <StatCard
          label="今日截图"
          value={todayShots}
          icon={<Camera size={20} className="text-primary-700" />}
          accent="bg-primary-100"
        />
        <StatCard
          label="今日条目"
          value={logs.length}
          icon={<FileText size={20} className="text-accent-600" />}
          accent="bg-accent-50"
        />
        <StatCard
          label="监听状态"
          value={
            <span
              className={clsx(
                'text-base font-semibold',
                status.running ? 'text-primary-700' : 'text-ink2'
              )}
            >
              {status.running ? '监听中' : '已停止'}
            </span>
          }
          icon={
            <Activity
              size={20}
              className={status.running ? 'text-primary-700' : 'text-ink2'}
            />
          }
          accent={status.running ? 'bg-primary-50' : 'bg-bg'}
          hint={
            status.running && status.intervalSeconds
              ? `每 ${status.intervalSeconds}s 一次`
              : undefined
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="快速操作" className="lg:col-span-2">
          {/* 6 个等高按钮，3 列网格，并排时统一对齐 */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            {status.running ? (
              <Button
                variant="secondary"
                size="md"
                icon={<Square size={14} />}
                onClick={onStop}
                loading={busy.stop}
                className="w-full"
              >
                停止监听
              </Button>
            ) : (
              <Button
                variant="primary"
                size="md"
                icon={<Play size={14} />}
                onClick={onStart}
                loading={busy.start}
                className="w-full"
              >
                开始监听
              </Button>
            )}
            <Button
              variant="secondary"
              size="md"
              icon={<Camera size={14} />}
              onClick={onCapture}
              loading={busy.cap}
              className="w-full"
            >
              立即截图
            </Button>
            <Button
              variant="secondary"
              size="md"
              icon={<GitBranch size={14} />}
              onClick={onSyncGit}
              loading={busy.git}
              className="w-full"
            >
              同步 Git
            </Button>
            <Button
              variant="primary"
              size="md"
              icon={<CalendarDays size={14} />}
              onClick={onGenDaily}
              loading={busy.gen}
              className="w-full"
            >
              生成今日日报
            </Button>
            <Button
              variant="secondary"
              size="md"
              icon={<CalendarRange size={14} />}
              onClick={() => navigate('/reports?kind=weekly')}
              className="w-full"
            >
              生成本周周报
            </Button>
            <Button
              variant="secondary"
              size="md"
              icon={<CalendarClock size={14} />}
              onClick={() => navigate('/reports?kind=monthly')}
              className="w-full"
            >
              生成本月月报
            </Button>
          </div>
        </Card>

        <Card
          title="显示器选择"
          description="点击切换截图目标，会自动保存到配置"
        >
          <div className="space-y-2 max-h-[180px] overflow-auto pr-1">
            {monitors.length === 0 && (
              <div className="text-sm text-ink2 py-2">暂未检测到显示器</div>
            )}
            {monitors.map((m) => {
              const active = config?.screenshot.monitor_index === m.index;
              return (
                <button
                  key={m.index}
                  onClick={() => void onChangeMonitor(m.index)}
                  className={clsx(
                    'w-full flex items-center gap-3 px-3 py-2 rounded-pix border text-left transition-all',
                    active
                      ? 'border-primary bg-primary-50'
                      : 'border-border hover:bg-bg hover:border-primary-300'
                  )}
                >
                  <Monitor
                    size={16}
                    className={active ? 'text-primary-700' : 'text-ink2'}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate text-ink">
                      #{m.index} {m.label}
                    </div>
                    <div className="text-xs text-ink2">
                      {m.width}×{m.height}
                    </div>
                  </div>
                  {active && (
                    <span className="text-[11px] text-primary-700 font-medium">
                      已选中
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </Card>
      </div>

      <Card
        title="最近工作流水"
        description="今日采集到的所有工作记录（最新在前）"
      >
        {logs.length === 0 ? (
          <div className="py-10 text-center text-sm text-ink2">
            今日暂无记录，开启监听或点击立即截图试试
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {sortedLogs.slice(0, 30).map((l) => (
              <li key={l.id} className="py-3 flex items-start gap-3 hover:bg-bg/40 -mx-2 px-2 rounded-pix transition-colors">
                <SourceTag source={l.source} category={l.category} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ink truncate">
                    {l.title || '(无标题)'}
                  </div>
                  {l.content && (
                    <div className="text-xs text-ink2 line-clamp-2 mt-0.5">
                      {l.content}
                    </div>
                  )}
                </div>
                <div className="text-[11px] text-ink2 shrink-0 font-mono">
                  {dayjs(l.ts).format('HH:mm:ss')}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function SourceTag({ source, category }: { source: string; category?: string }) {
  let cls = 'bg-bg text-ink2';
  let label = source;
  if (source === 'git') {
    cls = 'bg-primary-50 text-primary-700';
    label = 'Git';
  } else if (source === 'screenshot') {
    cls = 'bg-primary-100 text-primary-800';
    label = '截图';
  } else if (source === 'manual') {
    cls = 'bg-accent-50 text-accent-600';
    label = '手动';
  }
  return (
    <div className="flex flex-col items-start shrink-0">
      <span
        className={clsx(
          'text-[11px] px-2 py-0.5 rounded-pix font-medium',
          cls
        )}
      >
        {label}
      </span>
      {category && (
        <span className="text-[10px] text-ink2 mt-1">{category}</span>
      )}
    </div>
  );
}
