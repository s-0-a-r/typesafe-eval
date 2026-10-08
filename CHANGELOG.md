# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.3.0](https://github.com/s-0-a-r/typesafe-eval/compare/typesafe-eval-v1.2.1...typesafe-eval-v1.3.0) (2026-10-08)


### Features

* **safety:** add Japanese safety fixtures, phone features, and role email patterns ([01769ac](https://github.com/s-0-a-r/typesafe-eval/commit/01769acbb3a09cabcb0b9336188609e7f6f4db44))
* **safety:** add Japanese safety fixtures, phone features, and role email patterns ([37e1ac4](https://github.com/s-0-a-r/typesafe-eval/commit/37e1ac4bd99f68154cd30c9a53a5f40cdbceda18))


### Bug Fixes

* **presets:** align tech-spec has_test_plan prompt with labeling criteria to achieve 100% detection ([52be2a3](https://github.com/s-0-a-r/typesafe-eval/commit/52be2a38965424344473c1be1fb6f3394a72a13f))
* **presets:** align tech-spec has_test_plan prompt with labeling criteria to achieve 100% detection ([dc9d6e3](https://github.com/s-0-a-r/typesafe-eval/commit/dc9d6e362a5d63e32dcdccac45f1616229c18fee))


### Documentation

* **agents:** formalize pre-merge /boost review and release DoD checklist ([f712a46](https://github.com/s-0-a-r/typesafe-eval/commit/f712a46076bcdc92e7a966765c8c76c095d37b48))
* **agents:** formalize pre-merge /boost review and release DoD checklist in AGENTS.md ([e7b0c07](https://github.com/s-0-a-r/typesafe-eval/commit/e7b0c07371df82880a206c491d24ef06b156ee51))
* restructure README to elevate empirical reliability scope and practical scenarios ([19fa5af](https://github.com/s-0-a-r/typesafe-eval/commit/19fa5afbed32ef5c785b93f607c02579d29605a3))
* restructure README to prioritize empirical scope and practical gating scenarios ([385c40d](https://github.com/s-0-a-r/typesafe-eval/commit/385c40d40ddadb8c611ed31e3c6b5b6cb9b44030))
* **science:** publish empirical accuracy benchmarks for OpenAI Decisions API ([a38425f](https://github.com/s-0-a-r/typesafe-eval/commit/a38425f262ce513625569f5a1a56b905b4ddf1b7))
* **science:** publish empirical accuracy benchmarks for OpenAI Decisions API ([1f32614](https://github.com/s-0-a-r/typesafe-eval/commit/1f32614455c3d709968beff54be725c10d0a6606))

## [1.2.1](https://github.com/s-0-a-r/typesafe-eval/compare/typesafe-eval-v1.2.0...typesafe-eval-v1.2.1) (2026-10-08)


### Bug Fixes

* **science:** restore documentation integrity and wire validate multi-provider support ([7f7b6e1](https://github.com/s-0-a-r/typesafe-eval/commit/7f7b6e18daadd9e4e10297a4bf57eec9f46cc54b))
* **science:** restore documentation integrity and wire validate multi-provider support ([9ba1ced](https://github.com/s-0-a-r/typesafe-eval/commit/9ba1cedeecc9a8f3830ce48cca7187258140e1fe))

## [1.2.0](https://github.com/s-0-a-r/typesafe-eval/compare/typesafe-eval-v1.1.0...typesafe-eval-v1.2.0) (2026-10-08)


### Features

* **multimodal:** support markdown embedded diagrams via Decisions API ([#146](https://github.com/s-0-a-r/typesafe-eval/issues/146)) ([b8e53cf](https://github.com/s-0-a-r/typesafe-eval/commit/b8e53cfbdad58bcbf27a74fcb1ea851a17712fd2))
* **multimodal:** support markdown embedded diagrams via Decisions API ([#146](https://github.com/s-0-a-r/typesafe-eval/issues/146)) ([0c1068c](https://github.com/s-0-a-r/typesafe-eval/commit/0c1068c508abdb971506446b10bd84682b850d00))

## [1.1.0](https://github.com/s-0-a-r/typesafe-eval/compare/typesafe-eval-v1.0.0...typesafe-eval-v1.1.0) (2026-10-07)


### Features

* **ac-verification:** configure autonomous real CLI acceptance verification system ([#94](https://github.com/s-0-a-r/typesafe-eval/issues/94)) ([f7dc834](https://github.com/s-0-a-r/typesafe-eval/commit/f7dc83440c6843cd8ab268a693a26847183ce553))
* **agents:** Claude Code plugin and AGENTS.md guidance ([#35](https://github.com/s-0-a-r/typesafe-eval/issues/35)) ([#86](https://github.com/s-0-a-r/typesafe-eval/issues/86)) ([a67942f](https://github.com/s-0-a-r/typesafe-eval/commit/a67942f6ebf6184af6f359094a1541ee0c5754b1))
* **baseline:** add --baseline diff mode to detect score drops ([9502b57](https://github.com/s-0-a-r/typesafe-eval/commit/9502b57c3b1851d16e2ba68e22cf7c4c9aa62f7e))
* **baseline:** add --baseline diff mode to detect score drops (closes [#39](https://github.com/s-0-a-r/typesafe-eval/issues/39)) ([1185323](https://github.com/s-0-a-r/typesafe-eval/commit/1185323b7a832e44a7955c8efde9f2157148e7cb))
* **cache:** content-addressable evaluation result caching (--cache / --no-cache) ([#116](https://github.com/s-0-a-r/typesafe-eval/issues/116)) ([5687a75](https://github.com/s-0-a-r/typesafe-eval/commit/5687a75fbf6f99c89343c59ebb08c2320d3223e4)), closes [#112](https://github.com/s-0-a-r/typesafe-eval/issues/112)
* **chunking:** chunk long documents for presence questions ([#46](https://github.com/s-0-a-r/typesafe-eval/issues/46)) ([58b7c2c](https://github.com/s-0-a-r/typesafe-eval/commit/58b7c2c27fdaf4f9dd2e1abeb0f00dbe526c656f))
* **chunking:** chunk long documents for presence questions (Noul) ([d3bd671](https://github.com/s-0-a-r/typesafe-eval/commit/d3bd6718ef6d901894b3057db0d25ffb4226c3ff))
* **ci:** Phase 4 release automation via release-please, PyPI Trusted Publishing, and Python 3.14 CI ([#109](https://github.com/s-0-a-r/typesafe-eval/issues/109)) ([6a86088](https://github.com/s-0-a-r/typesafe-eval/commit/6a86088a97f05efd7dfc57facfab5fcd0b779269))
* **cli:** add file exclusion patterns (--exclude), config exclude list, and default ignores ([#118](https://github.com/s-0-a-r/typesafe-eval/issues/118)) ([4df7172](https://github.com/s-0-a-r/typesafe-eval/commit/4df717254660b59af2d5526ae6ec75e544ef90aa))
* **cli:** distinct exit codes and continue on file error ([0f8f5fe](https://github.com/s-0-a-r/typesafe-eval/commit/0f8f5fee2fbccda17d66cff750491c24de911723))
* **cli:** distinct exit codes and continue on file error (closes [#36](https://github.com/s-0-a-r/typesafe-eval/issues/36)) ([e4c346f](https://github.com/s-0-a-r/typesafe-eval/commit/e4c346f729cb4a0592d25ecda960fda1fdc576ab))
* **config:** support provider and model selection in project config ([#141](https://github.com/s-0-a-r/typesafe-eval/issues/141)) ([3f031cf](https://github.com/s-0-a-r/typesafe-eval/commit/3f031cfec0a30434e57a45670b28411db2fdb70e))
* **docs:** setup GitHub Pages deployment workflow and update v1.0.0 doc examples ([#130](https://github.com/s-0-a-r/typesafe-eval/issues/130)) ([b1c78c7](https://github.com/s-0-a-r/typesafe-eval/commit/b1c78c7ad641acd4a2269aae1eef9e14286d1e36))
* **dry-run:** show MOCK in table/json/markdown, verdict N/A, exit 0 for every preset ([#45](https://github.com/s-0-a-r/typesafe-eval/issues/45)) ([40be9d2](https://github.com/s-0-a-r/typesafe-eval/commit/40be9d2d8106761362fec7522b1d867941e1a34b))
* **dry-run:** show MOCK in table/json/markdown, verdict N/A, exit 0 for every preset ([#45](https://github.com/s-0-a-r/typesafe-eval/issues/45)) ([541854f](https://github.com/s-0-a-r/typesafe-eval/commit/541854f648486635efce96279eb7bb2c5a6c3f4f))
* **evaluator:** extensible preflight binding and transparent override reporting ([d5e35ec](https://github.com/s-0-a-r/typesafe-eval/commit/d5e35ec429ccad882c4ba25bbacec9023dcde847))
* **evaluator:** extensible preflight binding and transparent override reporting (closes [#7](https://github.com/s-0-a-r/typesafe-eval/issues/7), closes [#8](https://github.com/s-0-a-r/typesafe-eval/issues/8), closes [#9](https://github.com/s-0-a-r/typesafe-eval/issues/9), closes [#11](https://github.com/s-0-a-r/typesafe-eval/issues/11)) ([f6e357f](https://github.com/s-0-a-r/typesafe-eval/commit/f6e357fc9dcbda76362c7d8d993011bbe6fe2a40))
* **evaluator:** support pii preflight override and preserve composite weight for overridden questions ([a763c3d](https://github.com/s-0-a-r/typesafe-eval/commit/a763c3d62ff855c857effee0e7860d527d0a39de))
* **evaluator:** support pii preflight override and preserve composite weight for overridden questions (closes [#24](https://github.com/s-0-a-r/typesafe-eval/issues/24), closes [#25](https://github.com/s-0-a-r/typesafe-eval/issues/25)) ([53a89f7](https://github.com/s-0-a-r/typesafe-eval/commit/53a89f7de6720276323487dda16beb18f8a49810))
* initial release of typesafe-eval v0.1.0 ([6979f7b](https://github.com/s-0-a-r/typesafe-eval/commit/6979f7bb99359bfce32f802b6256f302c7301e11))
* **integration:** agent-agnostic JSON contract, pre-commit hook and GitHub Action ([#34](https://github.com/s-0-a-r/typesafe-eval/issues/34)) ([#85](https://github.com/s-0-a-r/typesafe-eval/issues/85)) ([96dcf42](https://github.com/s-0-a-r/typesafe-eval/commit/96dcf42096432b4e2404268f5b8c2794d8b9cc53))
* multi-provider decision engine with OpenAI Decisions API support ([#139](https://github.com/s-0-a-r/typesafe-eval/issues/139)) ([#140](https://github.com/s-0-a-r/typesafe-eval/issues/140)) ([11ca756](https://github.com/s-0-a-r/typesafe-eval/commit/11ca756337add20df0196da4bef9203a3256b882))
* **offline:** offline and rules-only evaluation mode (--offline / --rules-only) ([#114](https://github.com/s-0-a-r/typesafe-eval/issues/114)) ([536153b](https://github.com/s-0-a-r/typesafe-eval/commit/536153bd55bed45619d8b1cf32273237223160ed))
* **openai:** align OpenAIDecisionsProvider with verified Decisions API schema ([#142](https://github.com/s-0-a-r/typesafe-eval/issues/142)) ([fe16fe1](https://github.com/s-0-a-r/typesafe-eval/commit/fe16fe1dbae96d09106ceae2c482be49896c4247))
* **position:** line and column mapping for PII & secret violations with GitHub Actions annotations (-f github) ([#113](https://github.com/s-0-a-r/typesafe-eval/issues/113)) ([d15c2df](https://github.com/s-0-a-r/typesafe-eval/commit/d15c2dfbcff68f2061d3a1a4ebb7844f1724ddb7))
* **presets:** add design_doc and pr_description checklist presets ([#41](https://github.com/s-0-a-r/typesafe-eval/issues/41)) ([1e4e6e1](https://github.com/s-0-a-r/typesafe-eval/commit/1e4e6e17ed6373bcf1acd6267724ac4d9e46d293))
* **presets:** built-in checklists design_doc and pr_description ([#41](https://github.com/s-0-a-r/typesafe-eval/issues/41)) ([c38d68d](https://github.com/s-0-a-r/typesafe-eval/commit/c38d68d0196281efea04dab08b7f487682600400))
* **presets:** refine confidentiality_risk criteria to 4 levels (Round 1) ([5e11efa](https://github.com/s-0-a-r/typesafe-eval/commit/5e11efa98353fdfad5fbb72d5925f70cbffcd266))
* **presets:** remove the two tech-spec Scores that did not track removed content ([#43](https://github.com/s-0-a-r/typesafe-eval/issues/43)) ([ef4803d](https://github.com/s-0-a-r/typesafe-eval/commit/ef4803d7ada2db2eb0b4663faa60f6c8d228dc1f))
* **presets:** round 1 wording for the checklists ([d0efa2a](https://github.com/s-0-a-r/typesafe-eval/commit/d0efa2a58f32c1a55797b0e288298ed1d7d00946))
* **presets:** round 1 wording for the design_doc and pr_description checklists ([#41](https://github.com/s-0-a-r/typesafe-eval/issues/41)) ([08a4a26](https://github.com/s-0-a-r/typesafe-eval/commit/08a4a263527a7084d216ea419909d1f916f63328))
* **presets:** support custom role_emails glob patterns in preset sanitizer config ([255ccd9](https://github.com/s-0-a-r/typesafe-eval/commit/255ccd9eb68ac62749d9eb2da08a61aff149ead9))
* **presets:** support custom role_emails glob patterns in preset sanitizer config ([b609a3c](https://github.com/s-0-a-r/typesafe-eval/commit/b609a3cbc298e5d510e150c2de264e9d05209231))
* **presets:** trim tech-spec to has_test_plan and readiness ([0a56f28](https://github.com/s-0-a-r/typesafe-eval/commit/0a56f28c90faf0cfeb867d6ee1099bb96b952418))
* **quality:** redefine quality preset as regression detection ([#42](https://github.com/s-0-a-r/typesafe-eval/issues/42)) ([f87de0c](https://github.com/s-0-a-r/typesafe-eval/commit/f87de0cfe7836255b188ada0f47a088864f21d9d))
* **quality:** redefine quality preset as regression detection with warnings ([#42](https://github.com/s-0-a-r/typesafe-eval/issues/42)) ([8853c85](https://github.com/s-0-a-r/typesafe-eval/commit/8853c85db0b3777711b0f77be54e73a5371c6f90))
* **reporter:** mark scores within 0.1 of threshold as near_threshold ([#44](https://github.com/s-0-a-r/typesafe-eval/issues/44)) ([dd8d28c](https://github.com/s-0-a-r/typesafe-eval/commit/dd8d28c89fdbabbe0fbb84992534f0c05b082e47))
* **reporter:** mark values within 0.1 of threshold as near_threshold ([#44](https://github.com/s-0-a-r/typesafe-eval/issues/44)) ([e132645](https://github.com/s-0-a-r/typesafe-eval/commit/e132645e971d1b0593b49dd5fee9ba2d66d07dd2))
* **sanitizer:** contextual email PII via state features and dynamic batching ([612f1eb](https://github.com/s-0-a-r/typesafe-eval/commit/612f1ebfb0cfc8242e6568733ce729ca940880d5))
* **sanitizer:** contextual email PII via state features and dynamic batching (closes [#30](https://github.com/s-0-a-r/typesafe-eval/issues/30)) ([e2432e1](https://github.com/s-0-a-r/typesafe-eval/commit/e2432e18830f795027d9ceb8b7ab28dcf4c72663))
* **sanitizer:** per-candidate Noul for phone, ip, url, secrets and decouple detection from masking ([c883916](https://github.com/s-0-a-r/typesafe-eval/commit/c8839168d3ff6f513d06eb03f976592f973b1778))
* **sanitizer:** per-candidate Noul for phone, ip, url, secrets and decouple detection from masking (closes [#40](https://github.com/s-0-a-r/typesafe-eval/issues/40)) ([22e585b](https://github.com/s-0-a-r/typesafe-eval/commit/22e585b4c872e6e3ba04120d11301613b850db94))
* **skills:** add Antigravity code-review skill with /boost workflow ([#88](https://github.com/s-0-a-r/typesafe-eval/issues/88)) ([863abe6](https://github.com/s-0-a-r/typesafe-eval/commit/863abe6eabfe2382362a6eb34eeb6cf67055f65f))
* validate preset preflight field and make override probability semantics consistent ([6598177](https://github.com/s-0-a-r/typesafe-eval/commit/65981775c6d14897f5ebdbf18c9b72308fbb8120))
* validate preset preflight field and make override probability semantics consistent (closes [#19](https://github.com/s-0-a-r/typesafe-eval/issues/19), closes [#21](https://github.com/s-0-a-r/typesafe-eval/issues/21)) ([ee90963](https://github.com/s-0-a-r/typesafe-eval/commit/ee90963136ecb7ec0aa9ec3eb65deb46c94e2f52))
* **validate:** add --mask-secrets / --no-mask flag to validate ([0f85bbd](https://github.com/s-0-a-r/typesafe-eval/commit/0f85bbddd7603addec4c29159fee193c5590e6a4))
* **validate:** add validate command, labels runner, and ablate helper ([600b461](https://github.com/s-0-a-r/typesafe-eval/commit/600b461e333eb1adea87ef879f16015dfa204359))
* **validate:** add validate command, labels runner, and ablate helper (closes [#38](https://github.com/s-0-a-r/typesafe-eval/issues/38)) ([cdc7f99](https://github.com/s-0-a-r/typesafe-eval/commit/cdc7f99fb7271985794b143725cf6b9f0f66d5f2))
* **validator:** make tech-spec runnable with validate ([#43](https://github.com/s-0-a-r/typesafe-eval/issues/43)) ([9b99760](https://github.com/s-0-a-r/typesafe-eval/commit/9b99760da77f403dab8f5ab0af33e333368f41ba))
* **validator:** make tech-spec runnable with validate and choice distributions ([#43](https://github.com/s-0-a-r/typesafe-eval/issues/43)) ([9711306](https://github.com/s-0-a-r/typesafe-eval/commit/9711306360539053a941f9b6ac3d6c50251c0318))
* **validator:** pair_guard_down_tolerance for down pairs (default 0, unchanged behavior) ([7ed2775](https://github.com/s-0-a-r/typesafe-eval/commit/7ed2775ce8d70db9d5ca80ee6a88995f4f21d0e5))


### Bug Fixes

* address review round 1 on the release fixes ([#78](https://github.com/s-0-a-r/typesafe-eval/issues/78)) ([185e10c](https://github.com/s-0-a-r/typesafe-eval/commit/185e10c14dd9611d648d4039aac8245d1d1863a1))
* address review round 1 on the release leftovers ([#81](https://github.com/s-0-a-r/typesafe-eval/issues/81)) ([fd41761](https://github.com/s-0-a-r/typesafe-eval/commit/fd41761ca5be4e96f15095c24095efca34d24796))
* address review round 2 on the release fixes ([#78](https://github.com/s-0-a-r/typesafe-eval/issues/78)) ([452bb8b](https://github.com/s-0-a-r/typesafe-eval/commit/452bb8becf742e916f2b78de484055b9970d3707))
* **baseline:** reject dry-run baselines and preset mismatches with exit 2 (B) ([d605c86](https://github.com/s-0-a-r/typesafe-eval/commit/d605c86c1cc49882ef2920a916a78e6b7d7df419))
* **chunking:** raise runtime error if preset Noul missing across all chunks ([add019f](https://github.com/s-0-a-r/typesafe-eval/commit/add019f42bdca1bd269ed3978f4d19ff04d2c7f4))
* **ci:** make tests importable under pytest and run CI on release PRs ([da6c8b3](https://github.com/s-0-a-r/typesafe-eval/commit/da6c8b317a946665c3b71216b4a2d099dea4268d))
* **ci:** put the repository root on the pytest path so tests can import scripts/ ([7a46344](https://github.com/s-0-a-r/typesafe-eval/commit/7a46344e63cd549731d9f2518ebe0a0100079e1a))
* **client,sanitizer:** refine secret candidate prompt and exclude example URLs and IPs from PII counts ([0140e0f](https://github.com/s-0-a-r/typesafe-eval/commit/0140e0f27b198c626a812ace9169260238bd4ffc))
* **client:** match candidate questions in unmasked chunks ([#40](https://github.com/s-0-a-r/typesafe-eval/issues/40)) ([491b62f](https://github.com/s-0-a-r/typesafe-eval/commit/491b62f2fa5f67876ad0ebe8bde948499d8e0318))
* **client:** raise error when question is missing from response ([0b4c6c3](https://github.com/s-0-a-r/typesafe-eval/commit/0b4c6c3a3645bb7ac2e29c1b363e4a53d74f31c0))
* **client:** treat unplaced candidates as present in every chunk (A1) ([3a36b57](https://github.com/s-0-a-r/typesafe-eval/commit/3a36b575330c7e6bf706b17f56259196ac5fab63))
* **cli:** exit with code 3 on file error in dry-run mode ([d723619](https://github.com/s-0-a-r/typesafe-eval/commit/d723619e7109d8111651ff085359675273658fd9))
* correct unplaced warning and dry-run baseline messages ([#81](https://github.com/s-0-a-r/typesafe-eval/issues/81)) ([2bbef96](https://github.com/s-0-a-r/typesafe-eval/commit/2bbef96536b5e420803bcbb1d3868ae65a85e772))
* **docs:** fix LaTeX MathJax rendering and table header pipe formatting in noise calibration ([#133](https://github.com/s-0-a-r/typesafe-eval/issues/133)) ([d620372](https://github.com/s-0-a-r/typesafe-eval/commit/d62037237bc593329222056ff4d7acd3466c60da))
* **docs:** replace broken PyPI badges with release badges and add doc URLs ([4d39e2a](https://github.com/s-0-a-r/typesafe-eval/commit/4d39e2a4e6777568ce91da9629a76553c55ca39b))
* **docs:** replace broken PyPI badges with release badges and add doc URLs ([b27ab5e](https://github.com/s-0-a-r/typesafe-eval/commit/b27ab5e1e45bfeaedd6888aad2f791253ba7302e))
* **feasibility:** report null AUC and false-alarm rate when there is no held-out set ([1115085](https://github.com/s-0-a-r/typesafe-eval/commit/11150853819de0bc7b569e3cf5ad9464704a5e09))
* **near_threshold:** cover per-candidate nouls and restore module docstring ([#44](https://github.com/s-0-a-r/typesafe-eval/issues/44)) ([2863c05](https://github.com/s-0-a-r/typesafe-eval/commit/2863c05c4c8d92d4af021d0efaf0e3d61f9de8fe))
* **presets:** refine confidentiality_risk criteria and add validation fixtures ([#53](https://github.com/s-0-a-r/typesafe-eval/issues/53)) ([de61789](https://github.com/s-0-a-r/typesafe-eval/commit/de6178928021d6af674d6ffba79821ea2c19e7d7))
* **quality:** address review items for warning behavior and feasibility check ([#42](https://github.com/s-0-a-r/typesafe-eval/issues/42)) ([4f34573](https://github.com/s-0-a-r/typesafe-eval/commit/4f345731dc7d365a6fd3875a04b19bc579f76651))
* release review findings for v0.4.0 ([4b2ef99](https://github.com/s-0-a-r/typesafe-eval/commit/4b2ef994043cb347351eb43bb1279214448f2b81))
* remaining release review items for v0.4.0 ([70996c2](https://github.com/s-0-a-r/typesafe-eval/commit/70996c2d0e39ad73e83c5efa9ec4dbbae29fcb13))
* **safety:** detect secrets and PII in HTML comments before stripping ([#80](https://github.com/s-0-a-r/typesafe-eval/issues/80)) ([#84](https://github.com/s-0-a-r/typesafe-eval/issues/84)) ([41ab66e](https://github.com/s-0-a-r/typesafe-eval/commit/41ab66e2466442f9e2304b12e6e4054381ff6a15))
* **safety:** preserve detection signal during pre-flight masking (closes [#2](https://github.com/s-0-a-r/typesafe-eval/issues/2)) ([#4](https://github.com/s-0-a-r/typesafe-eval/issues/4)) ([7672712](https://github.com/s-0-a-r/typesafe-eval/commit/7672712a30715c6da205b8363d6667a279c0aa25))
* **sanitizer,safety:** decouple candidate PII/secrets from document-level questions and fix URL loopback ([82c5f3a](https://github.com/s-0-a-r/typesafe-eval/commit/82c5f3ac16a16a21dc516331dcb785b42db91872))
* **sanitizer:** bound next chunk start search to preserve overlap with small max_chars (A3, A4) ([f658a8a](https://github.com/s-0-a-r/typesafe-eval/commit/f658a8a5b7098d396822992b8feded3af00e8b43))
* **sanitizer:** drop HTML comments before evaluation, as a rendered page does ([9c16105](https://github.com/s-0-a-r/typesafe-eval/commit/9c16105967622d4f691e2eb87eaa1591b32b592f))
* **sanitizer:** expand role email local parts and match organizational affixes ([1a23c60](https://github.com/s-0-a-r/typesafe-eval/commit/1a23c60bdc009c314cfb1e525631f5aab551679d))
* **sanitizer:** expand role email local parts and match organizational affixes (closes [#27](https://github.com/s-0-a-r/typesafe-eval/issues/27)) ([5370856](https://github.com/s-0-a-r/typesafe-eval/commit/5370856b742235b7e3053f874191e7a732e7d45f))
* **sanitizer:** improve pattern precision and classify personal vs role emails ([a2c5350](https://github.com/s-0-a-r/typesafe-eval/commit/a2c5350e8da36b8019cc82ba6250bfeb15026253))
* **sanitizer:** improve pattern precision and classify personal vs role emails (closes [#6](https://github.com/s-0-a-r/typesafe-eval/issues/6), closes [#10](https://github.com/s-0-a-r/typesafe-eval/issues/10)) ([0f6dd10](https://github.com/s-0-a-r/typesafe-eval/commit/0f6dd10729dd8eb80c2f2d6dda123b5db1e74387))
* **sanitizer:** neutralize example tokens, consume bearer padding, and classify email domains (closes [#17](https://github.com/s-0-a-r/typesafe-eval/issues/17), closes [#18](https://github.com/s-0-a-r/typesafe-eval/issues/18), closes [#20](https://github.com/s-0-a-r/typesafe-eval/issues/20)) ([73f27ff](https://github.com/s-0-a-r/typesafe-eval/commit/73f27ffe7e68e317e20857e844b0f6d1901b0046))
* **sanitizer:** neutralize example tokens, fix bearer padding lookahead, and use email domain check ([43e2221](https://github.com/s-0-a-r/typesafe-eval/commit/43e22213f0d146e28952b93d839cee90607c4d9a))
* **sanitizer:** register placeholder syntax secrets in raw_mapping (A2) ([de67346](https://github.com/s-0-a-r/typesafe-eval/commit/de673469041234cd09db6c486866f0441b8ab3b9))
* **sanitizer:** remove raw domain from url features when masking is on ([#40](https://github.com/s-0-a-r/typesafe-eval/issues/40)) ([0f0fc1a](https://github.com/s-0-a-r/typesafe-eval/commit/0f0fc1aad197d0b67d4ca4551d6a8bb0559d7b9b))
* **scripts:** add utf-8 encoding and mutual exclusion in feasibility check (C) ([442e4d1](https://github.com/s-0-a-r/typesafe-eval/commit/442e4d1513a78e76e32ab95ad819f1875d74ba5f))
* tool fixes from the round 0 tuning run ([6d35184](https://github.com/s-0-a-r/typesafe-eval/commit/6d35184d70c885c4c4ca04f34afdd7ce449c5212))
* validate and baseline for risk questions and ID matching ([ad49401](https://github.com/s-0-a-r/typesafe-eval/commit/ad4940153dfd6dc250f8f65dc911dfec007d41d8))
* validate and baseline for risk questions and ID matching ([0e32464](https://github.com/s-0-a-r/typesafe-eval/commit/0e324648e14e7194c4aeb0a5785f340a8e6c22ea))
* **validate:** check API key before evaluating ([c1c0649](https://github.com/s-0-a-r/typesafe-eval/commit/c1c064954c6a14ec65eb6862fb52f390418e179d))
* **validate:** check API key before evaluating ([a53713d](https://github.com/s-0-a-r/typesafe-eval/commit/a53713de41ccda50b3541e75130f3af974db8de9))
* **validate:** remove mock inspection and isolate tests from env ([5682528](https://github.com/s-0-a-r/typesafe-eval/commit/56825283cbb7eb4f4331680bf06e55f01df878f9))
* **validate:** show MOCK in table/markdown, set mock=true and all_passed=null in JSON on --dry-run ([#45](https://github.com/s-0-a-r/typesafe-eval/issues/45)) ([b61b976](https://github.com/s-0-a-r/typesafe-eval/commit/b61b9764f5dab9cc18b1ed6d0705e70300bae284))
* **validation:** correct the feasibility columns in summarize_results.py ([ee4ed45](https://github.com/s-0-a-r/typesafe-eval/commit/ee4ed45a27aa62586490938eb3b1ec3ea9c24d01))
* **validation:** show the question in the pair-group table of summarize_results.py ([a4b53ed](https://github.com/s-0-a-r/typesafe-eval/commit/a4b53ed4d1fbc05cbc7aa57ebfdc09baeb859e02))
* **validator:** address PR 63 review comments ([#42](https://github.com/s-0-a-r/typesafe-eval/issues/42)) ([874665f](https://github.com/s-0-a-r/typesafe-eval/commit/874665fdaa5b02ad6dc2c5883507bc68d694ebe1))
* **validator:** address review items for tech-spec validation and question handling ([#43](https://github.com/s-0-a-r/typesafe-eval/issues/43)) ([79df709](https://github.com/s-0-a-r/typesafe-eval/commit/79df709a68f624e6e22eae14fe4c00d7e2a166e6))
* **validator:** fail down pairs only when mean delta strictly exceeds tolerance ([c822d1b](https://github.com/s-0-a-r/typesafe-eval/commit/c822d1bb458c52bfe4346266e9f028af1b36c9bc))
* **validator:** group pair results by kind and question ([af5f34e](https://github.com/s-0-a-r/typesafe-eval/commit/af5f34ebadb4d6f04220da8af340f7a35b3773f6))
* **validator:** implement pair CI gating, grouping, caching, and retries ([#42](https://github.com/s-0-a-r/typesafe-eval/issues/42)) ([16b1d1b](https://github.com/s-0-a-r/typesafe-eval/commit/16b1d1b131010370b822521ed8aa3300c493fd06))
* **validator:** implement pair CI gating, grouping, caching, and retries ([#42](https://github.com/s-0-a-r/typesafe-eval/issues/42)) ([256759b](https://github.com/s-0-a-r/typesafe-eval/commit/256759b2cedc7f5b10c04e1cfc306ac91f6206d9))
* **validator:** remove unused criteria.questions field ([e073e94](https://github.com/s-0-a-r/typesafe-eval/commit/e073e94ce088e903bd1c265542e5c73b31362305))
* **validator:** report unplaced warnings and fail masked mode matching bug ([#82](https://github.com/s-0-a-r/typesafe-eval/issues/82)) ([#83](https://github.com/s-0-a-r/typesafe-eval/issues/83)) ([2abbfec](https://github.com/s-0-a-r/typesafe-eval/commit/2abbfec524a41239462452130db7211d47a415ee))


### Documentation

* align README with measured results and restore omitted sections ([#47](https://github.com/s-0-a-r/typesafe-eval/issues/47)) ([0492dae](https://github.com/s-0-a-r/typesafe-eval/commit/0492dae904e33d2c0025513df3fbfa2ef50211f8))
* checklist status from the corpus measurement ([17c780b](https://github.com/s-0-a-r/typesafe-eval/commit/17c780ba08805c907519d933402c3d9279bd107e))
* checklist status from the corpus measurement; record the held-out result ([#41](https://github.com/s-0-a-r/typesafe-eval/issues/41)) ([e4e1626](https://github.com/s-0-a-r/typesafe-eval/commit/e4e16260758d36a01dcf12d8b1127efc71f552cc))
* clarify batching gain measurement for presets (closes [#1](https://github.com/s-0-a-r/typesafe-eval/issues/1)) ([#3](https://github.com/s-0-a-r/typesafe-eval/issues/3)) ([2ddc4d5](https://github.com/s-0-a-r/typesafe-eval/commit/2ddc4d5aedbdc2be170de5a897d22898f7819a45))
* clarify batching gain wording for 13 questions ([04f3438](https://github.com/s-0-a-r/typesafe-eval/commit/04f34388fb14a613cb40aa5e8de1505f5c4fc625))
* clarify batching gain wording for 13 questions (closes [#12](https://github.com/s-0-a-r/typesafe-eval/issues/12)) ([5113af1](https://github.com/s-0-a-r/typesafe-eval/commit/5113af1338304ea8a41d1e779c1b71c9196c4fc1))
* clarify free-mail bypass under --no-mask in known limitations ([9232a40](https://github.com/s-0-a-r/typesafe-eval/commit/9232a4087685b89e61f748042bae4425d78aa2c4))
* document multi-provider configuration, environment variables, and python API ([#143](https://github.com/s-0-a-r/typesafe-eval/issues/143)) ([783596d](https://github.com/s-0-a-r/typesafe-eval/commit/783596d55feb9b21dc6c74a00878a131e22594a2))
* **mkdocs:** setup Material for MkDocs documentation site and API guides ([#125](https://github.com/s-0-a-r/typesafe-eval/issues/125)) ([5d77d79](https://github.com/s-0-a-r/typesafe-eval/commit/5d77d79160c548f47d32950b64b707b199778c31))
* note the tool changes made after the recorded runs ([0715361](https://github.com/s-0-a-r/typesafe-eval/commit/071536163e0c5941f8e034efe53fe51be596fdb0))
* note the tool changes made after the recorded runs ([1f71ba4](https://github.com/s-0-a-r/typesafe-eval/commit/1f71ba424020b411742dacadd68320cf56e266b5))
* polish context-aware wording and document --no-mask limitation ([4de08e2](https://github.com/s-0-a-r/typesafe-eval/commit/4de08e2992310cb6a9c8ddb21fb7c256338f9dc5))
* **readme:** clean up What's New sections and update empirical noise calibration ([#124](https://github.com/s-0-a-r/typesafe-eval/issues/124)) ([2d069b0](https://github.com/s-0-a-r/typesafe-eval/commit/2d069b02f7c0dcda60fb9c09aa4cbc6ed2377908))
* record the quality held-out result ([6a14d86](https://github.com/s-0-a-r/typesafe-eval/commit/6a14d861710ee9c6403ae6bfd24720f40d71eff6))
* record the quality held-out result ([#42](https://github.com/s-0-a-r/typesafe-eval/issues/42)) ([d573819](https://github.com/s-0-a-r/typesafe-eval/commit/d573819beeb357ba88662fcc2b038914e0b2ebc6))
* record the reduced tech-spec measurement ([9442739](https://github.com/s-0-a-r/typesafe-eval/commit/9442739ebb167b6715a937750f5a77c48a28f278))
* record the reduced tech-spec measurement ([#43](https://github.com/s-0-a-r/typesafe-eval/issues/43)) ([51f4f38](https://github.com/s-0-a-r/typesafe-eval/commit/51f4f38dacd0e624c1bb4c2caf2e579c6424f000))
* record the tech-spec change and how the reduced preset is measured ([#43](https://github.com/s-0-a-r/typesafe-eval/issues/43)) ([4b390e0](https://github.com/s-0-a-r/typesafe-eval/commit/4b390e0ea11ed1f88616b1d4f60fa22d05269283))
* **science:** document empirical noise calibration for OpenAI Decisions API ([#144](https://github.com/s-0-a-r/typesafe-eval/issues/144)) ([9e9976f](https://github.com/s-0-a-r/typesafe-eval/commit/9e9976f9c8a1a18c9f46bf2c8d8495710fe86d90))
* separate CLI features from API properties and add non-goals ([#47](https://github.com/s-0-a-r/typesafe-eval/issues/47)) ([5352c0c](https://github.com/s-0-a-r/typesafe-eval/commit/5352c0cfbd36ef4dada306cafa8c7a00172cc077))
* separate CLI features from API properties and add non-goals ([#47](https://github.com/s-0-a-r/typesafe-eval/issues/47)) ([97b5dba](https://github.com/s-0-a-r/typesafe-eval/commit/97b5dbaaa134e85a11f691b36567788daccb9e74))
* update empirical noise calibration statistics from live TypeSafe API measurement ([#126](https://github.com/s-0-a-r/typesafe-eval/issues/126)) ([166e77f](https://github.com/s-0-a-r/typesafe-eval/commit/166e77f0710ba11a66d0e247372a7a84daa6d202))
* update limitations, noise figures, and CLI max-chars validation ([20492e0](https://github.com/s-0-a-r/typesafe-eval/commit/20492e07ce3c1c76f7a445c8122da2a7933d7f25))
* **validation:** refer to non-public documents by split, not by name ([050821b](https://github.com/s-0-a-r/typesafe-eval/commit/050821b0b80365deec017107c7b7e241003e2c1a))

## [1.0.0] - 2026-10-06

### Added
- **Official Documentation Site (Material for MkDocs)**:
  - Comprehensive documentation portal hosted at GitHub Pages with responsive Material design, dark/light theme, search, and code copying.
  - Complete guides: Installation, Quickstart, CLI Reference, Python API & Types, CI Integrations (GitHub Actions, pre-commit, Claude Code), Presets, and Scientific Noise Calibration.
  - Strict documentation build validation (`mkdocs build --strict`) integrated into CI.
- **Empirical Noise Calibration Matrix & Fixture Report**:
  - Live empirical evaluation of run-to-run variance on TypeSafe System One (`jev-1.13.0`) across all 5 built-in presets (60 evaluations, 396 pairwise comparisons).
  - Confirmed 99th percentile $|\Delta| = 0.030$ and max $|\Delta| = 0.040$, validating the statistical robustness of the $\pm 0.10$ threshold safety margin.
  - Automated reusable measurement CLI script (`scripts/measure_noise.py`) and artifact export (`tests/fixtures/noise_report.json`).
- **Comprehensive Production Hardening & Acceptance**:
  - 100% pass across all 18 Real CLI Acceptance Criteria (OS subprocess execution matrix).
  - 533 unit, integration, and property-based tests passing with strict typing (PEP 561 `py.typed`, mypy strict mode).
  - Cleaned up README.md with unified feature catalog and removed temporary release sections.

---

## [0.9.0] - 2026-10-06

### Added
- **File Exclusion Patterns & Default Ignores (`--exclude` / `-e`)**:
  - Repeatable `--exclude <pattern>` / `-e <pattern>` CLI flags supporting fnmatch / glob patterns.
  - Project configuration support via `exclude: [...]` in `.typesafe-eval.yaml` and `pyproject.toml` (`[tool.typesafe-eval]`).
  - Automatic filtering of standard build, dependency, and cache directories (`.git`, `node_modules`, `.venv`, `build`, `dist`, etc.) during glob resolution and git diff filtering.
  - Programmatic support via `evaluate_documents(paths, exclude=[...])`.
- **Offline Rules-Only Mode (`--offline` / `--rules-only`)**:
  - Pure local evaluation relying on deterministic rules (known credential patterns, AWS/Slack/GitHub tokens, free-mail PII) with zero network calls and no required `TYPESAFE_API_KEY`.
  - Ambiguous candidate fallback behavior producing soft informational notices instead of runtime errors.
  - Programmatic support via `evaluate(content, offline=True)` and `evaluate_documents(paths, offline=True)`.
- **Content-Addressable Result Caching (`--cache` / `--no-cache`)**:
  - Deterministic SHA-256 caching of evaluation results based on content, preset rules, model parameters, and options.
  - Configurable cache location via `--cache-dir` or `TYPESAFE_CACHE_DIR` (default: `.typesafe-eval-cache`).
  - Cache management CLI command: `typesafe-eval cache clear`.
  - Programmatic support via `evaluate_documents(paths, cache=True, cache_dir=...)`.
- **Line & Column Mapping & GitHub Actions Annotations (`-f github`)**:
  - Exact line and 1-indexed column position tracking for PII, secrets, and structural headings (`Position`, `ViolationItem.line`, `ViolationItem.col`).
  - Native GitHub Actions workflow commands emitted to `stdout` (`::error file=...,line=...,col=...::...` and `::warning file=...,line=...,col=...::...`).
- **Expanded 18-Item Real CLI Acceptance Criteria (AC) Matrix**:
  - Full end-to-end OS subprocess execution testing all 18 criteria (`scripts/verify_ac.py` and `pytest -v -m acceptance`).
  - Coverage expanded for offline mode (AC 15), result cache (AC 16), GitHub Actions annotations (AC 17), and file exclusions (AC 18).

---

## [0.8.0] - 2026-10-05

### Added
- **Public Python API** (`typesafe_eval`):
  - Top-level programmatic evaluation functions:
    - `evaluate(content: str, preset: str | PresetConfig = "quality", ...) -> DocumentEvalResult`
    - `evaluate_document(path: str | Path, preset: str | PresetConfig = "quality", ...) -> DocumentEvalResult`
    - `evaluate_documents(paths: Sequence[str | Path], preset: str | PresetConfig = "quality", concurrency: int = 4, ...) -> list[DocumentEvalResult]`
  - Re-exported core data models and configuration discovery utilities:
    - `DocumentEvalResult`, `ScoreResult`, `NoulResult`, `ChoiceResult`, `PresetConfig`, `QuestionConfig`
    - `load_preset`, `load_project_config`, `find_project_config`
  - High-performance connection pooling via shared `TypeSafeEvaluator` instance during batch evaluations.
- **Typed Exception Hierarchy** (`typesafe_eval.exceptions`):
  - `TypeSafeEvalError` (base exception)
  - `ConfigurationError` (subclass of `ValueError`)
  - `AuthenticationError` (subclass of `ValueError`)
  - `RuntimeEvalError` (subclass of `RuntimeError`)
  - `ContentViolationError` (with structured `result` and `results` attributes for batch failure handling)
- **Strict Typing & PEP 561**:
  - `py.typed` marker file included in `src/typesafe_eval/`.
  - Configured `[tool.mypy]` with `strict = true` across the entire codebase (0 errors across 12 source files).
- **Hypothesis Property-Based Testing** (`tests/test_properties.py`):
  - Invariant verification for text chunking coverage, chunk size limits, secret/PII token leakage prevention, and score bounds/monotonicity.
- **Configuration Auto-Discovery**:
  - Automatically searches parent directories for `.typesafe-eval.yaml`, `.typesafe-eval.yml`, or `pyproject.toml` (`[tool.typesafe-eval]`).
  - Supports preset extension (`extends: quality`) and per-question overrides.
- **JSON Schema Export**:
  - New CLI command `typesafe-eval schema` to export JSON Schema for IDE validation and auto-completion.
- **Parallel Document Concurrency**:
  - Concurrency flag `-j` / `--jobs` / `--concurrency` in CLI and `evaluate_documents()` API.
  - Thread-safe execution preserving deterministic document ordering in outputs.
- **Git Diff Evaluation**:
  - `--staged` flag to evaluate only staged git documents (pre-commit gating).
  - `--since <ref>` flag to evaluate documents modified relative to a branch or commit (CI gating).
- **Advisory Thresholds**:
  - Added `advisory: bool` flag to question configurations allowing non-blocking advisory observations without tripping Exit Code 1.
- **Adversarial Security Tests**:
  - Comprehensive adversarial PII & secret edge-case test suite (`tests/test_adversarial_sanitizer.py`).

### Changed
- Preserved original document filepaths in evaluation results for both CLI and API consumers.
- Improved error handling for unreadable or missing document files in batch processing.

---

## [0.7.0] - 2026-10-04

### Added
- Rich CLI terminal rendering with formatted progress and violation summaries.
- Real CLI acceptance test runner (`scripts/verify_ac.py`) covering 14 core acceptance criteria.
- Pre-commit hook graceful skipping when `TYPESAFE_API_KEY` is unset.
- Deterministic exit code precedence (Exit Code 1 over Exit Code 3).
- Scaffolding CLI command (`typesafe-eval init`).

---

## [0.6.0] - 2026-10-03

### Added
- Support for candidate-level Noul probability queries and calibration thresholds.
- Fine-grained PII and credential classifiers with zero-raw-leakage masking guarantees.

---

## [0.5.0] - 2026-10-02

### Added
- Agent-agnostic JSON output contract (`schema_version: "1.0"`).
- Pure `stdout` JSON stream separation for seamless integration with `jq`.
- Claude Code integration plugin with PostToolUse safety hooks.
- Comprehensive autonomous agent guidance documentation (`AGENTS.md`).
