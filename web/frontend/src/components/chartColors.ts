// Fixed 8-hue categorical order, matching the bot's Plotly renderers so both interfaces read
// consistently for anyone who uses both -- see dml_bot/bot_reply/ram_chart_plotly.py.
export const CATEGORICAL_COLORS = ['#2a78d6', '#1baf7a', '#eda100', '#008300', '#4a3aa7', '#e34948', '#e87ba4']
export const OTHER_COLOR = '#898781'
export const MAX_NAMED_USERS = CATEGORICAL_COLORS.length

export function rankUsers(totals: Record<string, number>): string[] {
  return Object.entries(totals)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([name]) => name)
}

export function colorMap(rankedUsers: string[]): Record<string, string> {
  const map: Record<string, string> = {}
  rankedUsers.slice(0, MAX_NAMED_USERS).forEach((name, i) => {
    map[name] = CATEGORICAL_COLORS[i]
  })
  return map
}

export function displayUnit(capMb: number): { label: string; divisor: number } {
  return capMb >= 1024 ? { label: 'GB', divisor: 1024 } : { label: 'MB', divisor: 1 }
}
