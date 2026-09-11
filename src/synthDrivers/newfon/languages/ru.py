# -*- coding: utf-8 -*-
# A part from newfon speech synthesizer
# Copyright (C) 2019/2022 Sergey Shishmintsev, Alexy Sadovoi, Sergey A.K.A. Electrik, Kvark and other developers

import re

# Русский текст готовит сам драйвер (см. __init__.py). Здесь лежат кириллические
# таблицы и правила, общие для модулей хорватского, польского и сербского языков.
# Названия букв (letters) и замены символов (pronunciation) берутся из секций
# SingleCharacters и Characters файла newfon.ini. Драйвер передаёт сюда их
# кириллическую часть через setCharacters
letters = {}
pronunciation = {}

rules = {
	re.compile("ц([яюьё])", re.U|re.I): "тс\\1",
}

def setCharacters(letterNames, replacements):
	global letters, pronunciation
	# Таблицы подменяются целиком, а не правятся на месте,
	# потому что рабочий поток может как раз читать их
	letters = dict(letterNames)
	pronunciation = dict(replacements)

def preprocessText(text):
	for rule in rules:
		text = rule.sub(rules[rule], text)
	for s in pronunciation:
		text = text.replace(s, pronunciation[s])
	return text
