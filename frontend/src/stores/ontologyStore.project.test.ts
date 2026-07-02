import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

describe('ontologyStore projects', () => {
  it('listProjects loads names from /projects', async () => {
    const spy = vi.spyOn(client, 'apiGet').mockResolvedValue(['a', 'b'] as any)
    const s = useOntologyStore()
    await s.listProjects()
    expect(spy).toHaveBeenCalledWith('/projects')
    expect(s.projects).toEqual(['a', 'b'])
  })

  it('saveProject posts name and stores returned names', async () => {
    const spy = vi.spyOn(client, 'apiPost').mockResolvedValue(['t'] as any)
    const s = useOntologyStore()
    await s.saveProject('t')
    expect(spy).toHaveBeenCalledWith('/projects/save?name=' + encodeURIComponent('t'), {})
    expect(s.projects).toEqual(['t'])
  })

  it('loadProject posts name then refreshes and clears selection', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    const get = vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    s.select('e#X')
    await s.loadProject('t')
    expect(post).toHaveBeenCalledWith('/projects/load?name=' + encodeURIComponent('t'), {})
    // refresh reloads classes; selection cleared afterwards
    expect(get).toHaveBeenCalledWith('/classes')
    expect(s.selectedIri).toBeNull()
  })
})
