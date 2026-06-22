"""Phase 1 health check — run from inside MyHR/"""
import sys, os, json, torch
import numpy as np

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

PASS = '[PASS]'
FAIL = '[FAIL]'
WARN = '[WARN]'

results = []

# ── 1.1  Evaluator loads with input_dim=768 ──────────────────────────────
try:
    from models.registry import registry
    ev = registry.load_evaluator()
    first_layer_in = list(ev.parameters())[0].shape[1]
    assert first_layer_in == 768, f'input_dim={first_layer_in}'
    dummy = torch.zeros(1, 768)
    out = ev.evaluate_answer(dummy)
    assert set(out.keys()) >= {'relevance', 'clarity', 'technical_depth', 'overall'}
    results.append(
        f"{PASS} 1.1  Evaluator: input_dim=768, forward pass OK  "
        f"(rel={out['relevance']:.1f} cla={out['clarity']:.1f} dep={out['technical_depth']:.1f})"
    )
except Exception as e:
    results.append(f'{FAIL} 1.1  Evaluator: {e}')

# ── 1.2  squeeze() fix — batch size 1 does not crash ────────────────────
try:
    src = open('training/train_evaluator.py', encoding='utf-8', errors='ignore').read()
    assert '.squeeze().tolist()' not in src, 'Old .squeeze().tolist() still present'
    assert 'view(-1).tolist()' in src
    results.append(f'{PASS} 1.2  squeeze fix: .view(-1).tolist() confirmed in train_evaluator.py')
except Exception as e:
    results.append(f'{FAIL} 1.2  squeeze fix: {e}')

# ── 1.3  generate_eval_data.py uses ChatGroq ─────────────────────────────
try:
    src = open('training/generate_eval_data.py', encoding='utf-8', errors='ignore').read()
    assert 'langchain_openai' not in src, 'langchain_openai still imported'
    assert 'ChatGroq' in src
    results.append(f'{PASS} 1.3  generate_eval_data.py uses ChatGroq (no langchain_openai)')
except Exception as e:
    results.append(f'{FAIL} 1.3  ChatGroq fix: {e}')

# ── 1.4  UTF-8 reconfigure in all training/generate scripts ─────────────
try:
    import glob
    scripts = glob.glob('training/train_*.py') + glob.glob('training/generate_*.py')
    missing = [s for s in scripts if 'reconfigure' not in open(s, encoding='utf-8', errors='ignore').read()]
    if missing:
        results.append(f"{WARN} 1.4  UTF-8 fix missing in: {[os.path.basename(m) for m in missing]}")
    else:
        results.append(f'{PASS} 1.4  UTF-8 reconfigure present in all {len(scripts)} training/generate scripts')
except Exception as e:
    results.append(f'{FAIL} 1.4  UTF-8 check: {e}')

# ── 1.5  Training data files exist with correct shape ───────────────────
try:
    checks = [
        ('data/eval_training_data.json',  'samples'),
        ('data/ranking_pairs.json',       None),
        ('data/performance_data.json',    'samples'),
    ]
    for path, key in checks:
        assert os.path.exists(path), f'{path} missing'
        data = json.load(open(path))
        count = len(data[key]) if key else len(data)
        results.append(f'{PASS} 1.5  {path}: {count:,} records')

    ev_data = json.load(open('data/eval_training_data.json'))
    dim = len(ev_data['samples'][0]['features'])
    assert dim == 768, f'features dim={dim}'
    results.append(f'{PASS} 1.5  eval_training_data feature dim = {dim}  (matches 768-D evaluator)')
except Exception as e:
    results.append(f'{FAIL} 1.5  Training data: {e}')

# ── 1.6  Emotion model + preprocessing CSV ──────────────────────────────
try:
    assert os.path.exists('data/interview_emotions_train.csv'), 'CSV missing'
    with open('data/interview_emotions_train.csv') as f:
        rows = sum(1 for _ in f) - 1
    em = registry.load_emotion_model()
    results.append(f'{PASS} 1.6  Emotion model loaded; preprocessing CSV has {rows:,} rows')
except Exception as e:
    results.append(f'{FAIL} 1.6  Emotion model/data: {e}')

# ── 1.7  All 8 checkpoints present ──────────────────────────────────────
try:
    ckpts = [
        'models/checkpoints/evaluator_v1.pt',
        'models/checkpoints/emotion_finetuned_v2.pt',
        'models/checkpoints/skill_matcher_v1.pt',
        'models/checkpoints/difficulty_engine_v1.pt',
        'models/checkpoints/difficulty_ppo_v1.zip',
        'models/checkpoints/performance_predictor_v1.pt',
        'models/checkpoints/candidate_ranker_v1.pt',
        'models/checkpoints/scorer_v2.pt',
    ]
    missing = [c for c in ckpts if not os.path.exists(c)]
    if missing:
        results.append(f'{FAIL} 1.7  Missing checkpoints: {missing}')
    else:
        results.append(f'{PASS} 1.7  All 8 checkpoints present')
except Exception as e:
    results.append(f'{FAIL} 1.7  Checkpoint check: {e}')

# ── 1.8  PPO loads, predicts, and outperforms REINFORCE ─────────────────
try:
    diff = registry.load_difficulty_engine(use_ppo=True)
    obs = np.array([0.7, 0.5, 0.6, 0.8, 0.4, 0.6], dtype=np.float32)
    action, _ = diff.predict(obs, deterministic=True)
    next_diff = int(action) + 1
    assert 1 <= next_diff <= 5, f'next_diff={next_diff} out of range'
    comp = json.load(open('training/results/difficulty_comparison.json'))
    ppo_pct  = comp['ppo']['pct_in_target_zone']
    rein_pct = comp['reinforce']['pct_in_target_zone']
    assert ppo_pct > rein_pct, f'PPO {ppo_pct:.1f} not > REINFORCE {rein_pct:.1f}'
    results.append(
        f"{PASS} 1.8  PPO loaded, predicted diff={next_diff}/5  "
        f"(PPO {ppo_pct:.1f}% vs REINFORCE {rein_pct:.1f}% in-zone)"
    )
except Exception as e:
    results.append(f'{FAIL} 1.8  PPO: {e}')

# ── Summary ──────────────────────────────────────────────────────────────
# ── Phase 2 spot-checks ──────────────────────────────────────────────────

# 2.1 CandidateScoringMLP wired into evaluate_answer_node
try:
    src = open('agent.py', encoding='utf-8', errors='ignore').read()
    assert 'load_scorer' in src, 'load_scorer not called in agent.py'
    assert 'EmbeddingExtractor' in src, 'EmbeddingExtractor not imported'
    assert 'mod1_score' in src, 'mod1_score blend not found'
    results.append(f'{PASS} 2.1  CandidateScoringMLP wired: load_scorer + EmbeddingExtractor + mod1_score blend')
except Exception as e:
    results.append(f'{FAIL} 2.1  CandidateScoringMLP: {e}')

# 2.2 load_performance_predictor has try/except / graceful None
try:
    src = open('models/registry.py', encoding='utf-8', errors='ignore').read()
    assert 'load_performance_predictor' in src
    # Check it returns None gracefully (not a bare torch.load)
    assert 'omitting performance forecast' in src or 'predictor"] = None' in src
    results.append(f'{PASS} 2.2  load_performance_predictor graceful None on missing checkpoint')
except Exception as e:
    results.append(f'{FAIL} 2.2  load_performance_predictor: {e}')

# 2.3 POST /candidates/rank endpoint exists in server.py
try:
    src = open('server.py', encoding='utf-8', errors='ignore').read()
    assert '/candidates/rank' in src, '/candidates/rank endpoint missing'
    assert 'extract_candidate_features' in src, 'feature_store not called'
    assert 'cosine_similarity' in src, 'cosine similarity not used'
    results.append(f'{PASS} 2.3  POST /candidates/rank endpoint present with feature_store + cosine ranking')
except Exception as e:
    results.append(f'{FAIL} 2.3  /candidates/rank: {e}')

# 2.4 Cross-encoder retired (NOT PRODUCTION marker)
try:
    src = open('training/train_cross_encoder.py', encoding='utf-8', errors='ignore').read()
    assert 'NOT PRODUCTION' in src, 'NOT PRODUCTION marker missing from train_cross_encoder.py'
    agent_src = open('agent.py', encoding='utf-8', errors='ignore').read()
    assert 'cross_encoder' not in agent_src.lower(), 'cross_encoder still referenced in agent.py'
    results.append(f'{PASS} 2.4  Cross-encoder retired: NOT PRODUCTION marker present, not wired into agent.py')
except Exception as e:
    results.append(f'{FAIL} 2.4  Cross-encoder: {e}')

# 2.5 database.py removed
try:
    assert not os.path.exists('database.py'), 'database.py still present'
    req = open('requirements.txt', encoding='utf-8', errors='ignore').read().lower()
    assert 'sqlalchemy' not in req, 'SQLAlchemy still in requirements.txt'
    results.append(f'{PASS} 2.5  database.py deleted, SQLAlchemy removed from requirements.txt')
except Exception as e:
    results.append(f'{FAIL} 2.5  Legacy DB cleanup: {e}')

print()
print('=' * 65)
print('  Phase 1 + Phase 2 Health Check')
print('=' * 65)
for r in results:
    print(' ', r)
print('=' * 65)
fails = [r for r in results if r.strip().startswith('[FAIL]')]
warns = [r for r in results if r.strip().startswith('[WARN]')]
passed = len(results) - len(fails) - len(warns)
print(f'  Result: {passed} passed  |  {len(warns)} warnings  |  {len(fails)} failed')
print('=' * 65)
sys.exit(1 if fails else 0)
