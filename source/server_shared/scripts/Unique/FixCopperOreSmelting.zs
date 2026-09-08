// Restore furnace smelting for copper ores that the pack's unification pass misses.
//
// OreProcessingAdditions.zs builds `additionalCopperOres` from a hand-written list.
// That list omits mysticalworld:copper_ore, the copper ore generated in the
// overworld, along with every Underground Biomes stone variant of it. Those ores do
// get registered for grinding in UnifyingDusts.zs and for Mekanism enrichment in
// OreProcessingAdditions.zs, but nothing ever calls furnace.addRecipe for them, so a
// plain furnace cannot smelt overworld copper. Nether copper works only because
// BasicNetherOres is handled on a separate code path.
//
// Iterating the oreCopper ore dictionary covers every copper ore registered there,
// including future ones, instead of repeating the hand-written list that caused the
// gap in the first place.

import crafttweaker.item.IItemStack;

val copperIngot = <thermalfoundation:material:128>;

for copperOre in <ore:oreCopper>.items {
    furnace.addRecipe(copperIngot, copperOre);
}

// Underground Biomes registers one block per host stone type rather than one block
// with metadata variants, and those blocks are not part of the oreCopper entries
// above. All three stone families exist in this world's registry.
val undergroundBiomesCopperOres = [
    <undergroundbiomes:igneous_stone_mysticalworld_copper_ore:*>,
    <undergroundbiomes:metamorphic_stone_mysticalworld_copper_ore:*>,
    <undergroundbiomes:sedimentary_stone_mysticalworld_copper_ore:*>
] as IItemStack[];

for copperOre in undergroundBiomesCopperOres {
    furnace.addRecipe(copperIngot, copperOre);
}
