import { useState, useEffect } from 'react'
import axios from 'axios'
import { useParams, Link } from 'react-router-dom'

function FileDetail() {
  const { fileId } = useParams()
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchFileDetails()
  }, [fileId])

  const fetchFileDetails = async () => {
    try {
      setLoading(true)
      const response = await axios.get(`/api/files/${fileId}`)
      setFile(response.data)
      setLoading(false)
    } catch (err) {
      setError(err.response?.data?.error || err.message)
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-4 text-gray-600">Loading file details...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <div className="text-red-500 text-xl mb-4">Error: {error}</div>
        <Link to="/browse" className="btn btn-primary">
          ← Back to Browse
        </Link>
      </div>
    )
  }

  const getFileIcon = (mimeType) => {
    if (!mimeType) return '📄'
    if (mimeType.startsWith('video/')) return '🎥'
    if (mimeType.startsWith('audio/')) return '🎵'
    if (mimeType.startsWith('image/')) return '🖼️'
    if (mimeType.includes('pdf')) return '📕'
    if (mimeType.includes('zip') || mimeType.includes('rar')) return '📦'
    return '📄'
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown'
    const date = new Date(dateString)
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="container mx-auto px-4 py-12">
      <Link to="/browse" className="text-primary hover:underline mb-6 inline-block">
        ← Back to Browse
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main File Info */}
        <div className="lg:col-span-2">
          <div className="card">
            <div className="flex items-start gap-6 mb-6">
              <div className="text-6xl">{getFileIcon(file.mime_type)}</div>
              <div className="flex-grow">
                <h1 className="text-3xl font-bold text-gray-900 mb-2">
                  {file.file_name || 'Unnamed File'}
                </h1>
                <p className="text-gray-600">File ID: {file.id}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <InfoBox label="Size" value={file.file_size_formatted} />
              <InfoBox label="Views" value={file.total_views.toLocaleString()} />
              <InfoBox label="Downloads" value={file.total_downloads.toLocaleString()} />
              <InfoBox 
                label="Bandwidth" 
                value={formatBytes(file.total_bandwidth || 0)} 
              />
            </div>

            <div className="border-t pt-6 space-y-3">
              <DetailRow label="MIME Type" value={file.mime_type || 'Unknown'} />
              <DetailRow label="Upload Date" value={formatDate(file.upload_date)} />
              <DetailRow 
                label="Uploaded By" 
                value={
                  file.username 
                    ? `@${file.username}${file.first_name ? ` (${file.first_name})` : ''}` 
                    : 'Unknown User'
                } 
              />
              <DetailRow label="File Hash" value={file.file_hash} mono />
            </div>
          </div>

          {/* Recent Access Logs */}
          {file.recent_access && file.recent_access.length > 0 && (
            <div className="card mt-8">
              <h2 className="text-2xl font-bold mb-4">Recent Access</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="px-4 py-2 text-left">Date</th>
                      <th className="px-4 py-2 text-left">Type</th>
                      <th className="px-4 py-2 text-left">IP Address</th>
                      <th className="px-4 py-2 text-left">Data</th>
                    </tr>
                  </thead>
                  <tbody>
                    {file.recent_access.map((log, index) => (
                      <tr key={index} className="border-t">
                        <td className="px-4 py-2">
                          {formatDate(log.accessed_at)}
                        </td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-1 rounded text-xs ${
                            log.access_type === 'download' 
                              ? 'bg-green-100 text-green-800' 
                              : 'bg-blue-100 text-blue-800'
                          }`}>
                            {log.access_type}
                          </span>
                        </td>
                        <td className="px-4 py-2 font-mono text-xs">
                          {log.ip_address}
                        </td>
                        <td className="px-4 py-2">
                          {formatBytes(log.bytes_served || 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Bot Mappings */}
          {file.bot_mappings && file.bot_mappings.length > 0 && (
            <div className="card">
              <h3 className="text-lg font-bold mb-4">Storage Info</h3>
              <div className="space-y-3">
                {file.bot_mappings.map((mapping, index) => (
                  <div key={index} className="bg-gray-50 p-3 rounded-lg">
                    <p className="text-sm text-gray-600">Bot {mapping.bot_index}</p>
                    <p className="text-xs font-mono text-gray-500 mt-1 truncate">
                      Msg ID: {mapping.telegram_message_id}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Quick Actions */}
          <div className="card">
            <h3 className="text-lg font-bold mb-4">Actions</h3>
            <div className="space-y-2">
              <button 
                className="w-full btn btn-primary"
                onClick={() => alert('Link generation requires authentication. This feature will be available in Phase 8.')}
              >
                🔗 Generate Download Link
              </button>
              <p className="text-xs text-gray-500 text-center">
                Authentication required
              </p>
            </div>
          </div>

          {/* File Statistics */}
          <div className="card">
            <h3 className="text-lg font-bold mb-4">Statistics</h3>
            <div className="space-y-3">
              <StatBar 
                label="Views" 
                value={file.total_views} 
                color="bg-blue-500"
              />
              <StatBar 
                label="Downloads" 
                value={file.total_downloads} 
                color="bg-green-500"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function InfoBox({ label, value }) {
  return (
    <div className="bg-gray-50 p-4 rounded-lg">
      <p className="text-xs text-gray-600 mb-1">{label}</p>
      <p className="text-xl font-bold text-gray-900">{value}</p>
    </div>
  )
}

function DetailRow({ label, value, mono = false }) {
  return (
    <div className="flex justify-between items-start">
      <span className="text-gray-600 font-medium">{label}:</span>
      <span className={`text-gray-900 text-right ml-4 ${mono ? 'font-mono text-xs' : ''}`}>
        {value}
      </span>
    </div>
  )
}

function StatBar({ label, value, color }) {
  const maxValue = 1000
  const percentage = Math.min((value / maxValue) * 100, 100)
  
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-semibold">{value.toLocaleString()}</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div 
          className={`${color} h-2 rounded-full transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
    </div>
  )
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

export default FileDetail
