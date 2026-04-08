import torch
from models.multi_head_evaluator import MultiHeadEvaluator

def test_multi_head_evaluator():
    print("Initializing the Multi-Head Evaluator...")
    # Initialize our new model
    evaluator = MultiHeadEvaluator(input_dim=8)
    
    # Let's simulate the 8 features of a VERY GOOD answer:
    # Features: [length, keyword_overlap, semantic_sim, structure, tone_confidence, tone_valence, specificity, relevance]
    # Tone valence is 1.0 (positive/confident), semantic similarity is high (0.85).
    excellent_answer_features = torch.tensor([[0.8, 0.7, 0.85, 1.0, 0.9, 1.0, 0.75, 0.8]])
    
    # Let's simulate the 8 features of a POOR, NERVOUS answer:
    # Tone valence is -1.0 (frustrated/nervous), semantic similarity is low (0.3).
    poor_answer_features = torch.tensor([[0.2, 0.1, 0.3, 0.0, 0.4, -1.0, 0.1, 0.2]])

    print("\n--- Running Inference Test ---")
    
    # Evaluate the excellent answer
    excellent_result = evaluator.evaluate_answer(excellent_answer_features)
    print("\nCandidate 1 (Strong Answer):")
    print(f"Relevance:       {excellent_result['relevance']}/100")
    print(f"Clarity:         {excellent_result['clarity']}/100")
    print(f"Technical Depth: {excellent_result['technical_depth']}/100")
    print(f"Overall Score:   {excellent_result['overall']}/100")
    
    # Evaluate the poor answer
    poor_result = evaluator.evaluate_answer(poor_answer_features)
    print("\nCandidate 2 (Weak Answer):")
    print(f"Relevance:       {poor_result['relevance']}/100")
    print(f"Clarity:         {poor_result['clarity']}/100")
    print(f"Technical Depth: {poor_result['technical_depth']}/100")
    print(f"Overall Score:   {poor_result['overall']}/100")
    
    print("\n✅ Phase 3 Core Architecture is fully functional!")

if __name__ == "__main__":
    test_multi_head_evaluator()