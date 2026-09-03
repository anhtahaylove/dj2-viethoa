"""Validate the translation JSONs that build_pack.py actually reads.

validate_runtime_locales.py covers work/runtime_locale_batches only. The pack is
built from work/translated/{runtime_locales,tooltips} against the .lang sources,
and nothing checked that pair — three real defects shipped through the gap:

  * tconstruct stat.fletching.modifier.desc lost a literal \\n (two clauses
    collapsed into one line, and the sentence was mistranslated with it),
  * openblocks sprinkler.description lost a literal \\n,
  * storagedrawers drawerKey.description carried a REAL newline where the
    source had the two-character sequence \\n.

Minecraft 1.12.2 splits tooltips on the literal two-character sequence \\n. A
real U+000A in a .lang value terminates the entry instead, so the rest of the
line silently disappears in game while every byte-level check still passes.
"""
from pathlib import Path
import json, re, sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
PAIRS = (
    ("work/runtime_locale_sources", "work/translated/runtime_locales"),
    ("source/tooltips", "work/translated/tooltips"),
)
FMT = re.compile(r"%(?:n|%|(?:\d+\$)?[-#+0,(<]*\d*(?:\.\d+)?[bBhHsScCdoxXeEfgGaAtT])")
COLOR = re.compile(r"§.")
AMP = re.compile(r"&[0-9a-fk-orA-FK-OR]")
URL = re.compile(r"https?://[^\s§]+")
VN_DIACRITIC = re.compile(
    r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    re.I,
)
# A `.name` key under one of these prefixes is the display name JEI and the wiki
# index on. Translating it breaks item search, so it must stay English.
REG_NAME_PREFIXES = (
    "item.", "tile.", "block.", "fluid.", "entity.", "material.",
    "potion.", "enchantment.", "itemGroup.", "biome.", "death.",
)
_TERMS_PATH = ROOT / "work/protected_terms.json"
PROTECTED_TERMS = sorted(
    (
        t
        for t in json.loads(_TERMS_PATH.read_text(encoding="utf-8"))
        if len(t) >= 5 and re.fullmatch(r"[A-Za-z][A-Za-z'\- ]+", t)
    ),
    key=len,
    reverse=True,
)


# A short label with no format token is a fixed piece of UI text: the same
# English string must read the same way in every mod, or the player sees two
# names for one feature. Longer strings are prose and may legitimately vary.
CONSISTENCY_MAX_LEN = 45
# Cleared by reading the key and its neighbours -- each is a mode, a live
# status, or one half of an on/off pair, not the plain noun label.
CONSISTENCY_EXEMPT = {
    # --- Config-screen batch. Each is a translated GUI label colliding with a
    # deliberately-English name elsewhere; one shared wording breaks one side.
    "enderio.config.tank",                    # EnderIO config row for the tank
                                              # machine -> "Bể chứa", matching the
                                              # shipped enderio.gui.tank.tank; IE's
                                              # `Tank` is a multiblock proper name
    "quark.config.module.world",              # Quark module category -> "Thế giới";
    "thaumicaugmentation.text.config.world",  # same category sense
    "cfg.endermodpacktweaks.minecraft.world",  # EnderModpackTweaks config category,
                                              # same "game world" sense as the rows above
    "ftbutilities.world",                      # FTB Utilities server-settings category,
                                              # same sense again
    "cfg.universaltweaks.config.world",        # third config category with that sense;
                                              # an exemption only silences a variant when
                                              # EVERY key holding it is listed. integrateddynamics
                                              # and thaumcraftfix keep `World` as a
                                              # data-type / registry word
    "extrautils2.text.globe.biome.ocean",      # Globe biome readout naming the vanilla
                                               # ocean biome -> "Đại dương". The colliding
                                               # key is astralsorcery's Octans constellation
                                               # lore, where "Ocean" is the constellation's
                                               # protected proper name and stays English
    "reccomplex.mazerule.connect.end",         # maze-rule path endpoint, the pair of
                                               # reccomplex.mazerule.connect.start ->
                                               # "Bắt đầu". The colliding keys name
                                               # THE END dimension, a proper noun that
                                               # stays English
    "jm.waypoint.chat",                        # JourneyMap waypoint ORIGIN, i.e. the
                                               # waypoint was created from a chat
                                               # message. Shipped as English `Chat`;
                                               # the config-screen sense follows
                                               # ftbutilities.chat -> "Trò chuyện"
    # --- Wave-18 batch. Homographs cleared by reading each key and its family.
    "reccomplex.gui.random.weight.custom.short",  # one-letter ABBREVIATION of "Custom"
                                                 # in a weight picker -> "T" for "Tùy
                                                 # chỉnh"; botania.rank1's `C` is a
                                                 # rank BADGE letter and stays English
    "reccomplex.gui.random.weight.default.short",  # same picker, abbreviation of
                                                 # "Default" -> "MĐ"; botania.rank0's
                                                 # `D` is the lowest rank badge
    "pe.pe_mercurial_eye.mode1",               # Mercurial Eye BUILD MODE "Creation"
                                               # -> "Kiến tạo"; the Astral Sorcery
                                               # collision is constellation Aevitas'
                                               # proper trait name, kept English
    "pe.pe_mercurial_eye.mode6",               # Mercurial Eye build mode "Pillar"
                                               # -> "Trụ"; multipart's `Pillar` is a
                                               # microblock EDGE SHAPE name
    "knowledge.astralsorcery.fragment.exploration.crystalgrowth.bookmark",
                                               # journal bookmark for crystal
                                               # "Splitting" -> "Tách"; Tinkers'
                                               # `Splitting` is a tool modifier name
    # Contextual UI/manual variants reviewed in the progression-priority batch.
    "info.cofh.holdShiftForDetails",                    # sentence-style UI capitalization
    "text.industrialforegoing.tooltip.hold_shift",      # same prompt, lower-case prose
    "roots.modifiers.modifiers.speed.desc",             # explicit player pronoun in modifier prose
    "desc.ma.charm_speed",                              # compact charm tooltip
    "enderio.gui.tank.tank",                            # generic container UI label
    # Wave-6/T1 batch. Same English string, genuinely different subject.
    "mod.chiselsandbits.help.leftshift",   # the physical Shift key in a controls
    "mod.chiselsandbits.help.rightshift",  # hint; integrateddynamics' Left/Right
                                           # Shift are the bitwise shift operators
    "enderio.farm.note.noPower",           # EnderIO farm status -> "Không có năng
                                           # lượng" (RF); Galacticraft's short GUI
                                           # badge keeps the compact "Không Có Điện"
    "ie.manual.entry.tank.name",                        # English machine/manual proper name
    "integratednbt:nbt_extractor.welcome",              # UI heading
    "dj2.introduction.book.name",                       # proper title retained for Wiki lookup
    # --- Second T1 batch (tooltips/messages). Each of these is the same
    # English word carrying a different sense in the new key than in the
    # already-shipped one, so one shared wording would be wrong somewhere.
    "tooltip.energyhatch.ic2.any",     # "any voltage tier" -> "Bất Kỳ";
                                       # integrateddynamics `Any` is a data
                                       # TYPE name in its logic system
    "info.cofh.augmentation",          # an installable upgrade -> "Nâng Cấp";
                                       # thaumicaugmentation's is a research
                                       # entry title, kept English
    "tooltip.ma.bow",                  # tool-TYPE label listing which tool a
                                       # material makes, kept as "Bow" like the
                                       # other type labels; tconstruct's
                                       # stat.bow.name names the weapon
    "tooltip.ma.flight",               # armour ability "Bay"; thaumcraft
    "tooltip.armor_info.fly",          # volatus is the ASPECT of motion
    "info.cofh.fluid",                 # prose label for a tank's contents;
                                       # AE2 FluidTunnel/commoncapabilities
                                       # keep "Fluid" as a system term
    "tooltip.wawla.head",              # the armour SLOT -> "Đầu";
                                       # integrateddynamics list.head is the
                                       # first ELEMENT of a list
    "info.cofh.item",                  # prose "Vật Phẩm" in a tooltip; AE2's
    "tooltip.wawla.item",              # ItemTunnel/LevelType_Item are system
                                       # channel names kept English
    "info.actuallyadditions.booklet.manualName.2",  # the book item's own title
                                       # -> "Sách Hướng Dẫn"; integrateddynamics
                                       # 'manual' is generic documentation
    "agricraft_tooltip.material",      # crafting material -> "Vật Liệu";
    "tooltip.ma.material",             # actuallyadditions' reconstructor line
                                       # means MATTER ("Vật Chất")
    "info.solarflux.maximum",          # max output value -> "Tối Đa";
                                       # integrateddynamics maximum.name is the
                                       # arithmetic operator
    "tooltip.gadget.mirror",           # the mirroring TRANSFORM -> "Lật";
                                       # enderutilities' is a mirror ITEM
    "tooltip.spartanshields.dev.unimplemented",  # dev placeholder sentence

    # used elsewhere as a mode or an energy level.
    "stat.head.attack.name",           # tool damage stat -> "Sát thương"
                                       # (plustic mode.laser_gun.attack is a
                                       # firing MODE -> "Tấn công")
    "stat.spaghetti.saturation.name",  # food saturation -> "Độ no"
                                       # (draconicevolution rsMode_sat is a
                                       # reactor energy level -> "Bão hòa")
    # Thaumcraft aspects are the names of magical ESSENCES, not the ordinary
    # nouns the same English word spells elsewhere in the pack. `Craft` as an
    # aspect is the principle of making (-> "Chế tác"); AE2's `Craft` is the
    # button that queues an autocrafting job (-> "Chế tạo"). `Life` as an
    # aspect is the life force itself (-> "Sự sống"); Draconic's
    # particleGenerator `Life` is a particle's lifetime (-> "Tuổi thọ").
    "tc.aspect.fabrico",               # aspect of making -> "Chế tác"
    "tc.aspect.victus",                # aspect of life force -> "Sự sống"
    # `Light` collides across two DIFFERENT conventions, not two translations.
    # The aspect is a described essence -> "Ánh sáng". AE2's LightTunnel is a
    # P2P resource-type name sitting beside EU/FE/ME/Redstone/Fluid, and
    # IntegratedDynamics' part label sits beside "Mono-Directional Connector":
    # both are proper nouns the pack deliberately keeps in English.
    "tc.aspect.lux",                   # aspect of light -> "Ánh sáng"
    # Fluid Transposer fill/drain mode, not an "empty" label.
    "gui.thermalexpansion.jei.transposer.modeEmpty",
    # Flamethrower firing mode, sits beside Combat/Inferno -- not a stat.
    "tooltip.flamethrower.heat",
    # Paired with Active -> "Đang bật"; normalising breaks the pair.
    "info.de.obliterationModefalse.txt",
    # Live status ("currently crafting"), not a static tab label.
    "waila.appliedenergistics2.Crafting",
    "gui.fusionCrafting.crafting.info",
    # Narrow button frames: the short form is deliberate.
    "enderio.gui.conduit_disabled_mode",
    "enderio.gui.disabled",
    # Tinkers uses "Rỗng" for vessels throughout -- internally consistent.
    "tooltip.tool.empty",
    "gui.waila.tank.empty",
    # Paired with Inactive -> "Đang tắt"; normalising breaks the pair.
    "info.de.obliterationModetrue.txt",
    # "Charge" is three different things in Draconic Evolution.
    "info.bc.charge.txt",           # battery charge -> "Sạc"
    "eNet.de.hudCharge.info",       # electric charge -> "Điện tích"
    "gui.reactor.charge.btn",       # reactor charging -> "Nạp năng lượng"
    # Fluid Transposer fill/drain mode, not the verb "fill".
    "gui.thermalexpansion.jei.transposer.modeFill",
    # Integrated Dynamics Part/operator proper names stay English.
    "info_book.integrateddynamics.manual.parts.writer.effect",
    "operator.operators.integrateddynamics.itemstack.inventory.name",
    # Keybind labels stay English so they match the controls screen.
    "enderio.keybind.nightvision",
    # Wave 8. `Moon` is the excavator DIMENSION proper name (kept English so it
    # matches the dimension list and JEI); Thaumic Augmentation's scan_moon is a
    # sentence describing the scan action, so it reads as prose.
    "thaumicaugmentation.gui.scan_moon",
    # Wave 8. AbyssalCraft/RecComplex list world DIMENSIONS ("Chiều không gian");
    # EnderUtilities' ruler tooltip and JourneyMap's waypoint field mean physical
    # SIZE ("Kích thước"). Same English word, two unrelated quantities.
    "ac_dimensions",
    "reccomplex.gui.dimensions",
    # Narrow config label; the tooltip beside it carries the full wording.
    "config.integrateddynamics.machine",
    # "Type" here is the VERB: the string joins to_allow_entry as
    # "Type /ssinvite <player> to allow another player to enter" -> "Nhập".
    "gui.spacestation.type_command",
    # Keybind labels stay English so they match the controls screen.
    "enderio.keybind.stepassist",
    # Integrated Dynamics keeps Slot/Part as Part proper nouns.
    "aspect.aspects.integrateddynamics.read.integer.inventory.slots.name",
    # Scale = particle size vs slimeling growth ratio: different quantities.
    "gui.particleGenerator.scale",
    "gui.slimeling.scale",
    # IntegratedDynamics operator names are FUNCTION names in a visual
    # programming language, written Title Case like the button labels they
    # sit on in the Logic Programmer. The colliding strings are ordinary
    # prose elsewhere: Galacticraft's space_race `Join` is joining a race
    # (-> "Tham gia"), Mekanism's upgrades `Amount` is a piece count
    # (-> "Số lượng"), Galacticraft's `Apply` is a dialog button in a
    # sentence-cased GUI (-> "Áp dụng").
    "operator.operators.integrateddynamics.string.join.name",
    "operator.operators.integrateddynamics.operator.apply.name",
    "operator.operators.integrateddynamics.fluidstack.amount.name",
    # Thaumonomicon tab label; Title Case matches the short-label convention.
    # Galacticraft's launch_controller `Advanced` is mid-sentence prose.
    "tc.adv",
    # The ELEMENT Air (one of the four classical elements, beside Fire/Water/
    # Earth) -> "Khí". `tc.aspect.aer` is the aspect of air as a described
    # essence -> "Không khí"; same English word, two different things, exactly
    # like the fabrico/victus/lux aspect entries above.
    "thaumcraft.AIR.name",
    # `Arcane Infusion` is the Infusion Altar RECIPE TYPE shown in JEI beside
    # Crucible/Arcane Workbench, which are registry names kept English; the
    # research CATEGORY of the same name is a Thaumonomicon tab
    # (-> "Truyền Phép Huyền Bí").
    "recipe.type.infusion",
    # Tinkers' tool modifier NAMES stay English like item names (all 23
    # moartinkers `modifier.*.name` are kept English, their `.desc` translated);
    # the colliding strings
    # are ordinary words elsewhere: IntegratedDynamics' `Constant` is a Logic
    # Programmer function, Thaumcraft's `Darkness` is an aspect essence,
    # Galacticraft's `Launch` is the rocket button.
    "modifier.constant.name",
    "modifier.darkness.name",
    "modifier.launch.name",
    # --- T2 wave 1 (GUI/JEI labels) ---
    # BiblioCraft's sign editor lists Minecraft's own formatting and colour
    # names. `Bold` there is a font style, while Thaumcraft's is a champion
    # mob's temperament; `Gold` there is the §6 text colour, while Immersive
    # Engineering's is the ore. One shared wording would misread one screen.
    "gui.sign.bold",
    "gui.sign.gold",
    # Tinkers' mining-LEVEL names are the material tiers (Stone/Iron/Diamond/
    # Cobalt) and stay English as a tier scale; Thaumcraft's `golem.material.iron`
    # is the golem's build material read as an ordinary noun (-> "Sắt").
    "ui.mininglevel.iron",
    # `Head` as a Tinkers' TOOL PART (beside Handle/Extra) -> "Đầu";
    # IntegratedDynamics' `list.head` is the first ELEMENT of a list
    # (-> "Phần Tử Đầu"), a different thing on a different screen. Exempting
    # either side clears the pair, so only the Tinkers' part is listed.
    "stat.head.name",
    # `Count` as an EnderIO redstone-filter threshold is a quantity
    # (-> "Số lượng"); IntegratedDynamics' `list.count` is the counting
    # FUNCTION in the Logic Programmer (-> "Đếm").
    "operator.operators.integrateddynamics.list.count.name",
    # `Volume` on the Audio Writer is loudness (-> "Âm Lượng"); Mekanism's
    # `gui.volume` is a Dynamic Tank's capacity in buckets (-> "Thể tích").
    "aspect.aspecttypes.integrateddynamics.double.volume.name",
    # `Full` as a Focus targeting PLAN (full block vs surface) -> "Toàn Bộ";
    # RebornCore's `Full` is a tank fill-state readout (-> "Đầy").
    "focus.plan.full",
    # `Heal` as the Thaumcraft focus EFFECT that restores health -> "Hồi Máu";
    # Galacticraft's is a generic recovery message (-> "Hồi phục").
    "thaumcraft.HEAL.name",
    # `Power` collides three ways: a Focus's spell strength (-> "Sức Mạnh"),
    # stored energy in Mekanism/Draconic (-> "Năng lượng"), and the
    # exponentiation operator in IntegratedDerivative (-> "Luỹ Thừa").
    "focus.common.power",
    "operator.operators.integratedderivative.arithmetic.pow.name",
    # `Dimensions` as ThaumcraftFix's config list of WORLDS (-> "Chiều không gian")
    # vs Mekanism's Digital Miner radius/height BOX SIZE (-> "Kích thước").
    "thaumcraftfix.text.config.dimList",
    # --- T2 wave 4 (GUI/JEI). Same English word, different sense.
    # `Dimensions` again: Rec Complex's structure GUI filters which WORLDS a
    # structure may generate in (-> "Chiều không gian", matching ThaumcraftFix),
    # while EnderUtilities' ruler reports the measured BOX SIZE (-> "Kích thước").
    "reccomplex.gui.dimensions",
    # `Breaker` as a Thaumcraft golem TRAIT, an ability listed beside
    # Climber/Hauler (-> "Phá Dỡ"), vs ActuallyAdditions' container title for
    # the Breaker MACHINE, kept English like its Placer/Repairer siblings.
    "golem.trait.breaker",
    # `Color` is one fragment of a three-piece Galacticraft button reading
    # "Change | Team | Color" -> "Đổi | màu | đội"; the fragment carries "đội",
    # not the colour noun that FTBLib's standalone `gui.color` needs.
    "gui.space_race.create.change_color.name.2",
    # `Block` as the KEY NAME on the keyboard/`Shift` prompt vs the noun. Rec
    # Complex's structure GUI labels a block-type field (-> "Khối"); the shipped
    # BuildingGadgets/EnderUtilities tooltips list `Block` as a gadget MODE name
    # kept English beside Grid/Column, so they must not converge.
    "reccomplex.gui.block",
    # `Shift` as Rec Complex's positional OFFSET field -- its own .tooltip reads
    # "The positional movement x, y, z." (-> "Dịch chuyển") -- vs the literal
    # SHIFT KEY players hold in the Draconic/SimplyJetpacks detail prompts,
    # which stays "Shift" because it names a physical key.
    "reccomplex.gui.blockpos.shift",
    # `Panel` as a Chisel area MODE (a 3x3 patch, its own .desc says "mảng") vs
    # Forge Multipart's cover-plate PART named `%s Panel`, kept English like Slab.
    "chisel.mode.panel.name",
    "container.chisel.hitech.preview.panel",
    # `Single` as a Chisel area mode (one block -> "Đơn", beside Row/Column) vs
    # Mekanism's Logistical Sorter sending items one at a time (-> "Một Item").
    "chisel.mode.single.name",
    "container.chisel.hitech.preview.single",
    # `Operator` as the IntegratedDynamics VALUE TYPE (a function, kept English
    # beside Fluid/NBT) vs EnderStorage's server OPERATOR, a person
    # (-> "Quản Trị Viên").
    "enderstorage.serverop",
    # `Ingredients` as the IntegratedDynamics VALUE TYPE (a recipe's item/fluid/
    # energy triple, kept English beside Fluid/Operator/NBT) vs Mekanism's
    # Formulaic Assemblicator tooltip listing crafting ingredients
    # (-> "Thành phần").
    "tooltip.ingredients",
    # --- T2 wave 2 (JEI / JECalculation / IndustrialForegoing / JourneyMap) ---
    # `Fluid` and `Item` as JECalculation's own GUI labels for the KIND of
    # ingredient a label holds (-> "Chất Lỏng" / "Vật Phẩm", matching cofh's
    # shipped info.cofh.item) vs AE2's FluidTunnel/ItemTunnel and
    # CommonCapabilities' recipe components, where the word is part of a device
    # or value-type proper name kept English for JEI/Wiki lookup.
    "jecalculation.gui.common.label.fluid",
    "jecalculation.gui.common.label.item",
    # `Tank` as the side-config name of a machine's own internal fluid buffer
    # (-> "Bể Chứa") vs Immersive Engineering's Sheetmetal Tank multiblock and
    # its manual entry, which name a craftable structure and stay English.
    "gui.industrialforegoing.side_config.tank",
    # `Water Tank` likewise names IndustrialForegoing's internal buffer
    # (-> "Bể Nước") vs Galacticraft's terraformer prose describing the portable
    # water container the player fills (-> "Bình Nước").
    "gui.industrialforegoing.side_config.water_tank",
    # --- T2 wave 3 (Patchouli / TeslaCoreLib / ValkyrieLib / OpenBlocks / AE2 / IE) ---
    # `Huge` as Patchouli's largest UI font step, sitting in the ordered scale
    # Default/Small/Medium/Medium-Large/Large/Huge (-> "Rất lớn"), vs
    # BiggerCraftingTables, where "Huge" is the tier name of the Huge Crafting
    # Table itself and stays English like every other registry-object name.
    "patchouli.gui.lexicon.button.resize.size5",
    # `Pull` is EnderIO's conduit I/O direction ("Hút" = draw items in), but
    # ActuallyAdditions' info.*.gui.pull labels the button that takes an item
    # OUT of the machine's slot -- "Lấy ra". Different actions, same English.
    "enderio.gui.machine.ioMode.pull",
    "enderio.gui.machine.ioMode.pull.colored",
    "info.actuallyadditions.gui.pull",
    # `Download` as a title-case menu action (cyclopscore/hammercore version
    # notices) vs ftblib's sentence-case button; each mod follows its own
    # surrounding casing and p2_ftblib already ships the sentence-case form.
    "general.cyclopscore.version.download",
    "chat.hammercore:newversion.clickdwn",
    "gui.download",
    # --- Wave 19. Surfaced only after the English sources were restored: the
    # sources had been overwritten with Vietnamese, so this guard was comparing
    # Vietnamese against Vietnamese and reported nothing. Each key was cleared
    # by reading its siblings and its family precedent.
    # Common/Rare/Uncommon: IndustrialForegoing's Infinity Drill rarity family
    # keeps all five tiers English as drill-tier names; CraftTweaker's excavator
    # rarity family translates all six as prose.
    "text.industrialforegoing.tooltip.infinitydrill.common",
    "text.industrialforegoing.tooltip.infinitydrill.rare",
    "text.industrialforegoing.tooltip.infinitydrill.uncommon",
    # Creative: Mekanism tier.* names machine tiers and keeps Basic/Elite/
    # Ultimate/Creative English; Botania's label is plain prose.
    "botaniamisc.creative",
    # Hover: SimplyJetpacks hud.state.* are HUD status names kept English 4/4;
    # Mekanism's jetpack tooltip is a sentence.
    "tooltip.jetpack.hover",
    # Shocking/Unnatural: Tinkers' modifier.*.name keeps proper modifier names
    # English 67/71; AE2 achievement titles translate 51/52.
    "achievement.ae2.ChargedQuartz",
    "achievement.ae2.Fluix",
    # Dim: IntegratedDynamics' diagnostics column abbreviates Dimension;
    # Astral Sorcery's is a brightness step (Dim/Faint/Bright).
    "astralsorcery.journal.constellation.dst.weak",
    # Usage: Astral Sorcery bookmarks a how-to-use section; Mekanism's
    # gui.usage is an energy consumption rate.
    "gui.usage",
    # Structure: EvilCraft names a built structure; Mekanism reports whether
    # a multiblock is correctly formed.
    "gui.structure",
    # Fill: Draconic Evolution's chest mode fills existing stacks; Mekanism
    # fills a tank.
    "gui.draconiumChest.fMode.fill.btn",
    # Point: Quark's emote wheel entry is the pointing gesture; Draconic
    # Evolution's is a numeric point value.
    "quark.emote.point",
    # Volume: Mekanism reports a tank's capacity; EnderUtilities' sound block
    # and IntegratedDynamics' aspect mean audio loudness.
    "gui.volume",
    # Chiseling: Chisel's JEI category title names the crafting action;
    # Botania's page text describes chiselling stone in prose.
    "chisel.jei.title",
    # full: Roots reports the moon phase; Galacticraft reports a container
    # being full.
    "roots.message.sense_time.moon.0",
    # Index/Normal/Entities: the Necronomicon keys are book furniture and are also
    # owned by books_abyssalcraft.json, which build_pack.py requires to agree, so
    # they keep the book's wording (Mục lục / Bình thường / Thực thể) while the GUI
    # keys elsewhere keep the UI wording (Chỉ mục / Thường / Các Entity).
    "necronomicon.index",
    "necronomicon.normal",
    "necronomicon.information.entities",
}


def parse_lang(text):
    """Keep the value byte-exact after the first '='.

    Do NOT strip the value: MC concatenates these strings, so a leading or
    trailing space is content, not formatting. Stripping here silently
    disarmed the edge-space check below -- it compared a stripped source
    against an unstripped translation, so every dropped space looked equal.
    """
    out = {}
    for line in text.splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        out.setdefault(key.strip(), value.rstrip("\r\n"))
    return out


# Botania lexicon pages whose Vietnamese word order moves a highlighted noun.
# Every one was checked by hand: same &-codes, same number of spans, and each
# span still wraps the same proper name as the English. Listed explicitly so a
# NEW reordering has to be reviewed rather than silently accepted.
AMP_REORDER_OK = {
    "botania.page.dandelifeon4",
    "botania.page.gaiaRitual0",
    "botania.page.grassSeeds0",
    "botania.page.heiseiDream0",
    "botania.page.loonium0",
    "botania.page.monocle0",
    "botania.page.pistonRelay0",
    "botania.page.pistonRelay2",
    "botania.page.spectranthemum0",
    "botania.page.tcIntegration3",
    "botania.page.terraPick4",
}


def balanced_spans(text):
    """True when every &-colour span in `text` is closed with &0.

    An unclosed span bleeds its colour over the rest of the tooltip, so a
    reordered string is only safe if the spans still pair up.
    """
    depth = 0
    for code in AMP.findall(text):
        if code[1] == "0":
            if depth == 0:
                return False
            depth -= 1
        else:
            depth += 1
    return depth == 0


def tokens(text):
    return {
        "format": FMT.findall(text),
        "color": COLOR.findall(text),
        "amp": AMP.findall(text),
        "url": URL.findall(text),
    }


def label_text(value):
    """Strip formatting codes so two renderings of one label compare equal."""
    return COLOR.sub("", AMP.sub("", value)).strip()


def consistency_errors(labels):
    """One English label rendered two ways reads as two different features.

    Bucket by the SOURCE string: grouping by the Vietnamese side finds nothing,
    because the divergent strings are exactly the ones that do not match.

    A key naming a MODE, a LIVE STATUS, or one half of an explicit on/off pair
    legitimately differs from the same word used as a static noun label, so
    CONSISTENCY_EXEMPT carries those with the reason they were cleared.
    """
    errors = []
    for english, seen in sorted(labels.items()):
        variants = {}
        for vietnamese, where in seen:
            variants.setdefault(vietnamese, []).append(where)
        if len(variants) < 2:
            continue
        live = {
            vi: where
            for vi, where in variants.items()
            if any(w.split(":", 1)[1] not in CONSISTENCY_EXEMPT for w in where)
        }
        if len(live) < 2:
            continue
        rendered = " | ".join(
            f"{vi!r} ({', '.join(sorted(w)[:2])})" for vi, w in sorted(live.items())
        )
        errors.append(f"inconsistent term {english!r}: {rendered}")
    return errors


def unbalanced(text, opener, closer):
    """True when brackets never close, or close before they open.

    Counting alone is wrong: emoticons (`=)`, `:(`, `:[`) leave the SOURCE
    unbalanced on purpose, so only flag a translation the source does not.
    """
    depth = 0
    for char in text:
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth < 0:
                return True
    return depth != 0


def key_covered_elsewhere(stem, key, own_path):
    """True when another translation family already provides this key.

    build_pack.py merges several families into a single namespace and raises on
    any key two families translate differently, so a key deliberately lives in
    exactly one family. Checking each family in isolation would report every
    such key as "missing" from the families that correctly do not carry it.
    """
    for candidate in _sibling_translation_files(stem):
        if candidate == own_path or not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if key in data:
            return True
    return False


def _sibling_translation_files(stem):
    """Every translation file that can feed the same namespace as `stem`."""
    trans = ROOT / "work" / "translated"
    return (
        trans / f"{stem}.json",
        trans / f"books_{stem}.json",
        trans / f"p2_{stem}.json",
        trans / "tooltips" / f"{stem}.json",
        trans / "advancements" / f"{stem}.json",
        trans / "runtime_locales" / f"{stem}.json",
        trans / "patchouli_metadata.json",
    )


# A protected term is a registry display name that must survive translation.
# The list is derived from every mod's en_us.lang, so a few entries are also
# ordinary English words ("Projectiles" is a DivineRPG entity name). Where the
# English string is plainly prose using the common noun -- not a reference to
# the named thing -- translating it is correct and the guard is what is wrong.
# Each entry below is cleared by reading the key and its siblings.
PROTECTED_TERM_EXEMPT = {
    # Thaumcraft focus-effect label. Siblings are "Health", "Yes", "No" and the
    # focus description, all translated. "Projectiles" here is the common noun
    # (the corpus renders it "Đạn" 20+ times), not DivineRPG's entity name.
    (
        "work/translated/runtime_locales/thaumicaugmentation.json",
        "focus.thaumicaugmentation.shield.reflect",
    ),
}


def validate():
    errors, report = [], {}
    labels = {}
    for source_dir, target_dir in PAIRS:
        for lang_path in sorted((ROOT / source_dir).glob("*.lang")):
            json_path = ROOT / target_dir / f"{lang_path.stem}.json"
            if not json_path.exists():
                continue
            source = parse_lang(lang_path.read_text(encoding="utf-8"))
            try:
                target = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"json error {json_path.name}: {exc}")
                continue
            rel = f"{target_dir}/{json_path.name}"
            if set(target) != set(source):
                # A key may legitimately live in a DIFFERENT translation family
                # than the one paired with this .lang. build_pack.py merges
                # several families (books/, tooltips/, advancements/, p2_*,
                # runtime_locales/) into one namespace and refuses to let two
                # families disagree about the same key, so each key is kept in
                # exactly one of them. Only flag a key that no family provides;
                # `extra` (a key no source declares) is always a real error.
                missing = sorted(
                    key
                    for key in set(source) - set(target)
                    if not key_covered_elsewhere(lang_path.stem, key, json_path)
                )[:3]
                extra = sorted(set(target) - set(source))[:3]
                if missing or extra:
                    errors.append(f"key mismatch {rel}: missing={missing} extra={extra}")
            checked = 0
            for key, english in source.items():
                if key not in target:
                    continue
                vietnamese = target[key]
                if not isinstance(vietnamese, str):
                    errors.append(f"non-string {rel}:{key}")
                    continue
                checked += 1
                ta, tb = tokens(english), tokens(vietnamese)
                if ta != tb:
                    # Vietnamese word order moves the highlighted noun, so a
                    # &-span can legitimately appear at a different position.
                    # That is safe ONLY when the same codes are all still
                    # present (same multiset) and every span stays balanced;
                    # a lost or invented code still renders wrong, and %s/%d
                    # order is never negotiable, so both stay strict.
                    reordered_amp_only = (
                        key in AMP_REORDER_OK
                        and ta["format"] == tb["format"]
                        and ta["color"] == tb["color"]
                        and ta["url"] == tb["url"]
                        and Counter(ta["amp"]) == Counter(tb["amp"])
                        and balanced_spans(vietnamese)
                    )
                    if not reordered_amp_only:
                        errors.append(f"token mismatch {rel}:{key}: {ta} != {tb}")
                # A real newline truncates the .lang entry in game.
                if "\n" in vietnamese or "\r" in vietnamese:
                    errors.append(f"raw newline {rel}:{key}")
                # Dropping a literal \n merges two tooltip lines into one.
                if english.count("\\n") != vietnamese.count("\\n"):
                    errors.append(
                        f"literal \\n count {rel}:{key}: "
                        f"{english.count(chr(92)+'n')} != {vietnamese.count(chr(92)+'n')}"
                    )
                # Registry display names are guarded in validate_lang.py, not
                # here: this module's PAIRS reach only runtime_locales and
                # tooltips, where every item./tile. key is a `.tooltip` and
                # every `.name` key is a gui./title. label. The guard that used
                # to live here matched 0 of 10,039 keys -- it looked like
                # coverage and enforced nothing. The 21 real registry names go
                # through source/*.lang, which validate_lang.py owns.
                # A protected term present in English must survive into Vietnamese.
                for term in PROTECTED_TERMS:
                    if term in english and term not in vietnamese:
                        if (rel, key) in PROTECTED_TERM_EXEMPT:
                            break
                        errors.append(
                            f"protected term dropped {rel}:{key}: {term!r}"
                        )
                        break
                # Brackets must close in the translation, and any figure inside
                # a source bracket must survive: those hold quantities and
                # ranges, and dropping one silently rewrites a spec.
                plain_en_full = label_text(english)
                plain_vi_full = label_text(vietnamese)
                for opener, closer in (("(", ")"), ("[", "]"), ("{", "}")):
                    if unbalanced(plain_vi_full, opener, closer) and not unbalanced(
                        plain_en_full, opener, closer
                    ):
                        errors.append(
                            f"unbalanced {opener}{closer} {rel}:{key}"
                        )
                for inner in re.findall(r"\(([^()]{1,80})\)", plain_en_full):
                    for figure in re.findall(r"\d+(?:[.,]\d+)?", inner):
                        if figure not in plain_vi_full:
                            errors.append(
                                f"figure dropped from bracket {rel}:{key}: {figure!r}"
                            )
                # CJK characters are machine-translation debris, never intent:
                # a stray one glued to a Vietnamese word ("thời điểm phát射")
                # reads as corruption even though the vanilla font renders it.
                # Emoji live outside the BMP, which this font cannot draw at
                # all, so they would surface in-game as a blank box.
                for char in vietnamese:
                    if char in english:
                        continue
                    point = ord(char)
                    if (
                        0x3040 <= point <= 0x30FF
                        or 0x3400 <= point <= 0x9FFF
                        or 0xAC00 <= point <= 0xD7AF
                    ):
                        errors.append(
                            f"CJK character {rel}:{key}: {char!r}"
                        )
                    elif point > 0xFFFF:
                        errors.append(
                            f"non-BMP character {rel}:{key}: {char!r}"
                        )
                # An untranslated string is not simply "equals the source":
                # proper nouns and command syntax are meant to stay English.
                # What is never intentional is a value that is itself a lang
                # key -- except where upstream already ships that bug, so the
                # source has to be checked before blaming the translation.
                stripped_vi = plain_vi_full.strip()
                if (
                    re.fullmatch(r"[a-z0-9_]+(\.[a-zA-Z0-9_]+){2,}", stripped_vi)
                    and stripped_vi != label_text(english).strip()
                ):
                    errors.append(
                        f"value is a lang key {rel}:{key}: {stripped_vi!r}"
                    )
                # An empty translation blanks the label in-game, but several
                # sources ship empty on purpose (spacer rows in tooltips).
                if not vietnamese.strip() and english.strip():
                    errors.append(f"empty translation {rel}:{key}")
                # Leading/trailing spaces are load-bearing: MC concatenates
                # these strings, so an added one shifts the label and a dropped
                # one glues two words together ("Máu: " + 20 -> "Máu:20").
                # Count them -- a boolean has/hasn't misses indentation, where
                # two leading spaces mean "sub-item" and one means something
                # else (enderutilities andmorestacksnotlisted shipped 2 -> 1).
                lead_en = len(english) - len(english.lstrip(" "))
                lead_vi = len(vietnamese) - len(vietnamese.lstrip(" "))
                if lead_en != lead_vi:
                    errors.append(
                        f"leading space {rel}:{key}: {lead_en} != {lead_vi}"
                    )
                # A trailing space on long guide-book prose is different: the
                # book self-wraps, nothing is concatenated after it, and the
                # source often just has a stray space before a paragraph end.
                # Only short strings can be a label or a split-sentence piece.
                tail_en = len(english) - len(english.rstrip(" "))
                tail_vi = len(vietnamese) - len(vietnamese.rstrip(" "))
                if tail_en != tail_vi and (len(english) <= 120 or tail_en == 0):
                    errors.append(
                        f"trailing space {rel}:{key}: {tail_en} != {tail_vi}"
                    )
                # Collect short fixed labels for the cross-file consistency pass.
                plain_en = label_text(english)
                if (
                    plain_en
                    and len(plain_en) <= CONSISTENCY_MAX_LEN
                    and "%" not in plain_en
                    and "\\n" not in english
                ):
                    labels.setdefault(plain_en, []).append(
                        (label_text(vietnamese), f"{json_path.stem}:{key}")
                    )
            report[rel] = {"entries": len(source), "checked": checked}
    errors.extend(consistency_errors(labels))
    return report, errors


if __name__ == "__main__":
    report, errors = validate()
    print(json.dumps({"report": report, "errors": errors}, ensure_ascii=False, indent=2))
    sys.exit(bool(errors))
