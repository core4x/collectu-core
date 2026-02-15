# CHANGELOG

<!-- version list -->

## v1.47.0 (2026-02-14)

### Features

- Fixed typo and added 'replace_existing' configuration param for all tag modules.
  ([`a16e564`](https://github.com/core4x/collectu-core/commit/a16e564eb3d6bcc268904f3ece1c7b654eb8d3da))


## v1.46.3 (2026-02-03)

### Bug Fixes

- Removed CHANGELOG.md.
  ([`bb35d9b`](https://github.com/core4x/collectu-core/commit/bb35d9ba66634e096140591048adce5325dde7c7))


## v1.46.2 (2026-02-03)

### Bug Fixes

- Fixed path to test data.
  ([`53f2b78`](https://github.com/core4x/collectu-core/commit/53f2b78f7c07d20bebfb33c7f8fbff366dc1df8c))


## v1.46.1 (2026-01-31)

### Bug Fixes

- Improved dragging behaviour.
  ([`87f914e`](https://github.com/core4x/collectu-core/commit/87f914e457d6ba68ea614073010bc7982f3c689e))


## v1.46.0 (2026-01-31)

### Features

- Added y_list dashboard.
  ([`73f943d`](https://github.com/core4x/collectu-core/commit/73f943d745546207992e81238a46ab8e994f8399))


## v1.45.1 (2026-01-31)

### Bug Fixes

- Forcefully update submodules.
  ([`09d8198`](https://github.com/core4x/collectu-core/commit/09d81984680bc68833a81e23ec8f68ebc9ec52e2))


## v1.45.0 (2026-01-31)

### Features

- Extended updater with stashing.
  ([`6b7a443`](https://github.com/core4x/collectu-core/commit/6b7a44392c61376e43e9a3b51b07d987333dbe99))


## v1.44.0 (2026-01-30)

### Bug Fixes

- Fixed task handling.
  ([`822a6c4`](https://github.com/core4x/collectu-core/commit/822a6c4c1d085d4e194f0e31191a12f1d1baa2c6))

- Improved toast messages.
  ([`6fa802c`](https://github.com/core4x/collectu-core/commit/6fa802c59f7889c43d03bb91426b830283079fd2))

- Removed tooltip settings generated with js.
  ([`751dad8`](https://github.com/core4x/collectu-core/commit/751dad86b601703ec232d806526fc3ea78840acc))

### Features

- Added allowed commands to settings and reporting.
  ([`5ead75c`](https://github.com/core4x/collectu-core/commit/5ead75c6fb381735261cf50314c49451f204943c))


## v1.43.0 (2026-01-27)

### Bug Fixes

- Updated interface.
  ([`696cced`](https://github.com/core4x/collectu-core/commit/696cced275df362262754454d371596ed3aa92e3))

### Features

- Added .venv.
  ([`9a821d8`](https://github.com/core4x/collectu-core/commit/9a821d85f33e860077dd78e459d22e07e4ce0699))


## v1.42.0 (2026-01-25)

### Features

- Added new configuration ui functions for module selection etc. and improved some smaller bugs.
  ([`e02f4a0`](https://github.com/core4x/collectu-core/commit/e02f4a0b217591d27ff12a364d4f79e2a5501353))


## v1.41.1 (2026-01-16)

### Bug Fixes

- Switched test-token method from POST to GET in order to fix login error on mobile.
  ([`897ea1a`](https://github.com/core4x/collectu-core/commit/897ea1a2029533159cb5eca826d530b89fe9b270))

- Updated interface.
  ([`a9ec10a`](https://github.com/core4x/collectu-core/commit/a9ec10a5cba19a7368cd5823661325303ab8d8fc))


## v1.41.0 (2025-12-23)

### Bug Fixes

- Added token refresh logic.
  ([`c073c16`](https://github.com/core4x/collectu-core/commit/c073c16377a5fa8aa9d74dbf01928dc4be440833))

- Made hub address easier configurable.
  ([`8d0b6dc`](https://github.com/core4x/collectu-core/commit/8d0b6dc07afa1ca0688216f8c6afd84f3e6633ae))

### Features

- Added remote_app_id functionality.
  ([`7fc3fb9`](https://github.com/core4x/collectu-core/commit/7fc3fb91af8bc33db1cec905686246261580d8a6))

- Replaced draggable (jquery-ui) with interact.js for mobile drag support.
  ([`a2d5ac0`](https://github.com/core4x/collectu-core/commit/a2d5ac0d7578b328c83b1834704744c07b2abd7a))


## v1.40.0 (2025-12-12)

### Features

- Added undo/redo and hub_config functionality.
  ([`9c361c0`](https://github.com/core4x/collectu-core/commit/9c361c0db66b3e63e60ecd353aadd455ca2f9b6d))


## v1.39.0 (2025-12-12)

### Bug Fixes

- Added time to console logging.
  ([`beb9d62`](https://github.com/core4x/collectu-core/commit/beb9d6208ef0d7c095e2715576bd9e280e894448))

### Features

- Added datetime type validation.
  ([`c0ca3df`](https://github.com/core4x/collectu-core/commit/c0ca3df903ea25d6201c835764bf6b6c8f9802eb))

- Added undo/redo and hub_config functionality.
  ([`da7c4dc`](https://github.com/core4x/collectu-core/commit/da7c4dcd270e8f4ee4d7402a5b06444dfcc130a4))


## v1.38.10 (2025-11-27)

### Bug Fixes

- Added updated for app_description and local_admin_password.
  ([`2bd1f46`](https://github.com/core4x/collectu-core/commit/2bd1f468de797f48ec2eba57feb695878ed57651))

- First compare if username and password exist.
  ([`a859a17`](https://github.com/core4x/collectu-core/commit/a859a1718031331f2eafaeebaa61d4e31e2d36db))


## v1.38.9 (2025-11-25)

### Bug Fixes

- Removed some special chars during default password generation, which caused ini parser
  interpolation error.
  ([`51cb479`](https://github.com/core4x/collectu-core/commit/51cb47934ca6340e1679179415342c00401a303a))

- Removed stashing logic from updater and improved logs.
  ([`0ac4042`](https://github.com/core4x/collectu-core/commit/0ac40427fe5d6a86bf693b308e43121ecc984c96))


## v1.38.8 (2025-11-25)

### Bug Fixes

- Removed default password and auto-generate on start.
  ([`3403bff`](https://github.com/core4x/collectu-core/commit/3403bffd30d8d04c7b4d1300dce0eea87c1e8c01))


## v1.38.7 (2025-11-24)

### Bug Fixes

- Improved styling of live data view.
  ([`0bce69c`](https://github.com/core4x/collectu-core/commit/0bce69cc5936bd0afe879994f70b6c0c026a7b75))

- Improved update logic, by automatically stashing and merging.
  ([`4ab1810`](https://github.com/core4x/collectu-core/commit/4ab18107d1e530d41dca78418cb4ab5b530ef842))

- Updated interface.
  ([`07ac6ae`](https://github.com/core4x/collectu-core/commit/07ac6ae5f7bfc8652e0223aa255f00cba1e21b6f))


## v1.38.6 (2025-11-20)

### Bug Fixes

- Removed COLLECTU_ from env vars.
  ([`ecae543`](https://github.com/core4x/collectu-core/commit/ecae543670c1c789ae899a3b4533489385cdb3c9))


## v1.38.5 (2025-11-20)

### Bug Fixes

- Rename and update local admin configuration keys.
  ([`93ca446`](https://github.com/core4x/collectu-core/commit/93ca4468d54e6b52b3f42d7a16e0f661578736fd))


## v1.38.4 (2025-11-20)

### Bug Fixes

- Updated type checking to work with Python 3.14.
  ([`4f107e3`](https://github.com/core4x/collectu-core/commit/4f107e358433dd64058885adc90ae45777535861))


## v1.38.3 (2025-11-20)

### Bug Fixes

- Support for Python 3.14, where __annotations__ do not longer exists.
  ([`a0129bc`](https://github.com/core4x/collectu-core/commit/a0129bc90cfcf2562ea6cf1374f5e56ba92e3e70))


## v1.38.2 (2025-11-20)

### Bug Fixes

- Make code params not changeable to textarea for dynamic variables.
  ([`d4250d1`](https://github.com/core4x/collectu-core/commit/d4250d134875ad081e8647abe90df83ed20eadfa))


## v1.38.1 (2025-11-20)

### Bug Fixes

- Updated interface module.
  ([`2d4206f`](https://github.com/core4x/collectu-core/commit/2d4206fa3a54e9c0677c79fc229a7b57009eeb47))


## v1.38.0 (2025-11-20)

### Features

- Added code editor for config params with the key 'code'.
  ([`58cc431`](https://github.com/core4x/collectu-core/commit/58cc4312766b51c00ee17c335e92671d39743649))


## v1.37.0 (2025-11-19)

### Bug Fixes

- Added progress bar for module download.
  ([`225c57f`](https://github.com/core4x/collectu-core/commit/225c57f4a1a946d45f90673a8a673a2397d84920))

- Do not set empty hub api acess token as env var.
  ([`7df521d`](https://github.com/core4x/collectu-core/commit/7df521d9e8c7ded747ea595ead38b09f31ffd9f0))

- Set env var from settings even if it has no value.
  ([`383cb58`](https://github.com/core4x/collectu-core/commit/383cb58b65b32b916e0fa55f1f1f31ed7e63069c))

### Documentation

- Improved error message.
  ([`1bf45b6`](https://github.com/core4x/collectu-core/commit/1bf45b6793e5cbca1d1543aebaa3f9b42400a988))

### Features

- Added text_advanced dashboard support.
  ([`f1804e0`](https://github.com/core4x/collectu-core/commit/f1804e02f3ab0ebe69538693fa78dda58aadadac))


## v1.36.2 (2025-11-07)

### Bug Fixes

- Simplified import_third_party_requirements and improved error messages.
  ([`3512a0e`](https://github.com/core4x/collectu-core/commit/3512a0ebb041d570998ac32de4aab63eda42e7ea))


## v1.36.1 (2025-11-05)

### Bug Fixes

- Improved local admin token verfification.
  ([`9bbc73a`](https://github.com/core4x/collectu-core/commit/9bbc73ac489b35d4d526d5f9d0607ae71520361d))


## v1.36.0 (2025-11-04)

### Features

- Added local admin user for authentication.
  ([`ecf324d`](https://github.com/core4x/collectu-core/commit/ecf324d311aaf805c78cbfe9d8d71579380d675c))


## v1.35.1 (2025-11-04)

### Bug Fixes

- Updated interface.
  ([`16b325b`](https://github.com/core4x/collectu-core/commit/16b325bb875d1460ea6d34d56f7b3db95a09c320))


## v1.35.0 (2025-11-01)

### Features

- Added category to config parameters.
  ([`b9108ee`](https://github.com/core4x/collectu-core/commit/b9108ee8a7aadf3e2a1b8444936f7fbd88a57ee8))


## v1.34.11 (2025-10-27)

### Bug Fixes

- Added better config interface for lists and dicts.
  ([`479c6f2`](https://github.com/core4x/collectu-core/commit/479c6f29b3b257d7051ad521caf2050a7604b005))

- Fixed tests, where we expected an exception for dynamic variables.
  ([`612486a`](https://github.com/core4x/collectu-core/commit/612486afb9a5ec7dc3a8a9fcbf519724d593dc60))

- If parameter is a dynamic var, we can not execute the parameter specific validation functions.
  ([`6e1ba19`](https://github.com/core4x/collectu-core/commit/6e1ba191aada76d038b6f700c34f47699010f81d))


## v1.34.10 (2025-10-27)

### Bug Fixes

- Added inactive symbol to module config.
  ([`279b03a`](https://github.com/core4x/collectu-core/commit/279b03aead675172042a1b250266fafbc7042859))


## v1.34.9 (2025-10-08)

### Bug Fixes

- Make current file path to work dir.
  ([`dcf5d83`](https://github.com/core4x/collectu-core/commit/dcf5d83c312b3091b64939399bfd938abe78ed87))

- Make current file path to work dir.
  ([`45e27a5`](https://github.com/core4x/collectu-core/commit/45e27a59dcf2cd03178e95b3c22db27071a62457))

- Make current file path to work dir.
  ([`06812a3`](https://github.com/core4x/collectu-core/commit/06812a3d7905bf72b8544ca022c11826b9cbc070))


## v1.34.8 (2025-10-07)

### Bug Fixes

- Improved stopping procedure.
  ([`e622017`](https://github.com/core4x/collectu-core/commit/e622017d7b92f52ddf1acf060b104ca0b47fa1d1))


## v1.34.7 (2025-10-07)

### Bug Fixes

- Update subproject commit reference in interface.
  ([`bf060a8`](https://github.com/core4x/collectu-core/commit/bf060a84f698fbfe2a08cca7ee7d8786b615abd1))


## v1.34.6 (2025-10-07)

### Bug Fixes

- Check if AUTO_INSTALL is enabled before installing third party requirements.
  ([`26cc541`](https://github.com/core4x/collectu-core/commit/26cc541b572f4cbe152bcb5fdbba680418181741))

- Enhance package installation handling based on AUTO_INSTALL environment variable.
  ([`e5acad7`](https://github.com/core4x/collectu-core/commit/e5acad7c8f418612485482828acccfa485ad51c5))

- Move third party imports inside try block to handle ImportError for requests.
  ([`560ba21`](https://github.com/core4x/collectu-core/commit/560ba21350fb72b6647583bb3a98063f2700bb0b))

- Update AUTO_INSTALL default value to 0 for third party package installation.
  ([`98aba3b`](https://github.com/core4x/collectu-core/commit/98aba3b28d2782b880d2fd9d76bb3e31cc711829))

### Documentation

- Improved description of mcp_app.
  ([`92c8ecb`](https://github.com/core4x/collectu-core/commit/92c8ecb8e6d1507c6ea89779bc24f5be78625c84))


## v1.34.5 (2025-10-07)

### Bug Fixes

- Improve exit handling by setting exit codes for KeyboardInterrupt and exceptions.
  ([`5c951ab`](https://github.com/core4x/collectu-core/commit/5c951abe155549041b3f448d2547ec2b773d2bf8))


## v1.34.4 (2025-10-06)

### Bug Fixes

- Refactor main entry to handle KeyboardInterrupt globally.
  ([`8187a4d`](https://github.com/core4x/collectu-core/commit/8187a4df6745d2689d7dfc3dbc36c2b491d3b28c))


## v1.34.3 (2025-09-30)

### Bug Fixes

- Replaced some innerHTML with textContent.
  ([`f28e1c2`](https://github.com/core4x/collectu-core/commit/f28e1c285db3ab965145b4d36055431080e33a5c))

- Replaced some innerHTML with textContent.
  ([`beb886c`](https://github.com/core4x/collectu-core/commit/beb886cfa6df493ac4c637f94625422c769818d9))


## v1.34.2 (2025-09-27)

### Bug Fixes

- Fixed check for cryptography availability.
  ([`128de1c`](https://github.com/core4x/collectu-core/commit/128de1c1e87e15f9ff2bcb95802ddf268392d93d))

- Show always start and end of stop routine.
  ([`e687048`](https://github.com/core4x/collectu-core/commit/e68704814178c29242c532b1c6ebfe7df3385da0))


## v1.34.1 (2025-09-27)

### Bug Fixes

- Made cryptography optional but added to requirements.txt.
  ([`79ae129`](https://github.com/core4x/collectu-core/commit/79ae12916b926aac0a280ef5b35dea40881aaa76))


## v1.34.0 (2025-09-27)

### Features

- Made all env variables to be adjustable from outside.
  ([`00cb8ce`](https://github.com/core4x/collectu-core/commit/00cb8ce07e33ff600a0883f314448b177c0c207f))


## v1.33.0 (2025-09-27)

### Features

- Added task signature verification for hub tasks.
  ([`1294526`](https://github.com/core4x/collectu-core/commit/12945262ca91b67b2fb07205a12578552df40662))


## v1.32.0 (2025-09-27)

### Features

- Auto-restart if we detected empty interface folder and successfully pulled the interface.
  ([`79526cd`](https://github.com/core4x/collectu-core/commit/79526cd27448e0e68c4d0ee5061396f516c95f65))


## v1.31.0 (2025-09-27)

### Features

- Added packaging to requirements.txt.
  ([`0cfc741`](https://github.com/core4x/collectu-core/commit/0cfc741ac85e22f5d44971b4bdc62ddb4165a9f1))


## v1.30.0 (2025-09-27)

### Features

- Added healthz endpoint for health checks.
  ([`76caa60`](https://github.com/core4x/collectu-core/commit/76caa605336c59d08acdc1c987957431fe32a959))

- Improved plugin system in order to support definition of requirements like done for pip (==, >=,
  <=, >, <, ~=, !=, etc.).
  ([`bddd9f5`](https://github.com/core4x/collectu-core/commit/bddd9f528dad67edc204756eacf758c9fd64c263))


## v1.29.1 (2025-09-25)

### Bug Fixes

- Fixed fallback (||) error, which treated 0 falsy. We now use ??.
  ([`268bed9`](https://github.com/core4x/collectu-core/commit/268bed9bdd3def1798cc8942d48c7dad88bc5189))

- Only try to get username if REPORT_TO_HUB is enabled.
  ([`8c4d192`](https://github.com/core4x/collectu-core/commit/8c4d192ac3d835890e667450bca35285d39976f4))


## v1.29.0 (2025-09-24)

### Documentation

- Added param description for regex flags.
  ([`006ed6c`](https://github.com/core4x/collectu-core/commit/006ed6cf4b5ddfee3ba0e105462312f76ab0a3f9))

### Features

- Added MCP instance to data layer.
  ([`a067708`](https://github.com/core4x/collectu-core/commit/a067708313d3b4319655a57e4bd67189b78be946))

- Text input fields are now text areas.
  ([`2ff1e88`](https://github.com/core4x/collectu-core/commit/2ff1e884023a23a20499996f46d14ceb666fba9d))

- The field entry of a data object can now be an empty dict.
  ([`00a17f5`](https://github.com/core4x/collectu-core/commit/00a17f53794934a7b0d2aa4cbb9e8ee798b380f8))


## v1.28.0 (2025-09-19)

### Features

- Adjusted card body height to be always 100%.
  ([`a25bf18`](https://github.com/core4x/collectu-core/commit/a25bf182ae872a261fe57ca54d15bba1140b90fd))


## v1.27.0 (2025-09-14)

### Features

- Initial commit.
  ([`49a2eae`](https://github.com/core4x/collectu-core/commit/49a2eae14f60bcb385ec0842560a8118e82692c7))


## v1.26.3 (2025-09-05)

### Bug Fixes

- Adjusted nav bar.
  ([`47e2da2`](https://github.com/core4x/collectu-core/commit/47e2da2df6cdda44cba5de5b01408cc9a7560e1d))


## v1.26.2 (2025-09-03)

### Bug Fixes

- Changed color of send button.
  ([`7b2122b`](https://github.com/core4x/collectu-core/commit/7b2122b42266f72ac61caed18ed99ff21b36f2f4))


## v1.26.1 (2025-09-03)

### Bug Fixes

- Adjusted button colors.
  ([`06e2404`](https://github.com/core4x/collectu-core/commit/06e2404d189a0968a79d0b4d9c9dab1b86d46b12))

- Removed title from configuration parameters of user input modules and replaced with name.
  ([`0f517db`](https://github.com/core4x/collectu-core/commit/0f517dbb02efe3a12ec92786298376ae2c2af75d))


## v1.26.0 (2025-09-02)

### Bug Fixes

- Added config param to make all mcp endpoints tools, since resources and resource_templates are
  currently not supported by most of the LLMs and langchain.
  ([`020f220`](https://github.com/core4x/collectu-core/commit/020f220281a9be405cd80424f11bccb8355bc101))

### Features

- Show user input masks in dashboard as well.
  ([`c4e672d`](https://github.com/core4x/collectu-core/commit/c4e672d0f04ce6ccefeaf567b4d99acecc5b61d0))


## v1.25.2 (2025-08-25)

### Bug Fixes

- Adjusted llm docs sitemap url.
  ([`c96b4a0`](https://github.com/core4x/collectu-core/commit/c96b4a02ff6d6c2555aa087249cabe140716e9b8))


## v1.25.1 (2025-08-25)

### Bug Fixes

- Adjusted llm docs sitemap url.
  ([`fd300b3`](https://github.com/core4x/collectu-core/commit/fd300b3db24bfda9e6e61ce63b4f830afc83ea5c))


## v1.25.0 (2025-08-25)

### Bug Fixes

- Added error string to log, if api or frontend could not be started.
  ([`4e38f82`](https://github.com/core4x/collectu-core/commit/4e38f8203c1abd8303360ba1b150990f3c38967d))

- Fixed save_configuration_as_file if no content was given, we have to stringify it before
  validating.
  ([`9c7cf9f`](https://github.com/core4x/collectu-core/commit/9c7cf9fae0f397c7810bf609dbd21ea706d2102e))

- Reformatted.
  ([`56cd68a`](https://github.com/core4x/collectu-core/commit/56cd68a193248e9f7796192957dd72d878688a4f))

### Features

- Added HUB_LLM_DOCS_ADDRESS.
  ([`5ee5ec1`](https://github.com/core4x/collectu-core/commit/5ee5ec1c946542d67d2c99c3892dc03cd3bff391))

- Added mcp endpoints.
  ([`43e4b95`](https://github.com/core4x/collectu-core/commit/43e4b95472b9bfddc46fee74cca6168b98b44f0b))


## v1.24.1 (2025-08-21)

### Bug Fixes

- Initial commit.
  ([`f0a745c`](https://github.com/core4x/collectu-core/commit/f0a745c4f825ccbe50d1e1b319d4fb4396e7cf25))

- Made MCP disabled by default.
  ([`a56b948`](https://github.com/core4x/collectu-core/commit/a56b948fa5257605865f3106de57110aa9c5e255))


## v1.24.0 (2025-08-19)

### Bug Fixes

- Changed default hosts from 127.0.0.1 to 0.0.0.0.
  ([`a474e06`](https://github.com/core4x/collectu-core/commit/a474e06a7c0019b78d3149957838ca284cdd49a2))

- Fixed lifespan if mcp is not enabled.
  ([`57f99fb`](https://github.com/core4x/collectu-core/commit/57f99fb17343185d31114c83356ba42293a3862e))

- Fixed logging things.
  ([`2627f36`](https://github.com/core4x/collectu-core/commit/2627f36f258c855755920d51bb2297416e56ac75))

- Fixed translation.
  ([`dd2ce47`](https://github.com/core4x/collectu-core/commit/dd2ce478de46bdd84abeb81d8898fc2fe3035dc4))

- Improved MCP server.
  ([`ea90a7e`](https://github.com/core4x/collectu-core/commit/ea90a7e7e9aa25c57c1f8592f580ce9df2f6f874))

- Made field and tag values right aligned.
  ([`152a4e4`](https://github.com/core4x/collectu-core/commit/152a4e4db3195b85f6d946d8e53d219eb3b3355d))

- Made mcp optional.
  ([`d34d056`](https://github.com/core4x/collectu-core/commit/d34d0569492ba8154306152e595d4cce89e3177a))

- Made uvicorn loop 'auto' from 'asyncio'.
  ([`8ca1e7e`](https://github.com/core4x/collectu-core/commit/8ca1e7e204f5392b069a36e416ff533e9e47233c))

### Features

- Added MCP server.
  ([`ff5fea6`](https://github.com/core4x/collectu-core/commit/ff5fea6d41d69eb339359a80a7e01f3d0b7df980))


## v1.23.14 (2025-08-12)

### Bug Fixes

- Include logger name in console.
  ([`9c66d17`](https://github.com/core4x/collectu-core/commit/9c66d1700d5b28b8d99c0792f7d57524d985b471))


## v1.23.13 (2025-08-07)

### Bug Fixes

- Use v10 instead of unstable master for python-semantic-release.
  ([`dab797d`](https://github.com/core4x/collectu-core/commit/dab797de41706f2775df24d953241d2fbca2d3ad))


## v1.23.12 (2025-08-07)

### Bug Fixes

- Fixed workflow.
  ([`27c946e`](https://github.com/core4x/collectu-core/commit/27c946e9c8c2af77f997432227925ff8563a7cdc))


## v1.23.11 (2025-08-07)

### Bug Fixes

- Improved logging by including module name and id in base classes.
  ([`6f5a439`](https://github.com/core4x/collectu-core/commit/6f5a43927596380cd5803a0998bce9fb8232630b))


## v1.23.10 (2025-08-07)

### Bug Fixes

- Fixed trigger of workflow.
  ([`70150ed`](https://github.com/core4x/collectu-core/commit/70150edcfb9941b37280228719e60d318cf64517))


## v1.23.9 (2025-08-07)

### Bug Fixes

- Improved error message if execution of processor module fails.
  ([`90047d8`](https://github.com/core4x/collectu-core/commit/90047d8be0f4cbafbe7bfc814bc94e4e57dd034a))


## v1.23.8 (2025-08-07)

### Bug Fixes

- Get triggered if new tag is released.
  ([`6bd5ce4`](https://github.com/core4x/collectu-core/commit/6bd5ce4f59f4e13fa5bffa06a6073a0753e702f4))


## v1.23.7 (2025-08-07)

### Bug Fixes

- Only start frontend if api is enabled.
  ([`7fff221`](https://github.com/core4x/collectu-core/commit/7fff221216a9ddd6ab0e62d63ae0e21d4d10d43a))


## v1.23.6 (2025-08-07)

### Bug Fixes

- Adjusted name of workflow.
  ([`d63ebef`](https://github.com/core4x/collectu-core/commit/d63ebef080094d562766dc6f3e0f72dddb57c2a6))

- Split into two workflows in order to receive tag version.
  ([`bf04518`](https://github.com/core4x/collectu-core/commit/bf0451863f8970d2c0fc5949479d5b69efc4fb60))


## v1.23.5 (2025-08-07)

### Bug Fixes

- Improved to fetch repo with newly created tags.
  ([`5d54590`](https://github.com/core4x/collectu-core/commit/5d545902645be879491b65ea3eab12df9c6dcb05))


## v1.23.4 (2025-08-07)

### Bug Fixes

- Do not delete old verisons.
  ([`dfcd384`](https://github.com/core4x/collectu-core/commit/dfcd384f45be9009c10dea31a5df0a09e93c1773))


## v1.23.3 (2025-08-07)

### Bug Fixes

- Fixed tags.
  ([`9c36d54`](https://github.com/core4x/collectu-core/commit/9c36d54595731807c6b55a6d500752eec138df45))


## v1.23.2 (2025-08-07)

### Bug Fixes

- Fixed triggering because main.yml is in the same workflow.
  ([`26d98eb`](https://github.com/core4x/collectu-core/commit/26d98ebcdd9df5ea543204aa20216c8dbcbafd3d))


## v1.23.1 (2025-08-07)

### Bug Fixes

- Updated translations.
  ([`214669b`](https://github.com/core4x/collectu-core/commit/214669b2ef39abf58903cf54e99b77f445f94b77))


## v1.23.0 (2025-08-07)

### Bug Fixes

- Removed docker image creation.
  ([`64adf89`](https://github.com/core4x/collectu-core/commit/64adf896f7c5b831e2526ba4fb2bf96948376697))

### Features

- Create release.yml
  ([`b3c36aa`](https://github.com/core4x/collectu-core/commit/b3c36aa04f54eb924dffd764a6d2189b482d8e5c))


## v1.22.3 (2025-08-07)

### Bug Fixes

- Added additional platform.
  ([`29d01af`](https://github.com/core4x/collectu-core/commit/29d01af0f610c9f14a03427e83460edcc3b578db))


## v1.22.2 (2025-08-07)


## v1.22.1 (2025-08-07)

### Bug Fixes

- Adjusted image tags.
  ([`d6b24f3`](https://github.com/core4x/collectu-core/commit/d6b24f3c933e03496f15af4255f7a72a47020394))

- Fixed tag generation for images.
  ([`f9e8afd`](https://github.com/core4x/collectu-core/commit/f9e8afd96dbe6bbe6e2f2a8daac3b08fee3cd35f))


## v1.22.0 (2025-08-07)

### Bug Fixes

- Changed hosts from 127.0.0.1 to 0.0.0.0.
  ([`a3d8d75`](https://github.com/core4x/collectu-core/commit/a3d8d75a30c2a7f261f14542bf90e96171052557))

- Removed URL.
  ([`fa41f78`](https://github.com/core4x/collectu-core/commit/fa41f789c52a7a03f3608eba77f2988f65b1e117))

### Features

- Dynamically determine host address the request was made to.
  ([`e66dd6d`](https://github.com/core4x/collectu-core/commit/e66dd6d3a11214fd5be59c10eb3946af9de0c954))


## v1.21.4 (2025-08-06)

### Bug Fixes

- Added platform info tag.
  ([`bf62aa7`](https://github.com/core4x/collectu-core/commit/bf62aa7f4580839817d69668b362f7678f2aa78f))


## v1.21.3 (2025-08-06)

### Bug Fixes

- Added default value for API_AUTHENTICATION env var.
  ([`8f21739`](https://github.com/core4x/collectu-core/commit/8f2173975e2c9f809a3307794ea19725f7f950b2))


## v1.21.2 (2025-08-06)

### Bug Fixes

- Added QEMU to docker build.
  ([`cebf702`](https://github.com/core4x/collectu-core/commit/cebf702afbfa389a3f9c9f72ed6182e7d09185df))


## v1.21.1 (2025-08-06)

### Bug Fixes

- Fixed multi-arch build for ghcr.
  ([`c1f3a8d`](https://github.com/core4x/collectu-core/commit/c1f3a8df7bd978bacc928c3d0ed181061d81957d))


## v1.21.0 (2025-08-06)

### Features

- Added multi-arch docker image builds.
  ([`9eab203`](https://github.com/core4x/collectu-core/commit/9eab203ffa4f91d1c89fd1a8c93d6e6a7a3d62a7))


## v1.20.0 (2025-08-05)

### Bug Fixes

- Folder text is now correctly indented with the depth.
  ([`44e7178`](https://github.com/core4x/collectu-core/commit/44e7178187d64732edd3fb6c1ce79cdf3c1b6418))

### Features

- Updated icon packages.
  ([`3c6167a`](https://github.com/core4x/collectu-core/commit/3c6167aa95ce7ec0d8f46b3d84eda0f6a2a8ab76))


## v1.19.5 (2025-07-30)

### Bug Fixes

- Adjusted height of left panel.
  ([`1039e5d`](https://github.com/core4x/collectu-core/commit/1039e5de65d41a091632caf3438cb01bc8fa0577))


## v1.19.4 (2025-07-29)

### Bug Fixes

- Handle case, if module config does not define a panel.
  ([`0b5cd0c`](https://github.com/core4x/collectu-core/commit/0b5cd0c3e0027e82525019f1736ed7b320038481))


## v1.19.3 (2025-07-29)

### Bug Fixes

- Removed changed ownership.
  ([`bca2f77`](https://github.com/core4x/collectu-core/commit/bca2f77a48fa04d3c12de06916778c625493cb2c))


## v1.19.2 (2025-07-29)

### Bug Fixes

- User ownership and git safe directory added.
  ([`ac19e22`](https://github.com/core4x/collectu-core/commit/ac19e228ba95ff33c748e8e553c6230006ccbc09))


## v1.19.1 (2025-07-29)


## v1.19.0 (2025-07-28)

### Bug Fixes

- User ownership and git safe directory added.
  ([`49a91b9`](https://github.com/core4x/collectu-core/commit/49a91b9383a0d0ec7d1d91310d17cf041a333def))

### Features

- Added AI assistent translations.
  ([`c431207`](https://github.com/core4x/collectu-core/commit/c4312070ef0a3efb6ab7373fd94f1eb7e37e4c49))


## v1.18.0 (2025-07-28)

### Features

- Added AI assistent.
  ([`59d0bbe`](https://github.com/core4x/collectu-core/commit/59d0bbe31d689aeb1de47a3bfba1c864752f6d0b))


## v1.17.11 (2025-07-22)

### Bug Fixes

- Fixed for paths containing empty space.
  ([`0a5891a`](https://github.com/core4x/collectu-core/commit/0a5891a6585896064e1e112fc54519af7a6d4966))


## v1.17.10 (2025-07-21)

### Bug Fixes

- Fixed searching for files helper funciton.
  ([`ee6bcf2`](https://github.com/core4x/collectu-core/commit/ee6bcf2149bcd214d74ce4656b7c61ab7b11817e))


## v1.17.9 (2025-07-21)

### Bug Fixes

- Fixed getting version.
  ([`8e1fe6b`](https://github.com/core4x/collectu-core/commit/8e1fe6bf47f4a568972066fc728399393c00180b))

- Fixed setting of env vars.
  ([`76158e5`](https://github.com/core4x/collectu-core/commit/76158e58b9be0ea18ee342ca5708f3a5da66eb84))


## v1.17.8 (2025-07-21)

### Bug Fixes

- Fixed getting version.
  ([`942673f`](https://github.com/core4x/collectu-core/commit/942673f76f4a1c4f5abce4cc29cae4fd7e308d2d))


## v1.17.7 (2025-07-18)

### Bug Fixes

- Improved and unified log message for up-to-date.
  ([`9553902`](https://github.com/core4x/collectu-core/commit/95539025eade531efa9e26f1efefb4ae2153f15e))

- Refactored updater.
  ([`2358cc9`](https://github.com/core4x/collectu-core/commit/2358cc90550191a403ae8e8cc82d00f629ffc61b))


## v1.17.6 (2025-07-18)

### Bug Fixes

- Improved log messages.
  ([`2820c78`](https://github.com/core4x/collectu-core/commit/2820c785bebae477a2c6b91f232fdaf27020e65a))


## v1.17.5 (2025-07-18)

### Bug Fixes

- Improved log messages.
  ([`3228fe7`](https://github.com/core4x/collectu-core/commit/3228fe76beed920e3433623f7757716c6e3cecc9))


## v1.17.4 (2025-07-08)

### Bug Fixes

- Fixed procedure for sending modules to hub.
  ([`f5e310c`](https://github.com/core4x/collectu-core/commit/f5e310cac47f043797094db539a1b41230a40445))


## v1.17.3 (2025-07-04)

### Bug Fixes

- Get version.
  ([`40ff779`](https://github.com/core4x/collectu-core/commit/40ff77987b200e3f7a385952215295c3d04c28d9))


## v1.17.2 (2025-07-04)

### Bug Fixes

- Do not update version but automatically restart after update.
  ([`86ba61d`](https://github.com/core4x/collectu-core/commit/86ba61d154c409001f11c68585b05d826569c2f6))


## v1.17.1 (2025-06-24)

### Bug Fixes

- Improved starting procedure.
  ([`56fe253`](https://github.com/core4x/collectu-core/commit/56fe25334cc235e819fcfd47e6fbca5e1b00b8fc))

- Improved stopping procedure.
  ([`cb9394a`](https://github.com/core4x/collectu-core/commit/cb9394a7fc8a26a49bb735dea023cade4d1541e4))


## v1.17.0 (2025-06-11)

### Features

- Refactored abort controller for websocket connections.
  ([`6ec6340`](https://github.com/core4x/collectu-core/commit/6ec6340f3e70334353239ce9ebe156176add8165))


## v1.16.5 (2025-06-10)

### Bug Fixes

- Try to properly close stream connection between api and frontend. This should solve the
  'socket.accept() out of system resource socket' bug.
  ([`9b6f058`](https://github.com/core4x/collectu-core/commit/9b6f058d7a7e831b2fdf984fe52f7f82785c8a46))


## v1.16.4 (2025-06-10)

### Bug Fixes

- Try to properly close stream connection between api and frontend. This should solve the
  'socket.accept() out of system resource socket' bug.
  ([`d3e3dbc`](https://github.com/core4x/collectu-core/commit/d3e3dbc450e8d214d385ec0d4cbde60008ebf2f4))


## v1.16.3 (2025-06-10)

### Bug Fixes

- Try to properly close stream connection between api and frontend. This should solve the
  'socket.accept() out of system resource socket' bug.
  ([`c161aa4`](https://github.com/core4x/collectu-core/commit/c161aa420473f78e4072373ca3aad16a7e99f622))


## v1.16.2 (2025-06-10)

### Bug Fixes

- Try to properly close stream connection between api and frontend. This should solve the
  'socket.accept() out of system resource socket' bug.
  ([`84f18e7`](https://github.com/core4x/collectu-core/commit/84f18e7f678490985352e29f68c69d6e606a4247))


## v1.16.1 (2025-06-06)

### Bug Fixes

- Write info message if retry procedure for starting a module was successful.
  ([`9721723`](https://github.com/core4x/collectu-core/commit/972172331102348a660d595687edf08f55513abc))


## v1.16.0 (2025-05-23)

### Features

- Retry getting the hub username if the initial procedure fails during initialization.
  ([`87bec6c`](https://github.com/core4x/collectu-core/commit/87bec6c385c1083a20fbc5484951d3025bd49fa4))


## v1.15.0 (2025-05-04)


## v1.14.0 (2025-05-03)

### Bug Fixes

- Updated translations.
  ([`0ad241e`](https://github.com/core4x/collectu-core/commit/0ad241e449e7b35e44c05027a135d3dfe1e2a755))

### Features

- Added module version update functionality to retrieve the latest version from the Hub.
  ([`35cb1e3`](https://github.com/core4x/collectu-core/commit/35cb1e3f18e39fbeb15f28ec8893f13628bc34f3))

- Integrated code editor for module code into the info view.
  ([`fa31b30`](https://github.com/core4x/collectu-core/commit/fa31b30225b185e7ae3fad52defd26363c3eda18))


## v1.13.4 (2025-04-28)


## v1.13.3 (2025-04-28)

### Bug Fixes

- Fixed check (now not null and not undefined) of valid value for text dashboard element. Otherwise,
  the value '0' is not displayed.
  ([`4e44509`](https://github.com/core4x/collectu-core/commit/4e445096becb24ee9052df680b79933e63eee293))

- Git_access_token file is not access via absolute path to make it more reliable.
  ([`b1cedc1`](https://github.com/core4x/collectu-core/commit/b1cedc1628dfc1904557351fd7ff8f75c7484c53))


## v1.13.2 (2025-04-13)

### Bug Fixes

- Switched language button content. If the current site is english, show 'de' and otherwise.
  ([`d4bb20b`](https://github.com/core4x/collectu-core/commit/d4bb20b297e6a858227336682c3e6c8815666682))


## v1.13.1 (2025-04-11)

### Bug Fixes

- Updated to v1.0.8 to work with newest firefox.
  ([`45fe3f6`](https://github.com/core4x/collectu-core/commit/45fe3f626eaea4760817361570eccc98bf84f0e2))


## v1.13.0 (2025-04-06)

### Features

- Updated third party packages.
  ([`888c517`](https://github.com/core4x/collectu-core/commit/888c51788fa4a97f7db493eee03ba02c7399bd10))


## v1.12.8 (2025-03-26)


## v1.12.7 (2025-03-26)

### Bug Fixes

- Fixed starting routine in order to consider the starting priority and also to provide client
  instances to variable and tag modules.
  ([`68a9ac9`](https://github.com/core4x/collectu-core/commit/68a9ac9c6b0b3b737cb79954403f45ec2ca52a3b))

- Fixed staticmethod and classmethod things.
  ([`e7c69d4`](https://github.com/core4x/collectu-core/commit/e7c69d435b5d1d7e65afb32fb5ff692d3dfd8354))


## v1.12.6 (2025-03-25)

### Bug Fixes

- Added some logs if we retry to start a module.
  ([`30b0be8`](https://github.com/core4x/collectu-core/commit/30b0be8846cd1a0e61f2eeb693c811884f6a4410))

- Refactored the start and retry procedure.
  ([`4de39e3`](https://github.com/core4x/collectu-core/commit/4de39e3f6b942541f8ac99b6659fdd06859eca35))

- Refactored the start and retry procedure.
  ([`ec1f809`](https://github.com/core4x/collectu-core/commit/ec1f809c1336b347cda2fb3f6b7cb4f4c938ce41))

- Removed ignore_start_fail setting.
  ([`867518f`](https://github.com/core4x/collectu-core/commit/867518f324c5bfcfac5f1d1bac479aa6d50d4aca))

- Removed MAX_ATTEMPTS since we refactored the retry procedure.
  ([`2271350`](https://github.com/core4x/collectu-core/commit/227135060272c88e19668750dad56dc2f04ee10b))

- Removed since we refactored the retry procedure.
  ([`266e619`](https://github.com/core4x/collectu-core/commit/266e619e03b86fa60efeab3ba75a7f55666cc110))

### Documentation

- Improved description of STOP_TIMEOUT.
  ([`5d007ff`](https://github.com/core4x/collectu-core/commit/5d007ff39dfe6a1d2799ea9886c3ebae8a67a9cd))


## v1.12.5 (2025-03-25)

### Bug Fixes

- Added threaded stop method call to remove_modules_from_configuration and added logs to method.
  ([`54ffc20`](https://github.com/core4x/collectu-core/commit/54ffc209bac50041c67888126968b1d9440a1b2e))


## v1.12.4 (2025-03-24)

### Bug Fixes

- Also show lists of objects stringified.
  ([`b88644e`](https://github.com/core4x/collectu-core/commit/b88644ec85f6d72187eb38ebff426ddc1647988c))


## v1.12.3 (2025-03-21)

### Bug Fixes

- Added error message for unexpected login fail.
  ([`c0e1943`](https://github.com/core4x/collectu-core/commit/c0e19438df97adb6ae96c8904729b8e513bdc8e9))


## v1.12.2 (2025-03-19)

### Bug Fixes

- Convert nested objects to string to be displayable.
  ([`1a876de`](https://github.com/core4x/collectu-core/commit/1a876de3748e4088a94b63c5dfd3ca285b48d659))


## v1.12.1 (2025-03-18)

### Bug Fixes

- Updated translations.
  ([`c59ebf3`](https://github.com/core4x/collectu-core/commit/c59ebf38a531e1f6ef8e2e27ae10adf013df690a))


## v1.12.0 (2025-03-18)


## v1.11.1 (2025-03-18)

### Bug Fixes

- Fixed corrupted file.
  ([`deb7d83`](https://github.com/core4x/collectu-core/commit/deb7d831511a7a7f7ad8e86dee6c727fa4644367))

- Fixed order of imports of third-party packages in order to be able to install dependencies on
  start-up.
  ([`2853982`](https://github.com/core4x/collectu-core/commit/2853982bc2e58baec07f6e16f52875930cd485ee))

- Removed test mode.
  ([`180d38c`](https://github.com/core4x/collectu-core/commit/180d38cb5f5275eff9488485f6c80cc337e90733))

### Features

- Added field_requirements and tag_requirements to output modules.
  ([`4614694`](https://github.com/core4x/collectu-core/commit/461469476aa948fff707420e86772870442bdb94))

- Improved stopping routine, to proceed also in the case of blocking stop methods of modules.
  ([`f87386a`](https://github.com/core4x/collectu-core/commit/f87386a75b731015475bb2460f0d5f3e756667a4))


## v1.11.0 (2025-03-17)

### Bug Fixes

- Fixed corrupted file.
  ([`3687913`](https://github.com/core4x/collectu-core/commit/3687913e944752d4e022bedde8e97424de45f0f0))

### Features

- Split requirements.txt for core and interface.
  ([`b939dcd`](https://github.com/core4x/collectu-core/commit/b939dcdba59858b1bc39400ef0ea0aab9f4fc1f9))


## v1.10.0 (2025-03-17)

### Features

- Added width and dashboard.
  ([`5e55e8a`](https://github.com/core4x/collectu-core/commit/5e55e8abadf500072cfb1bfb3f27604e473bdf1e))


## v1.9.5 (2025-03-17)


## v1.9.4 (2025-03-17)

### Bug Fixes

- Moved variable clearing of data_layer into finally block during stopping.
  ([`8dad07f`](https://github.com/core4x/collectu-core/commit/8dad07f4d6705a4a8693d0dcb309de485a505199))


## v1.9.3 (2025-03-17)

### Bug Fixes

- Handle disconnection of streams properly.
  ([`d8a3f38`](https://github.com/core4x/collectu-core/commit/d8a3f3836882e68fab485f9094f327c6a235dd62))


## v1.9.2 (2025-03-17)

### Bug Fixes

- Changed streams to text/event-stream.
  ([`781dec2`](https://github.com/core4x/collectu-core/commit/781dec245ebe1b221d51dbbc39270db1538539f9))

- Check if module data is defined before generating stream response.
  ([`1d35585`](https://github.com/core4x/collectu-core/commit/1d355857794a0398a2ab977263356b96b8964c9e))

### Documentation

- Fixed name of function.
  ([`df91582`](https://github.com/core4x/collectu-core/commit/df91582248519aa864eaf5d684ef4ab331508922))


## v1.9.1 (2025-03-13)

### Bug Fixes

- Fixed function call _dyn. Renamed input_string to input_data.
  ([`24936be`](https://github.com/core4x/collectu-core/commit/24936becdca60cda64a726f2ccdd738833099ecb))

- Improved some settings if in DEBUG mode in order to see exceptions.
  ([`8ad9c50`](https://github.com/core4x/collectu-core/commit/8ad9c50a40dea7dd98cf31bdc79292a16661f977))


## v1.9.0 (2025-03-13)

### Features

- Made yaml optional. Using json as fallback.
  ([`145dc1a`](https://github.com/core4x/collectu-core/commit/145dc1ad9d229ea5da28c32f6646920adf20bd05))


## v1.8.3 (2025-03-12)

### Bug Fixes

- Changed place of internal imports in order to set up logger before importing.
  ([`7ee0065`](https://github.com/core4x/collectu-core/commit/7ee00656f15c8b8ba44b00cf5f96b7d189494d81))

- Fixed check, if tinydb is installed during iterating all apps.
  ([`2fa92ab`](https://github.com/core4x/collectu-core/commit/2fa92abbfeffe7e7a36eaee5c1b9aee8dc5facbc))

- Fixed return type of database entry interactions.
  ([`73ac24c`](https://github.com/core4x/collectu-core/commit/73ac24c3358770f8fa2763508419408e88d10e36))

- Made internal imports only for type checking.
  ([`e66c987`](https://github.com/core4x/collectu-core/commit/e66c9872ca6a52811d38cbcdbbae6accff210322))

- Made markdown optional requirement.
  ([`40fda8d`](https://github.com/core4x/collectu-core/commit/40fda8de67a8c7a3300f5d2c9b9a53a4f480c414))

- Made tinydb optional requirement.
  ([`6a13b1f`](https://github.com/core4x/collectu-core/commit/6a13b1fc52f9616d1279694fba768bb0ad645263))

### Documentation

- Fixed docstring to contain correct information.
  ([`b783bf3`](https://github.com/core4x/collectu-core/commit/b783bf3130b8d8d8277e9233c8bfd087f9ac91f1))

- Fixed spelling in comment.
  ([`76c6c49`](https://github.com/core4x/collectu-core/commit/76c6c49c64f125d586b2ef5f9cdbd7445a1d4c13))

- Update README.md
  ([`61d9238`](https://github.com/core4x/collectu-core/commit/61d92381e24618659a4b4566939b6b947e954970))


## v1.8.2 (2025-03-12)

### Bug Fixes

- Delete src/modules/base/processors/README.md
  ([`f6296dc`](https://github.com/core4x/collectu-core/commit/f6296dcb351d6cfb7a97f400c0352df4ffc4e8e9))

- Delete src/modules/README.md
  ([`7ec694e`](https://github.com/core4x/collectu-core/commit/7ec694e53fb5d97d26eb823536f357b2d5ef8a33))


## v1.8.1 (2025-03-12)

### Bug Fixes

- Removed development hint.
  ([`4178523`](https://github.com/core4x/collectu-core/commit/4178523c29bd1938590facf6f7cc9cbc5538eb67))


## v1.8.0 (2025-03-08)


## v1.7.0 (2025-03-07)

### Features

- Frontend is now running in a separate process.
  ([`74abeef`](https://github.com/core4x/collectu-core/commit/74abeef719bf53ed1a07ddfaaaefd8efb2fe1427))

- Improved flask settings and added whitenoise for static file serving.
  ([`0a775e9`](https://github.com/core4x/collectu-core/commit/0a775e9addffaff609fb9f089b5fbf3dc5991a0e))


## v1.6.2 (2025-03-04)


## v1.6.1 (2025-03-04)

### Bug Fixes

- Added return value to load_and_process_settings_file in case of exception.
  ([`17243ab`](https://github.com/core4x/collectu-core/commit/17243ab0f1771fa2898323668db0a97bf937a5d2))

- Environment variables now have priority over settings.ini.
  ([`d8952ae`](https://github.com/core4x/collectu-core/commit/d8952ae05b46c12550914d82ea6a4058531aff6a))


## v1.6.0 (2025-02-22)

### Bug Fixes

- Improved data converting for dynamic variables.
  ([`1711d80`](https://github.com/core4x/collectu-core/commit/1711d80b292c2a8aa81ea395f65eb13299d46369))

### Documentation

- Added translations.
  ([`14b7a91`](https://github.com/core4x/collectu-core/commit/14b7a918d0fdbe75c758c2100eac963a13002089))

### Features

- Improved search functionality.
  ([`a3acf94`](https://github.com/core4x/collectu-core/commit/a3acf94ae959e3f75c0114b48932824ea529814a))


## v1.5.1 (2025-02-19)


## v1.5.0 (2025-02-19)

### Bug Fixes

- Removed debug message.
  ([`f0a933c`](https://github.com/core4x/collectu-core/commit/f0a933c1d0d344777d3e826d319fce9146b9139a))

### Features

- Generate app_description from hostname if not set.
  ([`d5b59d0`](https://github.com/core4x/collectu-core/commit/d5b59d0a600280c4a58d3c1297d49024e73dfd49))


## v1.4.3 (2025-02-09)

### Bug Fixes

- Increased waiting time in generator a little bit to improve overall performance.
  ([`d2f6fef`](https://github.com/core4x/collectu-core/commit/d2f6fef359a879e0125f5f5ee28b30904d1fb419))


## v1.4.2 (2025-02-06)

### Bug Fixes

- Remove white space while reading api access token.
  ([`628161c`](https://github.com/core4x/collectu-core/commit/628161cabf6318069577a4e6e6bda69ddb4716c1))


## v1.4.1 (2025-02-03)

### Bug Fixes

- Changed default frontend port from 8282 to 80.
  ([`4488798`](https://github.com/core4x/collectu-core/commit/448879888df5cfe04d95d0b1861fd9a2a743c186))


## v1.4.0 (2025-02-03)

### Bug Fixes

- Adjusted default values of method calls.
  ([`f347383`](https://github.com/core4x/collectu-core/commit/f347383394b0a3df9ad4a787f55d2ff6ae3b9d00))

### Features

- Added modules view and endpoints. Refactored plugin interface.
  ([`37a71ab`](https://github.com/core4x/collectu-core/commit/37a71ab41b6d9cb49c8289e92d8bf3c022f28b26))

- Added modules view and endpoints. Refactored plugin interface.
  ([`09c3509`](https://github.com/core4x/collectu-core/commit/09c3509af0ec7c35ac7b5af2dea24aaf68d897b6))


## v1.3.0 (2025-02-01)

### Features

- Get username if api access token is given.
  ([`f62e02e`](https://github.com/core4x/collectu-core/commit/f62e02e419d8eaf1263e90405f64ae690ed1d89a))


## v1.2.0 (2025-02-01)


## v1.1.3 (2025-02-01)

### Bug Fixes

- Added buffer to streams.
  ([`bb814f0`](https://github.com/core4x/collectu-core/commit/bb814f024f97cc20a4901c3a939e6ef7c6193711))

### Features

- Local dynamic variable can now be also measurement or time.
  ([`6d30ff5`](https://github.com/core4x/collectu-core/commit/6d30ff54eaa666fb022c82f39fe860d611241ace))


## v1.1.2 (2025-01-31)

### Bug Fixes

- Added more headers to prevent unknown compression.
  ([`426ca77`](https://github.com/core4x/collectu-core/commit/426ca773b491a6e7265914653cb2321577b0d127))

- Removed unnecessary variable declaration.
  ([`82b6a3b`](https://github.com/core4x/collectu-core/commit/82b6a3b3184ce480e4f489d0aaf44975469395f0))


## v1.1.1 (2025-01-31)

### Bug Fixes

- Fixed downloading procedure for modules.
  ([`beee673`](https://github.com/core4x/collectu-core/commit/beee673a21ef0196a0895f5a6c3acb32bf1ab0ff))


## v1.1.0 (2025-01-30)

### Features

- Further improvements.
  ([`ffb063a`](https://github.com/core4x/collectu-core/commit/ffb063aa4b42870e4e5695db04ed47f66d2ff9d0))


## v1.0.0 (2025-01-30)

### Bug Fixes

- Added buffer for streaming data.
  ([`ef7a6a4`](https://github.com/core4x/collectu-core/commit/ef7a6a41ad45f6592b4b443eb6ae5e8b35d9a92a))

- Disabled exc_info.
  ([`fda6bc0`](https://github.com/core4x/collectu-core/commit/fda6bc03622a10779830e99cc2836c82c8a15dc9))

### Features

- Further improvements.
  ([`dd38e96`](https://github.com/core4x/collectu-core/commit/dd38e96bce156b1271d4a98f81875449a72a46cb))

- Further improvements.
  ([`c064f84`](https://github.com/core4x/collectu-core/commit/c064f8438ffb2d8c949a4c9b1a8e6d8f98681d5d))

- Initial commit of new API and frontend.
  ([`79f65b9`](https://github.com/core4x/collectu-core/commit/79f65b97dca8fae849ef5b35eb85a56bd55619d6))


## v0.18.0 (2025-01-09)

### Bug Fixes

- Every mothership communication now has its own request session.
  ([`dc36a30`](https://github.com/core4x/collectu-core/commit/dc36a30b2e8927b31753d0e4f7983b01238cb276))

- If we are in debug logging mode, this also applies now for output module logging.
  ([`6c2e538`](https://github.com/core4x/collectu-core/commit/6c2e538936b611653448dfe0ba81f0d49f272db6))

### Features

- The config variable start_priority is now available for all modules and not only variable modules.
  ([`8d4b225`](https://github.com/core4x/collectu-core/commit/8d4b225fe62f52c0047ea080e02f4dada5368023))


## v0.17.3 (2025-01-03)

### Bug Fixes

- New style for configuration editor.
  ([`a912589`](https://github.com/core4x/collectu-core/commit/a9125898121e0d7730b544d52702d6ced1f008ab))


## v0.17.2 (2024-12-17)

### Bug Fixes

- Fixed module_name generation of custom modules.
  ([`65e41f0`](https://github.com/core4x/collectu-core/commit/65e41f06d6bbb08cdfc7ce086a5375d0bb0852eb))


## v0.17.1 (2024-12-16)

### Bug Fixes

- Added a time.sleep(0) in order to not block app, if data gets buffered in a loop.
  ([`713344a`](https://github.com/core4x/collectu-core/commit/713344a6ae33e17acdfe8e41837f49b85f4e2972))


## v0.17.0 (2024-12-08)

### Features

- Added possibility to add api_access_token as file.
  ([`c6930f8`](https://github.com/core4x/collectu-core/commit/c6930f8b2d6e14ff02db50c4fd626f95a3e716e7))

- Removed hub_api_access_token from settings file.
  ([`ddaaa04`](https://github.com/core4x/collectu-core/commit/ddaaa049436a169be0cc9f01c226dcbeb54e169d))


## v0.16.0 (2024-12-03)

### Features

- Removed name of logger in initially getting logger in order to receive the root logger.
  ([`056b527`](https://github.com/core4x/collectu-core/commit/056b527898f5e4596c7927b755259bc68d67eaa6))


## v0.15.4 (2024-11-28)

### Bug Fixes

- Changed filenames.
  ([`5ebec15`](https://github.com/core4x/collectu-core/commit/5ebec1527a4b615e07afdb16c6cec3c4670b9de4))


## v0.15.3 (2024-11-23)

### Bug Fixes

- Fixed use of datetime.
  ([`a18ca72`](https://github.com/core4x/collectu-core/commit/a18ca726cb8fb2845213bc4b90461243c2a64813))


## v0.15.2 (2024-11-22)

### Bug Fixes

- Load configuration before starting statistics and mothership communication.
  ([`7d09a91`](https://github.com/core4x/collectu-core/commit/7d09a916922a6bc5f710e55cf215d9478c3d827f))


## v0.15.1 (2024-11-21)


## v0.15.0 (2024-11-21)

### Bug Fixes

- Replace environment variables in the configuration module only, if the attribute is non-dynamic.
  Otherwise, the dynamic variable handling should be done in the modules themselves.
  ([`6dc2afc`](https://github.com/core4x/collectu-core/commit/6dc2afc9844c0e1f2cdf938add151643c29a2dcf))

### Features

- Dynamic environment variables can now be defined for every configuration parameter of a module.
  ([`2bcc10a`](https://github.com/core4x/collectu-core/commit/2bcc10a980700b24ea1759fd1623dee9d7f510ed))


## v0.14.1 (2024-11-19)


## v0.14.0 (2024-11-17)

### Bug Fixes

- Changed from datetime.utcnow() to datetime.now(timezone.utc) since it is better says the docs.
  ([`c2c637b`](https://github.com/core4x/collectu-core/commit/c2c637b520bf0559811f65dbcfc4c327ad81da9c))


## v0.13.0 (2024-11-09)

### Features

- Added util function to get a list of all used third party requirements by modules.
  ([`807163d`](https://github.com/core4x/collectu-core/commit/807163d454de83e2ae91a320835850804919b090))

- Fixed sizes of left panel.
  ([`6bcf3ee`](https://github.com/core4x/collectu-core/commit/6bcf3ee937d8b62b5170690f75140b352a8f9b98))


## v0.12.2 (2024-11-06)

### Bug Fixes

- Dump configuration object before loading.
  ([`468829a`](https://github.com/core4x/collectu-core/commit/468829ae1373d6b086b0a6c8f1c2cf790a0a0b95))


## v0.12.1 (2024-11-06)

### Bug Fixes

- Config comes now as json string.
  ([`02a9e8c`](https://github.com/core4x/collectu-core/commit/02a9e8c60fc19519d0cb32859cabc0bca41f8a51))


## v0.12.0 (2024-11-05)

### Bug Fixes

- Fixed extraction of dynamic variables.
  ([`255a590`](https://github.com/core4x/collectu-core/commit/255a590e8a3dc33e0112ce0d3ccaa71a0533e993))

### Features

- If no data type is defined, we use str.
  ([`fe6d1ca`](https://github.com/core4x/collectu-core/commit/fe6d1ca5ed73a64dc1fce939f724b955c2f51769))


## v0.11.0 (2024-11-03)


## v0.10.0 (2024-11-02)

### Features

- Removed send_data decorator. Use _call_links instead.
  ([`8fbb9d3`](https://github.com/core4x/collectu-core/commit/8fbb9d3ffdc1dc36314fc3e919aaeb0fc42ad44c))


## v0.9.0 (2024-11-02)

### Features

- Overworked start method of modules.
  ([`6466d4c`](https://github.com/core4x/collectu-core/commit/6466d4cd69f31d94fbb51bcd9d0c21312bf0e01b))

- Overworked start method of modules.
  ([`30ee410`](https://github.com/core4x/collectu-core/commit/30ee410abd64afd638af406b28f2c26c7b0c250b))


## v0.8.0 (2024-11-01)

### Features

- Added check if measurement exists before processing data object.
  ([`4d08b39`](https://github.com/core4x/collectu-core/commit/4d08b39acbf658f4052cd58bb9f08fba4a0f8a12))

- Added thread-safe functionality.
  ([`421e7a1`](https://github.com/core4x/collectu-core/commit/421e7a1df363226f3e2cbf08671229c74732624d))

- Improved base methods.
  ([`364e0a2`](https://github.com/core4x/collectu-core/commit/364e0a25939935366af13e141a68e13a1fb07ce5))


## v0.7.0 (2024-10-29)

### Features

- Check for updates after loading configuration.
  ([`4bdaa6e`](https://github.com/core4x/collectu-core/commit/4bdaa6e627dcb19a234e1e731ce814bd51662905))


## v0.6.5 (2024-10-26)

### Bug Fixes

- If None is given for a mandatory field of type union, we raise an error instead of converting.
  ([`2327b8e`](https://github.com/core4x/collectu-core/commit/2327b8eddff160db70849371cc1096c5608e2d8e))


## v0.6.4 (2024-10-18)


## v0.6.3 (2024-10-18)

### Bug Fixes

- Changed endpoint from get_public_by_module_name to get_by_module_name.
  ([`9abf3df`](https://github.com/core4x/collectu-core/commit/9abf3df1b2ec35998b41954f77026b497d65efe8))


## v0.6.2 (2024-10-18)

### Bug Fixes

- Prevent updater from tyring to clone interface submodule if not wanted.
  ([`dffe900`](https://github.com/core4x/collectu-core/commit/dffe900e324467538f35e0a0fc3fa77b92e22a52))


## v0.6.1 (2024-10-17)

### Bug Fixes

- Adjusted directories since we moved the files into subfolders.
  ([`b52985e`](https://github.com/core4x/collectu-core/commit/b52985e33273aff3d41b47826de4cf634f8da5fd))


## v0.6.0 (2024-10-16)

### Bug Fixes

- If the interface submodule can not be updated (e.g. due to blocking ssh), we ignore it and try a
  normal pull request.
  ([`be2a199`](https://github.com/core4x/collectu-core/commit/be2a1993e82f717cff247a0542b8a2e0b681513a))

### Documentation

- Added todo.
  ([`ffd2b92`](https://github.com/core4x/collectu-core/commit/ffd2b92c72eb44c2dd2a31e968531397d7c7af73))

### Features

- Added ssl support for hub communication.
  ([`007f78c`](https://github.com/core4x/collectu-core/commit/007f78cb0ed4164f6d11d39266b2b19ebf189a62))


## v0.5.0 (2024-10-13)

### Documentation

- Extended nested modules list.
  ([`b6e2abc`](https://github.com/core4x/collectu-core/commit/b6e2abcd2e967d10888b7bd42f0f2a428f543866))

### Features

- Added shell scripts for linux.
  ([`49b0df2`](https://github.com/core4x/collectu-core/commit/49b0df27af4468490703322e9f1fc9df9593c681))


## v0.4.4 (2024-10-09)

### Documentation

- Improved log message.
  ([`0f14184`](https://github.com/core4x/collectu-core/commit/0f14184d78f819d15d834feee2c8dea9491867d7))


## v0.4.3 (2024-10-09)

### Bug Fixes

- Fixed some things to improve the hub interaction.
  ([`b7dbad2`](https://github.com/core4x/collectu-core/commit/b7dbad2172c47569cea6730d16e58c3de89eb095))


## v0.4.2 (2024-10-09)

### Bug Fixes

- Fixed check if module already exists.
  ([`81624f8`](https://github.com/core4x/collectu-core/commit/81624f8a75c356676f68201a94c03b24e484f7d4))


## v0.4.1 (2024-10-09)

### Bug Fixes

- Fixed check if custom module folder exists.
  ([`5b5c160`](https://github.com/core4x/collectu-core/commit/5b5c1600c935a5f243cc72cfde8b5c8e314964a1))


## v0.4.0 (2024-10-09)

### Bug Fixes

- If all modules shall be sent, leave the list empty and not None.
  ([`03a611c`](https://github.com/core4x/collectu-core/commit/03a611cab9c904bcef60bac7241506cc6e5eef4e))

- Load modules after initialization.
  ([`b87ee15`](https://github.com/core4x/collectu-core/commit/b87ee15df82d68fa475c14713e13640f8c80df3f))

- Removed unnecessary files.
  ([`c7aae26`](https://github.com/core4x/collectu-core/commit/c7aae26cce96a76653eda5c795910b29c838f247))

- Rename package typing-extensions to typing_extensions otherwise, it is installed every start since
  the package name in requirements.txt differs from the "online" one.
  ([`f534fe9`](https://github.com/core4x/collectu-core/commit/f534fe9d6b1e2f1b66be6324590d63b434410d2b))

- Updated deprecated use of pkg_resources.working_set.
  ([`2a6352e`](https://github.com/core4x/collectu-core/commit/2a6352e9d00b5fcb666d54a6c6591e6fb227b94a))

### Features

- Added custom_module_folder variable.
  ([`46a4924`](https://github.com/core4x/collectu-core/commit/46a492415812fd63fa3dc9cac3b31e92fba370ac))

- Added functionality to include a custom module folder.
  ([`a9e1139`](https://github.com/core4x/collectu-core/commit/a9e11393856d8906be22863a0c78d6fd95a38409))


## v0.3.2 (2024-09-04)

### Bug Fixes

- Added tag for module cards and now check if a card is a module by this tag and no longer by
  checking if a footer exists.
  ([`4d2b5e6`](https://github.com/core4x/collectu-core/commit/4d2b5e669b99af19a325c7fc2ebff611916785d6))


## v0.3.1 (2024-09-03)


## v0.3.0 (2024-09-02)

### Bug Fixes

- Now, if the config of a module was changed (without executing) it will be shown, when newly
  opening the config modal.
  ([`b88c853`](https://github.com/core4x/collectu-core/commit/b88c85322d72f9c1b25da58fc503f81467d6ea08))

### Features

- The version of a module can now be changed.
  ([`1232e3d`](https://github.com/core4x/collectu-core/commit/1232e3dfb8e6b31071640bd027d194fe17ce6691))


## v0.2.1 (2024-09-02)

### Bug Fixes

- Added timeout for requests.
  ([`aa400d5`](https://github.com/core4x/collectu-core/commit/aa400d5fdc575338fbde7738fec3dc1b2860cf97))

- Removed unnecessary imports.
  ([`e6a27c5`](https://github.com/core4x/collectu-core/commit/e6a27c55b4e36b330c392e8ccdc679c0c6ffd435))


## v0.2.0 (2024-08-26)

### Features

- Added check that all versions of a module type are the same.
  ([`0453a28`](https://github.com/core4x/collectu-core/commit/0453a28f55b8148497643d95d59b5163d2835db6))

- Added log messages about which configuration file was loaded.
  ([`fc2dc83`](https://github.com/core4x/collectu-core/commit/fc2dc833c5bb62cbf778aa6c313f3936dec15956))


## v0.1.2 (2024-08-22)

### Bug Fixes

- Config fields with dynamic variables are no longer Json parsed after saving. By doing so, they are
  treated as string.
  ([`9077391`](https://github.com/core4x/collectu-core/commit/907739166c66eabbf53cf1e3d2d5da7b5e2edb54))


## v0.1.1 (2024-08-21)

### Bug Fixes

- Dynamic variables in a configuration shall be always handled as string.
  ([`8348a49`](https://github.com/core4x/collectu-core/commit/8348a4948d4e84b49e15eae4cb743e14fc5bfb06))


## v0.1.0 (2024-06-18)

### Features

- Added hint for further info.
  ([`c3964e2`](https://github.com/core4x/collectu-core/commit/c3964e2823695b593e20f89080b911f89a7937e9))


## v0.0.60 (2024-05-29)

### Bug Fixes

- Added accidentally deleted constant.
  ([`099111d`](https://github.com/core4x/collectu-core/commit/099111dc3480fc9e559841d02c28b7280da70fae))


## v0.0.59 (2024-05-26)

### Bug Fixes

- Replaced app_name with app_description.
  ([`b6eb499`](https://github.com/core4x/collectu-core/commit/b6eb4992ab64fa0b151ece7bfb0ae6b65c02ab0e))


## v0.0.58 (2024-05-22)


## v0.0.57 (2024-05-22)

### Bug Fixes

- Catch errors preventing complete start due to update failure.
  ([`68a8cc5`](https://github.com/core4x/collectu-core/commit/68a8cc5d83df5ab2c6ac170aaa5607d6e9953d7f))

- Catch errors preventing complete start due to update failure.
  ([`f649d0f`](https://github.com/core4x/collectu-core/commit/f649d0f93797d1accc7c398cc401aef5457fa8c0))


## v0.0.56 (2024-05-09)

### Bug Fixes

- Always reload module after import, in the case it already exists before downloading a new version.
  ([`c3def21`](https://github.com/core4x/collectu-core/commit/c3def211a21f07f1487be8759269ff8624a65c29))


## v0.0.55 (2024-05-07)

### Bug Fixes

- Fixed error message generation.
  ([`37b4995`](https://github.com/core4x/collectu-core/commit/37b49958e934bcf75ee396544c1ddec2e28f86ef))


## v0.0.54 (2024-05-06)

### Bug Fixes

- Fixed downloading.
  ([`0b0f21e`](https://github.com/core4x/collectu-core/commit/0b0f21e5e10b17f703eff5d5aaa71db14669556c))


## v0.0.53 (2024-05-05)


## v0.0.52 (2024-05-05)

### Bug Fixes

- Changed logo.
  ([`59c5d1e`](https://github.com/core4x/collectu-core/commit/59c5d1e93c97aafcd46a4f81bcaad031119c2dc5))


## v0.0.51 (2024-05-05)

### Bug Fixes

- Changed logo.
  ([`ccc9b58`](https://github.com/core4x/collectu-core/commit/ccc9b58b62678892be5f56c93db2c6db0584ba69))

- Changed logo.
  ([`df5ce95`](https://github.com/core4x/collectu-core/commit/df5ce95bba77814abdfb72c7525b0ee97c222cfc))


## v0.0.50 (2024-04-20)

### Bug Fixes

- Apps are now sending the correct version.
  ([`5917f9c`](https://github.com/core4x/collectu-core/commit/5917f9c1f13f51e994438adc44f89afe8dc334ff))


## v0.0.49 (2024-04-18)


## v0.0.48 (2024-04-18)

### Bug Fixes

- Disabled strict host key checking while cloning.
  ([`8fc44fc`](https://github.com/core4x/collectu-core/commit/8fc44fcf35eef35bea27d33f1befef2fb5df25fd))


## v0.0.47 (2024-04-18)

### Bug Fixes

- Cloning using ssh and not https since this destroyed latter update behaviour for submodules.
  ([`a1c57c3`](https://github.com/core4x/collectu-core/commit/a1c57c3f7698ff7b10b24c1d0e620fc0693b4530))

- Fixed update behaviour.
  ([`6d4b896`](https://github.com/core4x/collectu-core/commit/6d4b89603d2b0bd5bb1b5774c03a5f5ba194d80e))


## v0.0.46 (2024-04-18)

### Bug Fixes

- Fixed update behaviour.
  ([`b6355b2`](https://github.com/core4x/collectu-core/commit/b6355b23abdf752075d9e339b037878c5a924c38))


## v0.0.45 (2024-04-18)


## v0.0.44 (2024-04-18)

### Bug Fixes

- Fixed update behaviour.
  ([`03b5cb1`](https://github.com/core4x/collectu-core/commit/03b5cb194c7e95566205b0d6f87aa0bee7396f5c))


## v0.0.43 (2024-04-18)

### Bug Fixes

- Fixed update behaviour.
  ([`27952bf`](https://github.com/core4x/collectu-core/commit/27952bf3fb3ecb9a628605100525616e08834f59))


## v0.0.42 (2024-04-18)

### Bug Fixes

- Fixed update behaviour.
  ([`1772aec`](https://github.com/core4x/collectu-core/commit/1772aec39ed4bad84e2934338bf1149720242852))


## v0.0.41 (2024-04-18)

### Bug Fixes

- Fixed update behaviour.
  ([`0568674`](https://github.com/core4x/collectu-core/commit/05686741d3151addb7762886b4c3165668a57b60))


## v0.0.40 (2024-04-18)

### Bug Fixes

- Fixed update behaviour.
  ([`2463bf4`](https://github.com/core4x/collectu-core/commit/2463bf473e117f7dd1856c20b721ae724ef30b0a))


## v0.0.39 (2024-04-18)

### Bug Fixes

- Fixed update behaviour.
  ([`22f26fa`](https://github.com/core4x/collectu-core/commit/22f26fa64bffc1736a648f499383058f5bc03b00))


## v0.0.38 (2024-04-17)

### Bug Fixes

- Fixed update behaviour.
  ([`600bc32`](https://github.com/core4x/collectu-core/commit/600bc3217080d2911836ff6b278534afbee6fe20))


## v0.0.37 (2024-04-17)

### Bug Fixes

- Fixed update behaviour.
  ([`69eee35`](https://github.com/core4x/collectu-core/commit/69eee35fc34131fe931f9bfdf57e6d649d5f1a1b))


## v0.0.36 (2024-04-17)

### Bug Fixes

- Fixed update behaviour.
  ([`c33cda1`](https://github.com/core4x/collectu-core/commit/c33cda10c092151b0d4c716d309ae5ecdd018484))

- Fixed update behaviour.
  ([`f43a203`](https://github.com/core4x/collectu-core/commit/f43a2039ff794be44ea46247227194a6b025dce9))


## v0.0.35 (2024-04-17)


## v0.0.34 (2024-04-17)

### Bug Fixes

- Fixed update behaviour.
  ([`9e417c9`](https://github.com/core4x/collectu-core/commit/9e417c9353a8cc4c8571d1cad0d2e628245b20e1))


## v0.0.33 (2024-04-17)

### Bug Fixes

- Fixed update behaviour.
  ([`1794eb5`](https://github.com/core4x/collectu-core/commit/1794eb5219177a578db514927161d30e60a0a247))


## v0.0.32 (2024-04-17)

### Bug Fixes

- Fixed update behaviour.
  ([`f6b5eb3`](https://github.com/core4x/collectu-core/commit/f6b5eb37891e9fb7b6e226bea844805c84ed8229))

- Fixed update behaviour.
  ([`6cc45e3`](https://github.com/core4x/collectu-core/commit/6cc45e341bafac5212c6399e0a5cd23a88b6271d))


## v0.0.31 (2024-04-17)


## v0.0.30 (2024-04-17)

### Bug Fixes

- Fixed path to git_access_token_file.
  ([`7f12bbc`](https://github.com/core4x/collectu-core/commit/7f12bbcc473545b06e0330cd078d5b6274c0d51a))

- Replacing .tag and .variable now by rstrip and no longer by replace, since this caused a bug for
  some filter module names.
  ([`b28b326`](https://github.com/core4x/collectu-core/commit/b28b326ca83dd57245dbbedd193cdf023d26267f))


## v0.0.29 (2024-04-17)

### Bug Fixes

- Changed workdir.
  ([`7d7b88a`](https://github.com/core4x/collectu-core/commit/7d7b88aeb87b33fff1f2cee72935d94ea138ff28))

### Documentation

- Changed some comments.
  ([`300e23a`](https://github.com/core4x/collectu-core/commit/300e23aaf58cc489a22da376bdbd558194a0fd8a))


## v0.0.28 (2024-04-17)

### Bug Fixes

- Updated subprocess call (from check_call to run) for installing third party packages.
  ([`97cb562`](https://github.com/core4x/collectu-core/commit/97cb562f457d126f6cfb1a4a9be544aacbe08ed8))


## v0.0.27 (2024-04-16)


## v0.0.26 (2024-04-16)

### Bug Fixes

- Minor improvements.
  ([`2a5645f`](https://github.com/core4x/collectu-core/commit/2a5645f48183e8d24234d733eaddf3b7b7bbaee1))

- Minor improvements.
  ([`41f022d`](https://github.com/core4x/collectu-core/commit/41f022dfafcfd19037347975735b579eb4978c80))

- Minor improvements.
  ([`6e65fb5`](https://github.com/core4x/collectu-core/commit/6e65fb5082893d3af8ffac1d38ff6fbc2a430e6c))


## v0.0.25 (2024-04-16)

### Bug Fixes

- Fixed module versioning.
  ([`4828326`](https://github.com/core4x/collectu-core/commit/4828326b9ed404e5ebe5a67c73670fa22452eeb8))

- Fixed module versioning.
  ([`dd2c78a`](https://github.com/core4x/collectu-core/commit/dd2c78aaa5b66a0e89fdb2dbe509fb6453d90c59))


## v0.0.24 (2024-04-16)

### Documentation

- Added two comments.
  ([`47d56e0`](https://github.com/core4x/collectu-core/commit/47d56e0c2f469bef31d6fa9b7e1f1635a1998815))


## v0.0.23 (2024-04-16)

### Bug Fixes

- Fixed clone command.
  ([`dd48afd`](https://github.com/core4x/collectu-core/commit/dd48afd1b2e25f4caa1e474211a9af853b8a5edd))


## v0.0.22 (2024-04-16)

### Bug Fixes

- Fixed clone command.
  ([`aa479ad`](https://github.com/core4x/collectu-core/commit/aa479ade3af6fba4f574dba455bf9b22acf6cdba))


## v0.0.21 (2024-04-16)

### Bug Fixes

- Fixed clone command.
  ([`6f9bc1c`](https://github.com/core4x/collectu-core/commit/6f9bc1cc6f473bc1c070a2bbdd7258141ee3c076))

- Fixed clone command.
  ([`3a545e8`](https://github.com/core4x/collectu-core/commit/3a545e8e5f4022636de85fc0ca3c6ce45e65a409))


## v0.0.20 (2024-04-09)

### Bug Fixes

- Ignore codec errors.
  ([`04a86ca`](https://github.com/core4x/collectu-core/commit/04a86ca4f59320f234334f3c602eb80fa3a1c668))

### Documentation

- Added typing sessions.
  ([`c1c269e`](https://github.com/core4x/collectu-core/commit/c1c269ec46a6e1aa0162161b69db1b38cea6512b))


## v0.0.19 (2024-04-08)


## v0.0.18 (2024-04-08)

### Bug Fixes

- Fixed module sending endpoints.
  ([`22c84de`](https://github.com/core4x/collectu-core/commit/22c84dee7655fa08eafc0a43120ffa99e72ffbfe))


## v0.0.17 (2024-04-08)

### Bug Fixes

- Added new env vars.
  ([`8a34aaa`](https://github.com/core4x/collectu-core/commit/8a34aaadd9e68f198f6d7ae3c0db4edac3c14256))


## v0.0.16 (2024-04-08)

### Bug Fixes

- Minor fixes.
  ([`b080e93`](https://github.com/core4x/collectu-core/commit/b080e938b5f43db3be1998f55dd35df2138b4dba))


## v0.0.15 (2024-04-07)

### Bug Fixes

- Minor fixes.
  ([`d83511e`](https://github.com/core4x/collectu-core/commit/d83511ede924017c1f7dbf6bf35c2120a55cbb74))


## v0.0.14 (2024-04-07)

### Bug Fixes

- Minor fixes.
  ([`ed4adbd`](https://github.com/core4x/collectu-core/commit/ed4adbda5f81adac187703dd9a1817d58dc7390e))

- Minor fixes.
  ([`241db0a`](https://github.com/core4x/collectu-core/commit/241db0a7240aa700a359c6bccf37c88873ba0583))


## v0.0.13 (2024-04-07)

### Bug Fixes

- Removed all tests requiring modules.
  ([`c04d254`](https://github.com/core4x/collectu-core/commit/c04d25465ecc6f027552cde0368faaf60835407f))


## v0.0.12 (2024-03-21)

### Bug Fixes

- Minor fixes.
  ([`a013ee6`](https://github.com/core4x/collectu-core/commit/a013ee629e50b5bf622d4e8cebae933b69d36c91))


## v0.0.11 (2024-02-11)

### Bug Fixes

- Check for updates for submodules fixed.
  ([`fa099cf`](https://github.com/core4x/collectu-core/commit/fa099cf6e553a3d4db5a050d5ff028598a6d60c6))

### Documentation

- Specified interfaces as frontend and api.
  ([`5fd5611`](https://github.com/core4x/collectu-core/commit/5fd561196ec95c388f0d5fd7b5d3dd35b7e74b2b))


## v0.0.10 (2024-02-11)


## v0.0.9 (2024-02-11)

### Bug Fixes

- Removed default mothership.
  ([`1b49668`](https://github.com/core4x/collectu-core/commit/1b49668ea843e91a3b8cecfae407e90c365a1c32))


## v0.0.8 (2024-02-11)

### Bug Fixes

- Commented git_access_token.
  ([`da57dd9`](https://github.com/core4x/collectu-core/commit/da57dd9f980f46b62e7cc9c0a2e7581ebf8541b0))

- Fetch before checking for new commits.
  ([`e2a0e65`](https://github.com/core4x/collectu-core/commit/e2a0e653703d2f6a761af66b1fc42750da8e9a44))


## v0.0.7 (2024-02-11)

### Bug Fixes

- Fixed git_access_token mount.
  ([`a1617c2`](https://github.com/core4x/collectu-core/commit/a1617c21b56ede6eea06c107e427bab5338984c0))


## v0.0.6 (2024-02-11)


## v0.0.5 (2024-02-11)

### Bug Fixes

- Adjusted build context.
  ([`d3ad1f0`](https://github.com/core4x/collectu-core/commit/d3ad1f0cbdc5c90a40ce86f871e2de08ec2729c3))


## v0.0.4 (2024-02-11)

### Bug Fixes

- Added default configuration.yml.
  ([`eb18e24`](https://github.com/core4x/collectu-core/commit/eb18e24296236f84b1ffdb2d96487518471fc408))


## v0.0.3 (2024-02-11)

### Bug Fixes

- Removed gitignore from Dockerfile.
  ([`879427c`](https://github.com/core4x/collectu-core/commit/879427cd3ef4d196e20b678a4c8f2a6313c3305e))


## v0.0.2 (2024-02-11)

### Bug Fixes

- Changed location of Dockerfile.
  ([`974050f`](https://github.com/core4x/collectu-core/commit/974050ff20b5580cac664b698306579c80733861))

- Copy some more files.
  ([`1a26c84`](https://github.com/core4x/collectu-core/commit/1a26c84529db9746b4e0662a076b7ee1afad6d41))


## v0.0.1 (2024-02-10)

- Initial Release
