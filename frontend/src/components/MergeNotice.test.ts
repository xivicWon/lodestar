import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import MergeNotice from './MergeNotice.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('MergeNotice', () => {
  it('is hidden before any import', () => {
    useOntologyStore()
    expect(mount(MergeNotice).text()).toBe('')
  })

  it('is hidden when merge has no reapplied and no stale', () => {
    const s = useOntologyStore()
    s.lastMerge = { reapplied: 0, stale: 0, staleIris: [] }
    expect(mount(MergeNotice).text()).toBe('')
  })

  it('shows reapplied and stale counts', () => {
    const s = useOntologyStore()
    s.lastMerge = { reapplied: 3, stale: 2, staleIris: ['e#X', 'e#Y'] }
    const t = mount(MergeNotice).text()
    expect(t).toContain('확정 3건 복원')
    expect(t).toContain('미매칭 2건')
  })

  it('shows when only stale is present', () => {
    const s = useOntologyStore()
    s.lastMerge = { reapplied: 0, stale: 1, staleIris: ['e#X'] }
    expect(mount(MergeNotice).text()).toContain('미매칭 1건')
  })
})
