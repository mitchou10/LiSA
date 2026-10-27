# Changelog

## [1.5.0](https://github.com/mitchou10/LiSA/compare/v1.4.0...v1.5.0) (2026-10-27)


### Features

* **frontend:** add zoom to the page image when annotating ([#93](https://github.com/mitchou10/LiSA/issues/93)) ([bede103](https://github.com/mitchou10/LiSA/commit/bede103309bc83edb743dad8f5c476171220411b))

## [1.4.0](https://github.com/mitchou10/LiSA/compare/v1.3.5...v1.4.0) (2026-10-27)


### Features

* **backend:** draw boxes on run pages, stored and blurred on export ([4c9d116](https://github.com/mitchou10/LiSA/commit/4c9d116f3992867f46d960ab4dabd8f0df944deb))
* **frontend:** draw boxes on a page to blur them on export ([6459244](https://github.com/mitchou10/LiSA/commit/6459244b7b85ccaf78be65f4500d45c8a16f43c8))
* **frontend:** pick a label for a drawn box in a modal with the crop ([f550ef9](https://github.com/mitchou10/LiSA/commit/f550ef901678e7bd68acce2e75a8f418a3f636fc))


### Bug Fixes

* **helm:** use helper.fullname for worker backend URLs ([46c2f13](https://github.com/mitchou10/LiSA/commit/46c2f13216d7a1a6703065db2b46c6b70c118c96))

## [1.3.5](https://github.com/mitchou10/LiSA/compare/v1.3.4...v1.3.5) (2026-10-26)


### Bug Fixes

* **helm:** read the RustFS credentials from the lisa-s3 secret ([e596245](https://github.com/mitchou10/LiSA/commit/e59624572860b9b358cfb179660a29e92c4a0c1d))

## [1.3.4](https://github.com/mitchou10/LiSA/compare/v1.3.3...v1.3.4) (2026-10-26)


### Bug Fixes

* **helm:** set resources on the bundled RustFS ([3a8f485](https://github.com/mitchou10/LiSA/commit/3a8f48561ba391261e8797f1ef3a3d5f87b5061c))

## [1.3.3](https://github.com/mitchou10/LiSA/compare/v1.3.2...v1.3.3) (2026-10-26)


### Bug Fixes

* **helm:** enable the bundled RustFS in the DSO values ([aa2705c](https://github.com/mitchou10/LiSA/commit/aa2705cf1dd9d664660245e1c75acf2fa30ceebc))

## [1.3.2](https://github.com/mitchou10/LiSA/compare/v1.3.1...v1.3.2) (2026-10-26)


### Bug Fixes

* **backend:** skip the audience check on Keycloak tokens and log rejected ones ([3dda04d](https://github.com/mitchou10/LiSA/commit/3dda04d91fbc45620837d8c6636860d53ee24572))

## [1.3.1](https://github.com/mitchou10/LiSA/compare/v1.3.0...v1.3.1) (2026-10-26)


### Bug Fixes

* **frontend:** make the header sign-in button start the sign-in ([af3b2ce](https://github.com/mitchou10/LiSA/commit/af3b2cec03edf2c2c79e7c4fbf34551eb3251ca3))

## [1.3.0](https://github.com/mitchou10/LiSA/compare/v1.2.2...v1.3.0) (2026-10-26)


### Features

* **frontend:** say on the landing page that LiSA works offline ([1a393f4](https://github.com/mitchou10/LiSA/commit/1a393f45b2f2d79ea66614570f21f426b3db105b))


### Bug Fixes

* **helm:** select the Redis pods in the KEDA NetworkPolicy ([f1528a1](https://github.com/mitchou10/LiSA/commit/f1528a1fae6ae4227f595e45b994c1e0bc640b33))
* **services:** run the workers offline ([aadca68](https://github.com/mitchou10/LiSA/commit/aadca6836f460bceda48ba1215528928cccb6732))

## [1.2.2](https://github.com/mitchou10/LiSA/compare/v1.2.1...v1.2.2) (2026-10-26)


### Bug Fixes

* **helm:** render env values through tpl ([d16c7e9](https://github.com/mitchou10/LiSA/commit/d16c7e927fabda14547056a93c688dd4ad349235))

## [1.2.1](https://github.com/mitchou10/LiSA/compare/v1.2.0...v1.2.1) (2026-10-26)


### Bug Fixes

* **frontend:** call the API on the same origin by default ([1cb1ef1](https://github.com/mitchou10/LiSA/commit/1cb1ef19defcf9d4bc4efc3e836020878ab2446a))

## [1.2.0](https://github.com/mitchou10/LiSA/compare/v1.1.0...v1.2.0) (2026-10-26)


### Features

* **frontend:** turn the login page into a product landing page ([946ea46](https://github.com/mitchou10/LiSA/commit/946ea46c6a35214713a3ee1c867d9b4fdb8fe273))

## [1.1.0](https://github.com/mitchou10/LiSA/compare/v1.0.1...v1.1.0) (2026-10-26)


### Features

* **frontend:** open a run from My tasks in the analysis views ([5a5c747](https://github.com/mitchou10/LiSA/commit/5a5c747d374829bfe93a0950aa29766ff6fe5b50))
* **frontend:** step-by-step analysis page with mock backend ([b194929](https://github.com/mitchou10/LiSA/commit/b194929f5f3ee1262abc533c08a4054a1e4eb5dd))

## [1.0.1](https://github.com/mitchou10/LiSA/compare/v1.0.0...v1.0.1) (2026-10-24)


### Bug Fixes

* add NetworkPolicy to allow KEDA to reach Redis ([e3e3334](https://github.com/mitchou10/LiSA/commit/e3e3334281b5d2caded64b7e266288b18d6f9947))
* **helm:** remove duplicate extraObjects key in values.yaml ([59b241e](https://github.com/mitchou10/LiSA/commit/59b241e29e22e3f8bed9eeef640f45c38fe6836c))
* replace postgres dependency with CNPG cluster chart ([c180114](https://github.com/mitchou10/LiSA/commit/c1801140606fec350135bf88c1f69a286323f7d8))

## [1.0.0](https://github.com/mitchou10/LiSA/compare/v0.5.0...v1.0.0) (2026-10-24)


### ⚠ BREAKING CHANGES

* use Keycloak only, drop the local users table and login

### Features

* add Keycloak service with lisa realm, admin and user accounts ([afe8c23](https://github.com/mitchou10/LiSA/commit/afe8c23424958468915a1d324d884c4e3c1a7b4b))
* add llm-guard-safety service (prompt injection, toxicity, secrets) ([c0a1497](https://github.com/mitchou10/LiSA/commit/c0a1497c5c662d54364bec0c53d2f5b955f9e80b))
* add My Tasks page for users to track their analyses ([4525837](https://github.com/mitchou10/LiSA/commit/45258377d847a102a1d78ec3d10a49749caaeff6))
* add OCR parser worker (LiteParse/Tesseract) with page images and word boxes ([43243f5](https://github.com/mitchou10/LiSA/commit/43243f50a9f56b8b6f741cb555d383be94f457f5))
* anonymize step for runs, with nothing readable stored in the database ([2c936f8](https://github.com/mitchou10/LiSA/commit/2c936f85b128e3943daf375ea4a0fc8e88fd4985))
* **anonymize:** read page images by s3_key ([5a985d9](https://github.com/mitchou10/LiSA/commit/5a985d92b8412daa694d336c2f58fd4830b0aa90))
* **anonymize:** v2 service redacting spans and blurring page images in S3 ([bf15592](https://github.com/mitchou10/LiSA/commit/bf15592f9d1d38f58296c02b51725acdbe56dbb7))
* **backend:** also classify the page images of a classified file ([290bbef](https://github.com/mitchou10/LiSA/commit/290bbefdb435df56bbcadd4b407de4eb49df8ea1))
* **backend:** expose the S3 key of uploaded files ([4050ff4](https://github.com/mitchou10/LiSA/commit/4050ff4e2d18c6e322190c03ff31c44ee51f1f6d))
* **backend:** feed the dashboard from the current services, with compute times ([b7229bd](https://github.com/mitchou10/LiSA/commit/b7229bd9e15c598e16dd2ac481a78929aee1f6df))
* **backend:** record when a task started and finished ([f6deb25](https://github.com/mitchou10/LiSA/commit/f6deb255d416c956a013b6c7773f16d5493dba2b))
* **backend:** seed default safety checks and PII entities into new projects ([109358c](https://github.com/mitchou10/LiSA/commit/109358c5d49fae89060c198cd715513805fd6d1b))
* **backend:** seed default safety checks and PII entities into new projects ([9bd79dc](https://github.com/mitchou10/LiSA/commit/9bd79dc1cf728106269b918cbb71b5f081003f5f))
* BFF authentication with Keycloak (server-side sessions, HttpOnly cookie) ([7fa526b](https://github.com/mitchou10/LiSA/commit/7fa526b8ffbda78933329de3d4df33fd78bba488))
* **classification:** per-page single/multi-label classification with GLiNER2.5 ([8c79505](https://github.com/mitchou10/LiSA/commit/8c79505950724187117806df1d58e42290fa99e5))
* **classification:** return the probability of each label ([c890d62](https://github.com/mitchou10/LiSA/commit/c890d62c9cdee1c3b2ff0ae69471cb6deed1321a))
* export run pages blurred or annotated (png, zip, pdf) ([fdad00a](https://github.com/mitchou10/LiSA/commit/fdad00a668c046641a818f736ef1849c44c44b2c))
* export run pages blurred or annotated (png, zip, pdf) ([6fad13e](https://github.com/mitchou10/LiSA/commit/6fad13e16c31ac6331e6aba367b7b3b071cbcc4e))
* **frontend:** anonymize option and the probability of every prediction ([49594d0](https://github.com/mitchou10/LiSA/commit/49594d0846d9cedc8b8f25c2ff205febd0d02bf7))
* **frontend:** dashboard with compute time by service and a project filter ([890446d](https://github.com/mitchou10/LiSA/commit/890446d46fa9e27371df797c4b43aa3c3df25911))
* **frontend:** hide the analysed text behind coloured stars ([5f880ce](https://github.com/mitchou10/LiSA/commit/5f880cead617008e1fa37baeaa8098eb98a85e04))
* **frontend:** mock dashboard with realistic stats fallback ([8037edb](https://github.com/mitchou10/LiSA/commit/8037edbf47ebfd6d5e7a2b6ee3c5c42bd56b0ac8))
* **frontend:** move dashboard, services and sensitive data into the profile menu ([797ec4d](https://github.com/mitchou10/LiSA/commit/797ec4d47271badc5ee7c8107bd3b956a8cc1586))
* **frontend:** rich mock results with text annotation, document bboxes, and persist toggle ([e6b6d37](https://github.com/mitchou10/LiSA/commit/e6b6d37dcc0714dd0bfda525d6bfdba1c16bc6d3))
* **frontend:** show the compute time of each step and of the run ([695e1fa](https://github.com/mitchou10/LiSA/commit/695e1fa191029c5b1480f85b8a0e80feb46c5637))
* **frontend:** show the image classification of each page ([cbd0a92](https://github.com/mitchou10/LiSA/commit/cbd0a9275d463d26dd7c2b78a9432039c661aaef))
* **gliner:** add GLiNER NER service with comprehensive unit tests ([7874c90](https://github.com/mitchou10/LiSA/commit/7874c90aa2ce69d28be35d93643354fb3acd52ff))
* helm chart ([0089161](https://github.com/mitchou10/LiSA/commit/008916177431db0ba359b5fb826516f74356b2b2))
* **helm:** rebuild the chart on the Muffin layout with camelCase components ([dfbe99a](https://github.com/mitchou10/LiSA/commit/dfbe99a1475286c416f23354823c49c2681095b0))
* **image-classification:** zero-shot image classification with CLIP ([c061745](https://github.com/mitchou10/LiSA/commit/c061745a5ee43c870f73183948c8a48199e973ba))
* integrate GLiNER service into docker-compose and frontend ([9d02e83](https://github.com/mitchou10/LiSA/commit/9d02e83a4108c80859b6cb7159f26c35b9e7932d))
* **ner:** replace the gliner service by a GLiNER2 NER service with long context ([a63982e](https://github.com/mitchou10/LiSA/commit/a63982e3af0c2c93098a4e6cc5fb5337f9345254))
* **parser:** parse files from S3 into relative boxes and blurred S3 screenshots ([d2606a8](https://github.com/mitchou10/LiSA/commit/d2606a8dd96a01f560577de4986b44574e3f329d))
* projects, what they look for, and project runs through Celery ([d530987](https://github.com/mitchou10/LiSA/commit/d530987b799ee344111864ec6cf6fa9c9c2e8fa2))
* **relation:** zero-shot relation extraction with GLiNER2 and long context ([28dbe55](https://github.com/mitchou10/LiSA/commit/28dbe553aa6c25b694e2acd768680ace0cff69b4))
* run the default analysis without a project ([9a20dd7](https://github.com/mitchou10/LiSA/commit/9a20dd7d72e9a5c6cc7890ee4b5d96745e344724))
* run the default analysis without a project ([53fc7f0](https://github.com/mitchou10/LiSA/commit/53fc7f080426229c4f951f4ef71beafe8b7e96bf))
* **safety:** rebuild on GLiNER2 guardrails + PII with spans and boxes ([e30b4e0](https://github.com/mitchou10/LiSA/commit/e30b4e0bf4a9936b7a65d3564673d37bae8def9b))
* show the analysed pages with boxes and spans ([87cd75e](https://github.com/mitchou10/LiSA/commit/87cd75e733551de1952da8317220399535846f2b))
* store uploaded files in RustFS (S3) behind a files API ([1a71b6a](https://github.com/mitchou10/LiSA/commit/1a71b6a2780c2b29c9c97ad2359dd24d85c102c8))
* versioned detection profiles, Alembic migrations and sensitive-data page ([70da5f5](https://github.com/mitchou10/LiSA/commit/70da5f501719d0a78fc51b2a62e1b470d9cb72d9))


### Bug Fixes

* **ci:** run the backend and the frontend images as a non-root user ([82660d9](https://github.com/mitchou10/LiSA/commit/82660d9343e15595efad7efb02a1b46e4a36f04f))
* **ci:** run the worker images as a non-root user, with a healthcheck ([2436b42](https://github.com/mitchou10/LiSA/commit/2436b428d128190f3bf28fed6d46f056deedb71c))
* **ci:** use repo root as build context for service Docker builds ([35334d9](https://github.com/mitchou10/LiSA/commit/35334d975e59374d58a671f306495410034086ef))
* **docker:** add --create-home to useradd in service Dockerfiles ([4273d0a](https://github.com/mitchou10/LiSA/commit/4273d0a0bc05ed27a22ce07e9d11d3a0d25db2b5))
* **docker:** add --create-home to useradd in service Dockerfiles ([5a8652e](https://github.com/mitchou10/LiSA/commit/5a8652e599036ed1004bb836fe7063ce3df138e1))
* **docker:** copy Tesseract data from correct path in parser Dockerfile ([f6ae113](https://github.com/mitchou10/LiSA/commit/f6ae1139ac4b99815b42969da49debf7fa043e29))
* **docker:** copy Tesseract data from correct path in parser Dockerfile ([a49d278](https://github.com/mitchou10/LiSA/commit/a49d278559caa3e24f0f38d05235ca8c5acbc057))
* end-to-end text analysis pipeline (frontend → backend → worker → UI) ([a45efa4](https://github.com/mitchou10/LiSA/commit/a45efa44660066342ea6716e3bfdc548809e9778))
* **helm:** render image.repository with tpl for global.project substitution ([55e3084](https://github.com/mitchou10/LiSA/commit/55e308445f837a57b8246134a6cb04e46194406b))
* **parser:** lighter default blur that keeps the layout visible ([e54a72d](https://github.com/mitchou10/LiSA/commit/e54a72d9fe7cf9f6916f1cd8813d43faf11ebc25))
* remove hardcoded URLs, use Vault for secrets ([f882d4a](https://github.com/mitchou10/LiSA/commit/f882d4ac600c32887b4842a9c2cef12738eb71a9))
* **worker:** register with retries, and start workers after a healthy backend ([2a914a5](https://github.com/mitchou10/LiSA/commit/2a914a5b701c9266d6ccdecee2cd784cb01e08b9))


### Code Refactoring

* minor formatting and test fixtures cleanup ([34a3dbb](https://github.com/mitchou10/LiSA/commit/34a3dbbc7c99d1a265b007cd06cb4f2a5bc63b90))
* minor formatting and test fixtures cleanup ([54be15d](https://github.com/mitchou10/LiSA/commit/54be15d7ee909321b28967ed8948a85bb3c2cc8b))
* remove Annotated type hints from query parameters and fix imports ([0f4c858](https://github.com/mitchou10/LiSA/commit/0f4c858767f7da86562c4dc41ace32e762bc6967))
* remove Annotated type hints from query parameters and fix imports ([99a52fa](https://github.com/mitchou10/LiSA/commit/99a52fa60032f4f1c6160ff8f473d6a022439658))
* remove redundant response_model from detection_profiles routes ([d78811c](https://github.com/mitchou10/LiSA/commit/d78811c9a5ff8b26dc435fca17fe35ab791da7ee))
* remove redundant response_model from detection_profiles routes ([94e3c99](https://github.com/mitchou10/LiSA/commit/94e3c9963abcf31e6d360d96c583ef21cbff8b84))
* remove redundant response_model from FastAPI route decorators ([d167b1f](https://github.com/mitchou10/LiSA/commit/d167b1f9c75b7b189049bfd71342f16867030a92))
* remove redundant response_model from FastAPI route decorators ([454d830](https://github.com/mitchou10/LiSA/commit/454d8309edeff54be81eae8d74e140b29ed49e88))
* remove redundant response_model from file route decorators ([3f2e0bd](https://github.com/mitchou10/LiSA/commit/3f2e0bd9a932f7fd2cb0dd878d55bc61c270c1e0))
* remove redundant response_model from file route decorators ([74d1891](https://github.com/mitchou10/LiSA/commit/74d18917f700f7733ba5ca378e3e73c9a6bcfa52))
* use Keycloak only, drop the local users table and login ([0b4e2e2](https://github.com/mitchou10/LiSA/commit/0b4e2e2df8ccf5a169c3149876efd7240aca16b8))

## [0.5.0](https://github.com/mitchou10/LiSA/compare/v0.4.0...v0.5.0) (2026-06-05)


### Features

* add support for configurable Celery queues in service and task dispatching ([3d87fca](https://github.com/mitchou10/LiSA/commit/3d87fcabc2694ecec59b446c4e4bc5468d3aca6a))

## [0.4.0](https://github.com/mitchou10/LiSA/compare/v0.3.0...v0.4.0) (2026-06-05)


### Features

* implement local JWT authentication and Keycloak integration ([a853b9c](https://github.com/mitchou10/LiSA/commit/a853b9cc633dccf105c25db4bd4b45b3e45566c1))

## [0.3.0](https://github.com/mitchou10/LiSA/compare/v0.2.0...v0.3.0) (2026-06-05)


### Features

* Refactor models and schemas to support unified input handling and enhance prediction capabilities ([a1ea87b](https://github.com/mitchou10/LiSA/commit/a1ea87b44d050bca536034ec5ca8b9ae6378a2a2))
* **worker:** implement asynchronous worker with logging and model integration ([2dcb8dc](https://github.com/mitchou10/LiSA/commit/2dcb8dc67bd44b2044a7570f50712ace07283505))


### Bug Fixes

* Correct manifest file path in release workflow ([5f017be](https://github.com/mitchou10/LiSA/commit/5f017be5e7ab47dcf847dfe2d09cb131fa9a07fe))
* Fix run-test target dependency to ensure build-test is executed first ([5f017be](https://github.com/mitchou10/LiSA/commit/5f017be5e7ab47dcf847dfe2d09cb131fa9a07fe))
* Remove interactive flag from run-test command in Makefile ([5f017be](https://github.com/mitchou10/LiSA/commit/5f017be5e7ab47dcf847dfe2d09cb131fa9a07fe))
* Update environment variables in .env.example and refactor LiSASyncTask initialization ([a1ea87b](https://github.com/mitchou10/LiSA/commit/a1ea87b44d050bca536034ec5ca8b9ae6378a2a2))
* Update manifest file path and correct config file reference in release workflow ([5f017be](https://github.com/mitchou10/LiSA/commit/5f017be5e7ab47dcf847dfe2d09cb131fa9a07fe))
* Update release workflow and configuration for prerelease management ([#8](https://github.com/mitchou10/LiSA/issues/8)) ([1588d7b](https://github.com/mitchou10/LiSA/commit/1588d7be76e8a13aabeb63ad234fbfe465fcb556))

## [0.2.0](https://github.com/IA-Generative/LiSA/compare/v0.1.0...v0.2.0) (2025-09-17)


### Features

* **worker:** implement asynchronous worker with logging and model integration ([2dcb8dc](https://github.com/IA-Generative/LiSA/commit/2dcb8dc67bd44b2044a7570f50712ace07283505))


### Bug Fixes

* Correct manifest file path in release workflow ([5f017be](https://github.com/IA-Generative/LiSA/commit/5f017be5e7ab47dcf847dfe2d09cb131fa9a07fe))
* Fix run-test target dependency to ensure build-test is executed first ([5f017be](https://github.com/IA-Generative/LiSA/commit/5f017be5e7ab47dcf847dfe2d09cb131fa9a07fe))
* Remove interactive flag from run-test command in Makefile ([5f017be](https://github.com/IA-Generative/LiSA/commit/5f017be5e7ab47dcf847dfe2d09cb131fa9a07fe))
* Update manifest file path and correct config file reference in release workflow ([5f017be](https://github.com/IA-Generative/LiSA/commit/5f017be5e7ab47dcf847dfe2d09cb131fa9a07fe))
