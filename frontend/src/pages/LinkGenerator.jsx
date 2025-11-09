import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'

function LinkGenerator() {
  const navigate = useNavigate()
  const { token, isAuthenticated } = useAuth()
  
  const [files, setFiles] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [quota, setQuota] = useState(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [expiryDays, setExpiryDays] = useState(7)
  const [generatedLink, setGeneratedLink] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isAuthenticated()) {
      navigate('/login')
      return
    }
    
    fetchData()
  }, [isAuthenticated, navigate])

  const fetchData = async () => {
    try {
      const config = {
        headers: { Authorization: `Bearer ${token}` }
      }

      const [filesRes, quotaRes] = await Promise.all([
        axios.get('/api/files?limit=100', config),
        axios.get('/api/user/quota', config)
      ])

      setFiles(filesRes.data.files)
      setQuota(quotaRes.data)
      setLoading(false)
    } catch (err) {
      console.error('Error fetching data:', err)
      if (err.response?.status === 401) {
        navigate('/login')
      }
      setLoading(false)
    }
  }

  const handleGenerateLink = async () => {
    if (!selectedFile) return
    
    setError('')
    setGenerating(true)
    setGeneratedLink(null)

    try {
      const config = {
        headers: { Authorization: `Bearer ${token}` }
      }

      const response = await axios.post('/api/user/generate-link', {
        file_id: selectedFile.id,
        expiry_days: expiryDays
      }, config)

      setGeneratedLink(response.data)
      // Refresh quota
      const quotaRes = await axios.get('/api/user/quota', config)
      setQuota(quotaRes.data)
    } catch (err) {
      setError(err.response?.data?.message || err.response?.data?.error || 'Failed to generate link')
    } finally {
      setGenerating(false)
    }
  }

  const handleCopyLink = () => {
    if (generatedLink?.link) {
      navigator.clipboard.writeText(generatedLink.link)
      alert('Link copied to clipboard!')
    }
  }

  const filteredFiles = files.filter(file =>
    file.file_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-4 text-gray-600">Loading...</p>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Link Generator</h1>
        <p className="text-gray-600 mb-8">Generate shareable links for files in the database</p>

        {/* Quota Display */}
        {quota && (
          <div className="card mb-8 bg-gradient-to-r from-blue-50 to-purple-50 border-blue-200">
            <h2 className="text-lg font-semibold mb-4">Your Quota Status</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <QuotaCard
                title="5 Minutes"
                used={quota.quotas['5min'].used}
                limit={quota.quotas['5min'].limit}
                remaining={quota.quotas['5min'].remaining}
                canGenerate={quota.quotas['5min'].can_generate}
              />
              <QuotaCard
                title="1 Hour"
                used={quota.quotas.hour.used}
                limit={quota.quotas.hour.limit}
                remaining={quota.quotas.hour.remaining}
                canGenerate={quota.quotas.hour.can_generate}
              />
              <QuotaCard
                title="24 Hours"
                used={quota.quotas.day.used}
                limit={quota.quotas.day.limit}
                remaining={quota.quotas.day.remaining}
                canGenerate={quota.quotas.day.can_generate}
              />
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* File Selection */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Select File</h2>
            
            <div className="mb-4">
              <input
                type="text"
                placeholder="Search files..."
                className="input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div className="space-y-2 max-h-96 overflow-y-auto">
              {filteredFiles.length > 0 ? (
                filteredFiles.map(file => (
                  <FileCard
                    key={file.id}
                    file={file}
                    selected={selectedFile?.id === file.id}
                    onSelect={() => setSelectedFile(file)}
                  />
                ))
              ) : (
                <p className="text-gray-500 text-center py-8">No files found</p>
              )}
            </div>
          </div>

          {/* Link Generation */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Generate Link</h2>
            
            {selectedFile ? (
              <div className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <p className="text-sm text-gray-600 mb-1">Selected File</p>
                  <p className="font-semibold text-gray-900">{selectedFile.file_name}</p>
                  <p className="text-sm text-gray-600">{selectedFile.file_size_formatted}</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Link Expiry
                  </label>
                  <select
                    className="input"
                    value={expiryDays}
                    onChange={(e) => setExpiryDays(parseInt(e.target.value))}
                  >
                    <option value={1}>1 Day</option>
                    <option value={7}>7 Days</option>
                    <option value={14}>14 Days</option>
                    <option value={30}>30 Days</option>
                  </select>
                </div>

                {error && (
                  <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                    {error}
                  </div>
                )}

                <button
                  onClick={handleGenerateLink}
                  disabled={generating || !quota?.can_generate_link}
                  className="w-full btn btn-primary py-3"
                >
                  {generating ? 'Generating...' : 'Generate Link'}
                </button>

                {!quota?.can_generate_link && (
                  <p className="text-sm text-red-600 text-center">
                    ⚠️ Quota limit reached. Please wait before generating more links.
                  </p>
                )}

                {generatedLink && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4 space-y-3">
                    <div>
                      <p className="text-sm text-gray-600 mb-1">Your Link</p>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          readOnly
                          value={generatedLink.link}
                          className="input flex-1 text-sm"
                        />
                        <button
                          onClick={handleCopyLink}
                          className="btn btn-secondary px-4"
                        >
                          Copy
                        </button>
                      </div>
                    </div>
                    <div className="text-sm text-gray-600">
                      <p>Expires: {new Date(generatedLink.expiry_date).toLocaleString()}</p>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <p className="text-4xl mb-4">📁</p>
                <p>Select a file from the left to generate a link</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function QuotaCard({ title, used, limit, remaining, canGenerate }) {
  const percentage = (used / limit) * 100

  return (
    <div className="bg-white rounded-lg p-4 border">
      <div className="flex justify-between items-start mb-2">
        <p className="text-sm font-medium text-gray-700">{title}</p>
        <span className={`text-xs px-2 py-1 rounded ${
          canGenerate ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
        }`}>
          {canGenerate ? 'Available' : 'Limit Reached'}
        </span>
      </div>
      <p className="text-2xl font-bold text-gray-900 mb-2">
        {remaining} <span className="text-sm font-normal text-gray-600">left</span>
      </p>
      <div className="flex items-center gap-2 text-sm text-gray-600">
        <div className="flex-1 bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all ${
              percentage >= 100 ? 'bg-red-500' : percentage >= 80 ? 'bg-yellow-500' : 'bg-green-500'
            }`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>
        <span>{used}/{limit}</span>
      </div>
    </div>
  )
}

function FileCard({ file, selected, onSelect }) {
  const getFileIcon = (mimeType) => {
    if (!mimeType) return '📄'
    if (mimeType.startsWith('video/')) return '🎥'
    if (mimeType.startsWith('audio/')) return '🎵'
    if (mimeType.startsWith('image/')) return '🖼️'
    return '📄'
  }

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left p-3 rounded-lg border-2 transition ${
        selected
          ? 'border-primary bg-blue-50'
          : 'border-gray-200 hover:border-gray-300 bg-white'
      }`}
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl">{getFileIcon(file.mime_type)}</span>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-900 truncate">{file.file_name}</p>
          <p className="text-sm text-gray-600">
            {file.file_size_formatted} • {file.total_views} views
          </p>
        </div>
        {selected && (
          <span className="text-primary">✓</span>
        )}
      </div>
    </button>
  )
}

export default LinkGenerator
