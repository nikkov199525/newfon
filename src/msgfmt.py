# Minimal msgfmt: compiles a .po file into a binary .mo catalogue.
# It exists because the gettext tools are usually not available on Windows.
# Usage: python -B msgfmt.py -o output.mo input.po

import array
import struct
import sys


def unescape(value):
	return value.encode("raw_unicode_escape").decode("unicode_escape")


def parse(path):
	catalogue = {}
	msgid = msgstr = None
	section = None
	fuzzy = False
	pending_fuzzy = False
	with open(path, "rt", encoding="utf-8") as f:
		lines = f.readlines() + [""]
	for line in lines:
		line = line.strip()
		if line.startswith("#,") and "fuzzy" in line:
			pending_fuzzy = True
			continue
		if not line or line.startswith("#"):
			if section == "msgstr" and msgid is not None:
				if not fuzzy:
					catalogue[msgid] = msgstr
				msgid = msgstr = None
				section = None
				fuzzy = False
			continue
		if line.startswith("msgid_plural"):
			raise SystemExit("msgfmt.py: plural forms are not supported")
		if line.startswith("msgid"):
			if section == "msgstr" and msgid is not None and not fuzzy:
				catalogue[msgid] = msgstr
			if section == "msgstr":
				fuzzy = False
			section = "msgid"
			msgid = unescape(line[5:].strip()[1:-1])
			msgstr = ""
			fuzzy = pending_fuzzy
			pending_fuzzy = False
		elif line.startswith("msgstr"):
			section = "msgstr"
			msgstr = unescape(line[6:].strip()[1:-1])
		elif line.startswith('"'):
			if section == "msgid":
				msgid += unescape(line[1:-1])
			elif section == "msgstr":
				msgstr += unescape(line[1:-1])
	if section == "msgstr" and msgid is not None and not fuzzy:
		catalogue[msgid] = msgstr
	return catalogue


def generate(catalogue):
	keys = sorted(catalogue.keys())
	offsets = []
	ids = strs = b""
	for key in keys:
		encoded_id = key.encode("utf-8")
		encoded_str = catalogue[key].encode("utf-8")
		offsets.append((len(ids), len(encoded_id), len(strs), len(encoded_str)))
		ids += encoded_id + b"\0"
		strs += encoded_str + b"\0"
	keystart = 7 * 4 + 16 * len(keys)
	valuestart = keystart + len(ids)
	koffsets = []
	voffsets = []
	for o1, l1, o2, l2 in offsets:
		koffsets += [l1, o1 + keystart]
		voffsets += [l2, o2 + valuestart]
	output = struct.pack(
		"Iiiiiii",
		0x950412de,
		0,
		len(keys),
		7 * 4,
		7 * 4 + len(keys) * 8,
		0,
		0,
	)
	output += array.array("i", koffsets + voffsets).tobytes()
	output += ids
	output += strs
	return output


def main(argv):
	if (len(argv) != 4) or (argv[1] != "-o"):
		raise SystemExit("usage: msgfmt.py -o output.mo input.po")
	with open(argv[2], "wb") as f:
		f.write(generate(parse(argv[3])))


if __name__ == "__main__":
	main(sys.argv)
