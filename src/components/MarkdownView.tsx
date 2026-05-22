import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import clsx from 'clsx';

interface Props {
  content: string;
  className?: string;
}

export default function MarkdownView({ content, className }: Props) {
  return (
    <div className={clsx('markdown-body', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
