import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { listen } from '@tauri-apps/api/event';
import dayjs from 'dayjs';
import {
  Check,
  CheckCircle2,
  Circle,
  Eye,
  ListTodo,
  Pencil,
  Plus,
  Trash2,
  X,
} from 'lucide-react';
import clsx from 'clsx';
import MarkdownView from '../components/MarkdownView';
import {
  addTodo,
  completeTodo,
  deleteTodo,
  listTodos,
  onTodosChanged,
  updateTodo,
} from '../api/ipc';
import type { Todo } from '../api/types';

type ComposerMode = 'edit' | 'preview';
type Filter = 'pending' | 'done' | 'all';

/**
 * Alt+Space 一体弹窗：
 * ┌─────────────────────────────┐
 * │ 待办              Esc 关闭   │  ← 拖拽条
 * ├─────────────────────────────┤
 * │ Markdown 输入（编辑/预览）    │  ← 固定高度 composer
 * │ Ctrl+Enter 添加              │
 * ├─────────────────────────────┤
 * │ 未完成 | 已完成 | 全部        │
 * │ ○ 任务（MD 渲染）…           │  ← 可滚动列表
 * └─────────────────────────────┘
 */
export default function TodoPopup() {
  const [draft, setDraft] = useState('');
  const [composerMode, setComposerMode] = useState<ComposerMode>('edit');
  const [filter, setFilter] = useState<Filter>('pending');
  const [items, setItems] = useState<Todo[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState('');
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const focusComposer = useCallback(() => {
    setComposerMode('edit');
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      // 光标移到末尾
      const el = textareaRef.current;
      if (el) {
        const len = el.value.length;
        el.setSelectionRange(len, len);
      }
    });
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const status = filter === 'all' ? undefined : filter;
      const list = await listTodos(status);
      setItems(list);
    } catch (e) {
      console.warn(e);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    focusComposer();
    let un1: (() => void) | undefined;
    let un2: (() => void) | undefined;
    listen('todo-popup-focus', () => {
      void refresh();
      focusComposer();
    })
      .then((u) => {
        un1 = u;
      })
      .catch(() => {});
    onTodosChanged(() => {
      void refresh();
    })
      .then((u) => {
        un2 = u;
      })
      .catch(() => {});
    return () => {
      if (un1) un1();
      if (un2) un2();
    };
  }, [focusComposer, refresh]);

  const close = async () => {
    try {
      await getCurrentWindow().close();
    } catch {
      try {
        await getCurrentWindow().hide();
      } catch {
        /* ignore */
      }
    }
  };

  const onAdd = async () => {
    const content = draft.trim();
    if (!content) {
      setError('写点什么再添加');
      return;
    }
    if (adding) return;
    setAdding(true);
    setError(null);
    try {
      await addTodo(content);
      setDraft('');
      setComposerMode('edit');
      // 添加后切到未完成列表
      if (filter === 'done') setFilter('pending');
      else await refresh();
      focusComposer();
    } catch (e: any) {
      setError(typeof e === 'string' ? e : String(e?.message ?? e));
    } finally {
      setAdding(false);
    }
  };

  const onComplete = async (id: number) => {
    if (busyId != null) return;
    setBusyId(id);
    try {
      await completeTodo(id);
      await refresh();
    } catch (e) {
      console.warn(e);
    } finally {
      setBusyId(null);
    }
  };

  const onDelete = async (id: number) => {
    if (busyId != null) return;
    setBusyId(id);
    try {
      await deleteTodo(id);
      if (editingId === id) {
        setEditingId(null);
        setEditDraft('');
      }
      await refresh();
    } catch (e) {
      console.warn(e);
    } finally {
      setBusyId(null);
    }
  };

  const startEdit = (t: Todo) => {
    setEditingId(t.id);
    setEditDraft(t.content);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditDraft('');
  };

  const saveEdit = async () => {
    if (editingId == null) return;
    const content = editDraft.trim();
    if (!content) return;
    setBusyId(editingId);
    try {
      await updateTodo(editingId, content);
      setEditingId(null);
      setEditDraft('');
      await refresh();
    } catch (e) {
      console.warn(e);
    } finally {
      setBusyId(null);
    }
  };

  const pendingHint = useMemo(() => {
    if (filter === 'pending') return `${items.length} 条未完成`;
    if (filter === 'done') return `${items.length} 条已完成`;
    return `共 ${items.length} 条`;
  }, [filter, items.length]);

  // Esc 关闭（编辑中 Esc 先取消编辑）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (editingId != null) {
          e.preventDefault();
          cancelEdit();
          return;
        }
        e.preventDefault();
        void close();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [editingId]);

  return (
    <div className="h-screen w-screen bg-card border border-border flex flex-col overflow-hidden shadow-soft">
      {/* 标题栏 */}
      <div
        data-tauri-drag-region
        className="h-[34px] flex items-center justify-between px-3 border-b border-border bg-white shrink-0"
      >
        <div
          data-tauri-drag-region
          className="flex items-center gap-2 pointer-events-none"
        >
          <ListTodo size={14} className="text-primary-700" />
          <span className="text-[12px] font-semibold text-ink">待办</span>
          <span className="text-[10px] text-ink2/70 font-mono">Alt+Space</span>
        </div>
        <button
          type="button"
          onClick={() => void close()}
          className="p-1.5 rounded-pix text-ink2 hover:bg-red-50 hover:text-red-500"
          title="关闭 (Esc)"
        >
          <X size={13} />
        </button>
      </div>

      {/* Composer：Markdown 输入 */}
      <div className="px-3 pt-3 pb-2 border-b border-border shrink-0 bg-bg/30 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-[11px] text-ink2">
            支持 Markdown ·{' '}
            <kbd className="px-1 py-0.5 rounded bg-white border border-border font-mono text-[10px]">
              Ctrl+Enter
            </kbd>{' '}
            添加
          </div>
          <div className="flex items-center gap-0.5 bg-white border border-border rounded-pix p-0.5">
            <button
              type="button"
              onClick={() => setComposerMode('edit')}
              className={clsx(
                'px-2 py-0.5 rounded-pix text-[11px] flex items-center gap-1 transition-colors',
                composerMode === 'edit'
                  ? 'bg-primary-50 text-primary-800 font-medium'
                  : 'text-ink2 hover:text-ink'
              )}
            >
              <Pencil size={11} /> 编辑
            </button>
            <button
              type="button"
              onClick={() => setComposerMode('preview')}
              className={clsx(
                'px-2 py-0.5 rounded-pix text-[11px] flex items-center gap-1 transition-colors',
                composerMode === 'preview'
                  ? 'bg-primary-50 text-primary-800 font-medium'
                  : 'text-ink2 hover:text-ink'
              )}
            >
              <Eye size={11} /> 预览
            </button>
          </div>
        </div>

        {composerMode === 'edit' ? (
          <textarea
            ref={textareaRef}
            value={draft}
            disabled={adding}
            onChange={(e) => {
              setDraft(e.target.value);
              if (error) setError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                void onAdd();
              }
            }}
            rows={4}
            placeholder={
              '要做的事… 支持 Markdown\n例如：**完成** 登录页重构\n- 修超时\n- 补单测'
            }
            className="input-base resize-none font-mono text-[13px] leading-relaxed !py-2"
          />
        ) : (
          <div className="min-h-[96px] max-h-[160px] overflow-y-auto rounded-pix border border-border bg-white px-3 py-2">
            {draft.trim() ? (
              <MarkdownView content={draft} className="!text-[13px]" />
            ) : (
              <div className="text-xs text-ink2 py-6 text-center">预览为空，先写点内容</div>
            )}
          </div>
        )}

        <div className="flex items-center gap-2">
          {error && (
            <div className="text-[11px] text-red-500 truncate flex-1">{error}</div>
          )}
          <div className="flex-1" />
          <button
            type="button"
            disabled={adding || !draft.trim()}
            onClick={() => void onAdd()}
            className="btn-primary h-8 px-3 text-xs"
          >
            <Plus size={13} />
            {adding ? '添加中…' : '添加'}
          </button>
        </div>
      </div>

      {/* 过滤器 */}
      <div className="px-3 py-2 flex items-center gap-1.5 shrink-0 border-b border-border bg-white">
        {(
          [
            { key: 'pending' as const, label: '未完成' },
            { key: 'done' as const, label: '已完成' },
            { key: 'all' as const, label: '全部' },
          ] as const
        ).map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setFilter(t.key)}
            className={clsx(
              'px-2.5 py-1 rounded-pix text-[11px] border transition-colors',
              filter === t.key
                ? 'bg-primary-50 border-primary-200 text-primary-800 font-medium'
                : 'bg-white border-border text-ink2 hover:bg-bg'
            )}
          >
            {t.label}
          </button>
        ))}
        <span className="ml-auto text-[10px] text-ink2">
          {loading ? '加载中…' : pendingHint}
        </span>
      </div>

      {/* 列表 */}
      <ul className="flex-1 overflow-y-auto divide-y divide-border">
        {items.length === 0 ? (
          <li className="py-14 text-center text-xs text-ink2 flex flex-col items-center gap-2">
            <CheckCircle2 size={22} className="text-primary-300" />
            <div>
              {filter === 'pending'
                ? '暂无待办，在上方写一条吧'
                : '暂无记录'}
            </div>
          </li>
        ) : (
          items.map((t) => {
            const done = t.status === 'done';
            const busy = busyId === t.id;
            const editing = editingId === t.id;
            return (
              <li
                key={t.id}
                className="px-3 py-2.5 flex items-start gap-2.5 hover:bg-bg/70 group"
              >
                <button
                  type="button"
                  disabled={done || busy || editing}
                  onClick={() => void onComplete(t.id)}
                  className={clsx(
                    'mt-0.5 shrink-0 w-6 h-6 rounded-pix flex items-center justify-center border transition-colors',
                    done
                      ? 'bg-primary-50 border-primary-200 text-primary-700'
                      : 'bg-white border-border text-ink2 hover:border-primary-400 hover:text-primary-700 hover:bg-primary-50'
                  )}
                  title={done ? '已完成' : '完成并写入时间线'}
                >
                  {done ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                </button>

                <div className="flex-1 min-w-0">
                  {editing ? (
                    <div className="space-y-2">
                      <textarea
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                        rows={4}
                        className="input-base resize-y font-mono text-[12px] leading-relaxed !py-1.5"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                            e.preventDefault();
                            void saveEdit();
                          }
                        }}
                      />
                      <div className="flex items-center gap-1.5 justify-end">
                        <button
                          type="button"
                          onClick={cancelEdit}
                          className="btn-ghost h-7 px-2 text-[11px]"
                        >
                          取消
                        </button>
                        <button
                          type="button"
                          disabled={busy || !editDraft.trim()}
                          onClick={() => void saveEdit()}
                          className="btn-primary h-7 px-2 text-[11px]"
                        >
                          <Check size={12} /> 保存
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div
                        className={clsx(
                          'text-[13px] break-words',
                          done && 'opacity-60'
                        )}
                      >
                        <MarkdownView
                          content={t.content}
                          className={clsx(
                            '!text-[13px] leading-snug',
                            done && '[&_*]:line-through'
                          )}
                        />
                      </div>
                      <div className="text-[10px] text-ink2 mt-1 font-mono">
                        {done
                          ? `完成 ${dayjs(t.completed_at || t.created_at).format('MM-DD HH:mm')}`
                          : `创建 ${dayjs(t.created_at).format('MM-DD HH:mm')}`}
                      </div>
                    </>
                  )}
                </div>

                {!editing && (
                  <div className="shrink-0 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => startEdit(t)}
                      className="p-1 rounded-pix text-ink2 hover:text-primary-700 hover:bg-primary-50"
                      title="编辑 Markdown"
                    >
                      <Pencil size={12} />
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void onDelete(t.id)}
                      className="p-1 rounded-pix text-ink2 hover:text-red-500 hover:bg-red-50"
                      title="删除"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                )}
              </li>
            );
          })
        )}
      </ul>

      <div className="px-3 py-1.5 border-t border-border text-[10px] text-ink2 bg-bg/40 shrink-0">
        勾选完成 → 写入时间线 → 生成报表时优先采用 · Esc 关闭
      </div>
    </div>
  );
}
