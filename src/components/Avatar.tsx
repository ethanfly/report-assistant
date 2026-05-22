import clsx from 'clsx';

/**
 * 像素风头像组件
 * - 默认 32×32，启用 image-rendering: pixelated
 * - 1px 边框模拟像素描边
 */
interface AvatarProps {
  src?: string;
  size?: number;
  className?: string;
  bordered?: boolean;
}

export default function Avatar({
  src = '/avatar.png',
  size = 32,
  className,
  bordered = true,
}: AvatarProps) {
  return (
    <img
      src={src}
      alt="avatar"
      width={size}
      height={size}
      draggable={false}
      style={{ width: size, height: size }}
      className={clsx(
        'pixelated shrink-0 object-cover',
        bordered && 'border border-border rounded-pix bg-white',
        className
      )}
    />
  );
}
