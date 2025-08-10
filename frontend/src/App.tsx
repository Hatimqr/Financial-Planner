import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [apiStatus, setApiStatus] = useState<string>('Checking...')

  useEffect(() => {
    fetch('/api/health')
      .then(res => res.json())
      .then(data => setApiStatus(data.status))
      .catch(() => setApiStatus('Backend not running'))
  }, [])

  return (
    <div className="App">
      <header className="App-header">
        <h1>Financial Planning</h1>
        <p>Local-First Investment Planner & Portfolio Analytics</p>
        <div>
          <strong>API Status:</strong> {apiStatus}
        </div>
      </header>
    </div>
  )
}

export default App
