"""Test the real configuration methods without loading audio or importing NVDA."""
import ast
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/.deps/build-tools"))
from configobj import ConfigObj, flatten_errors
from configobj.validate import Validator


class Setting:
    def __init__(self, id, label="", **options):
        self.id = id
        self.label = label
        self.__dict__.update(options)


class DriverBase:
    VoiceSetting = LanguageSetting = RateSetting = PitchSetting = InflectionSetting = VolumeSetting = staticmethod(lambda: Setting("standard"))

    def loadSettings(self, onlyChanged=False):
        pass

    def saveSettings(self):
        pass


def load_driver_methods():
    tree = ast.parse((ROOT / "src/synthDrivers/newfon/__init__.py").read_text(encoding="utf-8-sig"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "SynthDriver")
    methods = {"_openUserConfiguration", "_loadUserConfiguration", "_writeUserConfiguration",
               "_speechFlags", "_get_zeroCountMin", "_set_zeroCountMin", "_saveSpeechFlags",
               "_get_useLegacyRateAlgo", "_set_useLegacyRateAlgo",
               "_get_decimalFractionsPoint", "_set_decimalFractionsPoint",
               "_get_decimalFractionsComma", "_set_decimalFractionsComma",
               "_updateSpeechFlags", "_get_supportedSettings", "loadSettings", "saveSettings"}
    cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in methods]
    cls.bases = [ast.Name(id="DriverBase", ctx=ast.Load())]
    constants = {"ZERO_COUNT_MIN_MAX", "ZERO_COUNT_MIN_SHIFT", "DEC_SEP_POINT", "DEC_SEP_COMMA", "USE_LEGACY_RATE_ALGO", "FLAGS_PARAM"}
    selected = [node for node in tree.body if
                isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets) or
                isinstance(node, ast.FunctionDef) and node.name in {"_normalizeInterpolationMultiplier", "_normalizeInterpolationAlgorithm"}]
    env = dict(DriverBase=DriverBase, DriverSetting=Setting, NumericDriverSetting=Setting,
               BooleanDriverSetting=Setting, _=lambda text: text, ConfigObj=ConfigObj,
               flatten_errors=flatten_errors, Validator=Validator, log=Mock(),
               CONFIG_SPEC_PATH=ROOT / "src/synthDrivers/newfon/config.spec",
               globalVars=SimpleNamespace(appArgs=SimpleNamespace(secure=False)))
    module = ast.fix_missing_locations(ast.Module(body=selected + [cls], type_ignores=[]))
    exec(compile(module, "newfon_configuration_methods", "exec"), env)
    driver = env["SynthDriver"]
    for setting in ("zeroCountMin", "useLegacyRateAlgo", "decimalFractionsPoint", "decimalFractionsComma"):
        setattr(driver, setting, property(getattr(driver, "_get_" + setting), getattr(driver, "_set_" + setting)))
    return driver, env


class ZeroCountSetting(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        cls, self.env = load_driver_methods()
        self.path = Path(self.temp.name) / "newfon.ini"
        self.env["CONFIG_FILE_PATH"] = self.path
        self.driver = cls()
        self.driver._SynthDriver__zeroCountMin = 3
        self.driver._SynthDriver__decSepPoint = True
        self.driver._SynthDriver__decSepComma = True
        self.driver._SynthDriver__useLegacyRateAlgo = True
        self.driver._SynthDriver__rulex_dict = None
        self.driver._SynthDriver__sampleRate = 10000
        self.driver._SynthDriver__interpolationMultiplier = "1"
        self.driver._SynthDriver__interpolationAlgorithm = "0"
        self.driver._setParameter = Mock()
        self.driver._applyTextConfiguration = Mock()
        self.driver._saveInterpolationConfiguration = Mock()
        self.driver._SynthDriver__user_config = self.driver._loadUserConfiguration()

    def test_missing_setting_defaults_to_three(self):
        self.assertEqual(ConfigObj(str(self.path), encoding="utf-8")["Parameters"]["zero_count_min"], "3")
        self.assertEqual(self.driver.zeroCountMin, 3)

    def test_setting_is_in_dialog_and_ring(self):
        settings = self.driver._get_supportedSettings()
        setting = next(s for s in settings if s.id == "zeroCountMin")
        self.assertTrue(setting.availableInSettingsRing)
        self.assertFalse(setting.useConfig)
        self.assertEqual((setting.minVal, setting.maxVal, setting.defaultVal, setting.normalStep), (2, 100, 3, 1))

    def test_gui_change_queues_flags_and_saves_ini(self):
        self.driver.zeroCountMin = 5
        self.driver._setParameter.assert_called_once_with("flags", (5 << 8) | 1 | 2 | 8)
        self.assertEqual(ConfigObj(str(self.path), encoding="utf-8")["Parameters"]["zero_count_min"], "5")
        self.driver.zeroCountMin = 5
        self.driver._setParameter.assert_called_once()

    def test_reload_uses_manual_ini_value(self):
        config = ConfigObj(str(self.path), encoding="utf-8")
        config["Parameters"]["zero_count_min"] = 8
        config.write()
        self.driver.loadSettings()
        self.assertEqual(self.driver.zeroCountMin, 8)
        self.driver._setParameter.assert_called_once_with("flags", (8 << 8) | 1 | 2 | 8)

    def test_invalid_ini_value_falls_back_to_default(self):
        for value in ("no", "0", "1", "101"):
            with self.subTest(value=value):
                self.path.write_text("[Parameters]\nzero_count_min = " + value + "\n", encoding="utf-8")
                self.assertEqual(self.driver._loadUserConfiguration()["Parameters"]["zero_count_min"], 3)

    def test_reload_applies_all_manual_changes_together(self):
        config = ConfigObj(str(self.path), encoding="utf-8")
        config["Parameters"].update({"zero_count_min": 8, "dec_sep_point": False, "UseLegacyRateAlgo": False})
        config.write()
        self.driver.loadSettings()
        self.assertEqual(self.driver.zeroCountMin, 8)
        self.assertFalse(self.driver.decimalFractionsPoint)
        self.assertFalse(self.driver.useLegacyRateAlgo)
        self.assertEqual(self.driver._setParameter.call_args.args, ("flags", (8 << 8) | 2))
        saved = ConfigObj(str(self.path), encoding="utf-8")["Parameters"]
        self.assertEqual((saved["zero_count_min"], saved["dec_sep_point"], saved["UseLegacyRateAlgo"]), ("8", "False", "False"))

    def test_changes_preserve_decimal_and_legacy_flags(self):
        self.driver._SynthDriver__decSepPoint = False
        self.driver._SynthDriver__useLegacyRateAlgo = False
        self.driver.zeroCountMin = 2
        self.driver._setParameter.assert_called_once_with("flags", (2 << 8) | 2)


if __name__ == "__main__":
    unittest.main()


