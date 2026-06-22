"""
utils/trainer_logger.py — Task 3.9
Thin wrapper that logs to MLflow (when available) in addition to TensorBoard.

MLflow activates automatically when MLFLOW_TRACKING_URI is set in the
environment (or when mlflow is importable and no URI is set, it uses the
local ./mlruns directory).

Usage in a training script:
    from utils.trainer_logger import ExperimentLogger
    logger = ExperimentLogger("train_evaluator", params={"lr": 1e-3, "epochs": 200})
    ...
    logger.log_metric("loss/train", loss_val, step=epoch)
    ...
    logger.finish()
"""
import os
from typing import Any, Dict, Optional


class ExperimentLogger:
    def __init__(
        self,
        run_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.run_name = run_name
        self._mlflow = None
        self._run = None

        try:
            import mlflow  # type: ignore

            tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "./mlruns")
            mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment(run_name)
            self._run = mlflow.start_run(run_name=run_name)
            self._mlflow = mlflow

            if params:
                mlflow.log_params(params)

            print(f"[MLflow] Tracking run '{run_name}' at {tracking_uri}")
        except ImportError:
            print(f"[MLflow] mlflow not installed — metrics logged to TensorBoard only.")

    def log_metric(self, key: str, value: float, step: Optional[int] = None) -> None:
        if self._mlflow and self._run:
            self._mlflow.log_metric(key, value, step=step)

    def log_params(self, params: Dict[str, Any]) -> None:
        if self._mlflow and self._run:
            self._mlflow.log_params(params)

    def log_artifact(self, local_path: str) -> None:
        if self._mlflow and self._run:
            self._mlflow.log_artifact(local_path)

    def finish(self) -> None:
        if self._mlflow and self._run:
            self._mlflow.end_run()
            self._run = None
