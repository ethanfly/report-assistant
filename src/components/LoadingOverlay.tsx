import { useEffect, useState } from 'react';
import { Sparkles } from 'lucide-react';

/**
 * 全屏阻塞 loading：
 * - 半透明遮罩，禁止背后交互
 * - 大号像素风 spinner（与 Spinner 组件共用 pixDot keyframes）
 * - 自动从 open 切到 true 时开始计时，关闭时停止；显示秒数 + 毫秒
 * - 标题/描述可外部传入；不传则显示通用文案
 *
 * 设计要点：计时不用 Date.now() 直接 setState，改成 100ms tick，
 * 既保证视觉精度（一位小数）又不浪费 render。
 */
interface Props {
  open: boolean;
  title?: string;
  description?: string;
}

export default function LoadingOverlay({ open, title, description }: Props) {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (!open) {
      setElapsedMs(0);
      return;
    }
    const start = performance.now();
    const id = window.setInterval(() => {
      setElapsedMs(performance.now() - start);
    }, 100);
    return () => window.clearInterval(id);
  }, [open]);

  if (!open) return null;

  const seconds = Math.floor(elapsedMs / 1000);
  const tenth = Math.floor((elapsedMs % 1000) / 100);

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-busy="true"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-[1px]"
    >
      <div className="flex flex-col items-center gap-5 px-8 py-7 rounded-lg bg-card border border-border shadow-xl min-w-[260px]">
        {/* 大像素风 spinner：5 个方块依次发光 */}
        <div className="flex items-center gap-1" aria-hidden="true">
          {[0, 1, 2, 3, 4].map((i) => (
            <span
              key={i}
              className="bg-primary block"
              style={{
                width: 10,
                height: 10,
                animation: 'pixDot 1s infinite ease-in-out',
                animationDelay: `${i * 0.12}s`,
              }}
            />
          ))}
        </div>

        <div className="flex items-center gap-2 text-ink">
          <Sparkles size={16} className="text-primary" />
          <span className="text-sm font-medium">
            {title ?? '正在生成报告...'}
          </span>
        </div>

        {/* 已用时长 */}
        <div className="font-mono text-2xl tabular-nums text-ink">
          {seconds}.{tenth}s
        </div>

        <div className="text-xs text-ink2 text-center max-w-[220px]">
          {description ?? '请稍候，模型正在汇总你的工作内容。耗时取决于模型与提交/截图数量。'}
        </div>
      </div>
    </div>
  );
}
