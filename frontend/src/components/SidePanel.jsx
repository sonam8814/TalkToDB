import { useEffect, useRef } from 'react'

const SCHEMA = [
  { name: 'employees',    cols: ['id','name','department_id','salary','hire_date','role'] },
  { name: 'departments',  cols: ['id','name','manager_id','location'] },
  { name: 'performance_reviews', cols: ['id','employee_id','rating','review_date'] },
]

export default function SidePanel({ logs, sql, isLoading }) {
  const logRef = useRef(null)

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs])

  return (
    <div style={s.panel}>

      {/* ── SQL Preview ── */}
      <div style={s.section}>
        <div style={s.sectionTitle}>// generated sql</div>
        <div style={s.sqlBox}>
          {sql
            ? <pre style={s.sqlPre}>{formatSQL(sql)}</pre>
            : <span style={s.placeholder}>awaiting query...</span>
          }
        </div>
      </div>

      {/* ── Pipeline Logs ── */}
      <div style={{ ...s.section, flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={s.sectionTitle}>
          // pipeline logs
          {isLoading && <span style={s.liveTag}> ● LIVE</span>}
        </div>
        <div ref={logRef} style={s.logBox}>
          {logs.length === 0
            ? <span style={s.placeholder}>no logs yet...</span>
            : logs.map((log, i) => <LogLine key={i} line={log} index={i} />)
          }
        </div>
      </div>

      {/* ── Schema ── */}
      <div style={s.section}>
        <div style={s.sectionTitle}>// schema</div>
        <div style={s.schemaBox}>
          {SCHEMA.map(t => (
            <div key={t.name} style={s.schemaTable}>
              <div style={s.tableName}>▸ {t.name}</div>
              {t.cols.map(col => (
                <div key={col} style={s.colName}>{col}</div>
              ))}
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}

function LogLine({ line, index }) {
  const isStep    = line.startsWith('Step')
  const isError   = line.toLowerCase().includes('error')
  const isDone    = line.includes('[done]')
  const isInit    = line.includes('[init]')

  const color =
    isError ? '#ff4444' :
    isDone  ? '#00ff41' :
    isStep  ? '#00cc33' :
    isInit  ? '#00aa33' : '#006600'

  return (
    <div style={{ ...s.logLine, color, animationDelay: `${index * 20}ms` }}>
      {line}
    </div>
  )
}

/* Very lightweight SQL keyword highlighter */
function formatSQL(sql) {
  const keywords = ['SELECT','FROM','WHERE','JOIN','LEFT','INNER','ON','GROUP BY',
                    'ORDER BY','HAVING','LIMIT','AS','AND','OR','IN','LIKE',
                    'COUNT','AVG','SUM','MAX','MIN','DISTINCT','BY']
  let out = sql
  keywords.forEach(kw => {
    out = out.replace(
      new RegExp(`\\b(${kw})\\b`, 'gi'),
      `\x1b[kw]${kw}\x1b[/kw]`
    )
  })
  return out
    .split('\x1b[kw]')
    .flatMap((part, i) => {
      if (i === 0) return [part]
      const [kw, rest] = part.split('\x1b[/kw]')
      return [<span key={i} style={{ color: '#00ff41', fontWeight: 600 }}>{kw}</span>, rest]
    })
}

const s = {
  panel: {
    display:       'flex',
    flexDirection: 'column',
    background:    '#000',
    overflow:      'hidden',
  },
  section: {
    borderBottom: '1px solid #002200',
  },
  sectionTitle: {
    fontSize:     10,
    color:        '#005500',
    letterSpacing: 2,
    padding:      '5px 12px',
    borderBottom: '1px solid #001a00',
    background:   '#000',
    display:      'flex',
    alignItems:   'center',
  },
  liveTag: {
    color:     '#00ff41',
    fontSize:  10,
    marginLeft: 6,
    animation: 'pulse 1s infinite',
  },
  sqlBox: {
    padding:   '10px 12px',
    minHeight: 60,
    maxHeight: 130,
    overflowY: 'auto',
    background:'#000',
  },
  sqlPre: {
    fontFamily: 'inherit',
    fontSize:   11,
    color:      '#00aa44',
    whiteSpace: 'pre-wrap',
    wordBreak:  'break-word',
    lineHeight: 1.6,
  },
  placeholder: { color: '#003300', fontSize: 11, fontStyle: 'italic' },
  logBox: {
    flex:      1,
    overflowY: 'auto',
    padding:   '8px 12px',
    maxHeight: 200,
  },
  logLine: {
    fontSize:    10,
    lineHeight:  1.7,
    whiteSpace:  'pre-wrap',
    wordBreak:   'break-all',
    letterSpacing: 0.3,
  },
  schemaBox: {
    padding:   '8px 12px',
    maxHeight: 190,
    overflowY: 'auto',
  },
  schemaTable: { marginBottom: 10 },
  tableName: { color: '#00ff41', fontSize: 11, fontWeight: 600, marginBottom: 3 },
  colName:   { color: '#005500', fontSize: 10, paddingLeft: 10, lineHeight: 1.6 },
}