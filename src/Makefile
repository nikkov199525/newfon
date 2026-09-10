# Makefile of Newfon for NVDA
#
# Copyright (C) 2023 - 2026 Александр Линьков <kvark128@yandex.ru>

ARCH = x86
TARGET = i686-w64-mingw32
CC = clang
DEPS_DIR = $(CURDIR)/.deps

ifeq ($(ARCH), x64)
TARGET = x86_64-w64-mingw32
endif


RULEX_DEFS = -DPCRE2_STATIC
ifneq ($(ARCH), x64)
RULEX_DEFS += -DMDB_VL32
endif

TARGET_CC = $(TARGET)-$(CC)
TARGET_DEPS_DIR = $(DEPS_DIR)/$(TARGET)

WITH_X86 = yes
WITH_X64 = yes
WITH_RULEX = yes


MSGFMT = python -B msgfmt.py
ZIP = 7z

CFLAGS = -Wall -Wextra -Werror -Wno-unused-parameter -Wno-unused-label -Wno-unused-but-set-variable -Wno-logical-op-parentheses -Wno-sign-compare -Wno-implicit-fallthrough -Wno-incompatible-pointer-types -Wno-int-conversion -Wno-unknown-pragmas -O3
LDFLAGS = -static -s
SAMPLERATE_FLAGS = -DHAVE_LRINT=1 -DHAVE_LRINTF=1
RULEX_LIBS = -lpthread -lpcre2-posix -lpcre2-8
CORE_OBJS = utterance.o transcription.o time_planner.o text2speech.o synth.o speechrate_control.o soundproducer.o sink.o numerics.o male.o intonator.o female.o voices.o
LEXHOLDER_X64 = $(DEPS_DIR)/bin/lexholder-x64.exe
DOC_FILES = doc/ru/readme.html
PO_FILES = $(wildcard locale/*/LC_MESSAGES/nvda.po)
MO_FILES = $(addsuffix .mo, $(basename $(PO_FILES)))
MANIFESTS = manifest.ini $(wildcard locale/*/manifest.ini)
SYNTH_DIR = synthDrivers/newfon
TARGET_LIB_DIR = $(SYNTH_DIR)/lib/$(ARCH)
TARGET_LIBS =
PY_FILES = $(wildcard $(SYNTH_DIR)/*.py) $(wildcard $(SYNTH_DIR)/languages/*.py)
LICENSES = $(wildcard $(SYNTH_DIR)/LICENSES/*.txt) $(SYNTH_DIR)/COPYING.txt
ADDON_FILES = $(TARGET_LIBS) config.spec $(MANIFESTS) $(PY_FILES) $(PO_FILES) $(MO_FILES) $(LICENSES) $(DOC_FILES)

CORE_DIR = ../Newfon_core
CORE_SOURCES = $(wildcard ../Newfon_core/src/*.c) $(wildcard ../Newfon_core/src/*.h) $(wildcard ../Newfon_core/include/*.h)
WRAPPER_SOURCES = $(SYNTH_DIR)/newfon_nvda.c $(SYNTH_DIR)/newfon_nvda.h $(SYNTH_DIR)/newfon.def
RULEX_SOURCES = $(SYNTH_DIR)/access_utf8.c $(SYNTH_DIR)/rulex.def $(wildcard ../external/rulex/src/*.c)
EXT_DIR = ../external
LEXICON_DIR = $(EXT_DIR)/rulex/data
LEXICON_DATA = $(addprefix $(LEXICON_DIR)/, explicit.dict implicit.dict general.rules lexicon.rules prefix.rules correction.rules)
VPATH = $(CORE_DIR)/src $(CORE_DIR)/include $(EXT_DIR)/libsamplerate $(EXT_DIR)/rulex/src $(EXT_DIR)/lmdb/libraries/liblmdb $(SYNTH_DIR) $(TARGET_LIB_DIR)
export SOURCE_DATE_EPOCH = 0

ifeq ($(WITH_X86),yes)
override TARGET_LIBS += $(SYNTH_DIR)/lib/x86/newfon.dll
endif

ifeq ($(WITH_X64),yes)
override TARGET_LIBS += $(SYNTH_DIR)/lib/x64/newfon.dll
endif

ifeq ($(WITH_RULEX),yes)
override ADDON_FILES += $(SYNTH_DIR)/rulex.db
ifeq ($(WITH_X86),yes)
override TARGET_LIBS += $(SYNTH_DIR)/lib/x86/rulex.dll
endif
ifeq ($(WITH_X64),yes)
override TARGET_LIBS += $(SYNTH_DIR)/lib/x64/rulex.dll
endif
endif

all: newfon.nvda-addon

# У целей ниже перечислены исходники, иначе правка ядра не приводила бы
# к пересборке уже собранной библиотеки
$(SYNTH_DIR)/lib/%/newfon.dll: $(CORE_SOURCES) $(WRAPPER_SOURCES)
	mkdir -p $(dir $@)
	$(MAKE) ARCH=$(notdir $(@D)) newfon-dll

$(SYNTH_DIR)/lib/%/rulex.dll: $(RULEX_SOURCES)
	mkdir -p $(dir $@)
	$(MAKE) ARCH=$(notdir $(@D)) rulex-dll

pot: newfon.pot

.PHONY .SILENT: clean
clean:
	rm -f *.nvda-addon *.pot
	rm -rf ./doc
	rm -rf $(SYNTH_DIR)/lib
	rm -f $(SYNTH_DIR)/*.db
	rm -f $(MO_FILES)

.PHONY .SILENT: clean-all
clean-all: clean
	rm -rf $(DEPS_DIR)

%.o: %.c
	$(TARGET_CC) -DUNICODE -D_UNICODE $(SAMPLERATE_FLAGS) $(CFLAGS) $(addprefix -I,$(CORE_DIR)/include $(EXT_DIR)/libsamplerate $(TARGET_DEPS_DIR)/include) -o $(TARGET_LIB_DIR)/$@ -c $<

%.mo: %.po
	$(MSGFMT) -o $@ $<

newfon.pot: $(PY_FILES)
	xgettext --package-name newfon -o $@ $^

doc/ru/readme.html: ../readme.md
	mkdir -p $(dir $@)
	python -B md2html.py $< $@ ru

$(DEPS_DIR)/%/done:
	$(MAKE) PREFIX="$(DEPS_DIR)/$*" CC=$*-$(CC) SRC_DIR="$(CURDIR)/$(EXT_DIR)/pcre2" CMAKE_SYSTEM_NAME=Windows -f pcre2.mk
	touch $@

# lexholder, наполняющий базу, собирается 64-разрядным, см. LEXHOLDER_X64
define build_lexholder
	mkdir -p $(dir $@)
	$(1)-$(CC) $(CFLAGS) -DPCRE2_STATIC -I$(EXT_DIR)/lmdb/libraries/liblmdb -I$(DEPS_DIR)/$(1)/include -o $@ $(filter %.c,$^) -L$(DEPS_DIR)/$(1)/lib $(LDFLAGS) $(RULEX_LIBS)
endef

LEXHOLDER_SOURCES = access_utf8.c lexholder.c lexdb.c coder.c mdb.c midl.c module.c

$(LEXHOLDER_X64): $(LEXHOLDER_SOURCES) $(DEPS_DIR)/x86_64-w64-mingw32/done
	$(call build_lexholder,x86_64-w64-mingw32)

.PHONY: newfon-dll
newfon-dll: newfon_nvda.o samplerate.o src_linear.o src_zoh.o $(CORE_OBJS)
	$(TARGET_CC) -shared -o $(TARGET_LIB_DIR)/newfon.dll $(SYNTH_DIR)/newfon.def $(addprefix $(TARGET_LIB_DIR)/, $(^F)) $(LDFLAGS)

.PHONY: rulex-dll
rulex-dll: access_utf8.c lexdb.c coder.c mdb.c midl.c module.c $(TARGET_DEPS_DIR)/done
	$(TARGET_CC) $(CFLAGS) $(RULEX_DEFS) -I$(EXT_DIR)/lmdb/libraries/liblmdb -I$(TARGET_DEPS_DIR)/include -shared -o $(TARGET_LIB_DIR)/rulex.dll $(SYNTH_DIR)/rulex.def $(filter %.c,$^) -L$(TARGET_DEPS_DIR)/lib $(LDFLAGS) $(RULEX_LIBS)

define build_lexicon
	@rm -f $@
	@echo "Inserting explicit dictionary:"
	$(1) -f $(LEXICON_DIR)/explicit.dict -X $@
	@echo "Inserting implicit dictionary:"
	$(1) -f $(LEXICON_DIR)/implicit.dict -M $@
	@echo "Inserting lexical classifiers:"
	$(1) -f $(LEXICON_DIR)/lexicon.rules -L $@
	@echo "Inserting general rules:"
	$(1) -f $(LEXICON_DIR)/general.rules -G $@
	@echo "Inserting prefix rules:"
	$(1) -f $(LEXICON_DIR)/prefix.rules -P $@
	@echo "Inserting correction rules:"
	$(1) -f $(LEXICON_DIR)/correction.rules -C $@
endef

$(SYNTH_DIR)/rulex.db: $(LEXHOLDER_X64) $(LEXICON_DATA)
	$(call build_lexicon,$(LEXHOLDER_X64))

newfon.nvda-addon: $(ADDON_FILES)
	$(ZIP) a -tzip -mx=7 -m0=LZMA $@ $^

synth.o: synth.c synth.h transcription.h soundscript.h voice.h newfon_core.h
numerics.o: numerics.c numerics.h transcription.h sink.h synth.h newfon_core.h
transcription.o: transcription.c transcription.h numerics.h sink.h
utterance.o: utterance.c soundscript.h transcription.h
time_planner.o: time_planner.c soundscript.h transcription.h
speechrate_control.o: speechrate_control.c timing.h soundscript.h transcription.h newfon_core.h
intonator.o: intonator.c transcription.h soundscript.h modulation.h voice.h
soundproducer.o: soundproducer.c sink.h soundscript.h voice.h
sink.o: sink.c sink.h newfon_core.h
male.o: male.c voice.h
female.o: female.c voice.h
voices.o: voices.c voice.h
text2speech.o: text2speech.c newfon_core.h sink.h transcription.h synth.h timing.h modulation.h voice.h
samplerate.o: samplerate.c samplerate.h common.h float_cast.h config.h
src_linear.o: src_linear.c samplerate.h common.h float_cast.h config.h
src_zoh.o: src_zoh.c samplerate.h common.h float_cast.h config.h
newfon_nvda.o: newfon_nvda.c newfon_nvda.h
