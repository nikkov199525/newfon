# Copyright (C) 2024 - 2026 Александр Линьков <kvark128@yandex.ru>

BUILD_DIR := $(PREFIX)/.build/pcre2

all: $(BUILD_DIR)/Makefile
	cd $(BUILD_DIR) && $(MAKE) && $(MAKE) install

$(BUILD_DIR)/Makefile:
	mkdir -p $(BUILD_DIR) && cd $(BUILD_DIR) && \
	cmake -DCMAKE_INSTALL_PREFIX=$(PREFIX) \
	-DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=$(CC) \
	-DCMAKE_MAKE_PROGRAM="$(MAKE)" \
	$(if $(CMAKE_SYSTEM_NAME),-DCMAKE_SYSTEM_NAME=$(CMAKE_SYSTEM_NAME)) \
	-DPCRE2_BUILD_PCRE2GREP=OFF -DPCRE2_BUILD_TESTS=OFF $(SRC_DIR) -G "Unix Makefiles"
