import warnings
from typing import Iterable, Optional, Sequence, Union

import matplotlib.pyplot as plt
import numpy as np
import shap
import torch


class ModelExplainer:
    """SHAP-based explainer for feature-driven PyTorch interview models.

    Expected feature order:
    ["skill_match", "relevance", "clarity", "depth",
     "confidence", "consistency", "gaps_inverted", "experience"]
    """

    def __init__(self, model, feature_names: Sequence[str]):
        self.model = model
        self.feature_names = list(feature_names)

    def _resolve_model(self):
        """Return the underlying PyTorch model when a wrapper object is passed."""
        if isinstance(self.model, torch.nn.Module):
            return self.model

        for attr in ("model", "evaluator", "network"):
            candidate = getattr(self.model, attr, None)
            if isinstance(candidate, torch.nn.Module):
                return candidate

        raise TypeError(
            "ModelExplainer expected a torch.nn.Module or a wrapper exposing one "
            "via `.model`, `.evaluator`, or `.network`."
        )

    def _predict_overall_score(self, x: np.ndarray) -> np.ndarray:
        """Return a 1D numpy array of overall scores for SHAP."""
        model = self._resolve_model()
        model.eval()

        with torch.no_grad():
            t = torch.tensor(x, dtype=torch.float32)
            output = model(t)

            # Multi-head raw output: tuple/list of tensors (relevance, clarity, depth)
            if isinstance(output, (tuple, list)) and len(output) >= 3:
                tensors = [o.detach().cpu().numpy().reshape(-1) for o in output[:3]]
                stacked = np.vstack(tensors)
                return stacked.mean(axis=0)

            # Dict output support, e.g. custom wrappers
            if isinstance(output, dict):
                if "overall" in output:
                    value = output["overall"]
                else:
                    keys = [k for k in ("relevance", "clarity", "technical_depth") if k in output]
                    if not keys:
                        raise ValueError("Model output dict does not contain explainable score keys.")
                    value = np.mean([output[k] for k in keys], axis=0)
                return np.asarray(value, dtype=np.float32).reshape(-1)

            # Single tensor output model
            if isinstance(output, torch.Tensor):
                arr = output.detach().cpu().numpy()
                if arr.ndim == 2 and arr.shape[1] > 1:
                    return arr.mean(axis=1)
                return arr.reshape(-1)

            raise TypeError(f"Unsupported model output type for SHAP: {type(output)!r}")

    @staticmethod
    def _to_numpy(x: Union[np.ndarray, torch.Tensor, Sequence[Sequence[float]]]) -> np.ndarray:
        if isinstance(x, np.ndarray):
            return x.astype(np.float32)
        if isinstance(x, torch.Tensor):
            return x.detach().cpu().numpy().astype(np.float32)
        return np.asarray(x, dtype=np.float32)

    def explain_prediction(
        self,
        features_tensor: Union[np.ndarray, torch.Tensor, Sequence[Sequence[float]]],
        background_data: Union[np.ndarray, torch.Tensor, Sequence[Sequence[float]]],
        nsamples: Union[str, int] = "auto",
    ):
        """Return SHAP values showing which features drove the prediction.

        Parameters
        ----------
        features_tensor:
            One sample or batch of samples to explain.
        background_data:
            Representative background samples used by KernelExplainer.
        nsamples:
            Passed to shap_values() to control approximation effort.
        """
        features_np = self._to_numpy(features_tensor)
        background_np = self._to_numpy(background_data)

        if features_np.ndim == 1:
            features_np = features_np.reshape(1, -1)
        if background_np.ndim == 1:
            background_np = background_np.reshape(1, -1)

        if features_np.shape[1] != len(self.feature_names):
            raise ValueError(
                f"Expected {len(self.feature_names)} features, got {features_np.shape[1]}"
            )

        if background_np.shape[1] != len(self.feature_names):
            raise ValueError(
                f"Background data must have {len(self.feature_names)} features, "
                f"got {background_np.shape[1]}"
            )

        # KernelExplainer is model-agnostic and works for the current feature-based setup.
        explainer = shap.KernelExplainer(self._predict_overall_score, background_np)
        shap_values = explainer.shap_values(features_np, nsamples=nsamples)
        expected_value = explainer.expected_value
        return shap_values, expected_value

    def plot_waterfall(
        self,
        shap_values,
        features: Union[np.ndarray, torch.Tensor, Sequence[Sequence[float]]],
        expected_value: Optional[Union[float, np.ndarray]] = None,
        sample_index: int = 0,
        max_display: Optional[int] = None,
        save_path: Optional[str] = None,
        show: bool = False,
    ):
        """Generate a SHAP waterfall plot for one sample."""
        features_np = self._to_numpy(features)
        if features_np.ndim == 1:
            features_np = features_np.reshape(1, -1)

        # Some SHAP versions return a list for multi-output models. Our score is scalar,
        # but this branch keeps the method defensive.
        values = shap_values[0] if isinstance(shap_values, list) and len(shap_values) == 1 else shap_values
        values = np.asarray(values)

        if values.ndim == 1:
            values = values.reshape(1, -1)

        base_value = expected_value
        if isinstance(base_value, np.ndarray):
            base_value = float(np.ravel(base_value)[0])
        if base_value is None:
            warnings.warn(
                "expected_value was not provided; defaulting to 50.0 as a visualization baseline.",
                stacklevel=2,
            )
            base_value = 50.0

        explanation = shap.Explanation(
            values=values[sample_index],
            base_values=base_value,
            feature_names=self.feature_names,
            data=features_np[sample_index],
        )

        shap.plots.waterfall(explanation, max_display=max_display or len(self.feature_names), show=show)

        if save_path:
            plt.savefig(save_path, bbox_inches="tight")
        if not show:
            plt.close()

        return explanation
