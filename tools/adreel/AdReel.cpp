// ArtFreqAdReel: films the takes of the ad from the real plug-in.
//
//   ArtFreqAdReel <output-dir> [--takes hook,type,draw,picture,fx,still] [--scale 4]
//
// Nothing in a take is mocked up. Each one opens the plug-in's own editor (ArtFreq's, or ArtFreq
// FX's) on the plug-in's own processor and films it offline, frame by frame, the way the
// plug-in's tools/DemoReel.cpp films the clips on anymeansaudio.com:
//
//   - The host is this tool: 48 kHz, 30 pictures a second, so 1600 samples of sound per picture,
//     in blocks of at most 400 samples, with a transport that is stopped and then plays from
//     bar 1. ArtFreq FX gets a song as its input (DemoReel's own test song); the instrument
//     gets nothing.
//   - After each picture's sound, the live view takes the analysis of what came out (its own
//     timer callback, called once per picture, so no column is dropped or shown twice), then
//     the window is drawn with createComponentSnapshot.
//   - The sound of a take is the processor's output for those same blocks, untouched:
//     picture i belongs to samples [1600 i, 1600 (i + 1)).
//   - Drawings are made the way a user makes them: "Add text" and typing into the text box,
//     the brush dragged over the canvas, a picture file dropped on the canvas.
//
// Per take it writes <name>.mkv (every picture, lossless, the whole window at --scale pixels per
// point), <name>.wav (32-bit float stereo) and <name>.json (sizes, the pictures at which things
// happen, and where the parts of the window are, in pixels of the picture).
//
// The plug-in's sources are compiled from a checkout of the plug-in (see CMakeLists.txt), and
// tools/DemoReel.cpp is included as it lies there, for its test song, its picture and its
// helpers. The way a take is filmed (the block loop, the live view's timer, the snapshot) follows
// DemoReel.cpp, and a few helper lines here are adapted from it and from tools/Snapshot.cpp.
// ArtFreq is AGPL-3.0, and so is this file.
//
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Run it under a virtual display large enough for the window (the live view runs only while
// its window is on screen):
//
//   xvfb-run -a -s "-screen 0 2400x1600x24" ArtFreqAdReel takes

// DemoReel.cpp is a program of its own: its main is renamed, everything else (in an unnamed
// namespace) becomes part of this file.
#define main artFreqDemoReelMain
#include "tools/DemoReel.cpp"
#undef main

#include "ui/ShellToolbar.h"

#include <functional>
#include <map>

namespace
{

float shotScale = 4.0f;   // pixels of the picture per point of the window
float hookDCeiling = -30.0f; // ad D: the Levels ceiling (dBFS) of the analyser view

//==============================================================================
/** The DAW's transport, as a take sets it for each block. */
struct AdTransport final : public juce::AudioPlayHead
{
    juce::Optional<PositionInfo> getPosition() const override { return info; }

    void set (bool playing, double bpm, int64_t songSample)
    {
        const auto seconds = static_cast<double> (songSample) / sampleRate;
        const auto ppq = seconds * bpm / 60.0;

        info = {};
        info.setIsPlaying (playing);
        info.setBpm (bpm);
        info.setTimeSignature (juce::AudioPlayHead::TimeSignature { 4, 4 });
        info.setTimeInSamples (songSample);
        info.setTimeInSeconds (seconds);
        info.setPpqPosition (ppq);
        info.setPpqPositionOfLastBarStart (std::floor (ppq / 4.0) * 4.0);
    }

    PositionInfo info;
};

/** A mouse event for a component, delivered straight to it (no pointer is ever in a picture). */
juce::MouseEvent mouseEventAt (juce::Component& c, juce::Point<float> position, juce::Point<float> downPosition,
                               juce::ModifierKeys mods, bool dragged = false)
{
    const auto now = juce::Time::getCurrentTime();
    return { juce::Desktop::getInstance().getMainMouseSource(), position, mods, juce::MouseInputSource::defaultPressure,
             0.0f, 0.0f, 0.0f, 0.0f, &c, &c, now, downPosition, now, 1, dragged };
}

template <typename Type>
Type* findPart (juce::Component& root, const juce::String& id)
{
    auto* c = dynamic_cast<Type*> (findComponentWithId (root, id));
    check (c != nullptr, "the window has its '" + id + "'");
    return c;
}

//==============================================================================
/** One filmed take: a processor, its window, the DAW, and where the pictures and the sound go. */
struct Take
{
    Take (const juce::String& nameToUse, bool effect, const std::function<void (ArtFreqProcessor&)>& configure,
          const juce::File& outputDirToUse, const ArtDocument& drawing = {})
        : name (nameToUse), outputDir (outputDirToUse)
    {
        std::cout << "== " << name << std::endl;
        const auto variant = effect ? ArtFreqProcessor::Variant::effect : ArtFreqProcessor::Variant::instrument;

        // A drawing given here arrives as a saved state, as when a project opens.
        juce::MemoryBlock state;
        {
            ArtFreqProcessor source (variant);
            source.setDocument (drawing);
            source.rebuildPlanIfNeeded();
            source.getStateInformation (state);
        }

        processor = std::make_unique<ArtFreqProcessor> (variant);
        processor->setPlayConfigDetails (effect ? 2 : 0, 2, sampleRate, maxBlockSize);
        processor->setStateInformation (state.getData(), static_cast<int> (state.getSize()));

        if (configure != nullptr)
            configure (*processor);

        processor->prepareToPlay (sampleRate, maxBlockSize);
        processor->rebuildPlanIfNeeded();
        processor->setPlayHead (&transport);
        check (processor->isLicensed(), name + ": the plug-in is activated (test licensing)");

        editor.reset (dynamic_cast<ArtFreqEditor*> (processor->createEditor()));

        if (editor == nullptr)
        {
            check (false, name + ": the processor makes an ArtFreqEditor");
            return;
        }

        // Not on a screen yet, as in the plug-in's snapshot tool: the canvas then shows its
        // measured preview ("Preview of the real sound") when settle() asks for it, not at a
        // moment of its own. showLive() puts the window on the (virtual) screen, which the live
        // view needs.
        pump (150);
        processor->rebuildPlanIfNeeded();
        pump (60);

        content = findComponentWithId (*editor, "content");
        canvas = findPart<ui::CanvasView> (*editor, "canvas");
        liveView = findPart<ui::LiveView> (*editor, "live-view");
        canvas->setFastPreviewMadeWhilePainting (true);

        if (auto* activation = findComponentWithId (*editor, "activation"))
            check (! activation->isShowing(), name + ": no licence screen");

        width = juce::roundToInt (static_cast<float> (editor->getWidth()) * shotScale);
        height = juce::roundToInt (static_cast<float> (editor->getHeight()) * shotScale);

        pipe = openVideo (name, width, height);
    }

    ~Take()
    {
        if (pipe != nullptr)
            check (pclose (pipe) == 0, name + ": ffmpeg wrote the pictures");

        for (auto& camera : cameras)
            if (camera.pipe != nullptr)
                check (pclose (camera.pipe) == 0, camera.name + ": ffmpeg wrote the pictures");

        check (output[0].size() == static_cast<size_t> (frames) * samplesPerFrame, name + ": a picture's sound for every picture");
        const auto peak = peakOf (output);
        check (peak < 1.0f, name + ": the output does not clip");
        check (writeWav (output, outputDir.getChildFile (name + ".wav")), name + ": write the sound");

        if (! input[0].empty())
        {
            // The song as it went in, on the take's own clock (silence until the DAW plays).
            Stereo in;

            for (size_t channel = 0; channel < 2; ++channel)
            {
                in[channel].assign (output[channel].size(), 0.0f);

                for (size_t i = 0; i < in[channel].size(); ++i)
                    if (static_cast<int64_t> (i) >= playStart && i - static_cast<size_t> (playStart) < input[channel].size())
                        in[channel][i] = input[channel][i - static_cast<size_t> (playStart)];
            }

            check (writeWav (in, outputDir.getChildFile (name + "-input.wav")), name + ": write the input");
        }

        writeJson (peak);
        std::cout << "  " << frames << " pictures (" << frames / static_cast<double> (framesPerSecond) << " s), "
                  << width << " x " << height << ", output peak " << juce::Decibels::gainToDecibels (peak) << " dBFS" << std::endl;

        if (processor != nullptr)
            processor->setPlayHead (nullptr);

        if (editor != nullptr && editor->isOnDesktop())
            editor->removeFromDesktop();

        pump (50);
        editor.reset();
    }

    //==========================================================================
    /** Remembers the next picture's number under a name (for the edit). */
    void mark (const juce::String& what)   { marks[what] = frames; }

    /** Where a part of the window is, in pixels of the picture. */
    juce::Rectangle<int> pixelsOf (juce::Component& part, juce::Rectangle<float> local) const
    {
        return (editor->getLocalArea (&part, local.toNearestInt()).toFloat() * shotScale).toNearestInt();
    }

    /** Notes where the parts of the window are now, under names starting with `prefix`. */
    void noteRects (const juce::String& prefix = {})
    {
        rects[prefix + "window"] = { 0, 0, width, height };
        rects[prefix + "canvas-plot"] = pixelsOf (*canvas, canvas->getDrawingArea());
        rects[prefix + "live-plot"] = pixelsOf (*liveView, ui::axes::plotArea (liveView->getLocalBounds(), ui::CanvasView::axisWidth,
                                                                              ui::CanvasView::axisHeight).toFloat());

        for (const auto* id : { "header", "toolbar", "canvas", "live-view", "inspector", "footer", "view-switch", "add-text", "add-image",
                                "inspector-text", "inspector-font", "inspector-style", "inspector-band", "inspector-mode", "layer-list",
                                "length", "repeat", "density", "contrast", "level", "preview", "mode", "depth", "live", "layers",
                                "sound-strip", "brush-strip", "tool-select", "tool-brush", "tool-erase" })
            if (auto* part = findComponentWithId (*editor, id))
                if (part->isShowing() || ! editor->isOnDesktop())
                    if (part->isVisible() && ! part->getBounds().isEmpty())
                        rects[prefix + id] = pixelsOf (*part, part->getLocalBounds().toFloat());
    }

    /** Over to the live view, with the window on the (virtual) screen and away from the mouse:
        the live view runs (and turns the processor's analyser on) only while it is showing. */
    void showLive()
    {
        editor->showLiveView (true);

        if (! editor->isOnDesktop())
        {
            editor->setTopLeftPosition (0, 0);
            editor->addToDesktop (0);
            editor->setVisible (true);
            juce::Desktop::setMousePosition ({ 4000, 4000 });
            pump (200);   // (well under 0.3 s: after that the view would scroll silence by the clock)
        }

        check (editor->isShowing(), name + ": the window is on screen");
        check (! editor->getScreenBounds().contains (juce::Desktop::getMousePosition()), name + ": the mouse is not over the window");
        check (processor->getAnalyzer().isActive(), name + ": the live view turns the analyser on");
        mark ("live");
    }

    /** The canvas's measured preview of what is drawn now ("Preview of the real sound"), at once. */
    void settle()
    {
        processor->rebuildPlanIfNeeded();
        pump (40);
        canvas->settleMeasuredPreview (shotScale);
    }

    /** The DAW starts playing (from bar 1), `delaySamples` into the next picture's sound. */
    void pressPlay (int delaySamples = 0)
    {
        playStart = static_cast<int64_t> (frames) * samplesPerFrame + delaySamples;
        mark ("play");
    }

    /** One picture's sound through the processor, the transport following. Blocks are 400
        samples, cut where the DAW starts so that it starts on the sample. */
    void play()
    {
        const auto frameStart = static_cast<int64_t> (frames) * samplesPerFrame;
        auto done = 0;

        while (done < samplesPerFrame)
        {
            const auto position = frameStart + done;
            auto length = juce::jmin (blockSize, samplesPerFrame - done);

            if (playStart > position && playStart < position + length)
                length = static_cast<int> (playStart - position);

            const auto playing = playStart >= 0 && position >= playStart;
            const auto songSample = playing ? position - playStart : 0;
            transport.set (playing, bpm, songSample);

            juce::AudioBuffer<float> buffer (2, length);
            buffer.clear();

            if (processor->isEffect() && playing)
                for (int i = 0; i < length; ++i)
                {
                    const auto index = static_cast<size_t> (songSample + i);

                    if (index < input[0].size())
                    {
                        buffer.setSample (0, i, input[0][index]);
                        buffer.setSample (1, i, input[1][index]);
                    }
                }

            juce::MidiBuffer midi;
            processor->processBlock (buffer, midi);

            for (size_t channel = 0; channel < 2; ++channel)
                output[channel].insert (output[channel].end(), buffer.getReadPointer (static_cast<int> (channel)),
                                        buffer.getReadPointer (static_cast<int> (channel)) + length);

            done += length;
        }
    }

    /** One picture: its sound, then the window as it then is. */
    void film()
    {
        if (editor == nullptr)
            return;

        play();

        const auto live = liveView->isVisible();

        if (live)
        {
            // The live view's own timer callback (a private base, hence the cast), once per
            // picture: every analysed column is taken, none dropped, none twice.
            ((juce::Timer*) liveView)->timerCallback();
            check (processor->getAnalyzer().process ({}) == 0, name + ": picture " + juce::String (frames) + " left analysis behind");
        }

        // A drawing or a setting changed since the last picture: the plan follows now, not when
        // the processor's own timer happens to run (which would differ from run to run).
        processor->rebuildPlanIfNeeded();
        pump (45);

        if (live)
            liveView->resized();   // its picture redrawn from the columns at the snapshot's scale

        if (writeMain)
        {
            if (mainFirst < 0)
                mainFirst = frames;

            const auto image = editor->createComponentSnapshot (editor->getLocalBounds(), true, shotScale);
            check (image.getWidth() == width && image.getHeight() == height, name + ": picture size");
            writePicture (image, pipe, width, height);
        }

        // Further cameras: a part of the window at a scale of its own, over a range of pictures.
        for (auto& camera : cameras)
        {
            if (frames < camera.first || frames > camera.last)
                continue;

            if (camera.pipe == nullptr)
                camera.pipe = openVideo (camera.name, camera.width, camera.height);

            const auto image = editor->createComponentSnapshot (camera.area, true, camera.scale);
            check (image.getWidth() == camera.width && image.getHeight() == camera.height, camera.name + ": picture size");
            writePicture (image, camera.pipe, camera.width, camera.height);
            ++camera.written;
        }

        ++frames;
    }

    /** One picture's sound and the live view's columns, with no picture taken (a stretch the
        edit does not use, played so that the clock and the live view's history are whole). */
    void advance (int numFrames)
    {
        for (int i = 0; i < numFrames && editor != nullptr; ++i)
        {
            play();

            if (liveView->isVisible())
            {
                ((juce::Timer*) liveView)->timerCallback();
                check (processor->getAnalyzer().process ({}) == 0, name + ": picture " + juce::String (frames) + " left analysis behind");
            }

            processor->rebuildPlanIfNeeded();
            ++frames;
        }
    }

    /** The pixels of a snapshot, row by row (opaque: the window covers itself, so the
        premultiplied colour is the colour; JUCE keeps them as B, G, R (, A) in memory). */
    void writePicture (const juce::Image& image, FILE* to, int w, int h)
    {
        const juce::Image::BitmapData data (image, juce::Image::BitmapData::readOnly);
        check (data.pixelStride == 3 || data.pixelStride == 4, name + ": 24- or 32-bit pictures");
        std::vector<uint8_t> row (static_cast<size_t> (w) * 4, 255);

        for (int y = 0; y < h && to != nullptr; ++y)
        {
            const auto* in = data.getLinePointer (y);

            for (int x = 0; x < w; ++x, in += data.pixelStride)
            {
                auto* out = row.data() + static_cast<size_t> (x) * 4;
                out[0] = in[0];
                out[1] = in[1];
                out[2] = in[2];
            }

            if (std::fwrite (row.data(), 1, row.size(), to) != row.size())
            {
                check (false, name + ": ffmpeg took the pictures");
                break;
            }
        }
    }

    FILE* openVideo (const juce::String& videoName, int w, int h)
    {
        const auto video = outputDir.getChildFile (videoName + ".mkv");
        video.deleteFile();
        const auto command = "ffmpeg -hide_banner -loglevel error -y -f rawvideo -pix_fmt bgr0 -s "
                           + juce::String (w) + "x" + juce::String (h) + " -framerate " + juce::String (framesPerSecond)
                           + " -i - -c:v libx264rgb -qp 0 -preset ultrafast " + video.getFullPathName().quoted();
        auto* opened = popen (command.toRawUTF8(), "w");
        check (opened != nullptr, videoName + ": start ffmpeg");
        return opened;
    }

    /** A camera on `area` (points of the window) at `scale` pixels a point, filming pictures
        `first` to `last` of the take into <take>-<cameraName>.mkv. */
    void addCamera (const juce::String& cameraName, juce::Rectangle<int> area, float scale, int first, int last)
    {
        Camera camera;
        camera.name = name + "-" + cameraName;
        camera.area = area;
        camera.scale = scale;
        camera.first = first;
        camera.last = last;
        camera.width = juce::roundToInt (static_cast<float> (area.getWidth()) * scale);
        camera.height = juce::roundToInt (static_cast<float> (area.getHeight()) * scale);
        cameras.push_back (camera);
    }

    void film (int numFrames)
    {
        for (int i = 0; i < numFrames; ++i)
            film();
    }

    void filmSeconds (double seconds)   { film (juce::roundToInt (seconds * framesPerSecond)); }

    //==========================================================================
    void writeJson (float peak) const
    {
        juce::DynamicObject::Ptr root (new juce::DynamicObject());
        root->setProperty ("name", name);
        root->setProperty ("plugin", processor->isEffect() ? "ArtFreq FX" : "ArtFreq");
        root->setProperty ("pluginVersion", ARTFREQ_VERSION_STRING);
        root->setProperty ("fps", framesPerSecond);
        root->setProperty ("sampleRate", sampleRate);
        root->setProperty ("samplesPerFrame", samplesPerFrame);
        root->setProperty ("scale", shotScale);
        root->setProperty ("width", width);
        root->setProperty ("height", height);
        root->setProperty ("frames", frames);
        root->setProperty ("bpm", bpm);
        root->setProperty ("playStartSample", static_cast<juce::int64> (playStart));
        root->setProperty ("latencySamples", processor->getLatencySamples());
        root->setProperty ("liveSeconds", liveView != nullptr ? liveView->getVisibleSeconds() : 0.0);
        root->setProperty ("peak", peak);

        juce::DynamicObject::Ptr markObject (new juce::DynamicObject());

        for (const auto& m : marks)
            markObject->setProperty (m.first, m.second);

        root->setProperty ("marks", markObject.get());

        juce::DynamicObject::Ptr rectObject (new juce::DynamicObject());

        for (const auto& r : rects)
            rectObject->setProperty (r.first, juce::Array<juce::var> { r.second.getX(), r.second.getY(), r.second.getWidth(), r.second.getHeight() });

        root->setProperty ("rects", rectObject.get());
        root->setProperty ("mainFirst", mainFirst);

        juce::DynamicObject::Ptr cameraObject (new juce::DynamicObject());

        for (const auto& c : cameras)
        {
            juce::DynamicObject::Ptr one (new juce::DynamicObject());
            one->setProperty ("area", juce::Array<juce::var> { c.area.getX(), c.area.getY(), c.area.getWidth(), c.area.getHeight() });
            one->setProperty ("scale", c.scale);
            one->setProperty ("first", c.first);
            one->setProperty ("written", c.written);
            one->setProperty ("width", c.width);
            one->setProperty ("height", c.height);
            cameraObject->setProperty (c.name, one.get());
        }

        root->setProperty ("cameras", cameraObject.get());
        outputDir.getChildFile (name + ".json").replaceWithText (juce::JSON::toString (juce::var (root.get())));
    }

    juce::String name;
    juce::File outputDir;
    std::unique_ptr<ArtFreqProcessor> processor;
    std::unique_ptr<ArtFreqEditor> editor;
    juce::Component* content = nullptr;
    ui::CanvasView* canvas = nullptr;
    ui::LiveView* liveView = nullptr;
    AdTransport transport;

    double bpm = 120.0;
    int64_t playStart = -1;   // the take's sample at which the DAW starts playing (-1: stopped)
    Stereo input;             // ArtFreq FX: the song going in, from where the DAW starts
    Stereo output;            // what came out

    std::map<juce::String, int> marks;
    std::map<juce::String, juce::Rectangle<int>> rects;
    int width = 0, height = 0, frames = 0;
    FILE* pipe = nullptr;

    struct Camera
    {
        juce::String name;
        juce::Rectangle<int> area;
        float scale = 1.0f;
        int first = 0, last = 0, written = 0, width = 0, height = 0;
        FILE* pipe = nullptr;
    };

    std::vector<Camera> cameras;
    bool writeMain = true;    // the whole window at shotScale, every filmed picture
    int mainFirst = -1;       // the take picture the main video starts with
};

//==============================================================================
// The drawings and settings of the takes.

/** How every take's analyser view is set (Settings > Match your analyser: FFT and Levels; they
    change how the canvas and the live view draw the sound, never the sound): 4096 points, which
    keeps short passes sharp in time, and colours from -90 to `ceiling` dBFS. */
void setView (ArtFreqProcessor& p, float ceilingDb)
{
    setParameter (p, params::id::analyserFft, 0.0f);
    setParameter (p, params::id::analyserCeiling, ceilingDb);
}

/** Where the words are put: the upper half of the plot. A vertical video shows the live view's
    plot from its top down, and the lower part of the page is where the apps put their own
    buttons and captions. (Up to 12.5 kHz, which clears the view's own LIVE badge.) */
constexpr float readLowHz = 700.0f, readHighHz = 12500.0f;

ArtObject makeWord (const juce::String& word, float lowHz, float highHz, float start = 0.04f, float end = 0.96f)
{
    auto text = ArtDocument::makeTextObject (word, lowHz, highHz);   // Inter Bold, solid
    text.startTime = start;
    text.endTime = end;
    return text;
}

//==============================================================================
/** The hook: ArtFreq's live view, two words appearing as they play, round and round (Repeat). */
void filmHook (const juce::File& outputDir)
{
    ArtDocument drawing;
    drawing.objects.push_back (makeWord ("HEAR\nTHIS", readLowHz, readHighHz));

    Take take ("hook", false, [] (ArtFreqProcessor& p)
    {
        setParameter (p, params::id::length, 2.0f);    // "1 bar": 2 s at 120 BPM (the live view shows 4 s)
        setParameter (p, params::id::repeat, 1.0f);
        setParameter (p, params::id::density, 512.0f);
        setView (p, -30.0f);
    }, outputDir, drawing);

    take.showLive();
    take.noteRects();
    take.film (2);
    take.pressPlay();
    take.filmSeconds (6.5);
}

//==============================================================================
/** "Type it": a text box on the canvas, its word typed into the text field letter by letter
    (the canvas follows every key), then played in the live view. */
void filmTyping (const juce::File& outputDir)
{
    // The text box as "Add text" makes it (the word "Text", Inter Bold, solid), dragged to its
    // place on the canvas.
    ArtDocument drawing;
    drawing.objects.push_back (makeWord ("Text", readLowHz, readHighHz));
    const auto id = drawing.objects.back().id;

    Take take ("type", false, [] (ArtFreqProcessor& p)
    {
        setParameter (p, params::id::length, 2.0f);    // 1 bar
        setParameter (p, params::id::repeat, 1.0f);
        setParameter (p, params::id::density, 512.0f);
        setView (p, -30.0f);
    }, outputDir, drawing);

    take.bpm = 160.0;                                   // 1 bar: 1.5 s
    take.editor->selectObject (id);                     // as if clicked: handles, and its settings beside the canvas
    take.settle();
    take.noteRects ("canvas/");
    take.film (4);

    if (auto* field = findPart<juce::TextEditor> (*take.editor, "inspector-text"))
    {
        field->selectAll();                             // as "Add text" leaves it: typing replaces the word
        take.mark ("typing");

        // Four pictures a letter (scripted keys, faster than hands), two for the new line.
        for (const auto letter : juce::String ("ART\nFREQ"))
        {
            field->insertTextAtCaret (juce::String::charToString (letter));
            pump (30);                                  // a text box reports its change a moment later
            take.film (letter == '\n' ? 2 : 4);
        }
    }

    // What the canvas shows right after a key is its quick preview ("Updating..."); the measured
    // one ("Preview of the real sound") follows after a pause, as it does here half a second on.
    take.mark ("typed");
    take.film (15);
    take.settle();
    take.mark ("settled");
    take.film (10);

    take.editor->selectObject (juce::Uuid::null());    // nothing selected: no handles
    take.showLive();
    take.noteRects ("live/");
    take.film (2);
    take.pressPlay();
    take.filmSeconds (4.8);   // three passes: the edit uses the second, with the first still in view
}

//==============================================================================
/** "Draw it": a star drawn with the brush in one stroke, then played. */
void filmBrush (const juce::File& outputDir)
{
    Take take ("draw", false, [] (ArtFreqProcessor& p)
    {
        setParameter (p, params::id::length, 2.0f);    // 1 bar
        setParameter (p, params::id::repeat, 1.0f);
        setParameter (p, params::id::density, 512.0f);
        setView (p, -30.0f);
    }, outputDir);

    take.bpm = 160.0;
    take.content->keyPressed (juce::KeyPress ('b', juce::ModifierKeys(), 'b'));   // the Brush tool
    pump (30);

    if (auto* toolbar = findPart<ui::shell::Toolbar> (*take.editor, "toolbar"))
    {
        toolbar->brushSize.getSlider().setValue (30.0, juce::sendNotificationSync);       // px on screen
        toolbar->brushSoftness.getSlider().setValue (25.0, juce::sendNotificationSync);   // %
        toolbar->brushStrength.getSlider().setValue (100.0, juce::sendNotificationSync);  // %
    }

    pump (30);
    take.noteRects ("canvas/");
    take.film (6);

    // A five-pointed star in one stroke, across the drawing's length.
    const auto area = take.canvas->getDrawingArea();
    const auto scale = take.processor->getScale();
    const auto top = 1.0 - scale.toNorm (11500.0), bottom = 1.0 - scale.toNorm (760.0);
    std::vector<juce::Point<float>> corners;

    for (int i = 0; i <= 5; ++i)
    {
        const auto angle = juce::MathConstants<double>::twoPi * (static_cast<double> (i * 2 % 5) / 5.0);
        const auto u = 0.5 + 0.5 * std::sin (angle) / std::sin (juce::MathConstants<double>::twoPi * 0.2);   // 0..1 across
        const auto v = (1.0 - std::cos (angle)) / (1.0 - std::cos (juce::MathConstants<double>::twoPi * 0.4));   // 0 at the tip .. 1 at the feet
        corners.push_back ({ area.getX() + static_cast<float> (0.10 + 0.80 * u) * area.getWidth(),
                             area.getY() + static_cast<float> (top + (bottom - top) * v) * area.getHeight() });
    }

    const auto held = juce::ModifierKeys (juce::ModifierKeys::leftButtonModifier);
    const auto start = corners.front();
    take.mark ("stroke");
    take.canvas->mouseDown (mouseEventAt (*take.canvas, start, start, held));

    constexpr int movesPerLine = 12, movesPerPicture = 4;   // 5 lines in 15 pictures: half a second
    auto moves = 0;

    for (size_t line = 0; line + 1 < corners.size(); ++line)
        for (int i = 1; i <= movesPerLine; ++i)
        {
            const auto at = corners[line] + (corners[line + 1] - corners[line]) * (static_cast<float> (i) / movesPerLine);
            take.canvas->mouseDrag (mouseEventAt (*take.canvas, at, start, held, true));

            if (++moves % movesPerPicture == 0)
                take.film();   // the brush's ring is drawn where the last move was
        }

    take.canvas->mouseUp (mouseEventAt (*take.canvas, corners.back(), start, {}, true));
    take.mark ("drawn");
    take.film (15);
    take.settle();
    take.mark ("settled");
    take.film (10);

    take.showLive();
    take.noteRects ("live/");
    take.film (2);
    take.pressPlay();
    take.filmSeconds (4.8);   // three passes: the edit uses the second, with the first still in view
}

//==============================================================================
/** "A picture": a picture file dropped on the canvas, then played. */
void filmPicture (const juce::File& outputDir)
{
    // The picture: DemoReel's sunset (a striped sun going down behind mountains), as a PNG file.
    const auto file = outputDir.getChildFile ("sunset.png");
    file.deleteFile();
    {
        juce::FileOutputStream stream (file);
        check (stream.openedOk() && juce::PNGImageFormat().writeImageToStream (makeSunsetPicture(), stream), "write sunset.png");
    }

    Take take ("picture", false, [] (ArtFreqProcessor& p)
    {
        setParameter (p, params::id::length, 2.0f);    // 1 bar: 2 s at 120 BPM
        setParameter (p, params::id::repeat, 1.0f);
        setParameter (p, params::id::density, 512.0f);
        setView (p, -30.0f);
    }, outputDir);

    const juce::StringArray files { file.getFullPathName() };
    const auto area = take.canvas->getDrawingArea();
    const auto x = juce::roundToInt (area.getCentreX()), y = juce::roundToInt (area.getY() + 0.45f * area.getHeight());

    check (take.canvas->isInterestedInFileDrag (files), "the canvas takes the picture file");
    take.noteRects ("canvas/");
    take.film (4);
    take.mark ("drag");
    take.canvas->fileDragEnter (files, x, y);   // "Drop to add the picture here"
    take.film (8);
    take.mark ("drop");
    take.canvas->filesDropped (files, x, y);    // lands under the mouse, selected
    pump (30);

    take.film (2);                              // as it lands: 40 % of the length, in the band under the mouse

    // ... then dragged out to its size by two of its corner handles, as a user does it.
    const auto selected = take.editor->getSelectedObject();
    check (! selected.isNull(), "the dropped picture is selected");
    const auto scale = take.processor->getScale();
    const auto place = [&] (double time, double hz)
    {
        return juce::Point<float> (area.getX() + static_cast<float> (time) * area.getWidth(),
                                   area.getY() + static_cast<float> (1.0 - scale.toNorm (hz)) * area.getHeight());
    };
    const auto dragHandle = [&] (bool right, bool top, juce::Point<float> to, int pictures)
    {
        const auto box = take.canvas->getObjectBounds (selected).reduced (ui::CanvasView::handleReach);
        const juce::Point<float> from (right ? box.getRight() : box.getX(), top ? box.getY() : box.getBottom());
        const auto held = juce::ModifierKeys (juce::ModifierKeys::leftButtonModifier);
        take.canvas->mouseDown (mouseEventAt (*take.canvas, from, from, held));

        for (int i = 1; i <= pictures; ++i)
        {
            take.canvas->mouseDrag (mouseEventAt (*take.canvas, from + (to - from) * (static_cast<float> (i) / pictures), from, held, true));
            take.film();
        }

        take.canvas->mouseUp (mouseEventAt (*take.canvas, to, from, {}, true));
    };

    take.mark ("resize");
    dragHandle (true, true, place (0.96, readHighHz), 4);     // top right corner: up and out
    dragHandle (false, false, place (0.04, 400.0), 4);        // bottom left corner: down and out
    take.mark ("resized");

    take.processor->rebuildPlanIfNeeded();
    pump (40);
    take.noteRects ("dropped/");
    take.film (15);
    take.settle();
    take.mark ("settled");
    take.film (10);

    take.editor->selectObject (juce::Uuid::null());
    take.showLive();
    take.noteRects ("live/");
    take.film (2);
    take.pressPlay();
    take.filmSeconds (6.3);   // three passes
}

//==============================================================================
/** The product still: ArtFreq with the drawing a new instance opens with (its own name), drawn
    with the view settings of the other takes. Nothing playing. */
void filmStill (const juce::File& outputDir)
{
    Take take ("still", false, [] (ArtFreqProcessor& p)
    {
        setParameter (p, params::id::density, 512.0f);
        setView (p, -30.0f);
    }, outputDir, ArtDocument::createDefault());

    take.settle();
    take.noteRects();
    take.film (3);
}

//==============================================================================
/** "Carve it into audio you already have": ArtFreq FX's live view on a loop.

    The loop runs through the plug-in for two passes of the drawing (2 bars each) in Carve with
    Depth at 0 dB, which carves nothing: the live view fills with the loop as it is. Then Depth
    goes to -80 dB, and each pass starts with a rest (the loop as it is, sample for sample) and
    then the words:
      mark "a": Carve + Draw (the words carved out and played into the hole)
      mark "b": Carve (the words carved out)
      mark "c": Carve + Draw again, to the end.
    Mode is changed as a host's automation changes it, on the first picture of a pass. */
void filmEffect (const juce::File& outputDir)
{
    ArtDocument drawing;
    drawing.objects.push_back (makeWord ("YOUR\nNAME", 400.0f, readHighHz, 0.30f, 0.86f));

    Take take ("fx", true, [] (ArtFreqProcessor& p)
    {
        setParameter (p, params::id::length, 3.0f);    // 2 bars: 4 s at 120 BPM (the live view shows 5 s)
        setParameter (p, params::id::repeat, 1.0f);
        setParameter (p, params::id::mode, static_cast<float> (static_cast<int> (EffectMode::carve)));
        setParameter (p, params::id::depth, 0.0f);
        setParameter (p, params::id::density, 512.0f);
        setView (p, -20.0f);
    }, outputDir, drawing);

    constexpr int passFrames = 4 * framesPerSecond;
    constexpr int dryPasses = 2, wetFrames = 17 * framesPerSecond;
    take.input = makeSong ((dryPasses * passFrames + wetFrames) / static_cast<double> (framesPerSecond) + 1.0);
    take.showLive();

    // ArtFreq FX's output is its latency behind its input. The DAW starts that much before a
    // picture, so the loop comes out of the plug-in from that picture's first sample on.
    const auto latency = take.processor->getLatencySamples();
    const auto leadFrames = (latency + samplesPerFrame - 1) / samplesPerFrame;
    take.pressPlay (leadFrames * samplesPerFrame - latency);
    take.film (leadFrames);
    take.mark ("sound");
    take.film (dryPasses * passFrames);

    const auto setMode = [&take] (EffectMode mode, const char* mark)
    {
        setParameter (*take.processor, params::id::mode, static_cast<float> (static_cast<int> (mode)));
        setParameter (*take.processor, params::id::depth, -80.0f);
        take.processor->rebuildPlanIfNeeded();
        pump (40);
        take.mark (mark);
        take.noteRects (juce::String (mark) + "/");
    };

    for (int frame = 0; frame < wetFrames; ++frame)
    {
        if (frame == 0)
            setMode (EffectMode::carveDraw, "a");
        else if (frame == passFrames)
            setMode (EffectMode::carve, "b");
        else if (frame == 2 * passFrames)
            setMode (EffectMode::carveDraw, "c");

        take.film();
    }
}

//==============================================================================
// Ad B, "Hidden in this beat" (hookB/). Every take is ArtFreq FX on the same loop and on one
// clock: the DAW starts so that the loop comes out of the plug-in at mark "sound", and plays on;
// mark "ad0" is two bars later, the ad's first picture. Ad time t is take picture ad0 + 30 t in
// every take, and the loop is at the same place there in every take, so a cut from one take to
// another on a picture keeps the music in step. The drawing passes once a bar (Length 1 bar,
// Repeat), in Carve.

constexpr int hookBPreRollFrames = 4 * framesPerSecond;   // two bars of the loop before the ad starts
constexpr float hookBLowHz = 400.0f;                      // the drawings: 400 Hz - 12.5 kHz

ArtDocument hookBTypedDrawing, hookBDroppedDrawing;       // what the typing and the drop takes end with

std::unique_ptr<Take> startHookB (const juce::String& name, const ArtDocument& drawing, float depthDb,
                                  double adSeconds, bool live, const juce::File& outputDir)
{
    auto take = std::make_unique<Take> (name, true, [depthDb] (ArtFreqProcessor& p)
    {
        setParameter (p, params::id::length, 2.0f);    // 1 bar: 2 s at 120 BPM (the live view shows 4 s)
        setParameter (p, params::id::repeat, 1.0f);
        setParameter (p, params::id::mode, static_cast<float> (static_cast<int> (EffectMode::carve)));
        setParameter (p, params::id::depth, depthDb);
        setParameter (p, params::id::density, 512.0f);
        setView (p, -20.0f);
    }, outputDir, drawing);

    take->input = makeSong ((hookBPreRollFrames + juce::roundToInt (adSeconds * framesPerSecond))
                                / static_cast<double> (framesPerSecond) + 2.0);

    if (live)
        take->showLive();

    take->noteRects (live ? "live/" : "canvas/");

    // ArtFreq FX's output is its latency behind its input: the DAW starts that much before a
    // picture, so the loop comes out of the plug-in from that picture's first sample on.
    const auto latency = take->processor->getLatencySamples();
    const auto leadFrames = (latency + samplesPerFrame - 1) / samplesPerFrame;
    take->pressPlay (leadFrames * samplesPerFrame - latency);
    take->film (leadFrames);
    take->mark ("sound");
    take->marks["ad0"] = take->marks["sound"] + hookBPreRollFrames;
    return take;
}

/** Films up to (not including) the picture at ad time `adSeconds`. */
void filmUntil (Take& take, double adSeconds)
{
    const auto end = take.marks["ad0"] + juce::roundToInt (adSeconds * framesPerSecond);

    while (take.frames < end && take.editor != nullptr)
        take.film();
}

void setDepth (Take& take, float depthDb, const char* mark)
{
    setParameter (*take.processor, params::id::depth, depthDb);
    take.processor->rebuildPlanIfNeeded();
    pump (40);
    take.mark (mark);
}

/** "Type your name.": the text box as "+ Text" makes it (the word "Text"), placed, selected so
    its settings are in the drawer, and the name typed into its text field while the loop plays. */
void filmHookBType (const juce::File& outputDir)
{
    ArtDocument drawing;
    drawing.objects.push_back (makeWord ("Text", hookBLowHz, readHighHz, 0.06f, 0.94f));
    const auto id = drawing.objects.back().id;

    auto take = startHookB ("b-type", drawing, -80.0f, 6.2, false, outputDir);
    take->editor->selectObject (id);   // as if clicked: handles, and its settings in the drawer
    take->settle();
    take->noteRects ("selected/");
    check (take->editor->isDrawerOpen(), "b-type: the drawer is open on the text");

    filmUntil (*take, 4.0);

    if (auto* field = findPart<juce::TextEditor> (*take->editor, "inspector-text"))
    {
        field->selectAll();   // as "+ Text" leaves it: typing replaces the word
        take->mark ("typing");

        for (const auto letter : juce::String ("YOUR\nNAME"))
        {
            field->insertTextAtCaret (juce::String::charToString (letter));
            pump (30);
            take->film (letter == '\n' ? 2 : 4);
        }
    }

    take->mark ("typed");
    filmUntil (*take, 5.5);
    take->settle();
    take->mark ("settled");
    filmUntil (*take, 6.2);

    hookBTypedDrawing = take->processor->getDocument();
    check (hookBTypedDrawing.objects.size() == 1 && hookBTypedDrawing.objects.front().text == "YOUR\nNAME",
           "b-type: the drawing is the typed name");
}

/** The hook: the live view of the loop, as it is for two bars (Depth 0 dB), then the typed name
    carved into it once a bar from the ad's first picture on. */
void filmHookBHook (const juce::File& outputDir)
{
    check (! hookBTypedDrawing.objects.empty(), "b-hook: film b-type first (its drawing is used here)");

    auto take = startHookB ("b-hook", hookBTypedDrawing, 0.0f, 16.2, true, outputDir);
    filmUntil (*take, -2.0 / framesPerSecond);   // the bar has begun; the name starts 0.12 s into it
    setDepth (*take, -80.0f, "carve");
    filmUntil (*take, 16.2);
}

/** "Or drop in your logo.": a logo file dropped on the empty canvas while the loop plays, then
    dragged out by two of its corners to the shape it has. */
void filmHookBDrop (const juce::File& outputDir, const juce::File& logo)
{
    auto take = startHookB ("b-drop", ArtDocument(), -80.0f, 10.2, false, outputDir);
    const juce::StringArray files { logo.getFullPathName() };
    check (take->canvas->isInterestedInFileDrag (files), "b-drop: the canvas takes the logo file");

    const auto area0 = take->canvas->getDrawingArea();
    const auto x = juce::roundToInt (area0.getCentreX()), y = juce::roundToInt (area0.getY() + 0.42f * area0.getHeight());

    filmUntil (*take, 8.0);
    take->mark ("drag");
    take->canvas->fileDragEnter (files, x, y);   // "Drop to add the picture here"
    filmUntil (*take, 8.27);
    take->mark ("drop");
    take->canvas->filesDropped (files, x, y);    // lands under the mouse, selected
    pump (30);
    take->film (2);

    // Dragged out to keep the logo's own shape on screen: the live view shows a bar across 326
    // of its points and the scale's 3 decades across 300, so a box of the logo's aspect spans
    // this much of the bar.
    const auto selected = take->editor->getSelectedObject();
    check (! selected.isNull(), "b-drop: the dropped logo is selected");
    const auto logoImage = juce::ImageFileFormat::loadFrom (logo);
    const auto aspect = logoImage.isValid() ? logoImage.getWidth() / static_cast<double> (logoImage.getHeight()) : 1.0;
    const auto heightPoints = 300.0 * std::log10 (readHighHz / hookBLowHz) / 3.0;
    const auto span = juce::jlimit (0.2, 0.9, heightPoints * aspect / 326.0);
    const auto scale = take->processor->getScale();

    const auto place = [&] (double time, double hz)
    {
        const auto area = take->canvas->getDrawingArea();
        return juce::Point<float> (area.getX() + static_cast<float> (time) * area.getWidth(),
                                   area.getY() + static_cast<float> (1.0 - scale.toNorm (hz)) * area.getHeight());
    };
    const auto dragHandle = [&] (bool right, bool top, double time, double hz, int pictures)
    {
        const auto box = take->canvas->getObjectBounds (selected).reduced (ui::CanvasView::handleReach);
        const juce::Point<float> from (right ? box.getRight() : box.getX(), top ? box.getY() : box.getBottom());
        const auto held = juce::ModifierKeys (juce::ModifierKeys::leftButtonModifier);
        take->canvas->mouseDown (mouseEventAt (*take->canvas, from, from, held));

        for (int i = 1; i <= pictures; ++i)
        {
            const auto to = place (time, hz);
            take->canvas->mouseDrag (mouseEventAt (*take->canvas, from + (to - from) * (static_cast<float> (i) / pictures), from, held, true));
            take->film();
        }

        take->canvas->mouseUp (mouseEventAt (*take->canvas, place (time, hz), from, {}, true));
    };

    take->mark ("resize");
    dragHandle (true, true, 0.5 + span / 2.0, readHighHz, 4);
    dragHandle (false, false, 0.5 - span / 2.0, hookBLowHz, 4);
    take->mark ("resized");
    take->processor->rebuildPlanIfNeeded();
    pump (40);
    take->noteRects ("dropped/");
    filmUntil (*take, 9.4);
    take->settle();
    take->mark ("settled");
    filmUntil (*take, 10.2);

    hookBDroppedDrawing = take->processor->getDocument();
    check (hookBDroppedDrawing.objects.size() == 1, "b-drop: the drawing is the dropped logo");
}

/** The logo's live view: the loop as it is, then the dropped logo carved into it from ad 10 s. */
void filmHookBLogo (const juce::File& outputDir)
{
    check (! hookBDroppedDrawing.objects.empty(), "b-logo: film b-drop first (its drawing is used here)");

    auto take = startHookB ("b-logo", hookBDroppedDrawing, 0.0f, 12.2, true, outputDir);
    filmUntil (*take, 10.0 - 2.0 / framesPerSecond);
    setDepth (*take, -80.0f, "carve");
    filmUntil (*take, 12.2);
}

//==============================================================================
// Ad C, "This beat is talking" (hookC/). One take of ArtFreq FX in Carve + Draw on the loop,
// filmed at --scale 7: the ad shows its live view turned a quarter right, so time runs up the
// screen. The drawing passes once every 2 bars (4 s) and is a different picture each pass: the
// words of the ad, laid out to read upright once turned (tools/make_strips_hookC.py), then, after
// the reveal, the native text "ArtFreq". Mark "ad0" is 1.5 s into the first word pass.

void filmHookC (const juce::File& outputDir)
{
    constexpr int passFrames = 4 * framesPerSecond;
    constexpr int preRollFrames = passFrames;                    // one pass of the loop as it is
    constexpr int ad0Offset = preRollFrames + 3 * framesPerSecond / 2;
    constexpr double adSeconds = 16.2;

    Take take ("c-wf", true, [] (ArtFreqProcessor& p)
    {
        setParameter (p, params::id::length, 3.0f);    // 2 bars: 4 s at 120 BPM (the live view shows 5 s)
        setParameter (p, params::id::repeat, 1.0f);
        setParameter (p, params::id::mode, static_cast<float> (static_cast<int> (EffectMode::carveDraw)));
        setParameter (p, params::id::depth, -80.0f);
        setParameter (p, params::id::density, 512.0f);
        setView (p, -20.0f);
    }, outputDir);

    take.input = makeSong ((ad0Offset + juce::roundToInt (adSeconds * framesPerSecond)) / static_cast<double> (framesPerSecond) + 2.0);
    take.showLive();
    take.noteRects ("live/");

    const auto latency = take.processor->getLatencySamples();
    const auto leadFrames = (latency + samplesPerFrame - 1) / samplesPerFrame;
    take.pressPlay (leadFrames * samplesPerFrame - latency);
    take.film (leadFrames);
    take.mark ("sound");
    const auto sound = take.marks["sound"];
    take.marks["ad0"] = sound + ad0Offset;

    // The drawings, one a pass: the three word pictures, then "ArtFreq" as text, as it comes.
    std::vector<ArtDocument> drawings;

    for (int i = 1; i <= 3; ++i)
    {
        const auto file = outputDir.getChildFile ("c-p" + juce::String (i) + ".png");
        const auto image = juce::ImageFileFormat::loadFrom (file);
        check (image.isValid(), "c-wf: " + file.getFileName());
        ArtDocument d;
        auto o = ArtDocument::makeImageObject (prepareImportedImage (image), 300.0f, 12000.0f);
        o.fileName = file.getFileName();
        o.startTime = 0.0f;
        o.endTime = 1.0f;
        d.objects.push_back (o);
        drawings.push_back (d);
    }

    ArtDocument name;
    name.objects.push_back (makeWord ("ArtFreq", 300.0f, 12000.0f, 0.08f, 0.92f));
    drawings.push_back (name);

    // A drawing goes in 4 pictures before its pass begins (the pass before has nothing drawn in
    // its last beat), so the plan is ready when the pass starts.
    for (size_t k = 0; k < drawings.size(); ++k)
    {
        const auto passStart = sound + preRollFrames + static_cast<int> (k) * passFrames;

        while (take.frames < passStart - 4)
            take.film();

        // No message loop here: the live view's own timer would run more than 0.3 s after its
        // last columns (a frame at this scale takes that long) and scroll silence into the view.
        // The window catches up in the next picture's pump, right after it takes its columns.
        take.processor->setDocument (drawings[k]);
        take.processor->rebuildPlanIfNeeded();
        take.mark (("pass" + juce::String (static_cast<int> (k) + 1)).toRawUTF8());
    }

    while (take.frames < take.marks["ad0"] + juce::roundToInt (adSeconds * framesPerSecond))
        take.film();
}


//==============================================================================
// Ad D, "Resolve" (hookD/). The ArtFreq instrument, one take: a drawing of a night sky (code-made
// pictures, tools/make_pictures_hookD.py) over 4 bars, Repeat on, in the live view. Density is
// turned up on the footer's own knob between the pictures: 64 lines, then 128, 256, 512 and, in
// the silent last beat of the pass, 1024 for the next pass. Filmed by three cameras at once: the
// live view's plot (100 Hz - 20 kHz) at `plotScale`, a part of the window with the layer list at
// `uiScale`, and the Density knob at `knobScale` (and the whole window at --scale, for checking).
// Mark "ad0" is the ad's first picture: 1 s into the second pass.

struct HookDPicture { const char* name; float start, end, lowHz, highHz; ImageMode mode; };

const HookDPicture hookDPictures[] = {
    { "planet", 0.000f, 0.190f, 1100.0f, 6300.0f,  ImageMode::original },
    { "moon",   0.250f, 0.406f, 2000.0f, 6300.0f,  ImageMode::original },
    { "waves",  0.250f, 0.406f, 1100.0f, 1800.0f,  ImageMode::original },
    { "galaxy", 0.500f, 0.656f, 1200.0f, 6300.0f,  ImageMode::outline },
    { "comet",  0.750f, 0.940f, 1100.0f, 6300.0f,  ImageMode::original },
    { "stars",  0.000f, 0.940f, 7500.0f, 11500.0f, ImageMode::original },
};

void filmHookD (const juce::File& outputDir, const juce::String& takeName, float plotScale, float uiScale, float knobScale,
                float ceilingDb, juce::Rectangle<int> uiArea)
{
    constexpr int passFrames = 8 * framesPerSecond;                // 4 bars at 120 BPM
    constexpr int adFrames = 16 * framesPerSecond;

    ArtDocument drawing;

    for (const auto& picture : hookDPictures)
    {
        const auto file = outputDir.getChildFile ("d-" + juce::String (picture.name) + ".png");
        const auto image = juce::ImageFileFormat::loadFrom (file);
        check (image.isValid(), takeName + ": " + file.getFileName());
        auto o = ArtDocument::makeImageObject (prepareImportedImage (image), picture.lowHz, picture.highHz);
        o.fileName = file.getFileName().fromFirstOccurrenceOf ("d-", false, false);
        o.startTime = picture.start;
        o.endTime = picture.end;
        o.imageMode = picture.mode;
        drawing.objects.push_back (o);
    }

    Take take (takeName, false, [ceilingDb] (ArtFreqProcessor& p)
    {
        setParameter (p, params::id::length, 4.0f);     // 4 bars: 8 s at 120 BPM (the live view shows 10 s)
        setParameter (p, params::id::repeat, 1.0f);
        setParameter (p, params::id::density, 64.0f);
        setView (p, ceilingDb);
    }, outputDir, drawing);

    take.editor->selectObject (juce::Uuid::null());
    take.showLive();
    take.noteRects ("live/");
    take.advance (2);
    take.pressPlay();
    const auto play = take.marks["play"];
    const auto ad0 = play + passFrames + framesPerSecond;
    take.marks["ad0"] = ad0;

    // The cameras. The plot: the newest 3.3 s of the live view's plot, from 12.4 kHz (under its
    // LIVE badge) down to 140 Hz.
    const auto plot = take.editor->getLocalArea (take.liveView, ui::axes::plotArea (take.liveView->getLocalBounds(),
                                                                                    ui::CanvasView::axisWidth, ui::CanvasView::axisHeight));
    const auto yOf = [&plot] (double hz) { return plot.getY() + juce::roundToInt (plot.getHeight() * std::log10 (20000.0 / hz) / 3.0); };
    const auto plotWidth = juce::roundToInt (plot.getWidth() * 3.3 / take.liveView->getVisibleSeconds());
    const juce::Rectangle<int> plotArea (plot.getRight() - plotWidth, yOf (12400.0), plotWidth, yOf (140.0) - yOf (12400.0));
    take.addCamera ("plot", plotArea, plotScale, ad0 - 6, ad0 + adFrames + 6);
    take.addCamera ("ui", uiArea, uiScale, ad0 + 300, ad0 + 400);

    auto* knob = findPart<juce::Slider> (*take.editor, "density");
    const auto knobArea = take.editor->getLocalArea (knob, knob->getLocalBounds()).expanded (14, 12);
    take.addCamera ("knob", knobArea, knobScale, ad0 + 180, ad0 + 225);
    take.rects["plot-pt"] = plot;
    take.rects["knob-pt"] = knobArea;

    // Density through the knob, as a hand turns it: one value a picture, set before the picture
    // (the plan follows at once, so the picture's sound already has it).
    std::map<int, double> turns;
    const auto ramp = [&turns, ad0] (int first, int count, double from, double to)
    {
        for (int i = 1; i <= count; ++i)
            turns[ad0 + first + i - 1] = from * std::pow (to / from, i / static_cast<double> (count));
    };
    ramp (24, 6, 64.0, 128.0);
    ramp (84, 6, 128.0, 256.0);
    ramp (144, 6, 256.0, 512.0);
    ramp (198, 13, 512.0, 1024.0);    // 1024 on the pass's first picture (the knob reads "1024 lin..." there)

    juce::Array<juce::var> densities;
    const auto end = ad0 + adFrames + 7;

    while (take.frames < end && take.editor != nullptr)
    {
        if (const auto turn = turns.find (take.frames); turn != turns.end())
        {
            // No message loop here (see filmHookC): the knob's attachment sets the parameter now.
            knob->setValue (std::round (turn->second), juce::sendNotificationSync);
            take.processor->rebuildPlanIfNeeded();
        }

        densities.add (knob->getValue());

        if (take.frames < ad0 - 6)
            take.advance (1);
        else
            take.film();
    }

    juce::DynamicObject::Ptr extra (new juce::DynamicObject());
    extra->setProperty ("firstFrame", play);
    extra->setProperty ("density", densities);
    outputDir.getChildFile (takeName + "-density.json").replaceWithText (juce::JSON::toString (juce::var (extra.get())));
}

} // namespace

int main (int argc, char* argv[])
{
   #if JUCE_LINUX || JUCE_BSD
    // As a standalone app JUCE installs X error handlers that tolerate a virtual display without
    // a window manager (Xlib's own would end the process). No application object is created.
    juce::JUCEApplicationBase::createInstance = [] () -> juce::JUCEApplicationBase* { return nullptr; };
   #endif

    const juce::ScopedJuceInitialiser_GUI gui;
    std::signal (SIGPIPE, SIG_IGN);

    if (argc < 2)
    {
        std::cerr << "usage: ArtFreqAdReel <output-dir> [--takes hook,type,draw,picture,fx,still] [--scale 4]" << std::endl;
        return 2;
    }

    const auto cwd = juce::File::getCurrentWorkingDirectory();
    const auto outputDir = cwd.getChildFile (argv[1]);
    juce::StringArray wanted;
    juce::File logoFile;

    for (int i = 2; i + 1 < argc; i += 2)
    {
        const juce::String option (argv[i]), value (argv[i + 1]);

        if (option == "--takes")
            wanted = juce::StringArray::fromTokens (value, ",", {});
        else if (option == "--scale")
            shotScale = value.getFloatValue();
        else if (option == "--ceiling")
            hookDCeiling = value.getFloatValue();
        else if (option == "--logo")
            logoFile = cwd.getChildFile (value);
        else
        {
            std::cerr << "unknown option " << option << std::endl;
            return 2;
        }
    }

    if (! outputDir.createDirectory())
    {
        std::cerr << "Cannot create " << outputDir.getFullPathName() << std::endl;
        return 1;
    }

    const auto want = [&wanted] (const char* take) { return wanted.isEmpty() || wanted.contains (take); };

    // Every instance is activated, against a fake licence server in a folder of the tool's own.
    licensetest::installRunnerLicensing();

    if (want ("hook"))      filmHook (outputDir);
    if (want ("type"))      filmTyping (outputDir);
    if (want ("draw"))      filmBrush (outputDir);
    if (want ("picture"))   filmPicture (outputDir);
    if (want ("fx"))        filmEffect (outputDir);
    if (want ("still"))     filmStill (outputDir);

    // Ad B: only when asked for by name; b-hook uses b-type's drawing, b-logo uses b-drop's.
    if (wanted.contains ("b-type"))   filmHookBType (outputDir);
    if (wanted.contains ("b-hook"))   filmHookBHook (outputDir);
    if (wanted.contains ("b-drop"))   filmHookBDrop (outputDir, logoFile);
    if (wanted.contains ("b-logo"))   filmHookBLogo (outputDir);
    if (wanted.contains ("c-wf"))     filmHookC (outputDir);

    // Ad D: d-test (small, to check the look) and d-orbit (the take the ad is cut from).
    const juce::Rectangle<int> hookDUiArea { 560, 44, 560, 446 };
    if (wanted.contains ("d-test"))   filmHookD (outputDir, "d-test", 4.0f, 2.0f, 4.0f, hookDCeiling, hookDUiArea);
    if (wanted.contains ("d-orbit"))  filmHookD (outputDir, "d-orbit", 14.0f, 4.0f, 12.0f, hookDCeiling, hookDUiArea);

    pump (50);
    licensetest::removeRunnerLicensing();

    std::cout << (failed ? "Some checks failed" : "All checks passed") << std::endl;
    return failed ? 1 : 0;
}
