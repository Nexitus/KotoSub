# AI Video Translator

AI Video Translator is a streamlined tool that automates the process of generating high-quality subtitles for your videos. It leverages state-of-the-art AI models to extract audio, transcribe it with automatic language detection, and translate it with context-aware precision.

## Key Features

-   **Seamless Video Input**: Supports popular formats like MP4, MKV, AVI, and MOV.
-   **Automated Audio Extraction**: High-quality audio extraction powered by FFmpeg.
-   **AI-Powered Transcription**: Utilizes OpenAI Whisper for high-accuracy transcription with **Automatic Language Detection**.
-   **Advanced Translation**: Context-aware translation using GPT-4 with an integrated **AI Quality Verification Pass**.
-   **Speaker Diarization**: Automatically identifies and labels different speakers within the video.
-   **subtitle formats**: Outputs industry-standard **SRT** and **ASS** files with intelligent segment refinement.
-   **Dual Interface**: Access the tool via a simple **Gradio Web UI** or a robust **CLI** for batch processing.

## Quick Start

1.  **Installation**:
    ```bash
    git clone https://github.com/Nexitus/KotoSub.git
    cd KotoSub
    pip install -r requirements.txt
    ```

2.  **Prerequisites**:
    -   Python 3.10+
    -   [FFmpeg](https://ffmpeg.org/) installed and added to your system PATH.
    -   An OpenAI API Key.

3.  **Configuration**:
    Create a `.env` file in the root directory:
    ```env
    OPENAI_API_KEY=your_api_key_here
    ```

4.  **Launch the App**:
    ```bash
    python ui/gradio_app.py
    ```

## Language Support

The application supports over **120 languages** for transcription and translation, including:
-   English, Chinese (Mandarin/Cantonese), Spanish, French, German, Japanese, Korean, Portuguese, Russian, and many more.

## LLM Supported

-   **Transcription**: [OpenAI Whisper](https://openai.com/research/whisper) (`whisper-1`)
-   **Translation & QA**: [OpenAI GPT-4](https://openai.com/gpt-4) (`gpt-4-turbo-preview`)

---

## Architecture

The application follows a modular, service-oriented architecture, ensuring clear separation between audio processing, AI transcription, LLM translation, and the user interface.
