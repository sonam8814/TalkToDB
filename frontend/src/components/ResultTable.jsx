export default function ResultTable({ rows }) {
  if (!rows || rows.length === 0) {
    return <div style={s.empty}>// no rows returned</div>
  }

  const cols = Object.keys(rows[0])

  return (
    <div style={s.wrapper}>
      <table style={s.table}>
        <thead>
          <tr>
            {cols.map(col => (
              <th key={col} style={s.th}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={i % 2 === 0 ? s.trEven : s.trOdd}>
              {cols.map(col => (
                <td key={col} style={s.td}>
                  {formatCell(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={s.footer}>// {rows.length} row{rows.length !== 1 ? 's' : ''}</div>
    </div>
  )
}

function formatCell(val) {
  if (val === null || val === undefined) return <span style={{ color: '#003300' }}>NULL</span>
  if (typeof val === 'number') {
    if (val > 1000 && Number.isInteger(val)) {
      return val.toLocaleString()   // salary: 142,000
    }
    if (!Number.isInteger(val)) {
      return val.toFixed(1)         // rating: 4.8
    }
  }
  return String(val)
}

const s = {
  wrapper: { overflowX: 'auto', marginTop: 4 },
  table: {
    borderCollapse: 'collapse',
    width:          '100%',
    fontSize:       11,
  },
  th: {
    border:       '1px solid #004400',
    padding:      '4px 12px',
    background:   '#001a00',
    color:        '#00ff41',
    textAlign:    'left',
    textTransform:'uppercase',
    fontSize:     10,
    letterSpacing: 1.5,
    whiteSpace:   'nowrap',
  },
  td: {
    border:   '1px solid #002800',
    padding:  '3px 12px',
    color:    '#00cc33',
    whiteSpace: 'nowrap',
  },
  trEven: { background: '#000' },
  trOdd:  { background: '#020d02' },
  empty:  { color: '#004400', fontSize: 11, fontStyle: 'italic', marginTop: 4 },
  footer: { color: '#004400', fontSize: 10, marginTop: 5 },
}