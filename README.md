<!--
Canonical description (use verbatim on every surface — repo About, PyPI, docs, blog, social):
"Archie is an open-source, AI-native enterprise architecture platform for TOGAF 9.2 and
ArchiMate 3.2 — model your application portfolio, run an AI-assisted solution-design
journey, and govern designs through an Architecture Review Board (ARB)."
-->

# Archie — Open-Source Enterprise Architecture Platform (TOGAF 9.2 · ArchiMate 3.2)

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Commercial license available](https://img.shields.io/badge/Commercial%20license-available-success.svg)](COMMERCIAL-LICENSE.md)

**Archie is an open-source, AI-native enterprise architecture platform for TOGAF 9.2 and
ArchiMate 3.2** — model your application portfolio, run an AI-assisted solution-design
journey, and govern designs through an **Architecture Review Board (ARB)**.

> **Archie vs Archi:** [Archi](https://www.archimatetool.com/) gives you ArchiMate
> *diagrams* on the desktop. **Archie** gives you a *governed, AI-driven, web-based
> enterprise architecture* — portfolio, capabilities, vendors, an ARB workflow, and an
> AI architect — and it's open source. If you've searched for an **open-source LeanIX or
> Ardoq alternative**, this is it.

---

## Why Archie

The open-source EA landscape has one well-known tool — Archi — and it's a desktop
*diagram editor*. Everything with governance, an application portfolio, and AI
(LeanIX, Ardoq, Bizzdesign, Sparx, MEGA) is expensive proprietary SaaS. **Archie is the
first open-source, web-based, AI-assisted, governed EA platform.**

| | Archie | Archi | LeanIX / Ardoq / Bizzdesign |
|---|:---:|:---:|:---:|
| Open source | ✅ AGPL-3.0 | ✅ | ❌ |
| Web-based / collaborative | ✅ | ❌ desktop | ✅ |
| ArchiMate 3.2 | ✅ | ✅ | ✅ |
| TOGAF ADM workflow | ✅ | partial | ✅ |
| Application portfolio mgmt | ✅ | ❌ | ✅ |
| Architecture Review Board (ARB) governance | ✅ | ❌ | partial |
| AI architect / design assistant | ✅ | ❌ | partial |
| Self-hostable | ✅ | ✅ | ❌ |

## Features

- **ArchiMate 3.2** across all layers (Strategy, Business, Application, Technology,
  Physical, Motivation, Implementation).
- **TOGAF-aligned solution-design journey** — capture drivers, goals, constraints,
  requirements, risks and options; link real applications, vendors and capabilities.
- **Architecture Review Board (ARB) governance** — maturity scoring, a readiness gate,
  and a submit-to-ARB workflow with an audit trail.
- **AI architect ("Archi")** — clarifies the problem, generates candidate architectures,
  and flags risks, grounded in *your* portfolio data.
- **Application Portfolio Management** — rationalization, dependencies, lifecycle.

## Open source vs. Commercial

Archie's **core is free and open source (AGPL-3.0)** — self-host it forever. When you need
to *not* run it yourself, or need enterprise features, there are two hosted products built
on Archie:

| | **Archie** (this repo) | **ReqArchitect** (hosted EA) | **Archiet** (spec→code) |
|---|---|---|---|
| What | Self-hosted EA platform | Managed multi-tenant EA SaaS, SSO, real-time collaboration, premium AI, connectors | PRD → production code across 12+ stacks + 7 compliance frameworks |
| For | Architects who self-host | Enterprises that want governed EA without ops | Founders/CTOs shipping compliant apps |
| Link | — | **[reqarchitect.com](https://reqarchitect.com)** | **[archiet.com](https://archiet.com)** |

Need to embed Archie in a proprietary product or offer it as a service without AGPL
obligations? A **[commercial license](COMMERCIAL-LICENSE.md)** is available.

## Quick start

```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # set SECRET_KEY, DATABASE_URL, admin creds
python manage.py create-db      # schema via db.create_all (no migrations needed)
python create_admin.py          # first admin user from .env
flask run                       # or: gunicorn -c gunicorn.conf.py "app:create_app()"
```

Open http://127.0.0.1:5000 and sign in. Ships with an empty schema and synthetic demo
data — **no customer data**.

## FAQ

**Is there an open-source LeanIX / Ardoq alternative?**
Yes — Archie is an open-source, web-based enterprise architecture platform with
application portfolio management, ArchiMate 3.2 and ARB governance.

**How is Archie different from Archi?**
Archi is a desktop ArchiMate *diagram* editor. Archie is a *governed, AI-driven,
web-based EA platform* (portfolio, ARB workflow, AI architect) — and open source.

**Does Archie support TOGAF and ArchiMate?**
Yes — ArchiMate 3.2 across all layers, with a TOGAF-aligned ADM solution-design journey
and an Architecture Review Board governance workflow.

**Can I use it commercially?**
Yes, under AGPL-3.0. To avoid AGPL's copyleft obligations (embedding in a proprietary
product, offering it as a hosted service), buy a [commercial license](COMMERCIAL-LICENSE.md).

## Stack
Python / Flask · PostgreSQL (SQLAlchemy, `db.create_all`) · Tailwind / shadcn-style UI ·
optional LLM providers for the AI assistant · optional Abacus/Avolution portfolio connector.

## License
**AGPL-3.0** — see [`LICENSE`](LICENSE). A **[commercial license](COMMERCIAL-LICENSE.md)**
is available for closed-source/SaaS use. © Anioko.

---
*Topics: `enterprise-architecture` `togaf` `archimate` `ea` `architecture-governance`
`application-portfolio-management` `leanix-alternative` `ardoq-alternative` `archimate-3-2`
`togaf-9-2` `ai-architect`*
