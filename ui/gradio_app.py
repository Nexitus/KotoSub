import gradio as gr
import os
import sys
import platform
import subprocess

# Add the project root to the python path to allow imports from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import VideoTranslatorApp

def open_output_folder(path):
    # Verify path exists
    if not os.path.exists(path):
        return "Folder not found! ❌"
    
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", path])
        else:  # Linux
            subprocess.Popen(["xdg-open", path])
        return "Folder opened! 📂"
    except Exception as e:
        return f"Error opening folder: {e}"

def transcode_process(file_objs, source_lang, target_lang, openai_api_key, openai_base_url, whisper_model, llm_model, output_dir, use_diarization, hf_token, use_quality_check, burn_subtitles, font_name, font_size, subtitle_position, progress=gr.Progress()):
    if not file_objs:
        raise gr.Error("Please upload at least one video file.")

    app = VideoTranslatorApp()
    
    # Check API Key
    if not openai_api_key:
        raise gr.Error("Please enter your OpenAI API Key in the configuration section.")

    results_summary = []
    output_files = []
    
    total_files = len(file_objs)
    
    try:
        for idx, file_obj in enumerate(file_objs):
            video_path = file_obj.name
            filename = os.path.basename(video_path)
            
            # Internal progress wrapper for current file
            def update_progress(p, msg):
                # Calculate global progress: completed files + current file progress
                global_p = (idx + p) / total_files
                progress(global_p, desc=f"Scanning {idx+1}/{total_files}: {msg}")
                print(f"[{idx+1}/{total_files}] {msg}")

            progress((idx) / total_files, desc=f"Starting file {idx+1} of {total_files}: {filename}")
            
            # Prepare burn options
            burn_options = {
                "font": font_name,
                "font_size": font_size,
                "position": subtitle_position
            }
            
            result = app.process(
                video_path,
                source_lang,
                target_lang,
                openai_api_key=openai_api_key,
                openai_base_url=openai_base_url,
                whisper_model=whisper_model,
                llm_model=llm_model,
                output_dir=output_dir,
                progress_callback=update_progress,
                use_diarization=use_diarization,
                hf_token=hf_token,
                use_quality_check=use_quality_check,
                burn_subtitles=burn_subtitles,
                burn_options=burn_options
            )
            
            output_path = result["output_file"]
            video_output = result.get("video_output")
            duration = result.get("duration", 0)
            segments = result.get("segments", 0)
            
            summary = f"✅ {filename}: {segments} segments ({duration:.1f}s)"
            if video_output:
                summary += " [Burned Video Created]"
                output_files.append(video_output)
            
            results_summary.append(summary)
            output_files.append(output_path)
        
        summary_text = f"🎉 Batch Processing Complete!\n\n" + "\n".join(results_summary)
        
        # Read preview for the first SRT file
        preview = ""
        first_srt = next((f for f in output_files if f.endswith('.srt')), None)
        if first_srt and os.path.exists(first_srt):
            with open(first_srt, "r", encoding="utf-8") as f:
                lines = f.readlines()
                preview = "".join(lines[:20]) + ("\n..." if len(lines) > 20 else "")
        
        return summary_text, output_files, preview
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise gr.Error(f"Processing failed: {str(e)}")

# Custom CSS for TELUS branding
# Colors: Purple #4B286D, Green #66CC00, Gray #F4F4F7, Dark Text #2A2C2E
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

body { 
    background-color: #F4F4F7; 
    font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif; 
    color: #2A2C2E;
}

.container { 
    max_width: 1200px; 
    margin: auto; 
    padding-top: 2rem; 
}

/* Header Styling */
.header-container { 
    background: white; 
    padding: 2rem; 
    border-radius: 8px; 
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    margin-bottom: 2rem;
    border-left: 6px solid #4B286D;
}
.header-title { 
    font-size: 2rem; 
    font-weight: 700; 
    color: #4B286D; 
    margin-bottom: 0.5rem; 
    letter-spacing: -0.5px; 
}
.header-subtitle { 
    font-size: 1.1rem; 
    color: #54595F; 
    font-weight: 400; 
}

/* Card/Panel Styling */
.gradio-container .panel {
    background: white;
    border-radius: 8px;
    border: 1px solid #E1E1E5 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02) !important;
}

/* Button Styling */
.submit-btn { 
    background: #66CC00 !important; 
    color: white !important; 
    border: none; 
    font-weight: 600; 
    border-radius: 24px !important; 
    font-size: 1.1rem !important;
    padding: 10px 24px !important;
    transition: all 0.2s ease;
    box-shadow: 0 4px 12px rgba(102, 204, 0, 0.3);
}
.submit-btn:hover { 
    background: #2B8000 !important; 
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(102, 204, 0, 0.4);
}

.secondary-btn {
    background: white !important;
    border: 1px solid #4B286D !important;
    color: #4B286D !important;
    border-radius: 24px !important;
}

/* Form Elements */
label span {
    color: #4B286D !important;
    font-weight: 600 !important;
}
.block.srt-preview textarea {
    font-family: 'Courier New', monospace;
    font-size: 0.9rem;
    background: #F9F9FA;
}

.footer { 
    text-align: center; 
    margin-top: 3rem; 
    padding-bottom: 2rem; 
    color: #71757B; 
    font-size: 0.875rem; 
    border-top: 1px solid #E1E1E5;
    padding-top: 1rem;
}
"""

# Theme Configuration matching TELUS guidelines
theme = gr.themes.Soft(
    primary_hue="purple",
    secondary_hue="green",
    neutral_hue="slate",
    font=["Inter", "Helvetica Neue", "Arial", "sans-serif"],
).set(
    body_background_fill="#F4F4F7",
    body_text_color="#2A2C2E",
    block_title_text_color="#4B286D",
    block_title_text_weight="600",
    block_label_text_color="#4B286D",
    input_background_fill="white",
    input_border_color="#D8D8D8",
    input_border_width="1px",
    button_primary_background_fill="#66CC00",
    button_primary_background_fill_hover="#2B8000",
    button_primary_text_color="white",
    checkbox_label_text_color="#2A2C2E",
    slider_color="#66CC00",
)

# JavaScript for LocalStorage Persistence
js_load_settings = """
function loadSettings() {
    return [
        localStorage.getItem("openai_api_key") || "",
        localStorage.getItem("openai_base_url") || "https://api.openai.com/v1",
        localStorage.getItem("whisper_model") || "whisper-1",
        localStorage.getItem("llm_model") || "gpt-4o",
        localStorage.getItem("output_dir") || "output",
        localStorage.getItem("hf_token") || ""
    ];
}
"""

js_save_settings = """
function saveSettings(apiKey, baseUrl, whisperModel, llmModel, outputDir, hfToken) {
    localStorage.setItem("openai_api_key", apiKey);
    localStorage.setItem("openai_base_url", baseUrl);
    localStorage.setItem("whisper_model", whisperModel);
    localStorage.setItem("llm_model", llmModel);
    localStorage.setItem("output_dir", outputDir);
    localStorage.setItem("hf_token", hfToken);
    return "Settings saved to browser! 💾";
}
"""

with gr.Blocks(theme=theme, css=custom_css, title="AI Video Translator") as demo:
    
    # Global Header
    with gr.Row(elem_classes="header-container"):
        with gr.Column(scale=4):
            gr.Markdown(
                """
                <div class="header-title">AI Video Subtitle Translator</div>
                <div class="header-subtitle">Enterprise-grade transcription and translation powered by AI</div>
                """
            )
        with gr.Column(scale=1):
            # Placeholder for logo or extra status
            pass

    with gr.Tabs():
        # Tab 1: Translator
        with gr.TabItem("Translator"):
            with gr.Column(elem_classes="container"):
                
                with gr.Row(equal_height=False):
                    # Left Column: Configuration
                    with gr.Column(scale=1, variant="panel"):
                        gr.Markdown("### 1. Upload Video")
                        video_input = gr.File(
                            label="Drop video files here", 
                            file_types=[".mp4", ".mkv", ".avi", ".mov", ".webm"],
                            file_count="multiple",
                            height=150
                        )
                        
                        gr.Markdown("### 2. Language")
                        with gr.Row():
                            source_lang = gr.Dropdown(
                                choices=[
                                    ("Auto-detect", None),
                                    ("Cantonese", "yue"),
                                    ("Mandarin (Simplified)", "zh"),
                                    ("Mandarin (Traditional)", "zh"),
                                    ("Japanese", "ja"), 
                                    ("English", "en"), 
                                    ("French", "fr"), 
                                    ("German", "de"), 
                                    ("Spanish", "es"),
                                    ("Korean", "ko"),
                                    ("Italian", "it")
                                ], 
                                value=None, 
                                label="Source Language"
                            )
                            target_lang = gr.Dropdown(
                                choices=[
                                    ("English", "en"),
                                    ("Spanish", "es"),
                                    ("French", "fr"),
                                    ("German", "de"),
                                    ("Chinese", "zh"),
                                    ("Japanese", "ja")
                                ], 
                                value="en", 
                                label="Target Language"
                            )
                        
                        gr.Markdown("### 3. Processing Options")
                        with gr.Group():
                            use_diarization = gr.Checkbox(label="Enable Speaker Diarization", value=False, info="Requires HF Token in Settings")
                            use_quality_check = gr.Checkbox(label="AI Quality Verification", value=True, info="Extra pass for accuracy")
                        
                        gr.Markdown("### 4. Output Format")
                        with gr.Group():
                            burn_subtitles = gr.Checkbox(label="Burn Subtitles into Video", value=False, info="Re-encodes video (Slower)")
                            with gr.Row(visible=False) as burn_options_row:
                                font_name = gr.Dropdown(["Arial", "Helvetica", "Roboto", "Times New Roman"], value="Arial", label="Font")
                                font_size = gr.Slider(12, 48, value=24, step=2, label="Size")
                                subtitle_position = gr.Dropdown(
                                    ["Bottom Center", "Bottom Left", "Bottom Right", "Top Center", "Center"], 
                                    value="Bottom Center", 
                                    label="Position"
                                )
                            
                            # Toggle visibility of burn options
                            burn_subtitles.change(
                                fn=lambda x: gr.update(visible=x),
                                inputs=[burn_subtitles],
                                outputs=[burn_options_row]
                            )

                        gr.Markdown("### ") # Spacer
                        submit_btn = gr.Button("Start Translation", variant="primary", elem_classes="submit-btn", size="lg")
                    
                    # Right Column: Results
                    with gr.Column(scale=1, variant="panel"):
                        gr.Markdown("### Processing Status")
                        status_output = gr.Textbox(label="Log", placeholder="Waiting for job...", interactive=False, max_lines=4)
                        
                        gr.Markdown("### Outputs")
                        file_output = gr.File(label="Download Files", interactive=False, height=100)
                        preview_output = gr.Code(label="Subtitle Preview", language="markdown", lines=15, interactive=False, elem_classes="srt-preview")
                        
                        open_folder_btn = gr.Button("📂 Open Output Folder", variant="secondary", elem_classes="secondary-btn")

                gr.Markdown(
                    """
                    <div class="footer">
                        AI Video Translator • Internal Tool
                    </div>
                    """
                )

        # Tab 2: Settings
        with gr.TabItem("⚙️ Settings"):
            with gr.Column(elem_classes="container"):
                gr.Markdown("## App Configuration")
                gr.Markdown("Settings are stored securely in your browser's local storage.")
                
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### OpenAI API")
                        openai_api_key = gr.Textbox(
                            label="API Key", 
                            placeholder="sk-...", 
                            type="password"
                        )
                        openai_base_url = gr.Textbox(
                            label="Base URL", 
                            placeholder="https://api.openai.com/v1"
                        )
                    
                    with gr.Column():
                        gr.Markdown("### Integration Tokens")
                        hf_token = gr.Textbox(
                            label="Hugging Face Token", 
                            placeholder="hf_...", 
                            type="password",
                            info="Required for Speaker Diarization (pyannote/speaker-diarization)"
                        )

                gr.Markdown("### Defaults")
                with gr.Row():
                    whisper_model = gr.Textbox(label="Whisper Model", value="whisper-1")
                    llm_model = gr.Textbox(label="LLM Model", value="gpt-4o")
                    output_dir = gr.Textbox(label="Output Directory", value="output")
                
                save_btn = gr.Button("Save Settings", variant="primary", elem_classes="submit-btn")
                save_status = gr.Textbox(label="Status", interactive=False, show_label=False)
                
                save_btn.click(
                    fn=None,
                    inputs=[openai_api_key, openai_base_url, whisper_model, llm_model, output_dir, hf_token],
                    outputs=[save_status],
                    js=js_save_settings
                )

    open_folder_btn.click(
        fn=open_output_folder,
        inputs=[output_dir],
        outputs=[status_output]
    )

    # Load settings from browser storage on launch
    demo.load(
        fn=None,
        inputs=None,
        outputs=[openai_api_key, openai_base_url, whisper_model, llm_model, output_dir, hf_token],
        js=js_load_settings
    )

    submit_btn.click(
        fn=transcode_process,
        inputs=[
            video_input, source_lang, target_lang, 
            openai_api_key, openai_base_url, whisper_model, llm_model, output_dir, 
            use_diarization, hf_token, use_quality_check,
            burn_subtitles, font_name, font_size, subtitle_position
        ],
        outputs=[status_output, file_output, preview_output]
    )

if __name__ == "__main__":
    demo.launch()
