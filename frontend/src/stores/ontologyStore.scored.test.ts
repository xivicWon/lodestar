import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

const scored = [{
  targetIri: 'e#TB_CUST_MST', currentName: 'TB_CUST_MST', consensusLabel: '고객 마스터',
  description: '거래처 기본정보', agreement: 0.6, n: 5,
  variants: [{ label: '고객 마스터', count: 3 }, { label: '거래처 정보', count: 2 }],
}]

describe('ontologyStore scoredEnrichSample', () => {
  it('posts to scored endpoint with runs and stores result', async () => {
    const spy = vi.spyOn(client, 'apiPost').mockResolvedValue(scored as any)
    const s = useOntologyStore()
    await s.scoredEnrichSample(5)
    expect(spy).toHaveBeenCalledWith('/ai/enrich/sample/scored?runs=5', {})
    expect(s.scoredCandidates).toEqual(scored)
    expect(s.enriching).toBe(false)
  })

  it('defaults runs to 5', async () => {
    const spy = vi.spyOn(client, 'apiPost').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.scoredEnrichSample()
    expect(spy).toHaveBeenCalledWith('/ai/enrich/sample/scored?runs=5', {})
  })
})
