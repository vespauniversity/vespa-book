"""The trusted endpoint: a query answered under a filter the *server* derives
from who is asking, never one the caller hands in.

The point of this tool is where the mandatory clause comes from. Every other tool
in this chapter takes a filter as an argument; this one takes an identity
(`--user`) and looks its allowed tenants up in a registry
(`docs/synthetic-data.md` §1: invented staff, `derive_tenants.py`'s
`INVENTED_USERS`) that the caller cannot see or edit from the request. The
YQL clause is then `tenant_id in (...)` (checked on this container:
`tenant_id in ("nike", "adidas")` gave exactly the sum of the two tenants'
own `contains` counts, so no `or`-chain fallback is needed), ANDed onto
whichever retriever's own YQL was asked for
(`rungs.wrap_where`, the same helper `filtered_ann.py` uses, so a retriever's
`or` cannot leak past the identity filter).

`--profile` is the second trusted route: the request selects the deployed
`tenant` query profile (`app/search/query-profiles/tenant.xml`, typed by
`types/tenant.xml`, which declares `tenant` a mandatory string) and sends no
YQL at all - the profile holds the union request and the seller boundary,
the request carries the query text, the query vector, `hits` and the typed
`tenant` value this endpoint derives from the registry. Hybrid only, and not
for an account allowed every seller, because the profile always filters.
`--profile --omit-tenant` sends that request without the value, to show the
profile refusing it before any matching happens (`--block refusal`).

`--untrusted --tenant <value>` is not a second kind of endpoint a reader
would ship; it exists only so `leakage_test.py` has a positive case, a
request that answers with documents outside the caller's own allowed set,
because a test that has only ever seen zero has not been shown to detect
anything.

    python chapters/ch08/authorized_query.py --user nike_staff \\
        --query "running shoes" --retriever hybrid --block hits
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import deployed                     # noqa: E402
from evaluate import build_request  # noqa: E402
from query import Vespa             # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rungs                         # noqa: E402

DEFAULT_USERS_PATH = Path(__file__).resolve().parent / "expected" / "users.json"

RETRIEVERS = ("lexical", "semantic", "hybrid")
# Which rank profile a retriever answers under - ch03's tuned profile, ch04's
# vector profile, ch05's linear-fusion profile. Named here once so
# `leakage_test.py` reads the same mapping rather than a second copy of it.
RANKING = {"lexical": "bm25_tuned", "semantic": "semantic", "hybrid": "hybrid_linear"}


def load_users(path: Path) -> dict[str, list[str] | str]:
    """The staff registry `derive_tenants.py --users-out` wrote -
    `{user: [tenant, ...]}` or `{user: "*"}` for the auditor."""
    data = json.loads(path.read_text())
    return data["users"]


def allowed_set(users: dict, user: str) -> list[str] | str:
    if user not in users:
        raise SystemExit(f"unknown user {user!r}; known: {sorted(users)}")
    return users[user]


def clause_for_allowed(allowed: list[str] | str) -> str:
    """The mandatory filter for an allowed set: `""` (no clause) for the
    auditor's `"*"`, otherwise `tenant_id in ("a", "b")`."""
    if allowed == "*":
        return ""
    values = ", ".join(f'"{t}"' for t in allowed)
    return f"tenant_id in ({values})"


PROFILE = "tenant"   # app/search/query-profiles/tenant.xml, typed by types/tenant.xml


def profile_value(allowed: list[str]) -> str:
    """The inside of the profile's `tenant_id in (%{tenant})`: `"nike"` or
    `"nike", "adidas"`. The profile substitutes it textually, so it is only
    ever built here, from the registry - never from a request."""
    return ", ".join(f'"{t}"' for t in allowed)


def build_profile_request(text: str, hits: int, allowed: list[str]) -> dict:
    """The same request through the deployed `tenant` query profile: no YQL
    is sent at all - the profile holds the union request and the seller
    boundary, the request carries the query text, the query vector, `hits`
    and the typed `tenant` value the profile requires."""
    embed = build_request("hybrid", text, hits)["input.query(q)"]
    return {"queryProfile": PROFILE, "query": text, "input.query(q)": embed,
            "tenant": profile_value(allowed)}


def build_authorized_request(retriever: str, text: str, hits: int, clause: str) -> dict:
    """`evaluate.build_request`'s own YQL for this retriever, widened to
    fetch `tenant_id` (not in the default summary - checked live on this
    container) and the identity clause ANDed on."""
    request = build_request(retriever, text, hits)
    request["yql"] = request["yql"].replace(
        "select id from product", "select id, title, tenant_id from product", 1)
    request["yql"] = rungs.wrap_where(request["yql"], clause)
    return request


def hits_block(response, query: str, user: str, retriever: str, embedders: str) -> str:
    """The demonstration table for the page: hits with their tenant, so a
    reader sees the filter actually reached what came back, not only the
    request that asked for it."""
    lines = [
        f"_User `{user}`, query {query!r}, retriever `{retriever}`, "
        f"{response.total:,} matched, deployed_embedders: {embedders}_",
        "", "| rank | title | tenant | relevance |", "|---|---|---|---|",
    ]
    for i, hit in enumerate(response.hits, 1):
        title = (hit.fields.get("title", "") or "")[:70]
        title = title.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")
        tenant = hit.fields.get("tenant_id", "")
        lines.append(f"| {i} | {title} | {tenant} | {hit.relevance:.3f} |")
    return "\n".join(lines) + "\n"


def vespa_error_message(text: str) -> str:
    """The `message` field of the first error in a failed query's body, or
    the text itself when it is not the JSON the client quotes."""
    import json
    start = text.find("{")
    if start >= 0:
        try:
            body = json.loads(text[start:])
            errors = body.get("root", {}).get("errors") or []
            if errors and errors[0].get("message"):
                return errors[0]["message"]
        except ValueError:
            pass
    return text


def refusal_block(message: str, user: str) -> str:
    """What the deployed profile answers when the typed value it requires
    is missing: the error text, verbatim, so a reader sees the refusal
    happen rather than reads that it would."""
    return (f"_User `{user}`, the `{PROFILE}` query profile asked for without "
            f"its `tenant` value: refused before matching_\n\n"
            f"```\n{message}\n```\n")


BLOCKS = {"hits": hits_block, "refusal": refusal_block}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", required=True, help="an id in the users registry")
    ap.add_argument("--users", type=Path, default=DEFAULT_USERS_PATH,
                    help="the staff registry; default is this chapter's own")
    ap.add_argument("--query", required=True)
    ap.add_argument("--retriever", choices=RETRIEVERS, required=True)
    ap.add_argument("--hits", type=int, default=10)
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--untrusted", action="store_true",
                    help="build the clause from --tenant (client-supplied) "
                         "instead of --user's registry entry - exists only "
                         "so leakage_test.py has a positive case; a trusted "
                         "endpoint never takes this path. Always warns on "
                         "stderr")
    ap.add_argument("--profile", action="store_true",
                    help="send the request through the deployed `tenant` query "
                         "profile (the filter's shape lives in the application; "
                         "the request carries no YQL, only the query text, the "
                         "vector, `hits` and the typed `tenant` value); hybrid "
                         "retriever only, and not for the auditor, whose "
                         "allowed set is everything")
    ap.add_argument("--omit-tenant", action="store_true",
                    help="with --profile: send the profile request without its "
                         "mandatory `tenant` value, to show the refusal "
                         "(--block refusal)")
    ap.add_argument("--tenant", default=None,
                    help="only with --untrusted: the tenant value the "
                         "client asks for, trusted without a lookup")
    ap.add_argument("--block", choices=sorted(BLOCKS), default=None,
                    help="the finished block for the page; omit for a "
                         "person's terminal output")
    args = ap.parse_args()

    if args.untrusted and not args.tenant:
        raise SystemExit("--untrusted needs --tenant")
    if args.profile and (args.untrusted or args.retriever != "hybrid"):
        raise SystemExit("--profile is the trusted route through the hybrid "
                         "request; it takes neither --untrusted nor another retriever")
    if args.omit_tenant and not args.profile:
        raise SystemExit("--omit-tenant only has meaning with --profile")
    if (args.block == "refusal") != bool(args.omit_tenant):
        raise SystemExit("--block refusal goes with --omit-tenant, and only with it")
    if args.tenant and not args.untrusted:
        raise SystemExit("--tenant only has meaning with --untrusted")

    users = load_users(args.users)
    if args.untrusted:
        print(f"WARNING --untrusted: the filter is tenant_id = {args.tenant!r}, "
              f"taken from the request rather than from {args.user!r}'s "
              f"registry entry. A trusted endpoint never does this; this "
              f"path exists to give leakage_test.py a case that detects.",
              file=sys.stderr)
        clause = clause_for_allowed([args.tenant])
    else:
        allowed = allowed_set(users, args.user)
        clause = clause_for_allowed(allowed)

    app = Vespa(args.endpoint)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    if args.profile:
        if allowed == "*":
            raise SystemExit(f"{args.user!r} may see every seller; the `{PROFILE}` "
                             "profile always filters, so that account uses the plain route")
        request = build_profile_request(args.query, args.hits, allowed)
        if args.omit_tenant:
            del request["tenant"]
            try:
                app.query(None, ranking=None, hits=args.hits, **request)
            except RuntimeError as exc:
                message = vespa_error_message(str(exc))
                print(refusal_block(message, args.user))
                return 0
            raise SystemExit("the profile answered a request without `tenant` - "
                             "it should have refused it")
        # ranking.profile comes from the query profile itself; nothing else is sent
        r = app.query(None, ranking=None, hits=args.hits, **request)
    else:
        request = build_authorized_request(args.retriever, args.query, args.hits, clause)
        r = app.query(ranking=RANKING[args.retriever], hits=args.hits, **request)

    if args.block:
        label = f"{args.retriever} via query profile {PROFILE}" if args.profile else args.retriever
        print(BLOCKS[args.block](r, args.query, args.user, label, deployed.embedder()))
        return 0

    print(f"{r.total:,} matched, showing {len(r.hits)}\n", file=sys.stderr)
    for i, hit in enumerate(r.hits, 1):
        tenant = hit.fields.get("tenant_id", "")
        title = hit.fields.get("title", "")
        print(f"{i:>2}. {hit.relevance:8.4f}  tenant={tenant!r:24}  {title[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
