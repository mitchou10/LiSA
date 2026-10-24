# Changelog

## [1.0.0-rc](https://github.com/mitchou10/LiSA/compare/v0.4.0...v1.0.0-rc) (2026-10-24)


### ⚠ BREAKING CHANGES

* use Keycloak only, drop the local users table and login

### Features

* add Keycloak service with lisa realm, admin and user accounts ([afe8c23](https://github.com/mitchou10/LiSA/commit/afe8c23424958468915a1d324d884c4e3c1a7b4b))
* add llm-guard-safety service (prompt injection, toxicity, secrets) ([c0a1497](https://github.com/mitchou10/LiSA/commit/c0a1497c5c662d54364bec0c53d2f5b955f9e80b))
* add OCR parser worker (LiteParse/Tesseract) with page images and word boxes ([43243f5](https://github.com/mitchou10/LiSA/commit/43243f50a9f56b8b6f741cb555d383be94f457f5))
* add support for configurable Celery queues in service and task dispatching ([3d87fca](https://github.com/mitchou10/LiSA/commit/3d87fcabc2694ecec59b446c4e4bc5468d3aca6a))
* anonymize step for runs, with nothing readable stored in the database ([2c936f8](https://github.com/mitchou10/LiSA/commit/2c936f85b128e3943daf375ea4a0fc8e88fd4985))
* **anonymize:** read page images by s3_key ([5a985d9](https://github.com/mitchou10/LiSA/commit/5a985d92b8412daa694d336c2f58fd4830b0aa90))
* **anonymize:** v2 service redacting spans and blurring page images in S3 ([bf15592](https://github.com/mitchou10/LiSA/commit/bf15592f9d1d38f58296c02b51725acdbe56dbb7))
* **backend:** also classify the page images of a classified file ([290bbef](https://github.com/mitchou10/LiSA/commit/290bbefdb435df56bbcadd4b407de4eb49df8ea1))
* **backend:** expose the S3 key of uploaded files ([4050ff4](https://github.com/mitchou10/LiSA/commit/4050ff4e2d18c6e322190c03ff31c44ee51f1f6d))
* **backend:** feed the dashboard from the current services, with compute times ([b7229bd](https://github.com/mitchou10/LiSA/commit/b7229bd9e15c598e16dd2ac481a78929aee1f6df))
* **backend:** record when a task started and finished ([f6deb25](https://github.com/mitchou10/LiSA/commit/f6deb255d416c956a013b6c7773f16d5493dba2b))
* **backend:** seed default safety checks and PII entities into new projects ([9bd79dc](https://github.com/mitchou10/LiSA/commit/9bd79dc1cf728106269b918cbb71b5f081003f5f))
* BFF authentication with Keycloak (server-side sessions, HttpOnly cookie) ([7fa526b](https://github.com/mitchou10/LiSA/commit/7fa526b8ffbda78933329de3d4df33fd78bba488))
* **classification:** per-page single/multi-label classification with GLiNER2.5 ([8c79505](https://github.com/mitchou10/LiSA/commit/8c79505950724187117806df1d58e42290fa99e5))
* **classification:** return the probability of each label ([c890d62](https://github.com/mitchou10/LiSA/commit/c890d62c9cdee1c3b2ff0ae69471cb6deed1321a))
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
* run the default analysis without a project ([53fc7f0](https://github.com/mitchou10/LiSA/commit/53fc7f080426229c4f951f4ef71beafe8b7e96bf))
* **safety:** rebuild on GLiNER2 guardrails + PII with spans and boxes ([e30b4e0](https://github.com/mitchou10/LiSA/commit/e30b4e0bf4a9936b7a65d3564673d37bae8def9b))
* show the analysed pages with boxes and spans ([87cd75e](https://github.com/mitchou10/LiSA/commit/87cd75e733551de1952da8317220399535846f2b))
* store uploaded files in RustFS (S3) behind a files API ([1a71b6a](https://github.com/mitchou10/LiSA/commit/1a71b6a2780c2b29c9c97ad2359dd24d85c102c8))
* update version to 0.4.0 across all components and add Helm chart files ([3342f5c](https://github.com/mitchou10/LiSA/commit/3342f5c055f8013be37fb34422d80c6f238cf76c))
* versioned detection profiles, Alembic migrations and sensitive-data page ([70da5f5](https://github.com/mitchou10/LiSA/commit/70da5f501719d0a78fc51b2a62e1b470d9cb72d9))


### Bug Fixes

* **ci:** run the backend and the frontend images as a non-root user ([82660d9](https://github.com/mitchou10/LiSA/commit/82660d9343e15595efad7efb02a1b46e4a36f04f))
* **ci:** run the worker images as a non-root user, with a healthcheck ([2436b42](https://github.com/mitchou10/LiSA/commit/2436b428d128190f3bf28fed6d46f056deedb71c))
* **ci:** use repo root as build context for service Docker builds ([35334d9](https://github.com/mitchou10/LiSA/commit/35334d975e59374d58a671f306495410034086ef))
* **docker:** add --create-home to useradd in service Dockerfiles ([5a8652e](https://github.com/mitchou10/LiSA/commit/5a8652e599036ed1004bb836fe7063ce3df138e1))
* **docker:** copy Tesseract data from correct path in parser Dockerfile ([a49d278](https://github.com/mitchou10/LiSA/commit/a49d278559caa3e24f0f38d05235ca8c5acbc057))
* end-to-end text analysis pipeline (frontend → backend → worker → UI) ([a45efa4](https://github.com/mitchou10/LiSA/commit/a45efa44660066342ea6716e3bfdc548809e9778))
* **helm:** render image.repository with tpl for global.project substitution ([55e3084](https://github.com/mitchou10/LiSA/commit/55e308445f837a57b8246134a6cb04e46194406b))
* **parser:** lighter default blur that keeps the layout visible ([e54a72d](https://github.com/mitchou10/LiSA/commit/e54a72d9fe7cf9f6916f1cd8813d43faf11ebc25))
* **worker:** register with retries, and start workers after a healthy backend ([2a914a5](https://github.com/mitchou10/LiSA/commit/2a914a5b701c9266d6ccdecee2cd784cb01e08b9))


### Code Refactoring

* minor formatting and test fixtures cleanup ([54be15d](https://github.com/mitchou10/LiSA/commit/54be15d7ee909321b28967ed8948a85bb3c2cc8b))
* remove Annotated type hints from query parameters and fix imports ([99a52fa](https://github.com/mitchou10/LiSA/commit/99a52fa60032f4f1c6160ff8f473d6a022439658))
* remove redundant response_model from detection_profiles routes ([94e3c99](https://github.com/mitchou10/LiSA/commit/94e3c9963abcf31e6d360d96c583ef21cbff8b84))
* remove redundant response_model from FastAPI route decorators ([454d830](https://github.com/mitchou10/LiSA/commit/454d8309edeff54be81eae8d74e140b29ed49e88))
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
