import { useState } from "react";

// Картинка карточки. Нет image_url или картинка не загрузилась — блок картинки не показываем вовсе.
export default function CardImage({ src, alt }) {
  const [broken, setBroken] = useState(false);
  if (!src || broken) return null;
  return <img src={src} onError={() => setBroken(true)} alt={alt} className="h-36 w-full object-cover" />;
}