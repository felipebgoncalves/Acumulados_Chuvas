import React, { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'

const SOURCES = [
  { name: 'CEPDEC', href: 'https://defesacivil.es.gov.br/' },
  { name: 'CEMADEN', href: 'http://www2.cemaden.gov.br/mapainterativo/#' },
  { name: 'ANA', href: 'https://www.snirh.gov.br/hidrotelemetria/Mapa.aspx' },
  { name: 'INMET', href: 'https://portal.inmet.gov.br/' },
  { name: 'PMVV' , href: 'https://tempovv.vilavelha.es.gov.br/' },
]

const TABS = [
  ['painel', 'Painel principal'],
  ['lista', 'Lista de acumulados'],
  ['geral', 'Lista geral'],
  ['fontes', 'Status das fontes'],
]

function mm(value) {
  return `${Number(value || 0).toFixed(2)} mm`
}

function dateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function colorFor(mmValue) {
  if (mmValue > 20) return '#d45243'
  if (mmValue > 10) return '#db8543'
  return '#4296c0'
}

function getSource(record) {
  return record['Instituição'] || record.Fonte || '—'
}

// Limites com margem ao redor dos municípios extremos do Espírito Santo.
const ES_BOUNDS = [[-21.35, -42.05], [-17.9, -39.55]]

function RainMap({ records }) {
  const mapped = records.filter((r) => r.Latitude != null && r.Longitude != null && Number.isFinite(Number(r.Latitude)) && Number.isFinite(Number(r.Longitude)))
  return (
    <div className="map-shell">
      <MapContainer bounds={ES_BOUNDS} boundsOptions={{ padding: [12, 12] }} zoomSnap={0.25} scrollWheelZoom={false} className="map" aria-label="Mapa de acumulados de chuva no Espírito Santo">
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {mapped.map((row, index) => (
          <CircleMarker key={`${row['Município']}-${index}`} center={[Number(row.Latitude), Number(row.Longitude)]} radius={8} pathOptions={{ color: '#fff', weight: 2, fillColor: colorFor(row.Prec_mm), fillOpacity: 1 }}>
            <Popup>
              <strong>{row['Município']}</strong><br />
              Acumulado 24h: <strong>{mm(row.Prec_mm)}</strong><br />
              Fonte: {getSource(row)}<br />
              Estação: {row['Estação'] || '—'}<br />
              Referência: {row.DataHoraReferencia || '—'}
              {row['Observação'] && <><br /><strong>Atenção:</strong> {row['Observação']}</>}
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
      <div className="map-legend">
        <strong>Acumulado 24h</strong>
        <span><i style={{ background: '#4296c0' }} /> até 10 mm</span>
        <span><i style={{ background: '#db8543' }} /> 10 a 20 mm</span>
        <span><i style={{ background: '#d45243' }} /> acima de 20 mm</span>
      </div>
    </div>
  )
}

function StatusPill({ status }) {
  const key = status === 'OK' ? 'ok' : status === 'Parcial' ? 'partial' : 'fail'
  return <span className={`status-pill ${key}`}><span className="status-dot" />{status}</span>
}

function Ranking({ rows, selectedSources, onToggle, search, onSearch }) {
  const sources = [...new Set(rows.map(getSource))].sort()
  const filtered = rows.filter((row) => selectedSources.includes(getSource(row)) && row['Município'].toLocaleLowerCase('pt-BR').includes(search.toLocaleLowerCase('pt-BR')))
  return (
    <section className="card ranking-card">
      <div className="card-heading"><div><span className="eyebrow">DESTAQUES POR MUNICÍPIO</span><h2>Ranking de acumulados</h2></div><span className="count-badge">{filtered.length} municípios</span></div>
      <div className="controls">
        <div><label className="field-label">Filtrar por fonte</label><div className="source-chips">{sources.map((source) => <button type="button" key={source} className={`chip ${selectedSources.includes(source) ? 'active' : ''}`} onClick={() => onToggle(source)} aria-pressed={selectedSources.includes(source)}>{source}</button>)}</div></div>
        <label><span className="field-label">Buscar município</span><input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Digite o nome do município" /></label>
      </div>
      <div className="table-wrap"><table><thead><tr><th>#</th><th>Município</th><th>Acumulado 24h</th><th>Fonte</th></tr></thead><tbody>{filtered.map((row, index) => <tr key={`${row['Município']}-${index}`}><td className="rank-number">{String(index + 1).padStart(2, '0')}</td><td className="city-cell">{row['Município']}{row['Observação'] && <small title={row['Observação']}>Leitura parcial</small>}</td><td className="amount">{mm(row.Prec_mm)}</td><td><span className="source-tag">{getSource(row)}</span></td></tr>)}</tbody></table>{filtered.length === 0 && <p className="empty-state">Nenhum registro para este filtro.</p>}</div>
    </section>
  )
}

function RecordList({ rows, general = false }) {
  const [copied, setCopied] = useState(false)
  const lines = rows.map((row, index) => `${index + 1}. ${row['Município']} - ${mm(row.Prec_mm)}${general ? ` - ${getSource(row)}` : ''}`)
  const heading = 'Acumulados de chuva em 24h:'
  const listText = `${heading}\n${lines.join('\n')}`

  async function copyList() {
    try {
      await navigator.clipboard.writeText(`*${heading}*\n${lines.join('\n')}`)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2500)
    } catch {
      setCopied(false)
    }
  }

  if (!general) {
    return <section className="card list-card"><div className="card-heading"><div><span className="eyebrow">ÚLTIMAS 24 HORAS</span><h2>Lista de acumulados</h2></div><span className="count-badge">{rows.length} municípios</span></div><p className="section-description">Maior acumulado registrado em cada município.</p><div className="copy-toolbar"><button type="button" onClick={copyList} disabled={rows.length === 0}>{copied ? 'Copiado!' : 'Copiar para WhatsApp'}</button></div>{rows.length > 0 ? <pre className="copyable-list">{listText}</pre> : <p className="empty-state">Sem acumulados de chuva no momento.</p>}</section>
  }
  return <section className="card list-card"><div className="card-heading"><div><span className="eyebrow">ÚLTIMAS 24 HORAS</span><h2>{general ? 'Lista de acumulados — geral' : 'Lista de acumulados'}</h2></div><span className="count-badge">{general ? 'até 60 registros' : `${rows.length} municípios`}</span></div><p className="section-description">{general ? 'Todas as medições disponíveis, inclusive múltiplas estações e fontes no mesmo município.' : 'Maior acumulado registrado em cada município.'}</p><ol className="records-list">{rows.map((row, index) => <li key={`${getSource(row)}-${row['Município']}-${index}`}><span className="list-position">{String(index + 1).padStart(2, '0')}</span><span className="list-city">{row['Município']}{row['Observação'] && <small>{row['Observação']}</small>}</span><strong>{mm(row.Prec_mm)}</strong>{general && <span className="source-tag">{getSource(row)}</span>}</li>)}</ol>{rows.length === 0 && <p className="empty-state">Sem acumulados de chuva no momento.</p>}</section>
}

function SourceStatus({ rows }) {
  return <section className="card status-card"><div className="card-heading"><div><span className="eyebrow">TRANSPARÊNCIA DA COLETA</span><h2>Status das fontes</h2></div><span className="count-badge">{rows.length} fontes</span></div><div className="status-grid">{rows.map((row) => <article className="status-item" key={row.Fonte}><div className="status-top"><h3>{row.Fonte}</h3><StatusPill status={row.Status} /></div><div className="status-meta"><span><b>{row.Registros}</b> registros</span><span>Atualizado: {row['Última atualização']}</span><span>Tentativa: {row['Última tentativa']}</span><span>Duração: {row['Duração (s)']} s</span></div><p>{row.Mensagem}</p></article>)}</div></section>
}

function App() {
  const [response, setResponse] = useState({ loading: true, data: null, error: null })
  const [tab, setTab] = useState('painel')
  const [search, setSearch] = useState('')
  const [selectedSources, setSelectedSources] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const result = await fetch('/api/dashboard')
        if (!result.ok) throw new Error(`API indisponível (HTTP ${result.status})`)
        const json = await result.json()
        if (active) setResponse(json)
      } catch (error) {
        if (active) setResponse((previous) => ({ ...previous, error: error.message, loading: false }))
      }
    }
    poll()
    const timer = window.setInterval(poll, 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  const data = response.data
  const ranking = data?.ranking || []
  const allSources = useMemo(() => [...new Set(ranking.map(getSource))].sort(), [ranking])
  const activeSources = selectedSources ?? allSources
  const partial = data?.sources?.filter((row) => row.Status === 'Parcial') || []

  async function refresh() {
    setRefreshing(true)
    try {
      await fetch('/api/refresh', { method: 'POST' })
      const result = await fetch('/api/dashboard')
      if (result.ok) setResponse(await result.json())
    } catch { /* A atualização automática continuará tentando. */ }
    finally { setRefreshing(false) }
  }

  function toggleSource(source) {
    setSelectedSources((previous) => {
      const current = previous ?? allSources
      return current.includes(source) ? current.filter((name) => name !== source) : [...current, source]
    })
  }

  return <div className="site">
    <header className="site-header"><div className="container header-inner"><div className="brand"><img src="/assets/logo_cepdec.png" alt="Símbolo da CEPDEC" /><span className="brand-word">cepdec</span><span className="brand-divider" /><span className="brand-subtitle">ESPÍRITO SANTO<br /><strong>MONITORAMENTO DE CHUVAS</strong></span></div><div className="header-right"><span className="live-indicator"><i /> ATUALIZAÇÃO CONTÍNUA</span><button className="refresh-button" type="button" onClick={refresh} disabled={refreshing || response.loading}>{refreshing ? 'Atualizando…' : '↻ Atualizar dados'}</button></div></div></header>
    <main className="container">
      <section className="hero"><div><span className="eyebrow hero-eyebrow"><span className="eyebrow-line" /> OBSERVATÓRIO PLUVIOMÉTRICO · ESPÍRITO SANTO</span><h1>Acumulados de chuva<br /><em>nas últimas 24 horas.</em></h1><p>Monitoramento integrado das estações pluviométricas do Espírito Santo. Visualize os maiores acumulados, acompanhe cada município e consulte a situação das fontes em um só lugar.</p></div><div className="hero-symbol"><img src="/assets/logo_cepdec.png" alt="" /></div></section>
      <div className="source-strip"><span>FONTES DE DADOS</span><div>{SOURCES.map((source) => <a key={source.name} href={source.href} target="_blank" rel="noreferrer">{source.name} <span>↗</span></a>)}</div></div>
      {response.error && <div className="banner error" role="alert">{response.error}</div>}
      {response.loading && <div className="banner loading" role="status">{data ? 'Atualizando leituras; os últimos dados continuam visíveis.' : 'Buscando leituras das fontes. A primeira coleta pode levar alguns minutos…'}</div>}
      {partial.length > 0 && <div className="banner warning">Dados parciais em {partial.map((row) => row.Fonte).join(', ')}. Os acumulados disponíveis foram mantidos; consulte a aba “Status das fontes”.</div>}
      <section className="metric-grid" aria-label="Resumo dos acumulados"><div className="metric"><span>MAIOR ACUMULADO</span><strong>{data ? mm(data.summary.maximum_mm) : '—'}</strong><small>registrado em 24h</small></div><div className="metric"><span>MUNICÍPIO DESTAQUE</span><strong>{data?.summary.top_city || '—'}</strong><small>maior volume observado</small></div><div className="metric"><span>MUNICÍPIOS COM CHUVA</span><strong>{data?.summary.rainy_cities ?? '—'}</strong><small>com registro positivo</small></div><div className="metric"><span>FONTES ATIVAS</span><strong>{data?.summary.active_sources ?? '—'}<small> / 5</small></strong><small>coletas com dados</small></div></section>
      <div className="dashboard-meta"><span><i /> Atualizado em {dateTime(data?.updated_at)}</span><span>CHUVA · ESPÍRITO SANTO</span></div>
      <nav className="tabs" aria-label="Seções do painel">{TABS.map(([key, label]) => <button key={key} type="button" className={tab === key ? 'selected' : ''} onClick={() => setTab(key)} aria-current={tab === key ? 'page' : undefined}>{label}</button>)}</nav>
      {tab === 'painel' && <div className="main-grid"><section className="card map-card"><div className="card-heading"><div><span className="eyebrow">VISÃO GEOGRÁFICA</span><h2>Mapa de acumulados</h2></div><span className="map-note">● estações com chuva</span></div><RainMap records={ranking} /></section><Ranking rows={ranking} selectedSources={activeSources} onToggle={toggleSource} search={search} onSearch={setSearch} /></div>}
      {tab === 'lista' && <RecordList rows={ranking} />}
      {tab === 'geral' && <RecordList rows={data?.general || []} general />}
      {tab === 'fontes' && <SourceStatus rows={data?.sources || []} />}
    </main>
    <footer className="site-footer"><div className="container footer-inner"><span>CEPDEC · ESPÍRITO SANTO</span><span>Dados de múltiplas fontes · Acumulados das últimas 24 horas</span><a className="developer-credit" href="https://github.com/felipebgoncalves" target="_blank" rel="noreferrer">Desenvolvido por @felipebgoncalves</a></div></footer>
  </div>
}

export default App
