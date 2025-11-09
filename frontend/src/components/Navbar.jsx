import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

function Navbar() {
  const { isAuthenticated, user } = useAuth()

  return (
    <nav className="bg-white shadow-lg">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="flex items-center space-x-2">
            <div className="text-2xl font-bold text-primary">LinkerX CDN</div>
          </Link>
          
          <div className="hidden md:flex space-x-6">
            <Link to="/" className="text-gray-700 hover:text-primary transition">
              Home
            </Link>
            <Link to="/browse" className="text-gray-700 hover:text-primary transition">
              Browse Files
            </Link>
            {isAuthenticated() ? (
              <>
                <Link to="/dashboard" className="text-gray-700 hover:text-primary transition">
                  Dashboard
                </Link>
                <Link to="/generate-link" className="text-gray-700 hover:text-primary transition">
                  Generate Link
                </Link>
              </>
            ) : (
              <Link to="/login" className="text-gray-700 hover:text-primary transition">
                Login
              </Link>
            )}
          </div>
          
          {isAuthenticated() && user && (
            <div className="hidden md:block text-sm text-gray-600">
              👤 {user.username || user.first_name}
            </div>
          )}
          
          <div className="md:hidden">
            <button className="text-gray-700">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </nav>
  )
}

export default Navbar
