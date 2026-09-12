# scripts/run_gold_transformation.py
from src.transformation.gold import transform_silver_to_gold


def run_gold_pipeline():
    print("🔄 Starting Gold Transformation Pipeline...\n")
    
    transform_silver_to_gold()
    
    print("✅ Gold Transformation Pipeline Completed Successfully!\n")

if __name__ == "__main__":
    run_gold_pipeline()