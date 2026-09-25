---
page_family: site
title: "Privacy"
page_role: "What Entelim stores, plainly, matched to the models and settings in the codebase."
source: app/models/user.py, app/models/waitlist_signup.py, app/main/views.py (waitlist form),
  .env.example (mail/AI provider settings), read 2026-09-25
---

# Privacy

## What we collect

**Your account.** If you create an account, we store your name, email address, and a salted hash of
your password — never the password itself.

**What you and your team enter.** Everything you record in your organisation's model — applications,
risks, roadmaps and the rest of what Entelim covers — is stored so it can answer your questions. It
belongs to your organisation and is scoped to it; other organisations on the same instance cannot
read it.

**The waiting list.** If you join the waiting list from the home page, we store your email address
and the fact that you agreed to it, and use it only to tell you about the Entelim launch.

## What we don't do

Entelim does not load third-party advertising trackers or analytics scripts on its public pages. No
data from your organisation's model is sent to a third party unless you connect one yourself, for
example by adding your own AI provider key for the AI chat features, or by configuring an
integration you choose to enable.

## Email and AI providers

If email is configured (for password resets and notifications), it goes through the mail provider
the operator of that instance has set up. AI features call the AI provider whose key the operator
has configured; if none is configured, those features are unavailable rather than silently using a
default provider.

## If you self-host

Running Entelim yourself means your data stays on your own infrastructure end to end. Nothing about
what you store is sent anywhere Entelim's maintainers can see, unless you choose to send it.

## Removing your data

To close an account and remove its data, or ask what we hold about you, [get in touch](/contact). If
you self-host, you already control the database directly.
