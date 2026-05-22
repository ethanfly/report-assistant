import { NavLink } from 'react-router-dom';
import {
  Home as HomeIcon,
  Clock,
  FileText,
  Settings as SettingsIcon,
} from 'lucide-react';
import { useWatchStatus } from '../hooks/useWatchStatus';
import Avatar from './Avatar';
import clsx from 'clsx';

const items = [
  { to: '/home', label: '首页', icon: HomeIcon },
  { to: '/timeline', label: '时间线', icon: Clock },
  { to: '/reports', label: '报告', icon: FileText },
  { to: '/settings', label: '设置', icon: SettingsIcon },
];

/**
 * 浅色像素风侧边栏
 * - 220px 宽，白底，右边 1px 边框
 * - 选中态：左侧 3px primary 竖条 + 浅绿背景
 */
export default function Sidebar() {
  const { status } = useWatchStatus();

  return (
    <aside className="flex flex-col w-[220px] shrink-0 bg-white border-r border-border">
      {/* 顶部 logo + 标题 */}
      <div className="px-4 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <Avatar src="/avatar.png" size={32} bordered />
          <div className="leading-tight min-w-0">
            <div className="text-[14px] font-semibold text-ink text-pix truncate">
              小T日报助手
            </div>
            <div className="text-[10px] text-ink2 mt-0.5 truncate">
              Report Assistant
            </div>
          </div>
        </div>
      </div>

      {/* 菜单 */}
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {items.map((it) => {
          const Icon = it.icon;
          return (
            <NavLink
              key={it.to}
              to={it.to}
              className={({ isActive }) =>
                clsx(
                  'group relative flex items-center gap-3 pl-4 pr-3 py-2 rounded-pix text-sm transition-all duration-150',
                  isActive
                    ? 'bg-primary-50 text-ink font-medium'
                    : 'text-ink2 hover:bg-bg hover:text-ink'
                )
              }
            >
              {({ isActive }) => (
                <>
                  {/* 选中竖条 */}
                  <span
                    className={clsx(
                      'absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r transition-all',
                      isActive ? 'bg-primary' : 'bg-transparent'
                    )}
                  />
                  <Icon
                    size={16}
                    className={clsx(
                      'transition-colors',
                      isActive ? 'text-primary-700' : 'text-ink2'
                    )}
                  />
                  <span>{it.label}</span>
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* 底部状态 */}
      <div className="px-4 py-3 border-t border-border bg-bg/50">
        <div className="flex items-center gap-2 text-xs">
          <span
            className={clsx(
              'inline-block w-2 h-2 rounded-full',
              status.running ? 'bg-primary animate-pulse' : 'bg-ink2/30'
            )}
          />
          <span className={status.running ? 'text-ink' : 'text-ink2'}>
            {status.running ? '监听中' : '已停止'}
          </span>
          {status.running && status.intervalSeconds ? (
            <span className="text-ink2/70">· {status.intervalSeconds}s</span>
          ) : null}
        </div>
        {status.lastError ? (
          <div className="mt-2 text-[11px] text-red-500/90 line-clamp-2">
            {status.lastError}
          </div>
        ) : null}
      </div>
    </aside>
  );
}
