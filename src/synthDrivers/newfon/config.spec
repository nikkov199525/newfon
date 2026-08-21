[Parameters]
# Частота дискретизации выходного аудиоустройства. Допустимые значения от 8000 до 16000. По умолчанию 10000
# Параметр доступен и в настройках синтезатора, там он меняется на лету и сохраняется сюда же
samples_per_sec = integer(min=8000, max=16000, default=10000)

# Множитель интерполяции выходного сигнала. Допустимые значения: 1, 2 или 4. По умолчанию 1
# Итоговая выходная частота равна samples_per_sec * interpolation_multiplier
interpolation_multiplier = integer(min=1, max=4, default=1)

# Алгоритм интерполяции. 0 — линейный, 1 — нулевого порядка (ZOH). По умолчанию 0
interpolation_algorithm = integer(min=0, max=1, default=0)

# Использовать исходный алгоритм перехода между звуками, как в Newfon.
# Если параметр выключен, используется адаптивный алгоритм ru_tts.
# Параметр доступен в кольце настроек и применяется сразу.
# Допустимые значения True или False. По умолчанию True
UseLegacyRateAlgo = boolean(default=True)

# Читать десятичные дроби, у которых целая часть отделена точкой. Допустимые значения True или False. По умолчанию True
dec_sep_point = boolean(default=True)

# Читать десятичные дроби, у которых целая часть отделена запятой. Допустимые значения True или False. По умолчанию True
dec_sep_comma = boolean(default=True)

# Использовать Unicode-нормализацию читаемого текста. Допустимые значения True или False. По умолчанию False
# Форма нормализации определяется параметром unicode_normalization_form
use_unicode_normalization = boolean(default=False)

# Форма Unicode-нормализации читаемого текста. Учитывается только если параметр use_unicode_normalization имеет значение True
# Допустимые значения: NFC, NFKC, NFD или NFKD. По умолчанию NFC
unicode_normalization_form = string(default=NFC)

[Characters]
j = string(default=дж)
q = string(default=ку)
w = string(default=в)
x = string(default=кс)

[SingleCharacters]
б = string(default=бэ)
в = string(default=вэ)
с = string(default=эс)
к = string(default=ка)
ь = string(default=мягкий знак)
ъ = string(default=твёрдый знак)

a = string(default=эй)
b = string(default=би)
c = string(default=си)
d = string(default=ди)
e = string(default=и)
f = string(default=эф)
g = string(default=джи)
h = string(default=эйчь)
i = string(default=ай)
j = string(default=джей)
k = string(default=кей)
l = string(default=эл)
m = string(default=эм)
n = string(default=эн)
o = string(default=оу)
p = string(default=пи)
q = string(default=къю)
r = string(default=ар)
s = string(default=эс)
t = string(default=ти)
u = string(default=ю)
v = string(default=ви)
w = string(default=даблъю)
x = string(default=экс)
y = string(default=вай)
z = string(default=зэт)
