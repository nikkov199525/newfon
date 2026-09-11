# -*- coding: utf-8 -*-
# A part from newfon speech synthesizer
# Copyright (C) 2019/2022 Sergey Shishmintsev, Alexy Sadovoi, Sergey A.K.A. Electrik, Kvark and other developers

import re

# Названия латинских букв (letters) и замены латинских символов (pronunciation)
# берутся из секций SingleCharacters и Characters файла newfon.ini. Драйвер
# передаёт сюда их латинскую часть через setCharacters
letters = {}
pronunciation = {}

# Сочетания букв. Заменяются раньше отдельных символов
rules = {
	'ee': "е е",
}

re_englishLetters = re.compile(r"\b([a-zA-Z])\b")
re_dash = re.compile(r"(\w)-(\w)")

def setCharacters(letterNames, replacements):
	global letters, pronunciation
	# Таблицы подменяются целиком, а не правятся на месте,
	# потому что рабочий поток может как раз читать их
	letters = dict(letterNames)
	pronunciation = dict(replacements)

def subEnglishLetters(match):
	letter = match.group(1).lower()
	return letters.get(letter, letter)

def preprocessText(text):
	text = re_dash.sub(r"\1 - \2", text)
	text = re_englishLetters.sub(subEnglishLetters, text)
	for s in rules:
		text = text.replace(s, rules[s])
	for s in pronunciation:
		text = text.replace(s, pronunciation[s])
	return text
