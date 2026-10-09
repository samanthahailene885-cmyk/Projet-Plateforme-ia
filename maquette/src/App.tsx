import { Fragment, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { deskCall, ensureAdminSession, enterSession, leaveSession, openSession, showSpace } from './work'

type Role = 'admin' | 'employee'
type Go = (page: string) => void

const adminPages = ['dashboard', 'employees', 'projects', 'tasks', 'todos', 'reports', 'permissions', 'documents', 'alerts', 'messaging', 'notifications', 'assistant', 'ai-reports', 'demo', 'settings']
const employeePages = ['dashboard', 'projects', 'tasks', 'todos', 'reports', 'permissions', 'messaging', 'notifications', 'assistant', 'profile']

const people = [
  { id: 'zaina', name: 'Zaina Nouzou', role: 'Graphiste', service: 'Création', initials: 'ZN', tone: '', status: 'Actif', todo: '4 / 5 tâches', seen: 'Il y a 8 min', online: true, reports: 8, presence: '92 %' },
  { id: 'paul', name: 'Paul Mbia', role: 'Chef de projet', service: 'Production', initials: 'PM', tone: 'tone-sky', status: 'Actif', todo: '3 / 4 tâches', seen: 'Il y a 24 min', online: false, reports: 6, presence: '88 %' },
  { id: 'amina', name: 'Amina Diallo', role: 'Community manager', service: 'Communication', initials: 'AD', tone: 'tone-amber', status: 'En congé', todo: 'Non renseignée', seen: '3 oct. 2026', online: false, reports: 5, presence: '80 %' },
  { id: 'lucas', name: 'Lucas Nguema', role: 'Développeur web', service: 'Digital', initials: 'LN', tone: 'tone-green', status: 'Actif', todo: '5 / 6 tâches', seen: 'Il y a 1 h', online: true, reports: 7, presence: '95 %' },
]

type ProjectFile = { name: string; kind: string; size: string; url?: string; html?: string }
type LeaveRequest = { id: string; who: string; type: string; dates: string; motif: string; status: string; file?: ProjectFile; seen?: boolean }
type ProjectCard = { id: string; name: string; client: string; owner: string; progress: number; status: string; due: string; start?: string; description?: string; priority?: string; members?: string[]; team?: { name: string; initials: string }[]; file?: ProjectFile; files?: ProjectFile[] }
type AssignedTask = { id: string; title: string; project: string; projectId: string; who: string; whoId: string; priority: string; tone: string; due: string; status: string; docs?: { name: string; url: string }[]; resultUrl?: string; resultName?: string }

const projects: ProjectCard[] = [
  { id: 'tiko', name: 'Campagne Tiko Transit', client: 'Tiko Transit Logistics', owner: 'Paul Mbia', progress: 72, status: 'En cours', due: '18 oct. 2026', members: ['paul', 'zaina'] },
  { id: 'hotel', name: 'Identité visuelle Hôtel Baie', client: 'Hôtel de la Baie', owner: 'Zaina Nouzou', progress: 40, status: 'En cours', due: '11 oct. 2026', members: ['zaina'] },
  { id: 'nova', name: 'Lancement produit Nova', client: 'Nova Cosmetics', owner: 'Amina Diallo', progress: 100, status: 'Terminé', due: '28 sept. 2026', members: ['amina'] },
]

function priorityTone(priority: string) {
  if (priority === 'Urgente') return 'urgent'
  if (priority === 'Élevée') return 'high'
  return 'mid'
}

function needsProof(motif: string) {
  const value = motif.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  return value.includes('maladie') || value.includes('arret')
}

function formatLeaveDates(from: string, to: string) {
  const start = formatFrenchDate(from)
  const end = to ? formatFrenchDate(to) : ''
  if (!start) return 'Non renseignée'
  return end && end !== start ? `${start} – ${end}` : start
}

function formatFrenchDate(iso: string) {
  const months = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
  const [year, month, day] = iso.split('-').map(Number)
  if (!year || !month || !day) return iso
  return `${day} ${months[month - 1]} ${year}`
}

const zaina = {
  name: 'zaina zaina',
  first: 'zaina',
  username: 'nouzou',
  email: 'hailene@gmail.com',
  initials: 'ZZ',
  job: 'Autre',
  roleLabel: 'Employée',
  hired: '21 juillet 2026',
  photo: '/profil-zaina.jpg',
}

const zainaProjects = [
  { id: 'marenova', name: 'creationn de site de marenova', client: 'Non renseigné', owner: zaina.name, progress: 100, status: 'Terminé', due: '10 sept. 2026' },
  { id: 'analyse', name: 'analyse du site', client: 'Non renseigné', owner: zaina.name, progress: 100, status: 'Terminé', due: '22 sept. 2026' },
  { id: 'nettoyage', name: 'NETTOYAGE ET SUPPRESSION DES ANCIENNES FONCTIONNALITÉS', client: 'Non renseigné', owner: zaina.name, progress: 100, status: 'Terminé', due: '23 sept. 2026' },
]

const zainaReports: { date: string; name: string; size: string; url?: string; kind?: string }[] = [
  { date: '5 oct. 2026', name: 'TIKO_TRANSIT__LOGISTICS_1_qm2FN9H.pdf', size: '4,8 Mo', kind: 'PDF', url: '/rapports/TIKO_TRANSIT__LOGISTICS_1_qm2FN9H.pdf' },
  { date: '2 oct. 2026', name: 'TIKO_TRANSIT__LOGISTICS_1.pdf', size: '4,8 Mo', kind: 'PDF', url: '/rapports/TIKO_TRANSIT__LOGISTICS_1.pdf' },
  { date: '23 sept. 2026', name: 'Rapport sans fichier', size: '—' },
  { date: '3 sept. 2026', name: 'Rapport sans fichier', size: '—' },
  { date: '22 juil. 2026', name: 'Rapport sans fichier', size: '—' },
  { date: '21 juil. 2026', name: 'Rapport sans fichier', size: '—' },
]

const zainaPermissions: LeaveRequest[] = [
  { id: 'zp1', who: zaina.name, type: 'Permission', dates: '6 sept. – 16 sept. 2026', motif: 'Rendez-vous médical', status: 'Annulée' },
  { id: 'zp2', who: zaina.name, type: 'Permission', dates: '25 sept. 2026', motif: 'Vacances', status: 'Approuvée' },
  { id: 'zp3', who: zaina.name, type: 'Congé annuel', dates: '30 sept. – 7 nov. 2026', motif: 'Vacances', status: 'Refusée' },
]

type Staff = { id: string; name: string; role: string; service: string; initials: string; tone: string; status: string; todo: string; seen: string; online: boolean; reports: number; presence: string; demo?: boolean }
type ReportFile = { id: string; person: string; name: string; kind: string; size: string; date: string; scope: string; demo?: boolean; url?: string; html?: string }
type PlanItem = { id: string; text: string; done: boolean }
type DayPlan = { personId: string; items: PlanItem[] }
const DEMO_PASSWORD = 'Demo-Racine-2026'

const reportFiles = [
  { id: 'f1', person: 'zaina', name: 'Rapport_05_octobre.pdf', kind: 'PDF', size: '1,2 Mo', date: '5 oct. 2026', scope: 'week' },
  { id: 'f2', person: 'zaina', name: 'TIKO_TRANSIT_LOGISTICS.pdf', kind: 'PDF', size: '5,0 Mo', date: '5 oct. 2026', scope: 'week' },
  { id: 'f3', person: 'zaina', name: 'Rapport_02_octobre.docx', kind: 'DOC', size: '860 Ko', date: '2 oct. 2026', scope: 'month' },
  { id: 'f4', person: 'paul', name: 'Rapport_04_octobre.pdf', kind: 'PDF', size: '980 Ko', date: '4 oct. 2026', scope: 'month' },
  { id: 'f5', person: 'lucas', name: 'Rapport_05_octobre.pdf', kind: 'PDF', size: '740 Ko', date: '5 oct. 2026', scope: 'week' },
]

function Icon({ name, size = 16 }: { name: string; size?: number }) {
  const props = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.7,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
  switch (name) {
    case 'grid':
      return <svg {...props}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg>
    case 'users':
      return <svg {...props}><circle cx="9" cy="8" r="3" /><circle cx="17" cy="9" r="2.2" /><path d="M3.5 19c.7-2.6 2.8-4 5.5-4s4.8 1.4 5.5 4" /><path d="M14.5 15.2c1.5-.2 3 .3 4 1.6.6.8 1 1.6 1.1 2.2" /></svg>
    case 'folder':
      return <svg {...props}><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2h7.5A2.5 2.5 0 0 1 21 9.5v7A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5v-9z" /></svg>
    case 'case':
      return <svg {...props}><rect x="3" y="8" width="18" height="12" rx="2" /><path d="M8 8V6.5A2.5 2.5 0 0 1 10.5 4h3A2.5 2.5 0 0 1 16 6.5V8" /><path d="M3 13h18" /></svg>
    case 'tasks':
      return <svg {...props}><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M8 12l2.2 2.2L16 9" /></svg>
    case 'list':
      return <svg {...props}><path d="M9 7h11M9 12h11M9 17h11" /><path d="M4.5 7h.01M4.5 12h.01M4.5 17h.01" /></svg>
    case 'file':
      return <svg {...props}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" /></svg>
    case 'calendar':
      return <svg {...props}><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16" /></svg>
    case 'bell':
      return <svg {...props}><path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2H4.5z" /><path d="M10 19a2 2 0 0 0 4 0" /></svg>
    case 'message':
      return <svg {...props}><path d="M5 17.5 3.5 21 8 18h9.5A2.5 2.5 0 0 0 20 15.5v-9A2.5 2.5 0 0 0 17.5 4h-11A2.5 2.5 0 0 0 4 6.5v9A2 2 0 0 0 5 17.5z" /></svg>
    case 'spark':
      return <svg {...props}><path d="M12 3l1.4 5.2L18 10l-4.6 1.8L12 17l-1.4-5.2L6 10l4.6-1.8z" /><path d="M18 14l.6 2 2 .6-2 .6-.6 2-.6-2-2-.6 2-.6z" /></svg>
    case 'database':
      return <svg {...props}><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" /><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></svg>
    case 'settings':
      return <svg {...props}><circle cx="12" cy="12" r="3" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" /></svg>
    case 'search':
      return <svg {...props}><circle cx="11" cy="11" r="6" /><path d="M20 20l-3.5-3.5" /></svg>
    case 'logout':
      return <svg {...props}><path d="M10 7V5a2 2 0 0 1 2-2h7v18h-7a2 2 0 0 1-2-2v-2" /><path d="M4 12h10M8 8l-4 4 4 4" /></svg>
    case 'plus':
      return <svg {...props}><path d="M12 5v14M5 12h14" /></svg>
    case 'eye':
      return <svg {...props}><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z" /><circle cx="12" cy="12" r="2.4" /></svg>
    case 'clip':
      return <svg {...props}><path d="M8 12.5 14.8 6a3 3 0 0 1 4.2 4.2l-8.2 8.2a4.2 4.2 0 0 1-6-6L12.5 5" /></svg>
    case 'send':
      return <svg {...props}><path d="M4 12 20 4l-6 16-2.5-6.5z" /></svg>
    case 'chevron':
      return <svg {...props}><path d="M9 6l6 6-6 6" /></svg>
    case 'clock':
      return <svg {...props}><circle cx="12" cy="12" r="8" /><path d="M12 8v5l3 2" /></svg>
    case 'alert':
      return <svg {...props}><path d="M12 4 3 19h18z" /><path d="M12 10v4M12 17h.01" /></svg>
    case 'check':
      return <svg {...props}><path d="M5 12.5 9.2 17 19 7" /></svg>
    case 'user':
      return <svg {...props}><circle cx="12" cy="8" r="3.2" /><path d="M5 19.2c1.2-3 3.5-4.5 7-4.5s5.8 1.5 7 4.5" /></svg>
    case 'shield':
      return <svg {...props}><path d="M12 3l7 3v6c0 4.2-2.8 7.4-7 9-4.2-1.6-7-4.8-7-9V6z" /><path d="M9 12l2 2 4-4" /></svg>
    case 'trend':
      return <svg {...props}><path d="M4 16l5-5 3 3 7-8" /><path d="M14 6h6v6" /></svg>
    case 'download':
      return <svg {...props}><path d="M12 4v10M8 10l4 4 4-4M5 19h14" /></svg>
    case 'sun':
      return <svg {...props}><circle cx="12" cy="12" r="3.5" /><path d="M12 2.5v2.2M12 19.3V21.5M2.5 12h2.2M19.3 12H21.5M5.1 5.1l1.6 1.6M17.3 17.3l1.6 1.6M18.9 5.1l-1.6 1.6M6.7 17.3l-1.6 1.6" /></svg>
    default:
      return null
  }
}

function Logo() {
  return (
    <div className="brand">
      <span className="brand-mark">R</span>
      <span>
        <strong>RAC<span>’</span>IN</strong>
        <small>Communication · Création · Impact</small>
      </span>
    </div>
  )
}

function Avatar({ initials, tone = '', size = '', online = false, src = '' }: { initials: string; tone?: string; size?: string; online?: boolean; src?: string }) {
  return (
    <span className={`avatar ${tone} ${size}`.trim()}>
      {src ? <img src={src} alt="" /> : initials}
      {online ? <i className="dot" /> : null}
    </span>
  )
}

function Button({ children, onClick, ghost = false, soft = false, danger = false, type = 'button' }: { children: ReactNode; onClick?: () => void; ghost?: boolean; soft?: boolean; danger?: boolean; type?: 'button' | 'submit' }) {
  return <button className={`btn${ghost ? ' ghost' : ''}${soft ? ' soft' : ''}${danger ? ' danger' : ''}`} type={type} onClick={onClick}>{children}</button>
}

function PageHeader({ kicker, title, subtitle, action }: { kicker?: string; title: string; subtitle: string; action?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        {kicker ? <p className="kicker">{kicker}</p> : null}
        <h1 className="page-title">{title}</h1>
        <p className="page-sub">{subtitle}</p>
      </div>
      {action}
    </div>
  )
}

type LiveMetrics = {
  employees_active: number
  employees_total: number
  projects_total: number
  projects_in_progress: number
  projects_completed: number
  projects_upcoming: number
  tasks_total: number
  tasks_completed: number
  tasks_completed_today: number
  tasks_in_progress: number
  tasks_not_started: number
  tasks_overdue: number
  todo_lists_today: number
  todo_lists_missing: number
  reports_submitted_today: number
  reports_missing_today: number
  pending_permissions: number
  difficulties_open: number
  alerts_active: number
}

type LiveDash = {
  authenticated: boolean
  manager_name: string
  metrics: LiveMetrics
  series: { labels: string[]; completed: number[]; in_progress: number[]; late: number[]; empty: boolean }
  donut: { total: number; empty: boolean; rows: { label: string; count: number; color: string; percent: number }[] }
  team: { rank: string; initials: string; name: string; role: string; width: string; score: string }[]
  alerts: { title: string; text: string }[]
  brief: string
}

function seriesPath(values: number[], peak: number) {
  const width = 700
  const height = 200
  const top = Math.max(peak, 1)
  if (!values.length) return ''
  return values.map((value, index) => {
    const x = values.length === 1 ? 0 : (index / (values.length - 1)) * width
    const y = height - 8 - (value / top) * (height - 24)
    return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`
  }).join(' ')
}

function csrfToken() {
  const raw = document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=')[1] ?? ''
  return decodeURIComponent(raw)
}

function AdminDashboard({ onNavigate }: { onNavigate: Go }) {
  const todayLabel = new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
  const [live, setLive] = useState<LiveDash | null>(null)
  const [notice, setNotice] = useState('')
  const [reportState, setReportState] = useState<'idle' | 'loading' | 'done'>('idle')
  const [synthesis, setSynthesis] = useState('')
  const [synthesisError, setSynthesisError] = useState('')
  useEffect(() => {
    let cancel = false
    function load() {
      fetch('/dashboard/indicateurs.json', { credentials: 'same-origin' })
        .then(async (response) => {
          if (!response.ok) throw new Error('unavailable')
          return response.json() as Promise<LiveDash>
        })
        .then((data) => { if (!cancel) setLive(data) })
        .catch(() => {
          if (!cancel) setNotice('Les indicateurs viennent de la base. Connectez-vous en responsable sur la plateforme de données pour les afficher. Aucun chiffre n’est inventé.')
        })
    }
    load()
    function onVisible() { if (document.visibilityState === 'visible') load() }
    document.addEventListener('visibilitychange', onVisible)
    const timer = window.setInterval(load, 15000)
    return () => { cancel = true; document.removeEventListener('visibilitychange', onVisible); window.clearInterval(timer) }
  }, [])
  const metrics = live?.metrics
  const kpis = [
    { icon: 'users', tone: 'blue', label: 'Employés actifs', value: String(metrics?.employees_active ?? 0), detail: `${metrics?.employees_total ?? 0} au total`, page: 'employees', danger: false },
    { icon: 'folder', tone: 'violet', label: 'Projets', value: String(metrics?.projects_total ?? 0), detail: `${metrics?.projects_completed ?? 0} terminé${(metrics?.projects_completed ?? 0) > 1 ? 's' : ''} · ${metrics?.projects_in_progress ?? 0} en cours`, page: 'projects', danger: false },
    { icon: 'check', tone: 'green', label: 'Tâches terminées', value: String(metrics?.tasks_completed ?? 0), detail: `${metrics?.tasks_in_progress ?? 0} en cours · ${metrics?.tasks_not_started ?? 0} non commencées`, page: 'tasks', danger: false },
    { icon: 'clock', tone: 'orange', label: 'Terminées aujourd’hui', value: String(metrics?.tasks_completed_today ?? 0), detail: `${metrics?.tasks_total ?? 0} tâches au total`, page: 'tasks', danger: false },
    { icon: 'file', tone: 'cyan', label: 'Rapports reçus', value: `${metrics?.reports_submitted_today ?? 0}/${metrics?.employees_active ?? 0}`, detail: `${metrics?.reports_missing_today ?? 0} non soumis`, page: 'reports', danger: false },
    { icon: 'alert', tone: 'red', label: 'Alertes actives', value: String(metrics?.alerts_active ?? 0), detail: `${metrics?.tasks_overdue ?? 0} en retard`, page: 'alerts', danger: true },
  ]
  const series = live?.series
  const peak = Math.max(0, ...(series?.completed ?? []), ...(series?.in_progress ?? []), ...(series?.late ?? []))
  const axis = [1, 0.75, 0.5, 0.25, 0].map((step) => String(Math.round(Math.max(peak, 4) * step)))
  const slices = (live?.donut.rows ?? []).filter((row) => row.count > 0)
  let cursor = 0
  const gradient = slices.length
    ? `conic-gradient(${slices.map((row) => {
        const start = cursor
        cursor += row.percent
        return `${row.color} ${start}% ${cursor}%`
      }).join(',')})`
    : '#e8edf4'
  const firstName = (live?.manager_name || '').split(' ')[0] || ''
  async function generateSynthesis() {
    setReportState('loading')
    setSynthesisError('')
    try {
      const response = await fetch('/reports/synthese/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrfToken() },
        body: new URLSearchParams({ date: new Date().toISOString().slice(0, 10) }),
      })
      const data = await response.json().catch(() => null) as { ok?: boolean; synthesis?: string; error?: string } | null
      if (!response.ok || !data?.ok || !data.synthesis) {
        setSynthesisError(data?.error || 'Le service IA est momentanément indisponible.')
        setReportState('idle')
        return
      }
      setSynthesis(data.synthesis)
      setReportState('done')
    } catch {
      setSynthesisError('Le service IA est momentanément indisponible.')
      setReportState('idle')
    }
  }
  return (
    <section className="africa">
      <div className="af-head">
        <div>
          <span className="af-eyebrow">{todayLabel}</span>
          <h1>Bonjour{firstName ? `, ${firstName}` : ''}</h1>
          <p>Voici ce qui se passe dans votre entreprise aujourd’hui.</p>
        </div>
        <button className={`af-primary${reportState === 'done' ? ' done' : ''}`} type="button" disabled={reportState === 'loading'} onClick={() => { void generateSynthesis() }}>
          <span className={reportState === 'loading' ? 'af-spin' : ''}><Icon name={reportState === 'done' ? 'check' : 'spark'} size={16} /></span>
          {reportState === 'loading' ? 'Analyse des rapports...' : reportState === 'done' ? 'Synthèse générée' : 'Générer la synthèse IA'}
        </button>
      </div>
      {notice ? <p className="lp-note">{notice}</p> : null}

      <div className="af-kpis">
        {kpis.map((item) => (
          <button className="af-kpi" type="button" key={item.label} onClick={() => onNavigate(item.page)}>
            <div className="af-kpi-top">
              <span className={`af-kpi-icon ${item.tone}`}><Icon name={item.icon} size={16} /></span>
              <span className="af-kpi-label">{item.label}</span>
            </div>
            <strong>{item.value}</strong>
            <small><b className={item.danger ? 'danger' : ''}>{item.danger ? <Icon name="alert" size={12} /> : null}{item.detail}</b></small>
          </button>
        ))}
      </div>

      <div className="af-grid">
        <article className="af-panel af-wide">
          <div className="af-panel-head">
            <div>
              <h2>Évolution des tâches</h2>
              <p>Comptes réels des 7 derniers jours</p>
            </div>
            <div className="af-legend">
              <span><i className="blue" /> Terminées</span>
              <span><i className="green" /> En cours</span>
              <span><i className="red" /> En retard</span>
              <em>7 derniers jours</em>
            </div>
          </div>
          <div className="af-chart">
            <div className="af-ylabs">{axis.map((label, index) => <span key={index}>{label}</span>)}</div>
            <div className="af-gridlines"><span /><span /><span /><span /><span /></div>
            <svg viewBox="0 0 700 200" preserveAspectRatio="none" role="img" aria-label="Évolution des tâches">
              <path className="af-line blue" d={seriesPath(series?.completed ?? [], peak)} />
              <path className="af-line green" d={seriesPath(series?.in_progress ?? [], peak)} />
              <path className="af-line red" d={seriesPath(series?.late ?? [], peak)} />
            </svg>
            <div className="af-xlabs">{(series?.labels ?? ['—']).map((label) => <span key={label}>{label}</span>)}</div>
          </div>
        </article>

        <AgencyCalendar />

        <article className="af-panel">
          <div className="af-panel-head">
            <div>
              <h2>Répartition globale</h2>
            </div>
          </div>
          <div className="af-donut-row">
            <div className="af-donut" style={{ background: gradient }}><div><strong>{live?.donut.total ?? 0}</strong><small>PROJETS</small></div></div>
            <div className="af-donut-legend">
              {(live?.donut.rows ?? []).filter((row) => ['En cours', 'Terminés', 'À venir', 'En retard'].includes(row.label)).map((row) => (
                <div key={row.label}><i style={{ background: row.color }} /><span>{row.label}<small>{row.count} projet{row.count > 1 ? 's' : ''}</small></span><b>{row.percent}%</b></div>
              ))}
              {live?.donut.empty || !live ? <div><span>Aucune tâche de répartition<small>0 projet enregistré</small></span></div> : null}
            </div>
          </div>
        </article>

        <article className="af-ai">
          <div className="af-ai-head">
            <span className="af-ai-icon"><Icon name="spark" size={18} /></span>
            <div>
              <small>Réel</small>
              <h2>Synthèse intelligente</h2>
            </div>
            <em>{synthesis ? 'Généré par IA' : 'Faits enregistrés'}</em>
          </div>
          <p>{synthesisError || synthesis || live?.brief || 'Aucune activité enregistrée pour cette date.'}</p>
          <div className="af-ai-stats">
            <span><strong>{metrics?.todo_lists_today ?? 0}</strong><small>Todo Lists du jour</small></span>
            <span><strong>{metrics?.todo_lists_missing ?? 0}</strong><small>Todo Lists manquantes</small></span>
            <span><strong>{metrics?.difficulties_open ?? 0}</strong><small>Difficultés ouvertes</small></span>
          </div>
          <button type="button" onClick={() => onNavigate('assistant')}>Voir l’analyse complète <Icon name="chevron" size={14} /></button>
        </article>

        <article className="af-panel af-team">
          <div className="af-panel-head">
            <div>
              <h2>Performance des équipes</h2>
              <p>Tâches terminées ce mois</p>
            </div>
            <button type="button" onClick={() => onNavigate('employees')}>Voir tous <Icon name="chevron" size={14} /></button>
          </div>
          <div className="af-team-list">
            {(live?.team ?? []).map((person, index) => (
              <div className="af-person" key={person.name}>
                <span className="af-rank">{person.rank}</span>
                <span className={`af-chip ${['violet', '', 'orange', 'green'][index] ?? ''}`}>{person.initials}</span>
                <span className="af-who"><strong>{person.name}</strong><small>{person.role}</small></span>
                <span className="af-bar"><i style={{ width: person.width }} /></span>
                <b>{person.score}</b>
              </div>
            ))}
            {live && live.team.length === 0 ? <p className="muted">Aucune tâche terminée ce mois.</p> : null}
          </div>
        </article>

        <article className="af-panel af-alerts">
          <div className="af-panel-head">
            <div>
              <h2>Centre d’alertes</h2>
              <p>Éléments nécessitant votre attention</p>
            </div>
            <button type="button" onClick={() => onNavigate('alerts')}>Tout voir <Icon name="chevron" size={14} /></button>
          </div>
          {(live?.alerts ?? []).map((alert) => (
            <button className="af-alert" type="button" key={`${alert.title}-${alert.text}`} onClick={() => onNavigate('alerts')}>
              <span className="red"><Icon name="alert" size={14} /></span>
              <span><strong>{alert.title}</strong><small>{alert.text}</small></span>
            </button>
          ))}
          {live && live.alerts.length === 0 ? <p className="muted">Aucune alerte active.</p> : null}
          {!live && !notice ? <p className="muted">Calcul des indicateurs...</p> : null}
        </article>
      </div>
    </section>
  )
}

function AgencyCalendar() {
  const today = new Date()
  const [cursor, setCursor] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1))
  const year = cursor.getFullYear()
  const month = cursor.getMonth()
  const lead = (new Date(year, month, 1).getDay() + 6) % 7
  const count = new Date(year, month + 1, 0).getDate()
  const cells = [...Array(lead).fill(0), ...Array.from({ length: count }, (_, index) => index + 1)]
  while (cells.length % 7) cells.push(0)
  const title = cursor.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
  function isToday(day: number) {
    return day === today.getDate() && month === today.getMonth() && year === today.getFullYear()
  }
  return (
    <article className="af-panel af-cal">
      <div className="af-panel-head">
        <div>
          <h2>Calendrier</h2>
          <p>Vue d’ensemble de l’équipe</p>
        </div>
      </div>
      <div className="af-cal-nav">
        <button type="button" aria-label="Mois précédent" onClick={() => setCursor(new Date(year, month - 1, 1))}><Icon name="chevron" size={14} /></button>
        <strong>{title}</strong>
        <button type="button" aria-label="Mois suivant" onClick={() => setCursor(new Date(year, month + 1, 1))}><Icon name="chevron" size={14} /></button>
      </div>
      <div className="af-cal-grid af-cal-week">
        {['L', 'M', 'M', 'J', 'V', 'S', 'D'].map((label, index) => <span key={`${label}-${index}`}>{label}</span>)}
      </div>
      <div className="af-cal-grid">
        {cells.map((day, index) => (
          <span key={index} className={day && isToday(day) ? 'today' : ''}>{day || ''}</span>
        ))}
      </div>
    </article>
  )
}


function statusClass(status: string) {
  if (status === 'Actif' || status === 'Terminée' || status === 'Terminé' || status === 'Approuvée' || status === 'Soumis') return 'ok'
  if (status === 'En congé' || status === 'En attente') return 'leave'
  if (status === 'En retard' || status === 'Critique' || status === 'Refusée') return 'late'
  return 'wait'
}

function EmployeeDashboard({ onNavigate, name = 'Aïcha' }: { checks: string[]; onToggle: (id: string) => void; onNavigate: Go; receivedProjects: ProjectCard[]; receivedTasks: AssignedTask[]; name?: string }) {
  const today = new Date()
  const [cursor, setCursor] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1))
  const year = cursor.getFullYear()
  const month = cursor.getMonth()
  const lead = (new Date(year, month, 1).getDay() + 6) % 7
  const count = new Date(year, month + 1, 0).getDate()
  const cells = [...Array(lead).fill(0), ...Array.from({ length: count }, (_, index) => index + 1)]
  while (cells.length % 7) cells.push(0)
  const monthTitle = cursor.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
  const [priorities, setPriorities] = useState([
    { n: '1', tone: 'pink', title: 'Aucune tâche pour le moment', project: 'Vos tâches apparaîtront ici', time: '—' },
  ])
  const [kpis, setKpis] = useState({ tasks: 0, done: 0, projects: 0, progress: '—', due: '—' })
  const [notices, setNotices] = useState<{ id: number; title: string; message: string; page: string }[]>([])
  useEffect(() => {
    Promise.all([deskCall('/api/taches/'), deskCall('/api/projets/')]).then(([taskData, projectData]) => {
      const tasks = ((taskData.tasks ?? []) as { title: string; project: string; due_date: string; status_label: string; planned_date: string }[]).filter((item) => !(item.planned_date && !item.due_date))
      const projects = (projectData.projects ?? []) as { name: string; progress: number }[]
      const done = tasks.filter((item) => item.status_label === 'Terminée').length
      setKpis({
        tasks: tasks.length,
        done,
        projects: projects.length,
        progress: projects[0] ? `${projects[0].progress} % ${projects[0].name}` : 'Aucun projet',
        due: tasks.find((item) => item.due_date)?.due_date || '—',
      })
      if (tasks.length) {
        setPriorities(tasks.slice(0, 3).map((item, index) => ({
          n: String(index + 1),
          tone: ['pink', 'violet', 'blue'][index] || 'blue',
          title: item.title,
          project: item.project || 'Sans projet',
          time: item.due_date || '—',
        })))
      }
    }).catch(() => undefined)
    deskCall('/api/notifications/').then((data) => {
      const rows = (data.notifications ?? []) as { id: number; title: string; message: string; link?: string; read: boolean }[]
      setNotices(rows.filter((item) => !item.read).slice(0, 4).map((item) => {
        const link = item.link || ''
        const page = /messages|messaging/.test(link) ? 'messaging' : /\/tasks\/\d+/.test(link) ? 'tasks' : /projects|projets/.test(link) ? 'projects' : 'notifications'
        return { id: item.id, title: item.title, message: item.message, page }
      }))
    }).catch(() => undefined)
  }, [])
  return (
    <section className="eh">
      <header className="eh-head">
        <div>
          <h1>Bonjour, {name}</h1>
          <p>Voici vos priorités et rendez-vous pour aujourd’hui.</p>
        </div>
        <button className="lp-btn" type="button" onClick={() => onNavigate('tasks')}><Icon name="plus" size={14} /> Créer une tâche</button>
      </header>
      {notices.length > 0 ? (
        <div className="eh-notes">
          {notices.map((item) => (
            <button type="button" key={item.id} onClick={() => onNavigate(item.page)}>
              <Icon name={item.page === 'messaging' ? 'message' : 'bell'} size={15} />
              <span><strong>{item.title}</strong><small>{item.message}</small></span>
            </button>
          ))}
        </div>
      ) : null}
      <div className="eh-kpis">
        <article>
          <span className="eh-ico blue"><Icon name="check" size={15} /></span>
          <span>Tâches aujourd’hui</span>
          <strong>{kpis.tasks}</strong>
          <small className="up"><Icon name="trend" size={12} /> {kpis.done} terminées sur {kpis.tasks} tâches</small>
        </article>
        <article>
          <span className="eh-ico violet"><Icon name="folder" size={15} /></span>
          <span>Projet actif</span>
          <strong>{kpis.projects}</strong>
          <small className="up"><Icon name="trend" size={12} /> {kpis.progress}</small>
        </article>
        <article>
          <span className="eh-ico orange"><Icon name="clock" size={15} /></span>
          <span>Temps déclaré</span>
          <strong>5h 30</strong>
          <small className="up"><Icon name="trend" size={12} /> 1h 30 à compléter</small>
        </article>
        <article>
          <span className="eh-ico green"><Icon name="calendar" size={15} /></span>
          <span>Prochaine échéance</span>
          <strong>{kpis.due}</strong>
          <small className="up"><Icon name="trend" size={12} /> Prochaine date limite</small>
        </article>
      </div>
      <div className="eh-grid">
        <article className="eh-card">
          <header>
            <div><h2>Mes priorités du jour</h2><p>Activités recommandées selon vos échéances</p></div>
            <button type="button" onClick={() => onNavigate('tasks')}>Voir ma liste <Icon name="chevron" size={13} /></button>
          </header>
          {priorities.map((item) => (
            <button className="eh-task" type="button" key={item.n} onClick={() => onNavigate('tasks')}>
              <b className={item.tone}>{item.n}</b>
              <span><strong>{item.title}</strong><small>{item.project}</small></span>
              <time><Icon name="clock" size={13} /> {item.time}</time>
              <Icon name="chevron" size={14} />
            </button>
          ))}
        </article>
        <article className="eh-card eh-cal">
          <header>
            <div><h2>Calendrier</h2><p>Vos rendez-vous et échéances</p></div>
          </header>
          <div className="af-cal-nav">
            <button type="button" aria-label="Mois précédent" onClick={() => setCursor(new Date(year, month - 1, 1))}><Icon name="chevron" size={14} /></button>
            <strong>{monthTitle}</strong>
            <button type="button" aria-label="Mois suivant" onClick={() => setCursor(new Date(year, month + 1, 1))}><Icon name="chevron" size={14} /></button>
          </div>
          <div className="af-cal-grid af-cal-week">
            {['L', 'M', 'M', 'J', 'V', 'S', 'D'].map((label, index) => <span key={`${label}-${index}`}>{label}</span>)}
          </div>
          <div className="af-cal-grid">
            {cells.map((day, index) => {
              const current = day === today.getDate() && month === today.getMonth() && year === today.getFullYear()
              return <span key={index} className={current ? 'today' : ''}>{day || ''}</span>
            })}
          </div>
          <div className="eh-meet">
            <span><Icon name="calendar" size={14} /></span>
            <p><strong>Revue du modèle prédictif</strong><small>Aujourd’hui · 14:30 – 15:15</small></p>
          </div>
        </article>
      </div>
      <div className="eh-bottom">
        <article className="eh-week">
          <span><Icon name="spark" size={16} /></span>
          <div>
            <small>Votre semaine</small>
            <strong>Vous êtes sur la bonne voie</strong>
            <p>4 tâches sur 7 sont déjà terminées. Gardez votre concentration sur le modèle prédictif avant la revue de 14:30.</p>
          </div>
          <b>57%</b>
        </article>
        <article className="eh-card eh-msg">
          <header>
            <div><h2>Message de votre responsable</h2><p>Dernière communication</p></div>
            <em>Nouveau</em>
          </header>
          <div className="eh-note">
            <b>AM</b>
            <span>
              <strong>Amadou Mensah</strong>
              <p>Bonjour Aïcha, le client a validé les nouveaux indicateurs. Nous en parlons pendant la revue.</p>
              <small>Il y a 18 min</small>
            </span>
          </div>
          <button type="button" onClick={() => onNavigate('messaging')}><Icon name="message" size={14} /> Ouvrir la conversation</button>
        </article>
      </div>
    </section>
  )
}

function LightHead({ kicker, title, text, action }: { kicker: string; title: string; text: string; action?: ReactNode }) {
  return (
    <div className="lp-head">
      <div>
        {kicker ? <span>{kicker}</span> : null}
        <h1>{title}</h1>
        <p>{text}</p>
      </div>
      {action}
    </div>
  )
}

const directory = [
  { initials: 'AK', tone: 'violet', name: 'Aïcha Konaté', email: 'aicha.konate@racin.africa', role: 'Data Analyst', project: 'Nova Analytics', tasks: '24 tâches', status: 'Actif', seen: 'Il y a 8 min' },
  { initials: 'MD', tone: 'blue', name: 'Moussa Diallo', email: 'moussa.diallo@racin.africa', role: 'Développeur Full Stack', project: 'Portail Finance', tasks: '19 tâches', status: 'Actif', seen: 'Il y a 24 min' },
  { initials: 'SN', tone: 'orange', name: 'Sarah N’Guessan', email: 'sarah.nguessan@racin.africa', role: 'UX/UI Designer', project: 'Mobile Banking', tasks: '16 tâches', status: 'Absent', seen: 'Hier, 18:32' },
  { initials: 'IT', tone: 'green', name: 'Ibrahim Traoré', email: 'ibrahim.traore@racin.africa', role: 'Data Engineer', project: 'Nova Analytics', tasks: '21 tâches', status: 'Actif', seen: 'Il y a 41 min' },
  { initials: 'FN', tone: 'pink', name: 'Fatou Ndiaye', email: 'fatou.ndiaye@racin.africa', role: 'Cheffe de projet', project: 'Portail Finance', tasks: '28 tâches', status: 'En congé', seen: 'Vendredi, 17:45' },
]

function EmployeesPage() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('Tous')
  const [adding, setAdding] = useState(false)
  const [live, setLive] = useState<typeof directory | null>(null)
  useEffect(() => {
    deskCall('/api/employes/').then((data) => {
      const people = (data.employees ?? []) as { name: string; username: string; initials: string }[]
      setLive(people.map((person) => ({
        initials: person.initials,
        tone: 'violet',
        name: person.name,
        email: person.username === 'nouzou' ? 'zaina' : person.username,
        role: 'Employé',
        project: '—',
        tasks: '—',
        status: 'Actif',
        seen: 'En base',
      })))
    }).catch(() => undefined)
  }, [])
  const rows = (live ?? directory).filter((person) => {
    const blob = `${person.name} ${person.role} ${person.project}`.toLowerCase()
    return blob.includes(query.toLowerCase()) && (status === 'Tous' || person.status === status)
  })
  return (
    <section className="lp">
      <LightHead kicker="Équipe" title="Gestion des employés" text="Gérez votre équipe et suivez les performances individuelles." action={<button className="lp-btn" type="button" onClick={() => setAdding((value) => !value)}><Icon name="plus" size={14} /> Ajouter un employé</button>} />
      {adding ? <p className="lp-note">Les comptes de test sont déjà en base : awa.traore, mamadou.kone, fatou.diarra, ibrahim.bah. Mot de passe Employe-2026.</p> : null}
      <div className="lp-stats">
        <span><Icon name="users" size={15} /> <b>{(live ?? directory).length}</b> Employés</span>
        <span className="ok"><i /> <b>43</b> Actifs</span>
        <span className="bad"><i /> <b>2</b> Absents</span>
        <span className="warn"><i /> <b>3</b> En congé</span>
      </div>
      <div className="lp-panel">
        <div className="lp-tools">
          <label><Icon name="search" size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher un employé..." /></label>
          <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filtres">
            <option>Tous</option>
            <option>Actif</option>
            <option>Absent</option>
            <option>En congé</option>
          </select>
        </div>
        <table className="lp-table">
          <thead><tr><th>Employé</th><th>Fonction</th><th>Projet actuel</th><th>Tâches</th><th>Statut</th><th>Dernière activité</th><th></th></tr></thead>
          <tbody>
            {rows.map((person) => (
              <tr key={person.email}>
                <td><span className="lp-person"><b className={person.tone}>{person.initials}</b><span><strong>{person.name}</strong><small>{person.email}</small></span></span></td>
                <td>{person.role}</td>
                <td className="link">{person.project}</td>
                <td>{person.tasks}</td>
                <td><em className={person.status === 'Actif' ? 'ok' : person.status === 'Absent' ? 'bad' : 'warn'}>{person.status}</em></td>
                <td className="muted">{person.seen}</td>
                <td><button type="button" aria-label="Actions">•••</button></td>
              </tr>
            ))}
            {rows.length === 0 ? <tr><td colSpan={7} className="empty">Aucun employé ne correspond.</td></tr> : null}
          </tbody>
        </table>
        <div className="lp-pages"><span>Affichage de 1 à {rows.length} sur {(live ?? directory).length} employés</span></div>
      </div>
    </section>
  )
}

function NewProject({ onBack, onCreate }: { onBack: () => void; onCreate: (project: ProjectCard, tasks: AssignedTask[]) => void }) {
  const [name, setName] = useState('')
  const [client, setClient] = useState('')
  const [owner, setOwner] = useState('Responsable')
  const [description, setDescription] = useState('')
  const [start, setStart] = useState('2026-10-09')
  const [end, setEnd] = useState('2026-10-30')
  const [status, setStatus] = useState('Planifié')
  const [priority, setPriority] = useState('Normale')
  const [roster, setRoster] = useState<{ id: string; name: string; role: string; service: string; initials: string; tone: string; status: string; todo: string; seen: string; online: boolean; reports: number; presence: string }[]>([])
  const [rawFile, setRawFile] = useState<File | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [rows, setRows] = useState([
    { id: 1, title: '', who: '', priority: 'Élevée', due: '2026-10-12' },
  ])
  const [error, setError] = useState('')
  const [draft, setDraft] = useState(false)
  const [attachment, setAttachment] = useState<ProjectFile | null>(null)
  const [fileError, setFileError] = useState('')
  const [teamReady, setTeamReady] = useState(false)
  const picker = useRef<HTMLInputElement>(null)
  const tones = ['tone-purple', 'tone-sky', 'tone-amber', 'tone-green']
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        await ensureAdminSession()
        const data = await deskCall('/api/employes/')
        const list = (data.employees ?? []) as { id: number; name: string; initials: string; role?: string; service?: string }[]
        if (cancelled) return
        setRoster(list.map((person) => ({
          id: String(person.id),
          name: person.name,
          role: person.role || 'Employé',
          service: person.service || 'Agence',
          initials: person.initials,
          tone: '',
          status: 'Actif',
          todo: '',
          seen: '',
          online: true,
          reports: 0,
          presence: '',
        })))
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : 'Impossible de charger les employés.')
      } finally {
        if (!cancelled) setTeamReady(true)
      }
    })()
    return () => { cancelled = true }
  }, [])
  function toggleMember(id: string) {
    setSelected((prev) => {
      const next = prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
      setRows((current) => current.map((row) => next.includes(row.who) ? row : { ...row, who: next[0] || '' }))
      return next
    })
    setError('')
  }
  async function takeFile(list: FileList | null) {
    const file = list?.[0]
    if (picker.current) picker.current.value = ''
    if (!file) return
    const lower = file.name.toLowerCase()
    const pdf = lower.endsWith('.pdf')
    const docx = lower.endsWith('.docx')
    if (!pdf && !docx) {
      setFileError('Formats acceptés : PDF ou DOCX.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setFileError('Le fichier dépasse 10 Mo.')
      return
    }
    let html = ''
    let url = ''
    if (docx) {
      const mammoth = await import('mammoth')
      const result = await mammoth.convertToHtml({ arrayBuffer: await file.arrayBuffer() })
      html = result.value
    } else {
      url = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result))
        reader.onerror = () => reject(reader.error)
        reader.readAsDataURL(file)
      })
    }
    setRawFile(file)
    setAttachment({ name: file.name, kind: pdf ? 'PDF' : 'DOC', size: formatSize(file.size), url: url || undefined, html: html || undefined })
    setFileError('')
  }
  async function create() {
    if (!name.trim()) {
      setError('Indiquez le nom du projet.')
      setDraft(false)
      return
    }
    const id = `p-${Date.now()}`
    const projectName = name.trim()
    const priorityCode = priority === 'Urgente' ? 'urgent' : priority === 'Élevée' ? 'high' : 'medium'
    const filled = rows.filter((item) => item.title.trim())
    const missingAssignee = filled.find((row) => !roster.some((person) => person.id === row.who))
    if (missingAssignee) {
      setError('Choisissez l’employé qui reçoit chaque tâche.')
      return
    }
    const employeeIds = [...new Set([
      ...selected.map(Number),
      ...filled.map((row) => Number(row.who)),
    ].filter((value) => value > 0))]
    if (!employeeIds.length) {
      setError(roster.length ? 'Cliquez sur l’employé à qui vous attribuez le projet.' : 'Aucun employé enregistré. Rechargez la page, puis réessayez.')
      return
    }
    const made = filled.map((row, index) => {
      const person = roster.find((item) => item.id === row.who)
      return {
        id: `nt-${id}-${index}`,
        title: row.title.trim(),
        project: projectName,
        projectId: id,
        who: person?.name || row.who,
        whoId: row.who,
        priority: row.priority,
        tone: priorityTone(row.priority),
        due: formatFrenchDate(row.due),
        status: 'À faire',
      }
    })
    const members = employeeIds.map(String)
    try {
      await ensureAdminSession()
      const saved = await deskCall('/api/projets/', {
        method: 'POST',
        body: JSON.stringify({
          name: projectName,
          client: client.trim() || 'Non renseigné',
          description: description.trim(),
          start_date: start,
          end_date: end,
          priority: priorityCode,
          employees: employeeIds,
        }),
      })
      const projectId = saved.project.id as number
      const fileRow = filled[0]
      for (const row of filled) {
        const body = new FormData()
        body.set('title', row.title.trim())
        body.set('project', String(projectId))
        body.set('employee', row.who)
        body.set('priority', row.priority === 'Urgente' ? 'urgent' : row.priority === 'Élevée' ? 'high' : 'medium')
        body.set('due_date', row.due)
        body.set('description', description.trim())
        if (rawFile && row === fileRow) body.append('documents', rawFile)
        await deskCall('/api/taches/', { method: 'POST', body })
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Enregistrement impossible.')
      return
    }
    onCreate({
      id,
      name: projectName,
      client: client.trim() || 'Non renseigné',
      owner,
      progress: 0,
      status,
      due: formatFrenchDate(end),
      start: formatFrenchDate(start),
      description: description.trim(),
      priority,
      members,
      file: attachment ?? undefined,
    }, made)
  }
  return (
    <section>
      <div className="create-head">
        <span />
        <div className="create-title">
          <h1>Créer un nouveau projet</h1>
          <p>Renseignez le projet, constituez l'équipe et attribuez les premières tâches.</p>
        </div>
        <Button ghost onClick={onBack}>Retour aux projets</Button>
      </div>
      <div className="create-layout">
        <div className="create-main">
          <article className="card card-pad create-card">
            <div className="step-top">
              <h2><span className="step-num">01</span>Informations du projet</h2>
            </div>
            <p className="sub" style={{ marginTop: -8, marginBottom: 10 }}>Les informations principales utilisées par toute l'équipe.</p>
            <label>Nom du projet<input className="field" value={name} onChange={(event) => setName(event.target.value)} placeholder="Ex. Campagne digitale Octobre" /></label>
            <div className="form-2">
              <label>Client<input className="field" value={client} onChange={(event) => setClient(event.target.value)} placeholder="Nom du client" /></label>
              <label>Responsable du projet
                <select className="field" value={owner} onChange={(event) => setOwner(event.target.value)}>
                  <option>Responsable</option>
                </select>
              </label>
            </div>
            <label style={{ marginTop: 10 }}>Description<textarea className="field" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Décrivez les objectifs, les livrables attendus et le contexte du projet..." /></label>
            <div className="form-2">
              <label>Date de début<input className="field" type="date" value={start} onChange={(event) => setStart(event.target.value)} /></label>
              <label>Date de fin<input className="field" type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></label>
              <label>Statut initial
                <select className="field" value={status} onChange={(event) => setStatus(event.target.value)}>
                  <option>Planifié</option>
                  <option>En cours</option>
                  <option>Terminé</option>
                </select>
              </label>
              <label>Priorité du projet
                <select className="field" value={priority} onChange={(event) => setPriority(event.target.value)}>
                  <option>Normale</option>
                  <option>Élevée</option>
                  <option>Urgente</option>
                </select>
              </label>
            </div>
            <div
              className="project-drop"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => { event.preventDefault(); void takeFile(event.dataTransfer.files) }}
            >
              <input ref={picker} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" hidden onChange={(event) => { void takeFile(event.target.files) }} />
              <span className={`file-ico${attachment ? ' ok' : ''}`}><Icon name={attachment ? 'check' : 'file'} size={16} /></span>
              <span className="grow">
                <strong>{attachment ? attachment.name : 'Importer un fichier'}</strong>
                <small>{attachment ? `${attachment.kind} · ${attachment.size}` : 'PDF ou DOCX, 10 Mo maximum'}</small>
              </span>
              <Button onClick={() => picker.current?.click()}>{attachment ? 'Remplacer' : 'Choisir un fichier'}</Button>
            </div>
            {fileError ? <p className="sub" style={{ color: '#fca5a5', marginTop: 8 }}>{fileError}</p> : null}
          </article>
          <article className="card card-pad">
            <div className="step-top">
              <div>
                <h2><span className="step-num">02</span>Équipe du projet</h2>
                <p className="sub">Cliquez sur les employés enregistrés qui doivent recevoir ce projet.</p>
              </div>
              <span className="step-count">{selected.length} sélectionné{selected.length > 1 ? 's' : ''}</span>
            </div>
            {teamReady && roster.length === 0 ? <p className="sub">{error || 'Aucun employé enregistré pour le moment.'}</p> : null}
            <div className="team-grid">
              {roster.map((person, index) => {
                const on = selected.includes(person.id)
                return (
                  <button className={`member-card${on ? ' on' : ''}`} type="button" key={person.id} onClick={() => toggleMember(person.id)}>
                    <span className={`member-pill ${tones[index % tones.length]}`}>{person.initials}</span>
                    <span className="grow"><strong>{person.name}</strong><small>{person.role} · {person.service}</small></span>
                    <span className="member-mark">{on ? <Icon name="check" size={12} /> : <Icon name="plus" size={12} />}</span>
                  </button>
                )
              })}
            </div>
          </article>
          <article className="card card-pad create-card">
            <div className="step-top task-head">
              <div>
                <h2><span className="step-num">03</span>Premières tâches à attribuer</h2>
                <p className="sub">Préparez le démarrage du projet en affectant chaque tâche au bon collaborateur.</p>
              </div>
              <button className="linkish" type="button" onClick={() => setRows((prev) => [...prev, { id: Date.now(), title: '', who: selected[0] || '', priority: 'Moyenne', due: end }])}><Icon name="plus" size={12} /> Ajouter</button>
            </div>
            {rows.map((row, index) => (
              <div className="task-row" key={row.id}>
                <span className="idx">{String(index + 1).padStart(2, '0')}</span>
                <div className="task-box">
                  <label>Tâche<input className="field" value={row.title} onChange={(event) => setRows((prev) => prev.map((item) => item.id === row.id ? { ...item, title: event.target.value } : item))} placeholder="Intitulé de la tâche" /></label>
                  <label>Attribuer à
                    <select className="field" value={row.who} onChange={(event) => {
                      const who = event.target.value
                      setRows((prev) => prev.map((item) => item.id === row.id ? { ...item, who } : item))
                      if (who) setSelected((prev) => prev.includes(who) ? prev : [...prev, who])
                    }}>
                      <option value="">Choisir un employé</option>
                      {roster.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
                    </select>
                  </label>
                  <label>Priorité
                    <select className="field" value={row.priority} onChange={(event) => setRows((prev) => prev.map((item) => item.id === row.id ? { ...item, priority: event.target.value } : item))}>
                      <option>Élevée</option>
                      <option>Moyenne</option>
                      <option>Urgente</option>
                    </select>
                  </label>
                  <label>Échéance<input className="field" type="date" value={row.due} onChange={(event) => setRows((prev) => prev.map((item) => item.id === row.id ? { ...item, due: event.target.value } : item))} /></label>
                </div>
                <button className="task-x" type="button" aria-label="Retirer la tâche" onClick={() => setRows((prev) => prev.filter((item) => item.id !== row.id))}>×</button>
              </div>
            ))}
          </article>
        </div>
        <div className="stack">
          <article className="card card-pad ready">
            <span className="metric-ico blue"><Icon name="folder" size={16} /></span>
            <h2>Prêt à lancer le projet ?</h2>
            <p className="sub">Une notification sera envoyée à chaque collaborateur assigné dès la création.</p>
            <div className="ready-line"><span>Membres</span><strong>{selected.length}</strong></div>
            <div className="ready-line"><span>Tâches initiales</span><strong>{rows.length}</strong></div>
            <div className="ready-people">
              {roster.filter((person) => selected.includes(person.id)).map((person, index) => <Avatar key={person.id} initials={person.initials} tone={tones[index] ?? ''} size="sm" />)}
            </div>
            {error ? <p className="sub" style={{ color: '#fca5a5' }}>{error}</p> : null}
            {draft ? <p className="sub">Brouillon enregistré sur cet écran.</p> : null}
            <Button onClick={create}><Icon name="plus" size={14} /> Créer le projet</Button>
            <button className="linkish" type="button" onClick={() => { setDraft(true); setError('') }}>Enregistrer comme brouillon</button>
          </article>
          <article className="card card-pad advice">
            <Icon name="spark" size={14} />
            <span><strong>Conseil RAC'IN</strong>Attribuer des tâches précises avec une échéance réaliste pour faciliter les Todo List quotidiennes de chaque employé.</span>
          </article>
        </div>
      </div>
    </section>
  )
}

function ProjectSheet({ project, tasks, onBack, role = 'admin', onChanged }: { project: ProjectCard; tasks: AssignedTask[]; onBack: () => void; role?: Role; onChanged?: () => void }) {
  const tones = ['tone-purple', 'tone-sky', 'tone-amber', 'tone-green']
  const members = project.team?.length ? project.team : (project.members ?? []).map((name) => ({ name, initials: name.slice(0, 2).toUpperCase() }))
  const files = project.files?.length ? project.files : project.file ? [project.file] : []
  const [openedFile, setOpenedFile] = useState<ProjectFile | null>(null)
  async function archive() {
    await deskCall(`/api/projets/${project.id}/`, { method: 'POST', body: JSON.stringify({ archive: true }) })
    onBack()
  }
  async function remove() {
    if (!window.confirm(`Supprimer le projet « ${project.name} » et ses tâches ?`)) return
    await deskCall(`/api/projets/${project.id}/`, { method: 'POST', body: JSON.stringify({ delete: true }) })
    onBack()
  }
  return (
    <section>
      <div className="create-head">
        <span />
        <div className="create-title">
          <h1>{project.name}</h1>
          <p>Les informations enregistrées à la création du projet.</p>
        </div>
        <span>
          <Button ghost onClick={onBack}>Retour aux projets</Button>
          {role === 'admin' ? <Button ghost onClick={() => { void archive() }}>Archiver</Button> : null}
          {role === 'admin' ? <Button danger onClick={() => { void remove() }}>Supprimer</Button> : null}
        </span>
      </div>
      <div className="create-layout">
        <div className="create-main">
          <article className="card card-pad create-card">
            <div className="step-top">
              <h2><span className="step-num">01</span>Informations du projet</h2>
            </div>
            <p className="sub" style={{ marginTop: -8, marginBottom: 10 }}>Les informations principales utilisées par toute l'équipe.</p>
            <label>Nom du projet<input className="field" readOnly value={project.name} /></label>
            <div className="form-2">
              <label>Client<input className="field" readOnly value={project.client} /></label>
              <label>Responsable du projet<input className="field" readOnly value={project.owner} /></label>
            </div>
            <label style={{ marginTop: 10 }}>Description<textarea className="field" readOnly value={project.description || 'Non renseignée'} /></label>
            <div className="form-2">
              <label>Date de début<input className="field" readOnly value={project.start || 'Non renseignée'} /></label>
              <label>Date de fin<input className="field" readOnly value={project.due} /></label>
              <label>Statut initial<input className="field" readOnly value={project.status} /></label>
              <label>Priorité du projet<input className="field" readOnly value={project.priority || 'Non renseignée'} /></label>
            </div>
            {files.length === 0 ? (
              <div className="project-drop">
                <span className="file-ico"><Icon name="file" size={16} /></span>
                <span className="grow"><strong>Aucun fichier importé</strong><small>Le responsable peut joindre un PDF ou un DOCX à la création.</small></span>
              </div>
            ) : files.map((file) => (
              <div className="project-drop" key={file.url || file.name}>
                <span className="file-ico ok"><Icon name="check" size={16} /></span>
                <span className="grow"><strong>{file.name}</strong><small>{file.kind || 'Document'}{file.size ? ` · ${file.size}` : ''}</small></span>
                <Button ghost onClick={() => { setOpenedFile(file); openInBrowser(file) }}>Ouvrir</Button>
              </div>
            ))}
            {openedFile ? <FileViewer file={openedFile} /> : null}
          </article>
          <article className="card card-pad">
            <div className="step-top">
              <div>
                <h2><span className="step-num">02</span>Équipe du projet</h2>
                <p className="sub">Les collaborateurs sélectionnés à la création.</p>
              </div>
              <span className="step-count">{members.length} sélectionné{members.length > 1 ? 's' : ''}</span>
            </div>
            <div className="team-grid">
              {members.map((person, index) => (
                <div className="member-card on" key={`${person.initials}-${person.name}`}>
                  <span className={`member-pill ${tones[index % tones.length]}`}>{person.initials}</span>
                  <span className="grow"><strong>{person.name}</strong><small>Employé · Agence</small></span>
                  <span className="member-mark"><Icon name="check" size={12} /></span>
                </div>
              ))}
            </div>
          </article>
          <article className="card card-pad create-card">
            <div className="step-top task-head">
              <div>
                <h2><span className="step-num">03</span>Premières tâches à attribuer</h2>
                <p className="sub">Les tâches attribuées au moment de la création.</p>
              </div>
            </div>
            {tasks.length === 0 ? <p className="muted">Aucune tâche n'a été enregistrée.</p> : null}
            {tasks.map((task, index) => (
              <div className="task-row view" key={task.id}>
                <span className="idx">{String(index + 1).padStart(2, '0')}</span>
                <div className="task-box">
                  <label>Tâche<input className="field" readOnly value={task.title} /></label>
                  <label>Attribuer à<input className="field" readOnly value={task.who} /></label>
                  <label>Priorité<input className="field" readOnly value={task.priority} /></label>
                  <label>Échéance<input className="field" readOnly value={task.due} /></label>
                  <label>Statut<input className="field" readOnly value={task.status} /></label>
                  {role === 'admin' ? <Button danger onClick={() => { if (!window.confirm(`Supprimer la tâche « ${task.title} » ?`)) return; void deskCall(`/api/taches/${task.id}/`, { method: 'POST', body: JSON.stringify({ delete: true }) }).then(() => onChanged?.()) }}>Supprimer</Button> : null}
                </div>
              </div>
            ))}
          </article>
        </div>
        <div className="stack">
          <article className="card card-pad ready">
            <span className="metric-ico blue"><Icon name="folder" size={16} /></span>
            <h2>{project.name}</h2>
            <p className="sub">Avancement {project.progress} % · {project.status}</p>
            <div className="ready-line"><span>Membres</span><strong>{members.length}</strong></div>
            <div className="ready-line"><span>Tâches initiales</span><strong>{tasks.length}</strong></div>
            <div className="ready-people">
              {members.map((person, index) => <Avatar key={`${person.initials}-${index}`} initials={person.initials} tone={tones[index % tones.length] ?? ''} size="sm" />)}
            </div>
          </article>
        </div>
      </div>
    </section>
  )
}

function ProjectsPage({ role, onCreate }: { role: Role; list: ProjectCard[]; duties: AssignedTask[]; onCreate: (project: ProjectCard, tasks: AssignedTask[]) => void }) {
  const [open, setOpen] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [projectQuery, setProjectQuery] = useState('')
  const [layout, setLayout] = useState<'grid' | 'list'>('grid')
  const [stamp, setStamp] = useState(0)
  const [liveCards, setLiveCards] = useState<ProjectCard[]>([])
  const [liveTasks, setLiveTasks] = useState<AssignedTask[]>([])
  useEffect(() => {
    Promise.all([deskCall('/api/projets/'), deskCall('/api/taches/')]).then(([projectData, taskData]) => {
      setLiveCards((projectData.projects as { id: number; name: string; client: string; end_date: string; start_date: string; status_label: string; priority_label: string; progress: number; description: string; employees: { id: number; name: string; initials: string }[] }[]).map((item) => ({
        id: String(item.id),
        name: item.name,
        client: item.client,
        owner: 'Responsable',
        progress: item.progress,
        status: item.status_label,
        due: formatFrenchDate(item.end_date),
        start: formatFrenchDate(item.start_date),
        description: item.description,
        priority: item.priority_label,
        members: item.employees.map((person) => person.initials || String(person.id)),
        team: item.employees.map((person) => ({ name: person.name, initials: person.initials || person.name.slice(0, 2).toUpperCase() })),
      })))
      setLiveTasks((taskData.tasks as { id: number; title: string; project: string; project_id: number | null; employee: string; employee_id: number | null; priority_label: string; due_date: string; status_label: string; planned_date?: string; documents: { name: string; url: string }[]; result_url: string; result_name: string }[])
        .filter((item) => !(item.planned_date && !item.due_date))
        .map((item) => ({
          id: String(item.id),
          title: item.title,
          project: item.project,
          projectId: String(item.project_id ?? ''),
          who: item.employee,
          whoId: String(item.employee_id ?? ''),
          priority: item.priority_label,
          tone: priorityTone(item.priority_label),
          due: item.due_date,
          status: item.status_label,
          docs: item.documents,
          resultUrl: item.result_url,
          resultName: item.result_name,
        })))
    }).catch(() => undefined)
  }, [role, stamp])
  const current = liveCards.find((item) => item.id === open)
  const currentTasks = liveTasks.filter((task) => task.projectId === current?.id)
  if (current) {
    const files = currentTasks.flatMap((task) => (task.docs ?? []).map((document) => ({
      name: document.name,
      kind: document.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOC',
      size: '',
      url: document.url,
    })))
    return <ProjectSheet role={role} project={{ ...current, file: files[0], files }} tasks={currentTasks} onBack={() => { setOpen(null); setStamp((value) => value + 1) }} onChanged={() => setStamp((value) => value + 1)} />
  }
  if (creating) {
    return <NewProject onBack={() => setCreating(false)} onCreate={(project, tasks) => { onCreate(project, tasks); setCreating(false); setStamp((value) => value + 1); setOpen(null) }} />
  }
  const cards = liveCards.filter((item) => `${item.name} ${item.client} ${item.owner}`.toLowerCase().includes(projectQuery.trim().toLowerCase())).map((item) => ({ ...item, tasks: `${liveTasks.filter((task) => task.projectId === item.id).length} tâches`, tone: item.progress >= 90 ? 'green' : item.progress < 40 ? 'orange' : 'violet' }))
    return (
      <section className="lp">
        <LightHead kicker="Portefeuille" title="Projets" text="Planifiez, pilotez et suivez tous vos projets en un seul endroit." action={role === 'admin' ? <button className="lp-btn" type="button" onClick={() => setCreating(true)}><Icon name="plus" size={14} /> Nouveau projet</button> : undefined} />
        <div className="lp-panel">
          <div className="lp-tools">
            <label><Icon name="search" size={15} /><input value={projectQuery} onChange={(event) => setProjectQuery(event.target.value)} placeholder="Rechercher un projet..." /></label>
            <button className="lp-filter" type="button">Filtres <b>2</b></button>
            <span className="lp-views">
              <button className={layout === 'grid' ? 'on' : ''} type="button" aria-label="Grille" onClick={() => setLayout('grid')}><Icon name="grid" size={14} /></button>
              <button className={layout === 'list' ? 'on' : ''} type="button" aria-label="Liste" onClick={() => setLayout('list')}><Icon name="list" size={14} /></button>
            </span>
          </div>
          <div className={`lp-projects${layout === 'list' ? ' list' : ''}`}>
            {cards.map((item) => (
              <article key={item.id} onClick={() => setOpen(item.id)} style={{ cursor: 'pointer' }}>
                <div className="lp-card-top"><span className="lp-folder"><Icon name="folder" size={16} /></span><em className={item.status === 'À venir' || item.status === 'Planifié' ? 'wait' : 'ok'}>{item.status}</em>{role === 'admin' ? <button type="button" onClick={(event) => { event.stopPropagation(); if (!window.confirm(`Supprimer le projet « ${item.name} » et ses tâches ?`)) return; void deskCall(`/api/projets/${item.id}/`, { method: 'POST', body: JSON.stringify({ delete: true }) }).then(() => setStamp((value) => value + 1)) }}>Supprimer</button> : <button type="button" aria-label="Ouvrir le projet" onClick={(event) => { event.stopPropagation(); setOpen(item.id) }}>•••</button>}</div>
                <h2>{item.name}</h2>
                <p>{item.client}</p>
                <div className="lp-meta"><span>Responsable<small>{item.owner}</small></span><span>Échéance<small>{item.due}</small></span></div>
                <div className="lp-progress"><span>Progression</span><b>{item.progress}%</b></div>
                <div className={`lp-bar ${item.tone}`}><i style={{ width: `${item.progress}%` }} /></div>
                <footer>
                  <span><Icon name="check" size={13} /> {item.tasks}</span>
                  <span className="lp-faces">
                    {(item.team ?? []).slice(0, 3).map((face) => <b key={face.initials}>{face.initials}</b>)}
                    <button type="button" aria-label="Ouvrir" onClick={(event) => { event.stopPropagation(); setOpen(item.id) }}>→</button>
                  </span>
                </footer>
              </article>
            ))}
          </div>
        </div>
      </section>
    )
}

function TasksPage({ role, focus = '' }: { role: Role; checks: string[]; onToggle: (id: string) => void; assigned: AssignedTask[]; focus?: string }) {
  const [tab, setTab] = useState('Toutes')
  const [query, setQuery] = useState('')
  const [stamp, setStamp] = useState(0)
  const [rows, setRows] = useState<{ code: string; title: string; project: string; who: string; initials: string; tone: string; priority: string; due: string; status: string; progress: number; docs: { name: string; url: string }[]; resultUrl: string; resultName: string; description: string }[]>([])
  const [picked, setPicked] = useState(focus ? `#${focus}` : '')
  useEffect(() => { if (focus) setPicked(`#${focus}`) }, [focus])
  const [note, setNote] = useState('')
  const [composer, setComposer] = useState(false)
  const [projectsList, setProjectsList] = useState<{ id: number; name: string }[]>([])
  const [peopleList, setPeopleList] = useState<{ id: number; name: string }[]>([])
  const [draft, setDraft] = useState({ title: '', project: '', employee: '', due: '', priority: 'medium' })
  useEffect(() => {
    deskCall('/api/taches/').then((data) => {
      const tasks = (data.tasks ?? []) as { id: number; title: string; description: string; project: string; employee: string; priority_label: string; due_date: string; status_label: string; planned_date: string; documents: { name: string; url: string }[]; result_url: string; result_name: string }[]
      setRows(tasks.filter((item) => !(item.planned_date && !item.due_date)).map((item) => ({
        code: `#${item.id}`,
        title: item.title,
        project: item.project || '—',
        who: item.employee || 'Zaina Zaina',
        initials: (item.employee || 'ZZ').split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase(),
        tone: 'violet',
        priority: item.priority_label === 'Haute' ? 'Élevée' : item.priority_label,
        due: item.due_date,
        status: item.status_label === 'Non commencée' ? 'À faire' : item.status_label,
        progress: item.status_label === 'Terminée' ? 100 : item.status_label === 'En cours' ? 50 : 0,
        docs: item.documents ?? [],
        resultUrl: item.result_url,
        resultName: item.result_name || '',
        description: item.description || '',
      })))
    }).catch(() => undefined)
    if (role === 'admin') {
      Promise.all([deskCall('/api/projets/'), deskCall('/api/employes/')]).then(([projectData, peopleData]) => {
        const projects = (projectData.projects ?? []) as { id: number; name: string }[]
        const people = (peopleData.employees ?? []) as { id: number; name: string; username: string }[]
        const zaina = people.find((person) => person.username === 'nouzou' || /zaina/i.test(person.name)) ?? people[0]
        setProjectsList(projects)
        setPeopleList(people)
        setDraft((prev) => ({ ...prev, project: prev.project || String(projects[0]?.id ?? ''), employee: prev.employee || String(zaina?.id ?? '') }))
      }).catch(() => undefined)
    }
  }, [role, stamp])
  const shown = rows.filter((task) => (tab === 'Toutes' || task.status === (tab === 'Terminées' ? 'Terminée' : tab)) && `${task.title} ${task.project} ${task.who}`.toLowerCase().includes(query.toLowerCase()))
  const chips = [
    ['Toutes', String(rows.length)],
    ['À faire', String(rows.filter((item) => item.status === 'À faire').length)],
    ['En cours', String(rows.filter((item) => item.status === 'En cours').length)],
    ['Terminées', String(rows.filter((item) => item.status === 'Terminée').length)],
    ['En retard', String(rows.filter((item) => item.status === 'En retard').length)],
  ]
  async function act(id: string, status: string) {
    const data = await deskCall(`/api/taches/${id.slice(1)}/statut/`, { method: 'POST', body: JSON.stringify({ status }) })
    setNote(data.message || 'Statut enregistré.')
    setStamp((value) => value + 1)
  }
  async function removeTask(id: string, title: string) {
    if (!window.confirm(`Supprimer la tâche « ${title} » ?`)) return
    const data = await deskCall(`/api/taches/${id.slice(1)}/`, { method: 'POST', body: JSON.stringify({ delete: true }) })
    setNote(data.message || 'Tâche supprimée.')
    setPicked('')
    setStamp((value) => value + 1)
  }
  async function deposit(id: string, list: FileList | null) {
    const file = list?.[0]
    if (!file) return
    const body = new FormData()
    body.set('result', file)
    const data = await deskCall(`/api/taches/${id.slice(1)}/resultat/`, { method: 'POST', body })
    setNote(data.message || 'Fichier envoyé.')
    setStamp((value) => value + 1)
  }
  async function createTask(event: FormEvent) {
    event.preventDefault()
    const body = new FormData()
    body.set('title', draft.title)
    body.set('project', draft.project)
    body.set('employee', draft.employee)
    body.set('priority', draft.priority)
    body.set('due_date', draft.due)
    const data = await deskCall('/api/taches/', { method: 'POST', body })
    setNote(data.message || 'Tâche attribuée.')
    setComposer(false)
    setDraft((prev) => ({ ...prev, title: '' }))
    setStamp((value) => value + 1)
  }
  if (role === 'employee') {
    const current = rows.find((task) => task.code === picked) ?? rows.find((task) => task.status !== 'Terminée') ?? rows[0]
    const stateLabel = current?.status === 'À faire' ? 'Non commencé' : current?.status ?? ''
    return (
      <section className="emp-task">
        {current ? (
          <>
            <div className="emp-task-top">
              <div>
                <p className="emp-task-kicker">Détail de ma tâche · {current.code.replace('#', '#TSK-')}</p>
                <h1>{current.title}</h1>
                <p className="emp-task-lead">Consultez les informations, mettez à jour votre progression et déposez votre livrable.</p>
              </div>
              <span className="emp-task-status"><i /> {stateLabel}</span>
            </div>
            {rows.length > 1 ? (
              <div className="emp-task-switch">
                {rows.map((task) => <button key={task.code} className={task.code === current.code ? 'on' : ''} type="button" onClick={() => setPicked(task.code)}>{task.title}</button>)}
              </div>
            ) : null}
            {note ? <p className="emp-task-note">{note}</p> : null}
            <div className="emp-task-grid">
              <article className="emp-task-card">
                <h2>Description</h2>
                <h3>Objectif de la tâche</h3>
                <p>{current.description || 'Préparer et finaliser ce livrable pour assurer l’avancement du projet. Vérifiez les données, documentez les choix effectués et transmettez une version prête pour validation.'}</p>
                <div className="emp-task-meta">
                  <span><small>Projet</small><strong>{current.project}</strong></span>
                  <span><small>Échéance</small><strong>{formatFrenchDate(current.due) || current.due || '—'}</strong></span>
                  <span><small>Priorité</small><strong>{current.priority}</strong></span>
                  <span><small>Assignée à</small><strong>Zaina Zaina</strong></span>
                </div>
                {current.docs.map((document) => <a key={document.url} href={`${document.url}?telecharger=1`}>Télécharger le brief</a>)}
                {current.resultUrl ? <a href={current.resultUrl} target="_blank" rel="noopener">Voir le fichier déposé{current.resultName ? ` · ${current.resultName}` : ''}</a> : null}
              </article>
              <article className="emp-task-card emp-task-side">
                <h2>Progression</h2>
                <b>{current.progress}%</b>
                <p>{current.status === 'Terminée' ? 'La tâche est terminée.' : current.status === 'En cours' ? 'La tâche est en cours.' : 'Commencez la tâche lorsque vous êtes prêt.'}</p>
              </article>
            </div>
            <article className="emp-task-card emp-task-work">
              <h2>Actions</h2>
              <h3>Mettre à jour la tâche</h3>
              <p>Votre responsable sera automatiquement informé de chaque changement.</p>
              <div className="emp-task-actions">
                {current.status === 'À faire' || current.status === 'En retard' ? <button className="emp-task-go" type="button" onClick={() => { void act(current.code, 'in_progress') }}>→ Commencer</button> : null}
                <label className="emp-task-file">Déposer mon travail<input type="file" hidden onChange={(event) => { void deposit(current.code, event.target.files) }} /></label>
                {current.status !== 'Terminée' ? <button className="emp-task-done" type="button" onClick={() => { void act(current.code, 'completed') }}>Marquer comme terminée</button> : null}
              </div>
            </article>
          </>
        ) : <h1>Aucune tâche pour le moment</h1>}
      </section>
    )
  }
    return (
      <section className="lp">
        <LightHead kicker="Activités" title="Gestion des tâches" text="Assignez les priorités et suivez l’exécution des activités." action={role === 'admin' ? <button className="lp-btn" type="button" onClick={() => setComposer((value) => !value)}><Icon name="plus" size={14} /> Nouvelle tâche</button> : undefined} />
        {composer ? (
          <form className="lp-panel lp-form" onSubmit={(event) => { void createTask(event) }}>
            <div className="form-grid">
              <label>Tâche<input className="field" value={draft.title} onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))} required /></label>
              <label>Projet<select className="field" value={draft.project} onChange={(event) => setDraft((prev) => ({ ...prev, project: event.target.value }))}>{projectsList.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
              <label>Employé<select className="field" value={draft.employee} onChange={(event) => setDraft((prev) => ({ ...prev, employee: event.target.value }))}>{peopleList.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
              <label>Priorité<select className="field" value={draft.priority} onChange={(event) => setDraft((prev) => ({ ...prev, priority: event.target.value }))}><option value="medium">Moyenne</option><option value="high">Élevée</option><option value="urgent">Urgente</option><option value="low">Faible</option></select></label>
              <label>Échéance<input className="field" type="date" value={draft.due} onChange={(event) => setDraft((prev) => ({ ...prev, due: event.target.value }))} /></label>
            </div>
            <Button type="submit">Créer et attribuer</Button>
          </form>
        ) : null}
        {note ? <p className="lp-note">{note}</p> : null}
        <div className="lp-chips">
          {chips.map(([label, count]) => <button key={label} className={tab === label ? 'on' : ''} type="button" onClick={() => setTab(label)}>{label} <b>{count}</b></button>)}
        </div>
        <div className="lp-panel">
          <div className="lp-tools">
            <label><Icon name="search" size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher une tâche..." /></label>
            <button className="lp-filter" type="button">Filtres <b>2</b></button>
          </div>
          <table className="lp-table">
            <thead><tr><th>Tâche</th><th>Projet</th><th>Responsable</th><th>Priorité</th><th>Date limite</th><th>Statut</th><th>Progression</th><th></th></tr></thead>
            <tbody>
              {shown.map((task) => (
                <Fragment key={task.code}>
                <tr onClick={() => setPicked(task.code)} style={{ cursor: 'pointer' }}>
                  <td><strong>{task.title}</strong><small>{task.code}</small>{task.resultUrl ? <a className="lp-open" href={task.resultUrl} target="_blank" rel="noopener" onClick={(event) => event.stopPropagation()}>Ouvrir le travail{task.resultName ? ` · ${task.resultName}` : ''}</a> : null}</td>
                  <td className="link">{task.project}</td>
                  <td><span className="lp-person"><b className={task.tone}>{task.initials}</b><span>{task.who}</span></span></td>
                  <td><em className={task.priority === 'Élevée' ? 'bad' : task.priority === 'Moyenne' ? 'warn' : 'muted-pill'}>{task.priority}</em></td>
                  <td>{task.due}</td>
                  <td><em className={task.status === 'Terminée' ? 'ok' : task.status === 'En retard' ? 'bad' : task.status === 'À faire' ? 'wait' : 'info'}>{task.status}</em></td>
                  <td><span className="lp-mini"><i style={{ width: `${task.progress}%` }} /></span> {task.progress}%</td>
                  <td>
                    <button type="button" aria-label="Actions" onClick={(event) => { event.stopPropagation(); setPicked(picked === task.code ? '' : task.code) }}>•••</button>
                    <button type="button" onClick={(event) => { event.stopPropagation(); void removeTask(task.code, task.title) }}>Supprimer</button>
                  </td>
                </tr>
                {picked === task.code ? (
                  <tr key={`${task.code}-actions`}>
                    <td colSpan={8}>
                      {task.docs.map((document) => <a key={document.url} href={`${document.url}?telecharger=1`}>Télécharger le brief</a>)}
                      {task.resultUrl ? <a className="lp-btn" href={task.resultUrl} target="_blank" rel="noopener">Ouvrir le document déposé</a> : <span className="muted">Aucun travail déposé.</span>}
                      <Button danger onClick={() => { void removeTask(task.code, task.title) }}>Supprimer</Button>
                    </td>
                  </tr>
                ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    )
}

function properName(value: string) {
  return value.replace(/\S+/g, (word) => word.charAt(0).toLocaleUpperCase('fr-FR') + word.slice(1))
}

function lead(value: string) {
  const text = value.trim()
  return text ? text.charAt(0).toLocaleUpperCase('fr-FR') + text.slice(1) : text
}

function TodosPage({ role, focusEmployee = '' }: { role: Role; staff: Staff[]; plans: DayPlan[]; username: string; assigned: AssignedTask[]; focusEmployee?: string }) {
  const [draft, setDraft] = useState('')
  const [link, setLink] = useState('')
  const [links, setLinks] = useState<{ id: number; title: string }[]>([])
  const [stamp, setStamp] = useState(0)
  const [note, setNote] = useState('')
  const [noteOk, setNoteOk] = useState(true)
  const [sent, setSent] = useState(false)
  const [revised, setRevised] = useState(false)
  const [sentAt, setSentAt] = useState('')
  const [openId, setOpenId] = useState(focusEmployee)
  const [board, setBoard] = useState<{ employee: { id: number; name: string; initials: string }; sent: boolean; sentAt: string; items: { id: number; title: string; project: string; priority_label: string; status_label: string }[] }[]>([])
  const draftRef = useRef<HTMLInputElement>(null)
  const todayLabel = new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: '2-digit', month: 'long' })
  const [sort, setSort] = useState<'time' | 'priority'>('time')
  const [plan, setPlan] = useState<{ id: string; time: string; title: string; project: string; priority: string; tone: string; done: boolean }[]>([])
  useEffect(() => { if (focusEmployee) setOpenId(focusEmployee) }, [focusEmployee])
  useEffect(() => {
    deskCall('/api/todos/').then((data) => {
      if (role === 'admin') {
        const rows = (data.board ?? []) as { employee: { id: number; name: string; initials: string }; sent: boolean; sent_at: string; items: { id: number; title: string; project: string; priority_label: string; status_label: string }[] }[]
        setBoard(rows.map((row) => ({ employee: row.employee, sent: row.sent, sentAt: row.sent_at || '', items: row.items || [] })))
        return
      }
      setSent(Boolean(data.sent))
      setRevised(Boolean(data.revised))
      setSentAt(String(data.sent_at || ''))
      const rows = (data.items ?? []) as { id: number; title: string; project: string; priority_label: string; status: string }[]
      setPlan(rows.map((item) => ({
        id: String(item.id),
        time: '—',
        title: item.title,
        project: item.project || 'Ma journée',
        priority: item.priority_label === 'Haute' ? 'Élevée' : item.priority_label || 'Moyenne',
        tone: item.priority_label === 'Haute' || item.priority_label === 'Urgente' ? 'bad' : 'warn',
        done: item.status === 'completed',
      })))
    }).catch(() => undefined)
    if (role === 'employee') {
      deskCall('/api/taches/').then((data) => {
        setLinks(((data.tasks ?? []) as { id: number; title: string; planned_date: string; due_date: string }[]).filter((item) => item.due_date || !item.planned_date).map((item) => ({ id: item.id, title: item.title })))
      }).catch(() => undefined)
    }
  }, [role, stamp])
  async function addTodo() {
    if (role !== 'employee') return
    const title = draft.trim()
    if (title.length < 2) {
      setNoteOk(false)
      setNote('Écrivez l’activité dans le champ, puis cliquez sur Ajouter.')
      draftRef.current?.focus()
      return
    }
    try {
      await openSession()
      const data = await deskCall('/api/todos/', { method: 'POST', body: JSON.stringify({ title, task: link }) })
      setNoteOk(true)
      setNote(data.message || 'Activité ajoutée.')
      setDraft('')
      setLink('')
      setStamp((value) => value + 1)
    } catch (error) {
      setNoteOk(false)
      setNote(error instanceof Error ? error.message : 'Impossible d’ajouter l’activité.')
    }
  }
  async function sendTodo() {
    if (role !== 'employee') return
    if (plan.length === 0) {
      setNoteOk(false)
      setNote('Ajoutez au moins une activité avant d’envoyer la Todo List.')
      draftRef.current?.focus()
      return
    }
    try {
      await openSession()
      const data = await deskCall('/api/todos/', { method: 'POST', body: JSON.stringify({ send: true }) })
      setNoteOk(true)
      setNote(data.message || 'Todo List envoyée au responsable.')
      setStamp((value) => value + 1)
    } catch (error) {
      setNoteOk(false)
      setNote(error instanceof Error ? error.message : 'Impossible d’envoyer la Todo List.')
    }
  }
  async function toggleTodo(item: { id: string; done: boolean }) {
    if (!/^\d+$/.test(item.id)) return
    await deskCall(`/api/taches/${item.id}/statut/`, { method: 'POST', body: JSON.stringify({ status: item.done ? 'todo' : 'completed' }) })
    setStamp((value) => value + 1)
  }
    const weight = (priority: string) => priority === 'Élevée' ? 0 : priority === 'Moyenne' ? 1 : 2
    const ordered = sort === 'time' ? plan : [...plan].sort((a, b) => weight(a.priority) - weight(b.priority))
    const doneCount = plan.filter((item) => item.done).length
    const ratio = plan.length ? Math.round((doneCount / plan.length) * 100) : 0
    const sendLabel = sent && revised ? 'Renvoyer la Todo List' : sent ? 'Envoyée au responsable' : 'Valider et envoyer'
    if (role === 'admin') {
      const sheet = board.find((row) => String(row.employee.id) === openId)
      if (sheet) {
        const personName = properName(sheet.employee.name)
        const when = sheet.sentAt.includes(' ') ? `Reçue le ${sheet.sentAt.replace(' ', ' à ')}` : 'Pas encore envoyée'
        return (
          <section className="lp">
            <LightHead kicker={todayLabel} title={`Todo List de ${personName}`} text={sheet.sent ? `${when} · ${sheet.items.length} activité${sheet.items.length > 1 ? 's' : ''}` : 'Cette Todo List n’a pas encore été envoyée.'} action={<button className="lp-btn light" type="button" onClick={() => setOpenId('')}>Retour</button>} />
            <article className="lp-panel todo-sheet">
              <header className="todo-who">
                <b>{sheet.employee.initials || personName.slice(0, 2).toUpperCase()}</b>
                <div>
                  <strong>{personName}</strong>
                  <small>Employée · {todayLabel}</small>
                </div>
                <em className={sheet.sent ? 'ok' : 'wait'}>{sheet.sent ? 'Reçue' : 'Non reçue'}</em>
              </header>
              <div className="todo-facts">
                <span><b>{sheet.items.length}</b> activité{sheet.items.length > 1 ? 's' : ''}</span>
                <span>{sheet.sent ? when : 'En attente d’envoi'}</span>
              </div>
              {sheet.items.length === 0 ? <p className="muted todo-empty">Aucune activité dans cette Todo List.</p> : null}
              {sheet.items.map((item, index) => (
                <div className="lp-line" key={item.id}>
                  <b className="todo-idx">{String(index + 1).padStart(2, '0')}</b>
                  <span><strong>{lead(item.title)}</strong><small>{item.project || 'Journée'}</small></span>
                  <em className="info">{item.priority_label || 'Moyenne'}</em>
                  <em className={item.status_label === 'Terminée' ? 'ok' : 'wait'}>{item.status_label || 'Non commencée'}</em>
                </div>
              ))}
            </article>
          </section>
        )
      }
      const received = board.filter((row) => row.sent).length
      return (
        <section className="lp">
          <LightHead kicker={todayLabel} title="Todo Lists du jour" text="Ouvrez la liste transmise par chaque employé." />
          <div className="lp-stats">
            <span><i className="ok" /><b>{received}</b> reçue{received > 1 ? 's' : ''}</span>
            <span><i className="warn" /><b>{board.length - received}</b> en attente</span>
          </div>
          <article className="lp-panel">
            <header><div><h2>Réception</h2><p>Todo Lists transmises aujourd’hui</p></div></header>
            {board.map((row) => (
              <button className="lp-act" type="button" key={row.employee.id} onClick={() => setOpenId(String(row.employee.id))}>
                <span className="lp-person"><b>{row.employee.initials || row.employee.name.slice(0, 2).toUpperCase()}</b></span>
                <span className="grow"><strong>{properName(row.employee.name)}</strong><small>{row.sent ? `${row.items.length} activité${row.items.length > 1 ? 's' : ''}` : 'Todo List non envoyée'}</small></span>
                <em className={row.sent ? 'ok' : 'wait'}>{row.sent ? 'Reçue' : 'Non reçue'}</em>
                <time>{row.sent ? row.sentAt : '—'}</time>
                <Icon name="chevron" size={16} />
              </button>
            ))}
          </article>
        </section>
      )
    }
    return (
      <section className="lp">
        <LightHead kicker={todayLabel} title="Ma Todo List du jour" text="Organisez votre journée, puis envoyez la liste au responsable." action={<button className="lp-btn" type="button" disabled={sent && !revised} onClick={() => { void sendTodo() }}><Icon name="check" size={14} /> {sendLabel}</button>} />
        {note ? <p className={`lp-note${noteOk ? '' : ' bad'}`}>{note}</p> : null}
        <div className="lp-todo">
          <div>
            <div className="lp-banner">
              <span><Icon name="check" size={16} /> <b>{doneCount} / {plan.length} tâches terminées</b><small>Vous avancez très bien, continuez ainsi.</small></span>
              <strong>{ratio}%</strong>
              <i><b style={{ width: `${ratio}%` }} /></i>
            </div>
            <article className="lp-panel">
              <header>
                <div><h2>Planning du jour</h2><p>Vos activités planifiées</p></div>
                <button type="button" onClick={() => setSort((current) => current === 'time' ? 'priority' : 'time')}>Trier</button>
              </header>
              {ordered.map((item) => (
                  <div className={`lp-line${item.done ? ' on' : ''}`} key={item.id}>
                    <button type="button" aria-label={item.title} onClick={() => { void toggleTodo(item) }}>{item.done ? <Icon name="check" size={12} /> : null}</button>
                    <time>{item.time}</time>
                    <span><strong>{item.title}</strong><small>{item.project}</small></span>
                    <em className={item.tone}>{item.priority}</em>
                    <button className="lp-more" type="button" aria-label="Terminer" onClick={() => { void toggleTodo(item) }}>•••</button>
                  </div>
              ))}
              {role === 'employee' ? (
              <>
              {sent && !revised ? <p className="todo-sent">Todo List envoyée au responsable{sentAt ? ` le ${sentAt}` : ''}.</p> : null}
              <form className="lp-add" onSubmit={(event) => { event.preventDefault(); void addTodo() }}>
                <input ref={draftRef} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Écrire l’activité du jour..." />
                <select value={link} onChange={(event) => setLink(event.target.value)} aria-label="Lier à une tâche">
                  <option value="">Sans lien</option>
                  {links.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
                </select>
                <button className="lp-btn" type="submit">Ajouter</button>
              </form>
              </>
              ) : null}
            </article>
          </div>
          <aside className="lp-advice">
            <span><Icon name="spark" size={16} /></span>
            <small>Conseil IA</small>
            <h2>Votre priorité du jour</h2>
            <p>Concentrez-vous sur le modèle prédictif avant 12 h. Cette tâche bloque deux activités du projet.</p>
            <button type="button">Voir la tâche →</button>
          </aside>
        </div>
      </section>
    )
}

function formatSize(bytes: number) {
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1).replace('.', ',')} Mo`
  return `${Math.max(1, Math.round(bytes / 1024))} Ko`
}

function blobUrlFromData(dataUrl: string) {
  const comma = dataUrl.indexOf(',')
  const mime = /data:([^;,]+)/.exec(dataUrl.slice(0, comma))?.[1] || 'application/octet-stream'
  const binary = atob(dataUrl.slice(comma + 1))
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
  return URL.createObjectURL(new Blob([bytes], { type: mime }))
}

function openableUrl(url?: string) {
  if (!url) return ''
  return url.startsWith('data:') ? blobUrlFromData(url) : url
}

function openInBrowser(file: { name: string; url?: string; html?: string; kind?: string }) {
  if (file.html && file.kind !== 'PDF') {
    const title = file.name.replace(/[&<>"]/g, '')
    const page = `<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>${title}</title><style>body{font-family:Georgia,serif;max-width:760px;margin:40px auto;padding:0 16px;line-height:1.55;color:#10283f}img{max-width:100%}</style></head><body>${file.html}</body></html>`
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([page], { type: 'text/html' }))
    link.target = '_blank'
    link.rel = 'noopener'
    document.body.appendChild(link)
    link.click()
    link.remove()
    return
  }
  const href = openableUrl(file.url)
  if (!href) return
  const link = document.createElement('a')
  link.href = href
  link.target = '_blank'
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

function FileViewer({ file }: { file?: { name: string; url?: string; html?: string; kind?: string } | null }) {
  const src = useMemo(() => openableUrl(file?.url), [file?.url])
  if (!file) return null
  if (src && file.kind !== 'DOC') return <iframe className="doc-frame" title={file.name} src={src} />
  if (file.html) return <div className="doc-preview doc-html" dangerouslySetInnerHTML={{ __html: file.html }} />
  return <p className="empty">Aucun fichier joint. Il pourra être ouvert ici dès qu'il aura été importé.</p>
}

const dailyReports = [
  { initials: 'AK', tone: 'violet', name: 'Aïcha Konaté', role: 'Data Analyst', date: '09 juin 2025', project: 'Nova Analytics', status: 'Soumis', time: '17:20', tasks: '6 tâches' },
  { initials: 'MD', tone: 'blue', name: 'Moussa Diallo', role: 'Développeur Full Stack', date: '09 juin 2025', project: 'Portail Finance', status: 'Soumis', time: '16:21', tasks: '5 tâches' },
  { initials: 'SN', tone: 'orange', name: 'Sarah N’Guessan', role: 'UX/UI Designer', date: '09 juin 2025', project: 'Mobile Banking', status: 'Brouillon', time: '—', tasks: '4 tâches' },
  { initials: 'IT', tone: 'green', name: 'Ibrahim Traoré', role: 'Data Engineer', date: '09 juin 2025', project: 'Nova Analytics', status: 'Soumis', time: '14:23', tasks: '3 tâches' },
  { initials: 'FN', tone: 'pink', name: 'Fatou Ndiaye', role: 'Cheffe de projet', date: '09 juin 2025', project: 'Portail Finance', status: 'Soumis', time: '13:24', tasks: '2 tâches' },
]

function EmployeeReportPage() {
  const picker = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)
  const [history, setHistory] = useState<{ date: string; name: string; time: string; url?: string }[]>([])
  const today = new Date().toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })
  useEffect(() => {
    deskCall('/api/rapports/').then((data) => {
      const rows = (data.reports ?? []) as { date: string; name: string; sent_at: string; url: string }[]
      setHistory(rows.map((item) => ({ date: item.date, name: item.name, time: item.sent_at, url: item.url })))
    }).catch(() => undefined)
  }, [sent])
  function take(list: FileList | null) {
    const picked = list?.[0]
    if (picker.current) picker.current.value = ''
    if (!picked) return
    if (!/\.(pdf|docx)$/i.test(picked.name)) {
      setError('Formats acceptés : PDF ou DOCX.')
      return
    }
    if (picked.size > 10 * 1024 * 1024) {
      setError('Le fichier dépasse 10 Mo.')
      return
    }
    setFile(picked)
    setError('')
    setSent(false)
  }
  function downloadTemplate() {
    const text = 'Rapport journalier\n\nDate :\nActivités réalisées :\nDifficultés rencontrées :\nBesoins :\n'
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
    link.download = 'modele-rapport-journalier.txt'
    link.click()
  }
  async function submit() {
    if (!file) {
      setError('Importez votre rapport avant de l’envoyer à Amadou.')
      return
    }
    const body = new FormData()
    body.set('file', file)
    try {
      const data = await deskCall('/api/rapports/', { method: 'POST', body })
      setSent(true)
      setError('')
      setMessage(data.message || 'Rapport envoyé.')
      setHistory((prev) => [{ date: data.report.date, name: data.report.name, time: data.report.sent_at, url: data.report.url }, ...prev])
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Envoi impossible.')
    }
  }
  return (
    <section className="lp my-report">
      <LightHead
        kicker=""
        title="Mon rapport journalier"
        text="Importez votre compte rendu et transmettez-le directement à votre responsable."
        action={<button className="lp-btn" type="button" onClick={downloadTemplate}><Icon name="download" size={14} /> Télécharger le modèle</button>}
      />
      <div className="my-report-grid">
        <article>
          <div className="my-report-top">
            <div>
              <h2>Rapport du {today}</h2>
              <p>Formats acceptés : PDF ou DOCX · 10 Mo maximum</p>
            </div>
            <em className={sent ? 'ok' : 'wait'}>{sent ? 'Soumis' : 'Brouillon'}</em>
          </div>
          <button
            className="my-drop"
            type="button"
            onClick={() => picker.current?.click()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => { event.preventDefault(); take(event.dataTransfer.files) }}
          >
            <span><Icon name="download" size={18} /></span>
            <strong>{file ? file.name : 'Importez votre rapport de la journée'}</strong>
            <small>{file ? formatSize(file.size) : 'Cliquez pour sélectionner un fichier depuis votre appareil'}</small>
          </button>
          <input ref={picker} type="file" accept=".pdf,.docx,.txt,application/pdf,text/plain" hidden onChange={(event) => take(event.target.files)} />
          <label className="my-note">
            <span>Message pour votre responsable <em>Optionnel</em></span>
            <textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ajoutez un contexte, une difficulté ou une information importante..." />
          </label>
          {error ? <p className="my-error">{error}</p> : null}
          {sent ? <p className="my-ok">Rapport transmis à Amadou Mensah.</p> : null}
          <footer>
            <small><Icon name="shield" size={14} /> Visible uniquement par votre responsable</small>
            <button className="lp-btn" type="button" onClick={() => { void submit() }}><Icon name="send" size={14} /> Envoyer à Amadou</button>
          </footer>
        </article>
        <aside>
          <h2>Derniers rapports</h2>
          <p>Votre historique récent</p>
          {history.map((item) => (
            <a className="my-history" key={`${item.date}-${item.name}`} href={item.url || undefined}>
              <span><Icon name="file" size={16} /></span>
              <div><strong>{item.date}</strong><small>{item.name}</small></div>
              <em><b>Soumis</b><small>{item.time}</small></em>
            </a>
          ))}
        </aside>
      </div>
    </section>
  )
}

function ReportsPage({ library }: { staff: Staff[]; library: ReportFile[] }) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('Tous')
  const [note, setNote] = useState('')
  const [opened, setOpened] = useState<ReportFile | null>(null)
  const [live, setLive] = useState<(typeof dailyReports[number] & { url?: string })[] | null>(null)
  useEffect(() => {
    deskCall('/api/rapports/').then((data) => {
      const reports = (data.reports ?? []) as { name: string; username: string; submitted: boolean; filename: string; url: string; sent_at: string }[]
      setLive(reports.map((item) => ({
        initials: item.name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase() || '—',
        tone: 'violet',
        name: item.name,
        role: item.username,
        date: String(data.date || ''),
        project: item.filename || '—',
        status: item.submitted ? 'Soumis' : 'Manquant',
        time: item.sent_at || '—',
        tasks: item.filename || '—',
        url: item.url,
      })))
    }).catch(() => undefined)
  }, [])
  const source = (live ?? dailyReports) as (typeof dailyReports[number] & { url?: string })[]
  const received = source.filter((item) => item.status === 'Soumis').length
  const ratio = source.length ? Math.round((received / source.length) * 100) : 0
  const rows = source.filter((item) => {
    const blob = `${item.name} ${item.project} ${item.role}`.toLowerCase()
    return blob.includes(query.toLowerCase()) && (status === 'Tous' || item.status === status)
  })
  function exportReports() {
    const text = ['Employé;Date;Projet;Statut;Soumis à;Activités', ...rows.map((item) => `${item.name};${item.date};${item.project};${item.status};${item.time};${item.tasks}`)].join('\n')
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
    link.download = 'rapports-journaliers.txt'
    link.click()
  }
  function openReport(name: string, url?: string) {
    if (url) {
      window.open(url, '_blank', 'noopener')
      return
    }
    const file = library.find((item) => item.url || item.html) ?? null
    setOpened(file)
    if (file) openInBrowser(file)
    else setNote(`Rapport de ${name}`)
  }
  return (
    <section className="lp">
      <LightHead kicker="Suivi quotidien" title="Rapports journaliers" text="Centralisez et analysez les comptes rendus de vos équipes." action={<button className="lp-btn" type="button" onClick={exportReports}><Icon name="download" size={14} /> Exporter les rapports</button>} />
      <div className="lp-day">
        <span className="lp-folder"><Icon name="file" size={16} /></span>
        <div>
          <small>Rapports du jour</small>
          <strong>{received} rapports reçus sur {source.length}</strong>
          <i><b style={{ width: `${ratio}%` }} /></i>
        </div>
        <b>{ratio}%</b>
        <button type="button" onClick={() => setNote('Les 9 employés ont été relancés.')}>Relancer les 9 employés <Icon name="send" size={14} /></button>
      </div>
      {note ? <p className="lp-note">{note}</p> : null}
      <div className="lp-panel">
        <div className="lp-tools">
          <label><Icon name="search" size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher un rapport..." /></label>
          <button className="lp-filter" type="button" onClick={() => setStatus(status === 'Tous' ? 'Soumis' : status === 'Soumis' ? 'Brouillon' : 'Tous')}>Filtres <b>2</b></button>
        </div>
        <table className="lp-table">
          <thead><tr><th>Employé</th><th>Date</th><th>Projet</th><th>Statut</th><th>Soumis à</th><th>Activités</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.name}>
                <td><span className="lp-person"><b className={item.tone}>{item.initials}</b><span><strong>{item.name}</strong><small>{item.role}</small></span></span></td>
                <td>{item.date}</td>
                <td className="link">{item.project}</td>
                <td><em className={item.status === 'Soumis' ? 'ok' : 'warn'}>{item.status}</em></td>
                <td className="muted">{item.time}</td>
                <td>{item.tasks}</td>
                <td className="lp-actions">
                  <button type="button" aria-label="Voir" onClick={() => openReport(item.name, item.url)}><Icon name="eye" size={14} /></button>
                  <button type="button" aria-label="Télécharger" onClick={() => { if (item.url) window.open(item.url, '_blank', 'noopener'); else exportReports() }}><Icon name="download" size={14} /></button>
                  <button type="button" aria-label="Actions">•••</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {opened ? <FileViewer file={opened} /> : null}
      </div>
    </section>
  )
}

type Note = { id: number; author: 'admin' | 'employee'; text: string; file?: ProjectFile }
type Account = { username: string; email: string; password: string; first: string; last: string }

const zainaThread: Note[] = [
  { id: 1, author: 'employee', text: 'bonjour monsieur' },
  { id: 2, author: 'admin', text: 'bonjour passe a mon bureau' },
  { id: 3, author: 'admin', text: 'Pièce jointe : TODO_LIST.pdf' },
  { id: 4, author: 'admin', text: 'passe a mon bureau' },
  { id: 5, author: 'admin', text: 'cc' },
  { id: 6, author: 'admin', text: 'cc' },
  { id: 7, author: 'employee', text: 'passe' },
]

function attachmentKind(name: string) {
  const lower = name.toLowerCase()
  if (lower.endsWith('.pdf')) return 'PDF'
  if (/\.(jpe?g|png|webp|gif)$/.test(lower)) return 'Image'
  if (lower.endsWith('.doc') || lower.endsWith('.docx')) return 'DOC'
  if (lower.endsWith('.xls') || lower.endsWith('.xlsx')) return 'Excel'
  if (lower.endsWith('.txt')) return 'Texte'
  return ''
}

function readDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

type MailNote = { id: number; mine: boolean; text: string; time: string; file?: ProjectFile }
type MailThread = {
  id: string
  name: string
  initials: string
  tone: string
  role: string
  online: boolean
  time: string
  unread: number
  project: string
  progress: string
  files: { name: string; meta: string }[]
  messages: MailNote[]
}

function MessagingPage({ role, focus = '' }: { role: Role; focus?: string }) {
  const [active, setActive] = useState(focus)
  const [mailbox, setMailbox] = useState<MailThread[]>([])
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [stamp, setStamp] = useState(0)
  const [draft, setDraft] = useState('')
  const [attachment, setAttachment] = useState<ProjectFile | null>(null)
  const [fileError, setFileError] = useState('')
  const picker = useRef<HTMLInputElement>(null)
  const stream = useRef<HTMLDivElement>(null)
  const activeRef = useRef(active)
  activeRef.current = active
  useEffect(() => { if (focus) setActive(focus) }, [focus])
  useEffect(() => {
    let stop = false
    async function pull() {
      const chosen = activeRef.current
      if (role === 'employee') {
        const data = await deskCall('/api/messages/')
        const contact = (data.contact ?? {}) as { name?: string; initials?: string }
        const messages = (data.messages ?? []) as { id: number; mine: boolean; text: string; at: string }[]
        if (stop) return
        setMailbox([{
          id: 'boss',
          name: properName(contact.name || 'Amadou Mensah'),
          initials: contact.initials || 'AM',
          tone: 'blue',
          role: 'Responsable',
          online: true,
          time: messages.at(-1)?.at || '',
          unread: 0,
          project: '',
          progress: '',
          files: [],
          messages: messages.map((item) => ({ id: item.id, mine: item.mine, text: item.text, time: item.at })),
        }])
        setActive('boss')
        return
      }
      const data = await deskCall(chosen ? `/api/messages/?with=${chosen}` : '/api/messages/')
      const people = (data.contacts ?? []) as { id: number; name: string; initials: string; preview: string; time: string; unread: number }[]
      const openMessages = (data.messages ?? []) as { id: number; mine: boolean; text: string; at: string }[]
      if (stop) return
      const preferred = chosen || String(people[0]?.id ?? '')
      setMailbox(people.map((person, index) => ({
        id: String(person.id),
        name: properName(person.name),
        initials: person.initials || person.name.slice(0, 2).toUpperCase(),
        tone: ['blue', 'violet', 'green', 'orange', 'pink'][index % 5],
        role: 'Employé',
        online: true,
        time: String(person.id) === preferred ? (openMessages.at(-1)?.at || person.time) : person.time,
        unread: String(person.id) === preferred ? 0 : person.unread,
        project: '',
        progress: '',
        files: [],
        messages: String(person.id) === preferred
          ? openMessages.map((item) => ({ id: item.id, mine: item.mine, text: item.text, time: item.at }))
          : (person.preview ? [{ id: person.id, mine: false, text: person.preview, time: person.time }] : []),
      })))
      if (preferred) setActive(preferred)
    }
    pull().catch((error: unknown) => { if (!stop) setFileError(error instanceof Error ? error.message : 'Messagerie indisponible.') })
    const timer = window.setInterval(() => { pull().catch(() => undefined) }, 4000)
    return () => { stop = true; window.clearInterval(timer) }
  }, [role, stamp, focus, active])
  const visible = mailbox.filter((item) => {
    const matches = item.name.toLowerCase().includes(query.trim().toLowerCase())
    if (!matches) return false
    if (filter === 'unread') return item.unread > 0
    return true
  })
  const opened = mailbox.find((item) => item.id === active) ?? visible[0] ?? mailbox[0]
  const unreadTotal = mailbox.filter((item) => item.unread > 0).length
  useEffect(() => { setAttachment(null) }, [opened?.id])
  useEffect(() => {
    const node = stream.current
    if (node) node.scrollTop = node.scrollHeight
  }, [opened?.messages.length, opened?.id])
  async function takeAttachment(list: FileList | null) {
    const picked = list?.[0]
    if (picker.current) picker.current.value = ''
    if (!picked) return
    const kind = attachmentKind(picked.name)
    if (!kind) {
      setFileError('Formats acceptés : PDF, image, Word, Excel ou texte.')
      return
    }
    if (picked.size > 10 * 1024 * 1024) {
      setFileError('Le fichier dépasse 10 Mo.')
      return
    }
    let html = ''
    if (picked.name.toLowerCase().endsWith('.docx')) {
      const mammoth = await import('mammoth')
      const result = await mammoth.convertToHtml({ arrayBuffer: await picked.arrayBuffer() })
      html = result.value
    }
    const url = await readDataUrl(picked)
    setAttachment({ name: picked.name, kind, size: formatSize(picked.size), url, html: html || undefined })
    setFileError('')
  }
  async function send() {
    if (!opened) return
    const text = draft.trim()
    const payload = text || (attachment ? `Pièce jointe : ${attachment.name}` : '')
    if (!payload) return
    try {
      await openSession()
      if (role === 'employee') await deskCall('/api/messages/', { method: 'POST', body: JSON.stringify({ text: payload }) })
      else await deskCall('/api/messages/', { method: 'POST', body: JSON.stringify({ text: payload, with: opened.id }) })
      setDraft('')
      setAttachment(null)
      setFileError('')
      setStamp((value) => value + 1)
    } catch (error) {
      setFileError(error instanceof Error ? error.message : 'Le message n’a pas été envoyé.')
    }
  }
  return (
    <section className="team-mail">
      <header className="team-mail-head">
        <div>
          {role === 'employee' ? null : <span>Communication</span>}
          <h1>{role === 'employee' ? 'Messagerie avec mon responsable' : 'Messagerie d’équipe'}</h1>
          <p>{role === 'employee' ? 'Un canal privé et direct avec Amadou Mensah, votre responsable.' : 'Échangez avec votre équipe et centralisez les décisions importantes.'}</p>
        </div>
        {role === 'employee' ? null : <button className="lp-btn" type="button" onClick={() => document.getElementById('team-search')?.focus()}><Icon name="plus" size={14} /> Nouvelle discussion</button>}
      </header>
      <div className="team-board">
        <aside className="team-list">
          <label className="team-search">
            <Icon name="search" size={14} />
            <input id="team-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher une conversation..." />
          </label>
          <div className="team-filters">
            <button className={filter === 'all' ? 'on' : ''} type="button" onClick={() => setFilter('all')}>Toutes <b>{mailbox.length}</b></button>
            <button className={filter === 'unread' ? 'on' : ''} type="button" onClick={() => setFilter('unread')}>Non lues <b>{unreadTotal}</b></button>
          </div>
          <div className="team-scroll">
            {visible.map((item) => (
              <button className={`team-row${item.id === opened?.id ? ' on' : ''}`} type="button" key={item.id} onClick={() => setActive(item.id)}>
                <span className={`tm-av ${item.tone}`}>{item.initials}{item.online ? <i /> : null}</span>
                <span>
                  <span className="team-row-top"><strong>{item.name}</strong><time>{item.time}</time></span>
                  <span className="team-row-bot"><em>{item.messages.at(-1)?.text || 'Aucun message'}</em>{item.unread ? <b>{item.unread}</b> : null}</span>
                </span>
              </button>
            ))}
          </div>
        </aside>
        {opened ? (
          <section className="team-thread">
            <header>
              <span className={`tm-av ${opened.tone}`}>{opened.initials}{opened.online ? <i /> : null}</span>
              <span>
                <strong>{opened.name}</strong>
                <small className={opened.online ? 'live' : ''}>{role === 'employee' ? 'Conversation privée' : 'En ligne'}</small>
              </span>
              {role === 'employee' ? <span className="team-secure"><i /> Sécurisée</span> : <span className="team-tools"><Icon name="search" size={15} /><Icon name="list" size={15} /></span>}
            </header>
            <div className="team-stream" ref={stream}>
              <p className="team-day">Aujourd’hui</p>
              {opened.messages.map((message) => (
                <div className={`team-bubble${message.mine ? ' me' : ''}`} key={message.id}>
                  {message.mine ? null : <span className={`tm-av sm ${opened.tone}`}>{opened.initials}</span>}
                  <span>
                    <p>{message.text}</p>
                    {message.file ? <small>{message.file.name}</small> : null}
                    <time>{message.time}{role === 'employee' && message.mine && message.id === opened.messages.filter((entry) => entry.mine).at(-1)?.id ? ' · Lu' : ''}</time>
                  </span>
                </div>
              ))}
              {opened.online ? <p className="team-typing"><i /><i /><i /> {opened.name} est en ligne</p> : null}
            </div>
            {attachment ? <p className="team-file">Pièce jointe : {attachment.name} <button type="button" onClick={() => setAttachment(null)}>Retirer</button></p> : null}
            {fileError ? <p className="team-file err">{fileError}</p> : null}
            <form onSubmit={(event) => { event.preventDefault(); void send() }}>
              <input ref={picker} type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.doc,.docx,.xls,.xlsx,.txt,application/pdf,image/*" hidden onChange={(event) => { void takeAttachment(event.target.files) }} />
              <button type="button" aria-label="Joindre un fichier" onClick={() => picker.current?.click()}><Icon name="plus" size={16} /></button>
              <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={role === 'employee' ? 'Écrivez à Amadou Mensah...' : 'Écrivez votre message...'} />
              <button className="send" type="submit" aria-label="Envoyer"><Icon name="send" size={16} /></button>
            </form>
            {role === 'employee' ? (
              <p className="team-file">
                <button type="button" onClick={() => { void deskCall('/api/messages/', { method: 'POST', body: JSON.stringify({ kind: 'meeting' }) }).then(() => setDraft('Demande de rendez-vous envoyée.')) }}>Demander un rendez-vous</button>
                <button type="button" onClick={() => { const description = draft.trim(); if (description.length < 5) { setFileError('Décrivez le problème dans le message (5 caractères minimum), puis cliquez sur Signaler.'); return }; void deskCall('/api/difficultes/', { method: 'POST', body: JSON.stringify({ description }) }).then(() => { setDraft(''); setFileError('') }) }}>Signaler un problème</button>
              </p>
            ) : null}
          </section>
        ) : <section className="team-thread" />}
        {opened ? (
          <aside className="team-side">
            <span className={`tm-av lg ${opened.tone}`}>{opened.initials}</span>
            <strong>{opened.name}</strong>
            <small>{opened.role}</small>
            <em className={opened.online ? 'on' : ''}><i /> {opened.online ? 'Disponible aujourd’hui' : 'Hors ligne'}</em>
            {opened.project ? (
              <div className="team-card">
                <span>Projet partagé</span>
                <p><Icon name="folder" size={14} /> <b>{opened.project}</b></p>
                <small>Progression : {opened.progress}</small>
              </div>
            ) : null}
            <div className="team-files">
              <span>Fichiers partagés {opened.files.length ? <button type="button">Voir tout</button> : null}</span>
              {opened.files.map((file) => (
                <p key={file.name}><Icon name="file" size={14} /><b>{file.name}</b><small>{file.meta}</small></p>
              ))}
            </div>
          </aside>
        ) : null}
      </div>
    </section>
  )
}

function AssistantPage({ role }: { role: Role }) {
  const prompts = role === 'admin'
    ? [
        { text: 'Quels sont les projets actuellement en retard ?', icon: 'alert', tone: 'red' },
        { text: "Quelles sont les activités qui n'ont pas été réalisées aujourd'hui ?", icon: 'tasks', tone: 'orange' },
        { text: 'Quelles sont les activités encore en cours ?', icon: 'clock', tone: 'blue' },
        { text: 'Quelles sont les activités urgentes ?', icon: 'alert', tone: 'red' },
        { text: 'Quelles sont les activités moyennement urgentes ?', icon: 'clock', tone: 'orange' },
        { text: 'Donne-moi la To-Do List de Zaina Zaina.', icon: 'list', tone: 'violet' },
        { text: "Quelles activités Zaina Zaina a-t-elle réalisées aujourd'hui ?", icon: 'check', tone: 'green' },
        { text: "Quelles activités Zaina Zaina n'a-t-elle pas terminées ?", icon: 'tasks', tone: 'orange' },
        { text: "Quel est l'état d'avancement des projets ?", icon: 'folder', tone: 'blue' },
        { text: 'Quels employés ont des tâches en retard ?', icon: 'users', tone: 'red' },
        { text: 'Quels sont les projets qui nécessitent une attention immédiate ?', icon: 'alert', tone: 'orange' },
        { text: "Fais-moi une synthèse des rapports d'aujourd'hui.", icon: 'file', tone: 'violet' },
        { text: "Quels employés n'ont pas encore envoyé leur rapport ?", icon: 'users', tone: 'blue' },
        { text: 'Quelles sont les activités les plus problématiques ?', icon: 'alert', tone: 'red' },
      ]
    : [
        { text: 'Quelles sont mes tâches en cours ?', icon: 'tasks', tone: 'blue' },
        { text: 'Quelles activités ai-je aujourd’hui ?', icon: 'spark', tone: 'violet' },
        { text: 'Quels sont mes prochains délais ?', icon: 'clock', tone: 'orange' },
      ]
  const [log, setLog] = useState<{ q: string; a: string }[]>([])
  const [draft, setDraft] = useState('')
  async function ask(question: string) {
    const text = question.trim()
    if (!text) return
    setDraft('')
    const url = role === 'admin' ? '/decision-ai/chat/' : '/decision-ai/mon-assistant/question/'
    try {
      const response = await fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrfToken() },
        body: new URLSearchParams({ question: text }),
      })
      const data = await response.json().catch(() => null) as { answer?: string; error?: string } | null
      const answer = data?.answer || data?.error || 'Le service IA est momentanément indisponible.'
      setLog((prev) => [...prev, { q: text, a: answer }])
    } catch {
      setLog((prev) => [...prev, { q: text, a: 'Le service IA est momentanément indisponible.' }])
    }
  }
  return (
      <section className="ai-home">
        <div className="ai-mark"><Icon name="spark" size={26} /></div>
        <p className="ai-live"><i /> IA opérationnelle</p>
        <h1>Comment puis-je vous aider ?</h1>
        <p>{role === 'admin' ? 'J’analyse en temps réel les projets, tâches et rapports de votre organisation.' : 'Posez vos questions sur vos activités et vos projets.'}</p>
        <div className="ai-grid">
          {prompts.map((prompt) => (
            <button className="ai-suggest" type="button" key={prompt.text} onClick={() => ask(prompt.text)}>
              <span className={prompt.tone}><Icon name={prompt.icon} size={15} /></span>
              <span>{prompt.text}</span>
              <em>→</em>
            </button>
          ))}
        </div>
        {log.length > 0 ? (
          <div className="ai-log">
            {log.map((entry) => (
              <div key={entry.q}>
                <p className="q">{entry.q}</p>
                <p className="a">{entry.a}</p>
              </div>
            ))}
          </div>
        ) : null}
        <form className="ai-ask" onSubmit={(event) => { event.preventDefault(); ask(draft) }}>
          <Icon name="spark" size={16} />
          <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Posez une question sur l’activité de votre entreprise..." aria-label="Question" />
          <button type="submit" aria-label="Envoyer"><Icon name="send" size={16} /></button>
        </form>
        <p className="ai-disclaimer">L’assistant peut commettre des erreurs. Vérifiez les informations importantes.</p>
      </section>
    )
}

const permissionCatalogue: LeaveRequest[] = [
  { id: 'seed-amina', who: 'Amina Diallo', type: 'Congé', dates: '7 oct. – 9 oct.', motif: 'Rendez-vous familial', status: 'En attente' },
  { id: 'seed-lucas', who: 'Lucas Nguema', type: 'Permission', dates: '6 oct.', motif: 'Rendez-vous médical', status: 'Approuvée' },
  { id: 'seed-paul', who: 'Paul Mbia', type: 'Absence', dates: '2 oct.', motif: 'Mission client', status: 'Approuvée' },
  { id: 'seed-zaina', who: 'Zaina Nouzou', type: 'Permission', dates: '15 oct.', motif: 'Formation', status: 'En attente' },
]

function PermissionsPage({ role, extra, who, onSend, onDecide }: { role: Role; extra: LeaveRequest[]; who: string; onSend: (item: LeaveRequest) => void; onDecide: (id: string, status: string) => void }) {
  const [decided, setDecided] = useState<Record<string, string>>(() => {
    try { return JSON.parse(localStorage.getItem('racin-permission-decisions') || '{}') as Record<string, string> } catch { return {} }
  })
  useEffect(() => { localStorage.setItem('racin-permission-decisions', JSON.stringify(decided)) }, [decided])
  function applyDecision(item: LeaveRequest) {
    return decided[item.id] ? { ...item, status: decided[item.id] } : item
  }
  const [remote, setRemote] = useState<LeaveRequest[] | null>(null)
  const [reloadLeaves, setReloadLeaves] = useState(0)
  useEffect(() => {
    deskCall('/api/permissions/').then((data) => {
      const rows = (data.permissions ?? []) as { id: number; employee: string; start_date: string; end_date: string; reason: string; status_label: string }[]
      setRemote(rows.map((item) => ({
        id: String(item.id),
        who: item.employee,
        type: 'Permission',
        dates: `${item.start_date} → ${item.end_date}`,
        motif: item.reason,
        status: item.status_label === 'Acceptée' ? 'Approuvée' : item.status_label,
        seen: item.status_label !== 'En attente',
      })))
    }).catch(() => undefined)
  }, [role, reloadLeaves])
  function decide(id: string, status: string) {
    setDecided((prev) => ({ ...prev, [id]: status }))
    onDecide(id, status)
    if (/^\d+$/.test(id)) {
      void deskCall(`/api/permissions/${id}/`, { method: 'POST', body: JSON.stringify({ status: status === 'Approuvée' ? 'approved' : 'rejected' }) }).then(() => setReloadLeaves((value) => value + 1))
    }
  }
  const mine = (remote ?? extra.filter((item) => item.who === who)).map(applyDecision)
  const rows = (remote ?? (role === 'admin'
    ? [...extra, ...permissionCatalogue]
    : [...extra.filter((item) => item.who === who), ...permissionCatalogue.filter((item) => item.who === who), ...zainaPermissions])).map(applyDecision)
  const [filter, setFilter] = useState('Toutes')
  const [focus, setFocus] = useState<string | null>(null)
  const [localDecision, setLocalDecision] = useState<Record<string, string>>({})
  const [open, setOpen] = useState(false)
  const [sent, setSent] = useState(false)
  const [kind, setKind] = useState('Permission')
  const [motif, setMotif] = useState('Formation')
  const [from, setFrom] = useState('2026-10-05')
  const [to, setTo] = useState('')
  const [proof, setProof] = useState<ProjectFile | null>(null)
  const [proofError, setProofError] = useState('')
  const picker = useRef<HTMLInputElement>(null)
  const sick = needsProof(motif)
  const shown = rows.filter((item) => filter === 'Toutes' || item.status === filter)
  async function takeProof(list: FileList | null) {
    const file = list?.[0]
    if (picker.current) picker.current.value = ''
    if (!file) return
    const lower = file.name.toLowerCase()
    const pdf = lower.endsWith('.pdf')
    const docx = lower.endsWith('.docx')
    const image = /\.(jpe?g|png|webp)$/.test(lower)
    if (!pdf && !docx && !image) {
      setProofError('Formats acceptés : PDF, image ou DOCX.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setProofError('Le fichier dépasse 10 Mo.')
      return
    }
    let html = ''
    let url = ''
    if (docx) {
      const mammoth = await import('mammoth')
      const result = await mammoth.convertToHtml({ arrayBuffer: await file.arrayBuffer() })
      html = result.value
    } else {
      url = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result))
        reader.onerror = () => reject(reader.error)
        reader.readAsDataURL(file)
      })
    }
    setProof({ name: file.name, kind: pdf ? 'PDF' : docx ? 'DOC' : 'IMG', size: formatSize(file.size), url: url || undefined, html: html || undefined })
    setProofError('')
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (sick && !proof) {
      setProofError('Joignez un justificatif pour une demande liée à une maladie.')
      return
    }
    if (role !== 'employee') {
      setProofError('Seul un employé envoie une demande. Passez en vue employé pour la créer.')
      return
    }
    if (role === 'employee') {
      try {
        await deskCall('/api/permissions/', { method: 'POST', body: JSON.stringify({ start_date: from, end_date: to || from, reason: motif.trim() || 'Non renseigné' }) })
        setReloadLeaves((value) => value + 1)
      } catch (reason) {
        setProofError(reason instanceof Error ? reason.message : 'Envoi impossible.')
        return
      }
    }
    onSend({
      id: `leave-${Date.now()}`,
      who,
      type: kind,
      dates: formatLeaveDates(from, to),
      motif: motif.trim() || 'Non renseigné',
      status: 'En attente',
      file: sick && proof ? proof : undefined,
      seen: false,
    })
    setOpen(false)
    setSent(true)
    setMotif('Formation')
    setProof(null)
    setProofError('')
  }
  const board = remote ? rows.map((item) => ({
    id: item.id,
    initials: item.who.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase(),
    tone: 'violet',
    name: item.who,
    meta: `${item.type} · ${item.dates} · ${item.motif}`,
    status: item.status,
    time: 'Enregistré',
    live: true,
  })) : [
    ...rows.filter((item) => item.status === 'En attente').map((item) => ({
      id: item.id,
      initials: item.who.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase(),
      tone: 'violet',
      name: item.who,
      meta: `${item.type} · ${item.dates}`,
      status: 'En attente',
      time: 'À l’instant',
      live: true,
    })),
    { id: '0205', initials: 'AK', tone: 'violet', name: 'Aïcha Konaté', meta: 'Permissions · demande #0205', status: localDecision['0205'] ? 'Traitée' : 'En attente', time: 'Il y a 1 h', live: false },
    { id: '0206', initials: 'MD', tone: 'blue', name: 'Moussa Diallo', meta: 'Permissions · demande #0206', status: 'Traitée', time: 'Il y a 2 h', live: false },
    { id: '0207', initials: 'SN', tone: 'orange', name: 'Sarah N’Guessan', meta: 'Permissions · demande #0207', status: 'Traitée', time: 'Il y a 3 h', live: false },
    { id: '0208', initials: 'IT', tone: 'green', name: 'Ibrahim Traoré', meta: 'Permissions · demande #0208', status: 'Traitée', time: 'Il y a 4 h', live: false },
  ]
  if (role === 'admin') {
    return (
      <section className="lp">
        <LightHead kicker="RAC’IN Africa" title="Permissions" text="Gérez les demandes d’absence et les autorisations de votre équipe." action={<button className="lp-btn" type="button" onClick={() => setOpen(true)}><Icon name="file" size={14} /> Nouvelle demande</button>} />
        <div className="lp-kpis">
          <article><span className="blue"><Icon name="calendar" size={16} /></span><small>En attente de validation</small><strong>{rows.filter((item) => item.status === 'En attente').length}</strong><em>Mis à jour aujourd’hui</em></article>
          <article><span className="green"><Icon name="calendar" size={16} /></span><small>Traitées ce mois</small><strong>28</strong><em>Mis à jour aujourd’hui</em></article>
          <article><span className="violet"><Icon name="calendar" size={16} /></span><small>Taux de complétion</small><strong>94%</strong><em>Mis à jour aujourd’hui</em></article>
        </div>
        {open ? (
          <form className="lp-panel lp-form" onSubmit={submit}>
            <div className="form-grid">
              <label>Type<select className="field" value={kind} onChange={(event) => setKind(event.target.value)}><option>Permission</option><option>Congé</option><option>Absence</option></select></label>
              <label>Motif<input className="field" list="motifs-admin" value={motif} onChange={(event) => { setMotif(event.target.value); setProofError('') }} /></label>
              <label>Du<input className="field" type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></label>
              <label>Au<input className="field" type="date" value={to} onChange={(event) => setTo(event.target.value)} /></label>
            </div>
            <datalist id="motifs-admin">
              <option value="Formation" />
              <option value="Vacances" />
              <option value="Maladie" />
              <option value="Rendez-vous médical" />
            </datalist>
            {sick ? (
              <div className="project-drop" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); void takeProof(event.dataTransfer.files) }}>
                <input ref={picker} type="file" accept=".pdf,.docx,.jpg,.jpeg,.png,.webp,application/pdf,image/*" hidden onChange={(event) => { void takeProof(event.target.files) }} />
                <span className={`file-ico${proof ? ' ok' : ''}`}><Icon name={proof ? 'check' : 'file'} size={16} /></span>
                <span className="grow"><strong>{proof ? proof.name : 'Justificatif médical'}</strong><small>{proof ? `${proof.kind} · ${proof.size}` : 'PDF, image ou DOCX, 10 Mo maximum'}</small></span>
                <Button type="button" onClick={() => picker.current?.click()}>{proof ? 'Remplacer' : 'Choisir un fichier'}</Button>
              </div>
            ) : null}
            {proofError ? <p className="lp-note">{proofError}</p> : null}
            <div className="lp-form-actions"><Button type="submit">Envoyer</Button><Button ghost onClick={() => setOpen(false)}>Annuler</Button></div>
          </form>
        ) : null}
        <div className="lp-panel">
          <header><h2>Activité récente</h2><p>Dernières opérations enregistrées</p></header>
          {board.map((item) => (
            <div key={item.id}>
              <div className="lp-act">
                <span className="lp-person"><b className={item.tone}>{item.initials}</b></span>
                <span className="grow"><strong>{item.name}</strong><small>{item.meta}</small></span>
                <em className={item.status === 'En attente' ? 'warn' : 'ok'}>{item.status}</em>
                <time>{item.time}</time>
                <button type="button" aria-label="Ouvrir" onClick={() => setFocus(focus === item.id ? null : item.id)}><Icon name="chevron" size={16} /></button>
              </div>
              {focus === item.id && item.status === 'En attente' ? (
                <div className="lp-decide">
                  <Button onClick={() => { if (item.live) decide(item.id, 'Approuvée'); else setLocalDecision((prev) => ({ ...prev, [item.id]: 'Approuvée' })); setFocus(null) }}>Accepter</Button>
                  <Button danger onClick={() => { if (item.live) decide(item.id, 'Refusée'); else setLocalDecision((prev) => ({ ...prev, [item.id]: 'Refusée' })); setFocus(null) }}>Refuser</Button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </section>
    )
  }
  return (
    <section>
      <LightHead kicker="Mon espace" title="Mes permissions" text="Suivez vos demandes de congés et de permissions." action={<button className="lp-btn" type="button" onClick={() => setOpen(true)}><Icon name="plus" size={14} /> Nouvelle demande</button>} />
      <div className="chips" style={{ marginBottom: 12 }}>
        {['Toutes', 'En attente', 'Approuvée', 'Refusée'].map((item) => <button key={item} className={`chip${filter === item ? ' on' : ''}`} type="button" onClick={() => setFilter(item)}>{item}</button>)}
      </div>
      {sent && (!mine[0] || mine[0].status === 'En attente') ? <div className="notice"><Icon name="check" size={14} /> Votre demande et le justificatif ont été envoyés au responsable.</div> : null}
      {mine[0] && mine[0].status !== 'En attente' ? <div className="notice"><Icon name="check" size={14} /> Le responsable a {mine[0].status === 'Approuvée' ? 'approuvé' : 'refusé'} votre demande.</div> : null}
      {open ? (
        <form className="card card-pad stack" style={{ marginBottom: 12 }} onSubmit={submit}>
          <div className="form-grid">
            <label>Type<select value={kind} onChange={(event) => setKind(event.target.value)}><option>Permission</option><option>Congé</option><option>Absence</option></select></label>
            <label>Motif<input list="motifs" value={motif} onChange={(event) => { setMotif(event.target.value); setProofError('') }} /></label>
            <label>Du<input type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></label>
            <label>Au<input type="date" value={to} onChange={(event) => setTo(event.target.value)} /></label>
          </div>
          <datalist id="motifs">
            <option value="Formation" />
            <option value="Vacances" />
            <option value="Maladie" />
            <option value="Arrêt maladie" />
            <option value="Rendez-vous médical" />
          </datalist>
          {sick ? (
            <div>
              <div
                className="project-drop"
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => { event.preventDefault(); void takeProof(event.dataTransfer.files) }}
              >
                <input ref={picker} type="file" accept=".pdf,.docx,.jpg,.jpeg,.png,.webp,application/pdf,image/*" hidden onChange={(event) => { void takeProof(event.target.files) }} />
                <span className={`file-ico${proof ? ' ok' : ''}`}><Icon name={proof ? 'check' : 'file'} size={16} /></span>
                <span className="grow">
                  <strong>{proof ? proof.name : 'Justificatif médical'}</strong>
                  <small>{proof ? `${proof.kind} · ${proof.size}` : 'Arrêt ou certificat, PDF, image ou DOCX, 10 Mo maximum'}</small>
                </span>
                <Button type="button" onClick={() => picker.current?.click()}>{proof ? 'Remplacer' : 'Choisir un fichier'}</Button>
              </div>
              {proofError ? <p className="sub" style={{ color: '#fca5a5', marginTop: 8 }}>{proofError}</p> : null}
            </div>
          ) : null}
          <div style={{ display: 'flex', gap: 8 }}><Button type="submit">Envoyer</Button><Button ghost onClick={() => setOpen(false)}>Annuler</Button></div>
        </form>
      ) : null}
      <div className="card table-wrap">
        <table>
          <thead><tr><th>Type</th><th>Dates</th><th>Motif</th><th>Justificatif</th><th>Statut</th></tr></thead>
          <tbody>
            {shown.map((item) => (
              <tr key={item.id ?? `${item.who}-${item.dates}-${item.motif}`}>
                <td>{item.type}</td>
                <td>{item.dates}</td>
                <td>{item.motif}</td>
                <td>{item.file ? <Button ghost onClick={() => openInBrowser(item.file!)}>{item.file.name}</Button> : <span className="muted">—</span>}</td>
                <td><span className={`status ${statusClass(item.status)}`}>{item.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function DocumentsPage({ onNavigate }: { onNavigate: Go }) {
  const [rows, setRows] = useState<{ id: string; name: string; initials: string; meta: string; project: string; status: string; time: string; url: string }[]>([])
  const [counts, setCounts] = useState({ pending: 0, processed: 0, completion: 0 })
  const [ready, setReady] = useState(false)
  useEffect(() => {
    deskCall('/api/documents/').then((data) => {
      setRows((data.documents ?? []) as typeof rows)
      setCounts({ pending: Number(data.pending) || 0, processed: Number(data.processed) || 0, completion: Number(data.completion) || 0 })
      setReady(true)
    }).catch(() => setReady(true))
  }, [])
  return (
    <section className="lp">
      <LightHead kicker="RAC’IN Africa" title="Documents" text="Briefs, rendus et rapports enregistrés pour la journée." action={<button className="lp-btn" type="button" onClick={() => onNavigate('demo')}><Icon name="database" size={14} /> Générer des données</button>} />
      <div className="lp-kpis">
        <article><span className="blue"><Icon name="file" size={16} /></span><small>En attente de validation</small><strong>{counts.pending}</strong><em>Briefs encore ouverts</em></article>
        <article><span className="green"><Icon name="file" size={16} /></span><small>Documents traités</small><strong>{counts.processed}</strong><em>Rendus et rapports</em></article>
        <article><span className="violet"><Icon name="file" size={16} /></span><small>Taux de complétion</small><strong>{counts.completion}%</strong><em>Parmi les documents listés</em></article>
      </div>
      <div className="lp-panel">
        <header><h2>Activité récente</h2><p>Derniers documents enregistrés</p></header>
        {rows.map((item) => (
          <a className="lp-act" key={item.id} href={item.url} target="_blank" rel="noreferrer">
            <span className="lp-person"><b>{item.initials}</b></span>
            <span className="grow"><strong>{item.name}</strong><small>{item.meta}{item.project ? ` · ${item.project}` : ''}</small></span>
            <em className={item.status === 'En attente' ? 'warn' : 'ok'}>{item.status}</em>
            <time>{item.time}</time>
            <Icon name="chevron" size={16} />
          </a>
        ))}
        {ready && rows.length === 0 ? <p className="muted" style={{ padding: 16 }}>Aucun document enregistré. Le générateur de données peut préparer des briefs, des rendus et des rapports.</p> : null}
      </div>
    </section>
  )
}

function AlertsPage() {
  const [alerts, setAlerts] = useState<{ id: string; level: string; tone: string; iconTone: string; icon: string; title: string; text: string; time: string }[]>([])
  useEffect(() => {
    deskCall('/api/alertes/').then((data) => {
      const rows = (data.alerts ?? []) as { kind: string; title: string; text: string; tone: string }[]
      setAlerts(rows.map((item, index) => ({
        id: `${item.kind}-${index}`,
        level: item.tone === 'danger' ? 'Priorité haute' : 'Information',
        tone: item.tone === 'danger' ? 'high' : 'info',
        iconTone: item.tone === 'danger' ? 'high' : 'info',
        icon: item.kind === 'permission' || item.kind === 'todo' ? 'bell' : 'alert',
        title: item.title,
        text: item.text,
        time: 'Aujourd’hui',
      })))
    }).catch(() => undefined)
  }, [])
  const [read, setRead] = useState<string[]>([])
  return (
    <section className="lp">
      <LightHead kicker="RAC’IN Africa" title="Centre d'alertes" text="Priorisez les événements qui nécessitent une action rapide." action={<button className="lp-btn" type="button" onClick={() => setRead(alerts.map((item) => item.id))}><Icon name="bell" size={14} /> Tout marquer comme lu</button>} />
      <div className="lp-alerts">
        {alerts.map((item) => (
          <article className={`lp-alert-card ${item.tone}${read.includes(item.id) ? ' read' : ''}`} key={item.id}>
            <span className={item.iconTone}><Icon name={item.icon} size={16} /></span>
            <span>
              <small>{item.level}</small>
              <strong>{item.title}</strong>
              <p>{item.text}</p>
              <time>{item.time}</time>
            </span>
            <button type="button" aria-label="Ouvrir" onClick={() => setRead((prev) => prev.includes(item.id) ? prev : [...prev, item.id])}><Icon name="chevron" size={16} /></button>
          </article>
        ))}
      </div>
    </section>
  )
}

function downloadSynthesis(day: string, text: string) {
  const blob = new Blob([`Synthèse\n${day}\n\n${text}`], { type: 'text/plain' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = 'synthese-rapports.txt'
  link.click()
}

function AiReportsPage() {
  const [text, setText] = useState('')
  const [html, setHtml] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const reportDay = new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
  const reportLabel = reportDay.charAt(0).toUpperCase() + reportDay.slice(1)
  async function generate() {
    setLoading(true)
    setError('')
    const now = new Date()
    const day = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    try {
      const response = await fetch('/reports/synthese/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrfToken() },
        body: new URLSearchParams({ date: day }),
      })
      const data = await response.json().catch(() => null) as { ok?: boolean; synthesis?: string; html?: string; error?: string } | null
      if (!response.ok || !data?.ok || !data.synthesis) {
        setText('')
        setHtml('')
        setError(data?.error || 'Aucun rapport soumis ne permet de rédiger la synthèse.')
      } else {
        setText(data.synthesis)
        setHtml(data.html || '')
      }
    } catch {
      setText('')
      setHtml('')
      setError('La synthèse n’a pas pu être affichée.')
    }
    setLoading(false)
  }
  return (
    <section className="lp">
      <LightHead kicker="RAC’IN Africa" title="Rapports IA" text="La synthèse est produite à partir des rapports réellement soumis." action={<button className="lp-btn" type="button" disabled={loading} onClick={() => { void generate() }}><Icon name="spark" size={14} /> {loading ? 'Analyse...' : 'Générer la synthèse IA'}</button>} />
      {error ? <p className="lp-note bad">{error}</p> : null}
      {text ? (
        <div className="lp-synth">
          <aside>
            <span><Icon name="spark" size={18} /></span>
            <em>Rapports soumis</em>
            <h2>Synthèse des rapports</h2>
            <time>{reportLabel}</time>
          </aside>
          <div>
            {html ? <div dangerouslySetInnerHTML={{ __html: html }} /> : <p style={{ whiteSpace: 'pre-wrap' }}>{text}</p>}
            <button className="lp-btn" type="button" onClick={() => downloadSynthesis(reportLabel, text)}><Icon name="download" size={14} /> Télécharger</button>
          </div>
        </div>
      ) : <p className="muted">Aucune synthèse n’est affichée tant que les rapports du jour n’ont pas été analysés.</p>}
    </section>
  )
}

function NotificationsPage({ incoming, onOpen, onOpenTask, onOpenProject, onOpenTodo, onOpenMessage }: { incoming: LeaveRequest[]; onOpen: (id: string) => void; onOpenTask?: (id: string) => void; onOpenProject?: (id: string) => void; onOpenTodo?: (id: string) => void; onOpenMessage?: (id: string) => void }) {
  const [live, setLive] = useState<{ id: string; title: string; meta: string; fresh: boolean; read: boolean; taskId: string; projectId: string; todoId: string; fileUrl: string; chatId: string }[] | null>(null)
  useEffect(() => {
    deskCall('/api/notifications/').then((data) => {
      const rows = (data.notifications ?? []) as { id: number; title: string; message: string; created_at: string; read: boolean; link?: string }[]
      setLive(rows.map((item) => {
        const link = item.link || ''
        const file = /\/taches\/\d+\/(fichier|resultat)\/?$/.test(link)
        return { id: String(item.id), title: item.title, meta: `${item.message} · ${item.created_at}`, fresh: false, read: item.read, taskId: /\/tasks\/(\d+)/.exec(link)?.[1] || '', projectId: /\/projects\/(\d+)|projets\/(\d+)/.exec(link)?.[1] || /projets\/(\d+)/.exec(link)?.[1] || '', todoId: /employe=(\d+)/.exec(link)?.[1] || '', fileUrl: file ? link.replace(/\/resultat\/?$/, '/fichier/') : '', chatId: /messages|messaging/.test(link) ? (/avec=(\d+)/.exec(link)?.[1] || 'boss') : '' }
      }))
    }).catch(() => undefined)
  }, [])
  const items = live ?? [
    ...incoming.map((item) => ({ id: item.id, title: `Demande de permission de ${item.who}`, meta: `${item.type} · ${item.motif}${item.file ? ` · ${item.file.name}` : ''} · à l’instant`, fresh: true, read: false, taskId: '', projectId: '', todoId: '', fileUrl: '', chatId: '' })),
    { id: 'n1', title: 'Nouveau rapport de Zaina Nouzou', meta: 'Rapports · il y a 8 min', fresh: false, read: false, taskId: '', projectId: '', todoId: '', fileUrl: '', chatId: '' },
    { id: 'n2', title: 'Nouvelle demande de permission', meta: 'Amina Diallo · il y a 1 h', fresh: false, read: false, taskId: '', projectId: '', todoId: '', fileUrl: '', chatId: '' },
    { id: 'n3', title: 'Message non lu de Paul Mbia', meta: 'Messagerie · il y a 2 h', fresh: false, read: false, taskId: '', projectId: '', todoId: '', fileUrl: '', chatId: '' },
  ]
  const [read, setRead] = useState<string[]>([])
  return (
    <section>
      <PageHeader title="Notifications" subtitle="Retrouvez ici toutes les notifications de votre agence." action={undefined} />
      <div className="card">
        <div style={{ padding: 12 }}><Button ghost onClick={() => { void deskCall('/api/notifications/', { method: 'POST', body: JSON.stringify({ all: true }) }).then(() => setRead(items.map((item) => item.id))) }}>Tout marquer comme lu</Button></div>
        {items.map((item) => (
          <button className={`notif-item${read.includes(item.id) || item.read ? ' read' : ''}`} type="button" key={item.id} onClick={() => { setRead((prev) => prev.includes(item.id) ? prev : [...prev, item.id]); if (/^\d+$/.test(item.id)) void deskCall('/api/notifications/', { method: 'POST', body: JSON.stringify({ id: item.id }) }); if (item.fileUrl) window.open(item.fileUrl, '_blank', 'noopener'); else if (item.chatId && onOpenMessage) onOpenMessage(item.chatId); else if (item.todoId && onOpenTodo) onOpenTodo(item.todoId); else if (item.taskId && onOpenTask) onOpenTask(item.taskId); else if (item.projectId && onOpenProject) onOpenProject(item.projectId); else if (item.fresh) onOpen(item.id) }}>
            <span className="metric-ico blue"><Icon name="bell" size={14} /></span>
            <span><strong>{item.title}</strong><small className="muted" style={{ display: 'block' }}>{item.meta}</small></span>
          </button>
        ))}
      </div>
    </section>
  )
}

function GenericPage({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <section>
      <PageHeader title={title} subtitle={subtitle} />
      {children}
    </section>
  )
}

function DemoPage({ onNavigate }: { onNavigate: Go }) {
  const [count, setCount] = useState('10')
  const [confirm, setConfirm] = useState(false)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [counts, setCounts] = useState({ employees: 0, projects: 0, tasks: 0, reports: 0, documents: 0 })
  async function load() {
    await ensureAdminSession()
    const data = await deskCall('/api/demonstration/')
    setCounts({
      employees: Number(data.employees) || 0,
      projects: Number(data.projects) || 0,
      tasks: Number(data.tasks) || 0,
      reports: Number(data.reports) || 0,
      documents: Number(data.documents) || 0,
    })
  }
  useEffect(() => { load().catch(() => undefined) }, [])
  async function generate() {
    setBusy(true)
    setError('')
    try {
      await ensureAdminSession()
      const data = await deskCall('/api/demonstration/', { method: 'POST', body: JSON.stringify({ action: 'generate', employees: Number(count), projects: 4, tasks: 24, days: 7 }) })
      setNote(String(data.message || 'Les données sont prêtes.'))
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'La génération a échoué.')
    }
    setBusy(false)
  }
  async function reset() {
    if (!confirm) {
      setError('Cochez la confirmation avant de réinitialiser.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await ensureAdminSession()
      const data = await deskCall('/api/demonstration/', { method: 'POST', body: JSON.stringify({ action: 'reset', confirm: 'oui' }) })
      setNote(String(data.message || 'Les données de démonstration ont été retirées.'))
      setConfirm(false)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'La réinitialisation a échoué.')
    }
    setBusy(false)
  }
  return (
    <GenericPage title="Générateur de données" subtitle="Prépare un tableau de bord explicable : projets, tâches, rapports et documents PDF. Les comptes déjà présents, dont Zaina, restent en place.">
      <div className="stack" style={{ maxWidth: 720 }}>
        <article className="card card-pad">
          <h2>Déjà préparées</h2>
          <div className="chips" style={{ marginTop: 10 }}>
            <span className="chip">{counts.employees} employés</span>
            <span className="chip">{counts.projects} projets</span>
            <span className="chip">{counts.tasks} tâches</span>
            <span className="chip">{counts.reports} rapports</span>
            <span className="chip">{counts.documents} documents</span>
          </div>
          <p className="muted" style={{ marginTop: 10 }}>Mot de passe des comptes générés : {DEMO_PASSWORD}. Identifiant du type demo.prenom.nom.</p>
        </article>
        <article className="card card-pad stack">
          <h2>Générer les données</h2>
          <label>Nombre d'employés
            <select className="field" value={count} onChange={(event) => setCount(event.target.value)} style={{ maxWidth: 220 }}>
              <option value="5">5</option>
              <option value="10">10</option>
              <option value="15">15</option>
              <option value="20">20</option>
            </select>
          </label>
          <div><Button onClick={() => { void generate() }}><Icon name="database" size={14} /> {busy ? 'Préparation...' : 'Générer les données'}</Button></div>
          {error ? <p className="lp-note bad">{error}</p> : null}
          {note ? (
            <div className="notice">
              <Icon name="check" size={14} /> {note}
              <span style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                <button className="linkish" type="button" onClick={() => onNavigate('dashboard')}>Voir le tableau de bord</button>
                <button className="linkish" type="button" onClick={() => onNavigate('documents')}>Voir les documents</button>
                <button className="linkish" type="button" onClick={() => onNavigate('projects')}>Voir les projets</button>
              </span>
            </div>
          ) : null}
        </article>
        <article className="card card-pad stack">
          <h2>Retirer les données générées</h2>
          <p className="muted">Seuls les employés, projets, tâches, rapports et documents créés par ce générateur sont supprimés.</p>
          <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><input type="checkbox" checked={confirm} onChange={(event) => setConfirm(event.target.checked)} /> Je confirme la suppression.</label>
          <div><Button ghost onClick={() => { void reset() }}>Réinitialiser</Button></div>
        </article>
      </div>
    </GenericPage>
  )
}

function FreshSpace({ account, page, detail = '' }: { account: Account; page: string; detail?: string }) {
  const copy: Record<string, [string, string]> = {
    dashboard: [`Bonjour ${account.first || account.username}`, detail || 'Votre compte est créé. Le responsable peut vous écrire et vous attribuer du travail.'],
    projects: ['Mes projets', 'Aucun projet ne vous a encore été attribué.'],
    tasks: ['Mes tâches', 'Aucune tâche ne vous a encore été attribuée.'],
    todos: ['Todo List du jour', 'Votre liste du jour est vide.'],
    reports: ['Mon rapport', "Vous n'avez pas encore transmis de rapport."],
    permissions: ['Mes permissions', "Vous n'avez aucune demande de permission."],
  }
  const [title, subtitle] = copy[page] ?? ['Mon espace', 'Rien à afficher pour le moment.']
  return (
    <section>
      <PageHeader title={title} subtitle={subtitle} />
      <article className="card card-pad">
        <p className="sub">Compte {account.username} · {account.email}</p>
      </article>
    </section>
  )
}

function ProfilePage({ role, account }: { role: Role; account: Account }) {
  const [saved, setSaved] = useState(false)
  const admin = role === 'admin'
  const known = account.username === zaina.username
  const fullName = `${account.first} ${account.last}`.trim() || account.username
  const initials = `${account.first[0] ?? ''}${account.last[0] ?? ''}`.toUpperCase() || account.username.slice(0, 2).toUpperCase()
  return (
    <GenericPage title={admin ? 'Paramètres' : 'Mon profil'} subtitle={admin ? 'Mettez à jour les informations du responsable.' : 'Consultez et mettez à jour vos informations.'}>
      <form className="card card-pad" style={{ maxWidth: 640 }} onSubmit={(event) => { event.preventDefault(); setSaved(true) }}>
        <div className="who" style={{ marginBottom: 14 }}>
          <Avatar initials={admin ? 'AM' : initials} src={admin || !known ? '' : zaina.photo} size="lg" tone={admin ? 'tone-navy' : ''} />
          <span>
            <strong>{admin ? 'Amadou Mensah' : fullName}</strong>
            <small className="muted" style={{ display: 'block' }}>{admin ? 'Administrateur' : known ? zaina.roleLabel : 'Employé'}</small>
            {admin ? null : <small className="muted" style={{ display: 'block' }}>{account.email}</small>}
            {admin || !known ? null : <small className="muted" style={{ display: 'block' }}>Membre depuis le {zaina.hired}</small>}
          </span>
        </div>
        <div className="form-grid">
          <label>Nom complet<input defaultValue={admin ? 'Amadou Mensah' : fullName} /></label>
          <label>Poste<input defaultValue={admin ? 'Administrateur' : known ? zaina.job : 'Employé'} readOnly /></label>
          <label>E-mail<input defaultValue={admin ? 'amadou.mensah@racin.africa' : account.email} /></label>
          <label>Téléphone<input defaultValue="" placeholder="Non renseigné" /></label>
          <label>Date de naissance<input type="date" defaultValue="" /></label>
          <label>Genre<select defaultValue=""><option value="">Non renseigné</option><option>Femme</option><option>Homme</option></select></label>
          <label className="span-2">Adresse<input defaultValue="" placeholder="Non renseignée" /></label>
          <label className="span-2">Bio<textarea defaultValue="" placeholder="Non renseignée" /></label>
          <label>Identifiant<input defaultValue={admin ? 'admin' : account.username} readOnly /></label>
        </div>
        <div style={{ marginTop: 12 }}><Button type="submit">Enregistrer</Button></div>
        {saved ? <div className="notice" style={{ marginTop: 12 }}><Icon name="check" size={14} /> Profil enregistré.</div> : null}
      </form>
    </GenericPage>
  )
}

function Sidebar({ role, page, badge, notices, pendingPermissions, onRole, onPage, onLogout }: { role: Role; page: string; badge: number; notices: number; pendingPermissions: number; onRole: (role: Role) => void; onPage: Go; onLogout: () => void }) {
  const hot = new Set(['messaging', 'alerts', 'notifications'])
  const link = (item: [string, string, string, string?]) => (
    <button key={item[0]} className={`lt-link${page === item[0] ? ' on' : ''}`} type="button" onClick={() => onPage(item[0])}>
      <Icon name={item[2]} size={16} />
      <span>{item[1]}</span>
      {item[3] ? <b className={hot.has(item[0]) ? 'hot' : ''}>{item[3]}</b> : null}
    </button>
  )
  if (role === 'admin') {
    const main: Array<[string, string, string, string?]> = [
      ['dashboard', 'Tableau de bord', 'grid'],
      ['employees', 'Employés', 'users'],
      ['projects', 'Projets', 'folder'],
      ['tasks', 'Tâches', 'tasks'],
      ['todos', 'Todo Lists', 'list'],
      ['reports', 'Rapports journaliers', 'file'],
      ['permissions', 'Permissions', 'calendar', String(Math.max(3, pendingPermissions))],
      ['documents', 'Documents', 'file'],
      ['messaging', 'Messagerie', 'message', String(Math.max(2, badge))],
      ['alerts', "Centre d'alertes", 'bell', '6'],
    ]
    const intel: Array<[string, string, string, string?]> = [
      ['assistant', 'Assistant IA', 'spark'],
      ['ai-reports', 'Rapports IA', 'trend'],
      ['demo', 'Générateur de données', 'database'],
    ]
    return (
      <aside className="sidebar lt-side lt-admin">
        <div className="lt-logo">
          <span className="lt-bars"><i /><i /><i /></span>
          <span><strong>RAC’IN</strong><small>AFRICA</small></span>
        </div>
        <div className="lt-work"><span><Icon name="case" size={16} /></span><span><small>ESPACE DE TRAVAIL</small><strong>Direction Générale</strong></span><Icon name="chevron" size={14} /></div>
        <nav>
          {main.map(link)}
        </nav>
        <div className="lt-intel">
          <span className="lt-label">Intelligence</span>
          {intel.map(link)}
        </div>
        <div className="lt-foot">
          <button className={`lt-link${page === 'settings' ? ' on' : ''}`} type="button" onClick={() => onPage('settings')}>
            <Icon name="settings" size={16} />
            <span>Paramètres</span>
          </button>
          <div className="lt-user">
            <b>AM</b>
            <span><strong>Amadou Mensah</strong><small>Administrateur</small></span>
            <button type="button" aria-label="Déconnexion" onClick={onLogout}><Icon name="logout" size={16} /></button>
          </div>
        </div>
      </aside>
    )
  }
  const items: Array<[string, string, string, string?]> = [
    ['dashboard', 'Tableau de bord', 'grid'],
    ['projects', 'Mes projets', 'folder'],
    ['tasks', 'Mes tâches', 'tasks'],
    ['todos', 'Todo List', 'list'],
    ['reports', 'Mon rapport', 'file'],
    ['permissions', 'Mes permissions', 'calendar'],
    ['messaging', 'Messagerie', 'message', badge ? String(badge) : ''],
    ['notifications', 'Notifications', 'bell', notices ? String(notices) : ''],
    ['assistant', 'Assistant IA', 'spark'],
  ]
  return (
    <aside className="sidebar lt-side">
      <div className="lt-logo">
        <span className="lt-bars"><i /><i /><i /></span>
        <span><strong>RAC’IN</strong><small>AFRICA</small></span>
      </div>
        <div className="lt-work"><span><Icon name="case" size={16} /></span><span><small>ESPACE DE TRAVAIL</small><strong>Direction Générale</strong></span><Icon name="chevron" size={14} /></div>
      <nav>
        <span className="lt-label">Menu principal</span>
        {items.map(link)}
      </nav>
      <div className="lt-foot">
        <button className={`lt-link${page === 'profile' ? ' on' : ''}`} type="button" onClick={() => onPage('profile')}><Icon name="user" size={16} /><span>Mon profil</span></button>
        <div className="lt-user">
          <b>ZZ</b>
          <span><strong>Zaina Zaina</strong><small>Employée</small></span>
          <button type="button" aria-label="Déconnexion" onClick={onLogout}><Icon name="logout" size={16} /></button>
        </div>
        <button className="lt-employee" type="button" onClick={() => onRole('admin')}>Espace responsable</button>
      </div>
    </aside>
  )
}

function Topbar({ role, notifCount, onNavigate, onRole, page }: { role: Role; notifCount: number; onNavigate: Go; onRole: (next: Role) => void; page: string }) {
  const [query, setQuery] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const catalog = role === 'admin'
    ? [
        { label: 'Zaina Nouzou', meta: 'Employé', page: 'employees' },
        { label: 'Campagne Tiko Transit', meta: 'Projet', page: 'projects' },
        { label: "Maquette page d'accueil", meta: 'Tâche', page: 'tasks' },
      ]
    : [
        { label: 'analyse du site', meta: 'Projet', page: 'projects' },
        { label: 'creationn de site de marenova', meta: 'Projet', page: 'projects' },
        { label: 'Explorer toutes les pages existantes du site CuisineFacile.', meta: 'Tâche', page: 'tasks' },
      ]
  const results = catalog.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()))
  const profile = role === 'admin'
    ? { initials: 'AM', name: 'Amadou Mensah', job: 'Responsable', page: 'settings' }
    : {
        initials: 'ZZ',
        name: 'Zaina Zaina',
        job: 'Employée',
        page: 'profile',
      }
  const titles: Record<string, string> = role === 'admin'
    ? {
        dashboard: 'Tableau de bord', employees: 'Employés', projects: 'Projets', tasks: 'Tâches', todos: 'Todo Lists',
        reports: 'Rapports journaliers', permissions: 'Permissions', documents: 'Documents', alerts: "Centre d'alertes",
        messaging: 'Messagerie', notifications: 'Notifications', assistant: 'Assistant IA', 'ai-reports': 'Rapports IA', demo: 'Données de démo', settings: 'Paramètres',
      }
    : {
        dashboard: 'Tableau de bord', projects: 'Projets', tasks: 'Mes tâches', todos: 'Todo Lists',
        reports: 'Rapports journaliers', permissions: 'Mes permissions', messaging: 'Messagerie', notifications: 'Notifications', assistant: 'Assistant IA', profile: 'Mon profil',
      }
  return (
      <header className="topbar lt-top">
        <div className="lt-crumbs">
          <button type="button" onClick={() => onNavigate('dashboard')}>RAC’IN Africa</button>
          <Icon name="chevron" size={13} />
          <strong>{titles[page] ?? 'Tableau de bord'}</strong>
        </div>
        <div className="lt-actions">
          <button className="lt-switch" type="button" onClick={() => onRole(role === 'admin' ? 'employee' : 'admin')}>
            <Icon name={role === 'admin' ? 'user' : 'folder'} size={15} />
            {role === 'admin' ? 'Vue employé' : 'Vue responsable'}
          </button>
          <div className="lt-search">
            {searchOpen ? <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher..." aria-label="Recherche" autoFocus /> : null}
            <button className="lt-icon" type="button" aria-label="Recherche" onClick={() => setSearchOpen((open) => !open)}><Icon name="search" size={17} /></button>
            {searchOpen && query.trim().length > 1 ? (
              <div className="search-drop">
                {results.map((item) => <button key={item.label} type="button" onClick={() => { onNavigate(item.page); setQuery(''); setSearchOpen(false) }}>{item.label}<small>{item.meta}</small></button>)}
                {results.length === 0 ? <button type="button">Aucun résultat</button> : null}
              </div>
            ) : null}
          </div>
          <button className="lt-icon" type="button" aria-label="Apparence"><Icon name="sun" size={17} /></button>
          <button className="lt-icon" type="button" aria-label="Notifications" onClick={() => onNavigate('notifications')}><Icon name="bell" size={17} />{notifCount ? <em>{notifCount}</em> : null}</button>
          <span className="lt-divider" />
          <button className="lt-profile" type="button" onClick={() => onNavigate(profile.page)}>
            <b className={role === 'employee' ? 'emp' : ''}>{profile.initials}</b>
            <span><strong>{profile.name}</strong><small>{profile.job}</small></span>
            <Icon name="chevron" size={14} />
          </button>
        </div>
      </header>
  )
}

function Login({ accounts, onSuccess }: { accounts: Account[]; onSuccess: (account: Account, role?: Role) => void }) {
  const [mode, setMode] = useState<'login' | 'create'>('login')
  const [identifiant, setIdentifiant] = useState('zaina')
  const [motDePasse, setMotDePasse] = useState('nabihouddine')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ first: '', last: '', username: '', email: '', password: '', confirm: '' })
  function create(event: FormEvent) {
    event.preventDefault()
    const username = form.username.trim().toLowerCase()
    const email = form.email.trim().toLowerCase()
    if (!username || !form.first.trim() || !form.last.trim()) {
      setError('Renseignez le prénom, le nom et l’identifiant.')
      return
    }
    if (form.password.length < 4) {
      setError('Le mot de passe doit contenir au moins 4 caractères.')
      return
    }
    if (form.password !== form.confirm) {
      setError('Les deux mots de passe ne correspondent pas.')
      return
    }
    if (accounts.some((item) => item.username === username || item.email === email)) {
      setError('Cet identifiant ou cet e-mail est déjà utilisé.')
      return
    }
    onSuccess({ username, email, password: form.password, first: form.first.trim(), last: form.last.trim() })
  }
  return (
    <div className="login">
      <section className="login-hero">
        <div>
          <Logo />
          <p className="login-kicker">Bienvenue sur votre espace</p>
          <h1>Ensemble pour<br /><span>des projets qui marquent</span></h1>
          <p className="login-lead">Une plateforme intelligente pour mieux gérer vos activités, suivre vos projets et contribuer au succès de l'agence.</p>
          <div className="art" aria-hidden="true">
            <div className="screen"><i /><i style={{ width: '70%' }} /><i style={{ width: '46%' }} /></div>
            <div className="head" />
            <div className="body" />
          </div>
        </div>
        <div className="pillars">
          <div><Icon name="trend" />Suivi des activités</div>
          <div><Icon name="users" />Travail en équipe</div>
          <div><Icon name="spark" />Innovation avec l’IA</div>
          <div><Icon name="check" />Objectifs communs</div>
        </div>
      </section>
      <section className="login-panel">
        {mode === 'login' ? (
        <form className="login-card" onSubmit={(event) => {
          event.preventDefault()
          const value = identifiant.trim().toLowerCase()
          const djangoName = value === 'zaina' || value === 'zaina.zaina' ? 'nouzou' : value
          const localName = djangoName
          setPending(true)
          setError('')
          void enterSession(djangoName, motDePasse).then((session) => {
            const known = session.username === 'nouzou'
            onSuccess({
              username: known ? zaina.username : session.username,
              email: known ? zaina.email : '',
              password: motDePasse,
              first: session.first || (known ? 'zaina' : ''),
              last: session.last || (known ? 'zaina' : ''),
            }, session.role === 'admin' ? 'admin' : 'employee')
          }).catch(() => {
            const found = accounts.find((item) => item.username === localName || item.username === value || item.email === value)
            if (!found || found.password !== motDePasse) {
              setError('Identifiant ou mot de passe incorrect.')
              setPending(false)
              return
            }
            onSuccess(found, 'employee')
          })
        }}>
          <h2>Espace Employé</h2>
          <p className="intro">Compte Zaina : identifiant zaina, mot de passe nabihouddine.</p>
          <label>Identifiant<input value={identifiant} onChange={(event) => setIdentifiant(event.target.value)} autoComplete="username" required /></label>
          <label>Mot de passe<input type="password" value={motDePasse} onChange={(event) => setMotDePasse(event.target.value)} autoComplete="current-password" required /></label>
          {error ? <p className="intro" style={{ color: '#b91c1c' }}>{error}</p> : null}
          <div className="login-row">
            <label><input type="checkbox" defaultChecked /> Se souvenir de moi</label>
            <button type="button" onClick={() => { setMode('create'); setError('') }}>Créer un compte</button>
          </div>
          <button className="btn full" type="submit" disabled={pending}>{pending ? 'Connexion…' : 'Se connecter →'}</button>
          <div className="assist">
            <Icon name="shield" />
            <span><strong>Pas encore de compte ?</strong>Un employé peut créer le sien, puis se connecter.</span>
          </div>
        </form>
        ) : (
        <form className="login-card" onSubmit={create}>
          <h2>Créer un compte</h2>
          <p className="intro">Réservé aux employés de l'agence qui n'ont pas encore d'accès.</p>
          <label>Prénom<input value={form.first} onChange={(event) => setForm({ ...form, first: event.target.value })} required /></label>
          <label>Nom<input value={form.last} onChange={(event) => setForm({ ...form, last: event.target.value })} required /></label>
          <label>Identifiant<input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} autoComplete="username" required /></label>
          <label>E-mail<input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /></label>
          <label>Mot de passe<input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /></label>
          <label>Confirmer<input type="password" value={form.confirm} onChange={(event) => setForm({ ...form, confirm: event.target.value })} required /></label>
          {error ? <p className="intro" style={{ color: '#b91c1c' }}>{error}</p> : null}
          <button className="btn full" type="submit">Créer mon compte →</button>
          <div className="login-row" style={{ marginTop: 12 }}>
            <button type="button" onClick={() => { setMode('login'); setError('') }}>J'ai déjà un compte</button>
          </div>
        </form>
        )}
      </section>
    </div>
  )
}

const zainaAccount: Account = { username: zaina.username, email: zaina.email, password: 'nabihouddine', first: 'zaina', last: 'zaina' }

export default function App() {
  const [authed, setAuthed] = useState(true)
  const [role, setRole] = useState<Role>('admin')
  const [page, setPage] = useState('dashboard')
  const [focusTask, setFocusTask] = useState('')
  const [focusTodo, setFocusTodo] = useState('')
  const [focusChat, setFocusChat] = useState('')
  const [bell, setBell] = useState(0)
  useEffect(() => {
    ensureAdminSession().then((session) => {
      if (session?.role === 'admin' || session?.role === 'employee') setRole(session.role)
    }).catch(() => undefined)
  }, [])
  const [checks, setChecks] = useState<string[]>(['6', '7', '8', '9', '10'])
  const [inbox] = useState<ReportFile[]>([])
  const [accounts, setAccounts] = useState<Account[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('racin-accounts') || '[]') as Account[]
      const extra = saved.filter((item) => item.username && item.username !== zainaAccount.username)
      return [zainaAccount, ...extra]
    } catch {
      return [zainaAccount]
    }
  })
  const [account, setAccount] = useState<Account>(zainaAccount)
  const [threads, setThreads] = useState<Record<string, Note[]>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('racin-threads') || '{}') as Record<string, Note[]>
      return { [zaina.username]: zainaThread, ...saved }
    } catch {
      return { [zaina.username]: zainaThread }
    }
  })
  const [demoStaff] = useState<Staff[]>(() => {
    try { return (JSON.parse(localStorage.getItem('racin-demo') || '{}') as { staff?: Staff[] }).staff ?? [] } catch { return [] }
  })
  const [demoFiles] = useState<ReportFile[]>(() => {
    try { return (JSON.parse(localStorage.getItem('racin-demo') || '{}') as { files?: ReportFile[] }).files ?? [] } catch { return [] }
  })
  const [demoPlans] = useState<DayPlan[]>(() => {
    try { return (JSON.parse(localStorage.getItem('racin-demo') || '{}') as { plans?: DayPlan[] }).plans ?? [] } catch { return [] }
  })
  const [extraProjects, setExtraProjects] = useState<ProjectCard[]>(() => {
    try { return (JSON.parse(localStorage.getItem('racin-work') || '{}') as { projects?: ProjectCard[] }).projects ?? [] } catch { return [] }
  })
  const [assignedTasks, setAssignedTasks] = useState<AssignedTask[]>(() => {
    try { return (JSON.parse(localStorage.getItem('racin-work') || '{}') as { tasks?: AssignedTask[] }).tasks ?? [] } catch { return [] }
  })
  const [leaves, setLeaves] = useState<LeaveRequest[]>(() => {
    try { return JSON.parse(localStorage.getItem('racin-leaves') || '[]') as LeaveRequest[] } catch { return [] }
  })
  const staff = [...people, ...demoStaff]
  const zainaArchive: ReportFile[] = zainaReports.filter((item) => item.url).map((item) => ({
    id: item.url ?? item.name,
    person: zaina.username,
    name: item.name,
    kind: item.kind ?? 'PDF',
    size: item.size,
    date: item.date,
    scope: 'month',
    url: item.url,
  }))
  const reportStaff: Staff[] = [
    {
      id: zaina.username,
      name: zaina.name,
      role: zaina.roleLabel,
      service: zaina.job,
      initials: zaina.initials,
      tone: '',
      status: 'Actif',
      todo: '—',
      seen: 'À l’instant',
      online: true,
      reports: zainaArchive.length + inbox.filter((file) => file.person === zaina.username).length,
      presence: '—',
    },
    ...staff.filter((person) => person.id !== zaina.username),
  ]
  const library = [...inbox, ...zainaArchive, ...reportFiles, ...demoFiles]

  useEffect(() => { localStorage.setItem('racin-accounts', JSON.stringify(accounts)) }, [accounts])
  useEffect(() => {
    try {
      localStorage.setItem('racin-threads', JSON.stringify(threads))
    } catch {
      const light = Object.fromEntries(Object.entries(threads).map(([key, notes]) => [
        key,
        notes.map((note) => note.file ? { ...note, file: { name: note.file.name, kind: note.file.kind, size: note.file.size } } : note),
      ]))
      try { localStorage.setItem('racin-threads', JSON.stringify(light)) } catch { /* la pièce jointe reste disponible dans la session */ }
    }
  }, [threads])
  useEffect(() => { localStorage.setItem('racin-demo', JSON.stringify({ staff: demoStaff, files: demoFiles, plans: demoPlans })) }, [demoStaff, demoFiles, demoPlans])
  useEffect(() => {
    const payload = JSON.stringify({ projects: extraProjects, tasks: assignedTasks })
    try {
      localStorage.setItem('racin-work', payload)
    } catch {
      const light = extraProjects.map((project) => project.file?.url?.startsWith('data:') ? { ...project, file: { ...project.file, url: undefined } } : project)
      try { localStorage.setItem('racin-work', JSON.stringify({ projects: light, tasks: assignedTasks })) } catch { /* le fichier reste disponible dans la session */ }
    }
  }, [extraProjects, assignedTasks])
  useEffect(() => {
    try {
      localStorage.setItem('racin-leaves', JSON.stringify(leaves))
    } catch {
      const light = leaves.map((item) => item.file?.url?.startsWith('data:') ? { ...item, file: item.file ? { ...item.file, url: undefined } : undefined } : item)
      try { localStorage.setItem('racin-leaves', JSON.stringify(light)) } catch { /* le justificatif reste disponible dans la session */ }
    }
  }, [leaves])

  function go(next: string) {
    setPage(next)
  }
  function changeRole(next: Role) {
    void showSpace(next).then((session) => {
      if (session?.role === 'admin' || session?.role === 'employee') {
        setRole(session.role)
        if (session.role === 'employee') {
          setAccount({ username: zaina.username, email: zaina.email, password: '', first: 'zaina', last: 'zaina' })
        }
      }
    }).catch(() => setRole(next))
    const allowed = next === 'admin' ? adminPages : employeePages
    if (!allowed.includes(page)) setPage('dashboard')
  }
  function toggle(id: string) {
    setChecks((prev) => prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id])
  }
  function enter(next: Account, nextRole: Role = 'employee') {
    setAccounts((prev) => prev.some((item) => item.username === next.username) ? prev : [...prev, next])
    setAccount(next)
    setThreads((prev) => prev[next.username] ? prev : { ...prev, [next.username]: [] })
    setRole(nextRole)
    setPage('dashboard')
    setAuthed(true)
  }
  const [messageBadge, setMessageBadge] = useState(0)

  const personId = account.username === zaina.username || account.email === zaina.email
    ? 'zaina'
    : people.find((person) => person.name.toLowerCase() === `${account.first} ${account.last}`.trim().toLowerCase())?.id ?? ''
  const requester = people.find((person) => person.id === personId)?.name ?? `${account.first} ${account.last}`.trim()
  const myTasks = assignedTasks.filter((task) => task.whoId === personId)
  const myProjects = extraProjects.filter((project) => (project.members ?? []).includes(personId) || myTasks.some((task) => task.projectId === project.id))

  useEffect(() => {
    let stop = false
    function load() {
      deskCall('/api/notifications/').then((data) => { if (!stop) setBell(Number(data.unread) || 0) }).catch(() => undefined)
      deskCall('/api/messages/').then((data) => {
        if (stop) return
        if (role === 'admin') {
          const contacts = (data.contacts ?? []) as { unread?: number }[]
          setMessageBadge(contacts.reduce((sum, item) => sum + (Number(item.unread) || 0), 0))
        } else {
          setMessageBadge(Number(data.unread) || 0)
        }
      }).catch(() => undefined)
    }
    load()
    const timer = window.setInterval(load, 8000)
    return () => { stop = true; window.clearInterval(timer) }
  }, [role, page])

  const view = useMemo(() => {
    const studio = new Set(['nouzou', 'awa.traore', 'fatou.diarra', 'mamadou.kone', 'ibrahim.bah'])
    const fresh = role === 'employee' && !studio.has(account.username)
    const demoAccount = account.username.startsWith('demo.')
    if (role === 'admin' && page === 'dashboard') return <AdminDashboard onNavigate={go} />
    if (fresh && !(demoAccount && ['todos', 'reports', 'dashboard'].includes(page)) && !['messaging', 'assistant', 'profile'].includes(page)) return <FreshSpace account={account} page={page} />
    if (role === 'employee' && demoAccount && page === 'dashboard') {
      const plan = demoPlans.find((item) => item.personId === account.username)
      const report = demoFiles.find((item) => item.person === account.username)
      return <FreshSpace account={account} page="dashboard" detail={`Votre todo list compte ${plan?.items.length ?? 0} tâches. Rapport transmis : ${report?.name ?? 'aucun'}.`} />
    }
    if (role === 'employee' && page === 'dashboard') return <EmployeeDashboard checks={checks} onToggle={toggle} onNavigate={go} receivedProjects={myProjects} receivedTasks={myTasks} name="Zaina" />
    if (page === 'employees') return <EmployeesPage />
    if (page === 'projects') return <ProjectsPage role={role} list={role === 'admin' ? [...extraProjects, ...projects] : [...myProjects, ...zainaProjects]} duties={assignedTasks} onCreate={(project, tasks) => { setExtraProjects((prev) => [project, ...prev]); setAssignedTasks((prev) => [...tasks, ...prev]) }} />
    if (page === 'tasks') return <TasksPage role={role} focus={focusTask} checks={checks} onToggle={toggle} assigned={role === 'admin' ? assignedTasks : myTasks} />
    if (page === 'todos') return <TodosPage role={role} staff={staff} plans={demoPlans} username={account.username} assigned={role === 'admin' ? assignedTasks : myTasks} focusEmployee={focusTodo} />
    if (page === 'reports') return role === 'employee' ? <EmployeeReportPage /> : <ReportsPage staff={reportStaff} library={library} />
    if (page === 'permissions') return <PermissionsPage role={role} extra={leaves} who={requester} onSend={(item) => setLeaves((prev) => [item, ...prev])} onDecide={(id, status) => setLeaves((prev) => prev.map((item) => item.id === id ? { ...item, status, seen: true } : item))} />
    if (page === 'documents') return <DocumentsPage onNavigate={go} />
    if (page === 'alerts') return <AlertsPage />
    if (page === 'messaging') return <MessagingPage key={role} role={role} focus={focusChat} />
    if (page === 'notifications') return <NotificationsPage incoming={leaves} onOpen={(id) => { setLeaves((prev) => prev.map((item) => item.id === id ? { ...item, seen: true } : item)); setPage('permissions') }} onOpenTask={(id) => { setFocusTask(id); setPage('tasks') }} onOpenProject={() => setPage('projects')} onOpenTodo={(id) => { setFocusTodo(id); setPage('todos') }} onOpenMessage={(id) => { setFocusChat(id); setPage('messaging') }} />
    if (page === 'assistant') return <AssistantPage key={role} role={role} />
    if (page === 'ai-reports') return <AiReportsPage />
    if (page === 'demo') return <DemoPage onNavigate={go} />
    return <ProfilePage role={role} account={account} />
  }, [role, page, checks, account, accounts, threads, demoStaff, demoFiles, demoPlans, inbox, extraProjects, assignedTasks, myProjects, myTasks, leaves, requester, focusTask, focusTodo, focusChat])

  if (!authed) return <Login accounts={accounts} onSuccess={enter} />

  return (
    <div className="app-shell light">
      <Sidebar role={role} page={page} badge={messageBadge} notices={bell} pendingPermissions={leaves.filter((item) => item.status === 'En attente').length} onRole={changeRole} onPage={go} onLogout={() => { void leaveSession().catch(() => undefined); setAuthed(false) }} />
      <div className="workspace">
        <Topbar role={role} notifCount={bell} onNavigate={go} onRole={changeRole} page={page} />
        <main>
          <div className={`content${role === 'admin' && page === 'dashboard' ? ' content-wide' : ''}`}>{view}</div>
        </main>
      </div>
    </div>
  )
}
