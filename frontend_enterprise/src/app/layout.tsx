import './globals.css'

export const metadata = {
  title: 'IT Road Consulting - Evaluation des Talents par IA',
  description: 'Automatisez votre recrutement et évaluation de CV avec notre plateforme SaaS intelligente.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="fr" className="dark">
      <body className="min-h-screen bg-[#0a0e27] text-white">
        {children}
      </body>
    </html>
  )
}
