import { Layout, Menu } from 'antd'
import { useState } from 'react'

export function App() {
  const [current, setCurrent] = useState('dashboard')
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider>
        <Menu selectedKeys={[current]} onClick={(e) => setCurrent(e.key)} items={[
          { key: 'dashboard', label: 'Dashboard' },
          { key: 'visits', label: 'Visits' },
        ]} />
      </Layout.Sider>
      <Layout.Content style={{ padding: 24 }}>
        <h1 className="text-xl font-semibold">Face Recognition MVP</h1>
        <p>Current: {current}</p>
      </Layout.Content>
    </Layout>
  )
}

