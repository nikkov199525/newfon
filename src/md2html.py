# Copyright (C) 2025 Alexander Linkov <kvark128@yandex.ru>

import sys
import markdown

def md2html(src, dst, lang):
	with open(src, "rt", encoding="utf-8") as f:
		mdText = f.read()
	title = mdText.split("\n")[0].strip("# ")
	htmlText = markdown.markdown(mdText)
	docText = "\n".join([
		"<!DOCTYPE html>",
		f"<html lang=\"{lang}\">",
		"<head>",
		"<meta charset=\"UTF-8\">",
		"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
		f"<title>{title}</title>",
		"</head>\n<body>",
		htmlText,
		"</body>\n</html>",
	])
	with open(dst, "wt", encoding="utf-8") as f:
		f.write(docText)

if __name__ == "__main__":
	src = sys.argv[1]
	dst = sys.argv[2]
	lang = sys.argv[3]
	md2html(src, dst, lang)
