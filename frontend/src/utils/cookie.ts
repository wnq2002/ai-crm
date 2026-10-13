// 读取同源 Cookie。身份会话 Cookie 为 HttpOnly，此处仅用于读取可读 Cookie（如 CSRF token）。
export function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const prefix = `${name}=`
  for (const part of document.cookie.split(';')) {
    const trimmed = part.trim()
    if (trimmed.startsWith(prefix)) {
      const value = trimmed.slice(prefix.length)
      try {
        return decodeURIComponent(value)
      } catch {
        return value
      }
    }
  }
  return null
}
