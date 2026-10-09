import sys
import json


def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
    protocol = sys.__stdout__
    sys.stdout = sys.stderr

    try:
        from app.processors.transcription import create_transcription_service
        service = create_transcription_service(model=model_name)
    except Exception as e:
        print(json.dumps({"type": "error", "message": str(e)}), file=protocol, flush=True)
        return

    print(json.dumps({"type": "ready"}), file=protocol, flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            if req.get("cmd") == "quit":
                break
            segments = service.transcribe_segment(
                req["wav"], float(req["offset"]), language=req.get("language")
            )
            print(json.dumps({"type": "segments", "segments": segments}), file=protocol, flush=True)
        except Exception as e:
            print(json.dumps({"type": "error", "message": str(e)}), file=protocol, flush=True)


if __name__ == "__main__":
    main()
