# scripts/run_silver_transformation.py
from src.transformation.silver import transform_bronze_to_silver


def run_silver_pipeline():
    print("🔄 Starting Silver Transformation Pipeline...\n")
    
    # Step 1: Bronze -> Silver
    transform_bronze_to_silver()
    
    print("✅ Silver Transformation Pipeline Completed Successfully!\n")

if __name__ == "__main__":
    run_silver_pipeline()