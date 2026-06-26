const { createApp, ref, computed, onMounted, watch, nextTick } = Vue
const { createRouter, createWebHistory, useRouter, useRoute } = VueRouter

// ── API Helper ───────────────────────────────────────────────

const api = {
    async get(path) {
        const r = await fetch('/api' + path)
        if (!r.ok) throw new Error('API ' + r.status)
        return r.json()
    },
    async post(path, body) {
        const r = await fetch('/api' + path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        })
        return r.json()
    },
    async put(path) {
        return (await fetch('/api' + path, { method: 'PUT' })).json()
    },
    async del(path) {
        return (await fetch('/api' + path, { method: 'DELETE' })).json()
    },
}

// ── Global State ─────────────────────────────────────────────

const currentProject = ref(null)
const projects = ref([])
const sidebarOpen = ref(false)

async function loadProjects() {
    try { projects.value = await api.get('/projects') }
    catch (e) { console.error('loadProjects:', e) }
}

// ── Navbar Component ─────────────────────────────────────────

const Navbar = {
    template: `
    <aside class="sidebar" :class="{ open: sidebarOpen }">
        <div class="brand">OpenLearning</div>
        <div class="sidebar-nav">
            <router-link to="/" @click="close">📊 仪表盘</router-link>
            <router-link to="/projects" @click="close">📁 项目管理</router-link>
            <router-link to="/bookmarks" @click="close">⭐ 我的收藏</router-link>
            <template v-if="currentProject">
                <div class="nav-divider"></div>
                <div class="nav-project-title">当前项目</div>
                <router-link :to="'/projects/' + currentProject.id" @click="close">📋 项目详情</router-link>
                <router-link :to="'/projects/' + currentProject.id + '/graph'" @click="close">🗺️ 知识图谱</router-link>
                <router-link :to="'/projects/' + currentProject.id + '/learning-path'" @click="close">📚 学习路径</router-link>
                <router-link :to="'/projects/' + currentProject.id + '/concepts'" @click="close">📖 知识列表</router-link>
            </template>
        </div>
        <div class="project-info" v-if="currentProject">
            {{ currentProject.title }}
        </div>
    </aside>
    `,
    setup() {
        function close() { sidebarOpen.value = false }
        return { currentProject, sidebarOpen, close }
    },
}

// ── StatCard Component ───────────────────────────────────────

const StatCard = {
    props: ['value', 'label', 'color'],
    template: `
    <div class="card stat-card">
        <div class="value" :style="color ? { color } : {}">{{ display }}</div>
        <div class="label">{{ label }}</div>
    </div>
    `,
    setup(props) {
        const display = computed(() => {
            if (typeof props.value === 'number') return Number.isInteger(props.value) ? props.value : props.value.toFixed(1)
            return props.value ?? '-'
        })
        return { display }
    },
}

// ── Badge Component ──────────────────────────────────────────

const Badge = {
    props: ['text', 'variant'],
    template: '<span class="badge" :class="cls">{{ text }}</span>',
    setup(props) {
        const cls = computed(() => 'badge-' + (props.variant || 'gray'))
        return { cls }
    },
}

// ── NodeCard Component ───────────────────────────────────────

const NodeCard = {
    props: ['node'],
    template: `
    <div class="card node-card" @click="go">
        <div class="node-header">
            <span class="node-name">{{ node.name }}</span>
            <span class="stars">{{ stars }}</span>
        </div>
        <div class="node-meta">
            <badge :text="node.type" variant="blue" />
            <badge :text="node.difficulty" :variant="dv" />
        </div>
        <div class="node-definition" v-if="node.definition">{{ node.definition }}</div>
    </div>
    `,
    setup(props) {
        const route = useRoute()
        const router = useRouter()
        const stars = computed(() => {
            const s = Math.round((props.node.importance || 0.5) * 5)
            return '★'.repeat(s) + '☆'.repeat(5 - s)
        })
        const dv = computed(() => ({ beginner: 'green', intermediate: 'yellow', advanced: 'red' })[props.node.difficulty] || 'gray')
        function go() { router.push('/projects/' + route.params.projectId + '/concepts/' + props.node.id) }
        return { stars, dv, go }
    },
}

// ── Dashboard Page ───────────────────────────────────────────

const DashboardPage = {
    template: `
    <div>
        <h1 class="page-title">仪表盘</h1>
        <div class="stats-grid">
            <stat-card :value="projects.length" label="项目数" />
            <stat-card :value="totalRes" label="资源总数" />
            <stat-card :value="avg" label="平均质量" />
        </div>
        <div class="card">
            <h2>最近项目</h2>
            <table>
                <thead><tr><th>ID</th><th>标题</th><th>状态</th><th>资源</th><th>操作</th></tr></thead>
                <tbody>
                    <tr v-for="p in projects.slice(0,10)" :key="p.id">
                        <td style="color:var(--text-muted)">{{ p.id.slice(0,8) }}</td>
                        <td><router-link :to="'/projects/'+p.id">{{ p.title }}</router-link></td>
                        <td><badge :text="p.status" :variant="sv(p.status)" /></td>
                        <td>{{ p.resource_count || 0 }}</td>
                        <td><router-link :to="'/projects/'+p.id" class="btn btn-primary btn-sm">查看</router-link></td>
                    </tr>
                    <tr v-if="!projects.length"><td colspan="5" class="empty-state">暂无项目，去项目管理创建</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    `,
    setup() {
        const totalRes = computed(() => projects.value.reduce((s, p) => s + (p.resource_count || 0), 0))
        const avg = computed(() => {
            const scored = projects.value.filter(p => p.avg_score)
            return scored.length ? (scored.reduce((s, p) => s + p.avg_score, 0) / scored.length).toFixed(1) : '-'
        })
        const sv = s => ({ active: 'green', archived: 'gray', paused: 'yellow' })[s] || 'gray'
        onMounted(loadProjects)
        return { projects, totalRes, avg, sv }
    },
}

// ── Projects Page ────────────────────────────────────────────

const ProjectsPage = {
    template: `
    <div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
            <h1 class="page-title" style="margin:0">项目管理</h1>
            <button class="btn btn-primary" @click="create_">+ 新建项目</button>
        </div>
        <div class="card">
            <table>
                <thead><tr><th>ID</th><th>标题</th><th>状态</th><th>资源</th><th>质量</th><th>操作</th></tr></thead>
                <tbody>
                    <tr v-for="p in projects" :key="p.id">
                        <td style="color:var(--text-muted)">{{ p.id.slice(0,8) }}</td>
                        <td><router-link :to="'/projects/'+p.id">{{ p.title }}</router-link></td>
                        <td><badge :text="p.status" :variant="sv(p.status)" /></td>
                        <td>{{ p.resource_count || 0 }}</td>
                        <td>{{ p.avg_score ? p.avg_score.toFixed(1) : '-' }}</td>
                        <td>
                            <router-link :to="'/projects/'+p.id" class="btn btn-primary btn-sm">查看</router-link>
                            <button class="btn btn-danger btn-sm" style="margin-left:6px" @click="del(p)">删除</button>
                        </td>
                    </tr>
                    <tr v-if="!projects.length"><td colspan="6" class="empty-state">暂无项目</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    `,
    setup() {
        const sv = s => ({ active: 'green', archived: 'gray', paused: 'yellow' })[s] || 'gray'
        async function create_() {
            const title = prompt('请输入学习主题:')
            if (!title) return
            await api.post('/projects', { title })
            await loadProjects()
        }
        async function del(p) {
            if (!confirm('确认删除 "' + p.title + '"？')) return
            await api.del('/projects/' + p.id)
            await loadProjects()
        }
        onMounted(loadProjects)
        return { projects, sv, create_, del }
    },
}

// ── Project Detail Page ──────────────────────────────────────

const ProjectDetailPage = {
    template: `
    <div v-if="project">
        <h1 class="page-title">{{ project.title }}</h1>
        <p v-if="project.description" style="color:var(--text-light);margin:-16px 0 24px">{{ project.description }}</p>
        <div class="stats-grid">
            <stat-card :value="project.resource_count" label="资源数" />
            <stat-card :value="project.avg_score" label="平均质量" />
            <stat-card :value="srcCount" label="数据源" />
        </div>
        <div class="grid-3">
            <div class="card nav-card" @click="go('graph')">
                <div class="nav-card-icon">🗺️</div>
                <div class="nav-card-title">知识图谱</div>
                <div class="nav-card-desc">交互式知识结构</div>
            </div>
            <div class="card nav-card" @click="go('learning-path')">
                <div class="nav-card-icon">📚</div>
                <div class="nav-card-title">学习路径</div>
                <div class="nav-card-desc">个性化学习计划</div>
            </div>
            <div class="card nav-card" @click="go('concepts')">
                <div class="nav-card-icon">📖</div>
                <div class="nav-card-title">知识列表</div>
                <div class="nav-card-desc">全部知识点</div>
            </div>
        </div>
        <div class="card" style="margin-top:16px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                <h2 style="margin:0">资源列表</h2>
                <div style="display:flex;gap:8px">
                    <button class="btn btn-outline btn-sm" @click="exportMd">导出 MD</button>
                    <button class="btn btn-primary btn-sm" @click="collect" :disabled="collecting">
                        {{ collecting ? '采集中...' : '采集新资源' }}
                    </button>
                </div>
            </div>
            <table>
                <thead><tr><th>标题</th><th>来源</th><th>质量</th><th>难度</th></tr></thead>
                <tbody>
                    <tr v-for="r in resources" :key="r.id">
                        <td><a :href="r.url" target="_blank">{{ r.title }}</a></td>
                        <td><badge :text="r.source" variant="gray" /></td>
                        <td :style="{ color: sc(r.quality_score) }">{{ r.quality_score ? r.quality_score.toFixed(1) : '-' }}</td>
                        <td>{{ r.difficulty || '-' }}</td>
                    </tr>
                    <tr v-if="!resources.length"><td colspan="4" class="empty-state">暂无资源</td></tr>
                </tbody>
            </table>
            <div v-if="totalPages > 1" class="pagination">
                <button class="btn btn-outline btn-sm" :disabled="page<=1" @click="goPage(page-1)">‹ 上一页</button>
                <span class="page-info">{{ page }} / {{ totalPages }} (共 {{ total }} 条)</span>
                <button class="btn btn-outline btn-sm" :disabled="page>=totalPages" @click="goPage(page+1)">下一页 ›</button>
            </div>
        </div>
    </div>
    <div v-else class="loading"><div class="spinner"></div><p>加载中...</p></div>
    `,
    setup() {
        const route = useRoute()
        const router = useRouter()
        const project = ref(null)
        const resources = ref([])
        const collecting = ref(false)
        const page = ref(1)
        const totalPages = ref(1)
        const total = ref(0)
        const srcCount = computed(() => Object.keys(project.value?.sources || {}).length)

        async function load() {
            const pid = route.params.projectId
            try {
                project.value = await api.get('/projects/' + pid)
                currentProject.value = project.value
                const data = await api.get('/projects/' + pid + '/resources?page=' + page.value + '&page_size=30')
                resources.value = Array.isArray(data) ? data : (data.items || [])
                totalPages.value = data.total_pages || 1
                total.value = data.total || 0
            } catch (e) { console.error(e) }
        }

        function goPage(p) { page.value = p; load() }

        function go(page) { router.push('/projects/' + route.params.projectId + '/' + page) }

        async function collect() {
            collecting.value = true
            try {
                const r = await api.post('/projects/' + route.params.projectId + '/collect', {})
                if (r.status === 'completed') {
                    alert('采集完成！\n资源: ' + r.resources_collected + '\n知识节点: ' + r.knowledge_graph_nodes)
                } else {
                    alert('采集失败: ' + (r.error || '未知错误'))
                }
                await load()
            } catch (e) {
                alert('采集请求失败: ' + e.message)
            } finally {
                collecting.value = false
            }
        }

        function exportMd() { window.open('/api/projects/' + route.params.projectId + '/export?format=markdown') }

        function sc(s) { return s >= 7 ? 'var(--success)' : s >= 5 ? 'var(--warning)' : 'var(--danger)' }

        onMounted(load)
        return { project, resources, collecting, srcCount, go, collect, exportMd, sc, page, totalPages, total, goPage }
    },
}

// ── Graph Page ───────────────────────────────────────────────

const GraphPage = {
    template: `
    <div>
        <div class="graph-toolbar">
            <input v-model="q" placeholder="搜索节点..." class="search-input" />
            <select v-model="layout" class="layout-select">
                <option value="breadthfirst">层次布局</option>
                <option value="cose">力导向</option>
                <option value="concentric">同心圆</option>
                <option value="circle">环形</option>
                <option value="grid">网格</option>
            </select>
            <div style="display:flex;gap:4px">
                <button class="btn btn-outline btn-sm" @click="zoomOut">−</button>
                <button class="btn btn-outline btn-sm" @click="fit">适应</button>
                <button class="btn btn-outline btn-sm" @click="zoomIn">+</button>
            </div>
            <span style="color:var(--text-muted);font-size:12px">{{ graphStats.nodes }} 节点 · {{ graphStats.edges }} 关系</span>
        </div>
        <div v-if="hasData">
            <div ref="cyEl" class="graph-container"></div>
            <div class="graph-legend">
                <h4>节点类型</h4>
                <div class="graph-legend-item"><span class="graph-legend-dot" style="background:#3B82F6"></span>概念</div>
                <div class="graph-legend-item"><span class="graph-legend-dot" style="background:#F59E0B"></span>技术</div>
                <div class="graph-legend-item"><span class="graph-legend-dot" style="background:#10B981"></span>原理</div>
                <div class="graph-legend-item"><span class="graph-legend-dot" style="background:#8B5CF6"></span>实践</div>
                <div style="border-top:1px solid var(--border);margin:8px 0"></div>
                <h4>难度边框</h4>
                <div class="graph-legend-item"><span class="graph-legend-dot" style="border:3px solid #10B981;background:transparent"></span>入门</div>
                <div class="graph-legend-item"><span class="graph-legend-dot" style="border:3px solid #F59E0B;background:transparent"></span>进阶</div>
                <div class="graph-legend-item"><span class="graph-legend-dot" style="border:3px solid #EF4444;background:transparent"></span>高级</div>
                <div style="border-top:1px solid var(--border);margin:8px 0"></div>
                <h4>关系类型</h4>
                <div class="graph-legend-item"><span class="graph-legend-line" style="background:#CBD5E1"></span>相关</div>
                <div class="graph-legend-item"><span class="graph-legend-line" style="background:#F87171;border-top:2px dashed #F87171;height:0"></span>前置</div>
                <div style="margin-top:8px;font-size:11px;color:var(--text-muted)">节点越大 = 重要度越高</div>
            </div>
        </div>
        <div v-else class="empty-state">
            <div class="icon">🗺️</div>
            <p>暂无知识图谱数据</p>
            <p style="font-size:13px;margin-top:8px">请先对此项目执行"采集新资源"</p>
            <router-link :to="'/projects/' + $route.params.projectId" class="btn btn-primary" style="margin-top:16px">返回项目详情</router-link>
        </div>
        <div v-show="tip.show" class="graph-tooltip" :style="{ left: tip.x+'px', top: tip.y+'px' }">
            <div class="tooltip-title">{{ tip.title }}</div>
            <div class="tooltip-meta">{{ tip.meta }}</div>
            <div class="tooltip-def" v-if="tip.def">{{ tip.def }}</div>
        </div>
    </div>
    `,
    setup() {
        const route = useRoute()
        const router = useRouter()
        const cyEl = ref(null)
        const q = ref('')
        const layout = ref('breadthfirst')
        const tip = ref({ show: false, x: 0, y: 0, title: '', meta: '', def: '' })
        const hasData = ref(false)
        const graphStats = ref({ nodes: 0, edges: 0 })
        let cy = null
        const TC = { concept: '#3B82F6', technology: '#F59E0B', principle: '#10B981', practice: '#8B5CF6', project: '#EC4899', application: '#06B6D4' }
        const DC = { beginner: '#10B981', intermediate: '#F59E0B', advanced: '#EF4444' }

        async function load() {
            const pid = route.params.projectId
            try {
                const [project, data] = await Promise.all([
                    api.get('/projects/' + pid),
                    api.get('/projects/' + pid + '/graph'),
                ])
                currentProject.value = project
                if (data.nodes && data.nodes.length) {
                    hasData.value = true
                    graphStats.value = { nodes: data.nodes.length, edges: data.edges.length }
                    await nextTick()
                    init(data.nodes, data.edges)
                }
            } catch (e) { console.error(e) }
        }

        function init(nodes, edges) {
            if (typeof cytoscape === 'undefined') {
                const s = document.createElement('script')
                s.src = 'https://unpkg.com/cytoscape@3.28.0/dist/cytoscape.min.js'
                s.onload = () => build(nodes, edges)
                document.head.appendChild(s)
            } else build(nodes, edges)
        }

        function build(nodes, edges) {
            const nodeIds = new Set(nodes.map(n => n.id))
            const validEdges = edges.filter(e => nodeIds.has(e.from) && nodeIds.has(e.to))
            // Compute in-degree for node sizing
            const inDeg = {}
            validEdges.forEach(e => { inDeg[e.to] = (inDeg[e.to] || 0) + 1 })
            const maxDeg = Math.max(1, ...Object.values(inDeg))

            cy = cytoscape({
                container: cyEl.value,
                elements: [
                    ...nodes.map(n => {
                        const imp = n.importance || 0.5
                        const deg = inDeg[n.id] || 0
                        const size = 30 + imp * 30 + (deg / maxDeg) * 15
                        return { data: { id: n.id, label: n.name, type: n.type, difficulty: n.difficulty, importance: imp, def: (n.definition || '').substring(0, 120), size } }
                    }),
                    ...validEdges.map(e => ({ data: { source: e.from, target: e.to, type: e.type, weight: e.weight || 1, reason: e.reason || '' } })),
                ],
                style: [
                    { selector: 'node', style: {
                        label: 'data(label)',
                        'background-color': el => TC[el.data('type')] || '#3B82F6',
                        color: '#1a1a2e',
                        'text-valign': 'bottom',
                        'text-margin-y': 6,
                        'font-size': '11px',
                        'font-weight': '600',
                        width: 'data(size)',
                        height: 'data(size)',
                        'text-wrap': 'ellipsis',
                        'text-max-width': '90px',
                        'border-width': 3,
                        'border-color': el => DC[el.data('difficulty')] || '#94A3B8',
                        'background-opacity': 0.9,
                        'text-outline-color': '#fff',
                        'text-outline-width': 2,
                    }},
                    { selector: 'node:active', style: { 'overlay-opacity': 0 } },
                    { selector: 'node.highlighted', style: {
                        'border-width': 4,
                        'border-color': '#F59E0B',
                        'background-opacity': 1,
                        'font-size': '13px',
                        'z-index': 999,
                    }},
                    { selector: 'node.dimmed', style: { opacity: 0.1 } },
                    { selector: 'edge', style: {
                        width: el => 1 + (el.data('weight') || 1) * 0.5,
                        'line-color': '#CBD5E1',
                        'target-arrow-color': '#CBD5E1',
                        'target-arrow-shape': 'triangle',
                        'arrow-scale': 0.8,
                        'curve-style': 'bezier',
                        opacity: 0.6,
                    }},
                    { selector: 'edge[type="prerequisite"]', style: {
                        'line-color': '#F87171',
                        'target-arrow-color': '#F87171',
                        'line-style': 'dashed',
                        width: 2,
                        opacity: 0.7,
                    }},
                    { selector: 'edge.highlighted', style: {
                        'line-color': '#F59E0B',
                        'target-arrow-color': '#F59E0B',
                        opacity: 1,
                        width: 3,
                    }},
                    { selector: 'edge.dimmed', style: { opacity: 0.05 } },
                ],
                layout: { name: 'breadthfirst', directed: true, spacingFactor: 1.6, padding: 30 },
                minZoom: 0.2, maxZoom: 4,
                wheelSensitivity: 0.3,
            })

            // Hover: highlight neighbors
            cy.on('mouseover', 'node', e => {
                const node = e.target
                const neighborhood = node.closedNeighborhood()
                cy.elements().addClass('dimmed')
                neighborhood.removeClass('dimmed')
                node.addClass('highlighted')
                neighborhood.edges().addClass('highlighted')
                const d = node.data()
                tip.value = { show: true, x: 0, y: 0, title: d.label, meta: d.type + ' · ' + d.difficulty + ' · 重要度 ' + (d.importance || 0.5).toFixed(1), def: d.def || '' }
            })
            cy.on('mousemove', e => { tip.value.x = e.originalEvent.clientX + 15; tip.value.y = e.originalEvent.clientY + 15 })
            cy.on('mouseout', 'node', () => {
                cy.elements().removeClass('dimmed highlighted')
                tip.value.show = false
            })
            cy.on('tap', 'node', e => router.push('/projects/' + route.params.projectId + '/concepts/' + e.target.id()))

            // Background click to reset
            cy.on('tap', e => { if (e.target === cy) cy.elements().removeClass('dimmed highlighted') })
        }

        function fit() { if (cy) cy.fit(undefined, 40) }
        function zoomIn() { if (cy) cy.zoom({ level: cy.zoom() * 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }) }
        function zoomOut() { if (cy) cy.zoom({ level: cy.zoom() / 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }) }

        watch(q, v => {
            if (!cy) return
            if (!v) { cy.elements().removeClass('highlighted dimmed'); return }
            cy.nodes().forEach(n => {
                const m = n.data('label').toLowerCase().includes(v.toLowerCase())
                n.toggleClass('highlighted', m).toggleClass('dimmed', !m)
            })
            cy.edges().addClass('dimmed')
            cy.edges().forEach(e => { if (e.source().hasClass('highlighted') || e.target().hasClass('highlighted')) e.removeClass('dimmed') })
        })

        watch(layout, v => { if (cy) cy.layout({ name: v, directed: v === 'breadthfirst', spacingFactor: 1.5, animate: true }).run() })

        onMounted(load)
        return { cyEl, q, layout, tip, hasData, graphStats, fit, zoomIn, zoomOut }
    },
}

// ── Learning Path Page ───────────────────────────────────────

const LearningPathPage = {
    template: `
    <div v-if="pd && pd.total_steps">
        <h1 class="page-title">{{ projectTitle }} — 学习路径</h1>
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                <span style="font-weight:500">学习进度</span>
                <span style="color:var(--text-light)">{{ done }}/{{ pd.total_steps }}</span>
            </div>
            <div class="progress-bar"><div class="fill" :style="{ width: pct + '%' }"></div></div>
        </div>
        <div v-for="(g, name) in groups" :key="name" class="phase-group">
            <div class="phase-header" @click="toggle(name)">
                <span><span class="dot" :class="'dot-'+g.color"></span>{{ name }} ({{ g.steps.length }})</span>
                <span style="color:var(--text-muted)">{{ exp[name] ? '▼' : '▶' }}</span>
            </div>
            <div class="phase-steps" v-show="exp[name]">
                <div v-for="s in g.steps" :key="s.concept" class="step-item">
                    <input type="checkbox" :checked="!!prog[s.concept]" @change="toggleStep(s.concept)" />
                    <div style="flex:1;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                        <router-link :to="'/projects/'+pid+'/concepts/'+s.concept" class="step-link">
                            {{ s.name || s.concept }}
                        </router-link>
                        <badge v-if="s.priority==='high'" text="优先" variant="red" />
                        <badge :text="s.difficulty" :variant="dv(s.difficulty)" />
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div v-else-if="pd && !pd.total_steps" class="empty-state">
        <div class="icon">📚</div>
        <p>暂无学习路径数据</p>
        <p style="font-size:13px;margin-top:8px">请先对此项目执行"采集新资源"</p>
        <router-link :to="'/projects/' + $route.params.projectId" class="btn btn-primary" style="margin-top:16px">返回项目详情</router-link>
    </div>
    <div v-else class="loading"><div class="spinner"></div><p>加载中...</p></div>
`,
    setup() {
        const route = useRoute()
        const pd = ref(null)
        const prog = ref({})
        const exp = ref({})
        const projectTitle = ref('学习路径')
        const pid = computed(() => route.params.projectId)
        const done = computed(() => Object.keys(prog.value).length)
        const pct = computed(() => Math.round(done.value / (pd.value?.total_steps || 1) * 100))

        const groups = computed(() => {
            const steps = pd.value?.steps || []
            const g = { '入门': [], '基础': [], '进阶': [], '高级': [] }
            for (const s of steps) {
                const d = s.difficulty || 'intermediate'
                if (d === 'beginner') g['入门'].push(s)
                else if (d === 'advanced') g['高级'].push(s)
                else if ((s.importance || 0.5) >= 0.5) g['进阶'].push(s)
                else g['基础'].push(s)
            }
            const r = {}
            const c = { '入门': 'green', '基础': 'blue', '进阶': 'amber', '高级': 'red' }
            for (const [n, s] of Object.entries(g)) {
                if (s.length) { r[n] = { steps: s, color: c[n] }; if (exp.value[n] === undefined) exp.value[n] = true }
            }
            return r
        })

        const dv = d => ({ beginner: 'green', intermediate: 'yellow', advanced: 'red' })[d] || 'gray'
        function toggle(n) { exp.value[n] = !exp.value[n] }
        function toggleStep(cid) {
            if (prog.value[cid]) delete prog.value[cid]
            else prog.value[cid] = Date.now()
            localStorage.setItem('ol_progress', JSON.stringify(prog.value))
        }

        async function load() {
            const p = route.params.projectId
            try {
                const [project, pathData] = await Promise.all([
                    api.get('/projects/' + p),
                    api.get('/projects/' + p + '/learning-path'),
                ])
                pd.value = pathData
                projectTitle.value = project.title || '学习路径'
                currentProject.value = project
                prog.value = JSON.parse(localStorage.getItem('ol_progress') || '{}')
            } catch (e) { console.error(e) }
        }

        onMounted(load)
        return { pd, prog, exp, pid, projectTitle, done, pct, groups, dv, toggle, toggleStep }
    },
}

// ── Concepts List Page ───────────────────────────────────────

const ConceptsPage = {
    template: `
    <div>
        <h1 class="page-title">知识列表</h1>
        <div class="search-bar">
            <input v-model="sq" placeholder="搜索知识点..." />
        </div>
        <div class="filter-pills" style="margin-bottom:8px">
            <button class="filter-pill" :class="{active:tf==='all'}" @click="tf='all'">全部类型</button>
            <button v-for="t in types" :key="t" class="filter-pill" :class="{active:tf===t}" @click="tf=t">{{ t }}</button>
        </div>
        <div class="filter-pills" style="margin-bottom:16px">
            <button class="filter-pill" :class="{active:df==='all'}" @click="df='all'">全部难度</button>
            <button v-for="d in diffs" :key="d" class="filter-pill" :class="{active:df===d}" @click="df=d">{{ d }}</button>
        </div>
        <p style="color:var(--text-light);margin-bottom:16px">{{ filtered.length }} 个知识点</p>
        <div class="node-grid">
            <node-card v-for="n in filtered" :key="n.id" :node="n" />
        </div>
        <div v-if="!filtered.length" class="empty-state">
            <div class="icon">📚</div>
            <p>未找到匹配的知识点</p>
        </div>
    </div>
    `,
    setup() {
        const route = useRoute()
        const concepts = ref([])
        const sq = ref('')
        const tf = ref('all')
        const df = ref('all')
        const types = computed(() => [...new Set(concepts.value.map(c => c.type))].sort())
        const diffs = computed(() => [...new Set(concepts.value.map(c => c.difficulty))].sort())
        const filtered = computed(() => {
            let l = concepts.value
            if (tf.value !== 'all') l = l.filter(c => c.type === tf.value)
            if (df.value !== 'all') l = l.filter(c => c.difficulty === df.value)
            if (sq.value) { const q = sq.value.toLowerCase(); l = l.filter(c => c.name.toLowerCase().includes(q) || (c.definition || '').toLowerCase().includes(q)) }
            return l.sort((a, b) => (b.importance || 0.5) - (a.importance || 0.5))
        })

        async function load() {
            const pid = route.params.projectId
            try {
                concepts.value = await api.get('/projects/' + pid + '/concepts')
                currentProject.value = await api.get('/projects/' + pid)
            } catch (e) { console.error(e) }
        }
        onMounted(load)
        return { concepts, sq, tf, df, types, diffs, filtered }
    },
}

// ── Concept Detail Page ──────────────────────────────────────

const ConceptDetailPage = {
    template: `
    <div v-if="node">
        <div class="concept-header">
            <h1 class="page-title" style="margin:0">{{ node.name }}</h1>
            <badge :text="node.type" variant="blue" />
            <badge :text="node.difficulty" :variant="dv" />
            <span class="stars">{{ stars }}</span>
            <button class="btn btn-ghost" @click="toggleBookmark" style="margin-left:auto">{{ bookmarked ? '★ 已收藏' : '☆ 收藏' }}</button>
        </div>

        <div class="card" v-if="node.definition">
            <h2>📖 定义</h2>
            <p>{{ node.definition }}</p>
        </div>

        <div class="card" v-if="node.explanation">
            <h2>💡 详解</h2>
            <p v-for="(p,i) in expl" :key="i" style="margin-bottom:12px">{{ p }}</p>
        </div>

        <div class="card" v-if="fl(node.key_points).length">
            <h2>🎯 关键要点</h2>
            <ul style="padding-left:20px"><li v-for="(p,i) in fl(node.key_points)" :key="i" style="margin-bottom:6px">{{ p }}</li></ul>
        </div>

        <div class="card" v-if="fl(node.examples).length">
            <h2>🔧 实例</h2>
            <div v-for="(e,i) in fl(node.examples)" :key="i" style="margin-bottom:8px">▸ {{ e }}</div>
        </div>

        <div class="card concept-card warning" v-if="fl(node.common_mistakes).length">
            <h2>⚠️ 常见误区</h2>
            <ul style="padding-left:20px"><li v-for="(m,i) in fl(node.common_mistakes)" :key="i" style="margin-bottom:6px">{{ m }}</li></ul>
        </div>

        <div class="card concept-card tip" v-if="node.learning_tips">
            <h2>💡 学习建议</h2>
            <p style="font-style:italic">{{ node.learning_tips }}</p>
        </div>

        <div class="card" v-if="node.references && node.references.length">
            <h2>📌 参考来源</h2>
            <p style="font-size:13px;color:var(--text-muted);margin-bottom:12px">以下资源为本知识点的生成提供了内容参考</p>
            <div v-for="(ref,i) in node.references" :key="i" style="margin-bottom:8px;padding:8px 12px;background:var(--bg);border-radius:6px">
                <a :href="ref.url" target="_blank" style="font-weight:500;color:var(--primary)">{{ ref.title || ref.url }}</a>
                <div style="font-size:12px;color:var(--text-muted);margin-top:2px">
                    <badge v-if="ref.source" :text="ref.source" variant="gray" />
                    <span v-if="ref.quality_score" style="margin-left:8px">质量: {{ ref.quality_score.toFixed(1) }}/10</span>
                </div>
            </div>
        </div>

        <div class="card" v-if="dt.prerequisites && dt.prerequisites.length">
            <h2>📋 前置知识</h2>
            <div class="link-group">
                <router-link v-for="p in dt.prerequisites" :key="p.id" :to="'/projects/'+pid+'/concepts/'+p.id" class="link-tag link-red">
                    {{ p.name }}<span v-if="p.reason" class="link-reason">({{ p.reason }})</span>
                </router-link>
            </div>
        </div>

        <div class="card" v-if="dt.extends && dt.extends.length">
            <h2>🚀 进阶方向</h2>
            <div class="link-group">
                <router-link v-for="e in dt.extends" :key="e.id" :to="'/projects/'+pid+'/concepts/'+e.id" class="link-tag link-green">{{ e.name }}</router-link>
            </div>
        </div>

        <div class="card" v-if="dt.related && dt.related.length">
            <h2>🔗 相关概念</h2>
            <div class="link-group">
                <router-link v-for="r in dt.related" :key="r.id" :to="'/projects/'+pid+'/concepts/'+r.id" class="link-tag link-blue">{{ r.name }}</router-link>
            </div>
        </div>

        <div class="card" v-if="dt.resources && dt.resources.length">
            <h2>📚 推荐资源</h2>
            <div v-for="r in dt.resources" :key="r.url" class="resource-item">
                <a :href="r.url" target="_blank">{{ r.title || r.url }}</a>
                <badge v-if="r.source" :text="r.source" variant="gray" />
                <span v-if="r.quality_score" class="stars" style="font-size:12px">{{ '★'.repeat(Math.round(r.quality_score/2)) }}</span>
            </div>
        </div>

        <div style="display:flex;justify-content:space-between;margin-top:24px;gap:16px">
            <router-link v-if="prev" :to="'/projects/'+pid+'/concepts/'+prev.id" class="card nav-card" style="flex:1;text-align:left">
                <div style="font-size:12px;color:var(--text-muted)">← 上一个</div>
                <div style="font-weight:600">{{ prev.name }}</div>
            </router-link>
            <div v-else style="flex:1"></div>
            <router-link v-if="next" :to="'/projects/'+pid+'/concepts/'+next.id" class="card nav-card" style="flex:1;text-align:right">
                <div style="font-size:12px;color:var(--text-muted)">下一个 →</div>
                <div style="font-weight:600">{{ next.name }}</div>
            </router-link>
            <div v-else style="flex:1"></div>
        </div>
    </div>
    <div v-else class="loading"><div class="spinner"></div><p>加载中...</p></div>
    `,
    setup() {
        const route = useRoute()
        const node = ref(null)
        const dt = ref({})
        const allNodes = ref([])
        const bookmarked = ref(false)
        const pid = computed(() => route.params.projectId)
        const dv = computed(() => ({ beginner: 'green', intermediate: 'yellow', advanced: 'red' })[node.value?.difficulty] || 'gray')
        const stars = computed(() => { const s = Math.round((node.value?.importance || 0.5) * 5); return '★'.repeat(s) + '☆'.repeat(5 - s) })
        const expl = computed(() => (node.value?.explanation || '').split('\n').filter(p => p.trim()))
        const idx = computed(() => allNodes.value.findIndex(n => n.id === route.params.conceptId))
        const prev = computed(() => idx.value > 0 ? allNodes.value[idx.value - 1] : null)
        const next = computed(() => idx.value >= 0 && idx.value < allNodes.value.length - 1 ? allNodes.value[idx.value + 1] : null)

        function fl(items) {
            if (!items) return []
            const r = []
            for (const i of items) { if (Array.isArray(i)) r.push(...i.filter(Boolean)); else if (i) r.push(i) }
            return r
        }

        function checkBookmark() {
            const bm = JSON.parse(localStorage.getItem('ol_bookmarks') || '[]')
            bookmarked.value = bm.some(b => b.id === route.params.conceptId)
        }

        function toggleBookmark() {
            let bm = JSON.parse(localStorage.getItem('ol_bookmarks') || '[]')
            const cid = route.params.conceptId
            if (bm.some(b => b.id === cid)) { bm = bm.filter(b => b.id !== cid); bookmarked.value = false }
            else { bm.push({ id: cid, name: node.value?.name || cid }); bookmarked.value = true }
            localStorage.setItem('ol_bookmarks', JSON.stringify(bm))
        }

        async function load() {
            const p = route.params.projectId, c = route.params.conceptId
            try {
                const data = await api.get('/projects/' + p + '/concepts/' + c)
                node.value = data.node; dt.value = data
                currentProject.value = { id: p, title: data.node?.name || '概念' }
                // Load all nodes for prev/next
                if (!allNodes.value.length) {
                    const list = await api.get('/projects/' + p + '/concepts')
                    allNodes.value = list.sort((a, b) => (b.importance || 0.5) - (a.importance || 0.5))
                }
                checkBookmark()
            } catch (e) { console.error(e) }
        }

        watch(() => route.params.conceptId, load)
        onMounted(load)
        return { node, dt, pid, dv, stars, expl, fl, prev, next, bookmarked, toggleBookmark }
    },
}

// ── Bookmarks Page ───────────────────────────────────────────

const BookmarksPage = {
    template: `
    <div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
            <h1 class="page-title" style="margin:0">⭐ 我的收藏</h1>
            <button v-if="bm.length" class="btn btn-outline btn-sm" @click="clear">清空全部</button>
        </div>
        <div v-if="bm.length">
            <p style="color:var(--text-light);margin-bottom:16px">{{ bm.length }} 个收藏</p>
            <div class="node-grid">
                <div v-for="b in bm" :key="b.id" class="card node-card" style="display:flex;align-items:center;justify-content:space-between">
                    <router-link :to="'/projects/' + (currentProject?.id || '_') + '/concepts/' + b.id" style="font-weight:500;color:var(--text)">{{ b.name }}</router-link>
                    <button class="btn btn-ghost btn-sm" @click="remove(b.id)" style="color:var(--danger)">移除</button>
                </div>
            </div>
        </div>
        <div v-else class="empty-state">
            <div class="icon">⭐</div>
            <p>暂无收藏</p>
            <p style="font-size:13px;margin-top:8px">在知识点详情页点击"收藏"按钮添加</p>
        </div>
    </div>
    `,
    setup() {
        const bm = ref([])
        function load() { bm.value = JSON.parse(localStorage.getItem('ol_bookmarks') || '[]') }
        function remove(id) { bm.value = bm.value.filter(b => b.id !== id); localStorage.setItem('ol_bookmarks', JSON.stringify(bm.value)) }
        function clear() { if (confirm('清空所有收藏？')) { bm.value = []; localStorage.removeItem('ol_bookmarks') } }
        onMounted(load)
        return { bm, remove, clear }
    },
}

// ── Router ───────────────────────────────────────────────────

const routes = [
    { path: '/', component: DashboardPage },
    { path: '/projects', component: ProjectsPage },
    { path: '/projects/:projectId', component: ProjectDetailPage },
    { path: '/projects/:projectId/graph', component: GraphPage },
    { path: '/projects/:projectId/learning-path', component: LearningPathPage },
    { path: '/projects/:projectId/concepts', component: ConceptsPage },
    { path: '/projects/:projectId/concepts/:conceptId', component: ConceptDetailPage },
    { path: '/bookmarks', component: BookmarksPage },
]

const router = createRouter({ history: createWebHistory(), routes })

// ── Mount ────────────────────────────────────────────────────

const app = createApp({
    template: `
    <button class="sidebar-toggle" @click="sidebarOpen = !sidebarOpen">☰</button>
    <div class="app-layout" @click="sidebarOpen = false">
        <navbar />
        <div class="main-content">
            <router-view />
        </div>
    </div>
    `,
    setup() { return { sidebarOpen } },
})

app.component('navbar', Navbar)
app.component('stat-card', StatCard)
app.component('badge', Badge)
app.component('node-card', NodeCard)
app.use(router)
app.mount('#app')
