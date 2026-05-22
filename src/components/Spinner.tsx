import clsx from 'clsx';

/**
 * 像素风 Spinner：4 个像素方块依次发光
 */
interface SpinnerProps {
  size?: number; // 单个像素方块边长
  className?: string;
}

export default function Spinner({ size = 4, className }: SpinnerProps) {
  const dots = [0, 1, 2, 3];
  return (
    <span
      className={clsx('inline-flex items-center gap-[2px]', className)}
      role="status"
      aria-label="loading"
    >
      {dots.map((i) => (
        <span
          key={i}
          className="bg-primary"
          style={{
            width: size,
            height: size,
            animation: 'pixDot 1s infinite ease-in-out',
            animationDelay: `${i * 0.12}s`,
          }}
        />
      ))}
    </span>
  );
}
