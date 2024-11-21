# CHANGELOG


## v0.15.0 (2024-11-21)

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

- Fixed sizes of left panel.
  ([`6bcf3ee`](https://github.com/core4x/collectu-core/commit/6bcf3ee937d8b62b5170690f75140b352a8f9b98))

- Added util function to get a list of all used third party requirements by modules.
  ([`807163d`](https://github.com/core4x/collectu-core/commit/807163d454de83e2ae91a320835850804919b090))


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

- Improved base methods.
  ([`364e0a2`](https://github.com/core4x/collectu-core/commit/364e0a25939935366af13e141a68e13a1fb07ce5))

- Added check if measurement exists before processing data object.
  ([`4d08b39`](https://github.com/core4x/collectu-core/commit/4d08b39acbf658f4052cd58bb9f08fba4a0f8a12))

- Added thread-safe functionality.
  ([`421e7a1`](https://github.com/core4x/collectu-core/commit/421e7a1df363226f3e2cbf08671229c74732624d))


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

- Removed unnecessary files.
  ([`c7aae26`](https://github.com/core4x/collectu-core/commit/c7aae26cce96a76653eda5c795910b29c838f247))

- If all modules shall be sent, leave the list empty and not None.
  ([`03a611c`](https://github.com/core4x/collectu-core/commit/03a611cab9c904bcef60bac7241506cc6e5eef4e))

- Load modules after initialization.
  ([`b87ee15`](https://github.com/core4x/collectu-core/commit/b87ee15df82d68fa475c14713e13640f8c80df3f))

- Rename package typing-extensions to typing_extensions otherwise, it is installed every start since
  the package name in requirements.txt differs from the "online" one.
  ([`f534fe9`](https://github.com/core4x/collectu-core/commit/f534fe9d6b1e2f1b66be6324590d63b434410d2b))

- Updated deprecated use of pkg_resources.working_set.
  ([`2a6352e`](https://github.com/core4x/collectu-core/commit/2a6352e9d00b5fcb666d54a6c6591e6fb227b94a))

### Features

- Added functionality to include a custom module folder.
  ([`a9e1139`](https://github.com/core4x/collectu-core/commit/a9e11393856d8906be22863a0c78d6fd95a38409))

- Added custom_module_folder variable.
  ([`46a4924`](https://github.com/core4x/collectu-core/commit/46a492415812fd63fa3dc9cac3b31e92fba370ac))


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

- Removed unnecessary imports.
  ([`e6a27c5`](https://github.com/core4x/collectu-core/commit/e6a27c55b4e36b330c392e8ccdc679c0c6ffd435))

- Added timeout for requests.
  ([`aa400d5`](https://github.com/core4x/collectu-core/commit/aa400d5fdc575338fbde7738fec3dc1b2860cf97))


## v0.2.0 (2024-08-26)

### Features

- Added log messages about which configuration file was loaded.
  ([`fc2dc83`](https://github.com/core4x/collectu-core/commit/fc2dc833c5bb62cbf778aa6c313f3936dec15956))

- Added check that all versions of a module type are the same.
  ([`0453a28`](https://github.com/core4x/collectu-core/commit/0453a28f55b8148497643d95d59b5163d2835db6))


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

### Bug Fixes

- Minor improvements.
  ([`fb34ca5`](https://github.com/core4x/collectu-core/commit/fb34ca52a5e797657a4ce9c0c5e006d43f035d7f))

- Minor improvements.
  ([`70f213e`](https://github.com/core4x/collectu-core/commit/70f213e0fe64d4e9b6bfa5977b6da3cd0794a850))

- Minor improvements.
  ([`9eb92da`](https://github.com/core4x/collectu-core/commit/9eb92dad59b4e578984a8559edc5e7af4afddac2))

- Fixed logging.
  ([`198c36f`](https://github.com/core4x/collectu-core/commit/198c36fd7e7aa303baaba84058d57b9be8aae747))

- Made ssh key not accessible by other users.
  ([`5aa516b`](https://github.com/core4x/collectu-core/commit/5aa516bae7e19e80e74389f105b2be8bc69e470c))

- Added ssh_key loading.
  ([`d32e1e7`](https://github.com/core4x/collectu-core/commit/d32e1e7bd4bc3073f45ad1936fd17ca95bedb4fd))

- Try to initialize submodules if they do not exist.
  ([`c9038a4`](https://github.com/core4x/collectu-core/commit/c9038a49842ff8478dcca647dd250ca076f987fe))

- Added access token for checking for updates for submodules.
  ([`ff0da73`](https://github.com/core4x/collectu-core/commit/ff0da737b7561bb50b1bda94653d71fe1182fb2b))

- Added --init, if the submodules does not exist yet.
  ([`93f127c`](https://github.com/core4x/collectu-core/commit/93f127c682e310927bc81e2655e1161b6a1eec6b))

- Removed id.
  ([`75db6dd`](https://github.com/core4x/collectu-core/commit/75db6dd78052ef1c9e91051d05a7fc8a9764539b))

- Removed unnecessary things.
  ([`dbd7f23`](https://github.com/core4x/collectu-core/commit/dbd7f23ee264a00f5dd627b7673ea2cf19c08922))

### Documentation

- Removed wrong things.
  ([`a979429`](https://github.com/core4x/collectu-core/commit/a97942985fc15d5ea7bc760a56d671fa5f0aef56))
