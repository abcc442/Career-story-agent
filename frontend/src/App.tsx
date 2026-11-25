
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  ArrowDownToLine, ArrowRight, ArrowUpRight, BookOpen, BrainCircuit,
  BriefcaseBusiness, Check, CheckCircle2, ChevronRight, CircleAlert,
  Compass, Copy, FileCheck2, FileText, FolderHeart,
  GitBranch, LayoutDashboard, Lightbulb, LoaderCircle,
  Menu, MessageCircle, Plus, RefreshCw, Send, Mic, MicOff, Volume2,
  ShieldCheck, Sparkles, Target, Trash2, Upload, WandSparkles, X,
} from 'lucide-react';
import { api } from './api';
import type { Experience, ExperiencePayload, Interview, JD, Mode, Page, Story, ResumeV3Preview } from './types';
import { emptyExperience } from './types';

const NAV: { id: Page; label: string; icon: typeof LayoutDashboard; num?: string }[] = [
  { id: 'home', label: '工作台', icon: LayoutDashboard },
  { id: 'experiences', label: '认识你', icon: FolderHeart, num: '01' },
  { id: 'jd', label: '理解岗位', icon: Target, num: '02' },
  { id: 'interview', label: '面试准备', icon: MessageCircle, num: '03' },
];
const PAGE_DESCRIPTION: Record<Page, { title: string; sub: string }> = {
  home: { title: '每段经历，都值得被看见。', sub: '整理真实经历，理解目标岗位，找到最有说服力的职业主线。' },
  experiences: { title: '让 Agent 真正认识你', sub: '不只是简历上的几行字，而是你实际做过什么、证明了什么。' },
  jd: { title: '找到岗位真正看重的能力', sub: '拆解 JD、辨别重点，再去寻找可靠的个人经历证据。' },
  interview: { title: '面试准备：从能力主线到真实追问', sub: '选择目标岗位，查看职业主线与自我介绍，并基于已确认经历开始模拟面试。' },
};

function StatusPill({ mode, status }: { mode: Mode; status: 'loading' | 'ready' | 'error' }) {
  const label = status === 'loading' ? '正在连接 AI 服务…'
    : status === 'error' ? '连接失败'
    : mode === 'ai' ? '真实 AI 模式' : '规则演示模式';
  return <span className={'mode-pill ' + (status === 'ready' && mode === 'ai' ? 'is-ai' : '')}>
    {status === 'loading' ? <LoaderCircle size={14} className="spin" /> : <span className="live-dot" />}
    {label}
  </span>;
}
function SectionHeading({ eyebrow, title, desc, right }: { eyebrow?: string; title: string; desc?: string; right?: ReactNode }) {
  return <div className="section-heading"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2>{desc && <p>{desc}</p>}</div>{right}</div>;
}
function Button({ children, onClick, disabled, variant = 'primary', className = '', type = 'button' }: {
  children: ReactNode; onClick?: () => void; disabled?: boolean; variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; className?: string; type?: 'button' | 'submit'
}) {
  return <button type={type} className={`btn btn-${variant} ${className}`} onClick={onClick} disabled={disabled}>{children}</button>;
}
function EmptyState({ icon: Icon, title, text, action }: { icon: typeof Sparkles; title: string; text: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon"><Icon size={26} strokeWidth={1.8} /></div><h3>{title}</h3><p>{text}</p>{action}</div>;
}
function downloadBlob(name: string, blob: Blob) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}
function downloadFile(name: string, contents: string, type = 'text/plain;charset=utf-8') {
  const blob = new Blob([contents], { type });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

export default function App() {
  const [page, setPage] = useState<Page>('home');
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [jds, setJds] = useState<JD[]>([]);
  const [stories, setStories] = useState<Story[]>([]);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [mode, setMode] = useState<Mode>('demo');
  const [modeStatus, setModeStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [selectedJD, setSelectedJD] = useState<number | null>(null);
  const [selectedStory, setSelectedStory] = useState<number | null>(null);
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);

  const reload = useCallback(async () => {
    const [exp, roles, narratives, sessions] = await Promise.all([
      api.experiences(), api.jds(), api.stories(), api.interviews(),
    ]);
    setExperiences(exp); setJds(roles); setStories(narratives); setInterviews(sessions);
    setSelectedJD(prev => prev && roles.some(j => j.id === prev) ? prev : roles[0]?.id ?? null);
    setSelectedStory(prev => prev && narratives.some(s => s.id === prev) ? prev : narratives[0]?.id ?? null);
  }, []);
  // AI mode is checked separately from workspace data.
  useEffect(() => {
    let active = true;

    api.meta()
      .then(info => {
        if (!active) return;
        setMode(info.mode);
        setModeStatus('ready');
      })
      .catch((err: Error) => {
        if (!active) return;
        setModeStatus('error');
        setError(err.message);
      });

    return () => { active = false; };
  }, []);

  // Load experiences, JDs, stories and interviews independently.
  useEffect(() => {
    reload().catch((err: Error) => setError(err.message));
  }, [reload]);
  useEffect(() => { if (notice) { const t = window.setTimeout(() => setNotice(''), 5000); return () => clearTimeout(t); } }, [notice]);

  async function perform<T>(label: string, action: () => Promise<T>): Promise<T | undefined> {
    setBusy(label); setError('');
    try { return await action(); }
    catch (err) { setError(err instanceof Error ? err.message : '操作失败，请重试。'); return undefined; }
    finally { setBusy(''); }
  }
  function navigate(next: Page) { setPage(next); setMenuOpen(false); setError(''); window.scrollTo({top: 0, behavior: 'smooth'}); }
  async function seed() {
    const res = await perform('加载示例数据', async () => { const result = await api.seed(); await reload(); return result; });
    if (res) { setSelectedJD(res.jd_id); setNotice('示例已载入。这些内容仅用于体验，不是你的真实经历。'); navigate('experiences'); }
  }
  async function exportData() {
    const data = await perform('导出数据', api.export);
    if (data) { downloadFile('career-story-data.json', JSON.stringify(data, null, 2), 'application/json;charset=utf-8'); setNotice('数据已导出为 JSON。'); }
  }
  async function wipe() {
    if (!window.confirm('确定清空所有经历、JD、故事与面试记录吗？此操作不可撤销，请先导出备份。')) return;
    const success = await perform('清空数据', api.clear);
    if (success) { await reload(); setNotice('本地数据已清空。'); navigate('home'); }
  }
  const activeStory = stories.find(s => s.id === selectedStory && s.jd_id === selectedJD) ?? stories.find(s => s.jd_id === selectedJD);
  const activeInterview = interviews.find(i => i.story_id === activeStory?.id);
  const confirmed = experiences.filter(e => e.status === 'confirmed');

  async function generateStory(jdId: number) {
    const story = await perform('构建职业故事', async () => { const s = await api.generate(jdId); await reload(); return s; });
    if (story) { setSelectedJD(jdId); setSelectedStory(story.id); setNotice('已生成职业主线和自我介绍，请核对事实后开始面试。'); navigate('interview'); }
  }
  async function quickStartInterview(jdId: number) {
    const ready = await perform('根据已确认经历准备面试', async () => {
      const item = await api.quickStartInterview(jdId);
      await reload();
      return item;
    });
    if (ready) {
      setSelectedJD(jdId);
      setSelectedStory(ready.story_id);
      setNotice('已基于已确认经历创建面试练习，职业主线为规则草稿，可稍后生成 AI 深度版。');
      navigate('interview');
    }
  }
  async function startInterview(storyId: number) {
    const interview = await perform('开始面试', async () => { const i = await api.startInterview(storyId); await reload(); return i; });
    if (interview) navigate('interview');
  }

  return <div className="app-shell">
    <aside className={'sidebar ' + (menuOpen ? 'sidebar-open' : '')}>
      <div className="brand" onClick={() => navigate('home')} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && navigate('home')}>
        <div className="brand-mark"><GitBranch size={22} /></div>
        <div><div className="brand-title">career<span>story</span><span className="brand-dot">.</span></div><div className="brand-caption">AI CAREER COMPANION</div></div>
      </div>
      <div className="sidebar-label">WORKSPACE</div>
      <nav className="nav-list">{NAV.map(item => <button className={'nav-item ' + (page === item.id ? 'active' : '')} key={item.id} onClick={() => navigate(item.id)}><item.icon size={18} strokeWidth={1.8} /><span>{item.label}</span>{item.num && <span className="nav-num">{item.num}</span>}</button>)}</nav>
      <div className="sidebar-bottom">
        <div className="sidebar-help"><div className="help-spark"><Sparkles size={17} /></div><b>从碎片到主线</b><p>让每一段真实经历，在合适的岗位上发挥作用。</p><span>Built for your next step <ArrowUpRight size={13}/></span></div>
        <div className="sidebar-foot">CAREER STORY AGENT <span>· MVP 0.1</span></div>
      </div>
    </aside>
    {menuOpen && <button aria-label="关闭导航" className="mobile-overlay" onClick={() => setMenuOpen(false)} />}
    <div className="main-area">
      <header className="topbar">
        <div className="topbar-left"><button className="mobile-menu" onClick={() => setMenuOpen(true)} aria-label="打开菜单"><Menu size={21} /></button><span className="breadcrumb">我的工作台</span><ChevronRight size={15} className="muted-icon"/><span className="crumb-current">{NAV.find(n => n.id === page)?.label}</span></div>
        <div className="topbar-right"><StatusPill mode={mode} status={modeStatus} /><div className="avatar">CS</div></div>
      </header>
      <main className="page-wrap">
        {error && <div role="alert" className="alert error"><CircleAlert size={18}/><span>{error}</span><button aria-label="关闭错误" onClick={() => setError('')}><X size={17}/></button></div>}
        {notice && <div role="status" className="alert success"><CheckCircle2 size={18}/><span>{notice}</span><button aria-label="关闭提示" onClick={() => setNotice('')}><X size={17}/></button></div>}
        {busy && <div className="working-indicator"><LoaderCircle size={15} className="spin"/> {busy}…</div>}
        <div className="page-heading"><div className="page-kicker"><span className="kicker-line"/>YOUR CAREER, BETTER TOLD</div><h1>{PAGE_DESCRIPTION[page].title}</h1><p>{PAGE_DESCRIPTION[page].sub}</p></div>
        {modeStatus === 'ready' && mode === 'demo' && <div className="demo-notice"><Lightbulb size={17}/><span>当前为<strong>规则演示模式</strong>：不具备大模型语义理解与面试评价能力。配置 API Key 后，系统将使用真正的 AI Agent。</span></div>}
        {page === 'home' && <HomePage navigate={navigate} experiences={experiences} confirmed={confirmed} jds={jds} stories={stories} seed={seed} exportData={exportData} wipe={wipe} busy={!!busy} />}
        {page === 'experiences' && <ExperiencesPage experiences={experiences} reload={reload} perform={perform} busy={!!busy} setNotice={setNotice} />}
        {page === 'jd' && <JDPage jds={jds} selectedJD={selectedJD} setSelectedJD={setSelectedJD} confirmedCount={confirmed.length} reload={reload} perform={perform} generateStory={generateStory} busy={!!busy} setNotice={setNotice} />}
        {page === 'interview' && <InterviewPage story={activeStory} interview={activeInterview} jds={jds} experiences={confirmed} selectedJD={selectedJD} setSelectedJD={setSelectedJD} generateStory={generateStory} quickStartInterview={quickStartInterview} startInterview={startInterview} perform={perform} reload={reload} busy={!!busy} navigate={navigate} mode={mode} />}
      </main>
    </div>
  </div>;
}

function HomePage({ navigate, experiences, confirmed, jds, stories, seed, exportData, wipe, busy }: {
  navigate: (page: Page) => void; experiences: Experience[]; confirmed: Experience[]; jds: JD[]; stories: Story[];
  seed: () => void; exportData: () => void; wipe: () => void; busy: boolean;
}) {
  const steps = [
    { n: '01', icon: FolderHeart, title: '让 AI 认识你', desc: '梳理每一段真实经历，发现隐藏在项目背后的个人能力。', cta: '整理我的经历', page: 'experiences' as Page, done: confirmed.length > 0 },
    { n: '02', icon: Target, title: '理解目标岗位', desc: '将 JD 拆解为具体能力要求，找到可信的经历证据。', cta: '分析目标 JD', page: 'jd' as Page, done: jds.length > 0 },
    { n: '03', icon: MessageCircle, title: '面试准备', desc: '职业主线、自我介绍、模拟面试在同一个页面完成。', cta: '进入面试准备', page: 'interview' as Page, done: stories.length > 0 },
  ];
  return <>
    <section className="hero"><div className="hero-glow hero-glow-a"/><div className="hero-glow hero-glow-b"/>
      <div className="hero-content"><div className="hero-tag"><Sparkles size={14}/> YOUR STORY MATTERS</div><h2>不止优化简历，<br/><span>更懂你为什么适合。</span></h2><p>从零散的实习与项目中找到属于你的能力主线。让岗位理解、经历匹配、简历表达和面试准备，围绕同一套真实证据展开。</p><Button onClick={() => navigate(experiences.length ? 'jd' : 'experiences')}>开始我的求职故事 <ArrowRight size={17}/></Button><div className="hero-foot"><ShieldCheck size={15}/> 基于真实经历 · 证据可追溯 · 用户确认后保存</div></div>
      <div className="hero-visual"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="visual-card vc-top"><div className="vc-icon purple"><BrainCircuit size={19}/></div><div><small>发现你的能力</small><strong>用户洞察 · AI 应用</strong></div><CheckCircle2 size={16} className="vc-check"/></div><div className="visual-card vc-center"><div className="story-symbol"><GitBranch size={32}/></div><strong>你的职业故事</strong><small>EXPERIENCE → IMPACT</small></div><div className="visual-card vc-bottom"><div className="vc-icon blue"><Target size={18}/></div><div><small>与岗位建立连接</small><strong>能力 × 事实证据</strong></div><ArrowUpRight size={17}/></div></div>
    </section>
    <div className="stats-grid"><div className="stat-card"><span>已整理经历</span><b>{experiences.length.toString().padStart(2, '0')}</b><small>{confirmed.length} 条已确认</small></div><div className="stat-card"><span>目标岗位</span><b>{jds.length.toString().padStart(2, '0')}</b><small>已解析岗位 JD</small></div><div className="stat-card"><span>职业故事版本</span><b>{stories.length.toString().padStart(2, '0')}</b><small>跨岗位可复用</small></div></div>
    <section className="workflow-section"><SectionHeading eyebrow="HOW IT WORKS" title="只需要三个步骤" desc="流程简单，复杂的理解与匹配交给 Agent。"/><div className="step-grid">{steps.map(step => <button key={step.n} className="step-card" onClick={() => navigate(step.page)}><div className="step-card-head"><span className="step-number">{step.n}</span>{step.done ? <span className="done-chip"><Check size={13}/> 已完成</span> : <ArrowUpRight size={18} className="step-arrow"/>}</div><div className="step-icon"><step.icon size={23} strokeWidth={1.8}/></div><h3>{step.title}</h3><p>{step.desc}</p><span className="step-link">{step.cta} <ArrowRight size={16}/></span></button>)}</div></section>
    <section className="bottom-utility"><div><h3>想快速体验完整流程？</h3><p>载入 3 条明确标记的虚构示例经历和 1 条岗位 JD，立即走通产品。</p></div><div className="utility-buttons"><Button variant="secondary" onClick={seed} disabled={busy || experiences.length > 0 || jds.length > 0}><WandSparkles size={16}/> 加载示例</Button><Button variant="ghost" onClick={exportData}><ArrowDownToLine size={16}/> 导出数据</Button><Button variant="ghost" className="text-danger" onClick={wipe}><Trash2 size={16}/> 清空数据</Button></div></section>
  </>;
}

function ExperiencesPage({ experiences, reload, perform, busy, setNotice }: {
  experiences: Experience[]; reload: () => Promise<void>; perform: <T,>(label: string, action: () => Promise<T>) => Promise<T | undefined>;
  busy: boolean; setNotice: (s: string) => void;
}) {
  const [text, setText] = useState('');
  const [drafts, setDrafts] = useState<ExperiencePayload[]>([]);
  const [extractNote, setExtractNote] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<ExperiencePayload | null>(null);
  const [followup, setFollowup] = useState<{question: string; reason: string} | null>(null);
  const [answer, setAnswer] = useState('');
  const [proposal, setProposal] = useState<{field: keyof ExperiencePayload; proposed_value: string; reason: string} | null>(null);
  const [typeFilter, setTypeFilter] = useState('all');

  async function readFile(file?: File) {
    if (!file) return;
    const result = await perform('解析文件', () => api.readResume(file));
    if (result) { setText(result.text); setNotice('文件文字已读取。请点击“识别经历草稿”。' + (result.truncated ? ' 内容已截断至25000字。' : '')); }
  }
  async function extract() {
    const result = await perform('识别经历', () => api.extract(text));
    if (result) { setDrafts(result.experiences.map(e => ({...emptyExperience(), ...e, status: 'draft'}))); setExtractNote(result.note); }
  }
  async function saveDraft(d: ExperiencePayload, idx: number) {
    const result = await perform('保存草稿', async () => { const row = await api.createExperience(d); await reload(); return row; });
    if (result) { setDrafts(old => old.filter((_, i) => i !== idx)); setNotice('草稿已保存。请补充事实并确认后用于岗位匹配。'); }
  }
  function edit(exp?: Experience) {
    setEditingId(exp?.id ?? null);
    setForm(exp ? {
      title: exp.title, organization: exp.organization, experience_type: exp.experience_type ?? 'other', parent_experience_id: exp.parent_experience_id ?? null, period: exp.period, background: exp.background, task: exp.task,
      actions: exp.actions, methods: exp.methods, results: exp.results, evidence: exp.evidence, skills: [...exp.skills], status: exp.status,
    } : emptyExperience());
    setFollowup(null); setAnswer(''); setProposal(null);
  }
  async function saveForm() {
    if (!form?.title.trim()) { setNotice('请先填写经历名称。'); return; }
    const result = await perform('保存经历', async () => { const row = editingId ? await api.saveExperience(editingId, form) : await api.createExperience(form); await reload(); return row; });
    if (result) { setNotice(form.status === 'confirmed' ? '经历已确认，可用于岗位分析。' : '经历草稿已保存。'); setForm(null); }
  }
  async function remove(id: number) {
    if (!window.confirm('确定删除这段经历？这不会自动删除此前生成的故事版本。')) return;
    const res = await perform('删除经历', async () => { await api.deleteExperience(id); await reload(); return true; });
    if (res) { setForm(null); setNotice('经历已删除。'); }
  }
  async function ask() {
    if (!editingId) return;
    const q = await perform('分析经历缺口', () => api.question(editingId));
    if (q) { setFollowup(q); setProposal(null); }
  }
  async function submitAnswer() {
    if (!editingId || !answer.trim()) return;
    const p = await perform('整理补充信息', () => api.propose(editingId, answer));
    if (p) setProposal(p);
  }
  function acceptProposal() {
    if (!proposal || !form) return;
    setForm({...form, [proposal.field]: proposal.proposed_value, status: 'draft'});
    setProposal(null); setAnswer(''); setFollowup(null);
    setNotice('建议已填入编辑表单（尚未保存）。检查无误后请点“保存经历”，再确认事实。');
  }
  const fields: {key: keyof ExperiencePayload; label: string; placeholder: string; tall?: boolean}[] = [
    {key: 'background', label: '项目背景', placeholder: '为什么会有这个项目？业务或用户遇到什么问题？'},
    {key: 'task', label: '目标与任务', placeholder: '当时需要解决的核心任务是什么？'},
    {key: 'actions', label: '我的具体行动', placeholder: '你亲自做了哪些事情？请区分个人与团队贡献。', tall: true},
    {key: 'methods', label: '方法与技术', placeholder: '使用了哪些方法、工具或技术？'},
    {key: 'results', label: '真实结果', placeholder: '交付了什么？有可验证的数据吗？没有可留空。'},
    {key: 'evidence', label: '证据或补充说明', placeholder: '作品链接、文档名称或需要注意的事实边界。'},
  ];
  return <div className="content-grid"><div className="content-main">
    <section className="panel import-panel"><SectionHeading eyebrow="IMPORT YOUR EXPERIENCE" title="从现有材料开始" desc="上传简历或粘贴项目文字，先识别，再人工确认。"/><label className="upload-zone"><Upload size={22}/><strong>上传简历文件</strong><span>支持 PDF / DOCX / TXT / MD · 最大 5MB</span><input type="file" accept=".pdf,.docx,.txt,.md" onChange={e => { void readFile(e.target.files?.[0]); e.target.value=''; }} /></label><div className="or-divider"><span>或者直接粘贴文字</span></div><textarea className="big-textarea" value={text} onChange={e => setText(e.target.value)} placeholder={'例如：\n供应商风险系统｜产品实习\n参与业务需求分析，设计RAG检索方案…\n\nAI数字宠物项目\n负责用户旅程与产品原型…'} /><div className="import-actions"><span>提取结果只会生成草稿，不会自动写入正式经历。</span><Button onClick={extract} disabled={busy || text.trim().length < 10}><Sparkles size={16}/> 识别经历草稿</Button></div></section>
    {drafts.length > 0 && <section className="panel extracted-panel"><SectionHeading eyebrow="REVIEW FIRST" title={`识别到 ${drafts.length} 段经历草稿`} desc={extractNote || '请核对信息；保存后仍需在编辑页确认事实。'} />{drafts.map((d, idx) => <div className="draft-row" key={idx}><div><b>{d.title}</b><p>{d.organization || d.evidence.slice(0, 95) || '待补充细节'}</p></div><Button variant="secondary" onClick={() => saveDraft(d, idx)} disabled={busy}><Plus size={15}/> 保存草稿</Button></div>)}</section>}
    <section className="panel experience-list"><SectionHeading eyebrow="EXPERIENCE LIBRARY" title={`我的经历库 · ${experiences.length}`} desc="只有“已确认”的经历会参与 JD 匹配和职业故事生成。" right={<Button variant="secondary" onClick={() => edit()}><Plus size={16}/> 手动添加</Button>} />
      <div className="experience-filters">{[['all','全部'],['internship','实习'],['work','工作'],['project','项目'],['research','科研'],['competition','竞赛'],['campus','校园'],['other','待分类/其他']].map(([key,label]) => <button key={key} className={typeFilter===key?'active':''} onClick={() => setTypeFilter(key)}>{label}</button>)}</div>
      {experiences.length === 0 ? <EmptyState icon={BookOpen} title="经历库还是空的" text="先导入简历，或从一段实习/项目开始记录。" /> : experiences.filter(exp => typeFilter === 'all' || (exp.experience_type || 'other') === typeFilter).map(exp => <div className="experience-row" key={exp.id} onClick={() => edit(exp)} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && edit(exp)}><div className="record-icon"><BriefcaseBusiness size={19}/></div><div className="record-content"><div className="record-title"><strong>{exp.title}</strong><span className={'tag ' + (exp.status === 'confirmed' ? 'tag-green' : 'tag-amber')}>{exp.status === 'confirmed' ? '已确认' : '待确认'}</span>{exp.source === 'demo' && <span className="tag tag-lilac">示例</span>}</div><p><span className="tag tag-lilac">{{internship:'实习',work:'工作',project:'项目',research:'科研',competition:'竞赛',campus:'校园',other:'待分类/其他'}[exp.experience_type] || '待分类/其他'}</span> {exp.organization || '未填写组织'}{exp.period && ` · ${exp.period}`}</p><div className="record-tags">{exp.skills.slice(0, 4).map(s => <span key={s}>{s}</span>)}</div></div><ChevronRight size={19} className="record-chevron"/></div>)}
    </section>
  </div><aside className="right-rail"><div className="tip-card"><div className="tip-icon"><Lightbulb size={19}/></div><h3>不止记录“做了什么”</h3><p>一段有价值的经历，需要能回答：当时是什么问题、你负责什么、为什么这么做、最终得到了什么。</p><div className="tip-points"><span><CheckCircle2 size={15}/> 背景与挑战</span><span><CheckCircle2 size={15}/> 个人行动</span><span><CheckCircle2 size={15}/> 真实结果</span><span><CheckCircle2 size={15}/> 可验证证据</span></div></div><div className="rail-stat"><span>已确认经历</span><b>{experiences.filter(e => e.status === 'confirmed').length}<small> / {experiences.length}</small></b><div className="progress-track"><div style={{width: experiences.length ? `${(experiences.filter(e => e.status === 'confirmed').length / experiences.length) * 100}%` : '0%'}} /></div><p>确认后才能进入岗位匹配</p></div></aside>
    {form && <div className="drawer-backdrop" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) setForm(null); }}><div className="edit-drawer" role="dialog" aria-modal="true" aria-label="编辑个人经历"><div className="drawer-top"><div><div className="eyebrow">EXPERIENCE DETAILS</div><h2>{editingId ? '完善这段经历' : '新增个人经历'}</h2></div><button className="icon-button" onClick={() => setForm(null)} aria-label="关闭"><X size={20}/></button></div><div className="drawer-body"><div className="field-grid"><label className="field"><span>经历名称 *</span><input value={form.title} onChange={e => setForm({...form, title: e.target.value, status: 'draft'})} placeholder="例如：AI产品实习"/></label><label className="field"><span>所属组织</span><input value={form.organization} onChange={e => setForm({...form, organization: e.target.value, status: 'draft'})} placeholder="公司 / 学校 / 个人项目"/></label></div><div className="field-grid"><label className="field"><span>经历类型</span><select value={form.experience_type} onChange={e => setForm({...form, experience_type: e.target.value as ExperiencePayload['experience_type'], status: 'draft'})}><option value="internship">实习经历</option><option value="work">正式工作</option><option value="project">独立项目</option><option value="research">学术科研</option><option value="competition">竞赛经历</option><option value="campus">校园经历</option><option value="other">其他</option></select></label><label className="field"><span>所属实习/工作（选填）</span><select value={form.parent_experience_id ?? ''} onChange={e => setForm({...form, parent_experience_id: e.target.value ? Number(e.target.value) : null, status: 'draft'})}><option value="">不关联</option>{experiences.filter(x => x.id !== editingId && ['internship','work'].includes(x.experience_type)).map(x => <option key={x.id} value={x.id}>{x.title}</option>)}</select></label></div><label className="field"><span>时间</span><input value={form.period} onChange={e => setForm({...form, period: e.target.value, status: 'draft'})} placeholder="2026.06 - 2026.09"/></label>{fields.map(f => <label className="field" key={f.key}><span>{f.label}</span><textarea className={f.tall ? 'tall' : ''} value={String(form[f.key])} onChange={e => setForm({...form, [f.key]: e.target.value, status: 'draft'})} placeholder={f.placeholder}/></label>)}<label className="field"><span>能力标签（使用逗号分隔）</span><input value={form.skills.join(', ')} onChange={e => setForm({...form, skills: e.target.value.split(/[,，]/).map(x => x.trim()).filter(Boolean), status: 'draft'})} placeholder="需求分析, RAG, 原型设计"/></label>
    {editingId && <div className="agent-question-card"><div className="question-head"><div><Sparkles size={17}/> Agent 追问</div><Button variant="ghost" onClick={ask} disabled={busy}><RefreshCw size={15}/> 生成问题</Button></div><p className="question-intro">让 Agent 找出最值得补充的事实，避免空泛润色。</p>{followup && <><blockquote>{followup.question}</blockquote><small>追问原因：{followup.reason}</small><textarea value={answer} onChange={e => setAnswer(e.target.value)} placeholder="用真实细节回答，暂不自动保存。"/><Button variant="secondary" onClick={submitAnswer} disabled={busy || answer.trim().length < 2}>整理成更新建议 <ArrowRight size={15}/></Button></>}{proposal && <div className="proposal"><b>建议更新「{fieldName(proposal.field)}」</b><p>{proposal.proposed_value}</p><small>{proposal.reason}</small><Button onClick={acceptProposal}><Check size={15}/> 填入表单（待保存）</Button></div>}</div>}
    <label className="confirm-row"><input type="checkbox" checked={form.status === 'confirmed'} onChange={e => setForm({...form, status: e.target.checked ? 'confirmed' : 'draft'})}/><div><strong>我已核对以上信息，确认其真实准确</strong><p>只有确认的内容会进入职业故事；修改事实后需要重新确认。</p></div></label></div><div className="drawer-footer">{editingId && <Button variant="ghost" className="text-danger" onClick={() => remove(editingId)}><Trash2 size={16}/> 删除</Button>}<div className="drawer-footer-right"><Button variant="secondary" onClick={() => setForm(null)}>取消</Button><Button onClick={saveForm} disabled={busy || !form.title.trim()}><Check size={16}/> 保存经历</Button></div></div></div></div>}
  </div>;
}
function fieldName(k: keyof ExperiencePayload): string { return ({background: '项目背景', task: '目标与任务', actions: '我的具体行动', methods: '方法与技术', results: '真实结果', evidence: '证据补充'} as Record<string, string>)[k] ?? k; }

function JDPage({ jds, selectedJD, setSelectedJD, confirmedCount, reload, perform, generateStory, busy, setNotice }: {
  jds: JD[]; selectedJD: number | null; setSelectedJD: (id: number) => void; confirmedCount: number;
  reload: () => Promise<void>; perform: <T,>(label: string, action: () => Promise<T>) => Promise<T | undefined>; generateStory: (id: number) => Promise<void>; busy: boolean; setNotice: (message: string) => void;
}) {
  const [title, setTitle] = useState(''); const [company, setCompany] = useState(''); const [text, setText] = useState('');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [useConfirmed, setUseConfirmed] = useState(true);
  const [preview, setPreview] = useState<ResumeV3Preview | null>(null);
  const [chosen, setChosen] = useState<number[]>([]);
  const active = jds.find(j => j.id === selectedJD) ?? jds[0];
  async function previewTailor() {
    if (!active || !resumeFile) return;
    setPreview(null);
    setChosen([]);
    const result = await perform('正在匹配已确认经历并生成修改预览', () => api.previewTailoredResume(resumeFile, active, useConfirmed));
    if (result) {
      setPreview(result);
      setChosen(result.edits.map(e => e.paragraph_id));
      setNotice(`已生成 ${result.edits.length} 条修改建议，请逐条核对事实，再确认下载。`);
    }
  }
  async function applyTailor() {
    if (!active || !resumeFile || !preview) return;
    const selections = preview.edits.filter(e => chosen.includes(e.paragraph_id));
    if (!selections.length) return;
    const result = await perform('正在将勾选的修改应用到原 Word', () => api.applyTailoredResume(resumeFile, active, selections));
    if (result) {
      const safe = active.title.replace(/[\\/:*?"<>|]/g, '_');
      downloadBlob(`${resumeFile.name.replace(/\.docx$/i, '')}_${safe}_V3定制版.docx`, result.blob);
      setNotice(`已应用 ${result.editCount} 条确认修改并下载新 Word，原文件保持不变。`);
    }
  }
  async function analyse() {
    const result = await perform('拆解岗位 JD', async () => { const jd = await api.createJD({title, company, raw_text: text}); await reload(); return jd; });
    if (result) { setSelectedJD(result.id); setTitle(''); setCompany(''); setText(''); }
  }
  return <div className="jd-page-stack">
    <section className="panel jd-resume-entry-panel">
      <div className="jd-resume-entry-copy">
        <span className="eyebrow">CORE FEATURE · AI RESUME TAILORING</span>
        <h2>上传现有简历，让 Agent 按目标岗位直接修改</h2>
        <p>不是重新生成一份陌生模板，而是在你上传的 Word 原文档中定位相关段落进行改写，尽可能保留原有版式、标题、表格和段落样式。</p>
      </div>
      <label className="jd-resume-entry-upload">
        <FileText size={24}/>
        <span><strong>{resumeFile?.name || '选择你的 Word 简历'}</strong><small>{resumeFile ? '文件已选择，可继续填写下方 JD' : '支持 .docx，最大 5MB'}</small></span>
        <input type="file" accept=".docx" onChange={e => { setResumeFile(e.target.files?.[0] ?? null); setPreview(null); setChosen([]); }}/>
        <Upload size={18}/>
      </label>
      <div className="jd-resume-entry-foot"><ShieldCheck size={16}/> 原始文件不会被覆盖；只修改 AI 能够准确定位的原有段落。</div>
    </section>
    <div className="jd-primary-column">
      <section className="panel">
        <SectionHeading eyebrow="TARGET ROLE" title="告诉 Agent，你想去哪里" desc="直接粘贴招聘 JD，Agent 会区分核心能力与加分要求。"/>
        <div className="field-grid">
          <label className="field"><span>目标岗位 *</span><input placeholder="如：AI 产品经理实习生" value={title} onChange={e => setTitle(e.target.value)}/></label>
          <label className="field"><span>公司（选填）</span><input placeholder="公司名称" value={company} onChange={e => setCompany(e.target.value)}/></label>
        </div>
        <label className="field"><span>岗位 JD *</span><textarea className="jd-textarea" value={text} onChange={e => setText(e.target.value)} placeholder={'粘贴招聘岗位要求，例如：\\n\\n岗位职责：\\n1. 参与AI产品需求调研、用户访谈；\\n2. 输出PRD及高保真原型；\\n3. 结合大模型能力设计业务应用方案；\\n\\n任职要求：\\n熟悉数据分析，具备跨团队沟通能力。'}/></label>
        <div className="form-actions"><span>{text.length} / 12000 字</span><Button onClick={analyse} disabled={busy || title.trim().length < 1 || text.trim().length < 10 || text.length > 12000}><WandSparkles size={16}/> 分析岗位要求</Button></div>
      </section>
      <section className="panel">
        <SectionHeading eyebrow="ANALYZED POSITIONS" title={`已分析岗位 · ${jds.length}`} desc="选择一个岗位，查看能力画像并生成对应的职业故事。"/>
        {jds.length === 0 ? <EmptyState icon={Target} title="尚未添加目标岗位" text="将感兴趣的岗位描述粘贴到上方，就能开始分析。"/> : <div className="jd-list">{jds.map(j => <button className={'jd-row ' + (active?.id === j.id ? 'selected' : '')} key={j.id} onClick={() => { setSelectedJD(j.id); setPreview(null); setChosen([]); }}><div className="jd-company-icon"><BriefcaseBusiness size={19}/></div><div><strong>{j.title}</strong><span>{j.company || '未填写公司'} · {j.requirements.length} 项能力要求</span></div>{active?.id === j.id ? <CheckCircle2 size={19} className="selected-check"/> : <ChevronRight size={19}/>}</button>)}</div>}
      </section>
    </div>

    {active ? <>
      <section className="panel jd-analysis-panel">
        <SectionHeading eyebrow="ROLE PROFILE & EXPERIENCE MATCH" title="岗位能力画像与经历匹配" desc="先看懂岗位真正看重什么，再检查你的哪些经历能够提供证据。"/>
        <div className="jd-role-summary"><div><span className="rail-label">当前分析岗位</span><h3>{active.title}</h3><p>{active.company || '目标岗位'} · {active.requirements.length} 项能力要求</p></div><span className="jd-active-badge"><CheckCircle2 size={15}/> 当前选中</span></div>
        <div className="jd-requirements-grid">{active.requirements.map((r, i) => <div className="jd-requirement-card" key={i}><div className="jd-requirement-title"><span className="req-dot"/><strong>{r.label}</strong></div><span className="jd-priority">{r.priority}</span><p>{r.meaning}</p></div>)}</div>
        <div className="jd-match-action"><div><strong>下一步：把岗位要求与你的真实经历对应起来</strong><p>Agent 会检索已确认的经历，生成有依据的匹配分析与职业故事。</p></div><Button onClick={() => generateStory(active.id)} disabled={busy || confirmedCount === 0}><GitBranch size={17}/> 生成职业主线并进入面试准备</Button></div>
        {confirmedCount === 0 && <p className="helper-warning">请先到「认识你」确认至少一条个人经历，再进行匹配。</p>}
      </section>

      <section className="panel jd-resume-panel">
        <SectionHeading eyebrow="RESUME EDITOR · TEMPLATE-PRESERVING" title="在原 Word 简历模板中定点修改" desc="结合当前 JD，只改写最相关的原有段落；不新建简历、不重排整份文档，尽可能保留原模板。"/>
        <div className="jd-resume-workspace jd-resume-workspace-final">
          <div className="jd-resume-file-state"><FileCheck2 size={25}/><div><strong>{resumeFile?.name || '还没有上传 Word 简历'}</strong><span>{resumeFile ? '已就绪 · 将在这份原文档上进行定点修改' : '请先在本页顶部上传 .docx 简历'}</span></div></div>
          <div className="jd-resume-instructions">
            <strong>V3 · 证据驱动的简历定制</strong>
            <p>先根据已确认经历与 JD 生成修改建议，逐条查看原文、改写理由、引用经历和岗位要求。确认后才会生成新 Word。</p>
            <label className="v3-toggle"><input type="checkbox" checked={useConfirmed} onChange={e => { setUseConfirmed(e.target.checked); setPreview(null); setChosen([]); }}/>
              使用经历库中的已确认经历（当前 {confirmedCount} 条）</label>
            <p className="v3-subtle">仅使用已确认且非演示数据；缺少证据的能力只会提出补充问题。</p>
            <Button onClick={previewTailor} disabled={busy || !resumeFile}><WandSparkles size={16}/> 第一步：生成修改预览</Button>
            <p className="helper-warning">不会覆盖原文件；复杂文本框、图片和部分特殊对象可能无法安全编辑。AI 校验并不能替代你对真实性的最终审核。</p>
          </div>
          {preview && <div className="v3-preview">
            <div className="v3-preview-head"><strong>修改预览 · {preview.edits.length} 条建议</strong><span>引用已确认经历 {preview.confirmed_count} 条</span></div>
            {preview.match && <div className="v3-match">
              <strong>JD 能力匹配</strong>
              {preview.match.items.map((item, index) => <div key={index} className="v3-match-row"><span>{item.requirement}</span><span>{item.level === 'strong' ? '较强证据' : item.level === 'partial' ? '部分证据' : '缺少证据'}</span></div>)}
            </div>}
            {preview.edits.length === 0 && <p>没有产生可安全应用的修改，建议先补充下方证据问题。</p>}
            {preview.edits.map(edit => <div className="v3-edit" key={edit.paragraph_id}>
              <label className="v3-edit-heading"><input type="checkbox" checked={chosen.includes(edit.paragraph_id)} onChange={e => setChosen(old => e.target.checked ? [...old, edit.paragraph_id] : old.filter(id => id !== edit.paragraph_id))}/>
                <strong>应用段落 #{edit.paragraph_id} 的修改</strong></label>
              <div className="v3-text-pair"><div><span>原文</span><p>{edit.original_text}</p></div><div><span>建议改写</span><p>{edit.revised_text}</p></div></div>
              <p className="v3-edit-reason"><strong>改写理由：</strong>{edit.reason || '请核对是否有实质改善'}</p>
              {!!edit.matched_requirements.length && <p className="v3-evidence"><strong>JD 对应：</strong>{edit.matched_requirements.join('、')}</p>}
              <p className="v3-evidence"><strong>引用事实：</strong>{edit.source_experiences.length ? edit.source_experiences.map(exp => `${exp.title}（#${exp.id}）`).join('、') : '仅来自原 Word 现有文字'}</p>
            </div>)}
            {!!preview.review_notes.length && <div className="v3-notes"><strong>建议补充或核实</strong><ul>{preview.review_notes.map((note, index) => <li key={index}>{note}</li>)}</ul></div>}
            <p className="v3-subtle">请确认每条新增事实与所引用经历确实属于同一项目，并由你本人核实。</p>
            <Button onClick={applyTailor} disabled={busy || chosen.length === 0}><ArrowDownToLine size={16}/> 第二步：应用已勾选的 {chosen.length} 条修改并下载 Word</Button>
          </div>}

        </div>
      </section>
    </> : <section className="panel jd-empty-followup"><EmptyState icon={Compass} title="分析完成后，这里会展示岗位能力画像和简历优化工具" text="先在上方粘贴 JD 并点击「分析岗位要求」，后续分析结果和 Word 简历功能都会显示在页面下方。"/></section>}
  </div>;
}

type BrowserSpeechRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type BrowserSpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

function InterviewPage({ story, interview, jds, experiences, selectedJD, setSelectedJD, generateStory, quickStartInterview, startInterview, perform, reload, busy, navigate, mode }: {
  story?: Story; interview?: Interview; jds: JD[]; experiences: Experience[]; selectedJD: number | null;
  setSelectedJD: (id: number) => void; generateStory: (id: number) => Promise<void>;
  quickStartInterview: (id: number) => Promise<void>; startInterview: (id: number) => Promise<void>;
  perform: <T,>(label: string, action: () => Promise<T>) => Promise<T | undefined>;
  reload: () => Promise<void>; busy: boolean; navigate: (p: Page) => void; mode: Mode;
}) {
  const [answer, setAnswer] = useState('');
  const [listening, setListening] = useState(false);
  const [speechStatus, setSpeechStatus] = useState('语音会先转成文字，你可以修改后再发送。');
  const [introDuration, setIntroDuration] = useState('1');
  const [customIntroDuration, setCustomIntroDuration] = useState('2');
  const [introStatus, setIntroStatus] = useState('');
  const [introCopied, setIntroCopied] = useState(false);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  useEffect(() => {
    const savedMinutes = story?.data?.introduction_minutes;
    if (savedMinutes && [1, 2, 3, 5].includes(savedMinutes)) {
      setIntroDuration(String(savedMinutes));
    } else if (savedMinutes) {
      setIntroDuration('custom');
      setCustomIntroDuration(String(savedMinutes));
    } else {
      setIntroDuration('1');
    }
    setIntroStatus('');
  }, [story?.id, story?.data?.introduction_minutes]);
  const currentJD = jds.find(j => j.id === selectedJD) ?? jds[0];
  const byId = new Map(experiences.map(e => [e.id, e]));

  function startVoiceInput() {
    const speechWindow = window as Window & {
      SpeechRecognition?: BrowserSpeechRecognitionConstructor;
      webkitSpeechRecognition?: BrowserSpeechRecognitionConstructor;
    };
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setSpeechStatus('当前浏览器暂不支持语音识别。请使用最新版 Chrome 或 Edge，或继续输入文字。');
      return;
    }
    try {
      const recognition = new Recognition();
      recognition.lang = 'zh-CN';
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.onresult = (event: any) => {
        let finalText = '';
        let interimText = '';
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const transcript = event.results[i][0]?.transcript || '';
          if (event.results[i].isFinal) finalText += transcript;
          else interimText += transcript;
        }
        if (finalText.trim()) setAnswer(previous => `${previous}${previous.trim() ? ' ' : ''}${finalText.trim()}`);
        setSpeechStatus(interimText.trim() ? `正在识别：${interimText.trim()}` : '正在聆听，可继续回答；结束后可以修改转写内容。');
      };
      recognition.onerror = (event: any) => {
        const reason = event?.error === 'not-allowed' ? '麦克风权限未开启，请在浏览器地址栏允许麦克风。' : `语音识别暂不可用（${event?.error || '未知错误'}），可以改用文字回答。`;
        setSpeechStatus(reason);
        setListening(false);
      };
      recognition.onend = () => {
        setListening(false);
        setSpeechStatus('语音识别已结束。请检查转写内容，确认无误后发送。');
      };
      recognitionRef.current = recognition;
      recognition.start();
      setListening(true);
      setSpeechStatus('正在请求麦克风并聆听……');
    } catch {
      setListening(false);
      setSpeechStatus('无法启动麦克风。请检查浏览器权限，或改用文字回答。');
    }
  }

  function stopVoiceInput() {
    recognitionRef.current?.stop();
    setListening(false);
  }

  function speakCurrentQuestion() {
    const latestQuestion = [...(interview?.messages ?? [])].reverse().find(message => message.role === 'assistant')?.content;
    if (!latestQuestion || !('speechSynthesis' in window)) {
      setSpeechStatus('当前浏览器不支持题目朗读，请直接阅读屏幕问题。');
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(latestQuestion);
    utterance.lang = 'zh-CN';
    utterance.rate = 1;
    window.speechSynthesis.speak(utterance);
  }

  useEffect(() => () => {
    recognitionRef.current?.stop();
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  }, []);

  async function reply() {
    if (!interview || answer.trim().length < 2) return;
    const result = await perform('分析回答并追问', async () => {
      const updated = await api.replyInterview(interview.id, answer.trim());
      await reload();
      return updated;
    });
    if (result) setAnswer('');
  }

  const selectedIntroMinutes = introDuration === 'custom' ? Number(customIntroDuration) : Number(introDuration);
  const validIntroDuration = Number.isFinite(selectedIntroMinutes) && selectedIntroMinutes >= 1 && selectedIntroMinutes <= 10;
  const targetIntroChars = validIntroDuration ? Math.round(selectedIntroMinutes * 230) : 0;
  const currentIntro = story?.data?.introduction || '';
  const currentIntroChars = currentIntro.replace(/[\s，。！？；：、,.!?;:（）()【】《》“”‘’…—\-·]+/g, '').length;
  const estimatedIntroMinutes = currentIntroChars / 230;

  async function generateIntroduction() {
    if (!story || !validIntroDuration) return;
    const updated = await perform(`生成${selectedIntroMinutes}分钟自我介绍`, async () => {
      const result = await api.generateIntroduction(story.id, selectedIntroMinutes);
      await reload();
      return result;
    });
    if (updated) setIntroStatus(`已生成约${selectedIntroMinutes}分钟版本，请核对事实并练习计时。`);
  }

  async function copyIntroduction() {
    if (!currentIntro) return;
    try {
      await navigator.clipboard.writeText(currentIntro);
      setIntroCopied(true);
      window.setTimeout(() => setIntroCopied(false), 1800);
    } catch {
      setIntroStatus('复制失败，请手动选择自我介绍文本复制。');
    }
  }

  return <div className="prep-layout">
    <section className="panel prep-overview">
      <SectionHeading eyebrow="INTERVIEW PREPARATION" title="你的岗位与准备材料" desc="不需要先到另一个页面生成职业故事。选择岗位后，可以生成深度职业主线，也可以直接开始练习。" />
      <div className="prep-top-row">
        <label className="field"><span>当前目标岗位</span>
          <select value={currentJD?.id ?? ''} onChange={e => setSelectedJD(Number(e.target.value))} disabled={!jds.length}>
            {jds.map(j => <option key={j.id} value={j.id}>{j.title}{j.company ? ` · ${j.company}` : ''}</option>)}
          </select>
        </label>
        <div className="prep-count"><span>已确认经历</span><strong>{experiences.length} 条</strong></div>
      </div>
      {!jds.length ? <div className="prep-guidance"><p>还没有目标岗位。先在「理解岗位」输入并分析一份 JD。</p><Button onClick={() => navigate('jd')}>去分析岗位 <ArrowRight size={16}/></Button></div>
        : experiences.length === 0 ? <div className="prep-guidance"><p>已经有目标岗位，但还没有已确认的经历。先核对并确认经历，再进行可信的职业叙事与面试。</p><Button onClick={() => navigate('experiences')}>去确认经历 <ArrowRight size={16}/></Button></div>
        : <div className="prep-actions">
          <Button onClick={() => generateStory(currentJD!.id)} disabled={busy}><Sparkles size={16}/> AI 生成职业主线与自我介绍</Button>
          <Button variant="secondary" onClick={() => quickStartInterview(currentJD!.id)} disabled={busy}><MessageCircle size={16}/> 直接开始模拟面试</Button>
          <p>直接开始使用已确认事实生成基础提纲，无需等待职业故事模型调用；答题追问仍使用当前模型（如已配置）。</p>
        </div>}
    </section>
    <section className="panel prep-story">
      <SectionHeading eyebrow="YOUR STORY ARC" title="职业能力主线" desc="突出与你所选 JD 相关、能够用事实证明的个人能力。" />
      {story && currentJD && story.jd_id === currentJD.id ? <>
        <div className="prep-state"><span className="tag tag-lilac">{story.mode === 'ai' ? 'AI 生成 · 需核对' : '规则提纲 · 待完善'}</span><span>对应岗位：{currentJD.title}</span></div>
        <h3 className="prep-position">{story.data.positioning}</h3>
        <p className="prep-narrative">{story.data.narrative}</p>
        <div className="prep-highlights">{story.data.highlights.map(h => <div className="prep-highlight" key={h.experience_id}>
          <strong>{byId.get(h.experience_id)?.title || '原经历已变更'}</strong><span>{h.role}</span><p>{h.reason}</p>
        </div>)}</div>
        {story.data.cautions.length > 0 && <p className="prep-caution"><CircleAlert size={15}/> {story.data.cautions[0]}</p>}
      </> : <div className="prep-placeholder"><GitBranch size={26}/><p>尚未为当前岗位创建职业主线。点击上方按钮生成；如生成慢或失败，可直接进入面试。</p></div>}
    </section>
    <section className="panel prep-intro">
      <SectionHeading eyebrow="SELF INTRODUCTION" title="面试自我介绍" desc="按面试场景选择时长，Agent 根据目标岗位与已确认经历生成口语化版本。" />
      {story && currentJD && story.jd_id === currentJD.id ? <>
        <div className="intro-duration-panel">
          <div className="intro-duration-heading"><strong>选择介绍时长</strong><span>中文面试语速按约230字/分钟估算</span></div>
          <div className="intro-duration-options">
            {[1, 2, 3, 5].map(minutes => <button key={minutes} type="button" className={'intro-duration-option ' + (introDuration === String(minutes) ? 'active' : '')} onClick={() => { setIntroDuration(String(minutes)); setIntroStatus(''); }}>
              <strong>{minutes} 分钟</strong><small>约 {minutes * 230} 字</small>
            </button>)}
            <button type="button" className={'intro-duration-option custom ' + (introDuration === 'custom' ? 'active' : '')} onClick={() => { setIntroDuration('custom'); setIntroStatus(''); }}>
              <strong>自定义</strong><small>1–10 分钟</small>
            </button>
          </div>
          {introDuration === 'custom' && <label className="intro-custom-field"><span>自定义时长</span><input type="number" min="1" max="10" step="0.5" value={customIntroDuration} onChange={e => { setCustomIntroDuration(e.target.value); setIntroStatus(''); }} /><span>分钟</span></label>}
          <div className="intro-duration-footer"><span>本次目标：约 {targetIntroChars} 字</span><Button onClick={generateIntroduction} disabled={busy || !validIntroDuration}><Sparkles size={15}/>{story.data.introduction_actual_chars ? '重新生成自我介绍' : '生成自我介绍'}</Button></div>
          {!validIntroDuration && <p className="intro-inline-warning">请输入 1–10 分钟之间的时长。</p>}
        </div>
        <div className="interview-intro">
          <div className="intro-result-heading"><span>{story.data.introduction_mode === 'ai' || story.mode === 'ai' ? 'AI 自我介绍草稿 · 请核对事实' : '基于事实的自我介绍提纲'}</span><button type="button" className="intro-copy-btn" onClick={copyIntroduction} disabled={!currentIntro}><Copy size={14}/>{introCopied ? '已复制' : '复制文本'}</button></div>
          <p>{currentIntro || '尚未生成自我介绍。请选择时长并点击生成。'}</p>
          {currentIntro && <div className="intro-result-meta"><span>有效字数：{story.data.introduction_actual_chars ?? currentIntroChars} 字</span><span>预计时长：约 {estimatedIntroMinutes.toFixed(1)} 分钟</span><span>目标：{story.data.introduction_target_chars ?? 230} 字</span></div>}
        </div>
        {(story.data.introduction_notes ?? []).map((note, index) => <p className="intro-note" key={index}><CircleAlert size={14}/>{note}</p>)}
        {introStatus && <p className="intro-status">{introStatus}</p>}
      </> : <p className="prep-muted">先选择上方的「AI 生成职业主线与自我介绍」，或直接开始模拟面试生成基础准备材料。</p>}
    </section>
    <section className="panel prep-chat">
      <SectionHeading eyebrow="MOCK INTERVIEW" title="针对性模拟面试" desc="针对目标 JD 与个人经历进行连续追问，不编造用户没有做过的事情。" />
      {!story ? <div className="prep-placeholder"><MessageCircle size={26}/><p>选择目标岗位与已确认经历后，点击上方「直接开始模拟面试」即可练习。</p></div>
      : !interview ? <div className="prep-guidance"><p>准备材料已就绪，可以从真实经历开始练习。</p><Button onClick={() => startInterview(story.id)} disabled={busy}>开始模拟面试 <ArrowRight size={16}/></Button></div>
      : <div className="prep-chat-body"><div className="chat-header"><div className="chat-avatar"><BrainCircuit size={21}/></div><div><b>Career Story 面试官</b><p>围绕当前 JD 与真实经历动态追问</p></div><span className="chat-online">{mode === 'ai' ? 'AI 面试' : '规则演示'}</span></div>
        <div className="chat-messages">{interview.messages.map((m, i) => <div className={'chat-row ' + (m.role === 'user' ? 'from-user' : '')} key={i}><div className="chat-bubble">{m.feedback && <div className="feedback-card"><div className="feedback-title"><Sparkles size={15}/> 上一轮反馈</div><p>{m.feedback.summary}</p>{m.feedback.strengths.length > 0 && <div className="feedback-point"><CheckCircle2 size={14}/> {m.feedback.strengths.join('；')}</div>}{m.feedback.improvements.length > 0 && <div className="feedback-point"><Lightbulb size={14}/> {m.feedback.improvements.join('；')}</div>}</div>}<p>{m.content}</p></div></div>)}</div>
        <form className="chat-composer" onSubmit={e => { e.preventDefault(); if (listening) stopVoiceInput(); void reply(); }}>
          <div className="voice-tools">
            <Button type="button" variant={listening ? 'danger' : 'secondary'} onClick={listening ? stopVoiceInput : startVoiceInput} disabled={busy}>
              {listening ? <MicOff size={16}/> : <Mic size={16}/>} {listening ? '结束语音回答' : '语音回答'}
            </Button>
            <Button type="button" variant="ghost" onClick={speakCurrentQuestion}><Volume2 size={16}/> 朗读当前问题</Button>
            <span className="voice-status">{speechStatus}</span>
          </div>
          <textarea rows={3} placeholder="可以直接说话转成文字，也可以在这里输入或修改答案……" value={answer} onChange={e => setAnswer(e.target.value)}/>
          <div><small>语音识别结果会显示在输入框中；确认内容后再发送。也可以全程使用文字回答。</small><Button type="submit" disabled={busy || answer.trim().length < 2}>发送回答 <Send size={16}/></Button></div>
        </form>
      </div>}
    </section>
  </div>;
}
