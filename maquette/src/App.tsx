import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'

type Role = 'admin' | 'employee'
type Go = (page: string) => void

const adminPages = ['dashboard', 'employees', 'projects', 'tasks', 'todos', 'reports', 'permissions', 'alerts', 'messaging', 'notifications', 'assistant', 'demo', 'settings']
const employeePages = ['dashboard', 'projects', 'tasks', 'todos', 'reports', 'permissions', 'messaging', 'assistant', 'profile']

const people = [
  { id: 'zaina', name: 'Zaina Nouzou', role: 'Graphiste', service: 'Création', initials: 'ZN', tone: '', status: 'Actif', todo: '4 / 5 tâches', seen: 'Il y a 8 min', online: true, reports: 8, presence: '92 %' },
  { id: 'paul', name: 'Paul Mbia', role: 'Chef de projet', service: 'Production', initials: 'PM', tone: 'tone-sky', status: 'Actif', todo: '3 / 4 tâches', seen: 'Il y a 24 min', online: false, reports: 6, presence: '88 %' },
  { id: 'amina', name: 'Amina Diallo', role: 'Community manager', service: 'Communication', initials: 'AD', tone: 'tone-amber', status: 'En congé', todo: 'Non renseignée', seen: '3 oct. 2026', online: false, reports: 5, presence: '80 %' },
  { id: 'lucas', name: 'Lucas Nguema', role: 'Développeur web', service: 'Digital', initials: 'LN', tone: 'tone-green', status: 'Actif', todo: '5 / 6 tâches', seen: 'Il y a 1 h', online: true, reports: 7, presence: '95 %' },
]

const projects = [
  { id: 'tiko', name: 'Campagne Tiko Transit', client: 'Tiko Transit Logistics', owner: 'Paul Mbia', progress: 72, status: 'En cours', due: '18 oct. 2026' },
  { id: 'hotel', name: 'Identité visuelle Hôtel Baie', client: 'Hôtel de la Baie', owner: 'Zaina Nouzou', progress: 40, status: 'En cours', due: '11 oct. 2026' },
  { id: 'nova', name: 'Lancement produit Nova', client: 'Nova Cosmetics', owner: 'Amina Diallo', progress: 100, status: 'Terminé', due: '28 sept. 2026' },
]

const tasks = [
  { id: 't1', title: "Maquette page d'accueil", project: 'Tiko Transit', who: 'Zaina Nouzou', priority: 'Élevée', tone: 'high', due: '8 oct. 2026', status: 'En cours', mine: true },
  { id: 'b', title: 'Validation du logo', project: 'Hôtel de la Baie', who: 'Paul Mbia', priority: 'Urgente', tone: 'urgent', due: '4 oct. 2026', status: 'En retard', mine: false },
  { id: 'c', title: 'Rédaction du post Instagram', project: 'Nova Cosmetics', who: 'Amina Diallo', priority: 'Moyenne', tone: 'mid', due: '5 oct. 2026', status: 'Terminée', mine: false },
  { id: 't2', title: 'Déclinaison des bannières', project: 'Tiko Transit', who: 'Zaina Nouzou', priority: 'Moyenne', tone: 'mid', due: '9 oct. 2026', status: 'À faire', mine: true },
]

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

const zainaTasks = [
  { id: '6', title: 'creationn de site de marenova', project: 'creationn de site de marenova', who: zaina.name, priority: 'Urgente', tone: 'urgent', due: '10 sept. 2026', status: 'Terminée', mine: true },
  { id: '7', title: 'Explorer toutes les pages existantes du site CuisineFacile.', project: 'analyse du site', who: zaina.name, priority: 'Moyenne', tone: 'mid', due: '—', status: 'Terminée', mine: true },
  { id: '8', title: 'Identifier les fonctionnalités liées aux BOX cuisine', project: 'analyse du site', who: zaina.name, priority: 'Moyenne', tone: 'mid', due: '—', status: 'Terminée', mine: true },
  { id: '9', title: 'Supprimer les mentions "Box cuisine"', project: 'NETTOYAGE ET SUPPRESSION DES ANCIENNES FONCTIONNALITÉS', who: zaina.name, priority: 'Moyenne', tone: 'mid', due: '—', status: 'Terminée', mine: true },
  { id: '10', title: "Retirer les éléments liés à la livraison d'ingrédients frais.", project: 'NETTOYAGE ET SUPPRESSION DES ANCIENNES FONCTIONNALITÉS', who: zaina.name, priority: 'Moyenne', tone: 'mid', due: '—', status: 'Terminée', mine: true },
]

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

const zainaPermissions = [
  { who: zaina.name, type: 'Permission', dates: '6 sept. – 16 sept. 2026', motif: 'Rendez-vous médical', status: 'Annulée' },
  { who: zaina.name, type: 'Permission', dates: '25 sept. 2026', motif: 'Vacances', status: 'Approuvée' },
  { who: zaina.name, type: 'Congé annuel', dates: '30 sept. – 7 nov. 2026', motif: 'Vacances', status: 'Refusée' },
]

type Staff = { id: string; name: string; role: string; service: string; initials: string; tone: string; status: string; todo: string; seen: string; online: boolean; reports: number; presence: string; demo?: boolean }
type ReportFile = { id: string; person: string; name: string; kind: string; size: string; date: string; scope: string; demo?: boolean; url?: string; html?: string }
type PlanItem = { id: string; text: string; done: boolean }
type DayPlan = { personId: string; items: PlanItem[] }
type DemoBundle = { staff: Staff[]; files: ReportFile[]; plans: DayPlan[]; accounts: Account[] }

const DEMO_PASSWORD = 'Demo-Racine-2026'
const DEMO_PEOPLE: [string, string][] = [
  ['Fatou', 'Diarra'], ['Mariama', 'Camara'], ['Awa', 'Traoré'], ['Aïcha', 'Touré'], ['Sophie', 'Koné'],
  ['Mariam', 'Bah'], ['Rokia', 'Coulibaly'], ['Aminata', 'Sangaré'], ['Yao', 'Kouadio'], ['Ibrahim', 'Bah'],
  ['Moussa', 'Diallo'], ['Sékou', 'Camara'], ['Amadou', 'Koné'], ['Oumar', 'Keita'], ['Cheick', 'Traoré'],
  ['Abdoulaye', 'Cissé'], ['Nadia', 'Ouédraogo'], ['Kadiatou', 'Sidibé'], ['Jean', 'Koffi'], ['Paul', 'Mensah'],
]
const DEMO_JOBS = [
  { role: 'Développeur web', service: 'Digital', tone: 'tone-green', tasks: ["Corriger la page d'accueil", 'Intégrer le formulaire de contact', "Vérifier l'affichage mobile", 'Mettre à jour les liens du menu'] },
  { role: 'Graphiste', service: 'Création', tone: '', tasks: ['Finaliser la maquette du site', 'Préparer les visuels Facebook', 'Ajuster la couverture de campagne', 'Décliner le logo en petit format'] },
  { role: 'Community manager', service: 'Communication', tone: 'tone-amber', tasks: ['Programmer les publications de la semaine', 'Répondre aux commentaires en attente', 'Préparer le calendrier éditorial', 'Relire les légendes des posts'] },
  { role: 'Chargé de communication', service: 'Communication', tone: 'tone-sky', tasks: ['Rédiger le texte de la page services', 'Relire le communiqué client', 'Préparer le brief de la campagne', 'Mettre à jour la présentation commerciale'] },
  { role: 'Chef de projet', service: 'Production', tone: 'tone-navy', tasks: ["Vérifier l'avancement avec le client", 'Mettre à jour le planning de livraison', 'Relancer les éléments manquants', "Préparer le point d'équipe"] },
]

function demoSlug(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z]/g, '')
}

function buildDemo(count: number): DemoBundle {
  const chosen = DEMO_PEOPLE.slice(0, count)
  const staff: Staff[] = []
  const files: ReportFile[] = []
  const plans: DayPlan[] = []
  const accounts: Account[] = []
  chosen.forEach(([first, last], index) => {
    const job = DEMO_JOBS[index % DEMO_JOBS.length]
    const username = `demo.${demoSlug(first)}.${demoSlug(last)}`
    const done = 3
    staff.push({
      id: username,
      name: `${first} ${last}`,
      role: job.role,
      service: job.service,
      initials: `${first[0] ?? ''}${last[0] ?? ''}`.toUpperCase(),
      tone: job.tone,
      status: 'Actif',
      todo: `${done} / ${job.tasks.length} tâches`,
      seen: 'À l’instant',
      online: index % 3 !== 2,
      reports: 1,
      presence: '100 %',
      demo: true,
    })
    plans.push({
      personId: username,
      items: job.tasks.map((text, taskIndex) => ({ id: `${username}-${taskIndex}`, text, done: taskIndex < done })),
    })
    files.push({
      id: `demo-report-${username}`,
      person: username,
      name: `Rapport_05_octobre_${demoSlug(last)}.pdf`,
      kind: 'PDF',
      size: '640 Ko',
      date: '5 oct. 2026',
      scope: 'week',
      demo: true,
    })
    accounts.push({ username, email: `${username}@demo.racin.local`, password: DEMO_PASSWORD, first, last })
  })
  return { staff, files, plans, accounts }
}

const reportFiles = [
  { id: 'f1', person: 'zaina', name: 'Rapport_05_octobre.pdf', kind: 'PDF', size: '1,2 Mo', date: '5 oct. 2026', scope: 'week' },
  { id: 'f2', person: 'zaina', name: 'TIKO_TRANSIT_LOGISTICS.pdf', kind: 'PDF', size: '5,0 Mo', date: '5 oct. 2026', scope: 'week' },
  { id: 'f3', person: 'zaina', name: 'Rapport_02_octobre.docx', kind: 'DOC', size: '860 Ko', date: '2 oct. 2026', scope: 'month' },
  { id: 'f4', person: 'paul', name: 'Rapport_04_octobre.pdf', kind: 'PDF', size: '980 Ko', date: '4 oct. 2026', scope: 'month' },
  { id: 'f5', person: 'lucas', name: 'Rapport_05_octobre.pdf', kind: 'PDF', size: '740 Ko', date: '5 oct. 2026', scope: 'week' },
]

const adminAnswers: Record<string, string> = {
  "Qui n'a pas renseigné sa Todo List aujourd'hui ?": "Amina Diallo n'a pas renseigné sa Todo List. Elle est en congé aujourd'hui, ce n'est pas une absence non justifiée.",
  'Quels projets sont en retard ?': "Aucun projet n'est en retard. Identité visuelle Hôtel Baie arrive à échéance le 11 octobre et demande un suivi.",
  "Résume l'activité de l'équipe aujourd'hui.": "8 employés sont actifs. 18 activités sont terminées, 16 sont en cours et 3 sont en retard. Zaina a transmis son rapport.",
}

const employeeAnswers: Record<string, string> = {
  'Quelles sont mes tâches en retard ?': "Aucune tâche en retard. Les 5 tâches attribuées à zaina zaina sont terminées.",
  'Résume ma journée.': "Le rapport TIKO_TRANSIT__LOGISTICS_1 a été transmis le 5 octobre. Aucune tâche n'est ouverte aujourd'hui.",
  'Quel est mon prochain délai ?': "Aucune échéance ouverte. La dernière échéance enregistrée était le 10 septembre 2026, pour le site Marenova.",
}

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

function Button({ children, onClick, ghost = false, soft = false, type = 'button' }: { children: ReactNode; onClick?: () => void; ghost?: boolean; soft?: boolean; type?: 'button' | 'submit' }) {
  return <button className={`btn${ghost ? ' ghost' : ''}${soft ? ' soft' : ''}`} type={type} onClick={onClick}>{children}</button>
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

function Metric({ icon, tone, label, value, hint, hintTone = '', onClick, active = false }: { icon: string; tone: string; label: string; value: string; hint?: string; hintTone?: string; onClick?: () => void; active?: boolean }) {
  const body = (
    <>
      <span className={`metric-ico ${tone}`}><Icon name={icon} size={15} /></span>
      <span>
        <span className="metric-label">{label}</span>
        <strong className="metric-value">{value}</strong>
        {hint ? <span className={`metric-hint ${hintTone}`}>{hint}</span> : null}
      </span>
    </>
  )
  if (onClick) return <button className={`card metric${active ? ' on' : ''}`} type="button" onClick={onClick}>{body}</button>
  return <article className="card metric">{body}</article>
}

function LineChart() {
  const w = 520
  const h = 168
  const pad = 22
  const labels = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
  const series = [
    { color: '#10B981', data: [3, 4, 5, 4, 6, 5, 7] },
    { color: '#38BDF8', data: [5, 6, 4, 7, 6, 5, 6] },
    { color: '#F59E0B', data: [2, 3, 2, 3, 2, 2, 1] },
    { color: '#EF4444', data: [1, 1, 2, 1, 2, 1, 1] },
  ]
  const max = 8
  const x = (i: number) => pad + (i * (w - pad * 2)) / 6
  const y = (v: number) => h - pad - (v / max) * (h - pad * 2)
  const path = (data: number[]) => data.map((v, i) => `${i ? 'L' : 'M'}${x(i)},${y(v)}`).join(' ')
  const area = `${path(series[1].data)} L${x(6)},${h - pad} L${x(0)},${h - pad} Z`
  return (
    <svg className="chart" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Évolution des activités">
      {[0, 1, 2, 3].map((i) => {
        const gy = pad + (i * (h - pad * 2)) / 3
        return <line key={i} x1={pad} x2={w - pad} y1={gy} y2={gy} stroke="rgba(185,204,224,.18)" />
      })}
      <path d={area} fill="rgba(37,99,235,.18)" />
      {series.map((item) => <path key={item.color} d={path(item.data)} fill="none" stroke={item.color} strokeWidth="2" />)}
      {labels.map((label, i) => <text key={label} x={x(i)} y={h - 4} textAnchor="middle" fill="#87A2BB" fontSize="10">{label}</text>)}
    </svg>
  )
}

function Donut() {
  const parts = [
    { label: 'En cours', value: 6, color: '#2563EB' },
    { label: 'Terminés', value: 3, color: '#10B981' },
    { label: 'En attente', value: 2, color: '#F59E0B' },
    { label: 'En retard', value: 1, color: '#EF4444' },
  ]
  const r = 42
  const c = 2 * Math.PI * r
  let cursor = 0
  const arcs = parts.map((part) => {
    const len = (part.value / 12) * c
    const start = cursor
    cursor += len
    return { ...part, len, start }
  })
  return (
    <div className="donut-row">
      <svg width="132" height="132" viewBox="0 0 140 140" role="img" aria-label="12 projets">
        <g transform="rotate(-90 70 70)">
          {arcs.map((arc) => (
            <circle key={arc.label} cx="70" cy="70" r={r} fill="none" stroke={arc.color} strokeWidth="12" strokeDasharray={`${arc.len - 2} ${c - arc.len + 2}`} strokeDashoffset={-arc.start} />
          ))}
        </g>
        <text x="70" y="68" textAnchor="middle" fill="#F8FAFC" fontSize="20" fontWeight="600">12</text>
        <text x="70" y="84" textAnchor="middle" fill="#87A2BB" fontSize="10">projets</text>
      </svg>
      <div className="donut-legend">
        {arcs.map((arc) => (
          <div key={arc.label}><span><i style={{ background: arc.color }} />{arc.label}</span><strong>{arc.value}</strong></div>
        ))}
      </div>
    </div>
  )
}

function FilterBar({ children }: { children: ReactNode }) {
  return <div className="filters">{children}</div>
}

function AttentionCard({ icon, tone, flag, flagTone, value, label, action, onClick }: { icon: string; tone: string; flag: string; flagTone: string; value: string; label: string; action: string; onClick: () => void }) {
  return (
    <button className="card attn-card" type="button" onClick={onClick}>
      <div className="attn-top">
        <span className={`metric-ico ${tone}`}><Icon name={icon} size={14} /></span>
        <span className={`flag ${flagTone}`}>{flag}</span>
      </div>
      <strong>{value}</strong>
      <p>{label}</p>
      <em>{action}</em>
    </button>
  )
}

function statusClass(status: string) {
  if (status === 'Actif' || status === 'Terminée' || status === 'Terminé' || status === 'Approuvée' || status === 'Soumis') return 'ok'
  if (status === 'En congé' || status === 'En attente') return 'leave'
  if (status === 'En retard' || status === 'Critique' || status === 'Refusée') return 'late'
  return 'wait'
}

function AdminDashboard({ onNavigate }: { onNavigate: Go }) {
  const [sheet, setSheet] = useState(false)
  return (
    <section>
      <PageHeader
        title="Tableau de bord"
        subtitle="Vue d'ensemble de l'activité de l'agence"
        action={<Button onClick={() => setSheet(true)}><Icon name="spark" size={14} /> Générer la synthèse IA</Button>}
      />
      <div className="metrics m5">
        <Metric icon="users" tone="blue" label="Employés actifs" value="8 / 10" hint="+1 ce mois" hintTone="up" />
        <Metric icon="list" tone="cyan" label="Activités totales" value="42" />
        <Metric icon="check" tone="green" label="Activités terminées" value="18" hint="+12 % cette semaine" hintTone="up" />
        <Metric icon="clock" tone="orange" label="Activités en cours" value="16" />
        <Metric icon="alert" tone="red" label="Activités en retard" value="3" hint="À traiter" hintTone="warn" />
      </div>
      <div className="dash-grid">
        <article className="card card-pad">
          <h2>Évolution des activités</h2>
          <p className="sub">Nombre d'activités par statut au cours des 7 derniers jours</p>
          <LineChart />
          <div className="legend">
            <span><i style={{ background: '#10B981' }} />Terminées</span>
            <span><i style={{ background: '#38BDF8' }} />En cours</span>
            <span><i style={{ background: '#F59E0B' }} />Non commencées</span>
            <span><i style={{ background: '#EF4444' }} />En retard</span>
          </div>
        </article>
        <article className="card card-pad">
          <h2>État des projets</h2>
          <p className="sub">Répartition des projets enregistrés</p>
          <Donut />
        </article>
      </div>
      <h2 className="card-title" style={{ margin: '4px 0 8px' }}>Points d'attention</h2>
      <div className="attn">
        <AttentionCard icon="alert" tone="red" flag="À traiter" flagTone="" value="3" label="activités en retard" action="Ouvrir les activités" onClick={() => onNavigate('tasks')} />
        <AttentionCard icon="clock" tone="orange" flag="Cette semaine" flagTone="warn" value="2" label="projets proches de l'échéance" action="Voir les projets" onClick={() => onNavigate('projects')} />
        <AttentionCard icon="file" tone="blue" flag="Aujourd'hui" flagTone="info" value="1" label="difficulté signalée" action="Lire le détail" onClick={() => onNavigate('alerts')} />
      </div>
      {sheet ? (
        <article className="card card-pad" style={{ marginTop: 12 }}>
          <h2>Synthèse IA</h2>
          <p className="sub" style={{ marginTop: 6 }}>Lundi 5 octobre 2026 · 8 rapports analysés</p>
          <p style={{ marginTop: 8, color: 'var(--muted)', lineHeight: 1.5 }}>L'équipe avance sur Tiko Transit et l'identité Hôtel Baie. Trois activités restent en retard, surtout la validation du logo. Amina est en congé et n'a pas déposé de rapport.</p>
        </article>
      ) : null}
    </section>
  )
}

function EmployeeDashboard({ checks, onToggle, onNavigate }: { checks: string[]; onToggle: (id: string) => void; onNavigate: Go }) {
  const done = zainaTasks.filter((task) => checks.includes(task.id)).length
  const rate = Math.round((done / zainaTasks.length) * 100)
  return (
    <section>
      <PageHeader title={`Bonjour ${zaina.first}`} subtitle="Voici un aperçu de vos activités aujourd'hui." />
      <div className="metrics m5">
        <Metric icon="list" tone="cyan" label="Tâches attribuées" value={String(zainaTasks.length)} hint={`${done} terminée${done > 1 ? 's' : ''}`} />
        <Metric icon="check" tone="green" label="Taux d'achèvement" value={`${rate} %`} />
        <Metric icon="file" tone="orange" label="Rapport du jour" value="Envoyé" hint="5 oct. 2026" />
        <Metric icon="folder" tone="blue" label="Projets actifs" value={`0 / ${zainaProjects.length}`} />
        <Metric icon="calendar" tone="red" label="Prochaine échéance" value="—" hint="Aucune échéance ouverte" />
      </div>
      <div className="dash-grid">
        <article className="card card-pad">
          <div className="page-head" style={{ marginBottom: 4 }}>
            <h2>Mes tâches</h2>
            <button className="linkish" type="button" onClick={() => onNavigate('tasks')}>Voir toutes</button>
          </div>
          {zainaTasks.map((task) => {
            const on = checks.includes(task.id)
            return (
              <div className={`task-line${on ? ' done' : ''}`} key={task.id}>
                <button className={`check${on ? ' on' : ''}`} type="button" aria-label={task.title} onClick={() => onToggle(task.id)}>{on ? <Icon name="check" size={12} /> : null}</button>
                <span className="grow"><strong>{task.title}</strong><small className="muted">{task.project}</small></span>
                <span className={`prio ${task.tone}`}>{task.priority}</span>
              </div>
            )
          })}
        </article>
        <div className="stack">
          <article className="card card-pad">
            <h2>Votre rapport a été transmis</h2>
            <p className="sub" style={{ margin: '6px 0 10px' }}>TIKO_TRANSIT__LOGISTICS_1_qm2FN9H.pdf · 5 oct. 2026</p>
            <Button onClick={() => onNavigate('reports')}>Voir mon rapport</Button>
          </article>
          <article className="card card-pad">
            <h2>Mes projets</h2>
            <p className="sub">Aucun projet en cours. Les trois projets attribués sont terminés.</p>
            {zainaProjects.map((item) => (
              <div key={item.id} style={{ marginTop: 10 }}>
                <div className="project-meta"><span>{item.name}</span><strong>{item.progress} %</strong></div>
                <div className="bar done" style={{ marginTop: 6 }}><span style={{ width: `${item.progress}%` }} /></div>
              </div>
            ))}
          </article>
        </div>
      </div>
    </section>
  )
}

function EmployeesPage({ staff }: { staff: Staff[] }) {
  const [query, setQuery] = useState('')
  const [service, setService] = useState('')
  const [status, setStatus] = useState('')
  const actifs = staff.filter((person) => person.status === 'Actif').length
  const demoCount = staff.filter((person) => person.demo).length
  const rows = staff.filter((person) => {
    const blob = `${person.name} ${person.role} ${person.service}`.toLowerCase()
    return blob.includes(query.toLowerCase()) && (!service || person.service === service) && (!status || person.status === status)
  })
  return (
    <section>
      <PageHeader title="Employés" subtitle="Gérez les membres de votre équipe et suivez leur activité." action={<Button><Icon name="plus" size={14} /> Ajouter un employé</Button>} />
      <div className="metrics m4">
        <Metric icon="users" tone="cyan" label="Effectif total" value={String(staff.length)} />
        <Metric icon="check" tone="green" label="Présents aujourd'hui" value={String(actifs)} />
        <Metric icon="clock" tone="orange" label="Absents aujourd'hui" value={String(staff.length - actifs)} />
        <Metric icon="user" tone="blue" label="Démonstration" value={String(demoCount)} />
      </div>
      <FilterBar>
        <label className="search-field"><Icon name="search" size={14} /><input className="field" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher un employé..." /></label>
        <select className="field" value={service} onChange={(event) => setService(event.target.value)}>
          <option value="">Service</option>
          <option>Création</option>
          <option>Production</option>
          <option>Communication</option>
          <option>Digital</option>
        </select>
        <select className="field" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">Statut</option>
          <option>Actif</option>
          <option>En congé</option>
        </select>
        <Button ghost onClick={() => { setQuery(''); setService(''); setStatus('') }}>Réinitialiser</Button>
      </FilterBar>
      <div className="card table-wrap">
        <table>
          <thead><tr><th>Employé</th><th>Poste</th><th>Service</th><th>Statut</th><th>Todo List du jour</th><th>Dernière activité</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.map((person) => (
              <tr key={person.id}>
                <td><span className="who"><Avatar initials={person.initials} tone={person.tone} size="sm" online={person.online} />{person.name}</span></td>
                <td>{person.role}</td>
                <td>{person.service}</td>
                <td><span className={`status ${statusClass(person.status)}`}>{person.status}</span></td>
                <td>{person.todo}</td>
                <td className="muted">{person.seen}</td>
                <td><span className="icon-actions"><button type="button" aria-label="Voir"><Icon name="eye" size={13} /></button></span></td>
              </tr>
            ))}
            {rows.length === 0 ? <tr><td colSpan={7} className="empty">Aucun employé ne correspond.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function ProjectsPage({ role }: { role: Role }) {
  const [open, setOpen] = useState<string | null>(null)
  const list = role === 'employee' ? zainaProjects : projects
  const current = list.find((item) => item.id === open)
  return (
    <section>
      <PageHeader
        title={role === 'admin' ? 'Projets' : 'Mes projets'}
        subtitle={role === 'admin' ? 'Gérez tous vos projets et suivez leur progression.' : 'Les projets auxquels vous participez.'}
        action={role === 'admin' ? <Button><Icon name="plus" size={14} /> Nouveau projet</Button> : undefined}
      />
      <div className="project-grid">
        {list.map((item) => (
          <article className="card project-card" key={item.id}>
            <div className="project-top">
              <span className="metric-ico blue"><Icon name="folder" size={14} /></span>
              <span className={`status ${statusClass(item.status)}`}>{item.status}</span>
            </div>
            <h2>{item.name}</h2>
            <p className="sub">{item.client}</p>
            <p className="muted">Responsable : {item.owner}</p>
            <div className={`bar${item.progress === 100 ? ' done' : ''}`}><span style={{ width: `${item.progress}%` }} /></div>
            <div className="project-meta"><span>{item.progress} %</span><span>Échéance {item.due}</span></div>
            <button className="linkish" type="button" onClick={() => setOpen(item.id)}>Voir le projet</button>
          </article>
        ))}
      </div>
      {current ? (
        <article className="card card-pad" style={{ marginTop: 12 }}>
          <h2>{current.name}</h2>
          <p className="sub" style={{ marginTop: 4 }}>{current.client} · {current.owner} · {current.status}</p>
          <p style={{ marginTop: 8, color: 'var(--muted)' }}>Échéance le {current.due}. Avancement {current.progress} %. L'équipe prépare les livrables de la semaine.</p>
        </article>
      ) : null}
    </section>
  )
}

function TasksPage({ role, checks, onToggle }: { role: Role; checks: string[]; onToggle: (id: string) => void }) {
  const [tab, setTab] = useState('Tous')
  const [query, setQuery] = useState('')
  const source = role === 'admin' ? tasks : zainaTasks
  const counts = {
    Tous: source.length,
    'À faire': source.filter((task) => task.status === 'À faire').length,
    'En cours': source.filter((task) => task.status === 'En cours').length,
    'En retard': source.filter((task) => task.status === 'En retard').length,
    Terminées: source.filter((task) => task.status === 'Terminée').length,
  }
  const rows = source.filter((task) => (tab === 'Tous' || task.status === (tab === 'Terminées' ? 'Terminée' : tab)) && `${task.title} ${task.project}`.toLowerCase().includes(query.toLowerCase()))
  return (
    <section>
      <PageHeader
        kicker={role === 'admin' ? 'Espace responsable' : 'Mon espace'}
        title={role === 'admin' ? 'Tâches' : 'Mes tâches'}
        subtitle={role === 'admin' ? 'Gérez et attribuez les tâches de votre équipe.' : 'Les tâches qui vous ont été attribuées.'}
        action={role === 'admin' ? <Button><Icon name="plus" size={14} /> Nouvelle tâche</Button> : undefined}
      />
      <div className="metrics m5">
        {Object.entries(counts).map(([label, value]) => (
          <Metric key={label} icon="tasks" tone={label === 'En retard' ? 'red' : label === 'Terminées' ? 'green' : 'blue'} label={label} value={String(value)} onClick={() => setTab(label)} active={tab === label} />
        ))}
      </div>
      <FilterBar>
        <label className="search-field"><Icon name="search" size={14} /><input className="field" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Titre, projet..." /></label>
        {role === 'admin' ? <select className="field" defaultValue=""><option value="">Employé</option>{people.map((person) => <option key={person.id}>{person.name}</option>)}</select> : null}
      </FilterBar>
      <div className="card table-wrap">
        <table>
          <thead><tr>{role === 'employee' ? <th></th> : null}<th>Titre</th><th>Projet</th>{role === 'admin' ? <th>Assigné à</th> : null}<th>Priorité</th><th>Échéance</th><th>Statut</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.map((task) => (
              <tr key={task.id}>
                {role === 'employee' ? <td><button className={`check${checks.includes(task.id) ? ' on' : ''}`} type="button" aria-label={task.title} onClick={() => onToggle(task.id)}>{checks.includes(task.id) ? <Icon name="check" size={12} /> : null}</button></td> : null}
                <td>{task.title}</td>
                <td>{task.project}</td>
                {role === 'admin' ? <td>{task.who}</td> : null}
                <td><span className={`prio ${task.tone}`}>{task.priority}</span></td>
                <td>{task.due}</td>
                <td><span className={`status ${statusClass(task.status)}`}>{task.status}</span></td>
                <td><span className="icon-actions"><button type="button" aria-label="Voir"><Icon name="eye" size={13} /></button></span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function TodosPage({ role, staff, plans, username }: { role: Role; staff: Staff[]; plans: DayPlan[]; username: string }) {
  const [items, setItems] = useState<string[]>([])
  const [draft, setDraft] = useState('')
  const [done, setDone] = useState<string[]>([])
  if (role === 'admin') {
    return (
      <section>
        <PageHeader title="Todo Lists du jour" subtitle="Consultez et suivez les Todo Lists de tous les employés pour la journée." action={<Button ghost><Icon name="download" size={14} /> Exporter</Button>} />
        <div className="card table-wrap">
          <table>
            <thead><tr><th>Employé</th><th>Service</th><th>Tâches du jour</th><th>Avancement</th><th>État</th></tr></thead>
            <tbody>
              {staff.map((person) => {
                const plan = plans.find((item) => item.personId === person.id)
                const total = plan?.items.length ?? 0
                const finished = plan?.items.filter((item) => item.done).length ?? 0
                const filled = plan ? total > 0 : person.id !== 'amina'
                const width = plan ? `${total ? Math.round((finished / total) * 100) : 0}%` : person.id === 'amina' ? '0%' : '75%'
                return (
                  <tr key={person.id}>
                    <td><span className="who"><Avatar initials={person.initials} tone={person.tone} size="sm" />{person.name}</span></td>
                    <td>{person.service}</td>
                    <td className="muted">{plan && total ? plan.items.map((item) => item.text).join(' · ') : '—'}</td>
                    <td style={{ width: 160 }}><div className="bar"><span style={{ width }} /></div></td>
                    <td><span className={`status ${filled ? 'ok' : 'leave'}`}>{filled ? (plan ? `${finished} / ${total}` : 'Renseignée') : 'Non renseignée'}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    )
  }
  const mine = plans.find((item) => item.personId === username)
  if (mine) {
    return (
      <section>
        <PageHeader kicker="Mon espace" title="Todo List du jour" subtitle="Les tâches préparées pour votre journée." />
        <article className="card card-pad">
          {mine.items.map((item) => (
            <div className={`task-line${item.done ? ' done' : ''}`} key={item.id}>
              <span className={`check${item.done ? ' on' : ''}`}>{item.done ? <Icon name="check" size={12} /> : null}</span>
              <strong>{item.text}</strong>
            </div>
          ))}
        </article>
      </section>
    )
  }
  return (
    <section>
      <PageHeader kicker="Mon espace" title="Todo List du jour" subtitle="Préparez et cochez les tâches de votre journée." />
      <article className="card card-pad">
        {items.length === 0 ? <p className="muted">Aucune tâche dans la Todo List du jour.</p> : null}
        {items.map((item) => {
          const on = done.includes(item)
          return (
            <div className={`task-line${on ? ' done' : ''}`} key={item}>
              <button className={`check${on ? ' on' : ''}`} type="button" onClick={() => setDone((prev) => on ? prev.filter((entry) => entry !== item) : [...prev, item])}>{on ? <Icon name="check" size={12} /> : null}</button>
              <strong>{item}</strong>
            </div>
          )
        })}
        <form className="ask" onSubmit={(event) => { event.preventDefault(); if (!draft.trim()) return; setItems((prev) => [...prev, draft.trim()]); setDraft('') }}>
          <input className="field" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ajouter une tâche..." />
          <Button type="submit">Ajouter</Button>
        </form>
      </article>
    </section>
  )
}

function formatSize(bytes: number) {
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1).replace('.', ',')} Mo`
  return `${Math.max(1, Math.round(bytes / 1024))} Ko`
}

function openInBrowser(file: { name: string; url?: string; html?: string; kind?: string }) {
  if (file.html && file.kind !== 'PDF') {
    const title = file.name.replace(/[&<>"]/g, '')
    const page = `<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>${title}</title><style>body{font-family:Georgia,serif;max-width:760px;margin:40px auto;padding:0 16px;line-height:1.55;color:#10283f}img{max-width:100%}</style></head><body>${file.html}</body></html>`
    window.open(URL.createObjectURL(new Blob([page], { type: 'text/html' })), '_blank', 'noopener')
    return
  }
  if (file.url) window.open(file.url, '_blank', 'noopener')
}

function FileViewer({ file }: { file?: { name: string; url?: string; html?: string; kind?: string } | null }) {
  if (!file) return null
  if (file.url && file.kind !== 'DOC') return <iframe className="doc-frame" title={file.name} src={file.url} />
  if (file.html) return <div className="doc-preview doc-html" dangerouslySetInnerHTML={{ __html: file.html }} />
  return <p className="empty">Aucun fichier joint. Il pourra être ouvert ici dès qu'il aura été importé.</p>
}

function ReportsPage({ staff, library }: { staff: Staff[]; library: ReportFile[] }) {
  const firstOpenable = library.find((file) => file.url || file.html)
  const [personId, setPersonId] = useState(firstOpenable?.person ?? 'nouzou')
  const [scope, setScope] = useState('all')
  const [opened, setOpened] = useState(firstOpenable?.id ?? '')
  const person = staff.find((item) => item.id === personId) ?? staff[0]
  const files = library.filter((file) => (personId === 'all' || file.person === personId) && (scope === 'all' || (scope === 'week' ? file.scope === 'week' : true)))
  const current = library.find((file) => file.id === opened)
  return (
    <section>
      <PageHeader title="Rapports journaliers" subtitle="Consultez et gérez les rapports de votre équipe." />
      <FilterBar>
        <div className="chips">
          {[['all', 'Tous les rapports'], ['week', 'Cette semaine'], ['month', 'Ce mois']].map(([id, label]) => (
            <button key={id} className={`chip${scope === id ? ' on' : ''}`} type="button" onClick={() => setScope(id)}>{label}</button>
          ))}
        </div>
      </FilterBar>
      <div className="reports">
        <aside className="card card-pad">
          <h2 className="col-title">Employés</h2>
          <div className="scroll-list">
            <button className={`person${personId === 'all' ? ' on' : ''}`} type="button" onClick={() => setPersonId('all')}>
              <Avatar initials="+" tone="tone-navy" size="sm" />
              <span className="grow"><strong>Tous les employés</strong></span>
              <span className="count">{staff.length}</span>
            </button>
            {staff.map((item) => (
              <button className={`person${personId === item.id ? ' on' : ''}`} type="button" key={item.id} onClick={() => { setPersonId(item.id); const first = library.find((file) => file.person === item.id); if (first) setOpened(first.id) }}>
                <Avatar initials={item.initials} tone={item.tone} size="sm" online={item.online} />
                <span className="grow"><strong>{item.name}</strong><small>{item.role}</small></span>
                <span className="count">{library.filter((file) => file.person === item.id).length}</span>
              </button>
            ))}
          </div>
        </aside>
        <section className="card card-pad">
          <h2 className="col-title">Rapports de {personId === 'all' ? "l'équipe" : person.name} {person.online && personId !== 'all' ? <span className="online">En ligne</span> : null}</h2>
          <div className="scroll-list">
            {files.map((file) => (
              <div className={`file-row${opened === file.id ? ' on' : ''}`} key={file.id}>
                <span className={`ext${file.kind === 'DOC' ? ' doc' : ''}`}>{file.kind}</span>
                <span className="grow"><strong>{file.name}</strong><small>{file.size} · {file.date}</small></span>
                <span className="status ok">Soumis</span>
                <button className="btn ghost" type="button" onClick={() => { setOpened(file.id); openInBrowser(file) }} disabled={!file.url && !file.html}><Icon name="eye" size={13} /> Ouvrir</button>
              </div>
            ))}
            {files.length === 0 ? <p className="empty">Aucun rapport sur cette période.</p> : null}
          </div>
          {current ? <FileViewer file={current} /> : null}
        </section>
        <aside className="card card-pad report-side">
          <div className="profile">
            <Avatar initials={person.initials} tone={person.tone} size="lg" online={person.online} />
            <h2>{person.name}</h2>
            <p className="muted">{person.role} · {person.service}</p>
            {person.online ? <span className="online">En ligne</span> : null}
          </div>
          <div className="mini-stats">
            <div><strong>{person.reports}</strong><span>Rapports</span></div>
            <div><strong>{person.presence}</strong><span>Présence</span></div>
            <div><strong>8 min</strong><span>Activité</span></div>
          </div>
          <p className="muted">Dernier rapport</p>
          <p style={{ margin: '4px 0 10px', fontWeight: 600 }}>{current?.name ?? 'Aucun fichier'}</p>
          <Button ghost onClick={() => current && openInBrowser(current)}>Ouvrir dans le navigateur</Button>
        </aside>
      </div>
    </section>
  )
}

function EmployeeReport({ latest, history, error, onFile }: { latest: { name: string } | null; history: { date: string; name: string; size: string; url?: string; html?: string; kind?: string }[]; error: string; onFile: (file: File) => void }) {
  const picker = useRef<HTMLInputElement>(null)
  function take(list: FileList | null) {
    const file = list?.[0]
    if (file) onFile(file)
    if (picker.current) picker.current.value = ''
  }
  return (
    <section>
      <PageHeader title="Mon rapport journalier" subtitle="Importez votre rapport de la journée afin de le transmettre au responsable." />
      {latest ? <div className="notice"><Icon name="check" size={14} /> Vous avez importé <strong style={{ marginLeft: 4 }}>{latest.name}</strong>.</div> : null}
      <div className="two">
        <div
          className="drop"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => { event.preventDefault(); take(event.dataTransfer.files) }}
        >
          <input ref={picker} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" hidden onChange={(event) => take(event.target.files)} />
          <span className={`file-ico${latest ? ' ok' : ''}`}><Icon name={latest ? 'check' : 'file'} size={20} /></span>
          <h2>{latest ? 'Vous avez importé' : 'Importer mon rapport'}</h2>
          <p>{latest ? latest.name : 'Déposez votre fichier ici ou choisissez-le depuis votre PC'}</p>
          {latest ? <p>Ce fichier a été transmis au responsable.</p> : null}
          {error ? <p style={{ color: '#fca5a5' }}>{error}</p> : null}
          <Button onClick={() => picker.current?.click()}><Icon name="folder" size={14} /> {latest ? 'Choisir un autre fichier' : 'Choisir un fichier'}</Button>
          <p className="muted">Formats acceptés : PDF, DOCX<br />Taille maximale : 10 Mo</p>
        </div>
        <aside className="card tips">
          <h2>Quelques conseils</h2>
          <ul>
            <li><Icon name="check" size={13} /> Votre rapport doit contenir les principales activités de la journée.</li>
            <li><Icon name="check" size={13} /> Vous pouvez utiliser le format de votre choix, PDF ou Word.</li>
            <li><Icon name="check" size={13} /> Assurez-vous que le fichier soit lisible et bien nommé.</li>
          </ul>
        </aside>
      </div>
      <article className="card table-wrap" style={{ marginTop: 12 }}>
        <div className="card-pad" style={{ paddingBottom: 0 }}><h2>Mes rapports précédents</h2></div>
        <table>
          <thead><tr><th>Date d'envoi</th><th>Nom du fichier</th><th>Taille</th><th>Statut</th><th>Action</th></tr></thead>
          <tbody>
            {history.map((item) => (
              <tr key={`${item.date}-${item.name}`}>
                <td>{item.date}</td>
                <td>{item.name}</td>
                <td>{item.size}</td>
                <td><span className="status ok">Soumis</span></td>
                <td>{item.url || item.html ? <button className="linkish" type="button" onClick={() => openInBrowser(item)}>Voir</button> : <span className="muted">Aucun fichier</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>
    </section>
  )
}

type Note = { id: number; author: 'admin' | 'employee'; text: string }
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

function MessagingPage({ role, account, contacts, threads, unread, onSend, onRead }: { role: Role; account: Account; contacts: Account[]; threads: Record<string, Note[]>; unread: Record<string, { admin: number; employee: number }>; onSend: (username: string, text: string) => void; onRead: (username: string) => void }) {
  const extras = [
    { id: 'paul', name: 'Paul Mbia', initials: 'PM', tone: 'tone-sky', photo: '', online: false, time: '09:15', unread: 2, messages: [
      { id: 101, author: 'employee' as const, text: 'Le client Tiko a validé le calendrier.' },
      { id: 102, author: 'employee' as const, text: 'Je t’envoie le rétroplanning.' },
    ] },
    { id: 'lucas', name: 'Lucas Nguema', initials: 'LN', tone: 'tone-green', photo: '', online: true, time: 'Hier', unread: 0, messages: [
      { id: 201, author: 'admin' as const, text: 'Le formulaire de contact est en ligne ?' },
      { id: 202, author: 'employee' as const, text: 'Oui, il est prêt pour la recette.' },
    ] },
  ]
  const mine = role === 'admin' ? 'admin' : 'employee'
  const live = contacts.map((person) => ({
    id: person.username,
    name: role === 'admin' ? `${person.first} ${person.last}` : 'Responsable',
    initials: role === 'admin' ? `${person.first[0] ?? ''}${person.last[0] ?? ''}`.toUpperCase() : 'R',
    tone: role === 'admin' ? '' : 'tone-navy',
    photo: role === 'admin' && person.username === zaina.username ? zaina.photo : '',
    online: true,
    time: 'À l’instant',
    unread: (unread[person.username] ?? { admin: 0, employee: 0 })[mine],
    messages: threads[person.username] ?? [],
  }))
  const rows = role === 'admin' ? [...live, ...extras] : [live.find((item) => item.id === account.username) ?? live[0]]
  const [active, setActive] = useState(role === 'admin' ? zaina.username : account.username)
  const [filter, setFilter] = useState('all')
  const [draft, setDraft] = useState('')
  const [file, setFile] = useState(false)
  const [local, setLocal] = useState<Record<string, Note[]>>({})
  const chat = rows.find((item) => item.id === active) ?? rows[0]
  const shared = contacts.some((person) => person.username === chat.id)
  useEffect(() => { if (shared) onRead(chat.id) }, [chat.id, shared, onRead])
  const messages = shared ? (threads[chat.id] ?? []) : (local[chat.id] ?? chat.messages)
  const visible = rows.filter((item) => filter === 'all' || (filter === 'unread' ? item.unread > 0 : true))
  function send() {
    const text = draft.trim()
    if (!text) return
    if (shared) onSend(chat.id, text)
    else setLocal((prev) => ({ ...prev, [chat.id]: [...(prev[chat.id] ?? chat.messages), { id: Date.now(), author: 'admin', text }] }))
    setDraft('')
    setFile(false)
  }
  return (
    <section className="card msg-app">
      <aside className="msg-list">
        <h1 className="page-title">Messagerie</h1>
        <p className="page-sub" style={{ marginBottom: 10 }}>Communiquez directement avec votre équipe</p>
        <label className="search-field" style={{ marginBottom: 8 }}><Icon name="search" size={14} /><input className="field" placeholder="Rechercher une conversation..." style={{ width: '100%' }} /></label>
        <div className="chips" style={{ marginBottom: 8 }}>
          {[['all', 'Toutes'], ['unread', 'Non lus'], ['mine', 'Mes conversations']].map(([id, label]) => (
            <button key={id} className={`chip${filter === id ? ' on' : ''}`} type="button" onClick={() => setFilter(id)}>{label}</button>
          ))}
        </div>
        <div className="msg-scroll">
          {visible.map((item) => (
            <button className={`msg-row${item.id === chat.id ? ' on' : ''}`} type="button" key={item.id} onClick={() => setActive(item.id)}>
              <Avatar initials={item.initials} tone={item.tone} online={item.online} src={item.photo} />
              <span className="grow">
                <span className="msg-top"><strong>{item.name}</strong><time>{item.time}</time></span>
                <span className="msg-top"><p>{(contacts.some((person) => person.username === item.id) ? (threads[item.id] ?? []) : (local[item.id] ?? item.messages)).at(-1)?.text}</p>{item.unread ? <span className="pill blue">{item.unread}</span> : null}</span>
              </span>
            </button>
          ))}
        </div>
      </aside>
      <section className="msg-pane">
        <div className="msg-head">
          <Avatar initials={chat.initials} tone={chat.tone} online={chat.online} src={chat.photo} />
          <span><strong>{chat.name}</strong><small className="muted" style={{ display: 'block' }}>{chat.online ? 'En ligne' : 'Hors ligne'}</small></span>
        </div>
        <div className="msg-stream">
          {messages.map((message) => <div className={`bubble ${message.author === mine ? 'me' : 'them'}`} key={message.id}>{message.text}</div>)}
        </div>
        {file ? <p className="picked">Pièce jointe : Rapport_05_octobre.pdf</p> : null}
        <form className="composer" onSubmit={(event) => { event.preventDefault(); send() }}>
          <button className="icon-btn" type="button" aria-label="Joindre un fichier" onClick={() => setFile(true)}><Icon name="clip" size={14} /></button>
          <input className="field" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Écrire un message..." />
          <Button type="submit"><Icon name="send" size={13} /> Envoyer</Button>
        </form>
      </section>
    </section>
  )
}

function AssistantPage({ role }: { role: Role }) {
  const prompts = role === 'admin'
    ? ["Qui n'a pas renseigné sa Todo List aujourd'hui ?", 'Quels projets sont en retard ?', "Résume l'activité de l'équipe aujourd'hui."]
    : ['Quelles sont mes tâches en retard ?', 'Résume ma journée.', 'Quel est mon prochain délai ?']
  const bank = role === 'admin' ? adminAnswers : employeeAnswers
  const [log, setLog] = useState<{ q: string; a: string }[]>([])
  const [draft, setDraft] = useState('')
  function ask(question: string) {
    const text = question.trim()
    if (!text) return
    const answer = bank[text] ?? (role === 'admin'
      ? "D'après les données du jour, 8 employés sont actifs, 3 activités sont en retard et 2 projets arrivent à échéance cette semaine."
      : "Vos 5 tâches sont terminées et le rapport du 5 octobre a déjà été transmis.")
    setLog((prev) => [...prev, { q: text, a: answer }])
    setDraft('')
  }
  return (
    <section>
      <PageHeader title={role === 'admin' ? 'Assistant IA' : 'Mon assistant'} subtitle={role === 'admin' ? 'Analysez les données de votre agence et obtenez des réponses en langage naturel.' : 'Posez vos questions sur vos activités et vos projets.'} />
      <div className="banner">Votre assistant intelligent à votre service</div>
      <div className="ai-layout">
        <article className="card card-pad">
          <h2>Suggestions rapides</h2>
          {prompts.map((prompt) => (
            <button className="suggest" type="button" key={prompt} onClick={() => ask(prompt)}>
              <span className="metric-ico cyan"><Icon name="spark" size={14} /></span>
              <span><strong>{prompt}</strong><small>Réponse à partir des données du jour</small></span>
            </button>
          ))}
        </article>
        <article className="card card-pad">
          <div className="thread">
            {log.length === 0 ? <p className="muted">Choisissez une suggestion ou posez votre question.</p> : null}
            {log.map((entry) => (
              <div key={entry.q}>
                <div className="bubble me">{entry.q}</div>
                <div className="bubble them" style={{ marginTop: 8 }}>{entry.a}</div>
              </div>
            ))}
          </div>
          <form className="ask" onSubmit={(event) => { event.preventDefault(); ask(draft) }}>
            <input className="field" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Posez votre question..." />
            <Button type="submit">Envoyer</Button>
          </form>
        </article>
      </div>
    </section>
  )
}

function PermissionsPage({ role }: { role: Role }) {
  const all = [
    { who: 'Amina Diallo', type: 'Congé', dates: '7 oct. – 9 oct.', motif: 'Rendez-vous familial', status: 'En attente' },
    { who: 'Lucas Nguema', type: 'Permission', dates: '6 oct.', motif: 'Rendez-vous médical', status: 'Approuvée' },
    { who: 'Paul Mbia', type: 'Absence', dates: '2 oct.', motif: 'Mission client', status: 'Approuvée' },
    { who: 'Zaina Nouzou', type: 'Permission', dates: '15 oct.', motif: 'Formation', status: 'En attente' },
  ]
  const rows = role === 'admin' ? all : zainaPermissions
  const [filter, setFilter] = useState('Toutes')
  const [open, setOpen] = useState(false)
  const [sent, setSent] = useState(false)
  const shown = rows.filter((item) => filter === 'Toutes' || item.status === filter)
  return (
    <section>
      <PageHeader
        title={role === 'admin' ? 'Permissions' : 'Mes permissions'}
        subtitle={role === 'admin' ? 'Gérez les demandes de congés et permissions.' : 'Suivez vos demandes de congés et de permissions.'}
        action={role === 'employee' ? <Button onClick={() => setOpen(true)}><Icon name="plus" size={14} /> Nouvelle demande</Button> : undefined}
      />
      <div className="chips" style={{ marginBottom: 12 }}>
        {['Toutes', 'En attente', 'Approuvée'].map((item) => <button key={item} className={`chip${filter === item ? ' on' : ''}`} type="button" onClick={() => setFilter(item)}>{item}</button>)}
      </div>
      {sent ? <div className="notice"><Icon name="check" size={14} /> Votre demande a été envoyée au responsable.</div> : null}
      {open ? (
        <form className="card card-pad stack" style={{ marginBottom: 12 }} onSubmit={(event) => { event.preventDefault(); setOpen(false); setSent(true) }}>
          <div className="form-grid">
            <label>Type<select defaultValue="Permission"><option>Permission</option><option>Congé</option><option>Absence</option></select></label>
            <label>Motif<input defaultValue="Formation" /></label>
          </div>
          <div style={{ display: 'flex', gap: 8 }}><Button type="submit">Envoyer</Button><Button ghost onClick={() => setOpen(false)}>Annuler</Button></div>
        </form>
      ) : null}
      <div className="card table-wrap">
        <table>
          <thead><tr>{role === 'admin' ? <th>Employé</th> : null}<th>Type</th><th>Dates</th><th>Motif</th><th>Statut</th></tr></thead>
          <tbody>
            {shown.map((item) => (
              <tr key={`${item.who}-${item.dates}`}>
                {role === 'admin' ? <td>{item.who}</td> : null}
                <td>{item.type}</td>
                <td>{item.dates}</td>
                <td>{item.motif}</td>
                <td><span className={`status ${statusClass(item.status)}`}>{item.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function AlertsPage() {
  const alerts = [
    { level: 'Critique', title: 'Tâche en retard — Validation du logo', meta: 'Paul Mbia · 4 oct. 2026' },
    { level: 'Critique', title: 'Échéance proche — Identité Hôtel Baie', meta: 'Dans 6 jours' },
    { level: 'Avertissement', title: 'Rapport non envoyé', meta: 'Paul Mbia · aujourd’hui' },
    { level: 'Information', title: 'Todo List incomplète', meta: 'Amina Diallo · en congé' },
  ]
  return (
    <section>
      <PageHeader title="Centre d'alertes" subtitle="Restez informé des événements importants et des points d'attention de votre agence." action={<Button ghost><Icon name="check" size={14} /> Marquer tout comme lu</Button>} />
      <article className="card card-pad" style={{ marginBottom: 12 }}>
        <h2>Points de vigilance</h2>
        <p className="sub" style={{ marginTop: 6 }}>Trois activités restent ouvertes après leur échéance. Le projet Hôtel Baie arrive à terme cette semaine.</p>
      </article>
      <div className="card alert-list">
        {alerts.map((item) => (
          <div className="alert-item" key={item.title}>
            <span className={`metric-ico ${item.level === 'Critique' ? 'red' : item.level === 'Avertissement' ? 'orange' : 'blue'}`}><Icon name="bell" size={14} /></span>
            <span><strong>{item.title}</strong><small className="muted" style={{ display: 'block' }}>{item.meta}</small></span>
            <span className={`status ${statusClass(item.level === 'Critique' ? 'En retard' : item.level === 'Avertissement' ? 'En attente' : 'En cours')}`}>{item.level}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function NotificationsPage() {
  const items = [
    { title: 'Nouveau rapport de Zaina Nouzou', meta: 'Rapports · il y a 8 min' },
    { title: 'Nouvelle demande de permission', meta: 'Amina Diallo · il y a 1 h' },
    { title: 'Message non lu de Paul Mbia', meta: 'Messagerie · il y a 2 h' },
  ]
  const [read, setRead] = useState<string[]>([])
  return (
    <section>
      <PageHeader title="Notifications" subtitle="Retrouvez ici toutes les notifications de votre agence." />
      <div className="card">
        {items.map((item) => (
          <button className={`notif-item${read.includes(item.title) ? ' read' : ''}`} type="button" key={item.title} onClick={() => setRead((prev) => prev.includes(item.title) ? prev : [...prev, item.title])}>
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

function DemoPage({ counts, note, onGenerate, onReset, onNavigate }: { counts: { employees: number; reports: number; plans: number }; note: string; onGenerate: (count: number) => void; onReset: () => void; onNavigate: Go }) {
  const [count, setCount] = useState('10')
  const [confirm, setConfirm] = useState(false)
  const [error, setError] = useState('')
  return (
    <GenericPage title="Données de démonstration" subtitle="Ces enregistrements servent à la soutenance. Ils s'ajoutent aux employés déjà présents.">
      <div className="stack" style={{ maxWidth: 720 }}>
        <article className="card card-pad">
          <h2>Déjà préparées</h2>
          <div className="chips" style={{ marginTop: 10 }}>
            <span className="chip">{counts.employees} employés</span>
            <span className="chip">{counts.reports} rapports</span>
            <span className="chip">{counts.plans} todo lists</span>
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
          <div><Button onClick={() => onGenerate(Number(count))}><Icon name="database" size={14} /> Générer les données</Button></div>
          {note ? (
            <div className="notice">
              <Icon name="check" size={14} /> {note}
              <span style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                <button className="linkish" type="button" onClick={() => onNavigate('employees')}>Voir les employés</button>
                <button className="linkish" type="button" onClick={() => onNavigate('reports')}>Voir les rapports</button>
                <button className="linkish" type="button" onClick={() => onNavigate('todos')}>Voir les todo lists</button>
              </span>
            </div>
          ) : null}
        </article>
        <article className="card card-pad stack">
          <h2>Réinitialiser les données de démonstration</h2>
          <p className="muted">Seuls les employés, rapports et todo lists générés ici sont supprimés.</p>
          <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><input type="checkbox" checked={confirm} onChange={(event) => setConfirm(event.target.checked)} /> Je confirme la suppression.</label>
          {error ? <p className="muted" style={{ color: '#fca5a5' }}>{error}</p> : null}
          <div><Button ghost onClick={() => { if (!confirm) { setError('Cochez la confirmation avant de réinitialiser.'); return }; setError(''); onReset() }}>Réinitialiser</Button></div>
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
          <Avatar initials={admin ? 'KM' : initials} src={admin || !known ? '' : zaina.photo} size="lg" tone={admin ? 'tone-navy' : ''} />
          <span>
            <strong>{admin ? 'Karim Menga' : fullName}</strong>
            <small className="muted" style={{ display: 'block' }}>{admin ? 'Responsable' : known ? zaina.roleLabel : 'Employé'}</small>
            {admin ? null : <small className="muted" style={{ display: 'block' }}>{account.email}</small>}
            {admin || !known ? null : <small className="muted" style={{ display: 'block' }}>Membre depuis le {zaina.hired}</small>}
          </span>
        </div>
        <div className="form-grid">
          <label>Nom complet<input defaultValue={admin ? 'Karim Menga' : fullName} /></label>
          <label>Poste<input defaultValue={admin ? 'Responsable' : known ? zaina.job : 'Employé'} readOnly /></label>
          <label>E-mail<input defaultValue={admin ? 'karim@racin-agency.com' : account.email} /></label>
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

function Sidebar({ role, page, badge, onRole, onPage, onLogout }: { role: Role; page: string; badge: number; onRole: (role: Role) => void; onPage: Go; onLogout: () => void }) {
  const items = role === 'admin'
    ? [
        ['dashboard', 'Tableau de bord', 'grid'],
        ['employees', 'Employés', 'users'],
        ['projects', 'Projets', 'folder'],
        ['tasks', 'Tâches', 'tasks'],
        ['todos', 'Todo Lists du jour', 'list'],
        ['reports', 'Rapports journaliers', 'file'],
        ['permissions', 'Permissions', 'calendar', '1', 'orange'],
        ['alerts', "Centre d'alertes", 'bell', '4', 'blue'],
        ['messaging', 'Messagerie', 'message', badge ? String(badge) : '', 'blue'],
        ['notifications', 'Notifications', 'bell'],
        ['assistant', 'Assistant IA', 'spark'],
        ['demo', 'Données de démo', 'database'],
        ['settings', 'Paramètres', 'settings'],
      ]
    : [
        ['dashboard', 'Tableau de bord', 'grid'],
        ['projects', 'Mes projets', 'folder'],
        ['tasks', 'Mes tâches', 'tasks'],
        ['todos', 'Todo List du jour', 'list'],
        ['reports', 'Mon rapport', 'file'],
        ['permissions', 'Mes permissions', 'calendar'],
        ['messaging', 'Messagerie', 'message', badge ? String(badge) : '', 'blue'],
        ['assistant', 'Mon assistant', 'spark'],
        ['profile', 'Mon profil', 'user'],
      ]
  return (
    <aside className="sidebar">
      <Logo />
      <div className="role-switch">
        <button className={role === 'admin' ? 'on' : ''} type="button" onClick={() => onRole('admin')}>Responsable</button>
        <button className={role === 'employee' ? 'on' : ''} type="button" onClick={() => onRole('employee')}>Employé</button>
      </div>
      <nav className="side-nav">
        {items.map((item) => (
          <button key={item[0]} className={`nav-link${page === item[0] ? ' active' : ''}`} type="button" onClick={() => onPage(item[0])}>
            <Icon name={item[2]} size={15} />
            <span className="label">{item[1]}</span>
            {item[3] ? <span className={`pill ${item[4]}`}>{item[3]}</span> : null}
          </button>
        ))}
      </nav>
      <div className="side-foot">
        <div className="ai-card">
          <span className="metric-ico cyan"><Icon name="spark" size={14} /></span>
          <h3>{role === 'admin' ? 'Assistant IA' : 'Mon assistant'}</h3>
          <p>{role === 'admin' ? 'Posez vos questions et obtenez des analyses basées sur les données de votre plateforme.' : "Besoin d'aide ? Posez vos questions et obtenez des réponses sur vos activités et projets."}</p>
          <button className="link" type="button" onClick={() => onPage('assistant')}>Ouvrir l’assistant →</button>
        </div>
        <button className="logout-btn" type="button" onClick={onLogout}><Icon name="logout" size={14} /> Déconnexion</button>
      </div>
    </aside>
  )
}

function Topbar({ role, account, onNavigate }: { role: Role; account: Account; onNavigate: Go }) {
  const [query, setQuery] = useState('')
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
  const employeeName = `${account.first} ${account.last}`.trim() || account.username
  const profile = role === 'admin'
    ? { initials: 'KM', name: 'Karim Menga', job: 'Responsable', page: 'settings', tone: 'tone-navy', photo: '' }
    : {
        initials: `${account.first[0] ?? ''}${account.last[0] ?? ''}`.toUpperCase() || account.username.slice(0, 2).toUpperCase(),
        name: employeeName,
        job: account.username === zaina.username ? zaina.roleLabel : 'Employé',
        page: 'profile',
        tone: '',
        photo: account.username === zaina.username ? zaina.photo : '',
      }
  return (
    <header className="topbar">
      <label className="search">
        <span className="search-ico"><Icon name="search" size={14} /></span>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={role === 'admin' ? 'Rechercher un employé, un projet, une tâche...' : 'Rechercher un projet, une tâche...'} aria-label="Recherche" />
        {query.trim().length > 1 ? (
          <div className="search-drop">
            {results.map((item) => (
              <button key={item.label} type="button" onClick={() => { onNavigate(item.page); setQuery('') }}>
                {item.label}<small>{item.meta}</small>
              </button>
            ))}
            {results.length === 0 ? <button type="button">Aucun résultat</button> : null}
          </div>
        ) : null}
      </label>
      <div className="top-tools">
        <span className="date-chip"><Icon name="calendar" size={14} /> Lundi 5 octobre 2026</span>
        <button className="icon-btn" type="button" aria-label="Notifications" onClick={() => onNavigate(role === 'admin' ? 'notifications' : 'messaging')}>
          <Icon name="bell" size={15} />
          <span className="pill red">3</span>
        </button>
        <button className="user-chip" type="button" onClick={() => onNavigate(profile.page)}>
          <Avatar initials={profile.initials} tone={profile.tone} src={profile.photo} />
          <span><strong>{profile.name}</strong><small>{profile.job}</small></span>
          <Icon name="chevron" size={14} />
        </button>
      </div>
    </header>
  )
}

function Login({ accounts, onSuccess }: { accounts: Account[]; onSuccess: (account: Account) => void }) {
  const [mode, setMode] = useState<'login' | 'create'>('login')
  const [identifiant, setIdentifiant] = useState(zaina.username)
  const [motDePasse, setMotDePasse] = useState('nabihouddine')
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
          const found = accounts.find((item) => item.username === value || item.email === value)
          if (!found || found.password !== motDePasse) {
            setError('Identifiant ou mot de passe incorrect.')
            return
          }
          onSuccess(found)
        }}>
          <h2>Espace Employé</h2>
          <p className="intro">Connectez-vous avec le compte zaina enregistré dans la base.</p>
          <label>Identifiant<input value={identifiant} onChange={(event) => setIdentifiant(event.target.value)} autoComplete="username" required /></label>
          <label>Mot de passe<input type="password" value={motDePasse} onChange={(event) => setMotDePasse(event.target.value)} autoComplete="current-password" required /></label>
          {error ? <p className="intro" style={{ color: '#b91c1c' }}>{error}</p> : null}
          <div className="login-row">
            <label><input type="checkbox" defaultChecked /> Se souvenir de moi</label>
            <button type="button" onClick={() => { setMode('create'); setError('') }}>Créer un compte</button>
          </div>
          <button className="btn full" type="submit">Se connecter →</button>
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
  const [authed, setAuthed] = useState(false)
  const [role, setRole] = useState<Role>('employee')
  const [page, setPage] = useState('dashboard')
  const [checks, setChecks] = useState<string[]>(['6', '7', '8', '9', '10'])
  const [inbox, setInbox] = useState<ReportFile[]>([])
  const [importError, setImportError] = useState('')
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
  const [unread, setUnread] = useState<Record<string, { admin: number; employee: number }>>({})
  const [demoStaff, setDemoStaff] = useState<Staff[]>(() => {
    try { return (JSON.parse(localStorage.getItem('racin-demo') || '{}') as { staff?: Staff[] }).staff ?? [] } catch { return [] }
  })
  const [demoFiles, setDemoFiles] = useState<ReportFile[]>(() => {
    try { return (JSON.parse(localStorage.getItem('racin-demo') || '{}') as { files?: ReportFile[] }).files ?? [] } catch { return [] }
  })
  const [demoPlans, setDemoPlans] = useState<DayPlan[]>(() => {
    try { return (JSON.parse(localStorage.getItem('racin-demo') || '{}') as { plans?: DayPlan[] }).plans ?? [] } catch { return [] }
  })
  const [demoNote, setDemoNote] = useState('')
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
  useEffect(() => { localStorage.setItem('racin-threads', JSON.stringify(threads)) }, [threads])
  useEffect(() => { localStorage.setItem('racin-demo', JSON.stringify({ staff: demoStaff, files: demoFiles, plans: demoPlans })) }, [demoStaff, demoFiles, demoPlans])

  function go(next: string) {
    setPage(next)
  }
  function changeRole(next: Role) {
    setRole(next)
    const allowed = next === 'admin' ? adminPages : employeePages
    if (!allowed.includes(page)) setPage('dashboard')
  }
  function toggle(id: string) {
    setChecks((prev) => prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id])
  }
  function enter(next: Account) {
    setAccounts((prev) => prev.some((item) => item.username === next.username) ? prev : [...prev, next])
    setAccount(next)
    setThreads((prev) => prev[next.username] ? prev : { ...prev, [next.username]: [] })
    setRole('employee')
    setPage('dashboard')
    setAuthed(true)
  }
  function sendMessage(username: string, text: string) {
    const author = role === 'admin' ? 'admin' : 'employee'
    setThreads((prev) => ({ ...prev, [username]: [...(prev[username] ?? []), { id: Date.now(), author, text }] }))
    setUnread((prev) => {
      const current = prev[username] ?? { admin: 0, employee: 0 }
      const target = author === 'admin' ? 'employee' : 'admin'
      return { ...prev, [username]: { ...current, [target]: current[target] + 1 } }
    })
  }
  async function importReport(file: File) {
    const lower = file.name.toLowerCase()
    const pdf = lower.endsWith('.pdf')
    const docx = lower.endsWith('.docx')
    if (!pdf && !docx) {
      setImportError('Formats acceptés : PDF ou DOCX.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setImportError('Le fichier dépasse 10 Mo.')
      return
    }
    let html = ''
    if (docx) {
      const mammoth = await import('mammoth')
      const result = await mammoth.convertToHtml({ arrayBuffer: await file.arrayBuffer() })
      html = result.value
    }
    setInbox((prev) => [{
      id: `upload-${Date.now()}`,
      person: account.username,
      name: file.name,
      kind: pdf ? 'PDF' : 'DOC',
      size: formatSize(file.size),
      date: '5 oct. 2026',
      scope: 'week',
      url: URL.createObjectURL(file),
      html,
    }, ...prev])
    setImportError('')
  }
  function generateDemo(count: number) {
    const bundle = buildDemo(count)
    setDemoStaff(bundle.staff)
    setDemoFiles(bundle.files)
    setDemoPlans(bundle.plans)
    setAccounts((prev) => [...prev.filter((item) => !item.username.startsWith('demo.')), ...bundle.accounts])
    setThreads((prev) => {
      const next = { ...prev }
      Object.keys(next).forEach((key) => { if (key.startsWith('demo.')) delete next[key] })
      bundle.accounts.forEach((item) => { next[item.username] = [] })
      return next
    })
    setDemoNote(`${bundle.staff.length} employés, ${bundle.files.length} rapports et ${bundle.plans.length} todo lists ont été créés.`)
  }
  function resetDemo() {
    setDemoStaff([])
    setDemoFiles([])
    setDemoPlans([])
    setAccounts((prev) => prev.filter((item) => !item.username.startsWith('demo.')))
    setThreads((prev) => {
      const next = { ...prev }
      Object.keys(next).forEach((key) => { if (key.startsWith('demo.')) delete next[key] })
      return next
    })
    if (account.username.startsWith('demo.')) setAccount(zainaAccount)
    setDemoNote('')
  }
  function readMessages(username: string) {
    const target = role === 'admin' ? 'admin' : 'employee'
    setUnread((prev) => {
      const current = prev[username]
      if (!current || current[target] === 0) return prev
      return { ...prev, [username]: { ...current, [target]: 0 } }
    })
  }

  const messageBadge = role === 'admin'
    ? Object.values(unread).reduce((sum, item) => sum + item.admin, 0)
    : (unread[account.username]?.employee ?? 0)

  const view = useMemo(() => {
    const fresh = role === 'employee' && account.username !== zaina.username
    const demoAccount = account.username.startsWith('demo.')
    if (role === 'admin' && page === 'dashboard') return <AdminDashboard onNavigate={go} />
    if (fresh && !(demoAccount && ['todos', 'reports', 'dashboard'].includes(page)) && !['messaging', 'assistant', 'profile'].includes(page)) return <FreshSpace account={account} page={page} />
    if (role === 'employee' && demoAccount && page === 'dashboard') {
      const plan = demoPlans.find((item) => item.personId === account.username)
      const report = demoFiles.find((item) => item.person === account.username)
      return <FreshSpace account={account} page="dashboard" detail={`Votre todo list compte ${plan?.items.length ?? 0} tâches. Rapport transmis : ${report?.name ?? 'aucun'}.`} />
    }
    if (role === 'employee' && page === 'dashboard') return <EmployeeDashboard checks={checks} onToggle={toggle} onNavigate={go} />
    if (page === 'employees') return <EmployeesPage staff={staff} />
    if (page === 'projects') return <ProjectsPage role={role} />
    if (page === 'tasks') return <TasksPage role={role} checks={checks} onToggle={toggle} />
    if (page === 'todos') return <TodosPage role={role} staff={staff} plans={demoPlans} username={account.username} />
    if (page === 'reports' && role === 'admin') return <ReportsPage staff={reportStaff} library={library} />
    if (page === 'reports') {
      const mine = inbox.filter((file) => file.person === account.username)
      const previous = demoAccount ? demoFiles.filter((file) => file.person === account.username) : zainaReports
      const history = [...mine, ...previous.filter((item) => !mine.some((file) => file.name === item.name))]
      return <EmployeeReport latest={mine[0] ?? null} history={history} error={importError} onFile={(file) => { void importReport(file) }} />
    }
    if (page === 'permissions') return <PermissionsPage role={role} />
    if (page === 'alerts') return <AlertsPage />
    if (page === 'messaging') return <MessagingPage role={role} account={account} contacts={accounts} threads={threads} unread={unread} onSend={sendMessage} onRead={readMessages} />
    if (page === 'notifications') return <NotificationsPage />
    if (page === 'assistant') return <AssistantPage key={role} role={role} />
    if (page === 'demo') return <DemoPage counts={{ employees: demoStaff.length, reports: demoFiles.length, plans: demoPlans.length }} note={demoNote} onGenerate={generateDemo} onReset={resetDemo} onNavigate={go} />
    return <ProfilePage role={role} account={account} />
  }, [role, page, checks, account, accounts, threads, unread, demoStaff, demoFiles, demoPlans, demoNote, inbox, importError])

  if (!authed) return <Login accounts={accounts} onSuccess={enter} />

  return (
    <div className="app-shell">
      <Sidebar role={role} page={page} badge={messageBadge} onRole={changeRole} onPage={go} onLogout={() => setAuthed(false)} />
      <div className="workspace">
        <Topbar role={role} account={account} onNavigate={go} />
        <main>
          <div className="content">{view}</div>
        </main>
      </div>
    </div>
  )
}
