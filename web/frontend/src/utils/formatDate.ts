/** Formats `date` as "YYYY/MM/DD, h:mm:ss AM/PM", optionally in the IANA zone `timeZone`. */
export function formatDateTime(date: Date, timeZone?: string): string {
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  })
  const parts: Record<string, string> = {}
  for (const p of dtf.formatToParts(date)) parts[p.type] = p.value
  return `${parts.year}/${parts.month}/${parts.day}, ${parts.hour}:${parts.minute}:${parts.second} ${parts.dayPeriod}`
}
