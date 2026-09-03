# Nguồn localization Divine Journey 2 v2.23.4

Các file trong thư mục này là nguồn English canonical dùng để tạo resource pack Việt hoá. Không sửa trực tiếp các file nguồn.

| File | Nguồn | Số key | SHA-256 |
|---|---|---:|---|
| `betterquesting-quests.lang` | Client archive DJ2 v2.23.4, `overrides/resources/betterquesting/lang/en_us.lang` | 3.532 | `13b2b2012e2ef4539d9f2035d200e5d6decfe71af78e2b2a449f93a3c72b7cc5` |
| `betterquesting-gui.lang` | `BetterQuesting-3.5.329.jar`, `assets/betterquesting/lang/en_US.lang` | 186 | `7e8eedc971e157c8075a184f0dbece0374514935e88f6d19b15a2ee92ed1d071` |
| `bqtweaker.lang` | `BQTweaker-1.3.5.jar`, `assets/bqtweaker/lang/en_us.lang` | 5 | `f20d538b2f479f9f6d62687cf24b6b6bcdfb425393c3e59e720dc344ee9879c9` |
| `crafttweaker.lang` | DJ2 v2.23.4 server/client override, `groovy/assets/crafttweaker/lang/en_us.lang` | 657 | `522137ce116f60b51f5bf0a258c31ba2ba894e71cb29f4e572f66414d2ff6208` |
| `divine_journey_2.lang` | DJ2 v2.23.4 server/client override, `groovy/assets/divine_journey_2/lang/en_us.lang` | 30 | `c8e4cfea19d061e276c993eb91c0c7a3ede95bdbbd255adfa9fdbb383042e500` |
| `enchantment_descriptions.lang` | `EnchantmentDescriptions-1.12.2-1.1.20.jar`, English locale | 19 | `c2bfcf811e16fe3ad410ddc97cec140118b95fb189e2d1400a783f566b9e2e16` |

Quest source được chia bằng `tools/split_by_chapter.py` thành 30 chapter batch và một batch 6 key mồ côi. Bản dịch canonical ở `work/translated/*.json`; ZIP phát hành chỉ là sản phẩm build và có thể tái tạo bằng `tools/build_pack.py`.
