import { createApp, ref, computed, onMounted, watch } from 'vue'
import { createRouter, createWebHistory, useRouter, useRoute } from 'vue-router'

// ── API Helper ───────────────────────────────────────────────

const api = {
    async get(path) {
        const r = await fetch('/api' + path)
        if (!r.ok) throw new Error(`API error: ${r.status}`)
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
        const r = await fetch('/api' + path, { method: 'PUT' })
        return r.json()
    },
    async del(path) {
        const r = await fetch('/api' + path, { method: 'DELETE' })
        return r.json()
    },
}

// ── Global State ─────────────────────────────────────────────

const currentProject = ref(null)
const projects = ref([])

async function loadProjects() {
    try {
        projects.value = await api.get('/projects')
    } catch (e) {
        console.error('Failed to load projects:', e)
    }
}

// ── Components ───────────────────────────────────────────────

const Navbar = {
    template: `
    <nav class="sidebar">
        <div class="brand">OpenLearning</div>
        <nav>
            <router-link to="/">仪表盘</router-link>
            <router-link to="/projects">项目管理</router-link>
            <template v-if="currentProject">
                <div class="nav-divider"></div>
                <div class="nav-project-title">{{ currentProject.title }}</div>
                <router-link :to="'/projects/' + currentProject.id + '/graph'">知识图谱</router-link>
                <router-link :to="'/projects/' + currentProject.id + '/learning-path'">学习路径</router-link>
                <router-link :to="'/projects/' + currentProject.id + '/concepts'">知识列表</router-link>
            </template>
        </nav>
        <div class="project-info" v-if="currentProject">
            当前项目: {{ currentProject.title }}
        </div>
    </nav>
    `,
    setup() {
        return { currentProject }
    },
}

const StatCard = {
    props: ['value', 'label', 'color'],
    template: `
    <div class="card stat-card">
        <div class="value" :style="{ color: color || 'var(--primary)' }">{{ displayValue }}</div>
        <div class="label">{{ label }}</div>
    </div>
    `,
    computed: {
        displayValue() {
            if (typeof this.value === 'number') {
                return Number.isInteger(this.value) ? this.value : this.value.toFixed(1)
            }
            return this.value ?? '-'
        },
    },
}

const Badge = {
    props: ['text', 'variant'],
    template: `<span class="badge" :class="'badge-' + (variant || 'gray')">{{ text }}</span>`,
}

const NodeCard = {
    props: ['node'],
    template: `
    <div class="card node-card" @click="$router.push('/projects/' + projectId + '/concepts/' + node.id)">
        <div class="node-header">
            <span class="node-name">{{ node.name }}</span>
            <span class="stars">{{ stars }}</span>
        </div>
        <div class="node-meta">
            <badge :text="node.type" variant="blue" />
            <badge :text="node.difficulty" :variant="diffVariant" />
        </div>
        <div class="node-definition" v-if="node.definition">{{ node.definition }}</div>
    </div>
    `,
    setup(props) {
        const route = useRoute()
        const projectId = computed(() => route.params.projectId || '')
        const stars = computed(() => {
            const s = Math.round((props.node.importance || 0.5) * 5)
            return '★'.repeat(s) + '☆'.repeat(5 - s)
        })
        const diffVariant = computed(() => {
            const map = { beginner: 'green', intermediate: 'yellow', advanced: 'red' }
            return map[props.node.difficulty] || 'gray'
        })
        return { projectId, stars, diffVariant }
    },
}

// ── Pages ────────────────────────────────────────────────────

const DashboardPage = {
    template: `
    <div>
        <h1 class="page-title">仪表盘</h1>
        <div class="stats-grid">
            <stat-card :value="projects.length" label="项目数" />
            <stat-card :value="totalResources" label="资源总数" />
            <stat-card :value="avgScore" label="平均质量" />
        </div>
        <div class="card">
            <h2>最近项目</h2>
            <table>
                <thead><tr><th>ID</th><th>标题</th><th>状态</th><th>资源数</th><th>操作</th></tr></thead>
                <tbody>
                    <tr v-for="p in projects.slice(0, 5)" :key="p.id">
                        <td style="color:#888">{{ p.id.slice(0,8) }}</td>
                        <td><router-link :to="'/projects/' + p.id">{{ p.title }}</router-link></td>
                        <td><badge :text="p.status" :variant="statusVariant(p.status)" /></td>
                        <td>{{ p.resource_count || 0 }}</td>
                        <td><router-link :to="'/projects/' + p.id" class="btn btn-primary btn-sm">查看</router-link></td>
                    </tr>
                    <tr v-if="!projects.length"><td colspan="5" class="empty-state">暂无项目</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    `,
    setup() {
        const totalResources = computed(() => projects.value.reduce((s, p) => s + (p.resource_count || 0), 0))
        const avgScore = computed(() => {
            const scored = projects.value.filter(p => p.avg_score)
            if (!scored.length) return '-'
            return (scored.reduce((s, p) => s + p.avg_score, 0) / scored.length).toFixed(1)
        })
        const statusVariant = (s) => ({ active: 'green', archived: 'gray', paused: 'yellow' }[s] || 'gray')
        onMounted(loadProjects)
        return { projects, totalResources, avgScore, statusVariant }
    },
}

const ProjectsPage = {
    template: `
    <div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <h1 class="page-title" style="margin:0">项目管理</h1>
            <button class="btn btn-primary" @click="createProject">+ 新建项目</button>
        </div>
        <div class="card">
            <table>
                <thead><tr><th>ID</th><th>标题</th><th>状态</th><th>资源数</th><th>质量</th><th>操作</th></tr></thead>
                <tbody>
                    <tr v-for="p in projects" :key="p.id">
                        <td style="color:#888">{{ p.id.slice(0,8) }}</td>
                        <td><router-link :to="'/projects/' + p.id">{{ p.title }}</router-link></td>
                        <td><badge :text="p.status" :variant="statusVariant(p.status)" /></td>
                        <td>{{ p.resource_count || 0 }}</td>
                        <td>{{ p.avg_score ? p.avg_score.toFixed(1) : '-' }}</td>
                        <td>
                            <router-link :to="'/projects/' + p.id" class="btn btn-primary btn-sm">查看</router-link>
                            <button class="btn btn-danger btn-sm" @click="deleteProject(p)">删除</button>
                        </td>
                    </tr>
                    <tr v-if="!projects.length"><td colspan="6" class="empty-state">暂无项目</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    `,
    setup() {
        const router = useRouter()
        const statusVariant = (s) => ({ active: 'green', archived: 'gray', paused: 'yellow' }[s] || 'gray')
        async function createProject() {
            const title = prompt('请输入学习主题:')
            if (!title) return
            await api.post('/projects', { title })
            await loadProjects()
        }
        async function deleteProject(p) {
            if (!confirm(`确认删除项目 "${p.title}"？`)) return
            await api.del('/projects/' + p.id)
            await loadProjects()
        }
        onMounted(loadProjects)
        return { projects, statusVariant, createProject, deleteProject }
    },
}

const ProjectDetailPage = {
    template: `
    <div v-if="project">
        <h1 class="page-title">{{ project.title }}</h1>
        <p style="color:var(--text-light);margin-bottom:20px;">{{ project.description || '' }}</p>
        <div class="stats-grid">
            <stat-card :value="project.resource_count" label="资源数" />
            <stat-card :value="project.avg_score" label="平均质量" />
            <stat-card :value="sourceCount" label="数据源" />
        </div>
        <div class="grid-3">
            <div class="card node-card" @click="goTo('graph')">
                <h2>知识图谱</h2>
                <p style="color:var(--text-light)">交互式知识图谱</p>
            </div>
            <div class="card node-card" @click="goTo('learning-path')">
                <h2>学习路径</h2>
                <p style="color:var(--text-light)">个性化学习路径</p>
            </div>
            <div class="card node-card" @click="goTo('concepts')">
                <h2>知识列表</h2>
                <p style="color:var(--text-light)">所有知识点</p>
            </div>
        </div>
        <div class="card" style="margin-top:16px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h2 style="margin:0;">资源列表</h2>
                <div>
                    <button class="btn btn-primary btn-sm" @click="collect" :disabled="collecting">
                        {{ collecting ? '采集中...' : '采集新资源' }}
                    </button>
                </div>
            </div>
            <table>
                <thead><tr><th>标题</th><th>来源</th><th>质量</th><th>难度</th></tr></thead>
                <tbody>
                    <tr v-for="r in resources.slice(0, 30)" :key="r.id">
                        <td><a :href="r.url" target="_blank">{{ r.title }}</a></td>
                        <td>{{ r.source }}</td>
                        <td :style="{ color: scoreColor(r.quality_score) }">{{ r.quality_score ? r.quality_score.toFixed(1) : '-' }}</td>
                        <td>{{ r.difficulty || '-' }}</td>
                    </tr>
                    <tr v-if="!resources.length"><td colspan="4" class="empty-state">暂无资源</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    <div v-else class="loading">加载中...</div>
    `,
    setup() {
        const route = useRoute()
        const router = useRouter()
        const project = ref(null)
        const resources = ref([])
        const collecting = ref(false)
        const sourceCount = computed(() => {
            const sources = project.value?.sources || {}
            return Object.keys(sources).length
        })

        async function load() {
            const pid = route.params.projectId
            try {
                project.value = await api.get('/projects/' + pid)
                currentProject.value = project.value
                resources.value = await api.get('/projects/' + pid + '/resources')
            } catch (e) {
                console.error(e)
            }
        }

        function goTo(page) {
            router.push('/projects/' + route.params.projectId + '/' + page)
        }

        async function collect() {
            collecting.value = true
            try {
                await api.post('/projects/' + route.params.projectId + '/collect', {})
                await load()
            } finally {
                collecting.value = false
            }
        }

        function scoreColor(s) {
            if (!s) return '#888'
            if (s >= 7) return '#2e7d32'
            if (s >= 5) return '#e65100'
            return '#c62828'
        }

        onMounted(load)
        return { project, resources, collecting, sourceCount, goTo, collect, scoreColor }
    },
}

const GraphPage = {
    template: `
    <div>
        <div class="graph-toolbar">
            <input v-model="searchQuery" placeholder="搜索节点..." class="search-input" />
            <select v-model="layoutName" class="layout-select">
                <option value="breadthfirst">层次布局</option>
                <option value="cose">力导向</option>
                <option value="circle">环形</option>
                <option value="grid">网格</option>
            </select>
        </div>
        <div ref="cyContainer" class="graph-container"></div>
        <div id="tooltip" v-show="tooltip.visible"
             :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
             class="graph-tooltip">
            <div class="tooltip-title">{{ tooltip.title }}</div>
            <div class="tooltip-meta">{{ tooltip.meta }}</div>
            <div class="tooltip-def">{{ tooltip.def }}</div>
        </div>
    </div>
    `,
    setup() {
        const route = useRoute()
        const router = useRouter()
        const cyContainer = ref(null)
        const searchQuery = ref('')
        const layoutName = ref('breadthfirst')
        const tooltip = ref({ visible: false, x: 0, y: 0, title: '', meta: '', def: '' })
        let cy = null

        const typeColors = {
            concept: '#3B82F6', technology: '#F59E0B', principle: '#10B981',
            practice: '#8B5CF6', project: '#EC4899', application: '#06B6D4',
        }

        async function loadGraph() {
            const pid = route.params.projectId
            try {
                const data = await api.get('/projects/' + pid + '/graph')
                currentProject.value = { id: pid, title: data.topic || '知识图谱' }
                initCytoscape(data.nodes, data.edges)
            } catch (e) {
                console.error('Failed to load graph:', e)
            }
        }

        function initCytoscape(nodes, edges) {
            // Dynamic import cytoscape
            const script = document.createElement('script')
            script.src = 'https://unpkg.com/cytoscape@3.28.0/dist/cytoscape.min.js'
            script.onload = () => {
                cy = cytoscape({
                    container: cyContainer.value,
                    elements: [
                        ...nodes.map(n => ({ data: { id: n.id, label: n.name, type: n.type, difficulty: n.difficulty, definition: (n.definition || '').substring(0, 80) } })),
                        ...edges.map(e => ({ data: { source: e.from, target: e.to, type: e.type, weight: e.weight, reason: e.reason || '' } })),
                    ],
                    style: [
                        { selector: 'node', style: { label: 'data(label)', 'background-color': el => typeColors[el.data('type')] || '#3B82F6', color: '#fff', 'text-valign': 'center', 'font-size': '11px', width: 36, height: 36, 'text-wrap': 'ellipsis', 'text-max-width': '80px' } },
                        { selector: 'node.highlighted', style: { 'border-width': 3, 'border-color': '#EF4444', width: 48, height: 48 } },
                        { selector: 'node.dimmed', style: { opacity: 0.2 } },
                        { selector: 'edge', style: { width: 1.5, 'line-color': '#94A3B8', 'target-arrow-color': '#94A3B8', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier' } },
                        { selector: 'edge[type="prerequisite"]', style: { 'line-color': '#EF4444', 'target-arrow-color': '#EF4444', 'line-style': 'dashed', width: 2 } },
                        { selector: 'edge.dimmed', style: { opacity: 0.1 } },
                    ],
                    layout: { name: 'breadthfirst', directed: true, spacingFactor: 1.5 },
                })

                cy.on('tap', 'node', evt => {
                    router.push('/projects/' + route.params.projectId + '/concepts/' + evt.target.id())
                })

                cy.on('mouseover', 'node', evt => {
                    const d = evt.target.data()
                    tooltip.value = { visible: true, x: 0, y: 0, title: d.label, meta: d.type + ' · ' + d.difficulty, def: d.definition || '' }
                })
                cy.on('mousemove', evt => {
                    tooltip.value.x = evt.originalEvent.clientX + 15
                    tooltip.value.y = evt.originalEvent.clientY + 15
                })
                cy.on('mouseout', 'node', () => { tooltip.value.visible = false })
            }
            document.head.appendChild(script)
        }

        watch(searchQuery, q => {
            if (!cy) return
            if (!q) { cy.elements().removeClass('highlighted dimmed'); return }
            cy.nodes().forEach(n => {
                const match = n.data('label').toLowerCase().includes(q.toLowerCase())
                n.toggleClass('highlighted', match)
                n.toggleClass('dimmed', !match)
            })
            cy.edges().addClass('dimmed')
            cy.edges().forEach(e => {
                if (e.source().hasClass('highlighted') || e.target().hasClass('highlighted')) e.removeClass('dimmed')
            })
        })

        watch(layoutName, name => {
            if (!cy) return
            cy.layout({ name, directed: name === 'breadthfirst', spacingFactor: 1.5, animate: true }).run()
        })

        onMounted(loadGraph)
        return { cyContainer, searchQuery, layoutName, tooltip }
    },
}

const LearningPathPage = {
    template: `
    <div v-if="pathData">
        <h1 class="page-title">学习路径</h1>
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <span class="text-sm">学习进度</span>
                <span class="text-sm" style="color:var(--text-light)">{{ doneCount }}/{{ pathData.total_steps }}</span>
            </div>
            <div class="progress-bar"><div class="fill" :style="{ width: progressPct + '%' }"></div></div>
        </div>

        <div v-for="(group, gName) in groupedSteps" :key="gName" class="phase-group">
            <div class="phase-header" @click="toggleGroup(gName)">
                <span><span class="dot" :class="'dot-' + group.color"></span> {{ gName }} ({{ group.steps.length }} 个)</span>
                <span>{{ expandedGroups[gName] ? '▼' : '▶' }}</span>
            </div>
            <div class="phase-steps" v-show="expandedGroups[gName]">
                <div v-for="step in group.steps" :key="step.concept" class="step-item">
                    <input type="checkbox" :checked="progress[step.concept]" @change="toggleStep(step.concept)" />
                    <div style="flex:1">
                        <router-link :to="'/projects/' + projectId + '/concepts/' + step.concept" class="step-link">
                            {{ step.name || step.concept }}
                        </router-link>
                        <badge v-if="step.priority === 'high'" text="优先" variant="red" style="margin-left:8px" />
                        <badge :text="step.difficulty" :variant="diffVariant(step.difficulty)" style="margin-left:4px" />
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div v-else class="loading">加载中...</div>
    `,
    setup() {
        const route = useRoute()
        const pathData = ref(null)
        const progress = ref({})
        const expandedGroups = ref({})

        const projectId = computed(() => route.params.projectId)

        const doneCount = computed(() => Object.keys(progress.value).length)
        const progressPct = computed(() => {
            const total = pathData.value?.total_steps || 1
            return Math.round(doneCount.value / total * 100)
        })

        const groupedSteps = computed(() => {
            const steps = pathData.value?.steps || []
            const groups = { '入门': [], '基础': [], '进阶': [], '高级': [] }
            for (const step of steps) {
                const diff = step.difficulty || 'intermediate'
                if (diff === 'beginner') groups['入门'].push(step)
                else if (diff === 'advanced') groups['高级'].push(step)
                else if ((step.importance || 0.5) >= 0.5) groups['进阶'].push(step)
                else groups['基础'].push(step)
            }
            const result = {}
            const colors = { '入门': 'green', '基础': 'blue', '进阶': 'amber', '高级': 'red' }
            for (const [name, steps] of Object.entries(groups)) {
                if (steps.length) {
                    result[name] = { steps, color: colors[name] }
                    if (expandedGroups.value[name] === undefined) expandedGroups.value[name] = true
                }
            }
            return result
        })

        function diffVariant(d) {
            return { beginner: 'green', intermediate: 'yellow', advanced: 'red' }[d] || 'gray'
        }

        function toggleGroup(name) {
            expandedGroups.value[name] = !expandedGroups.value[name]
        }

        function toggleStep(cid) {
            if (progress.value[cid]) delete progress.value[cid]
            else progress.value[cid] = Date.now()
            localStorage.setItem('openlearning_progress', JSON.stringify(progress.value))
        }

        async function load() {
            const pid = route.params.projectId
            try {
                pathData.value = await api.get('/projects/' + pid + '/learning-path')
                currentProject.value = { id: pid, title: '学习路径' }
                progress.value = JSON.parse(localStorage.getItem('openlearning_progress') || '{}')
            } catch (e) {
                console.error(e)
            }
        }

        onMounted(load)
        return { pathData, progress, expandedGroups, projectId, doneCount, progressPct, groupedSteps, diffVariant, toggleGroup, toggleStep }
    },
}

const ConceptsPage = {
    template: `
    <div>
        <h1 class="page-title">知识列表</h1>
        <div class="search-bar">
            <input v-model="searchQuery" placeholder="搜索知识点..." />
        </div>
        <div class="filter-pills">
            <button class="filter-pill" :class="{ active: typeFilter === 'all' }" @click="typeFilter = 'all'">全部类型</button>
            <button v-for="t in types" :key="t" class="filter-pill" :class="{ active: typeFilter === t }" @click="typeFilter = t">{{ t }}</button>
        </div>
        <div class="filter-pills" style="margin-top:8px;">
            <button class="filter-pill" :class="{ active: diffFilter === 'all' }" @click="diffFilter = 'all'">全部难度</button>
            <button v-for="d in diffs" :key="d" class="filter-pill" :class="{ active: diffFilter === d }" @click="diffFilter = d">{{ d }}</button>
        </div>
        <p style="color:var(--text-light);margin:12px 0;">{{ filtered.length }} 个知识点</p>
        <div class="node-grid">
            <node-card v-for="node in filtered" :key="node.id" :node="node" />
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
        const searchQuery = ref('')
        const typeFilter = ref('all')
        const diffFilter = ref('all')

        const types = computed(() => [...new Set(concepts.value.map(c => c.type))].sort())
        const diffs = computed(() => [...new Set(concepts.value.map(c => c.difficulty))].sort())

        const filtered = computed(() => {
            let list = concepts.value
            if (typeFilter.value !== 'all') list = list.filter(c => c.type === typeFilter.value)
            if (diffFilter.value !== 'all') list = list.filter(c => c.difficulty === diffFilter.value)
            if (searchQuery.value) {
                const q = searchQuery.value.toLowerCase()
                list = list.filter(c => c.name.toLowerCase().includes(q) || (c.definition || '').toLowerCase().includes(q))
            }
            return list.sort((a, b) => (b.importance || 0.5) - (a.importance || 0.5))
        })

        async function load() {
            const pid = route.params.projectId
            try {
                concepts.value = await api.get('/projects/' + pid + '/concepts')
                // Load project info
                const p = await api.get('/projects/' + pid)
                currentProject.value = p
            } catch (e) {
                console.error(e)
            }
        }

        onMounted(load)
        return { concepts, searchQuery, typeFilter, diffFilter, types, diffs, filtered }
    },
}

const ConceptDetailPage = {
    template: `
    <div v-if="node">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
            <h1 class="page-title" style="margin:0">{{ node.name }}</h1>
            <badge :text="node.type" variant="blue" />
            <badge :text="node.difficulty" :variant="diffVariant" />
            <span class="stars">{{ stars }}</span>
        </div>

        <div class="card" v-if="node.definition">
            <h2>📖 定义</h2>
            <p>{{ node.definition }}</p>
        </div>

        <div class="card" v-if="node.explanation">
            <h2>💡 详解</h2>
            <p v-for="(p, i) in explanationParagraphs" :key="i" style="margin-bottom:12px;">{{ p }}</p>
        </div>

        <div class="card" v-if="node.key_points && node.key_points.length">
            <h2>🎯 关键要点</h2>
            <ul>
                <li v-for="(p, i) in flatList(node.key_points)" :key="i">{{ p }}</li>
            </ul>
        </div>

        <div class="card" v-if="node.examples && node.examples.length">
            <h2>🔧 实例</h2>
            <div v-for="(e, i) in flatList(node.examples)" :key="i" style="margin-bottom:8px;">▸ {{ e }}</div>
        </div>

        <div class="card" v-if="node.common_mistakes && node.common_mistakes.length">
            <h2>⚠️ 常见误区</h2>
            <ul>
                <li v-for="(m, i) in flatList(node.common_mistakes)" :key="i">⚠ {{ m }}</li>
            </ul>
        </div>

        <div class="card" v-if="node.learning_tips" style="border-left:4px solid var(--primary);">
            <h2>💡 学习建议</h2>
            <p style="font-style:italic;">{{ node.learning_tips }}</p>
        </div>

        <div class="card" v-if="detail.prerequisites && detail.prerequisites.length">
            <h2>📋 前置知识</h2>
            <div class="link-group">
                <router-link v-for="p in detail.prerequisites" :key="p.id"
                    :to="'/projects/' + projectId + '/concepts/' + p.id"
                    class="link-tag link-red">
                    {{ p.name }} <span v-if="p.reason" class="link-reason">({{ p.reason }})</span>
                </router-link>
            </div>
        </div>

        <div class="card" v-if="detail.extends && detail.extends.length">
            <h2>🚀 进阶方向</h2>
            <div class="link-group">
                <router-link v-for="e in detail.extends" :key="e.id"
                    :to="'/projects/' + projectId + '/concepts/' + e.id"
                    class="link-tag link-green">
                    {{ e.name }}
                </router-link>
            </div>
        </div>

        <div class="card" v-if="detail.related && detail.related.length">
            <h2>🔗 相关概念</h2>
            <div class="link-group">
                <router-link v-for="r in detail.related" :key="r.id"
                    :to="'/projects/' + projectId + '/concepts/' + r.id"
                    class="link-tag link-blue">
                    {{ r.name }}
                </router-link>
            </div>
        </div>

        <div class="card" v-if="detail.resources && detail.resources.length">
            <h2>📚 推荐资源</h2>
            <div v-for="r in detail.resources" :key="r.url" class="resource-item">
                <a :href="r.url" target="_blank">{{ r.title || r.url }}</a>
                <span v-if="r.source" class="badge badge-gray" style="margin-left:8px;">{{ r.source }}</span>
            </div>
        </div>
    </div>
    <div v-else class="loading">加载中...</div>
    `,
    setup() {
        const route = useRoute()
        const node = ref(null)
        const detail = ref({})

        const projectId = computed(() => route.params.projectId)

        const diffVariant = computed(() => {
            const map = { beginner: 'green', intermediate: 'yellow', advanced: 'red' }
            return map[node.value?.difficulty] || 'gray'
        })

        const stars = computed(() => {
            const s = Math.round((node.value?.importance || 0.5) * 5)
            return '★'.repeat(s) + '☆'.repeat(5 - s)
        })

        const explanationParagraphs = computed(() => {
            return (node.value?.explanation || '').split('\n').filter(p => p.trim())
        })

        function flatList(items) {
            if (!items) return []
            return items.flat().filter(Boolean)
        }

        async function load() {
            const pid = route.params.projectId
            const cid = route.params.conceptId
            try {
                const data = await api.get('/projects/' + pid + '/concepts/' + cid)
                node.value = data.node
                detail.value = data
                currentProject.value = { id: pid, title: data.node?.name || '概念详情' }
            } catch (e) {
                console.error(e)
            }
        }

        watch(() => route.params.conceptId, load)
        onMounted(load)
        return { node, detail, projectId, diffVariant, stars, explanationParagraphs, flatList }
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
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

// ── App ──────────────────────────────────────────────────────

const app = createApp({
    template: `
    <div class="app-layout">
        <navbar />
        <div class="main-content">
            <router-view />
        </div>
    </div>
    `,
})

app.component('navbar', Navbar)
app.component('stat-card', StatCard)
app.component('badge', Badge)
app.component('node-card', NodeCard)
app.use(router)
app.mount('#app')
