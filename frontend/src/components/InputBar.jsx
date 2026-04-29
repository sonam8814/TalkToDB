import { useState, useRef, useEffect } from 'react'

const SUGGESTIONS = [
  'Who are the top 5 highest paid employees?',
  'What is the average salary per department?',
  'List employees hired after 2022',
  'Who has the highest performance rating?',
  'How many employees are in each department?',
  'Which department is based in San Francisco?',
  'Show me all Product Managers and their salaries',
  'What is the total salary budget for Engineering?',
]

export default function InputBar({ onSubmit, isLoading, booted }) {
  const [value,   setValue]   = useState('')
  const [history, setHistory] = useState([])
  const [histIdx, setHistIdx] = useState(-1)
  const inputRef = useRef(null)

  useEffect(() => {
    if (booted) inputRef.current?.focus()
  }, [booted])

  const submit = () => {
    const q = value.trim()
    if (!q || isLoading) return
    setHistory(prev => [q, ...prev.slice(0, 49)])
    setHistIdx(-1)
    setValue('')
    onSubmit(q)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter') { submit(); return }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      const next = Math.min(histIdx + 1, history.length - 1)
      setHistIdx(next)
      setValue(history[next] || '')
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      const next = Math.max(histIdx - 1, -1)
      setHistIdx(next)
      setValue(next === -1 ? '' : history[next])
    }
  }

  return (
    <div style={s.wrapper}>
      {/* Quick suggestion chips */}
      <div style={s.chips}>
        {SUGGESTIONS.slice(0, 4).map((q, i) => (
          <button
            key={i}
            style={s.chip}
            onClick={() => { setValue(q); inputRef.current?.focus() }}
            disabled={isLoading}
          >
            {q.length > 38 ? q.slice(0, 36) + '…' : q}
          </button>
        ))}
      </div>

      {/* Input row */}
      <div style={s.row}>
        <span style={s.prompt}>
          {isLoading ? <span style={s.spinner}>⟳</span> : '❯'}
        </span>
        <input
          ref={inputRef}
          style={s.input}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKey}
          placeholder={isLoading ? 'processing...' : 'Ask anything about your HR data...'}
          disabled={isLoading}
          autoComplete="off"
          spellCheck={false}
        />
        <span style={s.hint}>↑↓ history · enter to run</span>
        <button
          style={{ ...s.btn, opacity: isLoading || !value.trim() ? 0.3 : 1 }}
          onClick={submit}
          disabled={isLoading || !value.trim()}
        >
          {isLoading ? 'RUNNING' : 'EXECUTE'}
        </button>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}

const s = {
  wrapper: {
    background:  '#000',
    borderTop:   '1px solid #003300',
  },
  chips: {
    display:    'flex',
    gap:        6,
    padding:    '7px 14px 0',
    flexWrap:   'wrap',
  },
  chip: {
    fontFamily:  'inherit',
    fontSize:    10,
    padding:     '3px 9px',
    background:  'transparent',
    border:      '1px solid #002800',
    color:       '#005500',
    cursor:      'pointer',
    letterSpacing: 0.3,
    transition:  'all 0.12s',
    whiteSpace:  'nowrap',
  },
  row: {
    display:    'flex',
    alignItems: 'center',
    gap:        8,
    padding:    '8px 14px 10px',
  },
  prompt: {
    color:      '#00ff41',
    fontSize:   15,
    fontWeight: 700,
    minWidth:   16,
    textAlign:  'center',
    display:    'inline-block',
    animation:  'spin 1s linear infinite',
  },
  spinner: {
    display:   'inline-block',
    animation: 'spin 1s linear infinite',
    color:     '#00ff41',
  },
  input: {
    flex:        1,
    background:  'transparent',
    border:      'none',
    outline:     'none',
    color:       '#00ff41',
    fontFamily:  'inherit',
    fontSize:    13,
    caretColor:  '#00ff41',
  },
  hint: {
    fontSize:   10,
    color:      '#003300',
    whiteSpace: 'nowrap',
    letterSpacing: 0.5,
  },
  btn: {
    fontFamily:   'inherit',
    fontSize:     11,
    padding:      '5px 14px',
    background:   'transparent',
    border:       '1px solid #006600',
    color:        '#00cc33',
    cursor:       'pointer',
    letterSpacing: 1.5,
    transition:   'all 0.12s',
    whiteSpace:   'nowrap',
  },
}