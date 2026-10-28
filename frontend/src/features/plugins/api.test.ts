import { expect, it } from 'vitest'
import { formConfig, InputError, parseObject } from './api'

it('bounds JSON input by UTF8 bytes, including non-ASCII text', () => {
  const within = JSON.stringify({ text: 'ą'.repeat(30000) })
  const oversized = JSON.stringify({ text: 'ą'.repeat(33000) })
  expect(within.length).toBeLessThan(65536)
  expect(oversized.length).toBeLessThan(65536)
  expect(parseObject(within, 'Argumenty')).toEqual({ text: 'ą'.repeat(30000) })
  expect(() => parseObject(oversized, 'Argumenty')).toThrow(InputError)
})

it('rejects a secret value or embedded endpoint credentials before a configuration request', () => {
  expect(() => formConfig('https://example.test', 'synthetic-raw-value', 'status', '{}', 'mcp')).toThrow(InputError)
  expect(() => formConfig('https://user:password@example.test', '', 'status', '{}', 'mcp')).toThrow(InputError)
  expect(() => formConfig('https://example.test?key=synthetic', '', 'status', '{}', 'mcp')).toThrow(InputError)
  expect(formConfig('https://example.test/mcp', 'JARVIS_PLUGIN_SECRET_LOCAL', 'status', '{}', 'mcp')).toEqual({
    endpoint: 'https://example.test/mcp', secret_env: 'JARVIS_PLUGIN_SECRET_LOCAL', reviewed_read_tools: ['status'], openapi: null,
  })
})
