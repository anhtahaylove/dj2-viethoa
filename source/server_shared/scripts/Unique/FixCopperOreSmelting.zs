// Restore furnace smelting for the Underground Biomes copper ore variants.
//
// Underground Biomes wraps each host mod's ore in one block per stone family, then
// copies the base ore's furnace recipe onto those variants inside
// RegistryEvent.Register<IRecipe> (OresRegistry.applyBaseOreSmelting). That copy runs
// during registry construction, before CraftTweaker's INITIALIZATION phase. Whatever
// the base ore's furnace recipe is at that moment is what the variants inherit --
// forever. Nothing re-runs the copy afterwards.
//
// thermalfoundation:ore:0 is the copper ore the overworld actually generates
// (config/cofh/world/01_thermalfoundation_ores.json, y 30-75, blacklisted from
// dimensions -1 and 1). ThermalFoundation registers its own furnace recipe from
// BlockOre, but that registration does not land before Underground Biomes copies
// recipes, so the wrapped variants ship without one. The base ore smelts; the
// variants the player actually mines do not.
//
// Nether copper is unaffected: BasicNetherOres ore is not wrapped by Underground
// Biomes at all (undergroundbiomes.cfg sets ExcludedDimensions=-1,1), and it is
// removed from the oreCopper dictionary at OreProcessingAdditions.zs:435, so it keeps
// working through its own code path.
//
// Registering the variants explicitly is the only fix available from CraftTweaker,
// which runs long after the copy window has closed.

import crafttweaker.item.IItemStack;

val copperIngot = <thermalfoundation:material:128>;

// The three stone families Underground Biomes generates, wrapping the ores the pack's
// own UBCopperOres list (OreProcessingAdditions.zs:717) already treats as copper.
val undergroundBiomesCopperOres = [
    <undergroundbiomes:igneous_stone_thermalfoundation_ore:*>,
    <undergroundbiomes:metamorphic_stone_thermalfoundation_ore:*>,
    <undergroundbiomes:sedimentary_stone_thermalfoundation_ore:*>,
    <undergroundbiomes:igneous_stone_immersiveengineering_ore:*>,
    <undergroundbiomes:metamorphic_stone_immersiveengineering_ore:*>,
    <undergroundbiomes:sedimentary_stone_immersiveengineering_ore:*>,
    <undergroundbiomes:igneous_stone_mekanism_oreblock_1:*>,
    <undergroundbiomes:metamorphic_stone_mekanism_oreblock_1:*>,
    <undergroundbiomes:sedimentary_stone_mekanism_oreblock_1:*>
] as IItemStack[];

for copperOre in undergroundBiomesCopperOres {
    furnace.addRecipe(copperIngot, copperOre);
}

// The same registry-order defect hits every ThermalFoundation ore, because BlockOre
// registers all nine furnace recipes from one initialize() call
// (cofh/thermalfoundation/block/BlockOre.class: oreCopper, oreTin, oreSilver, oreLead,
// oreAluminum, oreNickel, orePlatinum, oreIridium, oreMithril). Copper is not special --
// it was simply the one reported. Of those, config/cofh/world/01_thermalfoundation_ores.json
// generates copper, tin, nickel and aluminum in the overworld, so those are the variants a
// player can actually mine and fail to smelt. Ingot metadata comes from
// ItemMaterial.addOreDictItem: 128 ingotCopper, 129 ingotTin, 132 ingotAluminum,
// 133 ingotNickel.

val tinIngot = <thermalfoundation:material:129>;
val aluminumIngot = <thermalfoundation:material:132>;
val nickelIngot = <thermalfoundation:material:133>;

// UBTinOres (OreProcessingAdditions.zs:718)
val undergroundBiomesTinOres = [
    <undergroundbiomes:igneous_stone_tile.thermalfoundation.ore.tin.name:*>,
    <undergroundbiomes:metamorphic_stone_tile.thermalfoundation.ore.tin.name:*>,
    <undergroundbiomes:sedimentary_stone_tile.thermalfoundation.ore.tin.name:*>,
    <undergroundbiomes:igneous_stone_mekanism_oreblock_2:*>,
    <undergroundbiomes:metamorphic_stone_mekanism_oreblock_2:*>,
    <undergroundbiomes:sedimentary_stone_mekanism_oreblock_2:*>
] as IItemStack[];

// UBAluminumOres (OreProcessingAdditions.zs:708)
val undergroundBiomesAluminumOres = [
    <undergroundbiomes:igneous_stone_immersiveengineering_ore_1:*>,
    <undergroundbiomes:metamorphic_stone_immersiveengineering_ore_1:*>,
    <undergroundbiomes:sedimentary_stone_immersiveengineering_ore_1:*>,
    <undergroundbiomes:igneous_stone_tile.thermalfoundation.ore.aluminum.name:*>,
    <undergroundbiomes:metamorphic_stone_tile.thermalfoundation.ore.aluminum.name:*>,
    <undergroundbiomes:sedimentary_stone_tile.thermalfoundation.ore.aluminum.name:*>
] as IItemStack[];

// UBNickelOres (OreProcessingAdditions.zs:702)
val undergroundBiomesNickelOres = [
    <undergroundbiomes:igneous_stone_tile.thermalfoundation.ore.nickel.name:*>,
    <undergroundbiomes:metamorphic_stone_tile.thermalfoundation.ore.nickel.name:*>,
    <undergroundbiomes:sedimentary_stone_tile.thermalfoundation.ore.nickel.name:*>,
    <undergroundbiomes:igneous_stone_immersiveengineering_ore_4:*>,
    <undergroundbiomes:metamorphic_stone_immersiveengineering_ore_4:*>,
    <undergroundbiomes:sedimentary_stone_immersiveengineering_ore_4:*>
] as IItemStack[];

for tinOre in undergroundBiomesTinOres {
    furnace.addRecipe(tinIngot, tinOre);
}

for aluminumOre in undergroundBiomesAluminumOres {
    furnace.addRecipe(aluminumIngot, aluminumOre);
}

for nickelOre in undergroundBiomesNickelOres {
    furnace.addRecipe(nickelIngot, nickelOre);
}
