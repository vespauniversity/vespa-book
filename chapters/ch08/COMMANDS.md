# ch08 commands

Every command this chapter's reports were written by, verbatim: one line the command, one line the file it writes, in the order they were run; a line starting with `#` says why the command after it is there, or why a run is not.

## A. The ladder
.venv/bin/python chapters/ch08/derive_tenants.py --out chapters/ch08/expected/tenants.json --users-out chapters/ch08/expected/users.json
chapters/ch08/expected/tenants.json, chapters/ch08/expected/users.json

.venv/bin/python chapters/ch08/derive_tenants.py --from chapters/ch08/expected/tenants.json --block ladder > chapters/ch08/expected/ladder.block.md
chapters/ch08/expected/ladder.block.md

## B. Filtered ANN — agreement and latency
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-none-default.json
chapters/ch08/expected/validation-filtered-ann-none-default.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --from chapters/ch08/expected/validation-filtered-ann-none-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-none-default.block.md
chapters/ch08/expected/validation-filtered-ann-none-default.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy pre --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_description-pre.json
chapters/ch08/expected/validation-filtered-ann-has_description-pre.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy pre --from chapters/ch08/expected/validation-filtered-ann-has_description-pre.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_description-pre.block.md
chapters/ch08/expected/validation-filtered-ann-has_description-pre.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy post --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_description-post.json
chapters/ch08/expected/validation-filtered-ann-has_description-post.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy post --from chapters/ch08/expected/validation-filtered-ann-has_description-post.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_description-post.block.md
chapters/ch08/expected/validation-filtered-ann-has_description-post.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_description-default.json
chapters/ch08/expected/validation-filtered-ann-has_description-default.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy default --from chapters/ch08/expected/validation-filtered-ann-has_description-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_description-default.block.md
chapters/ch08/expected/validation-filtered-ann-has_description-default.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy pre --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_brand-pre.json
chapters/ch08/expected/validation-filtered-ann-has_brand-pre.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy pre --from chapters/ch08/expected/validation-filtered-ann-has_brand-pre.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_brand-pre.block.md
chapters/ch08/expected/validation-filtered-ann-has_brand-pre.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy post --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_brand-post.json
chapters/ch08/expected/validation-filtered-ann-has_brand-post.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy post --from chapters/ch08/expected/validation-filtered-ann-has_brand-post.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_brand-post.block.md
chapters/ch08/expected/validation-filtered-ann-has_brand-post.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_brand-default.json
chapters/ch08/expected/validation-filtered-ann-has_brand-default.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy default --from chapters/ch08/expected/validation-filtered-ann-has_brand-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_brand-default.block.md
chapters/ch08/expected/validation-filtered-ann-has_brand-default.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy pre --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-marketplace-pre.json
chapters/ch08/expected/validation-filtered-ann-marketplace-pre.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy pre --from chapters/ch08/expected/validation-filtered-ann-marketplace-pre.json --block rung > chapters/ch08/expected/validation-filtered-ann-marketplace-pre.block.md
chapters/ch08/expected/validation-filtered-ann-marketplace-pre.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy post --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-marketplace-post.json
chapters/ch08/expected/validation-filtered-ann-marketplace-post.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy post --from chapters/ch08/expected/validation-filtered-ann-marketplace-post.json --block rung > chapters/ch08/expected/validation-filtered-ann-marketplace-post.block.md
chapters/ch08/expected/validation-filtered-ann-marketplace-post.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-marketplace-default.json
chapters/ch08/expected/validation-filtered-ann-marketplace-default.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy default --from chapters/ch08/expected/validation-filtered-ann-marketplace-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-marketplace-default.block.md
chapters/ch08/expected/validation-filtered-ann-marketplace-default.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy pre_full --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-marketplace-pre_full.json
chapters/ch08/expected/validation-filtered-ann-marketplace-pre_full.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy pre_full --from chapters/ch08/expected/validation-filtered-ann-marketplace-pre_full.json --block rung > chapters/ch08/expected/validation-filtered-ann-marketplace-pre_full.block.md
chapters/ch08/expected/validation-filtered-ann-marketplace-pre_full.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy pre --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-nike-pre.json
chapters/ch08/expected/validation-filtered-ann-nike-pre.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy pre --from chapters/ch08/expected/validation-filtered-ann-nike-pre.json --block rung > chapters/ch08/expected/validation-filtered-ann-nike-pre.block.md
chapters/ch08/expected/validation-filtered-ann-nike-pre.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy post --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-nike-post.json
chapters/ch08/expected/validation-filtered-ann-nike-post.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy post --from chapters/ch08/expected/validation-filtered-ann-nike-post.json --block rung > chapters/ch08/expected/validation-filtered-ann-nike-post.block.md
chapters/ch08/expected/validation-filtered-ann-nike-post.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-nike-default.json
chapters/ch08/expected/validation-filtered-ann-nike-default.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --from chapters/ch08/expected/validation-filtered-ann-nike-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-nike-default.block.md
chapters/ch08/expected/validation-filtered-ann-nike-default.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy pre_full --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-nike-pre_full.json
chapters/ch08/expected/validation-filtered-ann-nike-pre_full.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy pre_full --from chapters/ch08/expected/validation-filtered-ann-nike-pre_full.json --block rung > chapters/ch08/expected/validation-filtered-ann-nike-pre_full.block.md
chapters/ch08/expected/validation-filtered-ann-nike-pre_full.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy pre --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-small_brand-pre.json
chapters/ch08/expected/validation-filtered-ann-small_brand-pre.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy pre --from chapters/ch08/expected/validation-filtered-ann-small_brand-pre.json --block rung > chapters/ch08/expected/validation-filtered-ann-small_brand-pre.block.md
chapters/ch08/expected/validation-filtered-ann-small_brand-pre.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy post --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-small_brand-post.json
chapters/ch08/expected/validation-filtered-ann-small_brand-post.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy post --from chapters/ch08/expected/validation-filtered-ann-small_brand-post.json --block rung > chapters/ch08/expected/validation-filtered-ann-small_brand-post.block.md
chapters/ch08/expected/validation-filtered-ann-small_brand-post.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-small_brand-default.json
chapters/ch08/expected/validation-filtered-ann-small_brand-default.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy default --from chapters/ch08/expected/validation-filtered-ann-small_brand-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-small_brand-default.block.md
chapters/ch08/expected/validation-filtered-ann-small_brand-default.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy pre_full --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-small_brand-pre_full.json
chapters/ch08/expected/validation-filtered-ann-small_brand-pre_full.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy pre_full --from chapters/ch08/expected/validation-filtered-ann-small_brand-pre_full.json --block rung > chapters/ch08/expected/validation-filtered-ann-small_brand-pre_full.block.md
chapters/ch08/expected/validation-filtered-ann-small_brand-pre_full.block.md

# `exact` (approximateThreshold 1.0: the filter selects, every candidate is scored) on the two rungs where Vespa's defaults do not fall back to it by themselves — its latency is what that fallback would cost there. Not run on `none` (without a filter the threshold does not apply), nor on `nike` / `small_brand`, whose `default` row is already `exact`, nor on `has_brand`, where the graph walk is the ordinary one and `exact` would only repeat `has_description`'s point.
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy exact --explore 0 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-marketplace-exact.json
chapters/ch08/expected/validation-filtered-ann-marketplace-exact.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy exact --from chapters/ch08/expected/validation-filtered-ann-marketplace-exact.json --block rung > chapters/ch08/expected/validation-filtered-ann-marketplace-exact.block.md
chapters/ch08/expected/validation-filtered-ann-marketplace-exact.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy exact --explore 0 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_description-exact.json
chapters/ch08/expected/validation-filtered-ann-has_description-exact.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy exact --from chapters/ch08/expected/validation-filtered-ann-has_description-exact.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_description-exact.block.md
chapters/ch08/expected/validation-filtered-ann-has_description-exact.block.md

# `pre_full` is not run on `has_description` / `has_brand`: both sit above the 0.2 filter-first threshold, where the extra setting has nothing to switch off, so it would repeat `pre`'s reports.

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-none-default-tail.json
chapters/ch08/expected/validation-filtered-ann-none-default-tail.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --from chapters/ch08/expected/validation-filtered-ann-none-default-tail.json --block rung > chapters/ch08/expected/validation-filtered-ann-none-default-tail.block.md
chapters/ch08/expected/validation-filtered-ann-none-default-tail.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --from chapters/ch08/expected/validation-filtered-ann-*.json --block summary --at-explore 0 > chapters/ch08/expected/validation-filtered-ann-summary-explore0.block.md
chapters/ch08/expected/validation-filtered-ann-summary-explore0.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --from chapters/ch08/expected/validation-filtered-ann-*.json --block summary --at-explore 500 > chapters/ch08/expected/validation-filtered-ann-summary-explore500.block.md
chapters/ch08/expected/validation-filtered-ann-summary-explore500.block.md

## C. Latency under three retrievers — nike and no filter
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --retriever lexical --explore 0 --passes 3 --out chapters/ch08/expected/validation-filtered-latency-nike-lexical.json
chapters/ch08/expected/validation-filtered-latency-nike-lexical.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --retriever lexical --from chapters/ch08/expected/validation-filtered-latency-nike-lexical.json --block rung > chapters/ch08/expected/validation-filtered-latency-nike-lexical.block.md
chapters/ch08/expected/validation-filtered-latency-nike-lexical.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --retriever hybrid --explore 0 --passes 3 --out chapters/ch08/expected/validation-filtered-latency-nike-hybrid.json
chapters/ch08/expected/validation-filtered-latency-nike-hybrid.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --retriever hybrid --from chapters/ch08/expected/validation-filtered-latency-nike-hybrid.json --block rung > chapters/ch08/expected/validation-filtered-latency-nike-hybrid.block.md
chapters/ch08/expected/validation-filtered-latency-nike-hybrid.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --retriever lexical --explore 0 --passes 3 --out chapters/ch08/expected/validation-filtered-latency-none-lexical.json
chapters/ch08/expected/validation-filtered-latency-none-lexical.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --retriever lexical --from chapters/ch08/expected/validation-filtered-latency-none-lexical.json --block rung > chapters/ch08/expected/validation-filtered-latency-none-lexical.block.md
chapters/ch08/expected/validation-filtered-latency-none-lexical.block.md

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --retriever hybrid --explore 0 --passes 3 --out chapters/ch08/expected/validation-filtered-latency-none-hybrid.json
chapters/ch08/expected/validation-filtered-latency-none-hybrid.json

.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --retriever hybrid --from chapters/ch08/expected/validation-filtered-latency-none-hybrid.json --block rung > chapters/ch08/expected/validation-filtered-latency-none-hybrid.block.md
chapters/ch08/expected/validation-filtered-latency-none-hybrid.block.md

## D. Leakage
.venv/bin/python chapters/ch08/leakage_test.py --split validation --users chapters/ch08/expected/users.json --hits 10 --out chapters/ch08/expected/leakage-validation.json
chapters/ch08/expected/leakage-validation.json

.venv/bin/python chapters/ch08/leakage_test.py --split validation --from chapters/ch08/expected/leakage-validation.json --block leakage > chapters/ch08/expected/leakage-validation.block.md
chapters/ch08/expected/leakage-validation.block.md

## E. Demonstration
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_linear --hits 5 --block query > chapters/ch08/expected/query-running-shoes.block.md
chapters/ch08/expected/query-running-shoes.block.md

.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_linear --hits 5 --where 'tenant_id contains "nike"' --block query > chapters/ch08/expected/query-running-shoes-nike.block.md
chapters/ch08/expected/query-running-shoes-nike.block.md

.venv/bin/python chapters/ch08/authorized_query.py --user nike_staff --query "running shoes" --retriever hybrid --hits 5 --block hits > chapters/ch08/expected/authorized-running-shoes-nike_staff.block.md
chapters/ch08/expected/authorized-running-shoes-nike_staff.block.md

# the same account through the deployed `tenant` query profile: the request carries no YQL, only the query text, the vector, `hits` and the typed `tenant` value the endpoint derived
.venv/bin/python chapters/ch08/authorized_query.py --user nike_staff --query "running shoes" --retriever hybrid --hits 5 --profile --block hits > chapters/ch08/expected/authorized-running-shoes-nike_staff-profile.block.md
chapters/ch08/expected/authorized-running-shoes-nike_staff-profile.block.md

# the same request with the mandatory `tenant` value left out: the profile refuses it before matching; the block is Vespa's answer
.venv/bin/python chapters/ch08/authorized_query.py --user nike_staff --query "running shoes" --retriever hybrid --hits 5 --profile --omit-tenant --block refusal > chapters/ch08/expected/authorized-profile-missing-tenant.block.md
chapters/ch08/expected/authorized-profile-missing-tenant.block.md

## F. Memory
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --out chapters/ch08/expected/memory.json
chapters/ch08/expected/memory.json

.venv/bin/python shared/tools/memory.py --from chapters/ch08/expected/memory.json > chapters/ch08/expected/memory.block.md
chapters/ch08/expected/memory.block.md
