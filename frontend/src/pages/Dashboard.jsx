import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'

function Dashboard() {
  const navigate = useNavigate()
  const { user, token, logout, isAuthenticated } = useAuth()
  
  const [stats, setStats] = useState(null)
  const [files, setFiles] = useState([])
  const [links, setLinks] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview') // overview, files, links

  useEffect(() => {
    if (!isAuthenticated()) {
      navigate('/login')
      return
    }
    
    fetchDashboardData()
  }, [isAuthenticated, navigate])

  const fetchDashboardData = async () => {
    try {
      const config = {
        headers: { Authorization: `Bearer ${token}` }
      }

      const [statsRes, filesRes, linksRes] = await Promise.all([
        axios.get('/api/user/stats', config),
        axios.get('/api/user/files', config),
        axios.get('/api/user/links', config)
      ])

      setStats(statsRes.data)
      setFiles(filesRes.data.files)
      setLinks(linksRes.data.links)
      setLoading(false)
    } catch (err) {
      console.error('Error fetching dashboard data:', err)
      if (err.response?.status === 401) {
        logout()
        navigate('/login')
      }
      setLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-4 text-gray-600">Loading dashboard...</p>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600 mt-1">
            Welcome back, {user?.first_name || user?.username || 'User'}!
          </p>
        </div>
        <button
          onClick={handleLogout}
          className="btn btn-secondary"
        >
          Logout
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <StatCard
            icon="📁"
            title="My Files"
            value={stats.total_files}
            color="bg-blue-500"
          />
          <StatCard
            icon="🔗"
            title="Generated Links"
            value={stats.total_links}
            color="bg-green-500"
          />
          <StatCard
            icon="👁️"
            title="Total Views"
            value={stats.total_views.toLocaleString()}
            color="bg-purple-500"
          />
          <StatCard
            icon="📊"
            title="Bandwidth Used"
            value={stats.total_bandwidth_formatted}
            color="bg-orange-500"
          />
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <TabButton
            active={activeTab === 'overview'}
            onClick={() => setActiveTab('overview')}
            label="Overview"
          />
          <TabButton
            active={activeTab === 'files'}
            onClick={() => setActiveTab('files')}
            label={`My Files (${files.length})`}
          />
          <TabButton
            active={activeTab === 'links'}
            onClick={() => setActiveTab('links')}
            label={`My Links (${links.length})`}
          />
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Recent Files</h2>
            {files.slice(0, 5).length > 0 ? (
              <div className="space-y-3">
                {files.slice(0, 5).map(file => (
                  <FileListItem key={file.id} file={file} />
                ))}
              </div>
            ) : (
              <p className="text-gray-500">No files uploaded yet</p>
            )}
            {files.length > 5 && (
              <button
                onClick={() => setActiveTab('files')}
                className="mt-4 text-primary hover:underline text-sm"
              >
                View all files →
              </button>
            )}
          </div>

          <div className="card">
            <h2 className="text-xl font-bold mb-4">Recent Links</h2>
            {links.slice(0, 5).length > 0 ? (
              <div className="space-y-3">
                {links.slice(0, 5).map((link, idx) => (
                  <LinkListItem key={idx} link={link} />
                ))}
              </div>
            ) : (
              <p className="text-gray-500">No links generated yet</p>
            )}
            {links.length > 5 && (
              <button
                onClick={() => setActiveTab('links')}
                className="mt-4 text-primary hover:underline text-sm"
              >
                View all links →
              </button>
            )}
          </div>
        </div>
      )}

      {activeTab === 'files' && (
        <div className="card">
          <h2 className="text-xl font-bold mb-4">All My Files</h2>
          {files.length > 0 ? (
            <div className="space-y-3">
              {files.map(file => (
                <FileListItem key={file.id} file={file} detailed />
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No files uploaded yet</p>
          )}
        </div>
      )}

      {activeTab === 'links' && (
        <div className="card">
          <h2 className="text-xl font-bold mb-4">All My Links</h2>
          {links.length > 0 ? (
            <div className="space-y-3">
              {links.map((link, idx) => (
                <LinkListItem key={idx} link={link} detailed />
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No links generated yet</p>
          )}
        </div>
      )}
    </div>
  )
}

function StatCard({ icon, title, value, color }) {
  return (
    <div className="card hover:shadow-xl transition-shadow">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 mb-1">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
        </div>
        <div className={`${color} text-white text-3xl p-3 rounded-lg`}>
          {icon}
        </div>
      </div>
    </div>
  )
}

function TabButton({ active, onClick, label }) {
  return (
    <button
      onClick={onClick}
      className={`py-4 px-1 border-b-2 font-medium text-sm ${
        active
          ? 'border-primary text-primary'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
      }`}
    >
      {label}
    </button>
  )
}

function FileListItem({ file, detailed = false }) {
  const getFileIcon = (mimeType) => {
    if (!mimeType) return '📄'
    if (mimeType.startsWith('video/')) return '🎥'
    if (mimeType.startsWith('audio/')) return '🎵'
    if (mimeType.startsWith('image/')) return '🖼️'
    return '📄'
  }

  return (
    <Link
      to={`/file/${file.id}`}
      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition"
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl">{getFileIcon(file.mime_type)}</span>
        <div>
          <p className="font-medium text-gray-900">{file.file_name}</p>
          <p className="text-sm text-gray-600">
            {file.file_size_formatted} • {file.total_views} views
          </p>
        </div>
      </div>
      {detailed && (
        <span className="text-primary">→</span>
      )}
    </Link>
  )
}

function LinkListItem({ link, detailed = false }) {
  const isActive = new Date(link.expiry_date) > new Date()
  
  return (
    <div className="p-3 bg-gray-50 rounded-lg">
      <div className="flex items-start justify-between">
        <div className="flex-grow">
          <p className="font-medium text-gray-900">{link.file_name}</p>
          <p className="text-sm text-gray-600 mt-1">
            ID: {link.unique_file_id}
          </p>
          {detailed && (
            <p className="text-xs text-gray-500 mt-1">
              Created: {new Date(link.created_at).toLocaleDateString()} • 
              Expires: {new Date(link.expiry_date).toLocaleDateString()}
            </p>
          )}
        </div>
        <span className={`px-2 py-1 rounded text-xs ${
          isActive ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
        }`}>
          {isActive ? 'Active' : 'Expired'}
        </span>
      </div>
    </div>
  )
}

export default Dashboard
