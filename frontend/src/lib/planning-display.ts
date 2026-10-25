// Pure display validation shared by API/cache-backed proposal cards and tests.
export type PlaceCheck = { index: number; status: 'reference_matched' | 'area_reference' | 'unverified'; name: string; city: string | null; area: string | null; source_url: string | null; reviewed_on: string | null }
export type PlanningQuality = { version: number; trip_days: number; travelers: number; cost_basis: string; currency_conversion: string; arrival_departure_times: string; by_category: Record<string, string>; places: PlaceCheck[]; warnings: string[]; daily_window: string; buffer_policy: string; exclusions: string }
const referenceHosts = new Set(['www.gotokyo.org', 'kyoto.travel', 'www.mlit.go.jp', 'www.tsukiji.or.jp', 'shibuya-yokocho.com', 'www.tokyoeki-1bangai.co.jp', 'fng.or.jp', 'www.mugitoro.co.jp', 'www.asakusaimahan.co.jp', 'afuri.com', 'mai-sen.com', 'www.ginzalion.jp', 'www.tokyo-solamachi.jp', 'guide.michelin.com'])
export function safeReferenceUrl(value: unknown): string | null {
  if (typeof value !== 'string' || value.length > 500) return null
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password && referenceHosts.has(url.hostname) ? url.href : null } catch { return null }
}
export function inclusiveDays(first: string, last: string): number | null {
  const day = (value: string) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN
    const parsed = Date.parse(`${value}T00:00:00Z`)
    return Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0, 10) === value ? parsed : NaN
  }
  const count = (day(last) - day(first)) / 86400000 + 1
  return Number.isInteger(count) && count > 0 ? count : null
}
function cents(value: string): number {
  if (!/^-?\d{1,12}(?:\.\d{1,2})?$/.test(value)) throw new Error('Invalid planning amount')
  const negative = value.startsWith('-')
  const [whole, fraction = ''] = value.replace('-', '').split('.')
  return (Number(whole) * 100 + Number(fraction.padEnd(2, '0'))) * (negative ? -1 : 1)
}
export function subtractMoney(total: string, additions: string): string { return ((cents(total) - cents(additions)) / 100).toFixed(2) }
export function perPersonAllowance(total: string, travelers: number): string {
  if (!Number.isInteger(travelers) || travelers < 1 || travelers > 50) throw new Error('Invalid traveler count')
  return (Math.round(cents(total) / travelers) / 100).toFixed(2)
}
export function safePlanningQuality(value: unknown): PlanningQuality | null {
  if (!value || typeof value !== 'object') return null
  const data = value as Partial<PlanningQuality>
  const short = (s: unknown, limit = 500): s is string => typeof s === 'string' && s.length <= limit
  if (data.version !== 1 || !Number.isInteger(data.trip_days) || Number(data.trip_days) < 1 || Number(data.trip_days) > 366
    || !Number.isInteger(data.travelers) || Number(data.travelers) < 1 || Number(data.travelers) > 50
    || !short(data.cost_basis) || !short(data.currency_conversion) || !short(data.arrival_departure_times)
    || !short(data.daily_window) || !short(data.buffer_policy) || !short(data.exclusions)
    || !Array.isArray(data.warnings) || data.warnings.length > 20 || !data.warnings.every(w => short(w))
    || !Array.isArray(data.places) || data.places.length > 120 || !data.places.every(p => p && typeof p === 'object'
      && Number.isInteger(p.index) && p.index >= 0 && p.index < 120 && ['reference_matched', 'area_reference', 'unverified'].includes(p.status)
      && short(p.name, 160) && (p.city === null || short(p.city, 120)) && (p.area === null || short(p.area, 120))
      && (p.source_url === null || safeReferenceUrl(p.source_url)) && (p.reviewed_on === null || short(p.reviewed_on, 10)))) return null
  if (!data.by_category || typeof data.by_category !== 'object' || Object.keys(data.by_category).length !== 5) return null
  for (const key of ['activity', 'food', 'transport', 'accommodation', 'other']) {
    const amount = data.by_category[key]
    if (!short(amount, 20) || !/^\d+(?:\.\d{1,2})?$/.test(amount)) return null
  }
  return data as PlanningQuality
}
