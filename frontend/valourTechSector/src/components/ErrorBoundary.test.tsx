import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'

function BrokenPage(): null {
  throw new Error('Unexpected render failure')
}

it('offers a recovery screen instead of a blank page when rendering fails', () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  render(<ErrorBoundary><BrokenPage /></ErrorBoundary>)
  expect(screen.getByRole('alert')).toHaveTextContent('This page couldn’t load.')
  expect(screen.getByRole('button', { name: 'Reload the page' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Return to the home page' })).toHaveAttribute('href', '/')
})
