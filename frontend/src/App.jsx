import { useState, useRef, useEffect, useCallback } from 'react'
import axios from 'axios'
import Header        from './components/Header'
import OutputPanel   from './components/OutputPanel'
import InputBar      from './components/InputBar'
import SidePanel     from './components/SidePanel'
import './index.css'

const API = 'http://localhost:8000'

const BOOT_LINES = [
  '╔══════════════════════════════════════════════════════════╗',
  '║         DB-ORACLE  ::  Natural Language SQL v2.0         ║',
  '╚══════════════════════════════════════════════════════════╝',
  '',
  '  [OK] SQLite HR database .............. connected',
  '  [OK] ChromaDB schema index ........... loaded',
  '  [OK] Ollama LLM (llama3) ............. ready',
  '  [OK] Read-only guard ................. ACTIVE',
  '',
  '  Type a question in plain English to query your HR data.',
  '  Example: "Who are the top 5 highest paid employees?"',
  '',
]

export default function App() {
  const [messages,    setMessages]    = useState([])
  const [logs,        setLogs]        = useState([])
  const [isLoading,   setIsLoading]   = useState(false)
  const [health,      setHealth]      = useState(null)
  const [booted,      setBooted]      = useState(false)
  const [currentSQL,  setCurrentSQL]  = useState('')
  const abortRef = useRef(null)

  /* ── Boot sequence ───────────────────────────────────────── */
  useEffect(() => {
    let i = 0
    const tick = () => {
      if (i >= BOOT_LINES.length) { setBooted(true); return }
      setMessages(prev => [...prev, { type: 'boot', text: BOOT_LINES[i++] }])
      setTimeout(tick, 45)
    }
    tick()

    axios.get(`${API}/health`)
      .then(r => setHealth(r.data))
      .catch(() => setHealth({ status: 'unreachable' }))
  }, [])

  /* ── Submit question ─────────────────────────────────────── */
  const handleSubmit = useCallback(async (question) => {
    if (isLoading) return
    setIsLoading(true)
    setCurrentSQL('')
    setLogs([])

    setMessages(prev => [...prev,
      { type: 'user', text: question },
      { type: 'thinking' }
    ])

    try {
      const res = await axios.post(`${API}/query`, {
        question,
        use_react: false,
      })
      const data = res.data

      setCurrentSQL(data.sql || '')
      setLogs(data.logs || [])

      setMessages(prev => {
        const filtered = prev.filter(m => m.type !== 'thinking')
        return [...filtered, {
          type:    'result',
          question,
          sql:     data.sql,
          rows:    data.rows,
          summary: data.summary,
          tables:  data.relevant_tables,
          duration: data.duration_ms,
          error:   data.error,
        }]
      })
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Connection failed'
      setMessages(prev => {
        const filtered = prev.filter(m => m.type !== 'thinking')
        return [...filtered, { type: 'error', text: msg }]
      })
      setLogs([`ERROR: ${msg}`])
    } finally {
      setIsLoading(false)
    }
  }, [isLoading])

  const handleClear = () => {
    setMessages([])
    setLogs([])
    setCurrentSQL('')
    setBooted(false)
    let i = 0
    const tick = () => {
      if (i >= BOOT_LINES.length) { setBooted(true); return }
      setMessages(prev => [...prev, { type: 'boot', text: BOOT_LINES[i++] }])
      setTimeout(tick, 30)
    }
    tick()
  }

  return (
    <div style={styles.app}>
      <Header health={health} onClear={handleClear} />

      <div style={styles.body}>
        <OutputPanel
          messages={messages}
          isLoading={isLoading}
        />
        <SidePanel
          logs={logs}
          sql={currentSQL}
          isLoading={isLoading}
        />
      </div>

      <InputBar
        onSubmit={handleSubmit}
        isLoading={isLoading}
        booted={booted}
      />
    </div>
  )
}

const styles = {
  app: {
    display:       'grid',
    gridTemplateRows: 'auto 1fr auto',
    height:        '100vh',
    background:    '#000',
    overflow:      'hidden',
  },
  body: {
    display:       'grid',
    gridTemplateColumns: '1fr 340px',
    overflow:      'hidden',
    borderTop:     '1px solid #003300',
    borderBottom:  '1px solid #003300',
  },
}