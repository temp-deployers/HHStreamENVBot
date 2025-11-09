import { useState, useEffect } from 'react'
import axios from 'axios'
import { Link } from 'react-router-dom'

function Home() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchStats()
  }, [])

  const fetchStats = async () => {
    try {
      const response = await axios.get('/api/stats')
      setStats(response.data)
      setLoading(false)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-4 text-gray-600">Loading statistics...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <div className="text-red-500 text-xl">Error loading statistics</div>
        <p className="text-gray-600 mt-2">{error}</p>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-12">
      {/* Hero Section */}
      <div className="text-center mb-16">
        <h1 className="text-5xl font-bold text-gray-900 mb-4">
          Welcome to <span className="text-primary">LinkerX CDN</span>
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
          Secure file streaming service powered by Telegram. Fast, reliable, and efficient.
        </p>
        <Link to="/browse" className="btn btn-primary text-lg px-8 py-3">
          Browse Files
        </Link>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
        <StatCard
          icon="📁"
          title="Total Files"
          value={stats.total_files.toLocaleString()}
          color="bg-blue-500"
        />
        <StatCard
          icon="👥"
          title="Active Users"
          value={stats.total_users.toLocaleString()}
          color="bg-green-500"
        />
        <StatCard
          icon="👁️"
          title="Total Views"
          value={stats.total_views.toLocaleString()}
          color="bg-purple-500"
        />
        <StatCard
          icon="⬇️"
          title="Total Downloads"
          value={stats.total_downloads.toLocaleString()}
          color="bg-orange-500"
        />
      </div>

      {/* Additional Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-700 mb-2">Total Bandwidth</h3>
          <p className="text-3xl font-bold text-primary">{stats.total_bandwidth_formatted}</p>
          <p className="text-sm text-gray-500 mt-2">Data transferred</p>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-gray-700 mb-2">Active Links</h3>
          <p className="text-3xl font-bold text-primary">{stats.active_links.toLocaleString()}</p>
          <p className="text-sm text-gray-500 mt-2">Valid streaming links</p>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-gray-700 mb-2">System Uptime</h3>
          <p className="text-3xl font-bold text-primary">{stats.active_bots}</p>
          <p className="text-sm text-gray-500 mt-2">Active bots</p>
          <p className="text-xs text-gray-400 mt-1">Uptime: {stats.uptime}</p>
        </div>
      </div>

      {/* Features Section */}
      <div className="mt-16">
        <h2 className="text-3xl font-bold text-center mb-12">Why Choose LinkerX CDN?</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <FeatureCard
            icon="⚡"
            title="Lightning Fast"
            description="Powered by Telegram's global CDN infrastructure for ultra-fast file delivery."
          />
          <FeatureCard
            icon="🔒"
            title="Secure & Private"
            description="Advanced encryption and secure link generation with expiration controls."
          />
          <FeatureCard
            icon="📊"
            title="Analytics"
            description="Track views, downloads, and bandwidth usage with detailed analytics."
          />
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon, title, value, color }) {
  return (
    <div className="card hover:shadow-xl transition-shadow">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 mb-1">{title}</p>
          <p className="text-3xl font-bold text-gray-900">{value}</p>
        </div>
        <div className={`${color} text-white text-4xl p-4 rounded-lg`}>
          {icon}
        </div>
      </div>
    </div>
  )
}

function FeatureCard({ icon, title, description }) {
  return (
    <div className="card text-center hover:shadow-xl transition-shadow">
      <div className="text-5xl mb-4">{icon}</div>
      <h3 className="text-xl font-bold mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  )
}

export default Home
