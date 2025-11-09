import { useState, useEffect } from 'react'
import axios from 'axios'
import { Link } from 'react-router-dom'

function Browse() {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState(null)
  const [sortBy, setSortBy] = useState('upload_date')
  const [order, setOrder] = useState('desc')

  useEffect(() => {
    fetchFiles()
  }, [page, sortBy, order])

  const fetchFiles = async (searchQuery = search) => {
    try {
      setLoading(true)
      const params = {
        page,
        limit: 20,
        sort: sortBy,
        order,
      }
      if (searchQuery) {
        params.search = searchQuery
      }
      
      const response = await axios.get('/api/files', { params })
      setFiles(response.data.files)
      setPagination(response.data.pagination)
      setLoading(false)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  const handleSearch = (e) => {
    e.preventDefault()
    setPage(1)
    fetchFiles(search)
  }

  const handleSort = (newSortBy) => {
    if (sortBy === newSortBy) {
      setOrder(order === 'desc' ? 'asc' : 'desc')
    } else {
      setSortBy(newSortBy)
      setOrder('desc')
    }
    setPage(1)
  }

  return (
    <div className="container mx-auto px-4 py-12">
      <h1 className="text-4xl font-bold mb-8">Browse Files</h1>

      {/* Search and Filter Bar */}
      <div className="card mb-8">
        <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-4">
          <div className="flex-grow">
            <input
              type="text"
              placeholder="Search files by name..."
              className="input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary">
            🔍 Search
          </button>
          {search && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setSearch('')
                setPage(1)
                fetchFiles('')
              }}
            >
              Clear
            </button>
          )}
        </form>

        {/* Sort Options */}
        <div className="flex flex-wrap gap-2 mt-4">
          <span className="text-gray-600">Sort by:</span>
          <SortButton
            label="Upload Date"
            value="upload_date"
            active={sortBy === 'upload_date'}
            order={sortBy === 'upload_date' ? order : null}
            onClick={() => handleSort('upload_date')}
          />
          <SortButton
            label="Views"
            value="total_views"
            active={sortBy === 'total_views'}
            order={sortBy === 'total_views' ? order : null}
            onClick={() => handleSort('total_views')}
          />
          <SortButton
            label="Downloads"
            value="total_downloads"
            active={sortBy === 'total_downloads'}
            order={sortBy === 'total_downloads' ? order : null}
            onClick={() => handleSort('total_downloads')}
          />
          <SortButton
            label="Size"
            value="file_size"
            active={sortBy === 'file_size'}
            order={sortBy === 'file_size' ? order : null}
            onClick={() => handleSort('file_size')}
          />
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="text-center py-16">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading files...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="text-center py-16">
          <div className="text-red-500 text-xl">Error loading files</div>
          <p className="text-gray-600 mt-2">{error}</p>
        </div>
      )}

      {/* Files Grid */}
      {!loading && !error && (
        <>
          {files.length === 0 ? (
            <div className="text-center py-16">
              <div className="text-gray-400 text-xl">No files found</div>
              <p className="text-gray-500 mt-2">
                {search ? 'Try a different search query' : 'No files have been uploaded yet'}
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {files.map((file) => (
                  <FileCard key={file.id} file={file} />
                ))}
              </div>

              {/* Pagination */}
              {pagination && pagination.total_pages > 1 && (
                <div className="flex justify-center items-center gap-4 mt-8">
                  <button
                    className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={!pagination.has_prev}
                    onClick={() => setPage(page - 1)}
                  >
                    ← Previous
                  </button>
                  
                  <span className="text-gray-700">
                    Page {pagination.current_page} of {pagination.total_pages}
                  </span>
                  
                  <button
                    className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={!pagination.has_next}
                    onClick={() => setPage(page + 1)}
                  >
                    Next →
                  </button>
                </div>
              )}

              {/* Results Info */}
              {pagination && (
                <div className="text-center mt-4 text-gray-600">
                  Showing {files.length} of {pagination.total_count.toLocaleString()} files
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}

function SortButton({ label, value, active, order, onClick }) {
  return (
    <button
      className={`px-3 py-1 rounded-lg text-sm transition ${
        active
          ? 'bg-primary text-white'
          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
      }`}
      onClick={onClick}
    >
      {label} {active && (order === 'desc' ? '↓' : '↑')}
    </button>
  )
}

function FileCard({ file }) {
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
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  return (
    <Link to={`/file/${file.id}`} className="card hover:shadow-xl transition-shadow">
      <div className="flex items-start gap-4">
        <div className="text-4xl">{getFileIcon(file.mime_type)}</div>
        <div className="flex-grow min-w-0">
          <h3 className="font-semibold text-gray-900 truncate mb-2">
            {file.file_name || 'Unnamed File'}
          </h3>
          <div className="space-y-1 text-sm text-gray-600">
            <p>📦 {file.file_size_formatted}</p>
            <p>👁️ {file.total_views.toLocaleString()} views</p>
            <p>⬇️ {file.total_downloads.toLocaleString()} downloads</p>
            <p className="text-xs text-gray-500">
              📅 {formatDate(file.upload_date)}
            </p>
          </div>
          {file.username && (
            <p className="text-xs text-gray-400 mt-2">
              Uploaded by @{file.username}
            </p>
          )}
        </div>
      </div>
    </Link>
  )
}

export default Browse
