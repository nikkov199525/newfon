// Copyright (C) 2026 Александр Линьков <kvark128@yandex.ru>
// Этот файл распространяется под лицензией MIT

#ifdef _WIN32
#include <io.h>
#include <stringapiset.h>
#include <stdlib.h>

int __cdecl access(const char *path, int mode) {
	int wide_len = MultiByteToWideChar(CP_UTF8, 0, path, -1, NULL, 0);
	if (wide_len == 0) {
		return -1;
	}

	wchar_t *wide_path = malloc(wide_len * sizeof(wchar_t));
	if (wide_path == NULL) {
		return -1;
	}

	if (MultiByteToWideChar(CP_UTF8, 0, path, -1, wide_path, wide_len) == 0) {
		free(wide_path);
		return -1;
	}

	int result = _waccess(wide_path, mode);
	free(wide_path);
	return result;
}
#endif
