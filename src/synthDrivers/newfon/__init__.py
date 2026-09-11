# Copyright (C) 2021 - 2025 Александр Линьков <kvark128@yandex.ru>
# Copyright (C) 2019 - 2022 Sergey Shishmintsev, Alexy Sadovoi, Sergey A.K.A. Electrik, Kvark and other developers
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

import threading
import sys
import queue
import re
from pathlib import Path
from collections import OrderedDict
from ctypes import *
from ctypes import wintypes

import config
import addonHandler
import globalVars
import nvwave
from configobj import ConfigObj, flatten_errors
try:
	from configobj.validate import Validator
except ImportError: # NVDA ниже 2023.1
	from validate import Validator
try:
	from speech.commands import IndexCommand, PitchCommand, BreakCommand, SpeechCommand
except ImportError: # NVDA ниже 2021.1
	from speech import IndexCommand, PitchCommand, BreakCommand, SpeechCommand
from synthDriverHandler import SynthDriver, VoiceInfo, LanguageInfo, synthIndexReached, synthDoneSpeaking
try:
	from autoSettingsUtils.driverSetting import DriverSetting, NumericDriverSetting, BooleanDriverSetting
	from autoSettingsUtils.utils import StringParameterInfo
except ImportError: # NVDA ниже 2020.1
	from driverHandler import DriverSetting, NumericDriverSetting, BooleanDriverSetting, StringParameterInfo
from logHandler import log

from .languages import en, hr, pl, ru, sr, uk

addonHandler.initTranslation()

MODULE_DIR = Path(__file__).parent
# Каталоги с библиотеками называются так же, как цели сборки: x86 и x64
ARCH = "x64" if sys.maxsize > 2**32 else "x86"
LIB_DIR = MODULE_DIR.joinpath("lib", ARCH)
NEWFON_LIB_PATH = LIB_DIR.joinpath("newfon.dll")
RULEX_LIB_PATH = LIB_DIR.joinpath("rulex.dll")
# База одна на обе разрядности: она в 64-разрядном формате LMDB, а 32-разрядная
# rulex.dll собрана с MDB_VL32 и потому тоже открывает её, см. Makefile
RULEX_DB_PATH = MODULE_DIR.joinpath("rulex.db")
# Значения параметров хранятся в newfon.ini в каталоге конфигурации NVDA.
# config.spec описывает параметры и задаёт умолчания для тех, которых в файле нет
CONFIG_FILE_PATH = Path(globalVars.appArgs.configPath, "newfon.ini")
CONFIG_SPEC_PATH = MODULE_DIR.joinpath("config.spec")
NEWFON_CALLBACK = CFUNCTYPE(c_int, c_void_p, c_size_t, c_void_p)
BRAILLE_DOT_LABELS = ("первая", "вторая", "третья", "четвёртая", "пятая", "шестая", "седьмая", "восьмая")

SINGLE_CHARACTER_TRANSLATION_DICT = {
	# Подавляем произношение круглых скобок, заменяя их на пробелы
	ord('('): ' ',
	ord(')'): ' ',
}

# Кроме русского алфавита частью слова считаются дореформенные буквы и буквы
# других кириллических алфавитов, которые заменяет секция Characters
EXTRA_LETTERS = "іѣѳѵўґІѢѲѴЎҐ"
# Регулярные выражения для коррекции произношения
RE_WORDS = re.compile(f"[а-яё{EXTRA_LETTERS}́]+", re.I)
# По буквам читаются только сплошные согласные: ТТС, ФСБ, HTML, PNG.
# Слова с гласными (POCO, OZON, ВНИМАНИЕ, НАТО, GIF) не трогаем.
RE_ABBREVIATIONS = re.compile(
	f"(?<![а-яёА-ЯЁa-zA-Z{EXTRA_LETTERS}])"
	r"(?i:[bcdfghjklmnpqrstvwxzбвгджзклмнпрстфхцчшщ]{2,})"
	f"(?![а-яёА-ЯЁa-zA-Z{EXTRA_LETTERS}])"
)

# Разрезает camelCase, чтобы аббревиатура внутри слова стала отдельным
# фрагментом: chatGPT -> "chat GPT", RuTTS -> "Ru TTS", TTSEngine -> "TTS Engine".
RE_CAMEL_CASE = re.compile(
	r"(?<=[a-zа-яё])(?=[A-ZА-ЯЁ])"
	r"|(?<=[A-ZА-ЯЁ])(?=[A-ZА-ЯЁ][a-zа-яё])"
)
RE_LETTER_AFTER_NUMBER = re.compile(r"\d[а-яёa-z]", re.I)
RE_SINGLE_LATIN = re.compile(r"(?<![а-яёa-z])[a-z](?![а-яёa-z])", re.I)
# Символы KOI8-R, которые ядро не умеет читать: псевдографика │ ─ ║ ■,
# знаки ° ² ≤ ≥ √ © и неразрывный пробел, то есть всё от 0x80 до 0xBF,
# кроме ё и Ё. Ядро не пропускает их, а примешивает к речи, и «ratings │»
# звучит как «ratingzz». Такие символы заменяются пробелом, если их нет
# ни в одной секции newfon.ini
UNREADABLE_CHARACTERS = frozenset(bytes(range(0x80, 0xC0)).decode("koi8-r")) - {"ё", "Ё"}
RE_BRAILLE_PATTERNS = re.compile(r"[⠀-⣿]")

def _characterMap(section):
	result = {}
	for ch, value in section.items():
		ch = str(ch).lower()
		if len(ch) != 1:
			continue
		if isinstance(value, (list, tuple)):
			# Значение с запятыми без кавычек configobj превращает в список
			value = ", ".join(value)
		result[ch] = str(value)
	return result

def _cyrillicPart(table):
	return {ch: value for ch, value in table.items() if "Ѐ" <= ch <= "ӿ"}

def _latinPart(table):
	return {ch: value for ch, value in table.items() if "a" <= ch <= "z"}

# Text chunking mirrors the Android driver: a short first segment keeps
# startup latency low, while larger following segments reduce core restarts.
MIN_FIRST_SOURCE_SEGMENT_CHARS = 80
FIRST_SOURCE_SEGMENT_CHARS = 160
MIN_SOURCE_SEGMENT_CHARS = 240
MAX_SOURCE_SEGMENT_CHARS = 700

def _sourceSegments(text):
	start = 0
	while start < len(text):
		isFirstSegment = start == 0
		maxChars = FIRST_SOURCE_SEGMENT_CHARS if isFirstSegment else MAX_SOURCE_SEGMENT_CHARS
		minChars = MIN_FIRST_SOURCE_SEGMENT_CHARS if isFirstSegment else MIN_SOURCE_SEGMENT_CHARS
		hardLimit = min(start + maxChars, len(text))
		if hardLimit >= len(text):
			end = len(text)
		else:
			softStart = min(start + minChars, hardLimit)
			end = 0
			for index in range(hardLimit - 1, softStart - 1, -1):
				if text[index] in ".!?;\n":
					end = index + 1
					break
			if end == 0:
				for index in range(hardLimit - 1, softStart - 1, -1):
					if text[index].isspace():
						end = index + 1
						break
			if end == 0:
				end = hardLimit
		while end < len(text) and text[end].isspace():
			end += 1
		yield text[start:end]
		start = end

# Языки, поддерживаемые обвязкой Newfon. Русский текст обрабатывается
# средствами самого дополнения и словарём RuLex, остальные языки, как и в
# Newfon, приводятся к произносимому виду соответствующим модулем
LANGUAGE_MODULES = {
	"hr": hr,
	"pl": pl,
	"ru": ru,
	"sr": sr,
	"uk": uk,
}
DEFAULT_LANGUAGE = "ru"

# Скорость речи задаётся ядру так же, как это делал оригинальный Newfon:
# ползунок NVDA пересчитывается в множитель длительности, у которого
# ноль соответствует самой быстрой речи, а RATE_PARAM_MAX самой медленной
RATE_PARAM_MAX = 150
# Уровни ускорения. Ноль означает отсутствие ускорения
ACCELERATION_LEVELS = tuple(range(8))
# Пауза между фразами
PAUSE_MIN = 0
PAUSE_MAX = 100
INTERPOLATION_MULTIPLIERS = (1, 2, 4)
# Частоты дискретизации, как в старом драйвере Newfon
SAMPLE_RATES = ("8000", "9025", "10000", "11025", "12000", "13025", "14000", "15025", "16000")
SAMPLE_RATE_MIN = 8000
SAMPLE_RATE_MAX = 16000

def _rateToParam(rate):
	return RATE_PARAM_MAX - round(rate * RATE_PARAM_MAX / 100)

def _paramToRate(param):
	return round((RATE_PARAM_MAX - param) * 100 / RATE_PARAM_MAX)

def _normalizeInterpolationMultiplier(value):
	value = int(value)
	if value < 2:
		return 1
	if value > 2:
		return 4
	return 2

def _normalizeInterpolationAlgorithm(value):
	return 0 if int(value) <= 0 else 1

@POINTER
class TTS(Structure): pass

@POINTER
class RULEXDB(Structure): pass

# Ограничения на размер некоторых значений при работе с базой данных rulex
RULEXDB_MAX_KEY_SIZE = 50
RULEXDB_MAX_RECORD_SIZE = 200
RULEXDB_BUFSIZE = 256

# Режимы доступа к базе данных rulex
RULEXDB_SEARCH = 0
RULEXDB_UPDATE = 1
RULEXDB_CREATE = 2

# Коды возврата при работе с базой данных rulex
RULEXDB_SUCCESS = 0
RULEXDB_SPECIAL = 1
RULEXDB_FAILURE = -1
RULEXDB_EMALLOC = -2
RULEXDB_EINVKEY = -3
RULEXDB_EINVREC = -4
RULEXDB_EPARM = -5
RULEXDB_EACCESS = -6

# Управляющие флаги для поля flags в структуре NEWFON_CONF_T
DEC_SEP_POINT = 1 # Использовать точку в качестве десятичного разделителя
DEC_SEP_COMMA = 2 # Использовать запятую в качестве десятичного разделителя
USE_LEGACY_RATE_ALGO = 8 # Использовать исходный алгоритм перехода между звуками

class NEWFON_CONF_T(Structure):
	_fields_ = [
		("voice", c_int),
		("speech_rate", c_int),
		("acceleration", c_int),
		("pitch", c_int),
		("inflection", c_int),
		("pause", c_int),
		("flags", c_int),
	]

# Параметры синтезатора настраиваемые через графический интерфейс
VOICE_PARAM = "voice"
SPEECH_RATE_PARAM = "speech_rate"
ACCELERATION_PARAM = "acceleration"
PITCH_PARAM = "pitch"
INFLECTION_PARAM = "inflection"
PAUSE_PARAM = "pause"
FLAGS_PARAM = "flags"

# Возвращаемые значения для функции обратного вызова, обрабатывающей аудиоданные
CALLBACK_CONTINUE_SYNTHESIS = 0
CALLBACK_ABORT_SYNTHESIS = 1

class SpeechGeneration(object):
	# Каждая отмена речи начинает новое поколение, и всё, что осталось от
	# прежнего, отбрасывается. Прежний флаг тишины сбрасывался отдельным
	# заданием в очереди, и при быстрых повторных отменах рабочий поток мог
	# сбросить его раньше времени и продолжить отменённую речь. У счётчика
	# такой гонки нет. Меняет его только основной поток
	def __init__(self):
		self.value = 0

class AudioCallback(object):

	def __init__(self, generation, player):
		self.__generation = generation
		self.__player = player
		# Поколение речи, которую сейчас синтезирует рабочий поток
		self.speechGeneration = None

	def setPlayer(self, player):
		self.__player = player

	def __isCancelled(self):
		return self.speechGeneration != self.__generation.value

	def __call__(self, buffer, size, user_data):
		if self.__isCancelled():
			return CALLBACK_ABORT_SYNTHESIS
		try:
			if size > 0:
				data = string_at(buffer, size*sizeof(c_short))
				self.__player.feed(data)
			if self.__isCancelled():
				# Отмена пришла, пока кусок передавался проигрывателю. Если
				# stop() успел отработать до feed(), кусок заиграл бы заново
				# и звучал бы уже после отмены, поэтому глушим его здесь
				self.__player.stop()
				return CALLBACK_ABORT_SYNTHESIS
			return CALLBACK_CONTINUE_SYNTHESIS
		except Exception:
			log.error("newfon AudioCallback", exc_info=True)
			return CALLBACK_ABORT_SYNTHESIS

class RulexDict(object):

	def __init__(self, db_path):
		# Загрузка rulex.dll. Драйвера базы данных для словаря произношений
		self.__rulexdb = CDLL(str(RULEX_LIB_PATH))
		self.__rulexdb.rulexdb_open.argtypes = (c_char_p, c_int)
		self.__rulexdb.rulexdb_open.restype = RULEXDB
		self.__rulexdb.rulexdb_search.argtypes = (RULEXDB, c_char_p, c_char_p, c_int)
		self.__rulexdb.rulexdb_search.restype = c_int
		self.__rulexdb.rulexdb_close.argtypes = (RULEXDB,)

		# Открытие базы данных со словарём произношений и создание буфера в который мы будем получать результаты поиска по этой базе
		# При открытии базы данных драйверу передаётся указатель на строку с путём к файлу. Эта строка используется позже, поэтому нам необходимо защитить ее от сборки мусора
		self.__searchBuf = create_string_buffer(RULEXDB_BUFSIZE)
		self.__db_path = db_path.encode("utf-8")
		self.__db = self.__rulexdb.rulexdb_open(self.__db_path, RULEXDB_SEARCH)
		if not self.__db:
			raise RuntimeError("rulex: failed to open the dictionary database")

	def search(self, word):
		key = word.lower().encode("koi8-r", errors="ignore")
		if len(key) <= RULEXDB_MAX_KEY_SIZE:
			if self.__rulexdb.rulexdb_search(self.__db, key, self.__searchBuf, 0) == RULEXDB_SUCCESS:
				return self.__searchBuf.value.decode("koi8-r")
		return word

	def close(self):
		if self.__db:
			self.__rulexdb.rulexdb_close(self.__db)
		try:
			windll.kernel32.FreeLibrary(wintypes.HMODULE(self.__rulexdb._handle))
		except Exception:
			log.error("rulex: can not unload dll")
		finally:
			self.__rulexdb = None

class SpeechTask(object):
	# Задание, относящееся к конкретной речи: текст, индекс или завершение
	# речи. При отмене такие задания выбрасываются из очереди, а остальные
	# (смена параметров, громкости, интерполяции) сохраняются

	def __init__(self, func, *args):
		self.__func = func
		self.__args = args

	def __call__(self):
		self.__func(*self.__args)

class SetParameter(object):

	def __init__(self, conf, param, value):
		self.__config = conf
		self.param = param
		self.value = value

	def __call__(self):
		setattr(self.__config, self.param, self.value)

class TaskThread(threading.Thread):

	def __init__(self, task_queue):
		super().__init__()
		self.__queue = task_queue
		self.daemon = True

	def run(self):
		while True:
			try:
				task = self.__queue.get()
				if task is None:
					break
				task()
			except Exception:
				log.error("newfon: error while processing a task", exc_info=True)

class SynthDriver(SynthDriver):
	name = "newfon"
	description = "Newfon"

	def _get_supportedSettings(self):
		self.supportedSettings = settings = [
			SynthDriver.VoiceSetting(),
			SynthDriver.LanguageSetting(),
			SynthDriver.RateSetting(),
			DriverSetting("acceleration", _("&Acceleration"), availableInSettingsRing=True, defaultVal="0"),
			SynthDriver.PitchSetting(),
			SynthDriver.InflectionSetting(),
			SynthDriver.VolumeSetting(),
			NumericDriverSetting("pauseBetweenPhrases", _("&Pause between phrases"), availableInSettingsRing=True),
			DriverSetting(
				"samplesPerSec",
				_("&Samples per second (hz)"),
				availableInSettingsRing=True,
				defaultVal=str(self.__sampleRate),
				useConfig=False,
			),
			DriverSetting(
				"interpolationMultiplier",
				_("Interpolation multiplier"),
				availableInSettingsRing=True,
				defaultVal=self.__interpolationMultiplier,
				useConfig=False,
			),
			DriverSetting(
				"interpolationAlgorithm",
				_("Interpolation algorithm"),
				availableInSettingsRing=True,
				defaultVal=self.__interpolationAlgorithm,
				useConfig=False,
			),
		]
		settings.append(BooleanDriverSetting(
			"useLegacyRateAlgo",
			_("Use the old sound transition algorithm"),
			availableInSettingsRing=True,
			defaultVal=self.__useLegacyRateAlgo,
			useConfig=False,
		))
		# Как и в оригинальном Newfon, чтение десятичных дробей выключается
		# из настроек синтезатора. Значения хранятся в newfon.ini
		settings.append(BooleanDriverSetting(
			"decimalFractionsPoint",
			_("Read decimal fractions with a point"),
			availableInSettingsRing=True,
			defaultVal=self.__decSepPoint,
			useConfig=False,
		))
		settings.append(BooleanDriverSetting(
			"decimalFractionsComma",
			_("Read decimal fractions with a comma"),
			availableInSettingsRing=True,
			defaultVal=self.__decSepComma,
			useConfig=False,
		))
		if self.__rulex_dict is not None:
			rulexSetting = BooleanDriverSetting("useRulex", _("Use RuLex pronunciation dictionary"), availableInSettingsRing=True, defaultVal=True)
			settings.append(rulexSetting)
		return settings

	supportedCommands = {IndexCommand, PitchCommand, BreakCommand}
	supportedNotifications = {synthIndexReached, synthDoneSpeaking}

	def __init__(self):
		# Первым делом загружаем ядро синтезатора
		self.__newfon_lib = CDLL(str(NEWFON_LIB_PATH))
		self.__newfon_lib.tts_create.argtypes = (NEWFON_CALLBACK,)
		self.__newfon_lib.tts_create.restype = TTS
		self.__newfon_lib.tts_destroy.argtypes = (TTS,)
		self.__newfon_lib.tts_speak.argtypes = (TTS, POINTER(NEWFON_CONF_T), c_char_p)
		self.__newfon_lib.tts_setVolume.argtypes = (TTS, c_float)
		self.__newfon_lib.tts_setInterpolation.argtypes = (TTS, c_int, c_int)
		self.__newfon_lib.tts_setInterpolation.restype = c_int
		self.__newfon_lib.newfon_config_init.argtypes = (POINTER(NEWFON_CONF_T),)
		self.__newfon_lib.newfon_voice_name.argtypes = (c_int,)
		self.__newfon_lib.newfon_voice_name.restype = c_char_p

		self.__config = NEWFON_CONF_T()
		self.__newfon_lib.newfon_config_init(byref(self.__config))
		self.__user_config = self._loadUserConfiguration()

		params = self.__user_config["Parameters"]
		self.__sampleRate = params["samples_per_sec"]
		self.__interpolationMultiplier = str(params["interpolation_multiplier"])
		self.__interpolationAlgorithm = str(params["interpolation_algorithm"])
		# Паузы на знаках препинания такие же, как в Newfon, а чтение
		# десятичных дробей включается раздельно для точки и для запятой
		self.__decSepPoint = bool(params["dec_sep_point"])
		self.__decSepComma = bool(params["dec_sep_comma"])
		self.__useLegacyRateAlgo = bool(params["UseLegacyRateAlgo"])
		self.__config.flags = self._speechFlags()
		self._applyTextConfiguration()

		self.__rulex_dict = None
		try:
			self.__rulex_dict = RulexDict(str(RULEX_DB_PATH))
		except Exception:
			log.warning("rulex not available", exc_info=True)

		try:
			# Audio device used since NVDA 2025.1
			self.__outputDevice = config.conf["audio"]["outputDevice"]
		except KeyError:
			# Older NVDA versions
			self.__outputDevice = config.conf["speech"]["outputDevice"]
		self.__player = self._createPlayer()

		self.__generation = SpeechGeneration()
		self.__audio_callback = AudioCallback(self.__generation, self.__player)

		self.__c_audio_callback = NEWFON_CALLBACK(self.__audio_callback)
		self.__tts = self.__newfon_lib.tts_create(self.__c_audio_callback)
		if not self.__tts:
			raise RuntimeError("newfon: failed to create a TTS instance")
		if self.__newfon_lib.tts_setInterpolation(
			self.__tts,
			int(self.__interpolationMultiplier),
			int(self.__interpolationAlgorithm),
		) != 0:
			self.__newfon_lib.tts_destroy(self.__tts)
			self.__tts = None
			self.__player.close()
			raise RuntimeError("newfon: failed to initialize interpolation")

		self.__rate = _paramToRate(self.__config.speech_rate)
		self.__acceleration = str(self.__config.acceleration)
		self.__pitch = self.__config.pitch
		self.__inflection = self.__config.inflection
		self.__pauseBetweenPhrases = 50
		self.__config.pause = self.__pauseBetweenPhrases
		self.__volume = 50
		self.__newfon_lib.tts_setVolume(self.__tts, self.__volume/100)
		self.__useRulex = True
		self.__language = DEFAULT_LANGUAGE

		self.__task_queue = queue.Queue()
		self.__task_thread = TaskThread(self.__task_queue)
		self.__task_thread.start()

	@classmethod
	def check(cls):
		return NEWFON_LIB_PATH.is_file()

	def terminate(self):
		self.cancel()
		self.__task_queue.put(None)
		self.__task_thread.join()
		self.__player.close()
		if self.__rulex_dict is not None:
			self.__rulex_dict.close()
			self.__rulex_dict = None
		self.__config = None
		self.__newfon_lib.tts_destroy(self.__tts)
		self.__tts = None
		# Предотвращаем образование циклических ссылок
		self.__audio_callback = None
		self.__c_audio_callback = None
		# Пробуем выгрузить ядро синтезатора
		try:
			windll.kernel32.FreeLibrary(wintypes.HMODULE(self.__newfon_lib._handle))
		except Exception:
			log.error("newfon: can not unload dll")
		finally:
			self.__newfon_lib = None

	@staticmethod
	def _openUserConfiguration(path):
		with open(CONFIG_SPEC_PATH, encoding="utf-8") as spec:
			return ConfigObj(infile=path, configspec=spec, encoding="utf-8", default_encoding="utf-8")

	def _loadUserConfiguration(self):
		try:
			conf = self._openUserConfiguration(str(CONFIG_FILE_PATH))
			writable = not globalVars.appArgs.secure
		except Exception:
			log.error(f"newfon: failed to read {CONFIG_FILE_PATH}, defaults from config.spec are used", exc_info=True)
			conf = self._openUserConfiguration(None)
			# Файл с ошибкой не перезаписываем, чтобы не потерять правки пользователя
			writable = False
		validator = Validator()
		result = conf.validate(validator, copy=True, preserve_errors=True)
		if result is not True:
			# Без этого недопустимое значение оставалось строкой: например,
			# dec_sep_point = нет превращалось в True, и дроби не выключались
			for sections, key, error in flatten_errors(conf, result):
				if key is None:
					continue
				section = conf
				for name in sections:
					section = section[name]
				section[key] = validator.get_default_value(section.configspec[key])
				log.warning(f"newfon: invalid value of {'/'.join(sections + [key])} in {CONFIG_FILE_PATH}, the default {section[key]!r} is used: {error}")
		params = conf["Parameters"]
		params["interpolation_multiplier"] = _normalizeInterpolationMultiplier(params["interpolation_multiplier"])
		params["interpolation_algorithm"] = _normalizeInterpolationAlgorithm(params["interpolation_algorithm"])
		self.__configWritable = writable
		self._writeUserConfiguration(conf)
		return conf

	def _writeUserConfiguration(self, conf=None):
		if conf is None:
			conf = self.__user_config
		if not self.__configWritable:
			return
		try:
			conf.write()
		except OSError:
			log.error("newfon: failed to write config file", exc_info=True)

	def _applyTextConfiguration(self):
		conf = self.__user_config
		self.__characters = _characterMap(conf["Characters"])
		self.__singleCharacters = _characterMap(conf["SingleCharacters"])
		# Символ, для которого пользователь задал замену или название
		# в любой секции newfon.ini, не выбрасывается
		self.__unreadableCharacters = UNREADABLE_CHARACTERS.difference(self.__characters, self.__singleCharacters)
		# Таблицы нужны и модулям других языков: кириллическую часть хорватский,
		# польский и сербский берут из ru, а латинскую украинский берёт из en
		ru.setCharacters(_cyrillicPart(self.__singleCharacters), _cyrillicPart(self.__characters))
		en.setCharacters(_latinPart(self.__singleCharacters), _latinPart(self.__characters))

	def saveSettings(self):
		super().saveSettings()
		self._saveInterpolationConfiguration()
		self._saveSpeechFlags()

	def loadSettings(self, onlyChanged=False):
		super().loadSettings(onlyChanged=onlyChanged)
		if onlyChanged or not hasattr(self, "_SynthDriver__user_config"):
			return
		# newfon.ini перечитывается, чтобы правки, сделанные в нём вручную,
		# применялись при возврате к сохранённой конфигурации без перезапуска NVDA
		self.__user_config = self._loadUserConfiguration()
		params = self.__user_config["Parameters"]
		self.samplesPerSec = str(params["samples_per_sec"])
		self.interpolationMultiplier = str(params["interpolation_multiplier"])
		self.interpolationAlgorithm = str(params["interpolation_algorithm"])
		self.useLegacyRateAlgo = bool(params["UseLegacyRateAlgo"])
		self.decimalFractionsPoint = bool(params["dec_sep_point"])
		self.decimalFractionsComma = bool(params["dec_sep_comma"])
		self._applyTextConfiguration()

	def _createPlayer(self):
		return nvwave.WavePlayer(
			channels=1,
			samplesPerSec=self.__sampleRate * int(self.__interpolationMultiplier),
			bitsPerSample=16,
			outputDevice=self.__outputDevice,
		)

	def _applyInterpolationConfiguration(self, recreatePlayer):
		newPlayer = self._createPlayer() if recreatePlayer else None
		result = self.__newfon_lib.tts_setInterpolation(
			self.__tts,
			int(self.__interpolationMultiplier),
			int(self.__interpolationAlgorithm),
		)
		if result != 0:
			if newPlayer is not None:
				newPlayer.close()
			raise RuntimeError("newfon: failed to configure interpolation")
		if newPlayer is not None:
			oldPlayer = self.__player
			self.__player = newPlayer
			self.__audio_callback.setPlayer(newPlayer)
			oldPlayer.close()

	def _queueInterpolationConfiguration(self, recreatePlayer):
		self.cancel()
		self.__task_queue.put(lambda: self._applyInterpolationConfiguration(recreatePlayer))
		# NVDA не вызывает saveSettings при изменении параметра через кольцо
		# настроек, поэтому запоминаем выбор сразу
		self._saveInterpolationConfiguration()

	def _saveInterpolationConfiguration(self):
		if not hasattr(self, "_SynthDriver__user_config"):
			return
		params = self.__user_config["Parameters"]
		params["samples_per_sec"] = int(self.__sampleRate)
		params["interpolation_multiplier"] = int(self.__interpolationMultiplier)
		params["interpolation_algorithm"] = int(self.__interpolationAlgorithm)
		self._writeUserConfiguration()

	def _setParameter(self, param, value):
		task = SetParameter(self.__config, param, value)
		self.__task_queue.put(task)

	def speak(self, speechSequence):
		generation = self.__generation.value
		language = self.__language
		useRulex = self.__useRulex
		textList = []
		pitchChanged = False
		for item in speechSequence:
			if isinstance(item, str):
				textList.append(item)
			elif isinstance(item, IndexCommand):
				# Индекс сообщается в том месте, где он стоит в последовательности.
				# NVDA вешает на индексы звуки: например, звуковой отступ идёт
				# индексом перед строкой, и сообщать о нём после всей фразы нельзя
				self._queueText(generation, textList, language, useRulex)
				textList = []
				self.__task_queue.put(SpeechTask(self._indexTask, generation, item.index))
			elif isinstance(item, PitchCommand):
				# Как и в Newfon, высота задаётся произносимому куску целиком,
				# причём берётся первая из полученных команд. NVDA обрамляет
				# заглавную букву парой команд, и именно первая из них поднимает
				# высоту, а вторая возвращает её для следующих кусков
				if not pitchChanged:
					self._setParameter(PITCH_PARAM, item.newValue)
					pitchChanged = True
			elif isinstance(item, BreakCommand):
				# Как и в Newfon, длительность паузы передаётся ядру напрямую
				# и отрабатывается завершающей паузой произносимого куска
				self._setParameter(PAUSE_PARAM, max(PAUSE_MIN, min(item.time, 255)))
				self._queueText(generation, textList, language, useRulex)
				textList = []
				self._setParameter(PAUSE_PARAM, self.__pauseBetweenPhrases)
			elif isinstance(item, SpeechCommand):
				log.debugWarning(f"Unsupported speech command: {item}")
			else:
				log.error(f"Unknown speech: {item}")
		self._queueText(generation, textList, language, useRulex)
		if pitchChanged:
			self._setParameter(PITCH_PARAM, self.__pitch)
		self.__task_queue.put(SpeechTask(self._doneSpeakingTask, generation))

	def _queueText(self, generation, textList, language, useRulex):
		if not "".join(textList).strip():
			return
		# Текст готовится в рабочем потоке, а не здесь. На длинных текстах
		# подготовка и поиск по словарю занимают заметное время, и пока они
		# шли в основном потоке, NVDA не могла обработать команду заглушить речь
		self.__task_queue.put(SpeechTask(self._speakTask, generation, tuple(textList), language, useRulex))

	def _isCancelled(self, generation):
		return generation != self.__generation.value

	def _speakTask(self, generation, textList, language, useRulex):
		if self._isCancelled(generation):
			return
		text = self._processText("".join(textList).strip(), language)
		for chunk in _sourceSegments(text):
			if self._isCancelled(generation):
				return
			data = self._encodeChunk(chunk, language, useRulex)
			if data:
				self.__audio_callback.speechGeneration = generation
				self.__newfon_lib.tts_speak(self.__tts, byref(self.__config), data)

	def _indexTask(self, generation, index):
		if self._isCancelled(generation):
			return
		def onDone():
			if not self._isCancelled(generation):
				synthIndexReached.notify(synth=self, index=index)
		# Пустой кусок с onDone проигрыватель отмечает, когда доиграет всё
		# переданное до него, так что NVDA узнаёт об индексе ровно тогда,
		# когда до него дошла речь. Так же индексы сообщает eSpeak
		self.__player.feed(b"", onDone=onDone)

	def _doneSpeakingTask(self, generation):
		if self._isCancelled(generation):
			return
		self.__player.idle()
		if not self._isCancelled(generation):
			synthDoneSpeaking.notify(synth=self)

	def _processText(self, text, language):
		if language == DEFAULT_LANGUAGE:
			if len(text) == 1:
				text = self.__singleCharacters.get(text.lower(), text)
			else:
				text = RE_CAMEL_CASE.sub(" ", text)
				text = RE_SINGLE_LATIN.sub(self._singleLatinSearch, text)
				text = RE_ABBREVIATIONS.sub(self._abbreviationSearch, text)
				text = RE_LETTER_AFTER_NUMBER.sub(self._letterAfterNumberSearch, text)
		else:
			# Остальные языки приводит к произносимому виду модуль языка,
			# как это делал Newfon. Словарь RuLex здесь не применяется
			try:
				text = LANGUAGE_MODULES[language].process(text, language)
			except Exception:
				log.error(f"newfon: {language} text processing failed", exc_info=True)
		return text

	def _encodeChunk(self, chunk, language, useRulex):
		chunk = " ".join(chunk.split())
		if language == DEFAULT_LANGUAGE:
			# Замены из секции Characters делаются один раз. Внутри русских слов
			# они идут до словаря, чтобы словарь искал слово таким, каким оно
			# прозвучит: хлѣбъ как хлебъ. В остальном тексте словарь не нужен:
			# куски замен, прилипшие к латинице, он принял бы за русские слова
			parts = []
			start = 0
			for match in RE_WORDS.finditer(chunk):
				parts.append(self._replaceCharacters(chunk[start:match.start()]))
				parts.append(self._wordsSearch(self._replaceCharacters(match.group()), useRulex))
				start = match.end()
			parts.append(self._replaceCharacters(chunk[start:]))
			chunk = "".join(parts)
		chunk = chunk.translate(SINGLE_CHARACTER_TRANSLATION_DICT)
		chunk = RE_BRAILLE_PATTERNS.sub(self._brailleDotsSearch, chunk)
		# Нечитаемые символы заменяются пробелом, как и символы, которых
		# нет в KOI8-R, чтобы не склеивать слова по обе стороны от них
		unreadable = self.__unreadableCharacters
		chunk = "".join([" " if ch in unreadable else ch for ch in chunk])
		return b''.join([c if c else b' ' for c in [c.encode("koi8-r", errors="ignore") for c in chunk]])

	def pause(self, switch):
		self.__player.pause(switch)

	def cancel(self):
		# Новое поколение объявляется первым: всё, что рабочий поток возьмёт
		# после этого, увидит отмену и ничего не сделает
		self.__generation.value += 1
		tasks = []
		try:
			while True:
				task = self.__task_queue.get_nowait()
				if not isinstance(task, SpeechTask):
					tasks.append(task)
		except queue.Empty:
			pass
		for task in tasks:
			self.__task_queue.put(task)
		self.__player.stop()

	def _brailleDotsSearch(self, match):
		ch = match.group()
		dotLabels = []
		for offset, label in enumerate(BRAILLE_DOT_LABELS):
			if ord(ch) >> offset & 1:
				dotLabels.append(label)
		if len(dotLabels) == 0:
			return " брайлевский пробел "
		elif len(dotLabels) == 8:
			return " брайлевское восьмиточие "
		else:
			dotLabels.append("брайлевские точки" if len(dotLabels) > 1 else "брайлевская точка")
			return f" {' '.join(dotLabels)} "

	def _singleLatinSearch(self, match):
		ch = match.group().lower()
		return self.__singleCharacters.get(ch, ch)

	def _abbreviationSearch(self, match):
		word = match.group().lower()
		return " ".join([self.__singleCharacters.get(ch, ch) for ch in word])

	def _letterAfterNumberSearch(self, match):
		return " ".join(match.group())

	def _replaceCharacters(self, text):
		characters = self.__characters
		return "".join([characters.get(ch.lower(), ch) for ch in text])

	def _wordsSearch(self, word, useRulex):
		if "́" in word: # Проверяем наличие знака ударения
			return word.replace("́", "+", 1)
		if useRulex and (self.__rulex_dict is not None):
			return self.__rulex_dict.search(word)
		return word

	def _get_language(self):
		return self.__language

	def _set_language(self, language):
		# NVDA может передать код вида uk_UA
		language = (language or DEFAULT_LANGUAGE).replace("-", "_").split("_")[0].lower()
		if language not in LANGUAGE_MODULES:
			language = DEFAULT_LANGUAGE
		self.__language = language

	def _get_availableLanguages(self):
		# Именно _get_availableLanguages, а не _getAvailableLanguages: у голосов
		# NVDA вызывает второй метод, а язык читает напрямую из свойства.
		# Кольцу настроек и диалогу нужен словарь, у базового класса там
		# множество кодов языков, выведенное из голосов
		return OrderedDict(
			(language, LanguageInfo(language)) for language in sorted(LANGUAGE_MODULES)
		)

	def _speechFlags(self):
		flags = 0
		if self.__decSepPoint:
			flags |= DEC_SEP_POINT
		if self.__decSepComma:
			flags |= DEC_SEP_COMMA
		if self.__useLegacyRateAlgo:
			flags |= USE_LEGACY_RATE_ALGO
		return flags

	def _updateSpeechFlags(self):
		self._setParameter(FLAGS_PARAM, self._speechFlags())
		# NVDA не вызывает saveSettings при изменении параметра через кольцо
		# настроек, поэтому запоминаем выбор сразу
		self._saveSpeechFlags()

	def _get_useLegacyRateAlgo(self):
		return self.__useLegacyRateAlgo

	def _set_useLegacyRateAlgo(self, value):
		value = bool(value)
		if value == self.__useLegacyRateAlgo:
			return
		self.__useLegacyRateAlgo = value
		self._updateSpeechFlags()

	def _get_decimalFractionsPoint(self):
		return self.__decSepPoint

	def _set_decimalFractionsPoint(self, value):
		value = bool(value)
		if value == self.__decSepPoint:
			return
		self.__decSepPoint = value
		self._updateSpeechFlags()

	def _get_decimalFractionsComma(self):
		return self.__decSepComma

	def _set_decimalFractionsComma(self, value):
		value = bool(value)
		if value == self.__decSepComma:
			return
		self.__decSepComma = value
		self._updateSpeechFlags()

	def _saveSpeechFlags(self):
		if not hasattr(self, "_SynthDriver__user_config"):
			return
		params = self.__user_config["Parameters"]
		params["UseLegacyRateAlgo"] = self.__useLegacyRateAlgo
		params["dec_sep_point"] = self.__decSepPoint
		params["dec_sep_comma"] = self.__decSepComma
		self._writeUserConfiguration()

	def _getAvailableVoices(self):
		voices = OrderedDict()
		# Порядок голосов совпадает с оригинальным Newfon
		names = (
			# Translators: name of the first male voice
			_("male 1"),
			# Translators: name of the first female voice
			_("female 1"),
			# Translators: name of the second male voice
			_("male 2"),
			# Translators: name of the second female voice
			_("female 2"),
		)
		for id, displayName in enumerate(names):
			id = str(id)
			voices[id] = VoiceInfo(id, displayName, "ru")
		return voices

	def _get_voice(self):
		return str(self.__config.voice)

	def _set_voice(self, voice):
		if voice in self.availableVoices:
			self._setParameter(VOICE_PARAM, int(voice))

	def _get_rate(self):
		return self.__rate

	def _set_rate(self, value):
		self.__rate = value
		self._setParameter(SPEECH_RATE_PARAM, _rateToParam(value))

	def _get_availableAccelerations(self):
		return OrderedDict(
			(str(level), StringParameterInfo(str(level), _("Off") if level == 0 else str(level)))
			for level in ACCELERATION_LEVELS
		)

	def _get_acceleration(self):
		return self.__acceleration

	def _set_acceleration(self, value):
		value = str(value)
		if value not in self.availableAccelerations:
			return
		self.__acceleration = value
		self._setParameter(ACCELERATION_PARAM, int(value))

	def _get_pitch(self):
		return self.__pitch

	def _set_pitch(self, value):
		self.__pitch = value
		self._setParameter(PITCH_PARAM, value)

	def _get_inflection(self):
		return self.__inflection

	def _set_inflection(self, value):
		self.__inflection = value
		self._setParameter(INFLECTION_PARAM, value)

	def _get_volume(self):
		return self.__volume

	def _set_volume(self, volume):
		self.__volume = volume
		task = lambda: self.__newfon_lib.tts_setVolume(self.__tts, volume/100)
		self.__task_queue.put(task)

	def _get_pauseBetweenPhrases(self):
		return self.__pauseBetweenPhrases

	def _set_pauseBetweenPhrases(self, value):
		self.__pauseBetweenPhrases = max(PAUSE_MIN, min(int(value), PAUSE_MAX))
		self._setParameter(PAUSE_PARAM, self.__pauseBetweenPhrases)

	def _get_useRulex(self):
		return self.__useRulex

	def _set_useRulex(self, value):
		self.__useRulex = value

	def _get_availableSamplespersecs(self):
		# К стандартному ряду добавляется значение из ini, если оно другое
		rates = sorted(set(SAMPLE_RATES) | {str(self.__sampleRate)}, key=int)
		return OrderedDict(
			(rate, StringParameterInfo(rate, rate)) for rate in rates
		)

	def _get_samplesPerSec(self):
		return str(self.__sampleRate)

	def _set_samplesPerSec(self, value):
		try:
			rate = int(value)
		except ValueError:
			return
		rate = max(SAMPLE_RATE_MIN, min(rate, SAMPLE_RATE_MAX))
		if rate == self.__sampleRate:
			return
		self.__sampleRate = rate
		# Частота задаётся звуковому устройству, поэтому проигрыватель
		# пересоздаётся тем же путём, что и при смене интерполяции
		self._queueInterpolationConfiguration(recreatePlayer=True)

	def _get_availableInterpolationmultipliers(self):
		return OrderedDict(
			(str(value), StringParameterInfo(str(value), f"{value}x"))
			for value in INTERPOLATION_MULTIPLIERS
		)

	def _get_interpolationMultiplier(self):
		return self.__interpolationMultiplier

	def _set_interpolationMultiplier(self, value):
		value = str(_normalizeInterpolationMultiplier(value))
		if value == self.__interpolationMultiplier:
			return
		self.__interpolationMultiplier = value
		self._queueInterpolationConfiguration(recreatePlayer=True)

	def _get_availableInterpolationalgorithms(self):
		options = (
			("0", _("Linear")),
			("1", _("Zero-order hold")),
		)
		return OrderedDict(
			(value, StringParameterInfo(value, label))
			for value, label in options
		)

	def _get_interpolationAlgorithm(self):
		return self.__interpolationAlgorithm

	def _set_interpolationAlgorithm(self, value):
		value = str(_normalizeInterpolationAlgorithm(value))
		if value == self.__interpolationAlgorithm:
			return
		self.__interpolationAlgorithm = value
		self._queueInterpolationConfiguration(recreatePlayer=False)
