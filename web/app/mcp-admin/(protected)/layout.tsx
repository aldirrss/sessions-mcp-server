import NavSidebar from '@/components/nav-sidebar'

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <NavSidebar />
      <main className="flex-1 ml-60 p-8 overflow-y-auto">
        {children}
      </main>
    </div>
  )
}
