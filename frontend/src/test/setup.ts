import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// jsdom has no scrollIntoView. Mimic current Chrome, where it returns a Promise: an effect
// written as useEffect(() => el.scrollIntoView()) then returns that Promise, which React
// treats as a cleanup function and crashes on. This keeps tests honest about it.
Element.prototype.scrollIntoView = vi.fn(() => Promise.resolve()) as unknown as Element['scrollIntoView']

afterEach(() => {
  cleanup()
  document.body.innerHTML = ''
  localStorage.clear()
})
