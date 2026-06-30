import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'
import type { ClassDto } from '../api/types'

const animal: ClassDto = { iri: 'e#Animal', label: 'Animal', superClasses: [], annotations: [] }

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

describe('ontologyStore', () => {
  it('refresh loads classes and meta', async () => {
    vi.spyOn(client, 'apiGet').mockImplementation(async (p: string) =>
      p === '/classes' ? [animal] : { counts: { classes: 1 } } as any)
    const s = useOntologyStore()
    await s.refresh()
    expect(s.classes).toEqual([animal])
    expect(s.tree.map(n => n.iri)).toEqual(['e#Animal'])
  })

  it('select sets selected getter', async () => {
    vi.spyOn(client, 'apiGet').mockImplementation(async (p: string) =>
      p === '/classes' ? [animal] : {} as any)
    const s = useOntologyStore()
    await s.refresh()
    s.select('e#Animal')
    expect(s.selected?.label).toBe('Animal')
  })

  it('createClass posts and refreshes', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue(animal as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([animal] as any)
    const s = useOntologyStore()
    await s.createClass('Animal')
    expect(post).toHaveBeenCalledWith('/classes', { label: 'Animal', superClass: undefined })
    expect(s.classes).toEqual([animal])
  })

  it('deleteClass surfaces ApiError message', async () => {
    vi.spyOn(client, 'apiDelete').mockRejectedValue(new client.ApiError('in_use', '사용 중', 'e#Animal'))
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.deleteClass('e#Animal')
    expect(s.error).toBe('사용 중')
  })
})
