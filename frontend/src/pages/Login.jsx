import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'

function Login() {
  const navigate = useNavigate()
  const { login } = useAuth()
  
  const [step, setStep] = useState(1) // 1: Enter ID, 2: Enter OTP
  const [telegramId, setTelegramId] = useState('')
  const [otp, setOtp] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [generatedOtp, setGeneratedOtp] = useState('')

  const handleRequestOtp = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await axios.post('/api/auth/request-otp', {
        telegram_id: telegramId
      })
      
      if (response.data.success) {
        setGeneratedOtp(response.data.otp) // For testing only
        setStep(2)
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to request OTP')
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyOtp = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await axios.post('/api/auth/verify-otp', {
        telegram_id: telegramId,
        otp_code: otp
      })
      
      if (response.data.success) {
        login(response.data.token, response.data.user)
        navigate('/dashboard')
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to verify OTP')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Sign in to LinkerX CDN
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Telegram ID based authentication
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        {step === 1 ? (
          <form className="mt-8 space-y-6" onSubmit={handleRequestOtp}>
            <div>
              <label htmlFor="telegram-id" className="block text-sm font-medium text-gray-700 mb-2">
                Telegram User ID
              </label>
              <input
                id="telegram-id"
                type="text"
                required
                className="input"
                placeholder="Enter your Telegram ID"
                value={telegramId}
                onChange={(e) => setTelegramId(e.target.value)}
                disabled={loading}
              />
              <p className="mt-2 text-xs text-gray-500">
                Test IDs: 123456789 or 987654321
              </p>
            </div>

            <button
              type="submit"
              className="w-full btn btn-primary py-3 text-lg"
              disabled={loading}
            >
              {loading ? 'Requesting OTP...' : 'Request OTP'}
            </button>
          </form>
        ) : (
          <form className="mt-8 space-y-6" onSubmit={handleVerifyOtp}>
            {generatedOtp && (
              <div className="bg-blue-50 border border-blue-200 text-blue-700 px-4 py-3 rounded">
                <p className="font-semibold">Test Mode - Your OTP:</p>
                <p className="text-2xl font-bold mt-2">{generatedOtp}</p>
                <p className="text-xs mt-2">In production, this would be sent via Telegram</p>
              </div>
            )}

            <div>
              <label htmlFor="otp" className="block text-sm font-medium text-gray-700 mb-2">
                Enter OTP
              </label>
              <input
                id="otp"
                type="text"
                required
                maxLength="6"
                className="input text-center text-2xl tracking-widest"
                placeholder="000000"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                disabled={loading}
                autoFocus
              />
            </div>

            <div className="flex gap-4">
              <button
                type="button"
                className="flex-1 btn btn-secondary py-3"
                onClick={() => {
                  setStep(1)
                  setOtp('')
                  setGeneratedOtp('')
                  setError('')
                }}
                disabled={loading}
              >
                Back
              </button>
              <button
                type="submit"
                className="flex-1 btn btn-primary py-3"
                disabled={loading || otp.length !== 6}
              >
                {loading ? 'Verifying...' : 'Verify OTP'}
              </button>
            </div>
          </form>
        )}

        <div className="text-center">
          <p className="text-sm text-gray-600">
            Don't have an account? Contact admin or use the Telegram bot
          </p>
        </div>
      </div>
    </div>
  )
}

export default Login
