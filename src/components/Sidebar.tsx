import { NavLink } from 'react-router-dom';
import { Home, Clock, FileText, Settings as SettingsIcon } from 'lucide-react';
import { useWatchStatus } from '../hooks/useWatchStatus';
import clsx from 'clsx';

const items = [
  { to: '/home', label: '首页', icon: Home },
  { to: '/timeline', label: '时间线', icon: Clock },
  { to: '/reports', label: '报告', icon: FileText },
  { to: '/settings', label: '设置', icon: SettingsIcon },
];

export default function Sidebar() {
  const { status } = useWatchStatus();

  return (
    <aside className="flex flex-col w-[220px] shrink-0 bg-ink text-white">
      <div className="px-5 py-5 border-b border-white/5">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-primary-700 flex items-center justify-center font-bold">
            T
          </div>
          <div className="leading-tight">
            <div className="text-[15px] font-semibold">小T日报助手</div>
            <div className="text-[11px] text-white/50">Report Assistant</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-1">
        {items.map((it) => {
          const Icon = it.icon;
          return (
            <NavLink
              key={it.to}
              to={it.to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition',
                  isActive
                    ? 'bg-primary text-white shadow-sm'
                    : 'text-white/70 hover:bg-white/5 hover:text-white'
                )
              }
            >
              <Icon size={16} />
              <span>{it.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="px-4 py-4 border-t border-white/5">
        <div className="flex items-center gap-2 text-xs">
          <span
            className={clsx(
              'inline-block w-2 h-2 rounded-full',
              status.running ? 'bg-emerald-400 animate-pulse' : 'bg-white/30'
            )}
          />
          <span className="text-white/80">
            {status.running ? '监听中' : '已停止'}
          </span>
          {status.running && status.intervalSeconds ? (
            <span className="text-white/40">
              · {status.intervalSeconds}s
            </span>
          ) : null}
        </div>
        {status.lastError ? (
          <div className="mt-2 text-[11px] text-red-300/90 line-clamp-2">
            {status.lastError}
          </div>
        ) : null}
      </div>
    </aside>
  );
}
