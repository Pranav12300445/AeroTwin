import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AeroTwin — UAV Engine Health Monitor',
  description: 'Digital-twin health monitoring agent for UAV turbine engines',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-aero-dark">{children}</body>
    </html>
  )
}
