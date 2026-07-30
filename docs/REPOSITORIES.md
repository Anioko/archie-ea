# Repository topology and sync policy

Last verified: 2026-07-30.

Archie lives in three GitHub repositories. They are not interchangeable, and one
of them is public, so it matters which is which.

| Repository | Visibility | Role |
|---|---|---|
| `Anioko/archie-ea` | **PUBLIC** | The open-source distribution (AGPL-3.0). The **only** repo that is public. Must be kept up to date. |
| `saint-gobain-archie/archie-ea` | private | The company repository. Canonical for delivery, deployment and anything customer-specific. |
| `aniekanasuquookono-web/archie-ea` | public | **Being decommissioned.** A personal fork. Its content belongs in the two repos above. |

## Rules

1. **`Anioko/archie-ea` is the only public repository.** Anything pushed there is
   world-readable, permanently — assume it can never be truly deleted.
2. **`Anioko/archie-ea` must be kept updated.** It is the open-source release; a
   stale public repo is worse than no public repo.
3. **Never publish a `prod-live-snapshot-*` branch.** Those branches capture live
   production state, including working files that were never intended for
   release. They belong in `saint-gobain-archie` only.
4. **`aniekanasuquookono-web/archie-ea` must not accumulate new work.** Push to
   the company repo, and to the public repo for open-source content.
5. Before any push to the public repo, the secret scan must be green. See
   `.gitleaks.toml`; it narrows verified false positives only and must never be
   used to silence a real credential.

## What is safe to publish

Verified on 2026-07-30:

- The only environment file tracked in git is `.env.example`, a template.
- `.gitignore` (231 lines) is committed on every branch and ignores `.env`.
- A full-history gitleaks scan of 109 commits reported 10 findings. All ten were
  inspected by hand and are false positives — documentation placeholders
  (`Authorization: Bearer YOUR_OPENAI_API_KEY`), vendor catalogue prose
  (`"authentication": "Integrated/SQL Auth"`), and deliberately invalid JWTs in
  code-generation test fixtures. No live credential is present.

## Sync procedure

```bash
git remote add sg     https://github.com/saint-gobain-archie/archie-ea.git   # private
git remote add public https://github.com/Anioko/archie-ea.git               # PUBLIC

git fetch --all
git push sg     main
git push public main      # open-source content only; never prod-live-snapshot-*
```

## Outstanding at time of writing

- **Nobody on the current credentials can push to `Anioko/archie-ea`.** Pushes
  return HTTP 403: the token in use belongs to `aniekanasuquookono-web`, which
  has no write access to the `Anioko` account's repository. Until that is
  granted, the public repo **cannot** be kept updated, and rule 2 above cannot be
  honoured. Resolve by granting that account write access, or by using a token
  belonging to `Anioko`.

- **The production server pushes to the public repo.** On the app droplet,
  `/root/archie-ea` has `origin = https://github.com/Anioko/archie-ea.git`. A
  production host should not have the public repository as its default remote;
  point it at `saint-gobain-archie` instead. (It currently has no credentials, so
  nothing has actually been pushed from there.)

- Branches rescued from the personal fork into `saint-gobain-archie` on
  2026-07-30, none of which existed there before:
  `deploy-sync-2026-07-14` (27 commits), `pilot-readiness-fixes` (4),
  `fix/apex-codegen-dashboards-proxy-https` (1). These still need copying to the
  public repo once access is available.

- `Anioko/archie-ea` `main` carries one commit the company repo lacks
  (`3571dfa`, the squash-merge of its PR #1), while lagging the company repo by
  22. The two `main` branches need reconciling in a single merge; do not
  force-push either.
