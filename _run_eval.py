import sys, os
sys.stdout.reconfigure(encoding='ascii', errors='replace')
sys.stderr.reconfigure(encoding='ascii', errors='replace')
os.chdir(r'c:\Users\Remo\Documents\MyHR')
sys.path.insert(0, '.')

import traceback
try:
    from training.train_evaluator import main
    main()
except Exception:
    traceback.print_exc()
    sys.exit(1)
