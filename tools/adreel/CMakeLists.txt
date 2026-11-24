cmake_minimum_required(VERSION 3.22)

# ArtFreqAdReel: films the real ArtFreq / ArtFreq FX plug-in window while the real processor
# plays, for the ad in this repository. It compiles the plug-in's own sources from a checkout of
# the plug-in (never copied into this repository, never modified) and adds one file, AdReel.cpp.
#
#   cmake -S tools/adreel -B <build-dir> -G Ninja -DCMAKE_BUILD_TYPE=Release \
#         -DADREEL_ARTFREQ_DIR=<ArtFreq-plug-in checkout> -DADREEL_JUCE_DIR=<JUCE 8.0.15 checkout>
#   cmake --build <build-dir> --target ArtFreqAdReel

project(ArtFreqAdReel VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

set(ADREEL_ARTFREQ_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../ArtFreq-plug-in" CACHE PATH "ArtFreq plug-in checkout (read only)")
set(ADREEL_JUCE_DIR    "${CMAKE_CURRENT_SOURCE_DIR}/../../../deps/JUCE"       CACHE PATH "JUCE checkout (the tag the plug-in pins)")

if(NOT EXISTS "${ADREEL_ARTFREQ_DIR}/tools/DemoReel.cpp")
    message(FATAL_ERROR "ADREEL_ARTFREQ_DIR (${ADREEL_ARTFREQ_DIR}) is not an ArtFreq plug-in checkout")
endif()

add_subdirectory("${ADREEL_JUCE_DIR}" "${CMAKE_BINARY_DIR}/juce" EXCLUDE_FROM_ALL)

# The plug-in's version (saved in its state, shown in its Settings): read from its CMakeLists.
file(STRINGS "${ADREEL_ARTFREQ_DIR}/CMakeLists.txt" ADREEL_PROJECT_LINE REGEX "^project\\(ArtFreq VERSION ")
string(REGEX REPLACE "^project\\(ArtFreq VERSION ([0-9.]+).*$" "\\1" ADREEL_ARTFREQ_VERSION "${ADREEL_PROJECT_LINE}")
if(NOT ADREEL_ARTFREQ_VERSION MATCHES "^[0-9]+\\.[0-9]+\\.[0-9]+$")
    message(FATAL_ERROR "Could not read ArtFreq's version from ${ADREEL_ARTFREQ_DIR}/CMakeLists.txt")
endif()
message(STATUS "Filming ArtFreq ${ADREEL_ARTFREQ_VERSION} from ${ADREEL_ARTFREQ_DIR}")

file(GLOB_RECURSE ARTFREQ_CORE_SOURCES    CONFIGURE_DEPENDS "${ADREEL_ARTFREQ_DIR}/src/core/*.cpp")
file(GLOB_RECURSE ARTFREQ_DSP_SOURCES     CONFIGURE_DEPENDS "${ADREEL_ARTFREQ_DIR}/src/dsp/*.cpp")
file(GLOB_RECURSE ARTFREQ_UI_SOURCES      CONFIGURE_DEPENDS "${ADREEL_ARTFREQ_DIR}/src/ui/*.cpp")
file(GLOB         ARTFREQ_LICENSE_SOURCES CONFIGURE_DEPENDS "${ADREEL_ARTFREQ_DIR}/src/license/*.cpp")
file(GLOB         ARTFREQ_FONT_ASSETS     CONFIGURE_DEPENDS "${ADREEL_ARTFREQ_DIR}/assets/fonts/*.ttf")

# The names must stay: the plug-in's src/core/Fonts.cpp includes "ArtFreqAssets.h".
juce_add_binary_data(ArtFreqAssets
    HEADER_NAME ArtFreqAssets.h
    NAMESPACE   ArtFreqAssets
    SOURCES     ${ARTFREQ_FONT_ASSETS})

juce_add_console_app(ArtFreqAdReel PRODUCT_NAME "ArtFreqAdReel")

target_sources(ArtFreqAdReel PRIVATE
    AdReel.cpp
    "${ADREEL_ARTFREQ_DIR}/src/PluginProcessor.cpp"
    "${ADREEL_ARTFREQ_DIR}/src/Parameters.cpp"
    ${ARTFREQ_LICENSE_SOURCES}
    ${ARTFREQ_CORE_SOURCES}
    ${ARTFREQ_DSP_SOURCES}
    ${ARTFREQ_UI_SOURCES})

# src and tests as the plug-in's own tools have them (tests/ for LicenseTestSupport.h: every
# instance is activated against a fake licence server, so nothing reaches the real one); the
# checkout's root so AdReel.cpp can include tools/DemoReel.cpp where it lies.
target_include_directories(ArtFreqAdReel PRIVATE
    "${ADREEL_ARTFREQ_DIR}/src"
    "${ADREEL_ARTFREQ_DIR}/tests"
    "${ADREEL_ARTFREQ_DIR}")

target_compile_definitions(ArtFreqAdReel PRIVATE
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_VST3_CAN_REPLACE_VST2=0
    JUCE_DISPLAY_SPLASH_SCREEN=0
    JUCE_REPORT_APP_USAGE=0
    JUCE_STRICT_REFCOUNTEDPOINTER=1
    ARTFREQ_VERSION_STRING="${ADREEL_ARTFREQ_VERSION}"
    JucePlugin_Name="ArtFreq"
    JucePlugin_IsSynth=1
    JucePlugin_WantsMidiInput=1
    JucePlugin_ProducesMidiOutput=0
    JucePlugin_IsMidiEffect=0
    JucePlugin_EditorRequiresKeyboardFocus=1
    JucePlugin_VersionString="${ADREEL_ARTFREQ_VERSION}"
    JUCE_MODAL_LOOPS_PERMITTED=1)

target_link_libraries(ArtFreqAdReel
    PRIVATE
        ArtFreqAssets
        juce::juce_audio_processors
        juce::juce_audio_formats
        juce::juce_audio_utils
        juce::juce_dsp
        juce::juce_gui_basics
        juce::juce_gui_extra
        juce::juce_cryptography
    PUBLIC
        juce::juce_recommended_config_flags)
