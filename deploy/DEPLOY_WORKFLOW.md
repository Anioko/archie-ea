# Production deploy workflow

`.github/workflows/deploy.yml` deploys one commit that is already on `main` to
production by running `scripts/deploy_verified.sh` from a GitHub runner. It
exists for sessions that have GitHub access but no SSH access to the droplet.
It is manually triggered, its deploy job waits for a required reviewer before it
can use the droplet key, and it leaves an auditable run record.

Read "Decide first" before setting anything up. With a single maintainer,
GitHub's "prevent self-review" has to stay off, and then the person or session
that dispatches a run can also approve it. In that arrangement the approval is a
confirmation prompt with an audit trail, not a separation of duties. It becomes a
separation of duties only with a second reviewer account and prevent
self-review switched on.

It deploys the topology production runs today: a source checkout at
`/root/archie-ea` bind-mounted into the server container on the app droplet
(`134.122.105.56`). It is not the immutable-image pipeline in `deploy/deploy.sh`.
The Caddy proxy droplet (`165.22.125.156`) is not touched.

## What it does

Two jobs run in sequence.

1. **Pre-flight** (no secrets, no approval). Refuses the request unless all of
   these hold:
   - `ref` is a full 40-character lowercase hex SHA. Branch names, tags and
     short SHAs are refused, and so is the SHA of a tag object.
   - The workflow was dispatched from `main`.
   - The commit is on `origin/main`'s first-parent history: it was itself a
     commit on `main`. A commit that reached `main` only as part of a merged
     branch (a pull request's head commit under a merge commit) is an ancestor
     of `main` but is refused, because its checks ran on a merge preview of the
     branch and no push-triggered CI run ever ran on its own tree. Deploy the
     merge commit instead. With squash merges every commit on `main` qualifies.
   - No branch or tag named like the SHA exists (`<sha>`, or `origin/<sha>`). A
     name that merely starts with the SHA, for example `<sha>-revert`, counts too,
     because the refs lookup is a prefix match; renaming or deleting that ref
     clears the refusal. This is defence in depth. The real control is in `deploy_verified.sh`,
     which resolves a 40-hex ref as an object and never as `origin/<ref>`: git
     resolves a tag named `origin/<sha>` ahead of the remote-tracking branch, so
     the old lookup order could deploy a different commit from the one checked.
   - Every job in `ci.yml` except the one listed under `EXCLUDED_CHECKS` has
     concluded `success` on that exact commit (queried once from the checks API,
     not polled; the newest run of each job decides). Because the commit must be
     on the first-parent history of `main`, CI ran on that commit's own tree when
     it landed on `main`. The lists are in `scripts/deploy_workflow.py`; a test fails
     when `ci.yml` gains, loses or renames a job without them following. The one
     exclusion is `Build immutable release image`: it builds and pushes a GHCR
     image, production does not run that pipeline, and a registry or buildx
     outage must not block a deploy of a bind-mounted checkout.
   - The `production` environment has required reviewers and a deployment-branch
     policy, and its settings can be read (setup step 1). If they cannot be read,
     the request is refused.

   There is no override input and no path that skips the CI requirement for dry
   runs. A refused request never reaches a reviewer.

2. **Deploy** (declares `environment: production`, so it waits for a reviewer).
   After approval it repeats the pre-flight checks, installs the deploy key and
   the pinned host key, then:
   - `dry_run: true`: runs `deploy_verified.sh <sha> --skip-deploy`. Nothing on
     the droplet is changed.
   - `dry_run: false`: first verifies what is running now (the baseline, see
     "Rollback"), then runs `deploy_verified.sh <sha>`, then runs
     `post_deploy_verify.py --json` against the public site. The run fails if
     any of them fails.

   The job summary lists the requested commit, the commit that was running
   before, dry run or real, the result, whether a rollback happened, and a link
   to the run.

`deploy_verified.sh` is changed in one place only: a full 40-hex ref is resolved
as an object (`<sha>^{commit}`, which must equal the SHA) and never tried as
`origin/<ref>`, on the deploy path and on the auto-rollback path. A ref that does
not resolve stops the deploy before anything is checked out. Branch names still
resolve as before. Its verification (container healthy, bind mount present,
`/version` `build_id` equal to the deployed commit) is untouched and is what
decides success. The workflow additionally requires the script's
`DEPLOY VERIFIED: commit <sha>` line to name exactly the requested commit.

## What it does not do

- It does not deploy branches, tags or commits that are not on `main`, and it
  does not deploy commits whose required CI is not fully green. While any
  required job is red on every commit, every dispatch is refused (dry runs
  included). As measured on 2026-09-19 at `main` 1cdd8c4d, four required jobs are
  red: `Tests (pytest + coverage)`, `SAST (bandit)`, `Browser journeys (one per
  archetype)` and `Browser compatibility (webkit)`, so every real dispatch is
  refused by design until CI on `main` is green (the pre-flight prints the
  current list). Getting CI green, or deciding which jobs are required, is a
  decision for the repository owner and is recorded outside this workflow. Until
  then, deploy from a machine with SSH (`scripts/deploy_verified.sh <ref>`).
- The CI requirement protects against mistakes, not against someone with write
  access. A person who can push a workflow to a branch can publish check runs
  with the required names, so write access to the repository is equivalent to
  being able to get a commit past this check.
- `--skip-deploy` ignores the ref it is given. A dry run therefore proves the
  deployment that is running now is healthy, mounted and serving its own commit.
  It does not test the requested commit; the pre-flight does that.
- It does not run the authenticated Playwright smoke check (step 5 of the
  script), because no `DEPLOY_VERIFY_EMAIL`/`DEPLOY_VERIFY_PASSWORD` is
  provided. The script prints that it skipped it. `post_deploy_verify.py`
  covers the anonymous public pages only, and does not validate the site's TLS
  certificate.
- It does not print unfiltered droplet output. This repository is public, so
  Actions logs are readable by anyone. Every step that talks to the droplet
  passes its output (stdout and stderr) through a filter that shows only lines
  beginning like `deploy_verified.sh`'s own status lines (`==`, `OK:`,
  `DEPLOY-VERIFY FAIL:`, `DEPLOY ...`, `CRITICAL:`) or like ssh's own client
  errors; everything else is counted and withheld, as is any line starting with
  `::`. The filter matches by line prefix and cannot tell who wrote a line: text
  that begins like a status line is shown as it is. It reduces accidental
  disclosure; it is not a guarantee against a hostile droplet or hostile deployed
  code. To see why a deploy failed, read the droplet's logs from a machine that
  has SSH. The summary step discards the droplet's stderr.
- It does not deploy while another deploy is running (concurrency group
  `production-deploy`, never cancelled mid-run). GitHub keeps at most one
  further run waiting in the group and replaces an older waiting run when a
  newer one arrives. A run parked on approval holds the group; see "Rollback".
- It cannot finish a deploy that is cut off. The deploy job is stopped after 100
  minutes; the baseline and dry-run steps are each stopped after 25 (the health
  budget is 15 minutes) and the deploy step after 65. A baseline or dry run
  stopped that way fails the run before anything is deployed. A deploy stopped
  part-way leaves the droplet in whatever state
  `deploy_verified.sh` had reached, so check it from a machine with SSH before
  dispatching again.
- The tests that check file modes (key 0600, directory 0700) only run on POSIX.
  They have not run on the machine this was written on; their first execution is
  the Linux runner in CI.

## Decide first: who can approve a deployment

This is a decision for the repository owner. It comes before setup because it
changes how the environment is created (step 1).

Approving a deployment is a REST call
(`POST /repos/{owner}/{repo}/actions/runs/{id}/pending_deployments`) that any
required reviewer holding a `repo`-scope token can make. The `gh` login on the
machine that runs sessions is the repository owner's, with `repo` and `workflow`
scopes. Whenever that owner is a required reviewer, a session that can dispatch a
run can also approve it. GitHub evaluates reviewers and "prevent self-review" on
its own servers; nothing inside the workflow can see or change who approved a run.

- **Option (a): a second reviewer account, prevent self-review on.** The account
  that dispatches (the owner's login, or a session using it) can start runs but
  cannot approve them; the second account approves. This is a separation of
  duties. It needs a second GitHub account with at least read access to the
  repository, held by a person, and someone available to approve.
- **Option (b): accept a confirmation prompt.** One maintainer, prevent
  self-review off. A run still stops for an explicit approval, records who
  approved, when and for which commit, and the deploy key never exists in a job
  that has not been approved. But whoever holds the owner's token can dispatch and
  approve. Treat that token as the ability to deploy to production as root. Under
  this option a session may dispatch but must not approve its own run; that is a
  working rule, and GitHub does not enforce it.

The choice sets `prevent_self_review` when the environment is created (step 1).
Also consider protecting `main` (a ruleset that requires a pull request and the CI
checks): today `main` accepts direct pushes, so "a first-parent commit of `main`
with green CI" means CI-checked, not reviewed.

## One-time setup (a person with admin rights on the repository and root on the droplet)

The order matters: the environment and the rehearsal come before the key and the
secrets, so the guard is confirmed before anything that can reach the droplet
exists.

### 1. Create the `production` environment with required reviewers

Required reviewers are mandatory. If a job names an environment that has no
protection rules, GitHub starts the job immediately with no approval, and the
environment's secrets are available to it. If the environment does not exist at
all, GitHub creates it empty on first use.

Settings, Environments, New environment, name `production`:

- Required reviewers: the person who approves deployments (option (a): a second
  account, not the dispatching one).
- Prevent self-review: on for option (a); off for option (b), otherwise a single
  maintainer cannot approve anything.
- Deployment branches and tags: Selected branches and tags, add `main`. Without
  this, a copy of the workflow on another branch could be dispatched and, once
  approved, run with the environment's secrets.

Equivalent API calls, with `prevent_self_review` stated explicitly (replace
`<reviewer-user-id>` with `gh api users/<login> --jq .id`):

```bash
PREVENT_SELF_REVIEW=true    # option (a); use false for option (b)
gh api -X PUT repos/Anioko/archie-ea/environments/production --input - <<EOF
{"prevent_self_review": $PREVENT_SELF_REVIEW, "reviewers": [{"type": "User", "id": <reviewer-user-id>}], "deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
EOF
gh api -X POST repos/Anioko/archie-ea/environments/production/deployment-branch-policies -f name=main -f type=branch
```

Between the two calls the environment allows no branch, which fails closed.

The pre-flight reads these settings through the API and refuses if the reviewers
or the branch policy are missing, or if the settings cannot be read. That read is
a guard against a misconfigured environment; the settings above are the control,
because a copy of the workflow on another branch could leave the guard out.

### 2. Merge the workflow to `main`

The workflow file must be on the default branch before it can be dispatched.

### 3. Rehearse the guard, with no key and no secrets in place

Dispatch once with any recent commit on `main`:

```bash
gh workflow run deploy.yml --ref main -f ref=<any-recent-40-character-sha-on-main> -f dry_run=true
gh run view <run-id>
```

While CI on `main` is red, this run is refused in the pre-flight job, and that is
the expected result: the point is the line in the pre-flight summary,

```
Environment protection: verified (required reviewers: 1, deployment branches: custom branches)
```

The environment check runs even when CI has already failed. This rehearsal never
reaches the droplet: the deploy job does not start, and no key or secret exists
yet. If the chosen commit does pass CI, the run stops at the approval prompt;
reject it.

Other results and what they mean:

- `not evaluated (the request was refused before the environment was read)`:
  the request was refused before the environment was reached, because `ref` was
  not a full 40-character SHA, `dry_run` was not exactly `true` or `false`, or the
  workflow was not dispatched from `main`. It says nothing about the environment.
  Fix the dispatch and run it again.
- `REFUSED: environment 'production' has no required reviewers` or `can be
  deployed from any branch`: fix step 1.
- `REFUSED: environment 'production' does not exist, or the workflow token cannot
  see it`: the environment is missing or renamed.
- `REFUSED: environment settings could not be read: HTTP ...`: the workflow token
  could not read the environment, and the run is refused because the reviewer
  requirement cannot be confirmed. GitHub documents the endpoint as readable by
  anyone with read access to the repository, so the read-only token this
  workflow uses on a public repository should be able to call it. A 403 means
  that has changed or been narrowed (check the repository's Actions permissions
  and the `permissions:` blocks in the workflow); 5xx, 429 or a timeout are worth
  one re-run.

### 4. Create a dedicated deploy key

Do not reuse `DROPLET_SSH_KEY`; that key belongs to the read-only log scan in
`production-watch.yml`.

```bash
ssh-keygen -t ed25519 -N "" -C "archie-ea-github-deploy" -f ./archie_deploy_key
```

The key has no passphrase because the runner cannot type one.

### 5. Authorise the key on the droplet, restricted

Append one line to `/root/.ssh/authorized_keys` on `134.122.105.56`, using the
contents of `archie_deploy_key.pub`:

```
restrict ssh-ed25519 AAAA...the-public-key... archie-ea-github-deploy
```

`restrict` turns off port, agent and X11 forwarding, pty allocation and
`~/.ssh/rc`. `deploy_verified.sh` needs none of them: every call is
`ssh <host> bash -s -- <args>` with the script on stdin and no `-t`.

What else was considered:

- A forced `command=` that only accepts `bash -s -- ...` is feasible, because
  every remote call the script and the workflow make has that form. It blocks
  interactive logins, `scp` and `sftp` with this key, but not what `bash -s`
  runs, since that is script text supplied by the runner. The key is root
  access either way, so this adds little and is not recommended by default.
- `from="..."` is not practical: GitHub-hosted runners come from large address
  ranges that change.
- A non-root deploy user is not feasible without re-architecting the deploy: the
  script runs `git` and `docker compose` in `/root/archie-ea`, and `.env` is
  root-owned with mode 600.

The security boundary is therefore the environment's required reviewers and
branch policy, not the key restriction. Treat the key as full root on the app
droplet.

### 6. Get the host key value without trusting the network

`DROPLET_KNOWN_HOSTS` pins the droplet's SSH host key. The workflow never runs
`ssh-keyscan` and never disables host key checking. Take the key from the
droplet itself over a session you already trust (for example the machine that
already deploys):

```bash
ssh root@134.122.105.56 'cat /etc/ssh/ssh_host_ed25519_key.pub' | awk '{print "134.122.105.56", $1, $2}' > known_hosts_value
```

Or open the droplet's web console in the DigitalOcean dashboard and run
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`; compare that fingerprint with
`ssh-keygen -lf known_hosts_value`. The value must be plain
`<ip> <key-type> <key>` lines naming exactly `134.122.105.56`. Hashed entries,
`@` markers, host lists, patterns and other hosts are refused, and so is the
bracketed `[<ip>]:<port>` form that ssh uses for a non-22 port; if the droplet's
SSH port ever moves, the validator has to change first. If the host key
ever changes (the droplet is rebuilt), every run fails with "Host key
verification failed" until this secret is updated; that is intended.

### 7. Add the two secrets to the `production` environment

They must be environment secrets of `production`, not repository secrets, so
that no job can read them before a reviewer approves it.

```bash
gh secret set DROPLET_DEPLOY_KEY --env production < archie_deploy_key
gh secret set DROPLET_KNOWN_HOSTS --env production < known_hosts_value
```

Then delete `archie_deploy_key` and `known_hosts_value` from the machine that
generated them.

## Before dispatching

The repository rule is to run the full `python scripts/verify.py` (never a tag
subset) on the commit being deployed. The workflow does not run it: CI calls
`verify.py` by tag and by gate, not as the whole runner. Run it yourself and
dispatch only when it is green.

## Running it

A real dispatch needs a commit on `main` for which every required CI job is
green. While none exists, every dispatch is refused by design; see "What it does
not do".

```bash
# 1. Rehearse against the real droplet: verify what is running now, change nothing.
gh workflow run deploy.yml --ref main -f ref=<40-character-sha> -f dry_run=true

# 2. Deploy.
gh workflow run deploy.yml --ref main -f ref=<40-character-sha> -f dry_run=false

gh run list --workflow deploy.yml --limit 3
gh run watch <run-id>
```

Both modes need approval, because both use the droplet key. The first dry run
that gets through is the test of the key and host-key setup: it proves the runner
can reach the droplet with the pinned host key and read the running commit.

A session that dispatches a run reports the run link and that it is waiting for
approval. It does not approve its own run.

## How approval works

After the pre-flight job passes, the deploy job shows "Waiting for review" on the
run page. A required reviewer opens the run, reads the pre-flight summary
(requested commit, mode, CI result) and chooses Approve or Reject. Only after
approval does the job start and receive the environment's secrets. A run that is
not reviewed within 30 days fails.

What this gives, and what it does not, depends on the choice under "Decide
first". In every case a run stops for an explicit approval and records who
approved and when, and the key does not exist in a job that has not been
approved. With one maintainer and self-review off, the reviewer and the
dispatcher can be the same account, so the approval is a confirmation prompt with
an audit trail. It separates duties only when the reviewer is a second account
and prevent self-review is on.

## Rollback

`deploy_verified.sh` keeps the last commit it verified in a file on the machine
it runs from (`DEPLOY_STATE_FILE`) and reads that file locally; it does not read
anything from the droplet. A fresh runner has no such file, so on its own an
automatic rollback would find "no different known-good commit on record" and
leave the failed deploy in place. This is reproduced against the real script in
`tests/test_deploy_verified_fake_droplet.py`.

The workflow solves it without changing that logic. Before a real deploy it runs
`deploy_verified.sh --skip-deploy`. When that passes, the script records the
droplet's current commit as verified, which is exactly the commit to return to.
The deploy step then runs with `AUTO_ROLLBACK=1`, so if the requested commit
fails verification the script redeploys that commit, re-verifies it, and exits
non-zero (the requested commit did not ship). The run is marked failed and the
summary says the rollback was performed. The rollback resolves its target the
same way as a deploy, as an object.

Limits:

- If production was not verified healthy before the run (the baseline failed,
  after the same 15-minute health budget as the deploy), there is nothing
  known-good to return to. The run warns about it, deploys anyway, and if the
  deploy fails the failed commit stays deployed. The summary says "No rollback
  was possible".
- The script rolls back at most once. If the rollback itself fails to verify, the
  run reports CRITICAL and someone with SSH must look at the droplet.
- Only the commit that was running immediately before the run is a rollback
  target. Nothing is stored on the droplet.

Manual rollback: dispatch the workflow with the commit that was running before.
It is in the failed run's summary ("Running before") and in the previous
successful run.

```bash
gh workflow run deploy.yml --ref main -f ref=<previous-sha> -f dry_run=false
```

A run sitting in "Waiting for review" holds the `production-deploy` concurrency
group, so an urgent rollback dispatch would queue behind it. Reject or cancel the
parked run first (`gh run cancel <run-id>`), then dispatch.

The previous commit must still pass the pre-flight (on `main`, required CI green
for it). If it cannot, or the workflow itself is unavailable, use
`scripts/deploy_verified.sh <previous-sha>` from a machine with SSH.

## Revoking access

1. Remove the `archie-ea-github-deploy` line from `/root/.ssh/authorized_keys`
   on `134.122.105.56`. This is the step that actually cuts access; do it first.
2. Delete the environment secrets:
   `gh secret delete DROPLET_DEPLOY_KEY --env production` and
   `gh secret delete DROPLET_KNOWN_HOSTS --env production`.
3. To stop the workflow being dispatched at all: `gh workflow disable deploy.yml`,
   or delete the `production` environment.
4. To restore access, repeat setup steps 4 to 7 with a new key.

Assume the key is compromised whenever a run cannot be explained. Anyone who can
approve a run can also have read the private key out of the environment: one line
changed in `deploy.yml` on `main` (which accepts direct pushes) plus one approval
is enough, and log masking does not stop a transformed copy. So an unexplained
run, or a change to the workflow that nobody remembers making, means rotating the
key (remove the old line from `authorized_keys`, then repeat steps 4 to 7 with a
new key), not only removing access.

## Security notes for reviewers of this workflow

- The trigger is `workflow_dispatch` only. Inputs reach steps only through `env:`
  and are validated by the pre-flight before use; no `${{ }}` expression appears
  in any `run:` body (a test asserts this).
- Secrets are referenced by exactly one step, in the job that declares the
  environment. The key is written with mode 600 under the runner's temp
  directory and removed by an `always()` step. Nothing is traced with `set -x`.
- SSH runs with `StrictHostKeyChecking yes` against a `known_hosts` file that
  contains only the pinned entry, `IdentitiesOnly yes`, `BatchMode yes`, and no
  agent or X11 forwarding. `deploy_verified.sh` calls plain `ssh`, so the
  workflow places an `ssh` wrapper first on `PATH` that applies that
  configuration and also passes the pinning options on the command line ahead of
  its own arguments. OpenSSH keeps the first value it obtains and command-line
  options come before the config file, so a caller's `-o` cannot loosen them; a
  test proves it with `ssh -G`.
- The scripts that run come from the commit the workflow was dispatched from
  (`main`), not from the commit being deployed.
- Third-party actions are pinned to a full commit SHA.
