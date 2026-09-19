# Production deploy workflow

`.github/workflows/deploy.yml` deploys one commit that is already on `main` to
production by running `scripts/deploy_verified.sh` from a GitHub runner. It
exists for sessions that have GitHub access but no SSH access to the droplet.
It is manually triggered, needs a reviewer's approval before it can reach the
droplet, and leaves an auditable run record.

It deploys the topology production runs today: a source checkout at
`/root/archie-ea` bind-mounted into the server container on the app droplet
(`134.122.105.56`). It is not the immutable-image pipeline in `deploy/deploy.sh`.
The Caddy proxy droplet (`165.22.125.156`) is not touched.

## What it does

Two jobs run in sequence.

1. **Pre-flight** (no secrets, no approval). Refuses the request unless all of
   these hold:
   - `ref` is a full 40-character lowercase hex SHA. Branch names, tags and
     short SHAs are refused.
   - The workflow was dispatched from `main`.
   - The commit is an ancestor of `origin/main`.
   - No branch named like the SHA exists. `deploy_verified.sh` resolves
     `origin/<ref>` before the bare ref, so such a branch would deploy its own
     tip instead of the commit that was checked.
   - Every job in `ci.yml` has concluded `success` for that exact commit
     (queried once from the checks API, not polled). The list is
     `REQUIRED_CHECKS` in `scripts/deploy_workflow.py`; a test keeps it equal to
     the jobs in `ci.yml`.
   - The `production` environment has required reviewers and a deployment
     branch policy (setup step 1).

   There is no override input. A refused request never reaches a reviewer.

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

`deploy_verified.sh` is not modified. Its own verification (container healthy,
bind mount present, `/version` `build_id` equal to the deployed commit) is what
decides success. The workflow additionally requires the script's
`DEPLOY VERIFIED: commit <sha>` line to name exactly the requested commit.

## What it does not do

- It does not deploy branches, tags or commits that are not on `main`, and it
  does not deploy commits whose CI is not fully green. While CI is red, every
  dispatch is refused (dry runs included); deploy from a machine with SSH
  (`scripts/deploy_verified.sh <ref>`) in the meantime.
- `--skip-deploy` ignores the ref it is given. A dry run therefore proves the
  deployment that is running now is healthy, mounted and serving its own commit.
  It does not test the requested commit; the pre-flight does that.
- It does not run the authenticated Playwright smoke check (step 5 of the
  script), because no `DEPLOY_VERIFY_EMAIL`/`DEPLOY_VERIFY_PASSWORD` is
  provided. The script prints that it skipped it. `post_deploy_verify.py`
  covers the anonymous public pages only, and does not validate the site's TLS
  certificate.
- It does not print the droplet's output. This repository is public, so Actions
  logs are readable by anyone. Only `deploy_verified.sh`'s own status lines
  (`==`, `OK:`, `DEPLOY-VERIFY FAIL:`, `DEPLOY ...`, `CRITICAL:`) and ssh's own
  client errors are shown; everything else is counted and withheld. To see why a
  deploy failed, read the droplet's logs from a machine that has SSH.
- It does not deploy while another deploy is running (concurrency group
  `production-deploy`, never cancelled mid-run). GitHub keeps at most one
  further run waiting in the group and replaces an older waiting run when a
  newer one arrives.
- It cannot finish a deploy that is cut off. The deploy job is stopped after 75
  minutes (the deploy step after 65). A deploy stopped part-way leaves the
  droplet in whatever state `deploy_verified.sh` had reached, so check it from a
  machine with SSH before dispatching again.

## One-time setup (a person with admin rights on the repository and root on the droplet)

The workflow cannot work, and must not be dispatched, until every step is done.

### 1. Create the `production` environment with required reviewers

Required reviewers are mandatory. If a job names an environment that has no
protection rules, GitHub starts the job immediately with no approval, and the
environment's secrets are available to it. If the environment does not exist at
all, GitHub creates it empty on first use.

Settings, Environments, New environment, name `production`:

- Required reviewers: add at least one person who will approve deployments.
- Deployment branches and tags: Selected branches and tags, add `main`. Without
  this, a copy of the workflow on another branch could be dispatched and, once
  approved, run with the environment's secrets.
- Prevent self-review: leave off if there is a single maintainer, otherwise
  nobody can approve. With two or more maintainers, turn it on.

Equivalent API calls (replace `<user-id>` with `gh api users/<login> --jq .id`):

```bash
echo '{"reviewers":[{"type":"User","id":<user-id>}],"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}' \
  | gh api -X PUT repos/Anioko/archie-ea/environments/production --input -
gh api -X POST repos/Anioko/archie-ea/environments/production/deployment-branch-policies -f name=main -f type=branch
```

The pre-flight reads these rules through the API and refuses if the reviewers
or the branch policy are missing. That read is a guard against a
misconfigured environment; the settings above are the control. If the workflow
token cannot read the settings, the run continues, prints a warning annotation
and shows "NOT CHECKED" in the pre-flight summary. If the first dry run shows
that, the setup is the only protection, so confirm it by eye. If the pre-flight
refuses even though the reviewers exist, the token cannot see the rules: remove
`--check-environment production` from the two pre-flight steps in a reviewed
change.

### 2. Create a dedicated deploy key

Do not reuse `DROPLET_SSH_KEY`; that key belongs to the read-only log scan in
`production-watch.yml`.

```bash
ssh-keygen -t ed25519 -N "" -C "archie-ea-github-deploy" -f ./archie_deploy_key
```

The key has no passphrase because the runner cannot type one.

### 3. Authorise the key on the droplet, restricted

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

### 4. Get the host key value without trusting the network

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
`<ip> <key-type> <key>` lines for `134.122.105.56` only. Hashed entries, `@`
markers and other hosts are refused. If the host key ever changes (the droplet
is rebuilt), every run fails with "Host key verification failed" until this
secret is updated; that is intended.

### 5. Add the two secrets to the `production` environment

They must be environment secrets of `production`, not repository secrets, so
that no job can read them before a reviewer approves it.

```bash
gh secret set DROPLET_DEPLOY_KEY --env production < archie_deploy_key
gh secret set DROPLET_KNOWN_HOSTS --env production < known_hosts_value
```

Then delete `archie_deploy_key` and `known_hosts_value` from the machine that
generated them.

### 6. Recommended: keep the dispatcher and the approver separate

Approving a deployment is an API call (`POST /repos/{owner}/{repo}/actions/runs/{id}/pending_deployments`)
that any required reviewer with a `repo`-scope token can make. If a session
dispatches with the same GitHub account that is the only required reviewer, it
can also approve its own run, and the approval step protects nothing. Use a
dispatching identity that is not a reviewer (a separate account, or a
fine-grained token limited to Actions: write on this repository), and keep the
reviewer role with a person.

Also consider protecting `main` (branch protection or a ruleset that requires a
pull request and the CI checks). Today `main` accepts direct pushes, so
"an ancestor of `main` with green CI" is the guarantee, not "reviewed".

## Before dispatching

The repository rule is to run the full `python scripts/verify.py` (never a tag
subset) on the commit being deployed. The workflow does not run it: CI calls
`verify.py` by tag and by gate, not as the whole runner. Run it yourself and
dispatch only when it is green.

## Running it

The workflow file must be on `main` before it can be dispatched.

```bash
# 1. Rehearse: verify what is running now, change nothing.
gh workflow run deploy.yml --ref main -f ref=<40-character-sha> -f dry_run=true

# 2. Deploy.
gh workflow run deploy.yml --ref main -f ref=<40-character-sha> -f dry_run=false

gh run list --workflow deploy.yml --limit 3
gh run watch <run-id>
```

Both modes need approval, because both use the droplet key. The first dry run is
also the test of the setup: it proves the runner can reach the droplet with the
pinned host key and read the running commit, and it shows whether the
environment guard could read the environment's settings.

## How approval works

After the pre-flight job passes, the deploy job shows "Waiting for review" on
the run page. A required reviewer opens the run, reads the pre-flight summary
(requested commit, mode, CI result) and chooses Approve or Reject. Only after
approval does the job start and receive the environment's secrets. A run that is
not reviewed within 30 days fails. While a run is waiting it
holds the concurrency group, so reject or approve it before dispatching another.

## Rollback

`deploy_verified.sh` keeps the last commit it verified in a file on the machine
it runs from (`DEPLOY_STATE_FILE`) and reads that file locally; it does not read
anything from the droplet. A fresh runner has no such file, so on its own an
automatic rollback would find "no different known-good commit on record" and
leave the failed deploy in place. This is reproduced against the real script in
`tests/test_deploy_verified_fake_droplet.py`.

The workflow solves it without changing the script. Before a real deploy it runs
`deploy_verified.sh --skip-deploy`. When that passes, the script records the
droplet's current commit as verified, which is exactly the commit to return to.
The deploy step then runs with `AUTO_ROLLBACK=1`, so if the requested commit
fails verification the script redeploys that commit, re-verifies it, and exits
non-zero (the requested commit did not ship). The run is marked failed and the
summary says the rollback was performed.

Limits:

- If production was not verified healthy before the run (the baseline failed),
  there is nothing known-good to return to. The run warns about it, deploys
  anyway, and if the deploy fails the failed commit stays deployed. The summary
  says "No rollback was possible".
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

That commit must still pass the pre-flight (on `main`, CI green for it). If it
cannot, or the workflow itself is unavailable, use
`scripts/deploy_verified.sh <previous-sha>` from a machine with SSH.

## Revoking access

1. Remove the `archie-ea-github-deploy` line from `/root/.ssh/authorized_keys`
   on `134.122.105.56`. This is the step that actually cuts access; do it first.
2. Delete the environment secrets:
   `gh secret delete DROPLET_DEPLOY_KEY --env production` and
   `gh secret delete DROPLET_KNOWN_HOSTS --env production`.
3. To stop the workflow being dispatched at all: `gh workflow disable deploy.yml`,
   or delete the `production` environment.
4. To restore access, repeat setup steps 2 to 5 with a new key.

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
  workflow places an `ssh` wrapper first on `PATH` that forces that
  configuration.
- The scripts that run come from the commit the workflow was dispatched from
  (`main`), not from the commit being deployed.
- Third-party actions are pinned to a full commit SHA.
