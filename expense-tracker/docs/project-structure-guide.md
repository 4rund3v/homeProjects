# Project Structure Guide

> This doc does **not** give you a folder tree. It gives you the **principles and
> decision rules** for arriving at one, evolving it, and knowing when you got it
> wrong. You will build the structure as you build the project.

A structure is not a starting artifact — it is a **consequence** of decisions about
boundaries, ownership, and deployment. If you copy a "best practice" tree before you
understand those decisions, the tree will fight you. Instead, start small and let
structure emerge from pressure.

---

## 1. The two questions that determine structure

Before you create any directory, answer:

1. **What are the independently deployable units?**
   In this project: the **Django/DRF API**, the **Kafka consumer worker**, the
   **React UI**, and (later) **Terraform/Helm infra**. Each deployable unit is a
   candidate for its own top-level boundary. They may start in one repo
   (monorepo) but each must be able to version and deploy independently.

2. **What changes together, and who owns it?**
   Code that changes for the same reason and is owned by the same person belongs
   close together. Code that changes for different reasons belongs apart — even if
   it currently shares technology.

If you can't answer these yet, you don't need the directory. Build the feature
first, extract structure when the second copy appears (the "rule of three": extract
on the third duplicate, not the first).

---

## 2. Principles for a Python/DRF project

**Organize by feature/domain, not by technical layer.**
The common mistake is `models/`, `views/`, `serializers/`, `services/` at the top
level. That scatters one feature across four folders and makes it impossible to see
what "expenses" actually contains. Prefer grouping by domain concept so everything
about one concept sits together:

```
# Better: each feature owns its layers
<feature>/  →  models, serializers, views, services, migrations
```

The technical layers still exist — they just live *inside* each feature. This maps
cleanly to Django **apps**: one app per domain concept. An app is your boundary.

**Keep the boundary rules honest.** Within a feature, allow code to depend on
anything. *Across* features, only depend on public interfaces (models, service
functions), never on another feature's serializers or internals. If feature A needs
something from feature B, ask whether that thing actually belongs in a shared
`core`/`common` app instead.

**Separate "domain" from "integration."** Your domain logic (how a loan balance
changes) should not import Kafka, HTTP, or Django request objects. Keep the Kafka
producer, the DRF views, and the pure business logic in distinct layers so you can
test the business rules without a broker or a database. This is the single most
valuable boundary in the project.

**Config lives at the edges, not scattered.** All environment-driven values (DB
URL, Kafka brokers, secrets) read from one settings module that pulls from the
environment. Never hardcode a host or a credential. `django-environ` or `pydantic-settings`
are the standard choices — pick one and be consistent.

---

## 3. Where the React UI sits

This is the decision you asked about. You have three realistic options, and the
right one depends on how you want to deploy and learn:

| Option | Layout | Deploys as | Choose when |
|--------|--------|-----------|-------------|
| **A. Separate repo** | UI in its own git repo | Independent (S3+CDN, Vercel, or its own container) | You want clean ownership and the UI is genuinely throwaway |
| **B. Monorepo, separate deployable** | `ui/` and `api/` siblings in one repo | Two independent pipelines | You want one place to look, but independent deploys |
| **C. Monorepo, served by Django** | UI built to static files, served by DRF/NGINX | One deployable | Simplest ops; coupling is acceptable for a personal tool |

**Recommendation for this project: Option B.** Reasoning:

- The UI is LLM-generated and disposable, but it still needs to call your API during
  development (`localhost:8000`). Keeping it as a sibling folder with its own
  `package.json` and dev server makes that trivial.
- It still deploys independently — you can serve it as a static site behind the same
  NGINX ingress that fronts the API, which is exactly the production shape you want
  to learn.
- You avoid the coupling trap of Option C (Django serving a SPA complicates routing,
  caching, and auth-token handling for no learning benefit).

**The key boundary rule regardless of option:** the UI talks to the API **only**
through the documented OpenAPI contract. It never imports backend code, never shares
types from the backend, and gets its types from the generated client (see
[`api-contracts-guide.md`](api-contracts-guide.md)). If you ever find yourself
copying a Django serializer field into the frontend by hand, that's a signal your
contract workflow is broken.

**CORS and auth across the boundary:** because the UI and API are separate origins
(at least in dev), you'll configure CORS on the API and decide how the JWT is stored
in the browser. Decide storage deliberately — `httpOnly` cookie vs. `localStorage` —
and document the choice in [`design.md`](design.md) when you get there.

---

## 4. Where the infrastructure lives

Terraform, Helm, and k8s manifests should **not** live inside the Django app, and
should **not** be scattered. Keep them in a clearly separated area of the repo so
that "what runs in the cluster" is reviewable in one place. Two common shapes:

- **Infra inside the monorepo, top-level** — Terraform and Helm sit as siblings to
  `api/` and `ui/`. Good when one team (you) owns everything.
- **Infra in its own repo** — better if you later want infra changes to have a
  separate review/approval path. Overkill for now.

Start with infra as top-level siblings in the same repo. The important rule: infra
code references the app **by container image tag**, never by source path. That keeps
the deploy pipeline honest — you build an image, tag it, and infra consumes the tag.

---

## 5. How structure should evolve (and when to refactor)

Structure is not decided once. Use these signals:

**Signals you're getting it right**
- You can describe a feature by pointing at one folder.
- Adding a feature rarely touches unrelated folders.
- New team members (or future-you) can find things without a map.

**Signals you're getting it wrong — refactor when you see these**
- A change to one concept forces edits in four unrelated folders (layer-based
  structure creeping back).
- Circular imports between apps — almost always a sign two apps are really one.
- A `utils.py` or `common.py` that everything imports and nothing owns — that's a
  missing domain concept, not a dumping ground.
- You can't name what an app is *for* in one sentence.

**The refactoring discipline:** never do a big-bang restructure. Move one concept at
a time, keep the app runnable at every step, and commit between moves. Python's
import system makes this safe if you move whole modules and update imports in the
same commit.

---

## 6. Practical workflow for this project

1. **Phase 1:** Start with a single Django project and a single app. Don't
   pre-create `expenses/`, `loans/`, `categories/`. Build the first vertical slice
   end-to-end in one app.
2. **Phase 4–5:** When you add the *second* domain concept (loans after expenses),
   that's the pressure point. Now split into apps — one per concept — using the
   feature-based rule above.
3. **Phase 1:** Create the UI sibling folder with a generated starter. Keep it
   empty of real features until the API contract exists.
4. **Phase 9–10:** Create the infra siblings (Terraform, Helm) only once you have a
   container image to deploy. Infra before an image is guessing.
5. **Continuously:** when a refactor signal appears, do the small move immediately —
   don't batch them.

---

## 7. Best-practices checklist

- [ ] One Django app per domain concept (expenses, loans, categories, sources, events).
- [ ] Feature folders own their layers; technical layers live inside features.
- [ ] Domain logic has no imports from Kafka/HTTP/Django-request internals.
- [ ] All config reads from the environment through one settings module.
- [ ] The UI depends on the API only through the generated OpenAPI client.
- [ ] Infra references app images by tag, never by source path.
- [ ] You refactor on the first real signal, not on a schedule.
- [ ] Every directory can be explained in one sentence.

---

## 8. Questions to answer before you create each top-level folder

Write the answers in [`design.md`](design.md) as you go. If you can't answer one,
you're not ready to create that folder yet.

- What is the single responsibility of this folder?
- What is allowed to import it, and what is it allowed to import? (dependency direction)
- Does it deploy independently? If not, why does it have its own boundary?
- Who owns it, and what changes would land here?
- What would have to be true for this folder to be deleted or merged into another?
