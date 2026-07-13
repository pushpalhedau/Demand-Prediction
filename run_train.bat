@echo off
cd /d "c:\Users\Pushpal Hedau\RealEstate\Demand-Prediction"
set PYTHONUNBUFFERED=1
set OMP_NUM_THREADS=1
set CUDA_VISIBLE_DEVICES=
echo Starting training pipeline...
venv\Scripts\python.exe train_models.py > train_log.txt 2>&1
echo Exit code: %ERRORLEVEL%
echo Done. Check train_log.txt for output.
