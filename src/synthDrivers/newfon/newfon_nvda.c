// Newfon core wrapper for NVDA
// Copyright (C) 2021 - 2025 Александр Линьков <kvark128@yandex.ru>
// Этот файл распространяется под лицензией MIT

#include <stdlib.h>

#include <samplerate.h>
#include <newfon_core.h>
#include "newfon_nvda.h"

#define SUCCESS 0
#define FAILURE 1

#define WAVE_SIZE 4096
#define NUM_CHANNELS 1
#define MAX_INTERPOLATION_MULTIPLIER 4
#define RESAMPLED_WAVE_SIZE (WAVE_SIZE * MAX_INTERPOLATION_MULTIPLIER + 64)

static int normalizeInterpolationMultiplier(int multiplier) {
	if (multiplier < 2) {
		return 1;
	}
	if (multiplier > 2) {
		return 4;
	}
	return 2;
}

static int interpolationConverterType(int algorithm) {
	return algorithm <= 0 ? SRC_LINEAR : SRC_ZERO_ORDER_HOLD;
}

static int writeSamplesToConsumer(TTS_t *tts, const short *samples, int numSamples) {
	if (tts->converter == NULL || tts->interpolation_multiplier == 1) {
		return tts->consumer((void*)samples, (size_t)numSamples, NULL) ? FAILURE : SUCCESS;
	}

	src_short_to_float_array(samples, tts->resampler_input, numSamples);
	long inputOffset = 0;
	while (inputOffset < numSamples) {
		SRC_DATA data = {0};
		data.data_in = tts->resampler_input + inputOffset;
		data.input_frames = numSamples - inputOffset;
		data.data_out = tts->resampler_output;
		data.output_frames = RESAMPLED_WAVE_SIZE;
		data.src_ratio = tts->interpolation_multiplier;
		data.end_of_input = 0;

		if (src_process(tts->converter, &data) != 0) {
			return FAILURE;
		}
		if (data.output_frames_gen > 0) {
			src_float_to_short_array(
				tts->resampler_output,
				tts->resampled_buffer,
				(int)data.output_frames_gen
			);
			if (tts->consumer(tts->resampled_buffer, (size_t)data.output_frames_gen, NULL)) {
				return FAILURE;
			}
		}
		if (data.input_frames_used <= 0 && data.output_frames_gen <= 0) {
			return FAILURE;
		}
		inputOffset += data.input_frames_used;
	}
	return SUCCESS;
}

static int flushResampler(TTS_t *tts) {
	if (tts->converter == NULL || tts->interpolation_multiplier == 1) {
		return SUCCESS;
	}

	while (1) {
		SRC_DATA data = {0};
		data.data_in = NULL;
		data.input_frames = 0;
		data.data_out = tts->resampler_output;
		data.output_frames = RESAMPLED_WAVE_SIZE;
		data.src_ratio = tts->interpolation_multiplier;
		data.end_of_input = 1;

		if (src_process(tts->converter, &data) != 0) {
			src_reset(tts->converter);
			return FAILURE;
		}
		if (data.output_frames_gen > 0) {
			src_float_to_short_array(
				tts->resampler_output,
				tts->resampled_buffer,
				(int)data.output_frames_gen
			);
			if (tts->consumer(tts->resampled_buffer, (size_t)data.output_frames_gen, NULL)) {
				src_reset(tts->converter);
				return FAILURE;
			}
		}
		if (data.output_frames_gen < data.output_frames) {
			break;
		}
	}
	src_reset(tts->converter);
	return SUCCESS;
}

// Ядро отдаёт восьмибитные отсчёты. Newfon превращает их в шестнадцатибитные
// простым умножением на 256 с последующим применением громкости
int audio_callback(void *buffer, size_t size, void *user_data) {
	const signed char *samples = (const signed char*) buffer;
	TTS_t *tts = (TTS_t*) user_data;
	for (size_t i = 0; i < size; i++) {
		float value = ((float)samples[i]) * 256.0f * tts->volume;
		if (value > 32767.0f) {
			value = 32767.0f;
		} else if (value < -32768.0f) {
			value = -32768.0f;
		}
		tts->samples[i] = (short)value;
	}
	return writeSamplesToConsumer(tts, tts->samples, (int)size);
}

NEWFON_EXPORT TTS_t* tts_create(newfon_callback wave_consumer) {
	if (wave_consumer == NULL) {
		return NULL;
	}
	TTS_t *tts = calloc(1, sizeof(TTS_t));
	if (tts == NULL) {
		return NULL;
	}
	tts->wave_buffer = malloc(WAVE_SIZE);
	tts->samples = malloc(WAVE_SIZE * sizeof(short));
	tts->resampler_input = malloc(WAVE_SIZE * sizeof(float));
	tts->resampler_output = malloc(RESAMPLED_WAVE_SIZE * sizeof(float));
	tts->resampled_buffer = malloc(RESAMPLED_WAVE_SIZE * sizeof(short));
	if (
		tts->wave_buffer == NULL ||
		tts->samples == NULL ||
		tts->resampler_input == NULL ||
		tts->resampler_output == NULL ||
		tts->resampled_buffer == NULL
	) {
		tts_destroy(tts);
		return NULL;
	}
	tts->converter = NULL;
	tts->interpolation_multiplier = 1;
	tts->interpolation_algorithm = 0;
	tts->volume = 1.0f;
	tts->consumer = wave_consumer;
	return tts;
}

NEWFON_EXPORT void tts_destroy(TTS_t *tts) {
	if (tts == NULL) {
		return;
	}
	if (tts->converter != NULL) {
		src_delete(tts->converter);
		tts->converter = NULL;
	}
	free(tts->wave_buffer);
	free(tts->samples);
	free(tts->resampler_input);
	free(tts->resampler_output);
	free(tts->resampled_buffer);
	tts->wave_buffer = NULL;
	tts->samples = NULL;
	tts->resampler_input = NULL;
	tts->resampler_output = NULL;
	tts->resampled_buffer = NULL;
	tts->consumer = NULL;
	free(tts);
}

NEWFON_EXPORT void tts_speak(const TTS_t *tts, const newfon_conf_t *config, const char *text) {
	newfon_transfer(config, text, tts->wave_buffer, WAVE_SIZE, audio_callback, (void*)tts);
	flushResampler((TTS_t*)tts);
}

NEWFON_EXPORT void tts_setVolume(TTS_t *tts, float volume) {
	if (volume < 0.0f) {
		volume = 0.0f;
	} else if (volume > 1.0f) {
		volume = 1.0f;
	}
	tts->volume = volume;
}

NEWFON_EXPORT int tts_setInterpolation(TTS_t *tts, int multiplier, int algorithm) {
	if (tts == NULL) {
		return FAILURE;
	}

	multiplier = normalizeInterpolationMultiplier(multiplier);
	algorithm = algorithm <= 0 ? 0 : 1;
	if (
		tts->interpolation_multiplier == multiplier &&
		tts->interpolation_algorithm == algorithm &&
		(multiplier == 1 || tts->converter != NULL)
	) {
		return SUCCESS;
	}

	SRC_STATE *newConverter = NULL;
	if (multiplier != 1) {
		int error = 0;
		newConverter = src_new(interpolationConverterType(algorithm), NUM_CHANNELS, &error);
		if (newConverter == NULL || error != 0) {
			if (newConverter != NULL) {
				src_delete(newConverter);
			}
			return FAILURE;
		}
	}

	if (tts->converter != NULL) {
		src_delete(tts->converter);
	}
	tts->converter = newConverter;
	tts->interpolation_multiplier = multiplier;
	tts->interpolation_algorithm = algorithm;
	return SUCCESS;
}
