'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { login } from '@/lib/api'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await login(username, password)
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('role', data.role)
      router.push('/dashboard')
    } catch {
      setError('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  const quickLogin = async (user: string, pass: string) => {
    setUsername(user)
    setPassword(pass)
    setLoading(true)
    try {
      const data = await login(user, pass)
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('role', data.role)
      router.push('/dashboard')
    } catch {
      setError('Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-aero-dark">
      <div className="w-full max-w-md p-8">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            ✈️ Aero<span className="text-aero-accent">Twin</span>
          </h1>
          <p className="text-gray-400 text-sm">UAV Engine Digital-Twin Health Monitor</p>
          <p className="text-gray-500 text-xs mt-1">SIH 2026 — SIH26054</p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleLogin} className="bg-aero-panel border border-aero-border rounded-xl p-6 space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-aero-dark border border-aero-border rounded-lg px-4 py-2.5 text-white focus:border-aero-accent focus:outline-none"
              placeholder="Enter username"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-aero-dark border border-aero-border rounded-lg px-4 py-2.5 text-white focus:border-aero-accent focus:outline-none"
              placeholder="Enter password"
            />
          </div>
          {error && <p className="text-aero-red text-sm">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-aero-accent hover:bg-blue-600 text-white font-medium py-2.5 rounded-lg transition disabled:opacity-50"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        {/* Quick Login */}
        <div className="mt-6">
          <p className="text-gray-500 text-xs text-center mb-3">Quick Demo Login</p>
          <div className="flex gap-2">
            <button onClick={() => quickLogin('operator', 'operator123')}
              className="flex-1 bg-aero-panel border border-aero-border rounded-lg py-2 text-xs text-gray-300 hover:border-aero-green transition">
              👁️ Operator
            </button>
            <button onClick={() => quickLogin('engineer', 'engineer123')}
              className="flex-1 bg-aero-panel border border-aero-border rounded-lg py-2 text-xs text-gray-300 hover:border-aero-yellow transition">
              🔧 Engineer
            </button>
            <button onClick={() => quickLogin('admin', 'admin123')}
              className="flex-1 bg-aero-panel border border-aero-border rounded-lg py-2 text-xs text-gray-300 hover:border-aero-red transition">
              ⚙️ Admin
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
