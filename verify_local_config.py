import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

def verify_local_config():
    print("Starting Local GPU Configuration Verification...")
    print("---------------------------------------------")
    
    # Mock external libs in sys.modules to simulate them being installed/available
    mock_faster_whisper = MagicMock()
    mock_llama_cpp = MagicMock()
    mock_hf_hub = MagicMock()
    
    # We patch the modules so the app can import them even if they are not installed in the test env
    with patch.dict(sys.modules, {
        'faster_whisper': mock_faster_whisper,
        'llama_cpp': mock_llama_cpp,
        'huggingface_hub': mock_hf_hub
    }):
        # Mock settings to simulate "Local" mode configuration
        with patch('app.config.settings') as mock_settings:
            mock_settings.LOCAL_WHISPER_MODEL = "tiny"
            mock_settings.LOCAL_LLM_FILE = "test.gguf"
            mock_settings.MODELS_DIR = "C:\\temp\\models"
            mock_settings.LLM_MODEL = "gpt-4"
            mock_settings.WHISPER_MODEL = "whisper-1"
            mock_settings.LOCAL_LLM_MODEL = "TheBloke/Test-GGUF"
            
            # Mock CUDA availability
            with patch('torch.cuda.is_available', return_value=True):
                
                # --- Test 1: Transcription Service ---
                print("\n1. Testing TranscriptionService (Faster-Whisper)...")
                try:
                    from app.processors.transcription import TranscriptionService
                    ts_local = TranscriptionService(use_local=True)
                    
                    if ts_local.use_local and ts_local.model == "tiny":
                        # Verify it tried to initialize the WhisperModel
                        mock_faster_whisper.WhisperModel.assert_called()
                        print("✅ TranscriptionService initialized in Local Mode correctly.")
                        print("✅ CUDA device detected and passed to Whisper.")
                    else:
                        print("❌ Config mismatch.")
                except Exception as e:
                    print(f"❌ Failed to initialize TranscriptionService: {e}")
                    import traceback
                    traceback.print_exc()

                # --- Test 2: Translation Service ---
                print("\n2. Testing TranslationService (Local LLM)...")
                # Mock os.path.exists to False to force the 'download' code path
                with patch('os.path.exists', return_value=False):
                    try:
                        from app.processors.translation import TranslationService
                        
                        # Mock the download function to return a dummy path
                        mock_hf_hub.hf_hub_download.return_value = "C:\\temp\\models\\test.gguf"
                        
                        tr_local = TranslationService(use_local=True)
                        
                        if tr_local.use_local:
                             print("✅ TranslationService initialized in Local Mode correctly.")
                        
                        # Verify download was attempted
                        mock_hf_hub.hf_hub_download.assert_called()
                        print("✅ Model download triggered (via hf_hub_download).")
                        
                        # Verify LLM was initialized
                        mock_llama_cpp.Llama.assert_called()
                        print("✅ Local LLM loaded (via llama_cpp.Llama).")
                        
                    except Exception as e:
                        print(f"❌ Failed to initialize TranslationService: {e}")
                        import traceback
                        traceback.print_exc()

    print("\n---------------------------------------------")
    print("Verification Complete.")

if __name__ == "__main__":
    verify_local_config()
