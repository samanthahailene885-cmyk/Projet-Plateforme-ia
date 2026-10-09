import { useEffect, useState, type FormEvent } from 'react'

export type LiveUser = {
  id: number
  username: string
  first: string
  last: string
  name: string
  initials: string
  role: 'admin' | 'employee'
  job: string
  can_switch?: boolean
}

type Employee = { id: number; name: string; username: string; initials: string }
type Project = {
  id: number
  name: string
  description: string
  client: string
  start_date: string
  end_date: string
  status_label: string
  priority_label: string
  progress: number
  task_count: number
  employees: Employee[]
}
type Doc = { id: number; name: string; url: string }
type TaskRow = {
  id: number
  title: string
  description: string
  project_id: number | null
  project: string
  employee: string
  status: string
  status_label: string
  priority_label: string
  due_date: string
  result_name: string
  result_url: string
  documents: Doc[]
}
type Notice = { text: string; ok: boolean }

function token() {
  const found = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))
  return found ? decodeURIComponent(found.split('=')[1]) : ''
}

async function readJson(response: Response) {
  const text = await response.text()
  if (!text) throw new Error('Le serveur de données ne répond pas. Relancez run.bat, puis réessayez.')
  try {
    return JSON.parse(text)
  } catch {
    throw new Error('Le serveur de données ne répond pas. Relancez run.bat, puis réessayez.')
  }
}

async function call(url: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData) && options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (options.method && options.method !== 'GET') headers.set('X-CSRFToken', token())
  const response = await fetch(url, { credentials: 'same-origin', ...options, headers })
  const data = await readJson(response)
  if (!response.ok) throw new Error(data.error || 'Action impossible.')
  return data
}

export async function openSession(): Promise<LiveUser | null> {
  const response = await fetch('/api/session/', { credentials: 'same-origin' })
  const data = await readJson(response)
  return data.authenticated ? data.user : null
}

export async function switchSession(): Promise<LiveUser> {
  const data = await call('/api/basculer/', { method: 'POST', body: '{}' })
  return data.user
}

export async function enterSession(username: string, password: string): Promise<LiveUser> {
  await openSession()
  const data = await call('/api/connexion/', { method: 'POST', body: JSON.stringify({ username, password }) })
  return data.user
}

export async function ensureAdminSession(): Promise<LiveUser> {
  await openSession()
  let current = await openSession()
  if (!current) current = await enterSession('admin', 'admin123')
  if (current.role !== 'admin') {
    try {
      const data = await call('/api/basculer/', { method: 'POST', body: '{}' })
      current = data.user as LiveUser
    } catch {
      current = await enterSession('admin', 'admin123')
    }
  }
  if (!current || current.role !== 'admin') current = await enterSession('admin', 'admin123')
  return current
}

export async function leaveSession() {
  await openSession()
  await call('/api/deconnexion/', { method: 'POST', body: '{}' })
}

export async function showSpace(next: 'admin' | 'employee') {
  let current = await openSession().catch(() => null)
  if (!current) current = await enterSession('admin', 'admin123')
  if (next === 'employee' && current.role === 'employee' && current.username !== 'nouzou') {
    current = await switchSession()
  }
  if (current.role !== next) current = await switchSession()
  return current
}

export { call as deskCall }

function Banner({ notice }: { notice: Notice | null }) {
  if (!notice) return null
  return <p className="notice" style={{ margin: '12px 0', color: notice.ok ? '#157a45' : '#b91c1c' }}>{notice.text}</p>
}

export function LiveProjects({ role }: { role: 'admin' | 'employee' }) {
  const [rows, setRows] = useState<Project[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [open, setOpen] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)

  async function load() {
    const data = await call(`/api/projets/?q=${encodeURIComponent(query)}&status=${encodeURIComponent(status)}`)
    setRows(data.projects)
  }
  useEffect(() => { load().catch((error) => setNotice({ text: error.message, ok: false })) }, [query, status])
  useEffect(() => {
    if (role !== 'admin') return
    call('/api/employes/').then((data) => setEmployees(data.employees)).catch(() => setEmployees([]))
  }, [role])

  if (open) return <ProjectDetail id={open} role={role} employees={employees} onBack={() => { setOpen(null); load() }} />
  if (creating) {
    return <ProjectForm employees={employees} onBack={() => setCreating(false)} onDone={(id, text) => { setCreating(false); setNotice({ text, ok: true }); setOpen(id) }} />
  }
  return (
    <section className="lp">
      <header className="lp-head">
        <div><p>Portefeuille</p><h1>{role === 'admin' ? 'Projets' : 'Mes projets'}</h1></div>
        {role === 'admin' ? <button className="lp-btn" type="button" onClick={() => setCreating(true)}>+ Nouveau projet</button> : null}
      </header>
      <Banner notice={notice} />
      <div className="lp-panel">
        <div className="lp-tools">
          <label><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher un projet..." /></label>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Tous les statuts</option>
            <option value="planning">À venir</option>
            <option value="in_progress">En cours</option>
            <option value="completed">Terminés</option>
            <option value="overdue">En retard</option>
            <option value="cancelled">Archivés</option>
          </select>
        </div>
        {rows.length === 0 ? <p style={{ padding: 18 }}>Aucun projet pour le moment. {role === 'admin' ? 'Créez le premier avec « Nouveau projet ».' : 'Vous verrez ici les projets qui vous sont confiés.'}</p> : null}
        <div className="lp-projects">
          {rows.map((item) => (
            <article key={item.id}>
              <div className="lp-card-top"><em className={item.status_label === 'Terminé' ? 'ok' : 'wait'}>{item.status_label}</em></div>
              <h2>{item.name}</h2>
              <p>{item.client}</p>
              <div className="lp-meta"><span>Début<small>{item.start_date}</small></span><span>Échéance<small>{item.end_date}</small></span></div>
              <div className="lp-progress"><span>Progression</span><b>{item.progress}%</b></div>
              <div className="lp-bar"><i style={{ width: `${item.progress}%` }} /></div>
              <footer>
                <span>{item.task_count} tâches</span>
                <span>{item.employees.map((person) => person.initials).join(' ') || '—'}</span>
                <button className="lp-btn" type="button" onClick={() => setOpen(item.id)}>Voir</button>
              </footer>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

function ProjectForm({ employees, onBack, onDone }: { employees: Employee[]; onBack: () => void; onDone: (id: number, text: string) => void }) {
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<number[]>([])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    try {
      const data = await call('/api/projets/', {
        method: 'POST',
        body: JSON.stringify({
          name: form.get('name'),
          description: form.get('description'),
          client: form.get('client'),
          start_date: form.get('start_date'),
          end_date: form.get('end_date'),
          priority: form.get('priority'),
          employees: selected,
        }),
      })
      onDone(data.project.id, 'Projet créé.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Création impossible.')
    }
  }
  return (
    <section className="lp">
      <header className="lp-head"><div><p>Projets</p><h1>Nouveau projet</h1></div><button className="lp-btn" type="button" onClick={onBack}>Retour</button></header>
      <form className="lp-panel" style={{ padding: 18, display: 'grid', gap: 10 }} onSubmit={submit}>
        <label>Nom du projet<input name="name" required placeholder="Campagne Marenova" /></label>
        <label>Description<textarea name="description" rows={3} /></label>
        <label>Client<input name="client" required /></label>
        <label>Date de début<input type="date" name="start_date" required /></label>
        <label>Date d'échéance<input type="date" name="end_date" required /></label>
        <label>Priorité<select name="priority" defaultValue="medium"><option value="low">Faible</option><option value="medium">Moyenne</option><option value="high">Haute</option><option value="urgent">Urgente</option></select></label>
        <fieldset>
          <legend>Employés associés</legend>
          {employees.map((person) => (
            <label key={person.id}><input type="checkbox" checked={selected.includes(person.id)} onChange={() => setSelected((prev) => prev.includes(person.id) ? prev.filter((id) => id !== person.id) : [...prev, person.id])} /> {person.name}</label>
          ))}
        </fieldset>
        {error ? <p style={{ color: '#b91c1c' }}>{error}</p> : null}
        <button className="lp-btn" type="submit">Créer le projet</button>
      </form>
    </section>
  )
}

function ProjectDetail({ id, role, employees, onBack }: { id: number; role: 'admin' | 'employee'; employees: Employee[]; onBack: () => void }) {
  const [project, setProject] = useState<Project | null>(null)
  const [tasks, setTasks] = useState<TaskRow[]>([])
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [focus, setFocus] = useState<number | null>(null)

  async function load() {
    const data = await call(`/api/projets/${id}/`)
    setProject(data.project)
    setTasks(data.tasks)
  }
  useEffect(() => { load().catch((error) => setNotice({ text: error.message, ok: false })) }, [id])

  async function archive() {
    await call(`/api/projets/${id}/`, { method: 'POST', body: JSON.stringify({ archive: true }) })
    onBack()
  }

  if (!project) return <section className="lp"><Banner notice={notice} /></section>
  if (focus) return <TaskSheet id={focus} role={role} onBack={() => { setFocus(null); load() }} />
  if (adding && role === 'admin') {
    return <TaskForm projectId={project.id} employees={project.employees.length ? project.employees : employees} onBack={() => setAdding(false)} onDone={async (text) => { setAdding(false); setNotice({ text, ok: true }); await load() }} />
  }
  return (
    <section className="lp">
      <header className="lp-head">
        <div><p>{project.client}</p><h1>{project.name}</h1></div>
        <span>
          <button className="lp-btn" type="button" onClick={onBack}>Retour</button>
          {role === 'admin' ? <button className="lp-btn" type="button" onClick={() => setEditing((value) => !value)}>Modifier</button> : null}
          {role === 'admin' ? <button className="lp-btn" type="button" onClick={archive}>Archiver</button> : null}
        </span>
      </header>
      <Banner notice={notice} />
      <div className="lp-panel" style={{ padding: 18 }}>
        <p>{project.description || 'Sans description.'}</p>
        <p>Du {project.start_date} au {project.end_date} · {project.status_label} · Priorité {project.priority_label}</p>
        <div className="lp-progress"><span>Progression calculée</span><b>{project.progress}%</b></div>
        <div className="lp-bar"><i style={{ width: `${project.progress}%` }} /></div>
        {editing ? <ProjectEdit project={project} employees={employees} onSaved={async () => { setEditing(false); await load() }} /> : null}
        <h2>Employés du projet</h2>
        <p>{project.employees.map((person) => person.name).join(', ') || 'Aucun employé associé.'}</p>
        <h2>{role === 'admin' ? 'Tâches du projet' : 'Mes tâches sur ce projet'}</h2>
        {role === 'admin' ? <button className="lp-btn" type="button" onClick={() => setAdding(true)}>+ Ajouter une tâche</button> : null}
        <ul>
          {tasks.map((task) => (
            <li key={task.id}>
              <strong>{task.title}</strong> — {task.employee || 'Non assignée'} — {task.status_label} — {task.priority_label} — {task.due_date || 'sans échéance'}
              <button className="lp-btn" type="button" onClick={() => setFocus(task.id)}>Voir</button>
            </li>
          ))}
        </ul>
        {tasks.length === 0 ? <p>Aucune tâche pour le moment.</p> : null}
      </div>
    </section>
  )
}

function ProjectEdit({ project, employees, onSaved }: { project: Project; employees: Employee[]; onSaved: () => void }) {
  const [selected, setSelected] = useState<number[]>(project.employees.map((person) => person.id))
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    await call(`/api/projets/${project.id}/`, {
      method: 'POST',
      body: JSON.stringify({
        name: form.get('name'),
        description: form.get('description'),
        client: form.get('client'),
        start_date: form.get('start_date'),
        end_date: form.get('end_date'),
        priority: form.get('priority'),
        employees: selected,
      }),
    })
    onSaved()
  }
  return (
    <form onSubmit={submit} style={{ display: 'grid', gap: 8, marginTop: 12 }}>
      <input name="name" defaultValue={project.name} required />
      <input name="client" defaultValue={project.client} required />
      <textarea name="description" defaultValue={project.description} />
      <input type="date" name="start_date" defaultValue={project.start_date} />
      <input type="date" name="end_date" defaultValue={project.end_date} />
      <select name="priority" defaultValue="medium"><option value="low">Faible</option><option value="medium">Moyenne</option><option value="high">Haute</option></select>
      {employees.map((person) => (
        <label key={person.id}><input type="checkbox" checked={selected.includes(person.id)} onChange={() => setSelected((prev) => prev.includes(person.id) ? prev.filter((id) => id !== person.id) : [...prev, person.id])} /> {person.name}</label>
      ))}
      <button className="lp-btn" type="submit">Enregistrer</button>
    </form>
  )
}

function TaskForm({ projectId, employees, onBack, onDone }: { projectId: number; employees: Employee[]; onBack: () => void; onDone: (text: string) => void }) {
  const [error, setError] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const body = new FormData(event.currentTarget)
    body.set('project', String(projectId))
    try {
      const data = await call('/api/taches/', { method: 'POST', body })
      onDone(data.message)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Attribution impossible.')
    }
  }
  return (
    <section className="lp">
      <header className="lp-head"><div><h1>Ajouter une tâche</h1></div><button className="lp-btn" type="button" onClick={onBack}>Retour</button></header>
      <form className="lp-panel" style={{ padding: 18, display: 'grid', gap: 10 }} onSubmit={submit}>
        <label>Titre<input name="title" required placeholder="Préparer le visuel principal" /></label>
        <label>Description<textarea name="description" rows={3} /></label>
        <label>Employé responsable<select name="employee" required>{employees.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}</select></label>
        <label>Priorité<select name="priority" defaultValue="high"><option value="low">Faible</option><option value="medium">Moyenne</option><option value="high">Haute</option><option value="urgent">Urgente</option></select></label>
        <label>Date de début<input type="date" name="start_date" /></label>
        <label>Date limite<input type="date" name="due_date" required /></label>
        <label>Ajouter un document<input type="file" name="documents" /></label>
        {error ? <p style={{ color: '#b91c1c' }}>{error}</p> : null}
        <button className="lp-btn" type="submit">Créer et attribuer</button>
      </form>
    </section>
  )
}

export function LiveTasks({ role }: { role: 'admin' | 'employee' }) {
  const [rows, setRows] = useState<TaskRow[]>([])
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [focus, setFocus] = useState<number | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  async function load() {
    const data = await call(`/api/taches/?q=${encodeURIComponent(query)}&status=${encodeURIComponent(status)}`)
    setRows(data.tasks.filter((item: TaskRow & { planned_date?: string }) => !(item.planned_date && !item.due_date)))
  }
  useEffect(() => { load().catch((error) => setNotice({ text: error.message, ok: false })) }, [query, status])
  if (focus) return <TaskSheet id={focus} role={role} onBack={() => { setFocus(null); load() }} />
  const counts = {
    all: rows.length,
    todo: rows.filter((item) => item.status === 'todo' && item.status_label !== 'En retard').length,
    in_progress: rows.filter((item) => item.status === 'in_progress' && item.status_label !== 'En retard').length,
    completed: rows.filter((item) => item.status === 'completed').length,
    overdue: rows.filter((item) => item.status_label === 'En retard').length,
  }
  return (
    <section className="lp">
      <header className="lp-head"><div><p>Activités</p><h1>{role === 'admin' ? 'Gestion des tâches' : 'Mes tâches'}</h1></div></header>
      <Banner notice={notice} />
      <div className="lp-chips">
        {[['','Toutes', counts.all], ['todo','À faire', counts.todo], ['in_progress','En cours', counts.in_progress], ['completed','Terminées', counts.completed], ['overdue','En retard', counts.overdue]].map(([value, label, count]) => (
          <button key={String(label)} className={status === value ? 'on' : ''} type="button" onClick={() => setStatus(String(value))}>{label} <b>{count}</b></button>
        ))}
      </div>
      <div className="lp-panel">
        <div className="lp-tools"><label><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher une tâche..." /></label></div>
        <table className="lp-table">
          <thead><tr><th>Tâche</th><th>Projet</th><th>Employé</th><th>Priorité</th><th>Échéance</th><th>Statut</th><th></th></tr></thead>
          <tbody>
            {rows.map((task) => (
              <tr key={task.id}>
                <td><strong>{task.title}</strong></td>
                <td>{task.project}</td>
                <td>{task.employee}</td>
                <td>{task.priority_label}</td>
                <td>{task.due_date}</td>
                <td>{task.status_label}</td>
                <td><button type="button" onClick={() => setFocus(task.id)}>Voir</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 ? <p style={{ padding: 16 }}>Aucune tâche enregistrée.</p> : null}
      </div>
    </section>
  )
}

function TaskSheet({ id, role, onBack }: { id: number; role: 'admin' | 'employee'; onBack: () => void }) {
  const [task, setTask] = useState<TaskRow | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  async function load() {
    const data = await call(`/api/taches/${id}/`)
    setTask(data.task)
  }
  useEffect(() => { load().catch((error) => setNotice({ text: error.message, ok: false })) }, [id])
  async function status(next: string) {
    const data = await call(`/api/taches/${id}/statut/`, { method: 'POST', body: JSON.stringify({ status: next }) })
    setNotice({ text: data.message, ok: true })
    setTask(data.task)
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const body = new FormData(event.currentTarget)
    const data = await call(`/api/taches/${id}/resultat/`, { method: 'POST', body })
    setNotice({ text: data.message, ok: true })
    setTask(data.task)
  }
  if (!task) return <section className="lp"><Banner notice={notice} /></section>
  return (
    <section className="lp">
      <header className="lp-head"><div><p>{task.project}</p><h1>{task.title}</h1></div><button className="lp-btn" type="button" onClick={onBack}>Retour</button></header>
      <Banner notice={notice} />
      <div className="lp-panel" style={{ padding: 18, display: 'grid', gap: 10 }}>
        <p>{task.description || 'Sans description.'}</p>
        <p>Employé : {task.employee || '—'} · Priorité : {task.priority_label} · Échéance : {task.due_date || '—'} · Statut : {task.status_label}</p>
        {task.documents.map((document) => <a key={document.id} href={document.url}>Télécharger {document.name}</a>)}
        {role === 'employee' && task.status === 'todo' ? <button className="lp-btn" type="button" onClick={() => status('in_progress')}>Commencer</button> : null}
        {role === 'employee' && task.status !== 'completed' ? (
          <form onSubmit={upload}>
            <label>Déposer mon travail<input type="file" name="result" required /></label>
            <button className="lp-btn" type="submit">Déposer mon travail</button>
          </form>
        ) : null}
        {task.result_name ? <a href={task.result_url}>Fichier déposé : {task.result_name}</a> : null}
        {role === 'employee' && task.status !== 'completed' ? <button className="lp-btn" type="button" onClick={() => status('completed')}>Marquer comme terminée</button> : null}
      </div>
    </section>
  )
}

export function LiveTodos({ role }: { role: 'admin' | 'employee' }) {
  const [items, setItems] = useState<TaskRow[]>([])
  const [board, setBoard] = useState<{ employee: Employee; filled: boolean; done: number; doing: number; waiting: number }[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [tasks, setTasks] = useState<TaskRow[]>([])
  const [notice, setNotice] = useState<Notice | null>(null)
  async function load() {
    if (role === 'admin') {
      const data = await call('/api/todos/')
      setBoard(data.board)
      return
    }
    const [mine, projectData, taskData] = await Promise.all([call('/api/todos/'), call('/api/projets/'), call('/api/taches/')])
    setItems(mine.items)
    setProjects(projectData.projects)
    setTasks(taskData.tasks)
  }
  useEffect(() => { load().catch((error) => setNotice({ text: error.message, ok: false })) }, [role])
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const data = await call('/api/todos/', { method: 'POST', body: JSON.stringify({ title: form.get('title'), project: form.get('project'), task: form.get('task') }) })
    setNotice({ text: data.message, ok: true })
    event.currentTarget.reset()
    await load()
  }
  async function finish(id: number) {
    await call(`/api/taches/${id}/statut/`, { method: 'POST', body: JSON.stringify({ status: 'completed' }) })
    await load()
  }
  return (
    <section className="lp">
      <header className="lp-head"><div><p>Aujourd'hui</p><h1>{role === 'admin' ? 'Todo Lists' : 'Ma Todo List'}</h1></div></header>
      <Banner notice={notice} />
      {role === 'employee' ? (
        <form className="lp-panel" style={{ padding: 18, display: 'grid', gap: 8 }} onSubmit={add}>
          <h2>Ajouter une activité</h2>
          <input name="title" required placeholder="Finaliser le visuel Marenova" />
          <select name="project" defaultValue=""><option value="">Projet</option>{projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
          <select name="task" defaultValue=""><option value="">Tâche associée</option>{tasks.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select>
          <button className="lp-btn" type="submit">Ajouter</button>
        </form>
      ) : null}
      <div className="lp-panel" style={{ padding: 18 }}>
        {role === 'admin' ? board.map((row) => (
          <p key={row.employee.id}><strong>{row.employee.name}</strong> — {row.filled ? `✓ ${row.done} terminées · ${row.doing} en cours · ${row.waiting} non commencées` : 'Todo List non renseignée'}</p>
        )) : items.map((item) => (
          <p key={item.id}>{item.status === 'completed' ? '✓' : '○'} {item.title} — {item.status_label} {item.status !== 'completed' ? <button type="button" onClick={() => finish(item.id)}>Terminer</button> : null}</p>
        ))}
        {role === 'employee' && items.length === 0 ? <p>Aucune activité aujourd'hui.</p> : null}
      </div>
    </section>
  )
}

export function LiveReports({ role }: { role: 'admin' | 'employee' }) {
  const [rows, setRows] = useState<{ name: string; submitted: boolean; filename: string; url: string; sent_at: string; date?: string }[]>([])
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [notice, setNotice] = useState<Notice | null>(null)
  const [synthesis, setSynthesis] = useState('')
  async function load() {
    const data = await call(`/api/rapports/?date=${date}`)
    setRows(data.reports)
  }
  useEffect(() => { load().catch((error) => setNotice({ text: error.message, ok: false })) }, [date, role])
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const body = new FormData(event.currentTarget)
    body.set('date', date)
    const data = await call('/api/rapports/', { method: 'POST', body })
    setNotice({ text: data.message, ok: true })
    await load()
  }
  async function synthesize() {
    await openSession()
    const response = await fetch('/reports/synthese/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': token() },
      body: new URLSearchParams({ date }),
    })
    const data = await response.json()
    if (!response.ok || !data.ok) {
      setNotice({ text: data.error || 'Synthèse indisponible.', ok: false })
      setSynthesis('')
      return
    }
    setSynthesis(data.synthesis)
  }
  return (
    <section className="lp">
      <header className="lp-head"><div><p>Rapports</p><h1>{role === 'admin' ? 'Rapports journaliers' : 'Mon rapport journalier'}</h1></div></header>
      <Banner notice={notice} />
      <div className="lp-panel" style={{ padding: 18 }}>
        <label>Date <input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
        {role === 'employee' ? (
          <form onSubmit={send} style={{ display: 'grid', gap: 8, marginTop: 12 }}>
            <label>Importer mon rapport<input type="file" name="file" accept=".pdf,.docx" required /></label>
            <button className="lp-btn" type="submit">Envoyer le rapport</button>
          </form>
        ) : (
          <div>
            {rows.map((row) => (
              <p key={row.name}>{row.submitted ? '✓' : '✕'} {row.name} — {row.submitted ? <a href={row.url} target="_blank" rel="noreferrer">{row.filename}</a> : 'Non soumis'}</p>
            ))}
            <button className="lp-btn" type="button" onClick={synthesize}>Générer la synthèse IA</button>
            {synthesis ? <pre style={{ whiteSpace: 'pre-wrap' }}>{synthesis}</pre> : null}
          </div>
        )}
        {role === 'employee' ? rows.map((row) => <p key={row.date || row.name}>{row.date} — {row.url ? <a href={row.url}>{row.name}</a> : row.name}</p>) : null}
      </div>
    </section>
  )
}

export function LivePermissions({ role }: { role: 'admin' | 'employee' }) {
  const [rows, setRows] = useState<{ id: number; employee: string; start_date: string; end_date: string; reason: string; status: string; status_label: string }[]>([])
  const [notice, setNotice] = useState<Notice | null>(null)
  async function load() {
    const data = await call('/api/permissions/')
    setRows(data.permissions)
  }
  useEffect(() => { load().catch((error) => setNotice({ text: error.message, ok: false })) }, [])
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const data = await call('/api/permissions/', { method: 'POST', body: JSON.stringify({ start_date: form.get('start_date'), end_date: form.get('end_date'), reason: form.get('reason') }) })
    setNotice({ text: data.message, ok: true })
    await load()
  }
  async function decide(id: number, status: string) {
    const data = await call(`/api/permissions/${id}/`, { method: 'POST', body: JSON.stringify({ status }) })
    setNotice({ text: data.message, ok: true })
    await load()
  }
  return (
    <section className="lp">
      <header className="lp-head"><div><h1>{role === 'admin' ? 'Permissions' : 'Mes permissions'}</h1></div></header>
      <Banner notice={notice} />
      {role === 'employee' ? (
        <form className="lp-panel" style={{ padding: 18, display: 'grid', gap: 8 }} onSubmit={send}>
          <h2>Nouvelle demande</h2>
          <label>Date de début<input type="date" name="start_date" required /></label>
          <label>Date de fin<input type="date" name="end_date" required /></label>
          <label>Motif<input name="reason" required /></label>
          <button className="lp-btn" type="submit">Envoyer la demande</button>
        </form>
      ) : null}
      <div className="lp-panel" style={{ padding: 18 }}>
        {rows.map((row) => (
          <p key={row.id}>{row.employee} · {row.start_date} → {row.end_date} · {row.reason} · {row.status_label}
            {role === 'admin' && row.status === 'pending' ? <>
              <button type="button" onClick={() => decide(row.id, 'approved')}>Accepter</button>
              <button type="button" onClick={() => decide(row.id, 'rejected')}>Refuser</button>
            </> : null}
          </p>
        ))}
        {rows.length === 0 ? <p>Aucune demande.</p> : null}
      </div>
    </section>
  )
}

export function LiveAlerts() {
  const [rows, setRows] = useState<{ kind: string; title: string; text: string }[]>([])
  useEffect(() => { call('/api/alertes/').then((data) => setRows(data.alerts)).catch(() => setRows([])) }, [])
  return (
    <section className="lp">
      <header className="lp-head"><div><h1>Centre d'alertes</h1></div></header>
      <div className="lp-panel" style={{ padding: 18 }}>
        {rows.map((row, index) => <p key={`${row.kind}-${index}`}><strong>{row.title}</strong> — {row.text}</p>)}
        {rows.length === 0 ? <p>Aucune alerte active.</p> : null}
      </div>
    </section>
  )
}

export function LiveNotifications({ onOpen }: { onOpen: (page: string) => void }) {
  const [rows, setRows] = useState<{ id: number; title: string; message: string; read: boolean; created_at: string }[]>([])
  async function load() {
    const data = await call('/api/notifications/')
    setRows(data.notifications)
  }
  useEffect(() => { load().catch(() => setRows([])) }, [])
  async function read(id: number, title: string) {
    await call('/api/notifications/', { method: 'POST', body: JSON.stringify({ id }) })
    await load()
    if (title.toLowerCase().includes('tâche')) onOpen('tasks')
    else if (title.toLowerCase().includes('rapport')) onOpen('reports')
    else if (title.toLowerCase().includes('permission')) onOpen('permissions')
    else if (title.toLowerCase().includes('message') || title.toLowerCase().includes('appel')) onOpen('messaging')
  }
  return (
    <section className="lp">
      <header className="lp-head"><div><h1>Notifications</h1></div><button className="lp-btn" type="button" onClick={async () => { await call('/api/notifications/', { method: 'POST', body: JSON.stringify({ all: true }) }); await load() }}>Tout marquer comme lu</button></header>
      <div className="lp-panel" style={{ padding: 18 }}>
        {rows.map((row) => (
          <p key={row.id}><button type="button" onClick={() => read(row.id, row.title)}>{row.read ? 'Lu' : 'Marquer comme lu'}</button> <strong>{row.title}</strong> — {row.message} <small>{row.created_at}</small></p>
        ))}
        {rows.length === 0 ? <p>Aucune notification.</p> : null}
      </div>
    </section>
  )
}

export function LiveMessages({ role }: { role: 'admin' | 'employee' }) {
  const [contacts, setContacts] = useState<Employee[]>([])
  const [withId, setWithId] = useState<number | null>(null)
  const [lines, setLines] = useState<{ id: number; mine: boolean; author: string; text: string; at: string }[]>([])
  const [contactName, setContactName] = useState('')
  const [notice, setNotice] = useState<Notice | null>(null)
  async function load(partner = withId) {
    const url = role === 'admin' && partner ? `/api/messages/?with=${partner}` : '/api/messages/'
    const data = await call(url)
    if (role === 'admin') {
      setContacts(data.contacts || [])
      setLines(data.messages || [])
    } else {
      setContactName(data.contact?.name || 'Responsable')
      setLines(data.messages || [])
    }
  }
  useEffect(() => { load().catch((error) => setNotice({ text: error.message, ok: false })) }, [withId])
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const payload: Record<string, unknown> = { text: form.get('text') }
    if (role === 'admin') payload.with = withId
    await call('/api/messages/', { method: 'POST', body: JSON.stringify(payload) })
    event.currentTarget.reset()
    await load()
  }
  async function ask(kind: string) {
    const data = await call('/api/messages/', { method: 'POST', body: JSON.stringify({ kind, text: kind === 'problem' ? 'Je souhaite signaler un problème.' : '' }) })
    setNotice({ text: data.message, ok: true })
    await load()
  }
  return (
    <section className="lp">
      <header className="lp-head"><div><h1>{role === 'admin' ? 'Messagerie' : 'Messagerie avec mon responsable'}</h1><p>{contactName}</p></div></header>
      <Banner notice={notice} />
      <div className="lp-panel" style={{ padding: 18 }}>
        {role === 'admin' ? <select value={withId ?? ''} onChange={(event) => setWithId(Number(event.target.value))}><option value="">Choisir un employé</option>{contacts.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}</select> : null}
        {lines.map((line) => <p key={line.id}><strong>{line.author}</strong> {line.text} <small>{line.at}</small></p>)}
        <form onSubmit={send} style={{ display: 'flex', gap: 8 }}>
          <input name="text" placeholder="Écrire un message" required style={{ flex: 1 }} />
          <button className="lp-btn" type="submit">Envoyer</button>
        </form>
        {role === 'employee' ? <p><button type="button" onClick={() => ask('problem')}>Signaler un problème</button> <button type="button" onClick={() => ask('meeting')}>Demander à parler au responsable</button></p> : null}
      </div>
    </section>
  )
}

export function LiveDifficulty() {
  const [projects, setProjects] = useState<Project[]>([])
  const [tasks, setTasks] = useState<TaskRow[]>([])
  const [notice, setNotice] = useState<Notice | null>(null)
  useEffect(() => {
    Promise.all([call('/api/projets/'), call('/api/taches/')]).then(([projectData, taskData]) => {
      setProjects(projectData.projects)
      setTasks(taskData.tasks)
    }).catch(() => undefined)
  }, [])
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const data = await call('/api/difficultes/', { method: 'POST', body: JSON.stringify({ project: form.get('project'), task: form.get('task'), description: form.get('description'), priority: form.get('priority') }) })
    setNotice({ text: data.message, ok: true })
    event.currentTarget.reset()
  }
  return (
    <section className="lp">
      <header className="lp-head"><div><h1>Signaler un problème</h1></div></header>
      <Banner notice={notice} />
      <form className="lp-panel" style={{ padding: 18, display: 'grid', gap: 8 }} onSubmit={send}>
        <select name="project"><option value="">Projet</option>{projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        <select name="task"><option value="">Tâche</option>{tasks.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select>
        <textarea name="description" required minLength={5} placeholder="Décrivez le problème" />
        <select name="priority" defaultValue="medium"><option value="low">Faible</option><option value="medium">Moyenne</option><option value="high">Haute</option></select>
        <button className="lp-btn" type="submit">Envoyer le signalement</button>
      </form>
    </section>
  )
}

export function LiveEmployeeHome({ name, onNavigate }: { name: string; onNavigate: (page: string) => void }) {
  const [tasks, setTasks] = useState<TaskRow[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  useEffect(() => {
    Promise.all([call('/api/taches/'), call('/api/projets/')]).then(([taskData, projectData]) => {
      setTasks(taskData.tasks)
      setProjects(projectData.projects)
    }).catch(() => undefined)
  }, [])
  const done = tasks.filter((item) => item.status === 'completed').length
  return (
    <section className="lp">
      <header className="lp-head"><div><h1>Bonjour, {name}</h1><p>Vos projets et tâches viennent de la base.</p></div></header>
      <div className="lp-projects">
        <article><h2>{tasks.length}</h2><p>Tâches</p><small>{done} terminées</small></article>
        <article><h2>{projects.length}</h2><p>Projets</p></article>
        <article><button className="lp-btn" type="button" onClick={() => onNavigate('tasks')}>Voir mes tâches</button></article>
      </div>
    </section>
  )
}
