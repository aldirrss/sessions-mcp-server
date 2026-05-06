import NavSidebar from '@/components/nav-sidebar'

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <NavSidebar />
      <main className="flex-1 md:ml-60 pt-14 md:pt-0 p-4 md:p-8 overflow-y-auto min-w-0">
        {children}
      </main>
    </div>
  )
}
