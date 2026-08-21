// Newfon core wrapper for NVDA
// Copyright (C) 2021 - 2025 Александр Линьков <kvark128@yandex.ru>
// Этот файл распространяется под лицензией MIT

#ifdef __cplusplus
extern "C" {
#endif

#include <samplerate.h>
#include <newfon_core.h>

typedef struct {
	char *wave_buffer;
	short *samples;
	float *resampler_input;
	float *resampler_output;
	short *resampled_buffer;
	SRC_STATE *converter;
	int interpolation_multiplier;
	int interpolation_algorithm;
	float volume;
	newfon_callback consumer;
} TTS_t;

// tts_create принимает функцию обратного вызова для аудиоданных, инициализирует и возвращает указатель на экземпляр TTS.
// Если инициализация не удалась, возвращается NULL.
// Все дальнейшие операции по синтезу речи выполняются при помощи этого указателя.
// По окончании работы, экземпляр TTS необходимо уничтожить, вызвав tts_destroy
NEWFON_EXPORT TTS_t* tts_create(newfon_callback wave_consumer);

// tts_destroy уничтожает экземпляр TTS, освобождая всю выделенную для него память.
// После вызова tts_destroy, указатель на экземпляр TTS становится недействительным и больше не должен никак использоваться.
NEWFON_EXPORT void tts_destroy(TTS_t *tts);

// tts_speak принимает указатель на экземпляр TTS, указатель на структуру с конфигурацией синтезируемой речи, и текст в кодировке KOI8-R, который далее и произносится.
// Все синтезированные аудиоданные передаются порциями в функцию обратного вызова, установленную при создании экземпляра TTS.
NEWFON_EXPORT void tts_speak(const TTS_t *tts, const newfon_conf_t *config, const char *text);

// tts_setVolume задаёт громкость синтезируемых аудиоданных для экземпляра TTS. Значение громкости по умолчанию 1.0.
NEWFON_EXPORT void tts_setVolume(TTS_t *tts, float volume);

// tts_setInterpolation задаёт множитель (1, 2 или 4) и алгоритм интерполяции
// (0 — линейный, 1 — нулевого порядка). Возвращает 0 при успехе.
NEWFON_EXPORT int tts_setInterpolation(TTS_t *tts, int multiplier, int algorithm);

#ifdef __cplusplus
}
#endif
