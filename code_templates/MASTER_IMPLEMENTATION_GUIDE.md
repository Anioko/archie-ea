# 🎯 MASTER IMPLEMENTATION GUIDE
**Architecture Assistant - Phase 1 Complete Code Package**

---

## 📚 TABLE OF CONTENTS

1. [Quick Start](#quick-start)
2. [Complete File Inventory](#complete-file-inventory)
3. [Week-by-Week Implementation](#week-by-week-implementation)
4. [Code Quality Standards](#code-quality-standards)
5. [Testing Strategy](#testing-strategy)
6. [Deployment Guide](#deployment-guide)
7. [Troubleshooting](#troubleshooting)

---

## 🚀 QUICK START

### Prerequisites
```bash
# Python 3.9+
python --version

# PostgreSQL 13+
psql --version

# Redis 6+
redis-cli --version

# Git
git --version
```

### Installation (5 minutes)
```bash
# 1. Clone and navigate
git clone <repo-url>
cd archie

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install all dependencies
pip install -r requirements.txt
pip install -r requirements-phase1.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env with your values:
#   OPENAI_API_KEY=sk-...
#   DATABASE_URL=postgresql://...
#   REDIS_URL=redis://localhost:6379/0

# 5. Initialize database
flask db upgrade

# 6. Seed permissions
python scripts/sprint_1_1_seed_permissions.py

# 7. Run application
python run.py
```

### Verify Installation
```bash
# Run tests
pytest tests/ -v

# Check coverage
pytest --cov=app --cov-report=html

# Access application
open http://localhost:5000
```

---

## 📦 COMPLETE FILE INVENTORY

### Code Templates (15 files, ~5000 lines)

#### Sprint 1.1: Authentication (3 files)
- `sprint_1_1_auth_decorators.py` (250 lines)
  - @login_required decorator
  - @requires_permission decorator
  - @requires_any_permission decorator
  - @set_tenant_context decorator

- `sprint_1_1_permission_model.py` (180 lines)
  - Permission model
  - Role model
  - RolePermission model
  - UserRole model
  - User model extensions

- `sprint_1_1_seed_permissions.py` (220 lines)
  - 30+ permission definitions
  - 6 predefined roles
  - Seeding logic
  - Multi-tenant support

#### Sprint 1.2: Multi-Tenancy (2 files)
- `sprint_1_2_migration_add_tenant_id.py` (150 lines)
  - Add tenant_id to 10+ tables
  - Foreign key constraints
  - Indexes for performance
  - Upgrade/downgrade logic

- `sprint_1_2_service_update_example.py` (350 lines)
  - Service layer patterns
  - Tenant filtering examples
  - Query optimization
  - Security best practices

#### Sprint 1.3: Security (2 files)
- `sprint_1_3_rate_limiter.py` (150 lines)
  - Flask-Limiter configuration
  - Tiered rate limits (AI/medium/light)
  - Redis backend
  - Error handling

- `sprint_1_3_input_validators.py` (400 lines)
  - Marshmallow schemas (5 schemas)
  - HTML sanitization
  - SQL injection prevention
  - XSS protection

#### Sprint 1.4: LLM Integration (3 files)
- `sprint_1_4_openai_service.py` (350 lines)
  - OpenAI client wrapper
  - Token counting
  - Cost estimation
  - Usage tracking
  - Error handling & retries

- `sprint_1_4_prompt_templates.py` (500 lines)
  - Gap analysis prompt
  - Option generation prompt
  - ARB draft prompt
  - ADR generation prompt
  - Prompt builder functions

- `sprint_1_4_llm_usage_model.py` (150 lines)
  - LLMUsage model
  - Analytics queries
  - Cost reporting
  - Performance metrics

#### Sprint 1.5: ADR Generation (3 files)
- `sprint_1_5_adr_models.py` (200 lines)
  - ArchitectureDecisionRecord model
  - Nygard format support
  - Status workflow
  - Related ADRs linking

- `sprint_1_5_adr_service.py` (300 lines)
  - LLM-powered ADR generation
  - Context extraction
  - Export to Markdown
  - Export to PDF (future)

- `sprint_1_5_adr_routes.py` (150 lines)
  - POST /api/adr/generate
  - GET /api/adr/:id
  - GET /api/adr/:id/export
  - GET /api/adr/

#### Sprint 1.6: Enhanced Scoring (2 files)
- `sprint_1_6_enhanced_scoring_model.py` (450 lines)
  - SolutionScoring model (12+ criteria)
  - VendorViabilityAssessment model
  - Composite score calculation
  - Weight customization

- `sprint_1_6_enhanced_scoring_service.py` (400 lines)
  - Multi-criteria scoring logic
  - LLM-powered strategic scoring
  - Vendor viability assessment
  - Option comparison

#### Documentation (2 files)
- `README.md` (1300 lines)
  - Installation guide
  - Usage examples
  - API documentation
  - Architecture overview

- `FINAL_SUMMARY.md` (1000 lines)
  - Implementation roadmap
  - Success criteria
  - Troubleshooting
  - FAQ

---

## 📅 WEEK-BY-WEEK IMPLEMENTATION

### Week 1: Security Foundation

#### Monday: Authentication Setup
- [ ] Install Flask-Login, Flask-Principal
- [ ] Copy permission model
- [ ] Run migration
- [ ] Seed permissions
- [ ] Test: User can login

#### Tuesday: Add Auth to Routes
- [ ] Copy auth decorators
- [ ] Add @login_required to all 6+ routes
- [ ] Add @requires_permission
- [ ] Test: Unauthorized access returns 401

#### Wednesday: Multi-Tenancy Migration
- [ ] Copy migration file
- [ ] Update revision IDs
- [ ] Run migration
- [ ] Verify tenant_id on all models
- [ ] Test: Data isolated by tenant

#### Thursday: Update Service Layer
- [ ] Add tenant_id to all service methods
- [ ] Update queries with tenant filtering
- [ ] Test: Cross-tenant access blocked

#### Friday: Security Testing
- [ ] Write 20+ security tests
- [ ] Run security audit
- [ ] Fix issues
- [ ] Document security model
- [ ] **Week 1 Demo**

### Week 2: AI & Security Hardening

#### Monday: Rate Limiting
- [ ] Install Flask-Limiter, Redis
- [ ] Copy rate limiter code
- [ ] Configure limits (10/30/100)
- [ ] Test: Rate limit enforcement

#### Tuesday: Input Validation
- [ ] Install Marshmallow, Bleach
- [ ] Copy validation schemas
- [ ] Add to all POST endpoints
- [ ] Test: Invalid input rejected

#### Wednesday: OpenAI Integration
- [ ] Install openai, tiktoken
- [ ] Copy OpenAI service
- [ ] Set API key
- [ ] Test: Basic completion works

#### Thursday: LLM Usage Tracking
- [ ] Copy LLM usage model
- [ ] Run migration
- [ ] Integrate tracking
- [ ] Test: Usage logged correctly

#### Friday: Prompt Templates
- [ ] Copy prompt templates
- [ ] Test each prompt type
- [ ] Optimize for quality
- [ ] **Week 2 Demo**

### Week 3: ADR Feature (Part 1)

#### Monday-Tuesday: ADR Models
- [ ] Copy ADR model
- [ ] Run migration
- [ ] Test: Create ADR manually
- [ ] Verify sequential numbering

#### Wednesday-Thursday: ADR Service
- [ ] Copy ADR service
- [ ] Implement LLM generation
- [ ] Test: Generate ADR from session
- [ ] Verify quality of output

#### Friday: ADR Export
- [ ] Implement Markdown export
- [ ] Test: Download ADR.md
- [ ] **Week 3 Demo**

### Week 4: Enhanced Scoring & Polish

#### Monday-Tuesday: Scoring Models
- [ ] Copy enhanced scoring model
- [ ] Run migration
- [ ] Test: Score calculation

#### Wednesday: Scoring Service
- [ ] Copy scoring service
- [ ] Integrate LLM scoring
- [ ] Test: 12-criteria scoring

#### Thursday: Integration & Testing
- [ ] End-to-end testing
- [ ] Performance testing
- [ ] Bug fixes

#### Friday: Phase 1 Completion
- [ ] Final testing
- [ ] Documentation
- [ ] **Phase 1 Demo to Stakeholders**
- [ ] **Go/No-Go for Phase 2**

---

## ✅ CODE QUALITY STANDARDS

### Python Code Style
- PEP 8 compliant
- Type hints on all functions
- Docstrings (Google style)
- Max line length: 100
- Use Black formatter

### Git Workflow
```bash
# Feature branch naming
git checkout -b sprint-1.1/add-authentication

# Commit messages
git commit -m "feat(auth): Add @login_required decorator

- Implement login_required decorator
- Add custom error handling
- Return 401 JSON response
- Add unit tests

Refs: #123"

# Pull request
- Title: [Sprint 1.1] Add Authentication System
- Description: Comprehensive PR template
- Reviewers: Assign 2+ reviewers
- Tests: All passing
```

### Code Review Checklist
- [ ] All tests passing
- [ ] Coverage >= 80% for new code
- [ ] No security vulnerabilities
- [ ] Type hints present
- [ ] Docstrings complete
- [ ] No console.log / debug prints
- [ ] Error handling present
- [ ] Performance acceptable

---

## 🧪 TESTING STRATEGY

### Test Coverage Targets
- Unit tests: 80%+
- Integration tests: 60%+
- E2E tests: Critical paths only
- Security tests: 100% of auth/authz

### Running Tests
```bash
# All tests
pytest

# Specific sprint
pytest tests/unit/test_sprint_1_1_auth.py

# With coverage
pytest --cov=app --cov-report=html

# Only security tests
pytest -m security

# Fast tests only
pytest -m "not slow"
```

### Test Structure
```
tests/
├── unit/
│   ├── test_auth_decorators.py
│   ├── test_permission_model.py
│   ├── test_llm_service.py
│   └── test_scoring_service.py
├── integration/
│   ├── test_authentication_flow.py
│   ├── test_adr_generation.py
│   └── test_scoring_workflow.py
└── e2e/
    └── test_complete_session.py
```

---

## 🚀 DEPLOYMENT GUIDE

### Environment Setup
```bash
# Production environment variables
export FLASK_ENV=production
export OPENAI_API_KEY=sk-prod-...
export DATABASE_URL=postgresql://prod-db
export REDIS_URL=redis://prod-redis:6379/0
export SECRET_KEY=<strong-random-key>
```

### Database Migration (Production)
```bash
# Backup first!
pg_dump production_db > backup-$(date +%Y%m%d).sql

# Run migration
flask db upgrade

# Verify
flask db current

# Rollback if needed
flask db downgrade
```

### Deployment Checklist
- [ ] Environment variables set
- [ ] Database backup created
- [ ] Migrations tested in staging
- [ ] Security audit passed
- [ ] Load testing completed
- [ ] Monitoring configured
- [ ] Error tracking enabled
- [ ] Rollback plan documented

---

## 🆘 TROUBLESHOOTING

### Common Issues

**"ImportError: No module named 'app.auth.decorators'"**
```bash
# Ensure directory structure
mkdir -p app/auth
touch app/auth/__init__.py
cp code_templates/sprint_1_1_auth_decorators.py app/auth/decorators.py
```

**"OPENAI_API_KEY not configured"**
```bash
# Set in environment
export OPENAI_API_KEY="sk-..."

# Or in .env file
echo "OPENAI_API_KEY=sk-..." >> .env
```

**"Migration conflict detected"**
```bash
# Find latest migration
flask db current

# Update down_revision in new migration
# Edit migrations/versions/XXXX_add_tenant_id.py
# Change: down_revision = '<latest-revision-id>'

# Try again
flask db upgrade
```

**"Rate limit exceeded immediately"**
```python
# Increase limits in rate_limiter.py
AI_HEAVY_LIMIT = "20 per minute"  # Was 10
MEDIUM_LIMIT = "60 per minute"     # Was 30

# Or check Redis connection
redis-cli ping  # Should return PONG
```

---

## 🎯 SUCCESS METRICS

Track these metrics weekly:

| Metric | Week 1 | Week 2 | Week 3 | Week 4 |
|--------|--------|--------|--------|--------|
| Endpoints secured | 50% | 100% | 100% | 100% |
| Test coverage | 45% | 55% | 65% | 70% |
| Security tests | 10 | 25 | 35 | 45 |
| LLM integration | 0% | 100% | 100% | 100% |
| ADR generation | 0% | 0% | 80% | 100% |
| Enhanced scoring | 0% | 0% | 0% | 100% |

---

## 🎓 ADDITIONAL RESOURCES

- **Flask Documentation:** https://flask.palletsprojects.com/
- **SQLAlchemy ORM:** https://docs.sqlalchemy.org/
- **OpenAI API:** https://platform.openai.com/docs/
- **TOGAF:** https://www.opengroup.org/togaf
- **ADR Best Practices:** https://adr.github.io/

---

## ✅ YOU'RE READY!

**All code templates created ✅**
**All documentation complete ✅**
**Implementation plan ready ✅**

**Start Phase 1 NOW!** 🚀
