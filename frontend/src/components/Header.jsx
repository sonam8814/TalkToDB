export default function Header({ health, onClear }) {
  const statusColor =
    health?.status === 'ok'          ? '#00ff41' :
    health?.status === 'unreachable' ? '#ff3333' : '#ffb000'

  const statusLabel =
    health?.status === 'ok'          ? 'ONLINE' :
    health?.status === 'unreachable' ? 'OFFLINE' : 'CONNECTING'

  return (
    <header style={s.header}>
      <div style={s.left}>
        <span style={s.logo}>[ DB-ORACLE ]</span>
        <span style={s.sub}>HR · NATURAL LANGUAGE · SQL AGENT</span>
      </div>

      <div style={s.right}>
        {health && (
          <>
            <Chip label="MODEL"    value={health.model    || 'llama3'} />
            <Chip label="DB"       value={health.database === 'ok' ? 'OK' : 'ERR'} />
            <Chip label="CHROMA"   value={health.chroma?.startsWith('ok') ? 'OK' : 'ERR'} />
          </>
        )}
        <div style={{ ...s.status, color: statusColor }}>
          <span style={{ ...s.dot, background: statusColor }} />
          {statusLabel}
        </div>
        <button style={s.clearBtn} onClick={onClear} title="Clear terminal">
          [CLR]
        </button>
      </div>
    </header>
  )
}

function Chip({ label, value }) {
  const isErr = value === 'ERR'
  return (
    <div style={s.chip}>
      <span style={s.chipLabel}>{label}</span>
      <span style={{ ...s.chipVal, color: isErr ? '#ff3333' : '#00cc33' }}>{value}</span>
    </div>
  )
}

const s = {
  header: {
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    padding:        '7px 16px',
    background:     '#000',
    borderBottom:   '1px solid #003300',
    userSelect:     'none',
  },
  left: { display: 'flex', alignItems: 'center', gap: 14 },
  logo: { fontSize: 14, fontWeight: 700, letterSpacing: 3, color: '#00ff41' },
  sub:  { fontSize: 10, color: '#004400', letterSpacing: 2 },
  right:{ display: 'flex', alignItems: 'center', gap: 10 },
  chip: {
    display:    'flex',
    gap:        5,
    fontSize:   10,
    letterSpacing: 1,
    padding:    '2px 7px',
    border:     '1px solid #003300',
    background: '#000',
  },
  chipLabel: { color: '#005500' },
  chipVal:   { fontWeight: 700 },
  status: {
    display:    'flex',
    alignItems: 'center',
    gap:        6,
    fontSize:   11,
    letterSpacing: 1,
  },
  dot: {
    width: 6, height: 6, borderRadius: '50%',
    animation: 'pulse 1.5s ease-in-out infinite',
  },
  clearBtn: {
    background:  'transparent',
    border:      '1px solid #003300',
    color:       '#005500',
    fontFamily:  'inherit',
    fontSize:    11,
    padding:     '3px 8px',
    cursor:      'pointer',
    letterSpacing: 1,
    transition:  'all 0.15s',
  },
}