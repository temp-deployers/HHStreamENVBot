function Footer() {
  return (
    <footer className="bg-dark text-white mt-16">
      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <h3 className="text-xl font-bold mb-4">LinkerX CDN</h3>
            <p className="text-gray-400">
              Secure file streaming service powered by Telegram.
              Fast, reliable, and efficient.
            </p>
          </div>
          
          <div>
            <h3 className="text-xl font-bold mb-4">Quick Links</h3>
            <ul className="space-y-2 text-gray-400">
              <li><a href="/" className="hover:text-white transition">Home</a></li>
              <li><a href="/browse" className="hover:text-white transition">Browse Files</a></li>
              <li><a href="https://t.me/LiquidXProjects" target="_blank" rel="noopener noreferrer" className="hover:text-white transition">Telegram</a></li>
            </ul>
          </div>
          
          <div>
            <h3 className="text-xl font-bold mb-4">About</h3>
            <p className="text-gray-400">
              Built with ❤️ by Hash Hackers and LiquidX Projects
            </p>
          </div>
        </div>
        
        <div className="border-t border-gray-700 mt-8 pt-8 text-center text-gray-400">
          <p>&copy; 2025 LinkerX CDN. All rights reserved.</p>
        </div>
      </div>
    </footer>
  )
}

export default Footer
