# Описание параметров Newfon и их умолчания.
# Сами значения хранятся в файле newfon.ini в каталоге конфигурации NVDA
# (обычно %APPDATA%\nvda\newfon.ini). Менять их нужно там: этот файл
# перезаписывается при обновлении дополнения. Если параметра в newfon.ini нет,
# берётся умолчание отсюда. Недопустимое значение заменяется умолчанием,
# а в журнал NVDA пишется предупреждение.
# Правки newfon.ini применяются после перезапуска NVDA или возврата
# к сохранённой конфигурации (NVDA+Ctrl+R).

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

# Читать десятичные дроби, у которых целая часть отделена точкой: 3.14 — «три целых четырнадцать сотых».
# Если выключено, число читается как есть, что удобно для номеров версий.
# Параметр доступен в настройках синтезатора и кольце настроек.
# Допустимые значения True или False. По умолчанию True
dec_sep_point = boolean(default=True)

# Читать десятичные дроби, у которых целая часть отделена запятой: 3,14 — «три целых четырнадцать сотых».
# Параметр доступен в настройках синтезатора и кольце настроек.
# Допустимые значения True или False. По умолчанию True
dec_sep_comma = boolean(default=True)

# Замены отдельных символов. В русском тексте они делаются перед передачей
# текста ядру, а внутри русских слов ещё до словаря RuLex, чтобы словарь видел
# слово таким, каким оно прозвучит. Замены кириллических символов применяют
# и модули хорватского, польского и сербского языков, а латинских — украинского.
# Ядро само читает большую часть латиницы, как оригинальный Newfon (q как «к»,
# w как «в»), здесь перечислены буквы, которые оно читает неверно.
# Можно добавлять свои строки вида символ = замена
# Символы, которые ядро читать не умеет (псевдографика │ ─ ║ ■, знаки ° ² ≤ ≥ √ ©
# и т. п.), из речи выбрасываются, если их нет ни в этой секции, ни в SingleCharacters
[Characters]
e = string(default=е)
j = string(default=дж)
x = string(default=кс)
y = string(default=ы)
# Дореформенные буквы и буквы других кириллических алфавитов
ґ = string(default=г)
і = string(default=и)
ѣ = string(default=е)
ѳ = string(default=ф)
ѵ = string(default=и)
ў = string(default=у)

# Названия букв: когда текст состоит из одной буквы, когда латинская буква
# стоит отдельно и когда аббревиатура из одних согласных читается по буквам.
# Названия кириллических букв используют и модули хорватского, польского
# и сербского языков, а латинских — украинского.
# Можно добавлять свои строки вида буква = название
[SingleCharacters]
б = string(default=бэ)
в = string(default=вэ)
г = string(default=гэ)
д = string(default=дэ)
ж = string(default=же)
з = string(default=зэ)
й = string(default=и краткое)
к = string(default=ка)
л = string(default=эль)
м = string(default=эм)
н = string(default=эн)
п = string(default=пэ)
р = string(default=эр)
с = string(default=эс)
т = string(default=тэ)
ф = string(default=эф)
х = string(default=ха)
ц = string(default=це)
ч = string(default=че)
ш = string(default=ша)
щ = string(default=ща)
ъ = string(default=твёрдый знак)
ь = string(default=мягкий знак)
і = string(default=и десятеричное)
ѣ = string(default=ять)
ѳ = string(default=фита)
ѵ = string(default=ижица)
ў = string(default=у краткое)
ґ = string(default=гэ взрывное)

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
