import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SERVER=ROOT/"Divine_Journey_2.23.4_Server_Pack"

class ServerScriptLocalizationTests(unittest.TestCase):
    def test_excavator_only_contains_reviewed_display_localization(self):
        text=(SERVER/"scripts/JEI/Excavator.zs").read_text(encoding="utf-8")
        self.assertIn('var locations = "Sinh ra ở ";',text)
        self.assertIn('~ " và " ~',text)
        self.assertIn('locations ~ "và ";',text)
        self.assertNotIn('var locations = "Generates in the ";',text)
        self.assertEqual(text.count('Excavator.addMineral(name, rarity, 0.005, ores, chances, dims);'),1)
        self.assertEqual(text.count('container.addItemOutput("item_output" ~ i, ore.firstItem * (chances[i] * 100));'),1)

    def test_contenttweaker_only_localizes_player_messages(self):
        text=(SERVER/"scripts/ContentTweaker/ContentTweakerItems.zs").read_text(encoding="utf-8")
        self.assertIn('Chỉ số Warp của bạn đã được đặt về 0!',text)
        self.assertIn('Bạn phải ở Overworld để thực hiện công thức này!',text)
        self.assertNotIn('Your warp has been set to 0!',text)
        self.assertNotIn('You must be in the Overworld to perform this craft!',text)
        self.assertEqual(text.count('Commands.call("tc warp @p set 0", player, world, false, true);'),1)
        self.assertEqual(text.count('Commands.call("tc warp @p set 0 TEMP", player, world, false, true);'),1)

    def test_ftbutilities_join_hint_explains_tpa_direction_and_accept_command(self):
        text=(SERVER/"config/ftbutilities.cfg").read_text(encoding="utf-8")
        # FTBUtilities only translates the section sign; '&' codes reach the player
        # as literal text ("&aChao mung..."), which is exactly what was observed in-game.
        self.assertIn("Gõ \u00a7e/tpa <tên_người_chơi>\u00a77 để gửi yêu cầu dịch chuyển đến họ.",text)
        self.assertIn("Người nhận dùng \u00a7e/tpaccept <tên_người_chơi>\u00a77 để chấp nhận.",text)
        self.assertNotIn("Gõ \u00a7e/tpa \u00a77để dịch chuyển tới bạn bè.",text)

if __name__=="__main__": unittest.main()
