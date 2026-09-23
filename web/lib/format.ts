export function crc(value: number | null | undefined): string {
  if (value == null) return "Precio ?";
  return "₡" + Math.round(value).toLocaleString("es-CR");
}

export function whatsappLink(phone: string | null, url: string): string | null {
  if (!phone) return null;
  const text = `Hola, vi su anuncio del apartamento (${url}). ¿Sigue disponible? ¿Incluye parqueo?`;
  return `https://wa.me/506${phone}?text=${encodeURIComponent(text)}`;
}

export function ago(iso: string): string {
  const hours = (Date.now() - new Date(iso).getTime()) / 3_600_000;
  if (hours < 1) return "hace minutos";
  if (hours < 24) return `hace ${Math.floor(hours)} h`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "hace 1 día" : `hace ${days} días`;
}
