import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders Financial Planning heading', () => {
    render(<App />)
    const heading = screen.getByRole('heading', { name: /financial planning/i })
    expect(heading).toBeInTheDocument()
  })

  it('renders description text', () => {
    render(<App />)
    const description = screen.getByText(/local-first investment planner/i)
    expect(description).toBeInTheDocument()
  })
})
