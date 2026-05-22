import clsx from 'clsx';

/**
 * 像素风头像组件
 * - 默认 32×32，启用 image-rendering: pixelated
 * - 不再有边框/底色，避免视觉上像被框住
 */
interface AvatarProps {
  src?: string;
  size?: number;
  className?: string;
}

export default function Avatar({
  src = '/avatar.png',
  size = 32,
  className,
}: AvatarProps) {
  return (
    <img
      src={src}
      alt="avatar"
      width={size}
      height={size}
      draggable={false}
      style={{ width: size, height: size }}
      className={clsx('pixelated shrink-0 object-cover', className)}
    />
  );
}
