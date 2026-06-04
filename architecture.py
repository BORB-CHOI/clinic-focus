import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe

fig = plt.figure(figsize=(22, 16), facecolor='#0f172a')
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 22)
ax.set_ylim(0, 16)
ax.axis('off')
ax.set_facecolor('#0f172a')

# ── colour palette ───────────────────────────────────────────────────────────
C = {
    'fe':       '#0ea5e9',   # sky
    'be':       '#8b5cf6',   # violet
    'ai':       '#f59e0b',   # amber
    'dynamo':   '#10b981',   # emerald
    's3':       '#10b981',
    'bedrock':  '#f97316',   # orange
    'cloudfront':'#0ea5e9',
    'user':     '#64748b',
    'arrow':    '#94a3b8',
    'signal':   '#f43f5e',   # rose
    'border':   '#1e293b',
    'panel':    '#1e293b',
    'white':    '#f8fafc',
    'muted':    '#94a3b8',
    'heading':  '#e2e8f0',
    'tag':      '#334155',
}

def box(ax, x, y, w, h, color, alpha=0.18, radius=0.35, lw=2):
    fc = matplotlib.colors.to_rgba(color, alpha)
    ec = matplotlib.colors.to_rgba(color, 0.85)
    rect = FancyBboxPatch((x, y), w, h,
                          boxstyle=f"round,pad=0,rounding_size={radius}",
                          facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3)
    ax.add_patch(rect)
    return rect

def label(ax, x, y, text, size=9, color=C['white'], weight='normal',
          ha='center', va='center', zorder=5):
    ax.text(x, y, text, fontsize=size, color=color, fontweight=weight,
            ha=ha, va=va, zorder=zorder,
            fontfamily='DejaVu Sans')

def arrow(ax, x1, y1, x2, y2, color=C['arrow'], lw=1.8, style='->', bidirectional=False):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                                connectionstyle='arc3,rad=0'),
                zorder=4)
    if bidirectional:
        ax.annotate('', xy=(x1, y1), xytext=(x2, y2),
                    arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                                    connectionstyle='arc3,rad=0'),
                    zorder=4)

def dashed_arrow(ax, x1, y1, x2, y2, color=C['arrow'], lw=1.4):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                linestyle='dashed',
                                connectionstyle='arc3,rad=0'),
                zorder=4)

def tag(ax, x, y, text, color, size=7.2):
    tw = len(text) * 0.063 + 0.22
    fc = matplotlib.colors.to_rgba(color, 0.22)
    ec = matplotlib.colors.to_rgba(color, 0.70)
    rect = FancyBboxPatch((x - tw/2, y - 0.13), tw, 0.28,
                          boxstyle="round,pad=0,rounding_size=0.10",
                          facecolor=fc, edgecolor=ec, linewidth=1, zorder=6)
    ax.add_patch(rect)
    ax.text(x, y + 0.01, text, fontsize=size, color=color,
            ha='center', va='center', zorder=7, fontfamily='DejaVu Sans')

# ═══════════════════════════════════════════════════════════════════════════════
# TITLE
# ═══════════════════════════════════════════════════════════════════════════════
label(ax, 11, 15.4, 'clinic-focus  ·  System Architecture',
      size=16, weight='bold', color=C['white'])
label(ax, 11, 14.95,
      'Hospital Search Service  —  "What a clinic actually focuses on"',
      size=9.5, color=C['muted'])

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION LABELS (left rail)
# ═══════════════════════════════════════════════════════════════════════════════
for txt, yc, col in [
    ('USER',    13.65, C['user']),
    ('FRONTEND',12.35, C['fe']),
    ('BACKEND', 10.50, C['be']),
    ('AI / RAG', 7.80, C['ai']),
    ('DATA',     4.45, C['dynamo']),
]:
    ax.text(0.25, yc, txt, fontsize=7, color=col, fontweight='bold',
            ha='center', va='center', rotation=90, zorder=5,
            fontfamily='DejaVu Sans')

# horizontal dividers
for y in [14.65, 13.0, 11.65, 8.85, 5.85]:
    ax.plot([0.55, 21.45], [y, y], color='#1e3a5f', lw=0.8, zorder=2)

# ═══════════════════════════════════════════════════════════════════════════════
# USER
# ═══════════════════════════════════════════════════════════════════════════════
box(ax, 8.5, 13.10, 5.0, 0.78, C['user'], alpha=0.22)
label(ax, 11.0, 13.49, '[ User / Browser ]', size=10, weight='bold', color=C['user'])
label(ax, 11.0, 13.20, 'Natural Language Search  |  Map-based Nearby Search', size=8.2, color=C['muted'])

# ═══════════════════════════════════════════════════════════════════════════════
# FRONTEND
# ═══════════════════════════════════════════════════════════════════════════════
box(ax, 1.0, 11.72, 19.8, 1.18, C['fe'], alpha=0.14)
label(ax, 2.5, 12.86, 'FRONTEND', size=8, weight='bold', color=C['fe'])

# S3 + CloudFront
box(ax, 1.2, 11.82, 3.5, 0.95, C['fe'], alpha=0.22, radius=0.2)
label(ax, 2.95, 12.56, 'S3 + CloudFront', size=8.5, weight='bold', color=C['fe'])
label(ax, 2.95, 12.30, 'Static Hosting  /  CDN', size=7.5, color=C['muted'])
label(ax, 2.95, 12.05, 'aws s3 sync  (manual deploy)', size=7, color=C['muted'])

# React App
box(ax, 4.9, 11.82, 5.4, 0.95, C['fe'], alpha=0.22, radius=0.2)
label(ax, 7.6, 12.58, 'React + Vite  (TypeScript)', size=8.5, weight='bold', color=C['fe'])
label(ax, 7.6, 12.32, 'Tailwind CSS  +  shadcn/ui  +  TanStack Query', size=7.5, color=C['muted'])
label(ax, 7.6, 12.08, 'React Router  |  fetch  (openapi-typescript)', size=7, color=C['muted'])

# Kakao Map
box(ax, 10.5, 11.82, 3.8, 0.95, C['fe'], alpha=0.22, radius=0.2)
label(ax, 12.4, 12.58, 'Kakao Map SDK', size=8.5, weight='bold', color=C['fe'])
label(ax, 12.4, 12.32, 'Map Embed  /  GPS  /  Radius Slider', size=7.5, color=C['muted'])
label(ax, 12.4, 12.08, '0.5 / 1 / 3 / 5 / 10 km  |  Confidence Marker', size=7, color=C['muted'])

# Key Pages
box(ax, 14.5, 11.82, 6.1, 0.95, C['fe'], alpha=0.22, radius=0.2)
label(ax, 17.55, 12.58, 'Key Pages', size=8.5, weight='bold', color=C['fe'])
label(ax, 17.55, 12.33, 'Search Result Cards  |  Hospital Detail (9 sections)', size=7.5, color=C['muted'])
label(ax, 17.55, 12.09, 'Confidence Badge  |  Source Tags  |  Feedback 1-tap', size=7, color=C['muted'])

# ═══════════════════════════════════════════════════════════════════════════════
# BACKEND  (EC2 — support account)
# ═══════════════════════════════════════════════════════════════════════════════
box(ax, 1.0, 8.92, 19.8, 2.58, C['be'], alpha=0.12)
label(ax, 2.5, 11.32, 'BACKEND  (EC2  —  Support Account)', size=8, weight='bold', color=C['be'])

# FastAPI
box(ax, 1.2, 9.02, 5.0, 1.80, C['be'], alpha=0.22, radius=0.2)
label(ax, 3.7, 10.65, 'FastAPI + uvicorn', size=8.5, weight='bold', color=C['be'])
label(ax, 3.7, 10.40, 'Python 3.11  /  Pydantic  /  boto3', size=7.5, color=C['muted'])
label(ax, 3.7, 10.15, 'GET /api/search', size=7.2, color='#a78bfa')
label(ax, 3.7, 9.95,  'GET /api/hospitals/{id}', size=7.2, color='#a78bfa')
label(ax, 3.7, 9.75,  'POST /api/feedback', size=7.2, color='#a78bfa')
label(ax, 3.7, 9.55,  'GET /api/search/nearby', size=7.2, color='#a78bfa')
label(ax, 3.7, 9.28,  'OpenAPI  →  openapi-typescript  (FE auto-gen)', size=7, color=C['muted'])

# Crawler
box(ax, 6.4, 9.02, 4.5, 1.80, C['be'], alpha=0.22, radius=0.2)
label(ax, 8.65, 10.65, 'Crawler  (EC2)', size=8.5, weight='bold', color=C['be'])
label(ax, 8.65, 10.40, 'httpx  +  BeautifulSoup4', size=7.5, color=C['muted'])
label(ax, 8.65, 10.15, 'Playwright  (JS rendering)', size=7.5, color=C['muted'])
label(ax, 8.65, 9.92,  '5~10 pages / hospital', size=7.2, color=C['muted'])
label(ax, 8.65, 9.68,  'robots.txt compliant', size=7.2, color=C['muted'])
label(ax, 8.65, 9.42,  'HTML + Image URLs → S3 raw store', size=7.2, color=C['muted'])
label(ax, 8.65, 9.18,  'SQS for heavy load distribution', size=7.2, color=C['muted'])

# Public API
box(ax, 11.1, 9.02, 4.0, 1.80, C['be'], alpha=0.22, radius=0.2)
label(ax, 13.1, 10.65, 'Public Data', size=8.5, weight='bold', color=C['be'])
label(ax, 13.1, 10.40, '(HIRA  심평원)', size=8, color='#a78bfa')
label(ax, 13.1, 10.15, 'Hospital Basic Info', size=7.5, color=C['muted'])
label(ax, 13.1, 9.92,  'Specialist License', size=7.5, color=C['muted'])
label(ax, 13.1, 9.68,  'Registered Medical Devices', size=7.5, color=C['muted'])
label(ax, 13.1, 9.42,  'Legal  /  Free  /  Public API', size=7.2, color=C['muted'])
label(ax, 13.1, 9.18,  'Cold-start complement', size=7.2, color=C['muted'])

# shared models
box(ax, 15.3, 9.02, 5.3, 1.80, C['be'], alpha=0.22, radius=0.2)
label(ax, 17.95, 10.65, 'shared/models.py', size=8.5, weight='bold', color=C['be'])
label(ax, 17.95, 10.40, 'Single Source of Truth  (Pydantic)', size=7.5, color=C['muted'])
label(ax, 17.95, 10.12, 'CrawlData  |  Classification', size=7.2, color='#fcd34d')
label(ax, 17.95, 9.90,  'HospitalDescription  |  SearchQuery', size=7.2, color='#fcd34d')
label(ax, 17.95, 9.68,  'FeedbackEntry  |  Confidence', size=7.2, color='#fcd34d')
label(ax, 17.95, 9.45,  'ImageAnalysisResult  |  ServicesAndDoctors', size=7.2, color='#fcd34d')
label(ax, 17.95, 9.20,  'BE + AI both import — no manual sync', size=7, color=C['muted'])

# ═══════════════════════════════════════════════════════════════════════════════
# AI / RAG  (EC2 — personal account  for  Bedrock / S3 Vectors / Textract)
# ═══════════════════════════════════════════════════════════════════════════════
box(ax, 1.0, 5.92, 19.8, 2.80, C['ai'], alpha=0.10)
label(ax, 2.8, 8.55, 'AI / RAG  (EC2 same process  —  Personal Account: Bedrock / S3 Vectors / Textract)',
      size=8, weight='bold', color=C['ai'])

# classify_hospital
box(ax, 1.2, 6.02, 4.6, 1.92, C['ai'], alpha=0.22, radius=0.2)
label(ax, 3.5, 7.76, 'classify_hospital()', size=8.5, weight='bold', color=C['ai'])
label(ax, 3.5, 7.50, '4-Signal Cross Validation', size=8, color=C['muted'])

signals = [
    ('Self-claim  25%',  '#fb923c'),
    ('Vision     30%',  '#a78bfa'),
    ('Blog       20%',  '#34d399'),
    ('Reviews    25%',  '#f472b6'),
]
for i, (s, c) in enumerate(signals):
    y = 7.22 - i * 0.22
    ax.plot([1.35, 1.55], [y, y], color=c, lw=2, zorder=6)
    ax.text(1.60, y, s, fontsize=7.2, color=c, va='center', zorder=6,
            fontfamily='DejaVu Sans')

label(ax, 3.5, 6.22, 'Spam Penalty  |  Confidence Score', size=7.2, color=C['muted'])

# generate_description  ⭐
box(ax, 6.0, 6.02, 4.8, 1.92, C['signal'], alpha=0.22, radius=0.2)
# star accent
ax.text(6.22, 7.85, '★', fontsize=12, color=C['signal'], va='center', zorder=7,
        fontfamily='DejaVu Sans')
label(ax, 8.4, 7.76, 'generate_description()', size=8.5, weight='bold', color=C['signal'])
label(ax, 8.4, 7.52, 'Core Output of Service', size=8, color=C['muted'])
label(ax, 8.4, 7.28, 'Bedrock Claude Sonnet 4.5', size=7.5, color='#fb923c')
label(ax, 8.4, 7.05, 'Natural Language Hospital Profile', size=7.2, color=C['muted'])
label(ax, 8.4, 6.82, '[site] [vision] [blog] [review]  citation tags', size=7.2, color=C['muted'])
label(ax, 8.4, 6.58, 'Agent-subject expression  (medical law)', size=7.2, color=C['muted'])
label(ax, 8.4, 6.32, 'one_line_summary  for search card', size=7.2, color=C['muted'])
label(ax, 8.4, 6.10, 'Weakness / excluded services  included', size=7.2, color=C['muted'])

# search_similar / RAG
box(ax, 11.0, 6.02, 4.3, 1.92, C['ai'], alpha=0.22, radius=0.2)
label(ax, 13.15, 7.76, 'search_similar()  RAG', size=8.5, weight='bold', color=C['ai'])
label(ax, 13.15, 7.52, 'S3 Vectors  QueryVectors', size=7.5, color=C['muted'])
label(ax, 13.15, 7.28, 'Titan Embed Text v2  (1024-dim)', size=7.5, color=C['muted'])
label(ax, 13.15, 7.02, 'Natural Language  +  Location', size=7.5, color=C['muted'])
label(ax, 13.15, 6.78, 'Haversine  radius filter', size=7.2, color=C['muted'])
label(ax, 13.15, 6.54, 'Meta filter: specialty / sido / confidence', size=7.2, color=C['muted'])
label(ax, 13.15, 6.28, 'find_related_hospitals  (same_focus / fills_gap)', size=7, color=C['muted'])

# Vision + OCR
box(ax, 15.5, 6.02, 5.1, 1.92, C['ai'], alpha=0.22, radius=0.2)
label(ax, 18.05, 7.76, 'analyze_images()  +  OCR', size=8.5, weight='bold', color=C['ai'])
label(ax, 18.05, 7.52, 'Bedrock Vision  (Claude Sonnet 4.5)', size=7.5, color=C['muted'])
label(ax, 18.05, 7.28, 'Device detection  |  Procedure classification', size=7.5, color=C['muted'])
label(ax, 18.05, 7.02, 'Cosmetic  vs  General  (% distribution)', size=7.5, color=C['muted'])
label(ax, 18.05, 6.78, 'Amazon Textract  (medical device cert OCR)', size=7.5, color=C['muted'])
label(ax, 18.05, 6.52, 'MAX_VISION_IMAGES=10  cost control', size=7.2, color=C['muted'])
label(ax, 18.05, 6.28, 'recompute_confidence()  feedback loop', size=7.2, color=C['muted'])

# ═══════════════════════════════════════════════════════════════════════════════
# DATA LAYER
# ═══════════════════════════════════════════════════════════════════════════════
box(ax, 1.0, 1.65, 19.8, 4.06, C['dynamo'], alpha=0.08)
label(ax, 3.0, 5.58, 'DATA LAYER', size=8, weight='bold', color=C['dynamo'])

# DynamoDB
box(ax, 1.2, 3.60, 5.8, 1.88, C['dynamo'], alpha=0.20, radius=0.2)
label(ax, 4.1, 5.32, 'DynamoDB  (Support Account)', size=8.5, weight='bold', color=C['dynamo'])
tables = ['Hospitals', 'Classifications', 'Signals',
          'Confidence', 'Feedback', 'ChangeHistory']
cols = [(1.35, 4.98), (1.35, 4.75), (1.35, 4.52),
        (4.10, 4.98), (4.10, 4.75), (4.10, 4.52)]
for (tx, ty), tname in zip(cols, tables):
    tag(ax, tx + len(tname)*0.042, ty, tname, C['dynamo'], size=7.2)
label(ax, 4.1, 4.28, 'GeoHash GSI  for location query', size=7.2, color=C['muted'])
label(ax, 4.1, 4.06, 'device_id + hospital_id  unique  (feedback dedup)', size=7.2, color=C['muted'])
label(ax, 4.1, 3.82, 'ChangeHistory: classification version tracking', size=7.2, color=C['muted'])

# S3 Raw
box(ax, 7.2, 3.60, 4.3, 1.88, C['s3'], alpha=0.20, radius=0.2)
label(ax, 9.35, 5.32, 'S3  Raw Store  (Support)', size=8.5, weight='bold', color=C['s3'])
label(ax, 9.35, 5.06, 'Crawled HTML  origin files', size=7.5, color=C['muted'])
label(ax, 9.35, 4.82, 'Hospital Images  (JPEG/PNG/WebP)', size=7.5, color=C['muted'])
label(ax, 9.35, 4.58, 'Bucket: {username}-clinic-focus-*', size=7.2, color=C['muted'])
label(ax, 9.35, 4.34, 'Versioned  /  us-east-1', size=7.2, color=C['muted'])
label(ax, 9.35, 4.08, 'FE build → S3 + CloudFront CDN', size=7.2, color=C['muted'])

# S3 Vectors
box(ax, 11.7, 3.60, 4.3, 1.88, C['bedrock'], alpha=0.20, radius=0.2)
label(ax, 13.85, 5.32, 'S3 Vectors  (Personal Account)', size=8.5, weight='bold', color=C['bedrock'])
label(ax, 13.85, 5.06, 'Hospital Embeddings  (1024-dim)', size=7.5, color=C['muted'])
label(ax, 13.85, 4.82, 'Titan Embed Text v2', size=7.5, color=C['muted'])
label(ax, 13.85, 4.58, 'Metadata: lat, lng, specialty,', size=7.2, color=C['muted'])
label(ax, 13.85, 4.38, '  primary_focus, confidence_score', size=7.2, color=C['muted'])
label(ax, 13.85, 4.14, 'PutVectors  /  QueryVectors', size=7.2, color=C['muted'])
label(ax, 13.85, 3.90, 'Index: hospital-index', size=7.2, color=C['muted'])

# Bedrock
box(ax, 16.2, 3.60, 4.4, 1.88, C['bedrock'], alpha=0.20, radius=0.2)
label(ax, 18.4, 5.32, 'Amazon Bedrock  (Personal)', size=8.5, weight='bold', color=C['bedrock'])
label(ax, 18.4, 5.06, 'Claude Sonnet 4.5', size=7.5, color=C['muted'])
label(ax, 18.4, 4.84, '  LLM  |  Vision  |  OCR assist', size=7.2, color=C['muted'])
label(ax, 18.4, 4.58, 'us.anthropic.claude-sonnet-4-5-', size=7.2, color=C['muted'])
label(ax, 18.4, 4.38, '  20250929-v1:0  (US inference)', size=7.2, color=C['muted'])
label(ax, 18.4, 4.14, 'Titan Embed Text v2  (1024-dim)', size=7.2, color=C['muted'])
label(ax, 18.4, 3.90, 'Textract  OCR  (device cert)', size=7.2, color=C['muted'])

# ── bottom band: team + account info ──────────────────────────────────────────
box(ax, 1.0, 1.65, 19.8, 1.75, '#0f172a', alpha=0.0)

# account split banner
box(ax, 1.2, 1.72, 8.7, 1.55, C['dynamo'], alpha=0.10, radius=0.2, lw=1)
label(ax, 5.55, 3.08, 'Support Account  (us-east-1)  —  IAM Role only, no Access Key',
      size=7.5, weight='bold', color=C['dynamo'])
label(ax, 5.55, 2.82, 'EC2 (t3.nano~medium)  ·  DynamoDB  ·  S3  ·  API Gateway  ·  CloudFront  ·  SQS  ·  SNS',
      size=7.2, color=C['muted'])
label(ax, 5.55, 2.58, 'Credentials: EC2 Instance Profile  (SafeInstanceProfile-{username})',
      size=7, color=C['muted'])
label(ax, 5.55, 2.35, 'No Docker / No CI-CD / No Auth / Manual Deploy',
      size=7, color=C['muted'])
label(ax, 5.55, 2.12, 'Evaluation PoC only  —  Not production infra',
      size=7, color=C['muted'])
label(ax, 5.55, 1.90, 'Branches: feat/* / fix/* / refactor/*  (direct main commit blocked)',
      size=7, color=C['muted'])

box(ax, 10.1, 1.72, 10.5, 1.55, C['bedrock'], alpha=0.10, radius=0.2, lw=1)
label(ax, 15.35, 3.08, 'Personal Account  (us-east-1)  —  AI / ML Services',
      size=7.5, weight='bold', color=C['bedrock'])
label(ax, 15.35, 2.82, 'Bedrock  ·  S3 Vectors  ·  Amazon Textract',
      size=7.2, color=C['muted'])
label(ax, 15.35, 2.58, 'Credentials: Personal AWS credentials  (separate boto3 client)',
      size=7, color=C['muted'])

# Team
label(ax, 15.35, 2.28, 'Team:  Choi Biseong (AI/RAG)  ·  Ha Jaewon (FE)  ·  Kim Kyeongjae (BE/Data)',
      size=7.2, color=C['muted'])
label(ax, 15.35, 2.05, 'Stack:  Python 3.11  ·  TypeScript  ·  boto3  ·  FastAPI  ·  React + Vite',
      size=7, color=C['muted'])
label(ax, 15.35, 1.84, 'Search: S3 Vectors RAG  +  Kakao Map  |  Confidence: 4-signal  cross-validation',
      size=7, color=C['muted'])

# ═══════════════════════════════════════════════════════════════════════════════
# ARROWS
# ═══════════════════════════════════════════════════════════════════════════════
# User → FE
arrow(ax, 11.0, 13.10, 11.0, 12.90, color=C['fe'], lw=2.0)

# FE ↔ BE (REST)
arrow(ax, 7.6, 11.72, 7.6, 11.65, color=C['fe'], lw=1.8, bidirectional=True)
ax.text(8.05, 11.68, 'REST', fontsize=7, color=C['muted'], va='center', zorder=5,
        fontfamily='DejaVu Sans')

# BE → AI (Python import, same process)
arrow(ax, 3.7, 9.02, 3.7, 8.94, color=C['be'], lw=1.8)
ax.text(4.15, 8.98, 'import', fontsize=7, color=C['muted'], va='center', zorder=5,
        fontfamily='DejaVu Sans')

# AI pipeline internal arrows
arrow(ax, 5.80, 7.0, 6.02, 7.0, color=C['signal'], lw=1.8)
arrow(ax, 10.80, 7.0, 11.02, 7.0, color=C['ai'], lw=1.8)
arrow(ax, 15.30, 7.0, 15.52, 7.0, color=C['ai'], lw=1.8)

# AI → DynamoDB
arrow(ax, 8.4, 6.02, 4.1, 5.48, color=C['ai'], lw=1.5)
# AI → S3 Vectors
arrow(ax, 13.15, 6.02, 13.85, 5.48, color=C['ai'], lw=1.5)
# AI → Bedrock
dashed_arrow(ax, 18.05, 6.02, 18.4, 5.48, color=C['bedrock'], lw=1.5)

# Crawler → S3 Raw
arrow(ax, 8.65, 9.02, 9.35, 5.48, color=C['be'], lw=1.4)
# Public API → DynamoDB
arrow(ax, 11.5, 9.02, 4.8, 5.48, color=C['be'], lw=1.4)

# BE → DynamoDB (CRUD)
arrow(ax, 3.7, 9.02, 3.0, 5.48, color=C['dynamo'], lw=1.5)

# ═══════════════════════════════════════════════════════════════════════════════
# LEGEND
# ═══════════════════════════════════════════════════════════════════════════════
legend_items = [
    (C['fe'],      'Frontend  (FE)'),
    (C['be'],      'Backend  (BE)  — Support Account'),
    (C['ai'],      'AI / RAG Module  — Personal Account'),
    (C['dynamo'],  'DynamoDB / S3  — Support Account'),
    (C['bedrock'], 'Bedrock / S3 Vectors  — Personal Account'),
    (C['signal'],  '★  Core Differentiator'),
]
lx, ly = 1.3, 1.42
for i, (col, txt) in enumerate(legend_items):
    xi = lx + i * 3.35
    dot = FancyBboxPatch((xi, ly - 0.08), 0.22, 0.18,
                         boxstyle="round,pad=0,rounding_size=0.06",
                         facecolor=matplotlib.colors.to_rgba(col, 0.8),
                         edgecolor='none', zorder=8)
    ax.add_patch(dot)
    ax.text(xi + 0.28, ly + 0.01, txt, fontsize=6.8, color=C['muted'],
            va='center', zorder=8, fontfamily='DejaVu Sans')

plt.savefig('/home/ec2-user/clinic-focus/architecture.png',
            dpi=180, bbox_inches='tight',
            facecolor='#0f172a', edgecolor='none')
print('saved: architecture.png')
