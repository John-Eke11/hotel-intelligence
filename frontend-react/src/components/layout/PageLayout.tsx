import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

export default function PageLayout() {
  return (
    <div className="flex min-h-screen" style={{ background: 'var(--color-bg-base)' }}>
      <Sidebar />
      <div className="flex flex-col flex-1" style={{ marginLeft: 220 }}>
        <TopBar />
        <main className="flex-1 px-8 py-8" style={{ maxWidth: 1440 }}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
