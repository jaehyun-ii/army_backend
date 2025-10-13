import type { Metadata } from 'next'
import { Providers } from './providers'
import Navigation from './components/Navigation'

export const metadata: Metadata = {
  title: 'Adversarial Vision Platform',
  description: 'Platform for adversarial attacks and model evaluation',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <Navigation />
          <main>
            {children}
          </main>
        </Providers>
      </body>
    </html>
  )
}
