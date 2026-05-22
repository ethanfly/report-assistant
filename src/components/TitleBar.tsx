import { useEffect, useState } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { Minus, Square, X } from 'lucide-react';

/**
 * 自定义标题栏：30px 高，无原生装饰窗口下使用。
 * - 左侧：像素头像 + 标题（drag region）
 * - 中部：drag region 占位
 * - 右侧：最小化 / 最大化 / 关闭（hide）
 */
export default function TitleBar() {
  const [maximized, setMaximized] = useState(false);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    const win = getCurrentWindow();
    void win.isMaximized().then(setMaximized).catch(() => {});
    win
      .onResized(async () => {
        try {
          setMaximized(await win.isMaximized());
        } catch {
          /* ignore */
        }
      })
      .then((u) => {
        unlisten = u;
      })
      .catch(() => {});
    return () => {
      if (unlisten) unlisten();
    };
  }, []);

  const onMin = async () => {
    try {
      await getCurrentWindow().minimize();
    } catch (e) {
      console.warn('minimize failed', e);
    }
  };

  const onMax = async () => {
    try {
      await getCurrentWindow().toggleMaximize();
    } catch (e) {
      console.warn('toggleMaximize failed', e);
    }
  };

  const onClose = async () => {
    try {
      // 走 close → main.rs 中已配置 prevent_close + hide → 实际隐藏到托盘
      await getCurrentWindow().close();
    } catch (e) {
      // 兜底
      try {
        await getCurrentWindow().hide();
      } catch {
        /* ignore */
      }
    }
  };

  return (
    <div
      data-tauri-drag-region
      className="h-[30px] flex items-center justify-between bg-white border-b border-border select-none shrink-0"
    >
      <div
        data-tauri-drag-region
        className="flex items-center gap-2 px-3 h-full pointer-events-none"
      >
        <img
          src="/avatar.png"
          alt=""
          className="w-4 h-4 pixelated"
          draggable={false}
        />
        <span className="text-[12px] font-semibold text-ink text-pix">
          小T日报助手
        </span>
      </div>

      {/* 中部 drag 占位 */}
      <div data-tauri-drag-region className="flex-1 h-full" />

      <div className="flex h-full">
        <button
          onClick={() => void onMin()}
          className="w-11 h-full flex items-center justify-center text-ink2 hover:bg-bg hover:text-ink transition-colors"
          title="最小化"
        >
          <Minus size={14} />
        </button>
        <button
          onClick={() => void onMax()}
          className="w-11 h-full flex items-center justify-center text-ink2 hover:bg-bg hover:text-ink transition-colors"
          title={maximized ? '还原' : '最大化'}
        >
          <Square size={11} />
        </button>
        <button
          onClick={() => void onClose()}
          className="w-11 h-full flex items-center justify-center text-ink2 hover:bg-red-500 hover:text-white transition-colors"
          title="关闭（隐藏到托盘）"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
