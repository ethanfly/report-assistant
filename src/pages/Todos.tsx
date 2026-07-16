import { useCallback, useEffect, useMemo, useState } from 'react';
import dayjs from 'dayjs';
import {
  Check,
  CheckCircle2,
  Circle,
  Eye,
  ListTodo,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
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
import { useToast } from '../hooks/useToast';
import clsx from 'clsx';

type Filter = 'pending' | 'done' | 'all';
type ComposerMode = 'edit' | 'preview';

export default function Todos() {
  const toast = useToast();
  const [filter, setFilter] = useState<Filter>('pending');
  const [items, setItems] = useState<Todo[]>([]);
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState('');
  const [composerMode, setComposerMode] = useState<ComposerMode>('edit');
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const status = filter === 'all' ? undefined : filter;
      const list = await listTodos(status);
      setItems(list);
    } catch (e: any) {
      toast.error(`加载失败: ${e}`);
    } finally {
      setLoading(false);
    }
  }, [filter, toast]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    let un: (() => void) | undefined;
    onTodosChanged(() => {
      void refresh();
    })
      .then((u) => {
        un = u;
      })
      .catch(() => {});
    return () => {
      if (un) un();
    };
  }, [refresh]);

  const counts = useMemo(() => {
    const pending = items.filter((t) => t.status === 'pending').length;
    const done = items.filter((t) => t.status === 'done').length;
    return { pending, done, total: items.length };
  }, [items]);

  const onAdd = async () => {
    const content = draft.trim();
    if (!content) {
      toast.alert('请先输入要做的事', { kind: 'warning', title: '内容为空' });
      return;
    }
    if (adding) return;
    setAdding(true);
    try {
      await addTodo(content);
      setDraft('');
      setComposerMode('edit');
      await refresh();
      toast.success('已添加待办');
    } catch (e: any) {
      toast.error(`添加失败: ${e}`);
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
      toast.success('已完成，已写入时间线');
    } catch (e: any) {
      toast.error(`完成失败: ${e}`);
    } finally {
      setBusyId(null);
    }
  };

  const onDelete = async (id: number) => {
    if (!confirm('确认删除该待办？已写入时间线的完成记录不会被删除。')) return;
    if (busyId != null) return;
    setBusyId(id);
    try {
      const ok = await deleteTodo(id);
      if (ok) {
        if (editingId === id) {
          setEditingId(null);
          setEditDraft('');
        }
        toast.success('已删除');
        await refresh();
      } else {
        toast.error('待办不存在');
      }
    } catch (e: any) {
      toast.error(`删除失败: ${e}`);
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
    if (!content) {
      toast.alert('内容不能为空', { kind: 'warning' });
      return;
    }
    setBusyId(editingId);
    try {
      await updateTodo(editingId, content);
      setEditingId(null);
      setEditDraft('');
      await refresh();
      toast.success('已更新');
    } catch (e: any) {
      toast.error(`更新失败: ${e}`);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="p-6 space-y-5">
      <header className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink text-pix">待办</h1>
          <p className="text-sm text-ink2 mt-1">
            支持 Markdown · 完成后写入时间线 · 全局{' '}
            <kbd className="px-1.5 py-0.5 rounded-pix bg-white border border-border font-mono text-[11px]">
              Alt+Space
            </kbd>{' '}
            快速唤起
          </p>
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

      <Card hoverable={false}>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium text-ink">需要做什么？</div>
            <div className="flex items-center gap-0.5 bg-bg border border-border rounded-pix p-0.5">
              <button
                type="button"
                onClick={() => setComposerMode('edit')}
                className={clsx(
                  'px-2.5 py-1 rounded-pix text-xs flex items-center gap-1 transition-colors',
                  composerMode === 'edit'
                    ? 'bg-white text-primary-800 font-medium shadow-pix'
                    : 'text-ink2 hover:text-ink'
                )}
              >
                <Pencil size={12} /> 编辑
              </button>
              <button
                type="button"
                onClick={() => setComposerMode('preview')}
                className={clsx(
                  'px-2.5 py-1 rounded-pix text-xs flex items-center gap-1 transition-colors',
                  composerMode === 'preview'
                    ? 'bg-white text-primary-800 font-medium shadow-pix'
                    : 'text-ink2 hover:text-ink'
                )}
              >
                <Eye size={12} /> 预览
              </button>
            </div>
          </div>

          {composerMode === 'edit' ? (
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={4}
              placeholder={
                '支持 Markdown，例如：\n**完成** 登录页重构\n- 修超时\n- 补单测'
              }
              disabled={adding}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault();
                  void onAdd();
                }
              }}
              className="input-base resize-y font-mono text-sm leading-relaxed"
            />
          ) : (
            <div className="min-h-[112px] rounded-pix border border-border bg-white px-3 py-2">
              {draft.trim() ? (
                <MarkdownView content={draft} />
              ) : (
                <div className="text-sm text-ink2 py-8 text-center">预览为空</div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between">
            <p className="hint m-0">
              Ctrl/⌘ + Enter 添加 · 任务内容以 Markdown 渲染
            </p>
            <Button
              variant="primary"
              size="sm"
              icon={<Plus size={14} />}
              onClick={() => void onAdd()}
              loading={adding}
            >
              添加待办
            </Button>
          </div>
        </div>
      </Card>

      <Card hoverable={false}>
        <div className="flex items-center gap-2 flex-wrap">
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
                'px-3 py-1.5 rounded-pix text-xs border transition-colors',
                filter === t.key
                  ? 'bg-primary-50 border-primary-200 text-primary-800 font-medium'
                  : 'bg-white border-border text-ink2 hover:bg-bg'
              )}
            >
              {t.label}
            </button>
          ))}
          <span className="ml-auto text-xs text-ink2">
            {filter === 'pending' && `${counts.pending} 条未完成`}
            {filter === 'done' && `${counts.done} 条已完成`}
            {filter === 'all' && `共 ${counts.total} 条`}
          </span>
        </div>
      </Card>

      {items.length === 0 ? (
        <Card hoverable={false}>
          <div className="py-16 text-center text-sm text-ink2 flex flex-col items-center gap-2">
            <ListTodo size={28} className="text-primary-300" />
            <div>
              {filter === 'pending' ? '暂无待办，上面输入一条吧' : '暂无记录'}
            </div>
          </div>
        </Card>
      ) : (
        <Card noPadding hoverable={false}>
          <ul className="divide-y divide-border">
            {items.map((t) => {
              const done = t.status === 'done';
              const busy = busyId === t.id;
              const editing = editingId === t.id;
              return (
                <li
                  key={t.id}
                  className="px-5 py-3 flex items-start gap-3 group hover:bg-bg/60 transition-colors"
                >
                  <button
                    type="button"
                    disabled={done || busy || editing}
                    onClick={() => void onComplete(t.id)}
                    className={clsx(
                      'mt-0.5 shrink-0 w-7 h-7 rounded-pix flex items-center justify-center border transition-colors',
                      done
                        ? 'bg-primary-50 border-primary-200 text-primary-700'
                        : 'bg-white border-border text-ink2 hover:border-primary-400 hover:text-primary-700 hover:bg-primary-50'
                    )}
                    title={done ? '已完成' : '标记完成（写入时间线）'}
                  >
                    {done ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                  </button>
                  <div className="flex-1 min-w-0">
                    {editing ? (
                      <div className="space-y-2">
                        <textarea
                          value={editDraft}
                          onChange={(e) => setEditDraft(e.target.value)}
                          rows={5}
                          className="input-base resize-y font-mono text-sm leading-relaxed"
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                              e.preventDefault();
                              void saveEdit();
                            }
                            if (e.key === 'Escape') {
                              e.preventDefault();
                              cancelEdit();
                            }
                          }}
                        />
                        <div className="flex justify-end gap-2">
                          <Button variant="ghost" size="sm" onClick={cancelEdit}>
                            取消
                          </Button>
                          <Button
                            variant="primary"
                            size="sm"
                            icon={<Check size={14} />}
                            loading={busy}
                            onClick={() => void saveEdit()}
                          >
                            保存
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className={clsx(done && 'opacity-60')}>
                          <MarkdownView
                            content={t.content}
                            className={clsx(done && '[&_*]:line-through')}
                          />
                        </div>
                        <div className="text-[11px] text-ink2 mt-1 font-mono">
                          {done
                            ? `完成于 ${dayjs(t.completed_at || t.created_at).format('YYYY-MM-DD HH:mm')}`
                            : `创建于 ${dayjs(t.created_at).format('YYYY-MM-DD HH:mm')}`}
                        </div>
                      </>
                    )}
                  </div>
                  {!editing && (
                    <div className="shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {!done && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void onComplete(t.id)}
                          className="p-1.5 rounded-pix text-ink2 hover:text-primary-700 hover:bg-primary-50 transition-colors"
                          title="完成"
                        >
                          <Check size={14} />
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => startEdit(t)}
                        className="p-1.5 rounded-pix text-ink2 hover:text-primary-700 hover:bg-primary-50 transition-colors"
                        title="编辑 Markdown"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void onDelete(t.id)}
                        className="p-1.5 rounded-pix text-ink2 hover:text-red-500 hover:bg-red-50 transition-colors"
                        title="删除"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </div>
  );
}
