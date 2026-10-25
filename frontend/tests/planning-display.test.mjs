import { test } from 'node:test'
import assert from 'node:assert/strict'
import { inclusiveDays, subtractMoney, perPersonAllowance, safeReferenceUrl, safePlanningQuality } from '../src/lib/planning-display.ts'

test('calendar dates are inclusive, timezone-independent, and reject invalid dates', () => {
  assert.equal(inclusiveDays('2027-05-01', '2027-05-06'), 6)
  assert.equal(inclusiveDays('2028-02-28', '2028-03-01'), 3)
  assert.equal(inclusiveDays('2027-02-29', '2027-03-01'), null)
  assert.equal(inclusiveDays('2027-05-06', '2027-05-01'), null)
})
test('budget display subtracts cents and labels rounded per-person allowances', () => {
  assert.equal(subtractMoney('0.30', '0.20'), '0.10')
  assert.equal(subtractMoney('3000.00', '120.25'), '2879.75')
  assert.equal(perPersonAllowance('40.25', 2), '20.13')
  assert.throws(() => perPersonAllowance('10', 0))
  assert.throws(() => subtractMoney('NaN', '1'))
})
test('reference links cannot navigate to script, credentials, spoofed hosts, or arbitrary sites', () => {
  for (const url of ['javascript:alert(1)', 'https://www.gotokyo.org.evil.test/', 'https://user:password@www.gotokyo.org/', 'http://www.gotokyo.org/', 'https://evil.test/']) assert.equal(safeReferenceUrl(url), null)
  assert.equal(safeReferenceUrl('https://www.gotokyo.org/en/spot/63/index.html'), 'https://www.gotokyo.org/en/spot/63/index.html')
})
test('corrupt proposal quality from browser storage is ignored safely', () => {
  for (const value of [null, [], 'wrong', { version: 1, places: 'not-an-array' }, { version: 99 }]) assert.equal(safePlanningQuality(value), null)
})
