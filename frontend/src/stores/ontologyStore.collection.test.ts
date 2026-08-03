import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'
import type { CollectionReport } from '../api/types'

const report: CollectionReport = {
  sourceKind: 'ddl',
  locatorScheme: 'line',
  collected: 27,
  skipped: 8,
  failed: 1,
  partial: 1,
  complete: false,
  issues: [
    { kind: 'SKIPPED', reasonCode: 'OUT_OF_SCOPE_BY_DESIGN', reason: '행 데이터는 범위 밖', locator: '#L2', target: 'INSERT INTO customers' },
    { kind: 'FAILED', reasonCode: 'PARSE_ERROR', reason: '쉼표 누락', locator: '#L3', target: 'CREATE TABLE broken' },
  ],
  partials: [
    { kind: 'PARTIAL', reasonCode: 'PARTIAL_COLLECTION', reason: '부분 성공', locator: '#L1', target: '(ddl-text)' },
  ],
}

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

/** #129 — 세 입력 경로 모두 응답의 수집 보고를 스토어에 붙잡아야 한다. 한 경로라도 놓치면 그 경로는 조용해진다. */
describe('ontologyStore collection report', () => {
  for (const [name, call] of [
    ['importDdl', (s: ReturnType<typeof useOntologyStore>) => s.importDdl('CREATE TABLE t (id INT);', 'shop')],
    ['importSample', (s: ReturnType<typeof useOntologyStore>) => s.importSample()],
    ['importConnection', (s: ReturnType<typeof useOntologyStore>) =>
      s.importConnection({ host: 'h', port: 5432, database: 'd', user: 'u', password: 'p', vendor: 'postgresql' })],
  ] as const) {
    it(`${name} captures the collection report`, async () => {
      vi.spyOn(client, 'apiPost').mockResolvedValue({ meta: {}, merge: { reapplied: 0, stale: 0, staleIris: [] }, collection: report } as any)
      vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
      const s = useOntologyStore()
      await call(s)
      expect(s.lastCollection).toEqual(report)
    })
  }

  it('leaves lastCollection null before any import', () => {
    expect(useOntologyStore().lastCollection).toBeNull()
  })

  /**
   * 실패한 임포트 옆에 직전 실행의 보고가 남으면, 사용자는 그것을 이번 결과로 읽는다 —
   * 조용한 skip 을 없애려다 **틀린 보고**를 만드는 자리다.
   */
  it('clears the previous report when a later import fails', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({ meta: {}, merge: { reapplied: 0, stale: 0, staleIris: [] }, collection: report } as any)
    const s = useOntologyStore()
    await s.importDdl('CREATE TABLE t (id INT);')
    expect(s.lastCollection).toEqual(report)

    post.mockRejectedValue(new Error('연결 실패'))
    await s.importSample()
    expect(s.lastCollection).toBeNull()
    expect(s.error).toBe('연결 실패')
  })
})
