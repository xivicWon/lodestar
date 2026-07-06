import { describe, it, expect } from 'vitest'
import { shortName } from './shortName'

describe('shortName', () => {
  it('takes the fragment after # then the last path segment', () => {
    expect(shortName('http://x/rdb/shop#orders')).toBe('orders')
    expect(shortName('http://x/orders')).toBe('orders')
  })

  it('returns the whole string when there is no separator', () => {
    expect(shortName('orders')).toBe('orders')
  })
})
