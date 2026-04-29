import { useEffect, useRef } from 'react'
import ResultTable  from './ResultTable'

export default function OutputPanel({ messages, isLoading }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div style={s.panel}>
      <div style={s.titleBar}>
        <span style={s.title}>// terminal output</span>
        <span style={s.msgCount}>{messages.filter(m => m.type === 'result').length} queries</span>
      </div>

      <div style={s.output} id="output-area">
        {messages.map((msg, i) => (
          <MessageBlock key={i} msg={msg} />
        ))}
        {isLoading && <ThinkingBlock />}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function MessageBlock({ msg }) {
  if (msg.type === 'boot') {
    return <div style={s.bootLine}>{msg.text || <br />}</div>
  }

  if (msg.type === 'user') {
    return (
      <div style={s.userMsg}>
        <span style={s.prompt}>❯&nbsp;</span>
        <span style={s.userText}>{msg.text}</span>
      </div>
    )
  }

  if (msg.type === 'error') {
    return (
      <div style={s.errorBlock}>
        <span style={s.errorTag}>[ERROR]</span> {msg.text}
      </div>
    )
  }

  if (msg.type === 'result') {
    return (
      <div style={s.resultBlock}>
        {msg.error ? (
          <div style={s.errorBlock}>
            <span style={s.errorTag}>[BLOCKED]</span> {msg.error}
          </div>
        ) : (
          <>
            {msg.summary && (
              <div style={s.summary}>// {msg.summary}</div>
            )}
            <div style={s.meta}>
              <span style={s.metaChip}>tables: {msg.tables?.join(', ')}</span>
              <span style={s.metaChip}>{msg.rows?.length ?? 0} rows</span>
              <span style={s.metaChip}>{msg.duration}ms</span>
            </div>
            <ResultTable rows={msg.rows} />
          </>
        )}
      </div>
    )
  }

  return null
}

function ThinkingBlock() {
  return (
    <div style={s.thinking}>
      <span style={s.thinkingDots}>
        <span className="dot1">█</span>
        <span className="dot2">█</span>
        <span className="dot3">█</span>
      </span>
      <span style={{ color: '#005500', marginLeft: 8 }}>processing query...</span>

      <style>{`
        .dot1, .dot2, .dot3 {
          color: #00ff41;
          animation: blink-dot 1.2s infinite;
        }
        .dot2 { animation-delay: 0.2s; }
        .dot3 { animation-delay: 0.4s; }
        @keyframes blink-dot {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.1; }
        }
      `}</style>
    </div>
  )
}

const s = {
  panel: {
    display:       'flex',
    flexDirection: 'column',
    overflow:      'hidden',
    borderRight:   '1px solid #002200',
    background:    '#000',
  },
  titleBar: {
    display:        'flex',
    justifyContent: 'space-between',
    alignItems:     'center',
    padding:        '5px 14px',
    borderBottom:   '1px solid #002200',
    background:     '#000',
  },
  title:    { fontSize: 10, color: '#005500', letterSpacing: 2 },
  msgCount: { fontSize: 10, color: '#004400' },
  output: {
    flex:      1,
    overflowY: 'auto',
    padding:   '14px 16px',
  },
  bootLine: {
    color:    '#006600',
    fontSize: 12,
    minHeight: 18,
    fontFamily: 'inherit',
  },
  userMsg: {
    display:   'flex',
    marginTop: 14,
    marginBottom: 6,
  },
  prompt:    { color: '#00ff41', fontWeight: 700 },
  userText:  { color: '#00cc33', fontWeight: 500 },
  resultBlock: { marginBottom: 18 },
  summary: {
    color:    '#008833',
    fontSize: 11,
    marginBottom: 6,
    fontStyle: 'italic',
  },
  meta: {
    display:      'flex',
    gap:          8,
    marginBottom: 8,
  },
  metaChip: {
    fontSize:   10,
    color:      '#005500',
    border:     '1px solid #002200',
    padding:    '1px 6px',
    letterSpacing: 0.5,
  },
  errorBlock: {
    color:      '#ff4444',
    fontSize:   12,
    marginTop:  6,
    padding:    '6px 10px',
    border:     '1px solid #440000',
    background: '#0a0000',
  },
  errorTag: { fontWeight: 700 },
  thinking: {
    display:   'flex',
    alignItems: 'center',
    marginTop:  10,
    fontSize:   13,
  },
  thinkingDots: { display: 'flex', gap: 3 },
}