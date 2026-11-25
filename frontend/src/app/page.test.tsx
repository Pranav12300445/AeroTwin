import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const push = vi.fn()
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
const login = vi.fn()
vi.mock('@/lib/api', () => ({ login: (...a: unknown[]) => login(...a) }))

import LoginPage from './page'

beforeEach(() => { push.mockReset(); login.mockReset(); localStorage.clear() })

describe('LoginPage', () => {
  it('renders the form and the three demo logins', () => {
    render(<LoginPage />)
    expect(screen.getByPlaceholderText('Enter username')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Enter password')).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument()
    for (const n of [/Operator/, /Engineer/, /Admin/]) expect(screen.getByRole('button', { name: n })).toBeInTheDocument()
  })

  it('logs in, stores token + role and goes to the dashboard', async () => {
    login.mockResolvedValue({ access_token: 'jwt', role: 'admin' })
    render(<LoginPage />)
    await userEvent.type(screen.getByPlaceholderText('Enter username'), 'admin')
    await userEvent.type(screen.getByPlaceholderText('Enter password'), 'admin123')
    await userEvent.click(screen.getByRole('button', { name: 'Login' }))
    expect(login).toHaveBeenCalledWith('admin', 'admin123')
    await waitFor(() => expect(push).toHaveBeenCalledWith('/dashboard'))
    expect(localStorage.getItem('token')).toBe('jwt')
    expect(localStorage.getItem('role')).toBe('admin')
  })

  it('shows an error and stays on the page when credentials are wrong', async () => {
    login.mockRejectedValue(new Error('Login failed'))
    render(<LoginPage />)
    await userEvent.type(screen.getByPlaceholderText('Enter username'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Login' }))
    expect(await screen.findByText('Invalid credentials')).toBeInTheDocument()
    expect(push).not.toHaveBeenCalled()
    expect(localStorage.getItem('token')).toBeNull()
    expect(screen.getByRole('button', { name: 'Login' })).toBeEnabled()
  })

  it('disables the button while the request is in flight', async () => {
    let resolve!: (v: unknown) => void
    login.mockReturnValue(new Promise(r => { resolve = r }))
    render(<LoginPage />)
    await userEvent.click(screen.getByRole('button', { name: 'Login' }))
    expect(screen.getByRole('button', { name: 'Logging in...' })).toBeDisabled()
    resolve({ access_token: 't', role: 'operator' })
    await waitFor(() => expect(push).toHaveBeenCalled())
  })

  it('clears an earlier error on the next attempt', async () => {
    login.mockRejectedValueOnce(new Error('x')).mockResolvedValueOnce({ access_token: 't', role: 'operator' })
    render(<LoginPage />)
    await userEvent.click(screen.getByRole('button', { name: 'Login' }))
    await screen.findByText('Invalid credentials')
    await userEvent.click(screen.getByRole('button', { name: 'Login' }))
    await waitFor(() => expect(screen.queryByText('Invalid credentials')).not.toBeInTheDocument())
  })

  it.each([
    [/Operator/, 'operator', 'operator123'],
    [/Engineer/, 'engineer', 'engineer123'],
    [/Admin/, 'admin', 'admin123'],
  ])('quick login %s uses the demo credentials', async (button, user, pass) => {
    login.mockResolvedValue({ access_token: 'jwt', role: user })
    render(<LoginPage />)
    await userEvent.click(screen.getByRole('button', { name: button }))
    expect(login).toHaveBeenCalledWith(user, pass)
    await waitFor(() => expect(push).toHaveBeenCalledWith('/dashboard'))
    expect(localStorage.getItem('role')).toBe(user)
  })

  it('quick login failure shows an error', async () => {
    login.mockRejectedValue(new Error('x'))
    render(<LoginPage />)
    await userEvent.click(screen.getByRole('button', { name: /Admin/ }))
    expect(await screen.findByText('Login failed')).toBeInTheDocument()
  })
})
