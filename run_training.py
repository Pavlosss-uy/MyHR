"""Wrapper to run training scripts with proper error handling."""
import sys, os, traceback

os.environ["PYTHONUTF8"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_evaluator():
    try:
        from training.train_evaluator import main
        main()
    except Exception:
        traceback.print_exc()
        return False
    return True

def run_cross_encoder():
    try:
        from training.train_cross_encoder import main
        main()
    except Exception:
        traceback.print_exc()
        return False
    return True

def run_preprocessing():
    try:
        from training.preprocessing import generate_combined_dataset
        generate_combined_dataset(
            "./data/Audio_Speech_Actors_01-24",
            "./data/archive/AudioWAV",
            "./data/raw/IEMOCAP"
        )
    except Exception:
        traceback.print_exc()
        return False
    return True

def run_emotion():
    try:
        from training.train_emotion import main
        main()
    except Exception:
        traceback.print_exc()
        return False
    return True

if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "evaluator"
    
    funcs = {
        "evaluator": run_evaluator,
        "cross_encoder": run_cross_encoder,
        "preprocessing": run_preprocessing,
        "emotion": run_emotion,
    }
    
    if step in funcs:
        success = funcs[step]()
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown step: {step}")
        print(f"Available: {list(funcs.keys())}")
        sys.exit(1)
