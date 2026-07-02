import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ImportPanel from './ImportPanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ImportPanel', () => {
  it('imports ddl on button click', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'importDdl').mockResolvedValue()
    const w = mount(ImportPanel)
    await w.find('textarea.ddl-input').setValue('CREATE TABLE t (id INT);')
    await w.find('.import-ddl-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('CREATE TABLE t (id INT);', undefined)
  })

  it('injects sample legacy on button click', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'importSample').mockResolvedValue()
    const w = mount(ImportPanel)
    await w.find('.import-sample-btn').trigger('click')
    expect(spy).toHaveBeenCalled()
  })

  it('switches to connection tab and imports connection', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'importConnection').mockResolvedValue()
    const w = mount(ImportPanel)
    await w.find('.tab-connection').trigger('click')
    await w.find('.host-input').setValue('localhost')
    await w.find('.db-input').setValue('shop')
    await w.find('.import-conn-btn').trigger('click')
    expect(spy).toHaveBeenCalled()
  })

  it('imports with selected mysql vendor', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'importConnection').mockResolvedValue()
    const w = mount(ImportPanel)
    await w.find('.tab-connection').trigger('click')
    await w.find('.vendor-select').setValue('mysql')
    await w.find('.host-input').setValue('192.168.0.1')
    await w.find('.db-input').setValue('app')
    await w.find('.import-conn-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ vendor: 'mysql', port: 3306 }))
  })
})
